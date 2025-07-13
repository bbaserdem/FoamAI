# GitHub Actions Workflow Documentation

## Overview

This repository uses **optimized GitHub Actions workflows** that only run when relevant files change, preventing wasteful CI/CD runs. The workflows are organized by purpose to minimize unnecessary builds and deployments.

## 🚀 Workflow Organization

| Workflow | Purpose | Triggers | Runtime |
|----------|---------|----------|---------|
| **Docker** (`docker.yml`) | Build & push container images | Docker/source code changes | ~15-20 min |
| **Infrastructure** (`infrastructure.yml`) | Validate Terraform & deployment scripts | Infrastructure changes | ~2-3 min |
| **Documentation** (`docs.yml`) | Validate markdown & links | Documentation changes | ~1 min |

### 🎯 Path-Based Triggers (Smart CI/CD)

**Docker Workflow** only runs when these files change:
- `docker/**` - Dockerfile changes
- `src/**` - Source code changes  
- `pyproject.toml`, `uv.lock`, `requirements.txt` - Dependencies
- `docker-compose.yml` - Service configuration
- `.github/workflows/docker.yml` - Workflow itself

**Infrastructure Workflow** only runs when these files change:
- `infra/**` - Terraform, deployment scripts
- `dev/**` - Development utilities
- `.github/workflows/infrastructure.yml` - Workflow itself

**Documentation Workflow** only runs when these files change:
- `**/*.md` - Any markdown files
- `docs/**` - Documentation directory
- `.github/workflows/docs.yml` - Workflow itself

### 💡 Why This Optimization Matters

**Before**: Every commit triggered expensive Docker builds (~20 min)  
**After**: Only relevant changes trigger appropriate workflows

**Example Scenarios:**
- ✅ **Infra-only commit** (like your recent deployment improvements): Only `infrastructure.yml` runs (~3 min)
- ✅ **Docs-only commit**: Only `docs.yml` runs (~1 min)  
- ✅ **Code changes**: Only `docker.yml` runs (~20 min)
- ✅ **Mixed changes**: Multiple workflows run in parallel

## Services Built (Docker Workflow)

| Service | Description | Docker Image |
|---------|-------------|--------------|
| **OpenFOAM** | CFD simulation engine | `ghcr.io/bbaserdem/openfoam:latest` |
| **API** | FastAPI backend service | `ghcr.io/bbaserdem/api:latest` |
| **ParaView Server** | Remote visualization server | `ghcr.io/bbaserdem/pvserver:latest` |

## Required GitHub Secrets

The Docker workflow requires GitHub Container Registry authentication (no setup needed - uses `GITHUB_TOKEN`).

For Docker Hub (if switching back), you'd need:
- `DOCKER_USERNAME` - Your Docker Hub username
- `DOCKER_PASSWORD` - Your Docker Hub access token

## Workflow Features

### 🚀 **Docker Workflow (`docker.yml`)**
- **Parallel Builds**: All three services build simultaneously
- **Smart Tagging**: `latest`, `main-<sha>`, `pr-<number>`
- **Security Scanning**: Trivy vulnerability scanning
- **Registry**: GitHub Container Registry (ghcr.io)
- **Caching**: Docker layer caching for faster builds

### 🏗️ **Infrastructure Workflow (`infrastructure.yml`)**
- **Terraform Validation**: Format check, init, validate
- **Script Validation**: Bash syntax checking for all `.sh` files
- **Permission Checks**: Ensures scripts are executable
- **Fast Feedback**: Quick validation without expensive builds

### 📚 **Documentation Workflow (`docs.yml`)**
- **Link Checking**: Validates markdown links aren't broken
- **Format Validation**: Checks for trailing spaces, line endings
- **Lightweight**: Fastest possible feedback for docs changes

## Image Registry

All images are pushed to **GitHub Container Registry**:
- `ghcr.io/bbaserdem/foamai/openfoam:latest`
- `ghcr.io/bbaserdem/foamai/api:latest`
- `ghcr.io/bbaserdem/foamai/pvserver:latest`

## Local Testing

### Test Builds (when changing Docker/source files)
```bash
# Test building individual services
docker build -t foamai/openfoam:test -f docker/openfoam/Dockerfile .
docker build -t foamai/api:test -f docker/api/Dockerfile .
docker build -t foamai/pvserver:test -f docker/pvserver/Dockerfile .

# Test all services
docker-compose build
```

### Test Infrastructure (when changing infra files)
```bash
# Validate Terraform
cd infra/
terraform fmt -check
terraform init -backend=false
terraform validate

# Validate shell scripts
bash -n user_data.sh
bash -n user_data_modules/*.sh
bash -n ../dev/*.sh
```

### Test Documentation (when changing docs)
```bash
# Check markdown formatting
find . -name "*.md" -exec echo "Checking {}" \; -exec head -1 {} \;

# Test specific tools if available
markdownlint **/*.md
markdown-link-check README.md
```

## Troubleshooting

### Workflow Not Running?

Check if your changes match the path triggers:

```bash
# See which files you've changed
git status
git diff --name-only HEAD~1

# Check if they match workflow paths:
# - docker/** or src/** → Docker workflow
# - infra/** or dev/** → Infrastructure workflow  
# - **/*.md or docs/** → Documentation workflow
```

### Force a Specific Workflow

If you need to force a workflow to run:

1. **Docker workflow**: Edit `.github/workflows/docker.yml` (add a comment)
2. **Infrastructure workflow**: Edit `.github/workflows/infrastructure.yml` 
3. **Documentation workflow**: Edit `.github/workflows/docs.yml`

### Common Issues

1. **"No workflow runs" for infra changes**
   - ✅ **Expected behavior** - your recent infra changes won't trigger Docker builds!
   - The infrastructure workflow will validate your Terraform and scripts

2. **Multiple workflows running**
   - ✅ **Expected behavior** when changes span multiple areas
   - Each workflow handles its own domain efficiently

3. **Build seems slow despite optimization**
   - Check if you modified both code AND infra files
   - Each workflow runs independently and in parallel

## Integration with AWS Deployment

The optimized workflows support the complete deployment pipeline:

1. **Code changes** → Docker workflow → New images in GHCR
2. **Infrastructure changes** → Infrastructure workflow → Validated deployment scripts  
3. **Documentation changes** → Documentation workflow → Validated docs

The AWS EC2 deployment pulls the validated images and uses the validated infrastructure scripts for reliable deployments. 