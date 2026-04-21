# Agents.md — Multi-Agent Orchestration Guide

This file governs how coding agents coordinate when working on this project in parallel. Read CLAUDE.md first for project-level context, then use this file when multiple agents are running concurrently or handing off work.

---

## Jira Project

**Site:** https://vmspproject.atlassian.net  
**Project key:** `OCPI` (vMSP Project)  
**Cloud ID:** `9251a300-9ea6-4f5f-ba0e-b612151edc23`

### Issue Type Hierarchy

```
Epic
  └── Story / Feature / Bug / Task
        └── Subtask
```

### Issue Statuses

| Status | Meaning |
|--------|---------|
| To Do | Not started |
| In Progress | Actively being worked |
| Done | Merged to main |
| Blocked | Cannot proceed — dependency unmet (use label: `Blocked`) |

### Agents and Jira

- **Before starting any story**, check its status in Jira and confirm its dependencies are `Done`.
- **When claiming a story**, transition it to `In Progress` so no other agent picks it up.
- **When a PR is merged**, transition the story to `Done`.
- **If blocked**, add the `Blocked` label and leave a comment explaining why (e.g., "Waiting for OCPI-3 to merge").
- Reference the issue key in every commit message and branch name (see Git Standards below).

---

## Current Epic: Sessions Module (OCPI-1)

The active epic is **OCPI-1: OCPI 2.1.1 Sessions Module — Hub Implementation** at https://vmspproject.atlassian.net/browse/OCPI-1.

### Story Map & Dependency Graph

```
OCPI-2 (Story 1: Data Model)
  └── OCPI-3 (Story 2: Service Layer)
        ├── OCPI-4 (Story 3: CPO Receiver Endpoints)  ─┐
        ├── OCPI-5 (Story 4: eMSP Pull Endpoints)      ├─ can parallelize
        ├── OCPI-6 (Story 5: CPO Pull Endpoint)         ├─ can parallelize
        └── OCPI-8 (Story 7: Status Lifecycle)         ─┘
              └── OCPI-7 (Story 6: Hub Forwarding — depends on OCPI-4)
                    └── OCPI-9 (Story 8: Module Registration — parallel after OCPI-4/5)
                          └── OCPI-10 (Story 9: Integration Tests — depends on ALL, currently Blocked)
```

### Story Summary

| Key | Story | Priority | Status | Story Points |
|-----|-------|----------|--------|--------------|
| OCPI-2 | Session Data Model & Database Schema | Highest | To Do | 3 |
| OCPI-3 | Session CRUD Service Layer | Highest | To Do | 5 |
| OCPI-4 | CPO-Facing Receiver Endpoints (PUT/PATCH) | High | To Do | 5 |
| OCPI-5 | eMSP-Facing Sender Endpoints (GET from Hub) | High | To Do | 3 |
| OCPI-6 | CPO-Facing Pull Endpoint (CPOs GET their sessions) | Medium | To Do | 2 |
| OCPI-7 | Hub Forwarding — Push Sessions to eMSPs | High | To Do | 8 |
| OCPI-8 | Session Status Lifecycle & Validation | High | To Do | 3 |
| OCPI-9 | Sessions Module Registration in Versions/Endpoints | Medium | To Do | 1 |
| OCPI-10 | Integration Tests — End-to-End Session Flow | Medium | To Do (Blocked) | 5 |

**Total: 35 story points**

---

## Git Standards

These rules apply to all contributors — human and agent alike.

### Branch Naming

| Work type | Pattern | Example |
|-----------|---------|---------|
| Feature / Story | `feature/OCPI-<n>-<short-description>` | `feature/OCPI-3-session-service-layer` |
| Bug fix | `fix/OCPI-<n>-<short-description>` | `fix/OCPI-8-invalid-status-transition` |
| Refactor / Cleanup | `cleanup/<short-description>` | `cleanup/remove-dead-code` |
| Documentation | `docs/<short-description>` | `docs/claude-agent-guidance` |
| Hotfix to main | `hotfix/<short-description>` | `hotfix/auth-token-null-check` |

- Always branch from `main` unless instructed otherwise.
- One branch per Jira story. Do not combine unrelated stories on one branch.
- Delete branches after merging.

### Commit Messages

Format: `[OCPI-<n>] <imperative verb> <what changed>`

```
[OCPI-3] Add SessionService with create, get, update, patch, and list methods
[OCPI-4] Add CPO-facing PUT/PATCH session receiver endpoints
[OCPI-8] Enforce session status transition state machine
```

Rules:
- Subject line ≤ 72 characters.
- Use imperative mood: "Add", "Fix", "Remove", "Update" — not "Added", "Fixed".
- Include the Jira key prefix even for small commits.
- If a commit spans multiple stories (rare), list all keys: `[OCPI-4][OCPI-9]`.
- Body is optional but encouraged for non-obvious decisions.

### Pull Requests

- **Title:** `[OCPI-<n>] <story summary>` — mirrors the commit style.
- **Body:** Must include:
  - A brief summary of what was implemented.
  - Link to the Jira issue (e.g., `https://vmspproject.atlassian.net/browse/OCPI-3`).
  - Test plan: what was tested and how.
- **Target branch:** `main`.
- **One story per PR.** Do not bundle multiple stories unless they are tightly coupled with no way to separate.
- **Tests must pass** before requesting a review or merging.
- Do not merge your own PR without review (when working with other humans/agents).

### Protected Branch Rules

- `main` is the source of truth — never force-push to it.
- Never commit directly to `main` — always use a branch + PR.
- Never use `--no-verify` to skip hooks.

---

## Multi-Agent Coordination

### Ownership Model

Each Jira story is owned by exactly **one agent at a time**. Ownership is established by:
1. Transitioning the issue to `In Progress` in Jira.
2. Creating the feature branch and pushing at least one commit.

Once an agent owns a story, no other agent should touch that branch or story until it is merged or explicitly handed off.

### Parallelization Strategy

Based on the OCPI-1 dependency graph, the following parallel execution windows exist:

**Wave 1 — Sequential (no parallelism possible)**
- Agent A: OCPI-2 (Data Model) → must merge before Wave 2

**Wave 2 — Sequential**
- Agent A: OCPI-3 (Service Layer) → must merge before Wave 3

**Wave 3 — Parallel (all depend on OCPI-3)**
- Agent A: OCPI-4 (CPO Receiver Endpoints)
- Agent B: OCPI-5 (eMSP Pull Endpoints)
- Agent C: OCPI-6 (CPO Pull Endpoint)
- Agent D: OCPI-8 (Status Lifecycle)

**Wave 4 — Parallel (after Wave 3 merges)**
- Agent A: OCPI-7 (Hub Forwarding — depends on OCPI-4)
- Agent B: OCPI-9 (Module Registration — parallel)

**Wave 5 — Sequential (after all others)**
- Agent A: OCPI-10 (Integration Tests — depends on everything)

### Avoiding Conflicts

- Agents working in parallel **must not edit the same files**. Before starting, state which files you will touch and check that no other in-progress branch modifies the same paths.
- Schemas in `app/api/v2_1_1/schemas.py` are a **high-conflict file** — coordinate explicitly before editing it.
- `app/main.py` router registration is also a conflict hotspot — each wave-3 agent should add their router in a separate, clearly delimited block and resolve conflicts in order (OCPI-4, then OCPI-5, etc.).
- `app/database.py` model imports must be updated whenever a new table model is added — assign this responsibility to the agent adding the model.

### Handoff Protocol

When an agent completes a story and another picks up a dependent story:

1. The completing agent merges their PR to `main`.
2. The completing agent transitions the Jira issue to `Done`.
3. The next agent rebases or merges `main` into their branch before starting.
4. The next agent verifies the merged code compiles and tests pass before building on top of it.

### Conflict Resolution

If two agents have modified the same file and a merge conflict arises:
1. The agent whose story has the **higher priority** (or lower story number) takes precedence on shared sections.
2. Functional logic is never silently discarded — both agents' changes must be reconciled, not one overwriting the other.
3. Escalate to the human if the conflict cannot be cleanly resolved.

---

## Agent Responsibilities per Story

When picking up a story, an agent is responsible for:

| Responsibility | Required |
|---------------|----------|
| Read the full Jira story before writing code | Yes |
| Transition Jira issue to In Progress | Yes |
| Create branch from latest `main` | Yes |
| Implement all Requirements (R1–Rn) from the story | Yes |
| Verify all Acceptance Criteria (AC1–ACn) pass | Yes |
| Write or update tests for the work | Yes |
| Register new routers in `main.py` if applicable | Yes |
| Import new models in `database.py` if applicable | Yes |
| Open a PR with Jira link and test plan | Yes |
| Transition Jira issue to Done after merge | Yes |

---

## What Agents Must Not Do

- Do not pick up a story that is already `In Progress` in Jira.
- Do not merge to `main` without a passing test run.
- Do not combine multiple stories into one branch without explicit human approval.
- Do not delete another agent's branch.
- Do not create new Jira issues without human approval — ask first.
- Do not add speculative features not described in the Jira story's requirements.