"""Seed minimal demo CRM data for local UI work."""

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.db import AsyncSessionLocal
from app.models import Account, Contact, Deal, DealStage, Team, User, UserRole
from app.services.products import seed_demo_products_if_empty


DEFAULT_STAGES: list[tuple[str, bool]] = [
    ("Lead", False),
    ("Qualified", False),
    ("Proposal", False),
    ("Negotiation", False),
    ("Won", True),
    ("Lost", True),
]

CONTACTS: list[dict[str, str | bool | None]] = [
    {"first_name": "Ava", "last_name": "Martinez", "email": "ava.martinez@northstar.io", "phone": "+1-555-0101", "consent_sms": True, "consent_email": True},
    {"first_name": "Noah", "last_name": "Patel", "email": "noah.patel@brightpath.io", "phone": "+1-555-0102", "consent_sms": False, "consent_email": True},
    {"first_name": "Mia", "last_name": "Johnson", "email": "mia.johnson@peakworks.io", "phone": "+1-555-0103", "consent_sms": True, "consent_email": True},
    {"first_name": "Liam", "last_name": "Chen", "email": "liam.chen@craftline.io", "phone": "+1-555-0104", "consent_sms": True, "consent_email": False},
    {"first_name": "Emma", "last_name": "Davis", "email": "emma.davis@harborlane.io", "phone": "+1-555-0105", "consent_sms": False, "consent_email": True},
    {"first_name": "Ethan", "last_name": "Brown", "email": "ethan.brown@ridgepoint.io", "phone": "+1-555-0106", "consent_sms": True, "consent_email": True},
    {"first_name": "Sophia", "last_name": "Wilson", "email": "sophia.wilson@crestgrid.io", "phone": "+1-555-0107", "consent_sms": False, "consent_email": True},
    {"first_name": "James", "last_name": "Garcia", "email": "james.garcia@latticeops.io", "phone": "+1-555-0108", "consent_sms": True, "consent_email": True},
    {"first_name": "Olivia", "last_name": "Taylor", "email": "olivia.taylor@atlaslogic.io", "phone": "+1-555-0109", "consent_sms": True, "consent_email": True},
    {"first_name": "Benjamin", "last_name": "Thomas", "email": "benjamin.thomas@solidroute.io", "phone": "+1-555-0110", "consent_sms": False, "consent_email": True},
]

ACCOUNTS: list[dict[str, str | None]] = [
    {"name": "Northstar Logistics", "domain": "northstarlogistics.com", "industry": "Logistics"},
    {"name": "BrightPath Health", "domain": "brightpathhealth.com", "industry": "Healthcare"},
    {"name": "PeakWorks Manufacturing", "domain": "peakworksmfg.com", "industry": "Manufacturing"},
]


async def ensure_default_stages(session: AsyncSession, team: Team) -> list[DealStage]:
    """Ensure a team has the default pipeline stages."""
    result = await session.execute(
        select(DealStage).where(DealStage.team_id == team.id).order_by(DealStage.position)
    )
    existing = list(result.scalars().all())
    if existing:
        return existing

    stages: list[DealStage] = []
    for position, (name, is_closed) in enumerate(DEFAULT_STAGES, start=1):
        stage = DealStage(team_id=team.id, name=name, position=position, is_closed=is_closed)
        session.add(stage)
        stages.append(stage)

    await session.flush()
    return stages


async def main() -> None:
    """Insert demo data if the CRM is still empty."""
    async with AsyncSessionLocal() as session:
        team_count = await session.scalar(select(func.count()).select_from(Team))
        if team_count and team_count > 0:
            team = await session.scalar(select(Team).order_by(Team.created_at).limit(1))
            if team is not None:
                await seed_demo_products_if_empty(session, team_id=team.id)
                print("Demo seed skipped: teams already exist. Ensured demo products are present.")
            return

        team = Team(name="Acufy Demo Team", timezone="America/New_York")
        session.add(team)
        await session.flush()

        user = User(
            team_id=team.id,
            email="demo.rep@acufycrm.local",
            full_name="Morgan Lee",
            role=UserRole.MANAGER,
        )
        session.add(user)
        await session.flush()

        contacts: list[Contact] = []
        for contact_data in CONTACTS:
            contact = Contact(team_id=team.id, **contact_data)
            session.add(contact)
            contacts.append(contact)
        await session.flush()

        accounts: list[Account] = []
        for account_data in ACCOUNTS:
            account = Account(team_id=team.id, **account_data)
            session.add(account)
            accounts.append(account)
        await session.flush()

        stages = await ensure_default_stages(session, team)
        stage_map = {stage.name: stage for stage in stages}

        deals = [
            Deal(team_id=team.id, name="Northstar Expansion", amount=Decimal("12000.00"), currency="USD", probability=20, expected_close_date=date.today() + timedelta(days=45), owner_user_id=user.id, stage_id=stage_map["Lead"].id, account_id=accounts[0].id),
            Deal(team_id=team.id, name="BrightPath Pilot", amount=Decimal("18000.00"), currency="USD", probability=35, expected_close_date=date.today() + timedelta(days=30), owner_user_id=user.id, stage_id=stage_map["Qualified"].id, account_id=accounts[1].id, contact_id=contacts[1].id),
            Deal(team_id=team.id, name="PeakWorks Renewal", amount=Decimal("26000.00"), currency="USD", probability=55, expected_close_date=date.today() + timedelta(days=25), owner_user_id=user.id, stage_id=stage_map["Proposal"].id, account_id=accounts[2].id, contact_id=contacts[2].id),
            Deal(team_id=team.id, name="Ava Martinez Solo Plan", amount=Decimal("2400.00"), currency="USD", probability=60, expected_close_date=date.today() + timedelta(days=14), owner_user_id=user.id, stage_id=stage_map["Proposal"].id, contact_id=contacts[0].id),
            Deal(team_id=team.id, name="Emma Davis Upsell", amount=Decimal("3400.00"), currency="USD", probability=75, expected_close_date=date.today() + timedelta(days=10), owner_user_id=user.id, stage_id=stage_map["Negotiation"].id, contact_id=contacts[4].id),
            Deal(team_id=team.id, name="Olivia Taylor Closed Won", amount=Decimal("5200.00"), currency="USD", probability=100, expected_close_date=date.today() - timedelta(days=2), owner_user_id=user.id, stage_id=stage_map["Won"].id, contact_id=contacts[8].id),
            Deal(team_id=team.id, name="James Garcia Closed Lost", amount=Decimal("4100.00"), currency="USD", probability=0, expected_close_date=date.today() - timedelta(days=5), owner_user_id=user.id, stage_id=stage_map["Lost"].id, contact_id=contacts[7].id),
        ]
        session.add_all(deals)
        await seed_demo_products_if_empty(session, team_id=team.id)
        await session.commit()
        print("Demo data seeded: 1 team, 1 user, 10 contacts, 3 accounts, 7 deals, 5 products.")


if __name__ == "__main__":
    asyncio.run(main())
