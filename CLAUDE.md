# CLAUDE.md — Agent Guidance for emspProjectv1

This file provides context and conventions for coding agents (Claude Code and similar) working in this repository. Read it before making changes.

---

## Project Overview

This is an **OCPI 2.1.1 hub/platform** implementation that acts as both:
- **CPO** (Charge Point Operator) — manages charging locations, EVSEs, connectors, tariffs
- **EMSP** (e-Mobility Service Provider) — manages sessions, credentials, and roaming agreements

It is a learning/prototype project implementing the [OCPI protocol](https://github.com/ocpi/ocpi) for EV charging interoperability.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI |
| ORM / Models | SQLModel + SQLAlchemy (async) |
| Database | SQLite via `aiosqlite` |
| Python | 3.14 |
| Package manager | `uv` (see `pyproject.toml`) |
| Testing | pytest |

---

## Project Structure

```
app/
  main.py              # FastAPI app, router registration, startup
  database.py          # Async engine, session factory, create_db_and_tables()
  config.py            # App configuration
  crud.py              # CRUD helpers
  models/
    base.py            # OCPIBaseModel (SQLModel base with datetime serializer)
    location.py        # Location table model
    evse.py            # EVSE table model
    connector.py       # Connector table model
    session.py         # Session, ChargingPeriod, CdrDimension table models
    partner.py         # PartnerProfile, Endpoint table models
    tariff.py          # Tariff-related models
    roaming_agreement.py
  api/
    emspversions.py    # EMSP /versions endpoint
    cpoversions.py     # CPO /versions endpoint
    credentials.py     # Generic credentials router
    v2_1_1/
      schemas.py       # Pydantic/SQLModel request+response schemas
      locations.py     # Location routes (CPO + EMSP routers)
      tariffs.py       # Tariff routes
      credentials211.py # Credentials handshake routes
      versiondetails.py
  core/
    middleware.py      # OCPILoggingMiddleware, setup_logging()
    authorization.py   # Token auth helpers
    config.py
    utils.py
  migrations/          # Alembic migration scripts
    versions/
tests/
  test_logging_middleware.py
  test_session_models.py
```

---

## Key Conventions

### Models

- All database table models inherit from `OCPIBaseModel` (defined in `app/models/base.py`) and use `table=True`.
- `OCPIBaseModel` extends `SQLModel` and includes a global `field_serializer` that formats all `datetime` fields as `YYYY-MM-DDTHH:MM:SSZ` (OCPI-compliant UTC).
- Several models use **composite primary keys** — be careful when writing queries or relationships.
- Always import new table models in `app/database.py` so SQLModel's metadata registry sees them before `create_all` is called.

### Schemas

- API request/response schemas live in `app/api/v2_1_1/schemas.py`.
- Schemas use plain Pydantic `BaseModel` or `OCPIBaseModel` (not `table=True`).
- Duplicate enum definitions exist between `schemas.py` and model files (e.g., `SessionStatus`, `AuthMethod`). Prefer importing from models when possible to avoid drift.

### Routers

- Each OCPI module exposes **two routers**: `cporouter` and `emsprouter`.
- Both are registered in `app/main.py` with prefixes like `/ocpi/cpo/2.1.1/<module>` and `/ocpi/emsp/2.1.1/<module>`.
- When adding a new module, follow this pattern and register both routers in `main.py`.

### Database / Sessions

- The engine is async: `create_async_engine` + `AsyncSession`.
- Use `async_session_factory` from `app/database.py` for sessions in background tasks.
- Inject sessions in route handlers via `get_session()` dependency.
- The database file path is hardcoded in `database.py` — this is a known issue for portability.

### OCPI Protocol Rules

- All timestamps must be UTC and formatted as `YYYY-MM-DDTHH:MM:SSZ`.
- Authorization tokens are passed as `Authorization: Token <token>` headers.
- Tokens are masked in logs (see `core/middleware.py`) — never log raw tokens.
- OCPI responses wrap data in `{"data": ..., "status_code": 1000, "timestamp": ...}`.

### Testing

- Tests live in `tests/` and use `pytest`.
- Run with: `uv run pytest` or `python -m pytest`.
- Prefer integration tests over mocked tests where practical.

---

## Running the App

```bash
# Install dependencies
uv sync

# Run the development server
uv run uvicorn app.main:app --reload

# Initialize/reset the database
uv run python app/database.py
```

---

## Jira Project

All work in this repository is tracked in Jira.

**Site:** https://vmspproject.atlassian.net  
**Project key:** `OCPI` (vMSP Project)

### Issue Type Hierarchy

```
Epic → Story / Feature / Bug / Task → Subtask
```

### Workflow Rules

- Check the relevant Jira issue **before starting any work** to confirm it is not already In Progress.
- Transition the issue to **In Progress** when you begin.
- Transition the issue to **Done** when the PR is merged to `main`.
- Reference the issue key in every branch name and commit message (see Git Standards below).
- If you cannot proceed due to a dependency, add the `Blocked` label and leave a comment explaining why.

### Current Active Epic

**OCPI-1: OCPI 2.1.1 Sessions Module — Hub Implementation**  
https://vmspproject.atlassian.net/browse/OCPI-1

See `Agents.md` for the full story map and parallelization strategy.

---

## Git Standards

These rules apply to all work in this repository.

### Branch Naming

| Work type | Pattern | Example |
|-----------|---------|---------|
| Feature / Story | `feature/OCPI-<n>-<short-description>` | `feature/OCPI-3-session-service-layer` |
| Bug fix | `fix/OCPI-<n>-<short-description>` | `fix/OCPI-8-invalid-status-transition` |
| Refactor / Cleanup | `cleanup/<short-description>` | `cleanup/remove-dead-code` |
| Documentation | `docs/<short-description>` | `docs/claude-agent-guidance` |
| Hotfix | `hotfix/<short-description>` | `hotfix/auth-token-null-check` |

- Always branch from `main`.
- One branch per Jira story — do not combine unrelated work.

### Commit Messages

Format: `[OCPI-<n>] <imperative verb> <what changed>`

```
[OCPI-3] Add SessionService with create, get, update, patch, and list methods
[OCPI-4] Add CPO-facing PUT/PATCH session receiver endpoints
```

- Subject line ≤ 72 characters.
- Use imperative mood: "Add", "Fix", "Remove", "Update".
- Always include the Jira key prefix.

### Epic Integration Branches

Large epics use a single long-lived branch that accumulates all story work. Story PRs target the epic branch; one final PR merges the epic into `main` when all stories are done.

**Active epic branch:** `feature/OCPI-1-sessions-module` (Sessions Module, OCPI-1)

- Branch story work **from** the epic branch, PR **back into** it.
- Do not target `main` directly for work that belongs to an open epic.

### Pull Requests

- **Title:** `[OCPI-<n>] <story summary>`
- **Body:** Brief summary, link to the Jira issue, and test plan.
- **Target:** The active epic branch for the story's epic. Use `main` only for non-epic work or for the final epic → main PR.
- One story per PR.
- Tests must pass before merging.
- Never force-push to `main` or the epic branch, or commit directly to them.
- Never use `--no-verify` to bypass hooks.

---

## What NOT to Do

- Do not hardcode tokens or credentials in source files.
- Do not use synchronous SQLAlchemy (`Session`, `create_engine`) — the project uses async throughout.
- Do not add routes without registering the router in `main.py`.
- Do not change `OCPIBaseModel`'s datetime serializer without verifying all models still produce valid OCPI timestamps.
- Do not skip `model_rebuild()` calls at the bottom of model files — SQLModel requires them for forward-referenced relationships.

---

## Areas Under Active Development

- **Sessions module** — the schema and models exist (`app/models/session.py`, `app/api/v2_1_1/schemas.py`) but API routes have not been implemented yet.
- **Roaming agreements** — model exists but integration is incomplete.
- The `main.py` file contains leftover test helper functions (`test_location`, `test_location_db`) that should eventually be moved to tests or removed.