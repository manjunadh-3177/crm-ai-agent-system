from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Account,
    AgentApproval,
    AuditLog,
    Contact,
    Deal,
    DealStage,
    Meeting,
    Task,
    User,
)
from app.services.products import seed_demo_products_if_empty

DEFAULT_STAGES: list[tuple[str, bool]] = [
    ("Lead", False),
    ("Qualified", False),
    ("Proposal", False),
    ("Negotiation", False),
    ("Won", True),
    ("Lost", True),
]

PIPELINE_SAMPLE_ACCOUNTS: list[dict[str, str]] = [
    {"name": "Northstar Logistics", "domain": "northstarlogistics.com", "industry": "Logistics"},
    {"name": "BrightPath Health", "domain": "brightpathhealth.com", "industry": "Healthcare"},
    {"name": "PeakWorks Manufacturing", "domain": "peakworksmfg.com", "industry": "Manufacturing"},
    {"name": "HarborLane Finance", "domain": "harborlane.com", "industry": "Financial Services"},
]

PIPELINE_SAMPLE_CONTACTS: list[dict[str, Any]] = [
    {"first_name": "Ava", "last_name": "Martinez", "email": "ava.martinez@northstarlogistics.com", "job_title": "VP Operations", "lead_tier": "Hot"},
    {"first_name": "Noah", "last_name": "Patel", "email": "noah.patel@brightpathhealth.com", "job_title": "Director of IT", "lead_tier": "Warm"},
    {"first_name": "Mia", "last_name": "Johnson", "email": "mia.johnson@peakworksmfg.com", "job_title": "Head of Revenue", "lead_tier": "Hot"},
    {"first_name": "Liam", "last_name": "Chen", "email": "liam.chen@harborlane.com", "job_title": "Procurement Lead", "lead_tier": "Warm"},
    {"first_name": "Emma", "last_name": "Davis", "email": "emma.davis@atlaslogic.io", "job_title": "Founder", "lead_tier": "Warm"},
    {"first_name": "James", "last_name": "Garcia", "email": "james.garcia@latticeops.io", "job_title": "COO", "lead_tier": "Cold"},
]

PIPELINE_SAMPLE_DEALS: list[dict[str, Any]] = [
    {"name": "Northstar Routing Expansion", "amount": "42000.00", "probability": 20, "stage": "Lead", "account_index": 0, "contact_index": 0, "days": 45},
    {"name": "BrightPath Patient Portal", "amount": "28500.00", "probability": 25, "stage": "Lead", "account_index": 1, "contact_index": 1, "days": 38},
    {"name": "PeakWorks Renewal", "amount": "36000.00", "probability": 45, "stage": "Qualified", "account_index": 2, "contact_index": 2, "days": 30},
    {"name": "HarborLane Risk Dashboard", "amount": "52000.00", "probability": 50, "stage": "Qualified", "account_index": 3, "contact_index": 3, "days": 42},
    {"name": "AtlasLogic Starter Rollout", "amount": "14800.00", "probability": 65, "stage": "Proposal", "account_index": None, "contact_index": 4, "days": 18},
    {"name": "Northstar Fleet Analytics", "amount": "67000.00", "probability": 70, "stage": "Proposal", "account_index": 0, "contact_index": 0, "days": 21},
    {"name": "PeakWorks Plant Pilot", "amount": "24500.00", "probability": 80, "stage": "Negotiation", "account_index": 2, "contact_index": 2, "days": 12},
    {"name": "HarborLane Compliance Add-on", "amount": "31000.00", "probability": 85, "stage": "Negotiation", "account_index": 3, "contact_index": 3, "days": 9},
    {"name": "BrightPath Support Upgrade", "amount": "19500.00", "probability": 100, "stage": "Won", "account_index": 1, "contact_index": 1, "days": -4},
    {"name": "LatticeOps Replatform", "amount": "22000.00", "probability": 0, "stage": "Lost", "account_index": None, "contact_index": 5, "days": -7},
]


async def ensure_default_pipeline_stages(session: AsyncSession, team_id: UUID) -> list[DealStage]:
    """Ensure the canonical six-stage pipeline exists for the team."""
    result = await session.execute(
        select(DealStage).where(DealStage.team_id == team_id).order_by(DealStage.position, DealStage.created_at)
    )
    stages = list(result.scalars().all())
    by_name = {stage.name.lower(): stage for stage in stages}

    changed = False
    for position, (name, is_closed) in enumerate(DEFAULT_STAGES, start=1):
        stage = by_name.get(name.lower())
        if stage is None:
            stage = DealStage(team_id=team_id, name=name, position=position, is_closed=is_closed)
            session.add(stage)
            stages.append(stage)
            changed = True
        elif stage.position != position or stage.is_closed != is_closed:
            stage.position = position
            stage.is_closed = is_closed
            changed = True

    if changed:
        await session.flush()

    return sorted(stages, key=lambda stage: (stage.position, stage.created_at))


async def seed_pipeline_data_if_empty(session: AsyncSession, team_id: UUID, user_id: str | None = None) -> bool:
    """Seed realistic pipeline data for a dev workspace that has no deals."""
    settings = get_settings()
    if settings.app_env.lower() not in {"development", "dev", "local"}:
        return False

    deal_count = await session.scalar(select(func.count()).select_from(Deal).where(Deal.team_id == team_id))
    if deal_count and deal_count > 0:
        await ensure_default_pipeline_stages(session, team_id)
        await session.commit()
        return False

    stages = await ensure_default_pipeline_stages(session, team_id)
    stage_map = {stage.name: stage for stage in stages}

    owner_uuid = None
    if user_id:
        try:
            owner_uuid = UUID(str(user_id))
        except ValueError:
            owner_uuid = None

    if owner_uuid is None:
        owner_uuid = await session.scalar(select(User.id).where(User.team_id == team_id).order_by(User.created_at).limit(1))

    accounts: list[Account] = []
    for account_data in PIPELINE_SAMPLE_ACCOUNTS:
        account = Account(team_id=team_id, **account_data)
        session.add(account)
        accounts.append(account)
    await session.flush()

    contacts: list[Contact] = []
    for index, contact_data in enumerate(PIPELINE_SAMPLE_CONTACTS):
        account_id = accounts[index].id if index < len(accounts) else None
        contact = Contact(
            team_id=team_id,
            account_id=account_id,
            consent_email=True,
            consent_sms=index % 2 == 0,
            **contact_data,
        )
        session.add(contact)
        contacts.append(contact)
    await session.flush()

    for deal_data in PIPELINE_SAMPLE_DEALS:
        account_index = deal_data["account_index"]
        contact_index = deal_data["contact_index"]
        stage = stage_map[deal_data["stage"]]
        session.add(
            Deal(
                team_id=team_id,
                name=deal_data["name"],
                amount=Decimal(deal_data["amount"]),
                currency="USD",
                probability=deal_data["probability"],
                expected_close_date=date.today() + timedelta(days=deal_data["days"]),
                owner_user_id=owner_uuid,
                stage_id=stage.id,
                account_id=accounts[account_index].id if account_index is not None else None,
                contact_id=contacts[contact_index].id if contact_index is not None else None,
            )
        )

    await seed_demo_products_if_empty(session, team_id=team_id)
    await session.commit()
    return True

async def seed_starter_data_if_empty(session: AsyncSession, team_id: UUID, user_id: str) -> bool:
    """Seed starter CRM data for a new team if they have no records."""
    # Check if we already have contacts (cheapest check)
    contact_count = await session.scalar(
        select(func.count()).select_from(Contact).where(Contact.team_id == team_id)
    )
    if contact_count and contact_count > 0:
        return False

    # 1. Ensure Default Stages
    stages_result = await session.execute(
        select(DealStage).where(DealStage.team_id == team_id).order_by(DealStage.position)
    )
    stages = list(stages_result.scalars().all())
    if not stages:
        for pos, (name, is_closed) in enumerate(DEFAULT_STAGES, start=1):
            stage = DealStage(team_id=team_id, name=name, position=pos, is_closed=is_closed)
            session.add(stage)
            stages.append(stage)
        await session.flush()

    stage_map = {s.name: s for s in stages}

    # 2. Accounts
    acc1 = Account(team_id=team_id, name="Stark Industries", domain="stark.com", industry="Technology")
    acc2 = Account(team_id=team_id, name="Wayne Enterprises", domain="wayne.com", industry="Conglomerate")
    session.add_all([acc1, acc2])
    await session.flush()

    # 3. Contacts
    c1 = Contact(team_id=team_id, account_id=acc1.id, first_name="Tony", last_name="Stark", email="tony@stark.com", lead_tier="Hot")
    c2 = Contact(team_id=team_id, account_id=acc2.id, first_name="Bruce", last_name="Wayne", email="bruce@wayne.com", lead_tier="Warm")
    c3 = Contact(team_id=team_id, first_name="Peter", last_name="Parker", email="peter@dailybugle.com", lead_tier="Cold")
    session.add_all([c1, c2, c3])
    await session.flush()

    # 4. Deals
    d1 = Deal(
        team_id=team_id,
        account_id=acc1.id,
        contact_id=c1.id,
        name="Arc Reactor Expansion",
        amount=Decimal("50000.00"),
        probability=80,
        stage_id=stage_map["Proposal"].id,
        owner_user_id=user_id,
        expected_close_date=date.today() + timedelta(days=30)
    )
    d2 = Deal(
        team_id=team_id,
        account_id=acc2.id,
        contact_id=c2.id,
        name="Bat-Gadget Pilot",
        amount=Decimal("15000.00"),
        probability=40,
        stage_id=stage_map["Qualified"].id,
        owner_user_id=user_id,
        expected_close_date=date.today() + timedelta(days=60)
    )
    d3 = Deal(
        team_id=team_id,
        contact_id=c3.id,
        name="Freelance Photography Contract",
        amount=Decimal("2000.00"),
        probability=10,
        stage_id=stage_map["Lead"].id,
        owner_user_id=user_id,
        expected_close_date=date.today() + timedelta(days=14)
    )
    session.add_all([d1, d2, d3])
    await session.flush()

    # 5. Tasks
    t1 = Task(team_id=team_id, assigned_user_id=user_id, title="Follow up with Tony", description="Check status of the proposal", due_at=datetime.now(UTC) + timedelta(days=1), status="open")
    t2 = Task(team_id=team_id, assigned_user_id=user_id, title="Draft Wayne contract", description="Need legal review", due_at=datetime.now(UTC) + timedelta(days=3), status="open")
    session.add_all([t1, t2])

    # 6. Meeting
    m1 = Meeting(
        team_id=team_id,
        contact_id=c1.id,
        deal_id=d1.id,
        title="Strategy Review",
        description="Discuss next steps",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, minutes=60),
        status="scheduled"
    )
    session.add(m1)

    # 7. Approval item
    app1 = AgentApproval(
        team_id=team_id,
        contact_id=c2.id,
        deal_id=d2.id,
        type="email_draft",
        status="pending",
        created_at=datetime.now(UTC)
    )
    session.add(app1)

    # 8. Activity Logs
    log1 = AuditLog(
        team_id=team_id,
        actor_id=user_id,
        actor_type="user",
        action="contact.created",
        entity_type="contact",
        entity_id=str(c1.id),
        message="Created Tony Stark contact"
    )
    log2 = AuditLog(
        team_id=team_id,
        actor_id="ai-agent",
        actor_type="ai",
        action="deal.updated",
        entity_type="deal",
        entity_id=str(d1.id),
        message="AI increased probability based on sentiment"
    )
    session.add_all([log1, log2])

    # Ensure products exist
    await seed_demo_products_if_empty(session, team_id=team_id)

    await session.commit()
    return True
