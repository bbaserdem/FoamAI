```markdown
# One-Week DevOps Workflow (Person 4)  
*Fast-track plan for a first-time DevOps engineer building the MVP*

---

## 🎯 Guiding Principles
1. **Keep the footprint tiny** – one EC2 `c7i.2xlarge` VM, Docker, and Terraform only.  
2. **Automate just enough** – one GitHub Actions job that builds & pushes images, one Terraform root module that provisions the VM.  
3. **Load test with small OpenFOAM tutorials** – no need for autoscaling, HPC, or observability in week 1.  

---

## 🛠️ Toolchain at a Glance

| Purpose | Tool | Why |
|---------|------|-----|
| Infrastructure as Code | **Terraform 1.8** | Declarative, fastest learning curve, huge AWS docs. |
| Containerization | **Docker + docker-compose** | Single-VM orchestration with one YAML file. |
| CI/CD | **GitHub Actions** | Free runners, simple `.github/workflows/docker.yml`. |
| OS Image | **Ubuntu 22.04 LTS** | Official OpenFOAM/ParaView packages, stable on AWS. |
| Secrets | **GitHub Encrypted Secrets** | Easiest for MVP; mount into containers at runtime. |

---

## 🗓️ 7-Day Checklist (Copy into your project board)

| Day | Goal | Concrete Steps |
|-----|------|----------------|
| **Day 1** | Terraform basics + AWS setup | 1) Watch Terraform “getting started with AWS” (20 min).<br>2) Create AWS account / IAM user `devops` with Access Key.<br>3) Install Terraform & AWS CLI locally.<br>4) Run `aws configure` with the new key. |
| **Day 2** | Write Terraform root module | 1) `terraform init`.<br>2) Create `provider "aws"` block (region `us-east-1`).<br>3) Add `aws_key_pair`, `aws_security_group` (ports 22,80,443,11111).<br>4) Add `aws_instance "openfoam_vm"` with AMI `ubuntu-22.04` and `instance_type = "c7i.2xlarge"`. |
| **Day 3** | User-data & Docker install | 1) Write a tiny `cloud-init` script in `user_data.sh` that installs Docker & docker-compose.<br>2) In the same script, clone repo + `docker-compose up -d`.<br>3) Add `user_data = file("user_data.sh")` to the instance resource.<br>4) `terraform apply` → SSH in and verify Docker is running. |
| **Day 4** | Docker-compose skeleton | 1) Create `docker-compose.yml` with three placeholder services:<br>&nbsp;&nbsp;• `api` (will run FastAPI)<br>&nbsp;&nbsp;• `openfoam` (runs solver when invoked)<br>&nbsp;&nbsp;• `pvserver` (ParaView)<br>2) Mount a shared volume `/data` for test cases.<br>3) Expose ports `8000` and `11111`. |
| **Day 5** | GitHub Actions build & push | 1) Add GitHub secrets: `AWS_KEY`, `AWS_SECRET`, `DOCKERHUB_USER`, `DOCKERHUB_PWD`.<br>2) Create `.github/workflows/docker.yml` that:<br>&nbsp;&nbsp;• builds each Dockerfile<br>&nbsp;&nbsp;• tags `latest` + `$GITHUB_SHA`<br>&nbsp;&nbsp;• pushes to Docker Hub.<br>3) Test by pushing a commit. |
| **Day 6** | Wire backend image → VM | 1) Update `docker-compose.yml` to use `yourorg/api:latest` etc.<br>2) SSH to VM → `docker-compose pull && docker-compose up -d`.<br>3) Confirm `/ping` endpoint of API responds over public IP. |
| **Day 7** | MVP smoke test & docs | 1) Backend dev supplies test API call – run it, make sure OpenFOAM tutorial executes.<br>2) Add `README_vm_setup.md` with exact commands for refreshing containers.<br>3) Tag repo `v0.1-mvp`, push, demo to team. |

---

## 📂 Recommended Repo Layout

- infra/
- main.tf
- variables.tf
- outputs.tf
- user_data.sh
- docker/
- api/Dockerfile
- openfoam/Dockerfile
- pvserver/Dockerfile
- docker-compose.yml
- .github/
- workflows/docker.yml
- docs/
- devops_workflow.md   <-- this file

```

---

## 📝 Terraform File Skeleton (explanatory comments inline)

```hcl
# infra/main.tf
terraform {
  required_providers { aws = { source = "hashicorp/aws" } }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_key_pair" "mvp_key" {
  key_name   = "mvp-key"
  public_key = file("~/.ssh/id_rsa.pub")
}

resource "aws_security_group" "mvp_sg" {
  name_prefix = "cfd-sg-"
  ingress = [
    for p in [22, 80, 443, 11111] : {
      from_port   = p
      to_port     = p
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  ]
  egress = [
    { from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"] }
  ]
}

resource "aws_instance" "openfoam_vm" {
  ami           = "ami-0fc5d935ebf8bc3bc"    # Ubuntu 22.04 in us-east-1
  instance_type = "c7i.2xlarge"
  key_name      = aws_key_pair.mvp_key.key_name
  vpc_security_group_ids = [aws_security_group.mvp_sg.id]

  user_data = file("${path.module}/user_data.sh")  # installs Docker & runs compose

  tags = { Name = "openfoam-mvp" }
}

output "public_ip" {
  value = aws_instance.openfoam_vm.public_ip
}
````

---

## 🐳 Minimal `docker-compose.yml`

```yaml
version: "3.9"
services:
  api:
    image: yourorg/cfd-api:latest
    restart: unless-stopped
    ports: ["8000:8000"]
    env_file: .env

  openfoam:
    image: yourorg/openfoam:latest
    volumes:
      - /data:/data
    entrypoint: ["/bin/bash", "-c", "tail -f /dev/null"]  # solver runs on demand

  pvserver:
    image: yourorg/pvserver:latest
    restart: unless-stopped
    ports: ["11111:11111"]
```

---

## 🤖 GitHub Actions (`.github/workflows/docker.yml`)

```yaml
name: Build & Push Docker Images
on:
  push:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USER }}
          password: ${{ secrets.DOCKERHUB_PWD }}
      - name: Build & push
        run: |
          for s in api openfoam pvserver; do
            docker build -t yourorg/cfd-$s:latest -f docker/$s/Dockerfile .
            docker push yourorg/cfd-$s:latest
          done
```

---

## 🔐 Secrets & Environment Variables

| Name                                          | Stored Where                                   | Used By                             |
| --------------------------------------------- | ---------------------------------------------- | ----------------------------------- |
| `OPENAI_API_KEY`                              | GitHub Secrets → passed into API container     | LLM calls                           |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Local shell (`aws configure`) & GitHub Secrets | Terraform CLI, Actions              |
| `DOCKERHUB_USER` / `DOCKERHUB_PWD`            | GitHub Secrets                                 | Docker login in CI                  |
| `.env` file                                   | In repo (no secrets)                           | Shared configs like `API_PORT=8000` |

---

## ✅ Validation Steps

1. `terraform apply` → wait \~2 min → note public IP output.
2. `ssh ubuntu@<ip>` → `docker ps` should list `api`, `pvserver`, `openfoam`.
3. `curl http://<ip>:8000/ping` returns `"pong"`.
4. Trigger GitHub Actions → new images push → `ssh` then `docker-compose pull && docker-compose up -d` to refresh.
5. Run backend dev’s test request → confirm small OpenFOAM tutorial finishes and results directory appears under `/data`.

*If all five pass, the MVP infra is ready for demo.*

```
```

