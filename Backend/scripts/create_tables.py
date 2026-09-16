"""Create local database tables without Alembic."""

import asyncio
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.db import create_all_tables, get_table_names, engine
from sqlalchemy import text
from app.models.meeting import Meeting  # Ensure Meeting is in metadata
from app.models.note import Note        # Ensure Note is in metadata
from app.models.task import Task        # Ensure Task is in metadata
from app.models.automation import AutomationRule # Ensure AutomationRule is in metadata
from app.models.deal import Deal
from app.models.contact import Contact
from app.models.email_message import EmailMessage
from app.models.notification import Notification
from app.models.sms_message import SMSMessage

async def main() -> None:
    """Create all registered tables and apply safe migrations."""
    print("Initializing database...")
    await create_all_tables()
    
    # Safe migrations for recently added fields
    migrations = [
        # DealOrchestratorAgent fields
        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS deal_health VARCHAR(20) DEFAULT 'healthy' NOT NULL",
        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS deal_reason VARCHAR(500)",
        
        # LeadQualifierAgent fields
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS job_title VARCHAR(100)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS description VARCHAR(1000)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS account_id UUID",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS lead_score INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS lead_tier VARCHAR(20)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS lead_reason VARCHAR(500)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS preferred_timezone VARCHAR(100)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS working_days VARCHAR(100)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS working_hours_start VARCHAR(20)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS working_hours_end VARCHAR(20)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS preferred_meeting_windows VARCHAR(255)",
        "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS blocked_days VARCHAR(255)",

        # Automation V2 fields
        "ALTER TABLE automation_rules ADD COLUMN IF NOT EXISTS description VARCHAR(500)",
        "ALTER TABLE automation_rules ADD COLUMN IF NOT EXISTS run_count INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE automation_rules ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ",
    ]
    
    async with engine.begin() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                print(f"Executed: {sql}")
            except Exception as e:
                print(f"Skipped migration ({sql}): {e}")

    tables = await get_table_names()
    print("\nCurrent tables:")
    for table_name in tables:
        print(f"- {table_name}")


if __name__ == "__main__":
    asyncio.run(main())
