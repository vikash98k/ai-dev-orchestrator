# AI Dev Orchestrator

Production-oriented orchestrator that prepares software work from GitHub Projects through local workspace setup.

**Target repositories are external** (for example [`fashion-store-backend`](https://github.com/vikash98k/fashion-store-backend)). This repo is the orchestrator, not the product under development.

## What it does today

| Capability | Status |
|---|---|
| GitHub authentication (PAT) | Done |
| Repository metadata | Done |
| Issue reading / filtering | Done |
| GitHub Project V2 board reading | Done |
| Next-task selection (workflow engine) | Done |
| Local Git workspace preparation | Done |
| AI coding / Claude | Not yet |
| Commits / push / PRs | Not yet |

Current CLI flow:

1. Authenticate with GitHub  
2. Select the next **Ready** task (or use a demo branch if none)  
3. Clone/open the repo under `WORKSPACE_ROOT`  
4. Update the default branch and create the feature branch  
5. Report a clean workspace ready for AI implementation  

## Architecture

Clean Architecture with dependency injection. Managers never reach into each other’s GitHub/Git details directly.

```text
main.py
  └─ GitHubClient
       ├─ RepositoryManager
       │    ├─ IssueManager
       │    └─ ProjectBoardManager
       └─ WorkflowEngine  (rules + selectors)
            └─ GitWorkspaceManager  (GitPython via GitClient)
```

```text
app/
  github/          # GitHub API (auth, repos, issues, projects)
  workflow/        # Decision layer only (pick next task)
  git/             # Local workspace only (clone / branch)
main.py            # Temporary CLI demo
```

### Packages

**`app/github`**
- `GitHubClient` — token auth, connection verify, GraphQL adapter
- `RepositoryManager` — repo access + metadata
- `IssueManager` — read-only issues (list/filter/search/get)
- `ProjectBoardManager` — Project V2 items + status fields

**`app/workflow`**
- `WorkflowEngine` — eligibility + selection
- `rules.py` — Ready / open / locked / draft / archived / AI-assignee checks
- `selectors.py` — Strategy pattern (`Priority`, `Oldest`, `FIFO`, composite)

**`app/git`**
- `GitClient` — GitPython adapter
- `GitWorkspaceManager` — clone/open, checkout default branch, pull, create feature branch

## Sprint progress

| Task | Title | Notes |
|---|---|---|
| GH-002 | GitHub Authentication | Fine-grained or classic PAT |
| GH-003 | Repository Manager | Pydantic `RepositoryInfo` |
| GH-004 | Issue Manager | Read-only issue APIs |
| GH-005 | Project Board Manager | Project V2 via GraphQL |
| GH-006 | Workflow Engine | Select one Ready task |
| GH-007 | Git Workspace Manager | Local clone + feature branch |

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt` / `pyproject.toml`:
  - PyGithub
  - python-dotenv
  - pydantic v2
  - GitPython
  - ruff (dev/lint)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```bash
# Prefer a classic PAT for user-owned Projects V2
# (fine-grained PATs cannot access user projects)
GITHUB_TOKEN=ghp_...

GITHUB_OWNER=vikash98k
GITHUB_REPO=fashion-store-backend
GITHUB_PROJECT_NUMBER=6

WORKSPACE_ROOT=~/workspace
# GIT_DEFAULT_BRANCH=develop   # optional; defaults to repo default branch
```

### Token notes

| Need | Token type | Scopes / permissions |
|---|---|---|
| Public/private repos + issues | Fine-grained or classic | Contents / Issues read |
| **User-owned Project boards** (`/users/.../projects/N`) | **Classic** | `project` + `repo` |
| Local clone over SSH | SSH key for GitHub | Host alias / key configured |

Project number comes from the board URL, e.g.  
`https://github.com/users/vikash98k/projects/6` → `GITHUB_PROJECT_NUMBER=6`

## Run

```bash
python main.py
```

Example successful output:

```text
====================================================

AI Dev Orchestrator

Repository

fashion-store-backend

Workspace

✓ Repository Found

Location

~/workspace/fashion-store-backend

Branch

master

Pulling latest...

✓ Up To Date

Creating Feature Branch...

✓ feature/DEMO-000-workspace-prep

Workspace Status

Clean

Ready for AI Implementation

====================================================
```

If the board has no Ready items, the CLI still prepares the workspace using a demo feature branch.

## Configuration reference

| Variable | Purpose |
|---|---|
| `GITHUB_TOKEN` | GitHub PAT (never commit real tokens) |
| `GITHUB_OWNER` | User or org login |
| `GITHUB_REPO` | Target repository name |
| `GITHUB_PROJECT_NUMBER` | Project V2 board number |
| `WORKSPACE_ROOT` | Local root for clones (`~/workspace/<repo>`) |
| `GIT_DEFAULT_BRANCH` | Optional override before feature branching |

## Design principles

- **SOLID / DI** — managers and engine are injectable and testable  
- **Pydantic v2** — no raw dict contracts for domain data  
- **Strategy pattern** — workflow selectors are swappable  
- **Separation of concerns** — GitHub I/O ≠ decisions ≠ local Git  
- **No secrets in logs**  
- **Ruff** for lint/format  

## Explicitly out of scope (so far)

- Claude / AI code generation  
- Committing or pushing  
- Opening pull requests  
- Updating issues or project status after work  
- Full automation / agent loop  

Those are intended follow-on sprints on top of the current foundation.

## License

Add a license file when you publish the project.
