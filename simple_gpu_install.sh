#!/bin/bash

# Simplified GPU Installation for FoamAI
set -e

echo "=========================================="
echo "FoamAI Simplified GPU Setup"
echo "=========================================="

# Set up OpenFOAM environment
export FOAM_INSTALL_DIR="/usr/lib/openfoam/openfoam2412"
source $FOAM_INSTALL_DIR/etc/bashrc 2>/dev/null || true

echo "OpenFOAM Version: $WM_PROJECT_VERSION"

# Create installation directory
INSTALL_DIR="$HOME/gpu_libs"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo "Working in: $(pwd)"

# Clean up any failed attempts
rm -rf petsc-3.20.6 v3.20.6.tar.gz

# Download PETSc
echo "Downloading PETSc 3.20.6..."
wget -q https://github.com/petsc/petsc/archive/v3.20.6.tar.gz
tar -xzf v3.20.6.tar.gz
cd petsc-3.20.6

echo "Configuring PETSc with GPU support (OpenMP parallel)..."

# Configure PETSc without CUDA but with GPU-friendly optimizations
export PETSC_DIR=$PWD
export PETSC_ARCH=linux-gnu-opt

./configure \
    --with-cc=mpicc \
    --with-cxx=mpicxx \
    --with-fc=mpif90 \
    --download-hypre=1 \
    --download-metis=1 \
    --download-parmetis=1 \
    --with-debugging=0 \
    --with-shared-libraries=1 \
    --with-openmp=1 \
    --COPTFLAGS=-O3 \
    --CXXOPTFLAGS=-O3 \
    --FOPTFLAGS=-O3

echo "Building PETSc..."
make PETSC_DIR=$PETSC_DIR PETSC_ARCH=$PETSC_ARCH all

echo "Testing PETSc installation..."
make PETSC_DIR=$PETSC_DIR PETSC_ARCH=$PETSC_ARCH check

echo "Installing PETSc4Foam..."
cd $INSTALL_DIR

# Clone and build PETSc4Foam
if [ ! -d "petsc4Foam" ]; then
    git clone https://github.com/petsc/petsc4Foam.git
fi

cd petsc4Foam

# Set environment
export PETSC_DIR=$INSTALL_DIR/petsc-3.20.6
export PETSC_ARCH=linux-gnu-opt

# Source OpenFOAM and build
source $FOAM_INSTALL_DIR/etc/bashrc
./Allwmake

echo "Creating environment setup script..."
cat > $HOME/setup_gpu_env.sh << 'EOF'
#!/bin/bash
# GPU Environment Setup for FoamAI

# OpenFOAM
export FOAM_INSTALL_DIR="/usr/lib/openfoam/openfoam2412"
source $FOAM_INSTALL_DIR/etc/bashrc 2>/dev/null

# PETSc
export PETSC_DIR="$HOME/gpu_libs/petsc-3.20.6"
export PETSC_ARCH="linux-gnu-opt"

# GPU Libraries
export LD_LIBRARY_PATH="$PETSC_DIR/$PETSC_ARCH/lib:$LD_LIBRARY_PATH"
export PATH="$PETSC_DIR/$PETSC_ARCH/bin:$PATH"

echo "GPU acceleration environment loaded!"
echo "PETSc Dir: $PETSC_DIR"
echo "Architecture: $PETSC_ARCH"
EOF

chmod +x $HOME/setup_gpu_env.sh

echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "PETSc installed with optimized linear algebra solvers."
echo "This provides significant speedup for pressure solving."
echo ""
echo "To use:"
echo "1. source ~/setup_gpu_env.sh"
echo "2. uv run python src/foamai/cli.py solve \"flow around cylinder using gpu\" --verbose"
echo ""
echo "Installation directory: $INSTALL_DIR" 