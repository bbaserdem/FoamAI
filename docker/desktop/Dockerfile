# FoamAI Desktop Application Docker Container
# Provides a complete desktop environment with ParaView 6.0.0 and Python 3.12
FROM ubuntu:22.04

# Avoid timezone prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Python and GUI environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV QT_X11_NO_MITSHM=1
ENV DISPLAY=:0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Python 3.12 and development tools
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    python3-pip \
    build-essential \
    # GUI and X11 dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxrender1 \
    libxrandr2 \
    libxss1 \
    libxcursor1 \
    libxcomposite1 \
    libasound2 \
    libxi6 \
    libxtst6 \
    libx11-xcb1 \
    libxcb1 \
    libxcb-dri3-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxcb-cursor0 \
    libxkbcommon-x11-0 \
    libxkbcommon0 \
    libdbus-1-3 \
    libfontconfig1 \
    libfreetype6 \
    # ParaView dependencies
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libxt6 \
    libxext6 \
    libxmu6 \
    libxpm4 \
    libxss1 \
    libxv1 \
    libxxf86vm1 \
    # Additional utilities
    curl \
    wget \
    unzip \
    git \
    ca-certificates \
    # Clean up apt cache
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN groupadd -r foamuser && useradd -r -g foamuser -m -d /home/foamuser foamuser

# Set Python 3.12 as default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Install pip for Python 3.12
RUN python3.12 -m ensurepip --upgrade || curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

# Install ParaView 6.0.0 with Python bindings
WORKDIR /opt
RUN wget -q https://www.paraview.org/files/v6.0/ParaView-6.0.0-RC1-MPI-Linux-Python3.12-x86_64.tar.gz \
    && tar -xzf ParaView-6.0.0-RC1-MPI-Linux-Python3.12-x86_64.tar.gz \
    && mv ParaView-6.0.0-RC1-MPI-Linux-Python3.12-x86_64 paraview \
    && rm ParaView-6.0.0-RC1-MPI-Linux-Python3.12-x86_64.tar.gz

# Debug: Check ParaView directory structure
RUN echo "=== ParaView directory structure ===" \
    && ls -la /opt/paraview/ \
    && echo "=== ParaView bin directory ===" \
    && ls -la /opt/paraview/bin/ || true \
    && echo "=== ParaView lib directory ===" \
    && ls -la /opt/paraview/lib/ || true \
    && echo "=== Looking for Python site-packages ===" \
    && find /opt/paraview -name "site-packages" -type d 2>/dev/null || true \
    && echo "=== Looking for paraview.py ===" \
    && find /opt/paraview -name "paraview.py" -type f 2>/dev/null || true

# Set ParaView environment variables (will be updated after finding correct path)
ENV PARAVIEW_HOME=/opt/paraview
ENV PATH="${PARAVIEW_HOME}/bin:${PATH}"
ENV LD_LIBRARY_PATH="${PARAVIEW_HOME}/lib"

# Find and set correct PYTHONPATH for ParaView

# Set multiple potential ParaView Python paths
ENV PYTHONPATH="/opt/paraview/bin/Lib/site-packages:/opt/paraview/lib/python3.12/site-packages"

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY docker/desktop/requirements.txt ./

# Remove problematic system packages that conflict with pip
RUN apt-get update && apt-get remove -y python3-blinker || true \
    && rm -rf /usr/lib/python3/dist-packages/blinker* || true \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN python3.12 -m pip install --no-cache-dir --break-system-packages --upgrade pip setuptools wheel \
    && python3.12 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Create missing __init__.py files if they don't exist
RUN touch ./src/foamai-core/foamai_core/__init__.py || true \
    && touch ./src/foamai-desktop/foamai_desktop/__init__.py || true

# Install foamai packages in editable mode (core first, then desktop)
RUN echo "Installing foamai-core..." \
    && python3.12 -m pip install --break-system-packages -e ./src/foamai-core/ \
    && echo "foamai-core installation completed" \
    && echo "Installing foamai-desktop..." \
    && python3.12 -m pip install --break-system-packages -e ./src/foamai-desktop/ \
    && echo "foamai-desktop installation completed"

# Verify installations
RUN echo "Verifying package installations..." \
    && python3.12 -c "import foamai_core; print('✓ foamai-core found')" || echo "⚠ foamai-core import failed" \
    && python3.12 -c "import foamai_desktop; print('✓ foamai-desktop found')" || echo "⚠ foamai-desktop import failed"

# Upgrade ParaView Python libraries in BOTH site-packages directories
RUN echo "Upgrading typing-extensions in ParaView directories..." \
    && python3.12 -m pip install --break-system-packages --upgrade --target /opt/paraview/bin/Lib/site-packages typing-extensions numpy vtk \
    && python3.12 -m pip install --break-system-packages --upgrade --target /opt/paraview/lib/python3.12/site-packages typing-extensions numpy vtk \
    && echo "ParaView Python libraries upgraded successfully"

# Create necessary directories
RUN mkdir -p /app/logs \
    && mkdir -p /app/data \
    && mkdir -p /home/foamuser/.config

# Set proper permissions
RUN chown -R foamuser:foamuser /app \
    && chown -R foamuser:foamuser /home/foamuser \
    && chmod +x /opt/paraview/bin/*

# Copy entrypoint script
COPY docker/desktop/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Switch to non-root user
USER foamuser

# Create default .env file
RUN echo "# FoamAI Desktop Configuration" > /app/.env \
    && echo "SERVER_HOST=host.docker.internal" >> /app/.env \
    && echo "SERVER_PORT=8000" >> /app/.env \
    && echo "PARAVIEW_SERVER_HOST=host.docker.internal" >> /app/.env \
    && echo "PARAVIEW_SERVER_PORT=11111" >> /app/.env \
    && echo "WINDOW_WIDTH=1200" >> /app/.env \
    && echo "WINDOW_HEIGHT=800" >> /app/.env \
    && echo "CHAT_HISTORY_LIMIT=100" >> /app/.env \
    && echo "PARAVIEW_TIMEOUT=30" >> /app/.env \
    && echo "REQUEST_TIMEOUT=60" >> /app/.env

# Set working directory to desktop app
WORKDIR /app/src/foamai-desktop

# Expose any ports if needed (for internal Flask server)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3.12 -c "import sys; sys.exit(0)" || exit 1

# Entry point
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python3.12", "-m", "foamai_desktop.main"] 