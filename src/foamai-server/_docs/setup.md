# FoamAI Backend API Setup Guide

This document provides step-by-step instructions for setting up the FoamAI backend API on a fresh Ubuntu 22.04 server.

## Prerequisites

- Fresh Ubuntu 22.04 server with root or sudo access
- At least 4GB RAM and 20GB disk space
- Internet connectivity for downloading packages

## Table of Contents

1. [System Updates and Basic Dependencies](#1-system-updates-and-basic-dependencies)
2. [Python Environment Setup](#2-python-environment-setup)
3. [OpenFOAM Installation](#3-openfoam-installation)
4. [ParaView Installation](#4-paraview-installation)
5. [Project Setup](#5-project-setup)
6. [Environment Configuration](#6-environment-configuration)
7. [Database Setup](#7-database-setup)
8. [Service Configuration](#8-service-configuration)
9. [Testing the Installation](#9-testing-the-installation)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. System Updates and Basic Dependencies

First, update the system and install essential packages:

```bash
# Update package lists and upgrade system
sudo apt update && sudo apt upgrade -y

# Install essential build tools and dependencies
sudo apt install -y \
    build-essential \
    wget \
    tmux \
    git

# Install Python development dependencies
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-setuptools
```

## 2. Python Environment Setup

Set up Python environment and install uv package manager:

```bash
# Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Verify uv installation
uv --version
```

## 3. OpenFOAM Installation

Install OpenFOAM for CFD simulation capabilities:

```bash
# Add OpenFOAM repository
curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash

# Update package lists
sudo apt update

# Install OpenFOAMv2412
sudo apt-get install openfoam2412-default

# Add OpenFOAM to PATH (add to ~/.bashrc for persistence)
echo 'source /usr/lib/openfoam/openfoam2412/etc/bashrc' >> ~/.bashrc
source ~/.bashrc

# Verify OpenFOAM installation
which blockMesh
```

## 4. ParaView Installation

Install ParaView for visualization and pvserver functionality:

```bash
# Install ParaView from Ubuntu repositories
sudo apt install -y paraview

# Or install a specific version from ParaView website (recommended for latest features)
cd /tmp
wget "https://www.paraview.org/paraview-downloads/download.php?submit=Download&version=v6.0&type=binary&os=Linux&downloadFile=ParaView-6.0.0-RC2-MPI-Linux-Python3.12-x86_64.tar.gz" -O paraview.tar.gz
tar -xzf paraview.tar.gz
sudo mv ParaView-6.0.0-RC2-MPI-Linux-Python3.12-x86_64 /opt/paraview
sudo ln -s /opt/paraview/bin/paraview /usr/local/bin/paraview
sudo ln -s /opt/paraview/bin/pvserver /usr/local/bin/pvserver

# Verify ParaView installation
which pvserver
pvserver --version
```

## 5. Project Setup

Clone and set up the FoamAI project:

```bash
# Create application directory
sudo mkdir -p /opt/foamai
cd /opt/foamai

# Clone the repository (adjust URL as needed)
git clone https://github.com/bbaserdem/FoamAI .
# Or copy your project files here

# Navigate to the backend API directory
cd src/foamai-server

# Create Python virtual environment using uv
uv venv venv
source venv/bin/activate

# Install Python dependencies
uv pip install -r requirements.txt
```

## 6. Environment Configuration

Set up environment variables and configuration:

```bash
# Create environment file
cat > .env << 'EOF'
# API Configuration
API_PORT=8000
EC2_HOST=0.0.0.0
EOF
```

## 7. Database Setup

Initialize the database:

```bash
# Navigate to the backend directory
cd /opt/foamai/src/foamai-server

# Activate virtual environment
source venv/bin/activate

# Initialize the database
python foamai_server/init_database.py
```

## 8. Start the Server

```bash
# Navigate to the backend directory
cd /opt/foamai/src/foamai-server
```

Start celery in a detached session
```bash
# Start new tmux session
tmux new -s celery

# Activate virtual environment
source venv/bin/activate

# Run celery
uv run celery -A celery_worker worker --loglevel=info

# Now press `ctrl+b` then `d` to detach the session
```

Start FastAPI server in a detached session
```bash
# Start new tmux session
tmux new -s fastapi

# Activate virtual environment
source venv/bin/activate

# Run the FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000

# Now press `ctrl+b` then `d` to detach the session
```

## 9. Testing the Installation

Verify that everything is working correctly:

```bash
# Test API health endpoint
curl http://localhost:8000/health

# Test pvserver functionality
curl -X POST http://localhost:8000/api/pvservers/clear-all

# Test OpenFOAM commands
blockMesh -help

# Test ParaView server
pvserver --help
```

## 10. Troubleshooting

### Common Issues and Solutions

#### Issue: OpenFOAM commands not found
```bash
# Check if OpenFOAM is properly sourced
source /opt/openfoam10/etc/bashrc
which blockMesh

# Add to service environment if needed
sudo systemctl edit foamai-api.service
# Add under [Service]:
# Environment=PATH=/opt/openfoam10/bin:$PATH
```

#### Issue: ParaView/pvserver not found
```bash
# Check pvserver installation
which pvserver
pvserver --version

# If not found, ensure it's in PATH
export PATH=/opt/paraview/bin:$PATH
```

### Firewall Configuration

If using UFW firewall:

```bash
# Allow API port
sudo ufw allow 8000/tcp

# Allow pvserver port range
sudo ufw allow 11111:11116/tcp

# Enable firewall
sudo ufw enable
```

---

## Summary

After completing these steps, you should have:

1. ✅ A fully functional FoamAI backend API running on Ubuntu 22.04
2. ✅ OpenFOAM installed and configured for CFD simulations
3. ✅ ParaView with pvserver capabilities for visualization
5. ✅ Proper environment configuration and database setup

The API should be accessible at `http://your-server-ip:8000` and ready to handle OpenFOAM simulation requests and pvserver management.

For additional configuration or advanced deployment scenarios, refer to the project documentation or contact the development team. 