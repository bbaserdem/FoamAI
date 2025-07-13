#!/bin/bash

# Continue GPU Installation for FoamAI
set -e

echo "Continuing GPU acceleration setup..."

# Set up OpenFOAM environment (ignore warnings)
export FOAM_INSTALL_DIR="/usr/lib/openfoam/openfoam2412"
source $FOAM_INSTALL_DIR/etc/bashrc 2>/dev/null || true

echo "OpenFOAM Version: $WM_PROJECT_VERSION"
echo "Install Dir: $WM_PROJECT_DIR"

# Create installation directory
INSTALL_DIR="$HOME/gpu_libs"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo "Working directory: $(pwd)"

# Download PETSc if not already downloaded
if [ ! -d "petsc-3.20.6" ]; then
    echo "Downloading PETSc..."
    wget -q https://github.com/petsc/petsc/archive/v3.20.6.tar.gz
    tar -xzf v3.20.6.tar.gz
    echo "PETSc downloaded and extracted"
fi

cd petsc-3.20.6

echo "Configuring PETSc with CUDA support..."

# Configure PETSc with CUDA support
export PETSC_DIR=$PWD
export PETSC_ARCH=linux-gnu-cuda-opt

# Check if CUDA is available
if [ -d "/usr/local/cuda" ]; then
    CUDA_DIR="/usr/local/cuda"
elif [ -d "/usr/lib/cuda" ]; then
    CUDA_DIR="/usr/lib/cuda"
else
    echo "Warning: CUDA directory not found, using default path"
    CUDA_DIR="/usr/local/cuda"
fi

echo "Using CUDA directory: $CUDA_DIR"

# Configure PETSc
./configure \
    --with-cc=mpicc \
    --with-cxx=mpicxx \
    --with-fc=mpif90 \
    --with-cuda=1 \
    --with-cuda-dir=$CUDA_DIR \
    --download-hypre=1 \
    --download-metis=1 \
    --download-parmetis=1 \
    --with-debugging=0 \
    --with-shared-libraries=1 \
    --COPTFLAGS=-O3 \
    --CXXOPTFLAGS=-O3 \
    --FOPTFLAGS=-O3

echo "PETSc configuration completed!"
echo "Starting PETSc compilation (this will take 10-20 minutes)..."

# Build PETSc
make PETSC_DIR=$PETSC_DIR PETSC_ARCH=$PETSC_ARCH all

echo "PETSc compilation completed!"
echo "Running PETSc tests..."

# Test PETSc installation
make PETSC_DIR=$PETSC_DIR PETSC_ARCH=$PETSC_ARCH check

echo "PETSc installation and testing completed successfully!" 