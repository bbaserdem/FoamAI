<div align="center">
  <img src="assets/logo.png" alt="FoamAI Logo" width="200" height="200">
  
  # FoamAI - Natural Language CFD Assistant
  
  **AI-powered computational fluid dynamics (CFD) assistant that converts natural language descriptions into OpenFOAM simulations with ParaView visualization.**
  
  [![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
  [![OpenFOAM](https://img.shields.io/badge/OpenFOAM-10-green.svg)](https://openfoam.org/)
  [![ParaView](https://img.shields.io/badge/ParaView-6.0+-red.svg)](https://www.paraview.org/)
  [![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
  
</div>

## ✨ Key Features

- 🗣️ **Natural Language Interface** - Describe simulations in plain English
- 🤖 **AI-Powered Workflow** - LangGraph orchestrated multi-agent system  
- 🔧 **Automated Mesh Generation** - Intelligent mesh creation with validation
- 🎨 **3D Visualization** - Integrated ParaView for real-time results
- 🖥️ **Desktop & Server Modes** - GUI application and headless server deployment
- ☁️ **Cloud Ready** - AWS infrastructure with Terraform automation
- 📦 **Containerized** - Docker deployment for consistent environments
- 🚀 **Production Ready** - FastAPI backend with Celery task processing

## 🏗️ Project Structure

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

## 🚀 Quick Start

### 📋 Prerequisites

- Python 3.12+
- OpenFOAM 10
- ParaView 6.0+
- Docker & Docker Compose
- UV package manager

### 💻 Development Setup

1. **Clone and setup environment:**
```bash
git clone https://github.com/bbaserdem/FoamAI.git
cd FoamAI
uv sync
```

2. **Start local development:**
```bash
# Start local services
docker-compose -f dev/docker-compose.local.yml up -d

# Run the desktop application
uv run python -m foamai_desktop.main

# Or run examples
uv run python examples/demo_user_approval.py
```

3. **Run tests:**
```bash
uv run pytest tests/
```

### ☁️ Production Deployment

1. **Deploy infrastructure with Terraform:**
```bash
cd infra
terraform init
terraform apply
```

2. **Pre-built container images available:**
- `ghcr.io/bbaserdem/foamai/api:latest`
- `ghcr.io/bbaserdem/foamai/openfoam:latest` 
- `ghcr.io/bbaserdem/foamai/pvserver:latest`

3. **Or use the quick deployment script:**
```bash
./infra/deploy-fresh-instance.sh
```

## 📚 Documentation

Comprehensive documentation is available in the [docs/](docs/) directory:

- **[🤖 LangGraph Agents System](docs/Agents.md)** - AI agent architecture and workflow orchestration
- **[🔗 Backend API Reference](docs/BackendAPI.md)** - REST API endpoints and integration guide  
- **[🧠 Brainlift Guide](docs/Brainlift.md)** - Advanced AI capabilities and features
- **[🛠️ Contributing Guide](docs/Contributing.md)** - Development setup, workflows, and testing
- **[🖥️ Desktop Application Setup](docs/Desktop.md)** - GUI installation and usage guide
- **[🚀 DevOps Guide](docs/DevOps.md)** - Infrastructure deployment and monitoring

## 🏛️ Architecture

| Component | Technology | Purpose |
|-----------|------------|---------|
| **🔗 Backend** | FastAPI + Celery | REST API and async task processing |
| **🧠 AI Engine** | LangGraph + OpenAI | Multi-agent workflow orchestration |
| **⚙️ CFD Engine** | OpenFOAM 10 | Computational fluid dynamics solver |
| **🎨 Visualization** | ParaView 6.0 | 3D rendering and data visualization |
| **🖥️ Desktop App** | PySide6 + Qt | Cross-platform GUI application |
| **☁️ Infrastructure** | AWS EC2 + Terraform | Cloud deployment automation |
| **🚀 CI/CD** | GitHub Actions | Automated testing and deployment |
| **📦 Containers** | Docker + Docker Compose | Service orchestration |

## 🤝 Contributing

Welcome to FoamAI! To get started with development:

1. **Read the [Contributing Guide](docs/Contributing.md)** - Complete development setup and workflows
2. **Check [Desktop Setup](docs/Desktop.md)** - GUI application development
3. **Review [DevOps Guide](docs/DevOps.md)** - Infrastructure and deployment
4. **Explore [API Documentation](docs/BackendAPI.md)** - Backend development
5. **Run tests** from the [tests/](tests/) directory
6. **Try examples** from the [examples/](examples/) directory
7. **Use development tools** from [dev/](dev/) directory

### Quick Development Setup

```bash
# Clone and setup
git clone https://github.com/bbaserdem/FoamAI.git
cd FoamAI
uv sync

# Run tests
uv run pytest

# Start local development
cd dev && ./local-test.sh
```

## License

See [LICENSE](LICENSE) for details.
