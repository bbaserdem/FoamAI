# FoamAI Contributing Guide

A guide for developers contributing to the FoamAI project, including development environment setup and tooling recommendations.

## Table of Contents
- [Development Environment](#development-environment)
- [Project Structure](#project-structure)
- [UV Workspace Management](#uv-workspace-management)
- [Nix Dev Shell Setup](#nix-dev-shell-setup)
- [Local Testing Workflow](#local-testing-workflow)
- [Code Contribution Guidelines](#code-contribution-guidelines)
- [Development Tools](#development-tools)

## Development Environment

### Prerequisites
- **Python 3.13+** (required for UV workspace)
- **UV** (Python package manager) - [Install UV](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** (version 2.0+)
- **Docker** (for local testing and containers)
- **Text editor or IDE** of choice

### Repository Setup
```bash
# Clone the repository
git clone https://github.com/bbaserdem/FoamAI.git
cd FoamAI

# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up Python environment and workspace
uv sync

# Activate the virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

## Project Structure

FoamAI is organized as a UV workspace with multiple Python packages:

```
FoamAI/
├── pyproject.toml              # Workspace configuration
├── uv.lock                     # Dependency lock file
├── src/
│   ├── foamai-core/           # Core CFD logic and LLM agents
│   │   ├── foamai_core/
│   │   │   ├── orchestrator.py    # Main agent orchestrator
│   │   │   ├── solver_selector.py # OpenFOAM solver selection
│   │   │   ├── case_writer.py     # Case file generation
│   │   │   ├── mesh_generator.py  # Mesh generation logic
│   │   │   └── ...
│   │   └── pyproject.toml
│   ├── foamai-server/         # FastAPI backend service
│   │   ├── foamai_server/
│   │   │   ├── main.py            # API endpoints
│   │   │   ├── database.py        # Database models
│   │   │   ├── celery_worker.py   # Background job processing
│   │   │   └── ...
│   │   └── pyproject.toml
│   ├── foamai-desktop/        # PySide6 desktop application
│   │   ├── foamai_desktop/
│   │   │   ├── main_window.py     # Main GUI window
│   │   │   ├── paraview_widget.py # ParaView integration
│   │   │   └── ...
│   │   └── pyproject.toml
│   └── foamai-client/         # CLI client tools
│       ├── foamai_client/
│       │   ├── cli.py             # Command-line interface
│       │   └── ...
│       └── pyproject.toml
├── docker/                    # Container definitions
│   ├── api/Dockerfile         # Server container
│   ├── openfoam/Dockerfile    # OpenFOAM solver container
│   ├── pvserver/Dockerfile    # ParaView server container
│   └── desktop/Dockerfile     # Desktop app container
├── infra/                     # Infrastructure (Terraform)
├── tests/                     # Integration tests
├── examples/                  # Usage examples
└── dev/                       # Development tools
```

### Package Overview

| Package | Purpose | Key Dependencies |
|---------|---------|------------------|
| **foamai-core** | CFD logic, LLM agents, simulation orchestration | LangChain, LangGraph, Pydantic |
| **foamai-server** | REST API, background jobs, database | FastAPI, Celery, SQLAlchemy |
| **foamai-desktop** | GUI application for simulation setup/monitoring | PySide6, ParaView Qt widgets |
| **foamai-client** | CLI tools for automation and testing | Click, requests |

## UV Workspace Management

FoamAI uses UV for Python package and dependency management across multiple related packages.

### Initial Setup

```bash
# Install dependencies for all workspace members
uv sync

# Install with specific dependency groups
uv sync --group dev        # Development tools (ruff, pytest)
uv sync --group test       # Testing dependencies only
uv sync --group lint       # Linting tools only
```

### Working with Individual Packages

```bash
# Run commands in specific package context
uv run --package foamai-server python -m foamai_server.main
uv run --package foamai-desktop python -m foamai_desktop.main
uv run --package foamai-client foamai-cli --help

# Install package-specific dependencies
cd src/foamai-server
uv add fastapi uvicorn
uv add --dev pytest-asyncio

# Remove dependencies
uv remove httpx
```

### Development Workflow

```bash
# Install in development mode (editable)
uv sync --dev

# Add a new dependency to the workspace
uv add requests

# Add a dev dependency to specific package
cd src/foamai-core
uv add --dev pytest-mock

# Update all dependencies
uv lock --upgrade

# Run linting across workspace
uv run ruff check .
uv run ruff format .

# Run tests
uv run pytest
uv run pytest src/foamai-core/  # Test specific package
```

### Managing Virtual Environments

```bash
# UV automatically creates and manages .venv/
# Activate the environment manually if needed:
source .venv/bin/activate

# Check installed packages
uv pip list

# Show dependency tree
uv tree

# Export requirements for Docker builds
uv export --format requirements-txt > requirements.txt
uv export --package foamai-server --format requirements-txt > docker/api/requirements.txt
```

### Package Installation Modes

```bash
# Install from workspace (during development)
uv sync

# Install individual package in development mode
uv pip install -e src/foamai-core/

# Install from PyPI (when published)
uv add foamai-core==0.1.0

# Install from Git (for dependencies)
uv add git+https://github.com/example/package.git
```

### Dependency Groups

The workspace defines several dependency groups for different purposes:

```toml
[dependency-groups]
dev = [
    "pyyaml>=6.0.2",
    {include-group = "lint"},
    {include-group = "test"},
]
lint = [
    "ruff>=0.12.1",
]
test = [
    "pytest>=8.4.1",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=6.2.1",
    "pytest-mock>=3.14.1",
]
```

Use these groups for specific workflows:

```bash
# Development setup
uv sync --group dev

# CI/CD linting only
uv sync --group lint
uv run ruff check .

# Testing only
uv sync --group test
uv run pytest
```

### Local Testing with UV

```bash
# Test the API server locally
cd src/foamai-server
uv run python -m foamai_server.main

# Test the desktop application
cd src/foamai-desktop  
uv run python -m foamai_desktop.main

# Run integration tests
uv run pytest tests/

# Test specific functionality
uv run python examples/demo_user_approval.py
```

### Building and Distribution

```bash
# Build individual packages
uv build src/foamai-core/
uv build src/foamai-server/

# Build all packages
for pkg in src/*/; do
    echo "Building $pkg"
    uv build "$pkg"
done

# Publish to PyPI (when ready)
uv publish dist/foamai_core-*.whl
```

### Common UV Commands

| Command | Purpose |
|---------|---------|
| `uv sync` | Install/update all workspace dependencies |
| `uv add <package>` | Add dependency to workspace |
| `uv remove <package>` | Remove dependency from workspace |
| `uv run <command>` | Run command in UV environment |
| `uv lock` | Update lock file with latest versions |
| `uv tree` | Show dependency tree |
| `uv pip list` | List installed packages |
| `uv export` | Export requirements for Docker/CI |

### Troubleshooting UV Issues

```bash
# Clear UV cache
uv cache clean

# Reinstall from scratch
rm -rf .venv uv.lock
uv sync

# Check for dependency conflicts
uv lock --upgrade

# Verbose output for debugging
uv sync --verbose

# Use specific Python version
uv sync --python 3.13
```

## Nix Dev Shell Setup

For developers using Nix, a reproducible development environment is available through Nix flakes. This works on any system with Nix installed (Linux, macOS, WSL).

### Sample `flake.nix`

Create or use the provided `flake.nix` for a complete DevOps development shell:

```nix
{
  description = "Dev shell for CFD MVP DevOps tasks";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        devShells.default = pkgs.mkShell {
          name = "cfd-devops-shell";

          packages = with pkgs; [
            terraform
            awscli2
            docker-client           # CLI
            docker-buildx           # buildx plugin
            openssh
            jq
            tflint                  # optional linter
          ];

          shellHook = ''
            export TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache"
            mkdir -p "$TF_PLUGIN_CACHE_DIR"
            echo "🚀  DevOps shell ready. Run 'terraform init' to start."
          '';
        };
      });
}
```

### Direnv Integration (Recommended)

For automatic shell loading:

1. Create `.envrc` in the project root:
```bash
use flake .
```

2. Allow direnv to load the environment:
```bash
direnv allow
```

Now the development shell will load automatically when you `cd` into the repository.

### Nix vs Traditional Package Management

| Area | Traditional Approach | Nix Approach |
|------|---------------------|-------------|
| Installing CLI tools | `brew install terraform awscli` or `apt install` | Add to `devShells` in `flake.nix` |
| Docker daemon | System package manager | Install via system package manager (Docker not managed by Nix) |
| Binary plugins | Written to `~/.terraform.d` | Works as-is, keep outside Nix store |
| Secrets | `$HOME/.aws/credentials` or env vars | Same, but use `direnv` or `sops-nix` |
| Multi-arch buildx | Manual install | Add `docker-buildx` to shell |

### Nix Secrets Management

**Never** put AWS keys or secrets in flake configuration. Use one of:

- **direnv + dotenv**: Keep private `.env` outside git
- **sops-nix**: For encrypted secrets in repository
- **GitHub Secrets**: For CI/CD credentials

### Nix Environment Validation

Test your Nix development environment:

```bash
# Enter development shell
nix develop

# Validate tools are available
terraform --version
aws --version
docker --version

# Test AWS credentials (if configured)
nix develop -c aws sts get-caller-identity

# Test Docker access
nix develop -c docker version
```

## Local Testing Workflow

### Terraform Local Testing

Test infrastructure changes locally before CI deployment:

```bash
# 1. Enter development environment
nix develop  # (if using Nix) or ensure tools are installed

# 2. Initialize Terraform
cd infra
terraform init

# 3. Validate configuration
terraform validate
terraform fmt -check

# 4. Plan deployment (dry run)
terraform plan -var-file="terraform.tfvars"

# 5. Apply for testing (optional)
terraform apply -var-file="terraform.tfvars"

# 6. Cleanup when done
terraform destroy -var-file="terraform.tfvars"
```

### Quick Iteration Commands

| Task | Command |
|------|---------|
| Test user-data script only | `terraform apply -replace="aws_instance.foamai_instance"` |
| Test single resource | `terraform apply -target=aws_security_group.foamai_sg` |
| Test new variables | Edit `terraform.tfvars`, run `terraform plan` |

### Local Backend vs Remote

For local testing, use local state:
```hcl
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
```

Switch to S3 backend for production (one-line change).

## Code Contribution Guidelines

### Branch Management

- **main**: Production-ready code
- **feature/***: New features or improvements
- **bugfix/***: Bug fixes
- **docs/***: Documentation updates

### Commit Message Format

Use conventional commits:
```
type(scope): description

feat(api): add CFD solver endpoint
fix(docker): resolve volume mounting issue
docs(devops): update deployment guide
```

### Pull Request Process

1. **Create feature branch** from main
2. **Make changes** with clear, focused commits
3. **Test locally** using the local testing workflow
4. **Update documentation** if needed
5. **Submit pull request** with:
   - Clear description of changes
   - Test plan or validation steps
   - Reference to any related issues

### Code Review Requirements

- [ ] Code follows project conventions
- [ ] Tests pass (if applicable)
- [ ] Documentation updated
- [ ] Security considerations addressed
- [ ] Performance impact considered

## Development Tools

### Recommended IDE Setup

#### VS Code Extensions
- **Terraform**: HashiCorp Terraform
- **Docker**: Microsoft Docker
- **AWS**: AWS Toolkit
- **Nix**: Nix Language Support (for Nix users)

#### JetBrains IDEs
- **Terraform/HCL Plugin**
- **Docker Plugin**
- **AWS CloudFormation Plugin**

### Linting and Formatting

#### Python (UV + Ruff)
```bash
# Format Python code across workspace
uv run ruff format .

# Check Python code style and errors
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Type checking (if mypy is added)
uv run mypy src/

# Run all linting checks
uv sync --group lint
uv run ruff check . && uv run ruff format --check .
```

#### Terraform
```bash
# Format code
terraform fmt

# Validate syntax
terraform validate

# Advanced linting (if tflint available)
tflint
```

#### Shell Scripts
```bash
# Check syntax
bash -n script.sh

# Style checking (if shellcheck available)
shellcheck script.sh
```

### Debugging Tools

#### Terraform Debugging
```bash
# Enable debug logging
export TF_LOG=DEBUG
terraform apply

# Trace specific operations
export TF_LOG_PATH=./terraform.log
terraform plan
```

#### Docker Debugging
```bash
# Check container logs
docker-compose logs -f [service]

# Inspect running containers
docker ps
docker stats

# Debug container networking
docker network ls
docker network inspect foamai-network
```

#### AWS CLI Debugging
```bash
# Enable debug output
aws ec2 describe-instances --debug

# Test credentials
aws sts get-caller-identity

# Check specific regions
aws ec2 describe-regions
```

### Testing Infrastructure

#### Python Testing with UV
```bash
# Install test dependencies
uv sync --group test

# Run all tests
uv run pytest

# Run tests for specific package
uv run pytest src/foamai-core/
uv run pytest src/foamai-server/

# Run tests with coverage
uv run pytest --cov=src/ --cov-report=html

# Run tests matching pattern
uv run pytest -k "test_solver"

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_user_approval.py
```

#### Service Testing
FoamAI includes comprehensive testing tools for deployed services:

```bash
# Comprehensive Python test suite
uv run python test-foamai-service.py --host YOUR_IP --verbose

# Quick shell test for basic functionality
./test-foamai-quick.sh YOUR_IP

# Remote server inspection and diagnostics
./test-remote-server.sh YOUR_IP ~/.ssh/foamai-key
```

#### API Testing Workflow

```bash
# Test health endpoints
curl http://YOUR_IP:8000/ping
curl http://YOUR_IP:8000/api/health

# Test API documentation
curl -s http://YOUR_IP:8000/openapi.json | jq '.paths'

# View interactive documentation
open http://YOUR_IP:8000/docs
```

#### Infrastructure Testing

```bash
# Test network connectivity
telnet YOUR_IP 8000
telnet YOUR_IP 11111

# Test SSH access
ssh -i ~/.ssh/foamai-key ubuntu@YOUR_IP

# Check service status
ssh -i ~/.ssh/foamai-key ubuntu@YOUR_IP "sudo foamai-status"
```

#### Performance Testing

```bash
# Basic load testing
ab -n 100 -c 10 http://YOUR_IP:8000/ping

# Memory and CPU monitoring
ssh -i ~/.ssh/foamai-key ubuntu@YOUR_IP "htop"

# Docker container resource usage
ssh -i ~/.ssh/foamai-key ubuntu@YOUR_IP "docker stats"
```

#### Local Container Testing
```bash
# Test container setup locally
cd dev/
./local-test.sh setup      # Setup test environment
./local-test.sh build      # Build all containers
./local-test.sh test       # Run comprehensive tests
./local-test.sh cleanup    # Clean up resources

# Test individual operations
./local-test.sh start      # Start services
./local-test.sh status     # Check status
./local-test.sh logs       # View logs
./local-test.sh stop       # Stop services
```

#### Deployment Simulation
```bash
# Simulate AWS deployment locally
cd dev/
./simulate-deployment.sh full      # Full simulation
./simulate-deployment.sh init      # Initialize only
./simulate-deployment.sh test      # Test simulation
./simulate-deployment.sh cleanup   # Clean up
```

#### Infrastructure Testing
- **LocalStack**: Test AWS services locally
- **Terraform validate**: Validate infrastructure code
- **Docker Compose**: Test service orchestration locally

#### Staging Environment
- Use terraform workspaces for staging
- Test with minimal instance sizes
- Always clean up staging resources

### Common Development Tasks

#### Running Python Applications
```bash
# Start the API server
cd src/foamai-server
uv run python -m foamai_server.main

# Launch desktop application
cd src/foamai-desktop
uv run python -m foamai_desktop.main

# Use CLI tools
cd src/foamai-client
uv run foamai-cli --help

# Run examples
uv run python examples/demo_user_approval.py
uv run python examples/open_in_paraview.py
```

#### Package Development
```bash
# Add new dependency to core package
cd src/foamai-core
uv add numpy scipy

# Add development dependency
uv add --dev pytest-mock

# Remove dependency
uv remove httpx

# Update package dependencies
uv lock --upgrade
```

#### Container Development
```bash
# Build and test locally
docker build -t foamai/api:dev -f docker/api/Dockerfile .

# Test with docker-compose
docker-compose -f docker-compose.dev.yml up

# Export requirements for containers
uv export --package foamai-server --format requirements-txt > docker/api/requirements.txt
```

#### Testing User Data Scripts
```bash
# Validate syntax
bash -n infra/user_data.sh

# Test individual modules (if available)
cd infra/user_data_modules
./test_modules.sh
```

#### Infrastructure Updates
```bash
# Plan changes
terraform plan -out=changes.tfplan

# Review plan
terraform show changes.tfplan

# Apply changes
terraform apply changes.tfplan
```

## Troubleshooting Development Issues

### Nix-Specific Issues

| Problem | Solution |
|---------|----------|
| `docker: command not found` | Add `docker-client` to devShell packages |
| Cannot connect to Docker daemon | Install Docker via system package manager, add user to docker group |
| Terraform plugins fail | Ensure `TF_PLUGIN_CACHE_DIR` points to `$HOME` |
| AWS credentials not found | Verify `~/.aws/credentials` readable in devShell |

### General Development Issues

| Problem | Solution |
|---------|----------|
| Terraform state locked | `terraform force-unlock <lock-id>` |
| Docker permission denied | Add user to docker group, restart |
| AWS rate limiting | Add retry logic, use exponential backoff |
| Container build failures | Check Dockerfile syntax, verify base images |

### Getting Help

1. **Check existing documentation** in `docs_staging/`
2. **Search project issues** on GitHub
3. **Use debug modes** for detailed error information
4. **Test in isolation** to identify specific problems
5. **Ask in project discussions** or create an issue

---

*This contributing guide helps maintain code quality and development consistency. Update this document when adding new tools or changing development workflows.*