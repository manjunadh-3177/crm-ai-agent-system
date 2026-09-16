"""Add team_id columns to tenant workflow tables for Stage 7B."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.db import engine


STATEMENTS = [
    "ALTER TABLE email_drafts ADD COLUMN IF NOT EXISTS team_id UUID",
    "UPDATE email_drafts ed SET team_id = c.team_id FROM contacts c WHERE ed.contact_id = c.id AND ed.team_id IS NULL",
    "ALTER TABLE email_drafts ALTER COLUMN team_id SET NOT NULL",
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE table_name='email_drafts' AND constraint_name='fk_email_drafts_team_id') THEN ALTER TABLE email_drafts ADD CONSTRAINT fk_email_drafts_team_id FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE; END IF; END $$",
    "ALTER TABLE agent_approvals ADD COLUMN IF NOT EXISTS team_id UUID",
    "UPDATE agent_approvals aa SET team_id = c.team_id FROM contacts c WHERE aa.contact_id = c.id AND aa.team_id IS NULL",
    "ALTER TABLE agent_approvals ALTER COLUMN team_id SET NOT NULL",
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE table_name='agent_approvals' AND constraint_name='fk_agent_approvals_team_id') THEN ALTER TABLE agent_approvals ADD CONSTRAINT fk_agent_approvals_team_id FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE; END IF; END $$",
    "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS team_id UUID",
    "UPDATE agent_runs ar SET team_id = d.team_id FROM deals d WHERE ar.deal_id = d.id AND ar.team_id IS NULL",
    "ALTER TABLE agent_runs ALTER COLUMN team_id SET NOT NULL",
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE table_name='agent_runs' AND constraint_name='fk_agent_runs_team_id') THEN ALTER TABLE agent_runs ADD CONSTRAINT fk_agent_runs_team_id FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE; END IF; END $$",
]


async def main() -> None:
    async with engine.begin() as connection:
        for statement in STATEMENTS:
            await connection.execute(text(statement))
    print("Stage 7B tenant columns updated.")


if __name__ == "__main__":
    asyncio.run(main())
