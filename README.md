# FoamAI - Natural Language CFD Assistant

AI-powered computational fluid dynamics (CFD) assistant that converts natural language descriptions into OpenFOAM simulations with ParaView visualization.

## Project Structure

```
FoamAI/
├── src/                     # Core application code
│   ├── foamai-core/        # Core simulation logic
│   ├── foamai-server/      # FastAPI backend server
│   ├── foamai-client/      # Client library
│   └── foamai-desktop/     # Desktop application
├── infra/                  # AWS infrastructure (Terraform)
├── docker/                 # Container definitions
├── tests/                  # Test files
├── examples/               # Demo scripts and examples
├── dev/                    # Development utilities
├── docs/                   # Project documentation
└── .github/               # CI/CD workflows
```

## Quick Start

### Prerequisites

- Python 3.11+
- OpenFOAM 10
- ParaView 5.10+
- Docker & Docker Compose

### Development Setup

1. **Clone and setup environment:**
```bash
git clone https://github.com/bbaserdem/FoamAI.git
cd FoamAI
uv sync
```

2. **Local development:**
```bash
# Start local services
docker-compose -f dev/docker-compose.local.yml up -d

# Run examples
python examples/demo_user_approval.py
```

3. **Run tests:**
```bash
python -m pytest tests/
```

### Production Deployment

1. **Build and deploy via Terraform:**
```bash
cd infra
terraform apply
```

2. **Images are automatically built via GitHub Actions and available at:**
- `ghcr.io/bbaserdem/foamai/api:latest`
- `ghcr.io/bbaserdem/foamai/openfoam:latest` 
- `ghcr.io/bbaserdem/foamai/pvserver:latest`

## Documentation

- **[DevOps Documentation](docs/task_4_devops/)** - Deployment and infrastructure
- **[Testing Guide](docs/TESTING.md)** - Comprehensive testing documentation
- **[Development Workflow](docs/)** - Additional development guides

## Architecture

- **Backend:** FastAPI server with Celery workers
- **CFD Engine:** OpenFOAM 10 with Python integration
- **Visualization:** ParaView server for remote rendering
- **Infrastructure:** AWS EC2 with Terraform
- **CI/CD:** GitHub Actions with container registry

## Contributing

1. Check the [docs/](docs/) directory for project documentation
2. Run tests from the [tests/](tests/) directory
3. Try examples from the [examples/](examples/) directory
4. Use development configurations from [dev/](dev/)

## License

See [LICENSE](LICENSE) for details.
