# FoamAI Contributing Guide

A guide for developers contributing to the FoamAI project, including development environment setup and tooling recommendations.

## Table of Contents
- [Development Environment](#development-environment)
- [Nix Dev Shell Setup](#nix-dev-shell-setup)
- [Local Testing Workflow](#local-testing-workflow)
- [Code Contribution Guidelines](#code-contribution-guidelines)
- [Development Tools](#development-tools)

## Development Environment

### Prerequisites
- Git (version 2.0+)
- Docker (for local testing)
- Text editor or IDE of choice

### Repository Setup
```bash
# Clone the repository
git clone https://github.com/bbaserdem/FoamAI.git
cd FoamAI

# Set up development environment
# (See specific sections below for your OS)
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

#### Local Infrastructure Testing
- **LocalStack**: Test AWS services locally
- **Vagrant/Multipass**: Test scripts on local VMs
- **Docker Compose**: Test service orchestration

#### Staging Environment
- Use terraform workspaces for staging
- Test with minimal instance sizes
- Always clean up staging resources

### Common Development Tasks

#### Updating Container Images
```bash
# Build and test locally
docker build -t foamai/api:dev -f docker/api/Dockerfile .

# Test with docker-compose
docker-compose -f docker-compose.dev.yml up
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