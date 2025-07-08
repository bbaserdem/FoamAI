# GitHub Actions Workflow Documentation

## Overview

This repository uses GitHub Actions for automated CI/CD to build and deploy Docker images for the FoamAI project. The workflow automatically builds and pushes three Docker services to Docker Hub.

## Services Built

| Service | Description | Docker Image |
|---------|-------------|--------------|
| **OpenFOAM** | CFD simulation engine | `foamai/openfoam:latest` |
| **API** | FastAPI backend service | `foamai/api:latest` |
| **ParaView Server** | Remote visualization server | `foamai/pvserver:latest` |

## Workflow Triggers

The workflow runs automatically on:
- **Push to main/master branch** - Builds and pushes images to Docker Hub
- **Pull Requests** - Builds images for testing (does not push)

## Required GitHub Secrets

Before the workflow can push to Docker Hub, you need to configure these secrets in your GitHub repository:

### Setting up Docker Hub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Add the following repository secrets:

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `DOCKER_USERNAME` | Your Docker Hub username | `your-dockerhub-username` |
| `DOCKER_PASSWORD` | Your Docker Hub access token | `dckr_pat_abcdef123456...` |

### Creating Docker Hub Access Token

⚠️ **Important**: Use an access token, not your password!

1. Log in to [Docker Hub](https://hub.docker.com/)
2. Go to **Account Settings** → **Security**
3. Click **New Access Token**
4. Name it `github-actions-foamai`
5. Select **Read, Write, Delete** permissions
6. Copy the generated token and use it as `DOCKER_PASSWORD`

## Workflow Features

### 🚀 **Parallel Builds**
All three services build simultaneously using matrix strategy for faster CI/CD.

### 🏷️ **Smart Tagging**
Images are tagged with:
- `latest` (for main branch pushes)
- `main-<commit-sha>` (for traceability)
- `pr-<number>` (for pull requests)

### 🔒 **Security Scanning**
Built-in vulnerability scanning with Trivy that reports to GitHub Security tab.

### 📊 **Build Summary**
Automatic build status summary in GitHub Actions runs.

### ⚡ **Caching**
Docker layer caching for faster subsequent builds.

## Image Registry

All images are pushed to Docker Hub under the `foamai` organization:
- https://hub.docker.com/r/foamai/openfoam
- https://hub.docker.com/r/foamai/api  
- https://hub.docker.com/r/foamai/pvserver

## Local Testing

To test the workflow locally before pushing:

```bash
# Test building individual services
docker build -t foamai/openfoam:test -f docker/openfoam/Dockerfile .
docker build -t foamai/api:test -f docker/api/Dockerfile .
docker build -t foamai/pvserver:test -f docker/pvserver/Dockerfile .

# Test all services
docker-compose build
```

## Troubleshooting

### Common Issues

1. **"No such file or directory" errors**
   - Check that all Dockerfile paths in the workflow match actual files
   - Ensure build context is set correctly (usually `.`)

2. **Docker Hub authentication failures**
   - Verify `DOCKER_USERNAME` and `DOCKER_PASSWORD` secrets are set
   - Make sure you're using an access token, not a password
   - Check that the access token has write permissions

3. **Build timeouts**
   - Large Docker images may take 20+ minutes to build
   - Consider optimizing Dockerfiles or using smaller base images

4. **Security scan failures**
   - Trivy may find vulnerabilities in base images
   - Update base images or add vulnerability exceptions if needed

### Viewing Logs

1. Go to **Actions** tab in your GitHub repository
2. Click on the failing workflow run
3. Expand the failed job to see detailed logs
4. Check the build summary for service-specific status

## Integration with AWS Deployment

This workflow prepares Docker images for AWS EC2 deployment. The images built here will be pulled by:
- Terraform-provisioned EC2 instance
- `user_data.sh` startup script
- `docker-compose.yml` orchestration

For the complete deployment process, see the main project documentation. 