# OpenFOAM Docker Container
# Based on Ubuntu 22.04 LTS for stability and OpenFOAM compatibility
FROM ubuntu:22.04

# Avoid timezone prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Set OpenFOAM version
ENV OPENFOAM_VERSION=10

# Install system dependencies and OpenFOAM
RUN apt-get update && apt-get install -y \
    # Core system utilities
    wget \
    curl \
    vim \
    git \
    # Build tools (needed for some OpenFOAM functionality)
    build-essential \
    cmake \
    # OpenFOAM dependencies
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    # Mathematical libraries
    libopenmpi-dev \
    openmpi-bin \
    openmpi-common \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Add OpenFOAM repository and install OpenFOAM
RUN wget -O - https://dl.openfoam.org/gpg.key | apt-key add - \
    && add-apt-repository http://dl.openfoam.org/ubuntu \
    && apt-get update \
    && apt-get install -y openfoam${OPENFOAM_VERSION} \
    && rm -rf /var/lib/apt/lists/*

# Create OpenFOAM user (non-root for security)
RUN groupadd -r openfoam && useradd -r -g openfoam -m -d /home/openfoam openfoam

# Set OpenFOAM environment variables
ENV FOAM_INST_DIR=/opt/openfoam${OPENFOAM_VERSION}
ENV FOAM_RUN=/home/openfoam/run
ENV WM_PROJECT_USER_DIR=/home/openfoam/OpenFOAM

# Source OpenFOAM environment (this needs to be done in scripts that use OpenFOAM)
ENV BASH_ENV=/opt/openfoam${OPENFOAM_VERSION}/etc/bashrc

# Create necessary directories
RUN mkdir -p /home/openfoam/run \
    && mkdir -p /data \
    && chown -R openfoam:openfoam /home/openfoam \
    && chown -R openfoam:openfoam /data

# Set working directory
WORKDIR /home/openfoam

# Switch to openfoam user
USER openfoam

# Create a proper test script to verify installation
RUN echo '#!/bin/bash' > /home/openfoam/test-openfoam.sh \
    && echo 'source /opt/openfoam${OPENFOAM_VERSION}/etc/bashrc 2>/dev/null' >> /home/openfoam/test-openfoam.sh \
    && echo 'echo "Testing OpenFOAM installation..."' >> /home/openfoam/test-openfoam.sh \
    && echo 'which blockMesh && echo "blockMesh found ✓"' >> /home/openfoam/test-openfoam.sh \
    && echo 'which foamJob && echo "foamJob found ✓"' >> /home/openfoam/test-openfoam.sh \
    && echo 'echo "OpenFOAM installation test completed successfully!"' >> /home/openfoam/test-openfoam.sh \
    && chmod +x /home/openfoam/test-openfoam.sh

# Default command to keep container running
CMD ["/bin/bash"]

# Expose any ports that might be needed (can be overridden)
EXPOSE 8080

# Health check to ensure OpenFOAM is working
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD bash -c "source /opt/openfoam${OPENFOAM_VERSION}/etc/bashrc 2>/dev/null && which blockMesh" || exit 1 