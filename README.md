# Acufy CRM

An AI-augmented CRM where a multi-agent system does the busywork of sales follow-up — lead qualification, contact research, email drafting, deal-rescue detection, and proposal generation — while every AI-generated action pauses for human approval before it goes out.

## The problem

Sales reps spend a large share of their time on low-judgment, repetitive work around every deal: qualifying new leads, researching contacts before outreach, drafting follow-up emails, noticing deals that have gone quiet, and scheduling next steps. This work is easy to defer or forget, and quality depends heavily on individual rep discipline — leads go cold and deals stall silently.

Acufy CRM automates that judgment layer directly on top of CRM events, instead of just being a system of record:

- A new lead is created → a qualifier agent scores it, a research agent gathers context, a nurturer agent drafts a personalized outreach email.
- A deal goes quiet → a watch agent flags it, an orchestrator agent decides the next action, a scheduler agent proposes a meeting slot and creates a task.
- A deal reaches a proposal stage → a proposal agent drafts the proposal automatically.

Every AI-drafted email passes through a compliance check and then **pauses for human approval** before sending — the system drafts, a person decides. Every decision is written to an audit log.

## Architecture

```
                     ┌─────────────────────────┐
   React SPA  ─────▶ │   FastAPI (REST + WS)   │
  (Auth0 login)      └────────────┬────────────┘
                                   │
                    domain event (deal.created, etc.)
                                   │
                     ┌─────────────▼────────────┐
                     │   Event bus (in-proc)     │──▶ Redis pub/sub ──▶ WebSocket bridge ──▶ live UI updates
                     └─────────────┬────────────┘
                                   │
                     ┌─────────────▼────────────┐
                     │  LangGraph agent graph    │
                     │  (per workflow: NewLead,  │
                     │   DealRescue, Proposal)   │
                     └─────────────┬────────────┘
                                   │
                degree of trust: agents run, but nothing
                sends until a human clicks Approve
                                   │
                     ┌─────────────▼────────────┐
                     │  Compliance check          │
                     │  → Approval queue (paused) │
                     │  → Audit log                │
                     └────────────────────────────┘
```

**Backend** — Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + PostgreSQL (pgvector-enabled), Redis, `arq` for background jobs, LangGraph for multi-agent orchestration, Langfuse for LLM tracing/observability, JWT/Auth0 for auth, native WebSockets for live updates.

**Frontend** — React 19 + TypeScript + Vite, Auth0 for authentication.

**Infra** — Docker Compose (Postgres, Redis, backend, frontend/nginx), GitHub Actions CI (lint, type-check, test, build, docker-compose validation).

## Agents

| Agent | Trigger | Job |
|---|---|---|
| Lead Qualifier | `contact.created` | Scores a new lead |
| Research | `contact.created` | Gathers contextual notes on a contact |
| Nurturer | `contact.created` (post-qualify) | Drafts a personalized outreach email |
| Opportunity Watch | `deal.rescue` scan | Flags deals going stale/at risk |
| Deal Orchestrator | `deal.rescue` | Decides the next action on an at-risk deal |
| Scheduler | `deal.rescue` | Proposes a meeting slot, creates a follow-up task |
| Proposal | `deal.stage_changed` | Drafts a proposal document |
| Compliance | every drafted email | Blocks sends that fail policy checks |
| Forecast | on demand | Pipeline/forecast summaries for managers |

Agents are composed into three LangGraph state machines — `NewLeadGraph`, `DealRescueGraph`, and `ProposalGraph` — each with retry-on-failure per node, full run/state persistence (`AgentRun`, `AuditLog`), and an approval-pause node before anything reaches a contact. See [`Backend/app/ai/graphs/crm_orchestration.py`](Backend/app/ai/graphs/crm_orchestration.py).

## Human-in-the-loop safety

No AI-generated email or SMS is ever sent automatically. Every draft:

1. Passes a rule-based compliance check.
2. Is written to an `AgentApproval` row with status `pending`.
3. Surfaces in the Approvals queue in the UI, live via WebSocket.
4. Only sends once a human clicks Approve — which is logged to the audit trail along with who approved it and when.

This is a deliberate design choice: an AI system that silently emails contacts on your behalf is not one most sales teams — or regulators — would trust. Draft-then-approve keeps a human accountable for every outbound message while still eliminating the manual drafting work.

## Running it

### Docker (recommended)

```powershell
docker compose up --build
```

- Frontend: http://localhost
- Backend: http://localhost:8000 (`/docs` for the OpenAPI schema)
- Postgres: localhost:5432
- Redis: localhost:6379

Reset all state: `docker compose down -v`

### Local, without Docker

**Backend**
```powershell
cd Backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend**
```powershell
cd Frontend
npm install
npm run dev
```

Validate: `GET http://127.0.0.1:8000/health` → `{"status":"ok"}`; frontend at `http://127.0.0.1:5173`.

## Configuration

Copy `.env.example` to `.env` (and `Frontend/.env.example` to `Frontend/.env`) and fill in your own values — LLM provider API key (Groq/OpenAI/Anthropic/Gemini all supported through one gateway), database URL, Auth0 credentials if you want real login instead of the local demo mode, and optionally Resend/Twilio credentials for real email/SMS delivery. Nothing is required to run in local demo mode; auth is disabled by default and email/SMS providers fall back to console/stub implementations.

## CI/CD

GitHub Actions runs on every push/PR to `main`:
- **Backend** — dependency install, `compileall` syntax check, `ruff` + `mypy` lint, `pytest`.
- **Frontend** — install, production build, lint.
- **Docker** — validates `docker-compose.yml`.

A manual-trigger `deploy.yml` workflow exists as a placeholder for a future cloud deployment pipeline.

## Known limitations / next steps

- Frontend is organized into per-page components (`src/pages/`) and reusable components/modals (`src/components/`), but doesn't yet use a router — page switching is handled by local state rather than URL-based routing.
- Test coverage currently covers core business logic (compliance checks, lead scoring) and the health endpoint; expanding coverage to the agent graphs and full approval flow end-to-end is the next priority.
- No production deployment is live yet — Docker Compose covers local/single-host use.
- The app has not yet been run and manually verified end-to-end (Docker Compose up, clicking through each page); only static compilation, type-checking, and unit tests have been verified so far.
