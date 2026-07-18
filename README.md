# IncidentIQ

**AI-powered root cause analysis for production incidents.**

When a service breaks, someone has to read the logs, check what shipped recently, and work out
which change caused it - under pressure, at 3am. IncidentIQ does that correlation automatically
and returns ranked root cause hypotheses with supporting evidence, typically in under two minutes.

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-ff6b35)](https://langchain-ai.github.io/langgraph/)
[![Cloud Run](https://img.shields.io/badge/Google_Cloud_Run-deployed-4285F4)](https://cloud.google.com/run)

**Live API:** https://incidentiq-384221529062.us-central1.run.app
**Interactive docs:** https://incidentiq-384221529062.us-central1.run.app/docs

---

## What makes it different

Most incident tooling shows you data. IncidentIQ reasons over it.

| | Traditional tooling | IncidentIQ |
|---|---|---|
| Log search | You write the query | Fetched automatically for the incident window |
| Deploy correlation | You check GitHub manually | Commits matched to error timing |
| Conclusion | You form it | Ranked hypotheses with confidence scores |
| Evidence | You gather it | Every hypothesis links to a log line or commit SHA |

It never invents an answer. If no logs are available for the incident window, the analysis fails
with an explanation rather than returning a confident guess.

---

## How it works

Five specialist agents run as a directed graph. Triage sets the investigation window, then log
analysis and deploy correlation run **in parallel** -they read independent sources, so running
them sequentially would double the wait.

```mermaid
graph TD
    A[Incident reported] --> B[Triage Agent]
    B -->|severity, affected services,<br/>investigation window| C[Log Analysis Agent]
    B --> D[Deploy Correlation Agent]
    C -->|error patterns,<br/>first failure time| E[Synthesis Agent]
    D -->|commits, changed files,<br/>risk signals| E
    E -->|ranked hypotheses| F[Report Agent]
    F --> G[RCA Report]
    G --> H[Webhook delivery]

    style B fill:#4285F4,color:#fff
    style C fill:#34A853,color:#fff
    style D fill:#34A853,color:#fff
    style E fill:#FBBC04,color:#000
    style F fill:#EA4335,color:#fff
    style G fill:#1a1a1a,color:#fff
```

**A key design rule:** deterministic tools run before the LLM. Raw logs are parsed with regex to
extract timestamps, error levels, and frequency stats first. Only those extracted signals reach
Gemini -never 50,000 raw log lines. This keeps analysis fast, cheap, and inside context limits.

---

## Request lifecycle

```mermaid
sequenceDiagram
    participant C as Customer
    participant API as FastAPI
    participant P as Pipeline
    participant L as Log source
    participant G as Gemini

    C->>API: POST /incidents
    API-->>C: 202 Accepted (incident_id)
    Note over API,P: Response returns immediately;<br/>analysis runs in the background
    P->>L: Fetch logs for window
    L-->>P: Log entries
    P->>G: Reason over extracted signals
    G-->>P: Ranked hypotheses
    P->>C: Webhook: RCA report
    C->>API: GET /incidents/{id}/report
    API-->>C: 200 Full report
```

---

## Quick start

**1. Register and get an API key**

```bash
curl -X POST https://incidentiq-384221529062.us-central1.run.app/management/organisations \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme SRE Team", "admin_email": "sre@acme.com"}'
```

The API key is returned **once** and never stored in readable form. Save it.

**2. Connect a log source** *(optional -you can upload logs manually instead)*

```bash
curl -X POST https://incidentiq-384221529062.us-central1.run.app/management/log-source \
  -H "Authorization: Bearer iqk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "gcp_logging",
    "credentials": {"project_id": "my-project", "service_account_key": "..."},
    "config_metadata": {"service_name": "auth-service"}
  }'
```

**3. Report an incident**

```bash
curl -X POST https://incidentiq-384221529062.us-central1.run.app/incidents \
  -H "Authorization: Bearer iqk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Auth service returning 500s since 14:32",
    "github_repo_url": "https://github.com/acme/auth-service",
    "reported_at": "2026-07-18T14:35:00Z"
  }'
```

With a log source configured, analysis starts immediately. Otherwise upload logs to
`POST /incidents/{id}/logs` to trigger it.

**4. Get the report**

```bash
curl https://incidentiq-384221529062.us-central1.run.app/incidents/INC-20260718-A3F9C12B/report \
  -H "Authorization: Bearer iqk_live_..."
```

---

## API reference

All endpoints require `Authorization: Bearer <api_key>` except where marked public.

### Incidents

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/incidents` | Create an incident and start analysis · `202` |
| `POST` | `/incidents/{id}/logs` | Upload a log file (multipart) |
| `GET` | `/incidents/{id}` | Poll analysis status and progress |
| `GET` | `/incidents/{id}/report` | Retrieve the completed RCA report |
| `POST` | `/incidents/{id}/feedback` | Confirm or reject a hypothesis |

### Management

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/management/organisations` | Register an organisation · **public** |
| `POST` | `/management/log-source` | Configure a log connector |
| `POST` | `/management/webhook` | Configure RCA report delivery |
| `GET` | `/management/organisations/me` | View current configuration |
| `GET` | `/health` | Health check · **public** |

### Supported log sources

| Type | Value | Notes |
|---|---|---|
| Google Cloud Logging | `gcp_logging` | Supports custom log filters |
| AWS CloudWatch | `aws_cloudwatch` | Defaults to `/aws/ecs/{service}` log group |
| Datadog | `datadog` | Filters by service tag |
| Manual upload | `manual` | No credentials required |

---

## Architecture

```mermaid
graph LR
    subgraph Client
        SRE[SRE / Monitoring]
    end

    subgraph "Cloud Run"
        MW[API key auth<br/>middleware]
        API[FastAPI]
        PIPE[LangGraph<br/>pipeline]
    end

    subgraph "Data"
        DB[(PostgreSQL<br/>Neon)]
        SM[Secret Manager]
    end

    subgraph External
        GCP[Cloud Logging]
        AWS[CloudWatch]
        DD[Datadog]
        GH[GitHub API]
        GEM[Gemini 1.5 Pro]
    end

    SRE -->|Bearer token| MW --> API --> PIPE
    API --- DB
    PIPE --- DB
    PIPE -->|fetch credentials| SM
    PIPE --> GCP & AWS & DD
    PIPE --> GH
    PIPE --> GEM
    PIPE -->|RCA report| SRE

    style MW fill:#EA4335,color:#fff
    style API fill:#009688,color:#fff
    style PIPE fill:#ff6b35,color:#fff
    style DB fill:#336791,color:#fff
```

**Multi-tenancy** is enforced at the middleware layer. Every request resolves to an organisation
before reaching a route handler, and all queries are scoped to that organisation. Customer
credentials are stored in Google Cloud Secret Manager -never in the database.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | Async throughout, automatic OpenAPI docs |
| Orchestration | LangGraph | Native fan-out/fan-in, typed state between agents |
| LLM | Gemini 1.5 Pro | Large context window; `temperature=0.1` for analytical determinism |
| Database | PostgreSQL + JSONB | Relational integrity where it matters, flexible shape for agent findings |
| ORM | SQLAlchemy 2.0 async | Non-blocking DB access under an async server |
| Migrations | Alembic | Versioned, reversible schema changes |
| Secrets | GCP Secret Manager | Customer credentials never touch the application database |
| Runtime | Cloud Run + Docker | Alpine multi-stage build, non-root user |
| CI/CD | GitHub Actions | Auto-deploys on push to `main` |

---

## Running locally

**Prerequisites:** Python 3.11+, PostgreSQL, a Gemini API key, a GitHub personal access token.

```bash
git clone https://github.com/Maheesh09/IncidentIQ.git
cd IncidentIQ

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then fill in your values
alembic upgrade head
uvicorn main:app --reload
```

Open http://localhost:8000/docs for interactive API documentation.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://user:pass@host/incidentiq` |
| `GEMINI_API_KEY` | ✅ | Google AI Studio API key |
| `GITHUB_PAT` | ✅ | Personal access token with `repo` scope |
| `GCP_PROJECT_ID` | -| Required only for Secret Manager |
| `DEFAULT_LOOKBACK_MINUTES` | -| Investigation window size (default `30`) |
| `MAX_LOG_SIZE_BYTES` | -| Upload limit (default `10485760`) |

### Docker

```bash
docker build -t incidentiq .
docker run -p 8080:8080 --env-file .env incidentiq
```

---

## Project structure

```
IncidentIQ/
├── main.py                 App entry point, lifespan, router registration
├── config.py               Settings via pydantic-settings
├── database.py             Async engine and session factory
├── agents/                 The five LangGraph agents
│   ├── triage.py           Severity, affected services, investigation window
│   ├── log_analysis.py     Regex extraction, then LLM reasoning
│   ├── deploy_correlation.py   GitHub commits matched to error timing
│   ├── synthesis.py        Ranked hypotheses with confidence scores
│   └── report.py           Final human-readable RCA
├── pipeline/
│   ├── graph.py            Graph wiring, fan-out/fan-in
│   ├── state.py            Typed state shared between nodes
│   └── runner.py           Background execution and webhook delivery
├── routers/
│   ├── incidents.py        Incident lifecycle endpoints
│   └── management.py       Organisation, log source, webhook config
├── tools/
│   ├── log_parser.py       Deterministic regex extraction
│   ├── github_client.py    GitHub API with rate limit backoff
│   └── connectors/         GCP, AWS, Datadog, manual
├── middleware/auth.py      API key authentication
├── models/                 SQLAlchemy ORM and Pydantic schemas
└── alembic/versions/       Database migrations
```

---

## Database schema

```mermaid
erDiagram
    ORGANISATIONS ||--o{ API_KEYS : has
    ORGANISATIONS ||--o| LOG_SOURCE_CONFIGS : has
    ORGANISATIONS ||--o| WEBHOOK_CONFIGS : has
    ORGANISATIONS ||--o{ INCIDENTS : owns
    INCIDENTS ||--o{ AGENT_RUNS : tracks
    INCIDENTS ||--o| RCA_REPORTS : produces
    INCIDENTS ||--o| FEEDBACK : receives
```

`agent_runs` records timing and findings per agent, so a slow or failing stage can be identified
without re-running the analysis.

---

## Reliability

| Concern | Handling |
|---|---|
| Transient agent failures | Automatic retry before the incident is marked failed |
| GitHub rate limits | Exponential backoff |
| Partial agent failure | Errors flow into graph state; synthesis proceeds with partial data |
| No logs available | Incident fails with an explanation -never a fabricated report |
| Malformed logs | Falls back to passing the raw chunk to the LLM |
| Invalid input | Rejected at the schema boundary before any work is queued |

---

## Roadmap

- [x] **Phase 1** -Core pipeline: five agents, five endpoints, four tables
- [x] **Phase 2** -Retry logic, rate limit backoff, confidence calibration, input validation
- [x] **Phase 3** -Multi-tenancy, API key auth, log connectors, webhooks, Cloud Run, CI/CD
- [ ] **Phase 4** -Slack and PagerDuty integration, historical dashboard, GitLab support

---

## Contributing

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
Development happens on `dev` and merges to `main` via pull request, which triggers deployment.

---

## License

MIT
