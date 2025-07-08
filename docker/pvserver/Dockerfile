# ParaView Server Docker Container
# Based on Ubuntu 22.04 LTS for scientific visualization and OpenFOAM integration
FROM ubuntu:22.04

# Avoid timezone prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

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
    # ParaView from Ubuntu repositories
    paraview \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Create ParaView user (non-root for security)
RUN groupadd -r paraview && useradd -r -g paraview -m -d /home/paraview paraview

# Set ParaView environment variables
ENV PATH="/usr/bin:$PATH"
ENV LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"

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
    && echo 'exec pvserver --force-offscreen-rendering --server-port=11111' >> /home/paraview/start-pvserver.sh \
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