"""WebSocket routes for live CRM notifications."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.auth import resolve_websocket_auth_context
from app.events.ws import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Connect a team-scoped live notification socket."""
    try:
        auth = await resolve_websocket_auth_context(websocket)
    except Exception:
        await websocket.close(code=4401)
        return

    await manager.connect(auth.team_id, websocket)
    await websocket.send_json(
        {
            "type": "connection",
            "status": "live",
            "team_id": str(auth.team_id),
        }
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(auth.team_id, websocket)
