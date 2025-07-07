# 🧑‍💻 Team Role Breakdown – LangGraph + OpenFOAM LLM Assistant Project

This document outlines a recommended 4-person team structure for building the CFD LLM assistant using LangGraph and OpenFOAM.
Each role owns distinct parts of the system with well-defined handoff points for collaboration.

## Current division

1) Eric
2) Jack
3) Matt
4) Batuhan

---
## 👤 1. LLM Agent Engineer (Person A)

**Focus:** Agent logic, LangGraph orchestration, OpenAI tool calls.

### Responsibilities
- Design and implement LangGraph agent nodes and transitions.
- Define agent input/output schemas (e.g., Pydantic, JSONSchema).
- Implement:
  - `NL Interpreter Agent`
  - `Solver Selector Agent`
  - `Boundary Condition Agent`
- Write prompt templates and tool definitions using LangChain or LangGraph tools.
- Maintain the LangGraph graph YAML or Python definition.

### Git Ownership

```
/agents/nl_interpreter/
/agents/solver_selector/
/langgraph_flow/
```

---

## 👤 2. Backend & Job Runner Engineer (Person B)

**Focus:** FastAPI backend, job orchestration, OpenFOAM/ParaView execution.

### Responsibilities
- Build HTTP & WebSocket endpoints:
  - `/submit-job`
  - `/job-status`
- Implement:
  - `Simulation Executor Agent`
  - `Result Summarizer Agent`
  - `File Manager Agent`
- Handle Docker subprocess calls or SSH execution.
- Integrate Celery or task queue for job dispatching.
- Ensure job logging, retries, and error propagation.

### Git Ownership

```
/backend/api/
/backend/jobs/
/backend/openfoam_runner/
```

---

## 👤 3. Desktop App & UX Engineer (Person C)

**Focus:** GUI desktop app (Qt), ParaView viewer, job interaction.

### Responsibilities
- Build PySide6 desktop interface:
  - Chat window
  - Job history & status
  - Plot viewer
- Handle backend communication (REST, WebSocket).
- Embed ParaView Qt widget connected to `pvserver`.
- Implement file upload/download UX.
- Conduct end-to-end tests using agent-generated cases.

### Git Ownership

```
/desktop_client/
```

---

## 👤 4. DevOps & Data Engineer (Person D)

**Focus:** Infrastructure (Terraform, Docker), storage, CI/CD, observability.

### Responsibilities
- Create Terraform scripts for single-VM cloud setup.
- Manage Dockerfiles for:
  - OpenFOAM
  - ParaView
  - API server
- Set up S3/MinIO buckets for storing simulation inputs/outputs.
- Implement GitHub Actions pipelines for:
  - Code linting
  - Testing
  - Deployment
- Configure logging and monitoring (Prometheus + Grafana).

### Git Ownership

```
/infra/terraform/
/infra/docker/
/ci/
```

---

## 🔄 Shared Conventions

- Use **GitHub Projects** or **Issues** to track features and bugs.
- All merges must go through **Pull Requests**, reviewed by at least one teammate.
- Establish clear **naming conventions and folder structures** early.
- Centralize shared formats and schemas in:

```
/schemas/job_config.py
```

- Weekly check-in: **merge working features into `dev` branch** for full integration tests.

---

Let us know if you'd like a starter Git repo scaffold with empty folders, README stubs, and `.gitignore` templates!

