# ParaView Server Docker Container
# Based on Ubuntu 22.04 LTS for scientific visualization and OpenFOAM integration
FROM ubuntu:22.04

# Avoid timezone prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ParaView version and configuration
ENV PARAVIEW_VERSION=5.11
ENV PARAVIEW_MAJOR_VERSION=5.11
ENV PARAVIEW_FULL_VERSION=5.11.2

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Core utilities
    wget \
    curl \
    unzip \
    # OpenGL and visualization libraries
    libgl1-mesa-glx \
    libglu1-mesa \
    libglvnd0 \
    libgl1 \
    libglx0 \
    libegl1 \
    libxrender1 \
    libxcursor1 \
    libxft2 \
    libxinerama1 \
    # X11 libraries for remote visualization
    libx11-6 \
    libxext6 \
    libxrandr2 \
    libxss1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    # MPI support (for parallel processing)
    libopenmpi-dev \
    openmpi-bin \
    openmpi-common \
    # Python support for ParaView
    python3 \
    python3-pip \
    # Networking utilities
    netcat \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Create ParaView user (non-root for security)
RUN groupadd -r paraview && useradd -r -g paraview -m -d /home/paraview paraview

# Download and install ParaView
RUN mkdir -p /opt/paraview && cd /opt/paraview \
    && wget -O paraview.tar.gz "https://www.paraview.org/files/v${PARAVIEW_VERSION}/ParaView-${PARAVIEW_FULL_VERSION}-MPI-Linux-Python3.10-x86_64.tar.gz" \
    && tar -xzf paraview.tar.gz --strip-components=1 \
    && rm paraview.tar.gz \
    && chown -R paraview:paraview /opt/paraview

# Set ParaView environment variables
ENV PATH="/opt/paraview/bin:$PATH"
ENV PARAVIEW_ROOT="/opt/paraview"
ENV LD_LIBRARY_PATH="/opt/paraview/lib:$LD_LIBRARY_PATH"

# Create necessary directories
RUN mkdir -p /data \
    && mkdir -p /home/paraview/logs \
    && chown -R paraview:paraview /data \
    && chown -R paraview:paraview /home/paraview

# Set working directory
WORKDIR /home/paraview

# Switch to paraview user
USER paraview

# Create a startup script for ParaView server
RUN echo '#!/bin/bash' > /home/paraview/start-pvserver.sh \
    && echo 'echo "Starting ParaView server..."' >> /home/paraview/start-pvserver.sh \
    && echo 'echo "ParaView version: $(pvserver --version 2>&1 | head -1)"' >> /home/paraview/start-pvserver.sh \
    && echo 'echo "Listening on port 11111..."' >> /home/paraview/start-pvserver.sh \
    && echo 'exec pvserver --use-offscreen-rendering --server-port=11111' >> /home/paraview/start-pvserver.sh \
    && chmod +x /home/paraview/start-pvserver.sh

# Create a test script to verify ParaView installation
RUN echo '#!/bin/bash' > /home/paraview/test-paraview.sh \
    && echo 'echo "Testing ParaView installation..."' >> /home/paraview/test-paraview.sh \
    && echo 'which pvserver && echo "pvserver found ✓"' >> /home/paraview/test-paraview.sh \
    && echo 'which paraview && echo "paraview found ✓"' >> /home/paraview/test-paraview.sh \
    && echo 'pvserver --version && echo "ParaView version check ✓"' >> /home/paraview/test-paraview.sh \
    && echo 'echo "ParaView installation test completed successfully!"' >> /home/paraview/test-paraview.sh \
    && chmod +x /home/paraview/test-paraview.sh

# Expose ParaView server port
EXPOSE 11111

# Health check to ensure ParaView server is accessible
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD netcat -z localhost 11111 || exit 1

# Default command to run ParaView server
CMD ["/home/paraview/start-pvserver.sh"] 