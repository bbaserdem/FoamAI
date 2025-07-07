## 1  Infrastructure & Provisioning

| Layer | Primary Choice | Why It Fits | Alternatives (when / why) |
|---|---|---|---|
| **1.1 Cloud** | **AWS EC2 c7i / hpc7a VM** | Fast E-cores + generous RAM → good price-perf for CFD; ubiquitous enterprise support. | GCP C3-standard (lower-latency global net), Azure HBv4 (better InfiniBand). |
| **1.2 IaC** | **Terraform** | Largest multi-cloud module ecosystem → fast turnkey scripts for users. | Pulumi (team prefers TypeScript/Go), AWS CDK (single-cloud but richer abstractions). |
| **1.3 OS Image** | **Ubuntu 22.04 LTS** | Official OpenFOAM/ParaView packages, rock-solid driver support. | AlmaLinux 9 (if org mandates RHEL), NixOS (full reproducibility but steeper learning curve). |

---

## 2  Runtime & Environment Management

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **2.1 Isolation** | **Docker + docker-compose** | Single-VM, single-command deploy that encapsulates OpenFOAM, ParaView, API, and Redis queue. | Podman (rootless, lower attack surface), bare-metal Nix flakes (no containers). |
| **2.2 Scheduler** | **Celery w/ Redis** | Lightweight job queue ≤ hundreds of runs/day; integrates with FastAPI background tasks. | SQS + Lambda (managed, cloud-specific), Slurm (if bursting to HPC cluster later). |

---

## 3  CFD & Visualization Layer

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **3.1 Solver** | **OpenFOAM v2312 (Foundation)** | Cleaner codebase, fewer breaking syntax changes → safer for scripted LLM edits. | OpenFOAM 2312 (ESI) for extra turbulence models; SU2 for adjoint/shape opt. |
| **3.2 Post-processing** | **ParaView Server 5.12** | Native OpenFOAM reader, remote rendering → minimal client CPU/GPU. | PyVista-VTK in Jupyter (lighter, fewer advanced filters). |

---

## 4  LLM Integration

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **4.1 Model API** | **OpenAI GPT-4o** | Best NL-to-CFD prompt fidelity; long context handles mesh dicts. | Mix-tral-8x22B via Together, private Llama-3-70B on vLLM for offline. |
| **4.2 Framework** | **LangChain 0.2** | Rapid tool-wrappers, prompt templates, async calls; large recipe base. | Llama-Index (better RAG), vanilla SDK (leanest). |

---

## 5  Backend API & Realtime Messaging

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **5.1 Web API** | **FastAPI** | Async, Pydantic typing, auto-gen OpenAPI docs; deploy via Uvicorn. | Flask (legacy familiarity), Go Fiber (≈2× throughput, compiled). |
| **5.2 Realtime** | **WebSocket endpoints in FastAPI** | Push job status / residuals without polling; lives in same codebase. | gRPC stream (strong types, C++ client), MQTT (if IoT devices later). |

---

## 6  Desktop Client

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **6.1 UI Toolkit** | **PySide6 (Qt 6)** | Native look, Python bindings, reuse LangChain client code. | Electron + React (web dev talent, heavier), Tauri + Svelte (tiny binaries, Rust safety). |
| **6.2 3-D View** | **ParaView Qt widget** | Embeds remote-rendered scene via `pqRemoteRendering`. | VTK.js in Electron/Tauri (all-web). |
| **6.3 Packaging** | **PyInstaller one-file exe/app** | Zero-install for users; code-sign via CI. | conda-pack (scientific users), Snapcraft (Linux-only). |

---

## 7  Data & Storage

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **7.1 Object Store** | **AWS S3 Standard-IA** | Cheap large result files; presigned URLs for desktop download. | MinIO on same VM, GCS/Azure Blob on other clouds. |
| **7.2 Metadata DB** | **PostgreSQL 16** | ACID job records, JSONB for LLM logs. | DynamoDB (serverless), SQLite (on-disk for true single-VM PoC). |

---

## 8  Security & Auth

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **8.1 Identity** | **Auth0 Universal Login** | Rapid OAuth2/OIDC, social logins, generous free tier. | Keycloak (self-host), AWS Cognito (if AWS-only). |
| **8.2 Secrets** | **AWS Parameter Store** | Inline with Terraform, free at small scale. | HashiCorp Vault (multi-cloud), Doppler (SaaS). |

---

## 9  Observability & CI/CD

| Layer | Primary Choice | Why It Fits | Alternatives |
|---|---|---|---|
| **9.1 Metrics & Logs** | **Prometheus + Grafana + Loki** | De-facto OSS stack; Helm charts if you dockerize later. | DataDog (SaaS, less ops), CloudWatch + Grafana (AWS-native). |
| **9.2 CI/CD** | **GitHub Actions → Terraform Cloud + Docker Hub** | Free runners, LLM-linting integration, simple matrix builds. | GitLab CI (self-host), Jenkins (legacy). |

---

### Why this stack?

1. **All components run on one VM** yet upgrade cleanly to multi-VM / HPC by swapping Docker-compose for Kubernetes and Celery for Slurm.  
2. **Python end-to-end** (backend, orchestration, desktop) shortens dev time and leverages existing OpenFOAM scripting.  
3. **Open standards (OpenAPI, OAuth, WebSocket)** keep cloud lock-in minimal for admin users.  
4. **Every alternative lets you pivot** when requirements change (offline LLM, heavier post-processing, stricter security).
