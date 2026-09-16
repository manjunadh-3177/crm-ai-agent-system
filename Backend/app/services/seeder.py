from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.agent_approval import AgentApproval
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.deal_stage import DealStage
from app.models.email_draft import EmailDraft
from app.models.meeting import Meeting
from app.models.task import Task
from app.services.agent_runs import create_agent_run
from app.services.audit import log_audit

logger = logging.getLogger(__name__)

async def seed_current_workspace(db: AsyncSession, team_id: UUID, user_id: str) -> dict:
    """Seed the specified team with dummy demo data."""
    logger.info("Seeding workspace for team %s", team_id)

    # 1. Deals Stages (fetch existing)
    stages_result = await db.execute(select(DealStage).order_by(DealStage.probability))
    stages = stages_result.scalars().all()
    if not stages:
        return {"error": "No deal stages found. Please run the base seeder first."}

    stage_map = {s.name.lower(): s for s in stages}
    default_stage = stages[0]

    def get_stage(name: str) -> DealStage:
        return stage_map.get(name.lower(), default_stage)

    # 2. Accounts
    accounts_data = [
        {"name": "Northstar Realty", "domain": "northstar-realty.example.com", "industry": "Real Estate"},
        {"name": "UrbanNest Properties", "domain": "urbannest.example.com", "industry": "Real Estate"},
        {"name": "Prime Estates", "domain": "primeestates.example.com", "industry": "Real Estate"},
        {"name": "Skyline Ventures", "domain": "skyline.example.com", "industry": "Investment"},
        {"name": "GreenField Homes", "domain": "greenfield.example.com", "industry": "Real Estate"},
    ]

    # Check if already seeded to prevent duplicates on rerun
    existing_accs = await db.execute(select(Account.domain).where(Account.team_id == team_id))
    existing_domains = {r for r in existing_accs.scalars()}

    if "northstar-realty.example.com" in existing_domains:
        logger.info("Workspace already seeded, skipping to prevent duplicates.")
        return {"status": "skipped", "reason": "Already seeded"}

    created_accounts = []
    for ad in accounts_data:
        account = Account(
            team_id=team_id,
            name=ad["name"],
            domain=ad["domain"],
            industry=ad["industry"]
        )
        db.add(account)
        created_accounts.append(account)

    await db.flush()

    # 3. Contacts
    contacts_data = [
        ("Sarah", "Connor", "sarah@northstar-realty.example.com", created_accounts[0], 85, "warm", "Active buyer"),
        ("John", "Smith", "john.s@urbannest.example.com", created_accounts[1], 45, "cold", "Unresponsive"),
        ("Emily", "Davis", "emily.d@primeestates.example.com", created_accounts[2], 90, "hot", "Ready to sign"),
        ("Michael", "Johnson", "michael@skyline.example.com", created_accounts[3], 60, "warm", "Evaluating options"),
        ("Jessica", "Williams", "jessica@greenfield.example.com", created_accounts[4], 75, "warm", "Good fit"),
        ("David", "Brown", "david.b@example.com", None, 30, "cold", "Just browsing"),
        ("Ashley", "Jones", "ashley.j@northstar-realty.example.com", created_accounts[0], 80, "warm", "Secondary contact"),
    ]

    created_contacts = []
    for c in contacts_data:
        contact = Contact(
            team_id=team_id,
            first_name=c[0],
            last_name=c[1],
            email=c[2],
            account_id=c[3].id if c[3] else None,
            lead_score=c[4],
            lead_tier=c[5],
            lead_reason=c[6],
            consent_email=True
        )
        db.add(contact)
        created_contacts.append(contact)

    await db.flush()

    # 4. Deals
    now = datetime.now(UTC)
    deals_data = [
        ("Northstar Expansion", created_accounts[0], created_contacts[0], "Proposal", Decimal("150000.00"), 60, 15),
        ("UrbanNest Renewal", created_accounts[1], created_contacts[1], "Lead", Decimal("50000.00"), 10, 45),
        ("Prime Estates Contract", created_accounts[2], created_contacts[2], "Negotiation", Decimal("250000.00"), 90, 5),
        ("Skyline Integration", created_accounts[3], created_contacts[3], "Qualified", Decimal("85000.00"), 40, 30),
        ("GreenField Setup", created_accounts[4], created_contacts[4], "Won", Decimal("120000.00"), 100, -5),
    ]

    created_deals = []
    for d in deals_data:
        deal = Deal(
            team_id=team_id,
            name=d[0],
            account_id=d[1].id,
            contact_id=d[2].id,
            stage_id=get_stage(d[3]).id,
            amount=d[4],
            probability=d[5],
            expected_close_date=(now + timedelta(days=d[6])).date(),
            owner_user_id=UUID(user_id) if user_id else None
        )
        db.add(deal)
        created_deals.append(deal)

    await db.flush()

    # 5. Tasks
    tasks_data = [
        ("Send brochure to Sarah", created_contacts[0], created_deals[0], "todo", 2),
        ("Follow up with John", created_contacts[1], created_deals[1], "todo", 5),
        ("Pricing review with Emily", created_contacts[2], created_deals[2], "in_progress", 1),
        ("Contract review Skyline", created_contacts[3], created_deals[3], "todo", 7),
        ("Onboarding GreenField", created_contacts[4], created_deals[4], "done", -1),
    ]

    for t in tasks_data:
        task = Task(
            team_id=team_id,
            title=t[0],
            contact_id=t[1].id,
            deal_id=t[2].id,
            status=t[3],
            due_date=now + timedelta(days=t[4]),
            owner_user_id=UUID(user_id) if user_id else None
        )
        db.add(task)

    # 6. Meetings
    meetings_data = [
        ("Discovery Call - Northstar", created_contacts[0], created_deals[0], "scheduled", 1, 60),
        ("Review Sync - Prime", created_contacts[2], created_deals[2], "scheduled", 3, 30),
        ("Intro Call - Skyline", created_contacts[3], created_deals[3], "completed", -2, 45),
    ]

    for m in meetings_data:
        start_t = now + timedelta(days=m[4])
        meeting = Meeting(
            team_id=team_id,
            title=m[0],
            contact_id=m[1].id,
            deal_id=m[2].id,
            status=m[3],
            start_time=start_t,
            end_time=start_t + timedelta(minutes=m[5]),
            organizer_id=UUID(user_id) if user_id else None
        )
        db.add(meeting)

    # 8. Approvals
    draft_1 = EmailDraft(
        team_id=team_id,
        contact_id=created_contacts[0].id,
        deal_id=created_deals[0].id,
        subject="Following up on our proposal",
        body="<p>Hi Sarah,</p><br><p>I wanted to follow up on the proposal we discussed. Let me know if you have any questions.</p>",
        generation_context={"intent": "follow_up"}
    )
    db.add(draft_1)
    await db.flush()

    approval_1 = AgentApproval(
        team_id=team_id,
        contact_id=created_contacts[0].id,
        deal_id=created_deals[0].id,
        draft_id=draft_1.id,
        type="email",
        status="pending",
    )
    db.add(approval_1)

    draft_2 = EmailDraft(
        team_id=team_id,
        contact_id=created_contacts[2].id,
        deal_id=created_deals[2].id,
        subject="Contract details",
        body="<p>Hi Emily,</p><br><p>Please find the contract details attached. Looking forward to getting this signed!</p>",
        generation_context={"intent": "contract_send"}
    )
    db.add(draft_2)
    await db.flush()

    approval_2 = AgentApproval(
        team_id=team_id,
        contact_id=created_contacts[2].id,
        deal_id=created_deals[2].id,
        draft_id=draft_2.id,
        type="email",
        status="pending",
    )
    db.add(approval_2)

    await db.commit()

    # 9. History / Activity Feed & Swarm Console
    await log_audit(db, action="contact.created", entity_type="contact", entity_id=str(created_contacts[0].id), team_id=team_id, actor_type="user", actor_id=user_id)
    await log_audit(db, action="deal.stage_changed", entity_type="deal", entity_id=str(created_deals[0].id), team_id=team_id, actor_type="user", actor_id=user_id)

    # Swarm console history
    run = await create_agent_run(
        db,
        team_id=team_id,
        graph_name="swarm_followup",
        event_name="deal.stage_changed",
        deal_id=created_deals[0].id,
        status_value="completed",
        result="draft_created",
        duration_ms=12400
    )
    await log_audit(
        db,
        action="graph.swarm.completed",
        entity_type="agent_run",
        entity_id=str(run.id),
        actor_type="system",
        team_id=team_id,
        metadata={"graph_name": "swarm_followup", "result": "draft_created", "status": "completed", "logs": ["lead qualified", "research complete", "draft generated"]}
    )

    await db.commit()

    return {
        "status": "success",
        "accounts_created": len(created_accounts),
        "contacts_created": len(created_contacts),
        "deals_created": len(created_deals),
        "tasks_created": len(tasks_data),
        "meetings_created": len(meetings_data),
        "approvals_created": 2
    }
