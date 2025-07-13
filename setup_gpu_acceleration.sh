#!/bin/bash

# GPU Acceleration Setup Script for FoamAI
# This script installs PETSc with CUDA support and PETSc4Foam

set -e  # Exit on any error

echo "=========================================="
echo "FoamAI GPU Acceleration Setup"
echo "=========================================="

# Check if running in WSL
if ! grep -q WSL /proc/version 2>/dev/null; then
    echo "Error: This script must be run in WSL"
    exit 1
fi

# Check NVIDIA GPU
if ! nvidia-smi.exe >/dev/null 2>&1; then
    echo "Error: NVIDIA GPU not detected. Please install NVIDIA drivers."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    python3 \
    python3-pip \
    gfortran \
    libopenmpi-dev \
    openmpi-bin \
    libhdf5-dev \
    libmetis-dev \
    libparmetis-dev \
    libscotch-dev \
    libptscotch-dev \
    pkg-config

# Set up OpenFOAM environment
export FOAM_INSTALL_DIR="/usr/lib/openfoam/openfoam2412"
if [ ! -d "$FOAM_INSTALL_DIR" ]; then
    echo "Error: OpenFOAM not found at $FOAM_INSTALL_DIR"
    exit 1
fi

source $FOAM_INSTALL_DIR/etc/bashrc

echo "OpenFOAM Version: $WM_PROJECT_VERSION"
echo "Architecture: $WM_ARCH"
echo "Install Dir: $WM_PROJECT_DIR"

# Create installation directory
INSTALL_DIR="$HOME/gpu_libs"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Download and install PETSc with CUDA support
echo "=========================================="
echo "Installing PETSc with CUDA support..."
echo "=========================================="

if [ ! -d "petsc-3.20.6" ]; then
    wget -q https://github.com/petsc/petsc/archive/v3.20.6.tar.gz
    tar -xzf v3.20.6.tar.gz
fi

cd petsc-3.20.6

# Configure PETSc with CUDA support
export PETSC_DIR=$PWD
export PETSC_ARCH=linux-gnu-cuda-opt

./configure \
    --with-cc=mpicc \
    --with-cxx=mpicxx \
    --with-fc=mpif90 \
    --with-cuda=1 \
    --with-cuda-dir=/usr/local/cuda \
    --download-hypre=1 \
    --download-metis=1 \
    --download-parmetis=1 \
    --with-debugging=0 \
    --with-shared-libraries=1 \
    --COPTFLAGS=-O3 \
    --CXXOPTFLAGS=-O3 \
    --FOPTFLAGS=-O3

# Build PETSc
make PETSC_DIR=$PETSC_DIR PETSC_ARCH=$PETSC_ARCH all

# Test PETSc installation
make PETSC_DIR=$PETSC_DIR PETSC_ARCH=$PETSC_ARCH check

echo "PETSc installation completed!"

# Install PETSc4Foam
echo "=========================================="
echo "Installing PETSc4Foam..."
echo "=========================================="

cd $INSTALL_DIR

if [ ! -d "petsc4Foam" ]; then
    git clone https://github.com/petsc/petsc4Foam.git
fi

cd petsc4Foam

# Set PETSc environment
export PETSC_DIR=$INSTALL_DIR/petsc-3.20.6
export PETSC_ARCH=linux-gnu-cuda-opt

# Source OpenFOAM environment
source $FOAM_INSTALL_DIR/etc/bashrc

# Build PETSc4Foam
./Allwmake

echo "PETSc4Foam installation completed!"

# Create environment setup script
echo "=========================================="
echo "Creating environment setup script..."
echo "=========================================="

cat > $HOME/setup_gpu_env.sh << 'EOF'
#!/bin/bash
# GPU Environment Setup for FoamAI

# OpenFOAM
export FOAM_INSTALL_DIR="/usr/lib/openfoam/openfoam2412"
source $FOAM_INSTALL_DIR/etc/bashrc

# PETSc
export PETSC_DIR="$HOME/gpu_libs/petsc-3.20.6"
export PETSC_ARCH="linux-gnu-cuda-opt"

# GPU Libraries
export LD_LIBRARY_PATH="$PETSC_DIR/$PETSC_ARCH/lib:$LD_LIBRARY_PATH"
export PATH="$PETSC_DIR/$PETSC_ARCH/bin:$PATH"

# CUDA
export CUDA_HOME="/usr/local/cuda"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:$LD_LIBRARY_PATH"

echo "GPU acceleration environment loaded!"
echo "PETSc Dir: $PETSC_DIR"
echo "CUDA Home: $CUDA_HOME"
EOF

chmod +x $HOME/setup_gpu_env.sh

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To use GPU acceleration:"
echo "1. Run: source ~/setup_gpu_env.sh"
echo "2. Use FoamAI with: --use-gpu flag"
echo ""
echo "Test with:"
echo "uv run python src/foamai/cli.py solve \"flow around cylinder using gpu\" --verbose"
echo ""
echo "The GPU libraries are installed in: $INSTALL_DIR" 