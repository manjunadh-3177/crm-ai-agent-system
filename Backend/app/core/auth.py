"""Auth0 validation and request auth context helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request, WebSocket, status
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.models import Team, User
from app.services.products import seed_demo_products_if_empty

OPEN_PATH_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/ws", "/me", "/api/v1/twilio/webhook")
VALID_ROLES = {"admin", "manager", "rep"}
_jwks_clients: dict[str, Any] = {}
_user_info_cache: dict[str, str] = {}


@dataclass(slots=True)
class AuthContext:
    user_id: str
    email: str
    team_id: UUID
    team_name: str
    role: str
    full_name: str | None
    auth_disabled: bool


async def auth_context_middleware(request: Request, call_next):
    """Resolve auth context once per request and store it on request.state."""
    if request.url.path.startswith(OPEN_PATH_PREFIXES) or request.method == "OPTIONS":
        return await call_next(request)

    try:
        request.state.auth_context = await resolve_request_auth_context(request)
    except HTTPException as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    except Exception as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=401, content={"detail": f"Auth error: {str(exc)}"})

    return await call_next(request)


async def get_auth_context(request: Request) -> AuthContext:
    """Return the auth context already resolved by middleware."""
    context = getattr(request.state, "auth_context", None)
    if context is None:
        context = await resolve_request_auth_context(request)
        request.state.auth_context = context
    return context


async def resolve_request_auth_context(request: Request) -> AuthContext:
    """Resolve request auth using Auth0 JWT or local dev fallback."""
    settings = get_settings()
    if settings.auth_disabled:
        return await _resolve_demo_auth_context()

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    claims = await _validate_auth0_token(token, settings)
    from app.core.db import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        return await _auth_context_from_claims(claims, settings, session, auto_provision=True, token=token)


async def resolve_websocket_auth_context(websocket: WebSocket) -> AuthContext:
    """Resolve WebSocket auth using query token or local dev fallback."""
    settings = get_settings()
    if settings.auth_disabled:
        return await _resolve_demo_auth_context()

    token = websocket.query_params.get("token")
    if not token:
        authorization = websocket.headers.get("Authorization", "")
        scheme, _, header_token = authorization.partition(" ")
        if scheme.lower() == "bearer" and header_token:
            token = header_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing WebSocket auth token.",
        )

    print("WS auth started")
    claims = await _validate_auth0_token(token, settings)
    print("JWT valid")

    from app.core.db import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        context = await _auth_context_from_claims(claims, settings, session, auto_provision=False, token=token)
        print("User found")
        print("WS accepted")
        return context


async def _resolve_demo_auth_context() -> AuthContext:
    """Use the seeded demo team/user when auth is disabled."""
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).order_by(User.created_at).limit(1))
        team = await session.scalar(select(Team).order_by(Team.created_at).limit(1))

        if team is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Demo team not found. Seed demo data first.",
            )

        if user is not None:
            user_team = await session.get(Team, user.team_id)
            await seed_demo_products_if_empty(session, team_id=user.team_id)
            return AuthContext(
                user_id=str(user.id),
                email=user.email,
                team_id=user.team_id,
                team_name=user_team.name if user_team is not None else team.name,
                role=str(user.role.value if hasattr(user.role, "value") else user.role).lower(),
                full_name=user.full_name,
                auth_disabled=True,
            )

        await seed_demo_products_if_empty(session, team_id=team.id)
        return AuthContext(
            user_id="demo-user",
            email="demo@acufycrm.local",
            team_id=team.id,
            team_name=team.name,
            role="admin",
            full_name="Demo User",
            auth_disabled=True,
        )


async def _validate_auth0_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate Auth0 JWT using PyJWKClient."""
    if not settings.auth0_domain or not settings.auth0_audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 settings are not configured.",
        )

    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PyJWT is required for Auth0 validation.",
        ) from exc

    domain = settings.auth0_domain
    if domain not in _jwks_clients:
        url = f"https://{domain}/.well-known/jwks.json"
        _jwks_clients[domain] = PyJWKClient(url)

    jwks_client = _jwks_clients[domain]

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        issuer = f"https://{domain}/"
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=issuer,
        )
    except jwt.exceptions.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        ) from exc
    except jwt.exceptions.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience.",
        ) from exc
    except jwt.exceptions.InvalidIssuerError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer.",
        ) from exc
    except jwt.exceptions.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error decoding token.",
        ) from exc
    except Exception as exc:
        print(f"JWT Validation Error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid auth token: {exc}",
        ) from exc


def _normalize_role(role_value: Any) -> str:
    role = str(role_value or "rep").lower()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unsupported role claim: {role}",
        )
    return role


async def _get_auth0_email(token: str, domain: str, sub: str) -> str:
    """Fetch user email from Auth0 /userinfo if not present in access token."""
    if sub in _user_info_cache:
        return _user_info_cache[sub]

    url = f"https://{domain}/userinfo"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            data = resp.json()
            email = data.get("email", "")
            if email:
                _user_info_cache[sub] = email
                return email
    return ""


async def _auth_context_from_claims(
    claims: dict[str, Any], settings: Settings, session: Any, auto_provision: bool = True, token: str = ""
) -> AuthContext:
    from app.models import Team, User, UserRole
    from app.services.seeding import seed_starter_data_if_empty

    user_id = str(claims.get("sub") or claims.get("user_id") or "")

    # Try custom namespace first
    email = str(
        claims.get(f"{settings.auth0_claims_namespace}/email") or
        claims.get("email") or
        ""
    ).lower()

    if not email and user_id and token and settings.auth0_domain:
        email = await _get_auth0_email(token, settings.auth0_domain, user_id)
        email = email.lower()

    if not user_id or not email:
        print(f"WS/HTTP Auth Rejected: Cannot resolve email for token. user_id={user_id}, email={email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required auth claims (email).",
        )

    # 1. Try to find user by email first (most reliable link)
    user = None
    if email:
        user = await session.scalar(select(User).where(User.email == email))

    if user:
        team_id = user.team_id
        user_team = await session.get(Team, team_id)
        team_name = user_team.name if user_team else "My Workspace"
    else:
        if not auto_provision:
            print(f"WS Auth Rejected: User {email} not found. Refusing to auto-provision during websocket connect.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not fully provisioned. Please complete HTTP login first.",
            )

        # 2. Check if a team_id is provided in the claims (e.g. via custom metadata)
        team_id_value = claims.get(f"{settings.auth0_claims_namespace}/team_id") or claims.get("team_id")
        if team_id_value:
            try:
                team_id = UUID(str(team_id_value))
                user_team = await session.get(Team, team_id)
                if user_team:
                    team_name = user_team.name
                else:
                    team_id_value = None # Team doesn't exist in DB
            except (ValueError, TypeError):
                team_id_value = None

        if not team_id_value:
            # 3. AUTO-PROVISION: Create a new team and user for this first-time Auth0 login
            team_name = f"{claims.get('name', 'My')} Workspace"
            new_team = Team(name=team_name, timezone="UTC")
            session.add(new_team)
            await session.flush() # Get the new_team.id

            team_id = new_team.id

            new_user = User(
                team_id=team_id,
                email=email,
                full_name=claims.get("name") or email.split("@")[0],
                role=UserRole.ADMIN, # First user in team is admin
            )
            session.add(new_user)
            await session.commit() # Commit user first!
            user = new_user
            print("User provisioned successfully")

            # Also seed some initial data so it's not a ghost town
            try:
                print("Starter seed started")
                await seed_starter_data_if_empty(session, team_id=team_id, user_id=str(user.id))
                await session.commit()
            except Exception as e:
                print(f"Starter seed failed: {e}")
                await session.rollback()
        else:
            # User doesn't exist but team_id_value was valid
            # We should still create the user in this team
            new_user = User(
                team_id=team_id,
                email=email,
                full_name=claims.get("name") or email.split("@")[0],
                role=UserRole.REP,
            )
            session.add(new_user)
            await session.commit()
            user = new_user

    user_role_val = user.role.value if hasattr(user.role, "value") else user.role
    role = _normalize_role(
        claims.get(f"{settings.auth0_claims_namespace}/role") or claims.get("role") or user_role_val
    )
    return AuthContext(
        user_id=str(user.id),
        email=user.email,
        team_id=user.team_id,
        team_name=team_name,
        role=role,
        full_name=user.full_name,
        auth_disabled=False,
    )


def requires_role(*roles: str):
    allowed_roles = {_normalize_role(role) for role in roles}

    def role_checker(auth: AuthContext = Depends(get_auth_context)):
        if auth.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {auth.role} is not permitted. Required: {sorted(allowed_roles)}",
            )
        return auth

    return role_checker
