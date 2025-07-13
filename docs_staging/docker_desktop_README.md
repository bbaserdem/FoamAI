# FoamAI Desktop Docker Container

A complete Docker container for the FoamAI Desktop Application with ParaView 6.0.0, Python 3.12, and all dependencies pre-installed.

## Features

- 🐳 **Containerized**: Complete desktop environment in Docker
- 🐍 **Python 3.12**: Latest stable Python version
- 📊 **ParaView 6.0.0**: Pre-installed with Python bindings
- 🖥️ **GUI Support**: X11 forwarding for native desktop experience
- 🔧 **Pre-configured**: All dependencies and environment variables set up
- 🌐 **Cross-platform**: Works on Windows, macOS, and Linux

## Quick Start

### Prerequisites

1. **Docker and Docker Compose** installed
2. **X11 Server** (for GUI display):
   - **Linux**: Usually pre-installed
   - **macOS**: Install XQuartz
   - **Windows**: Install VcXsrv or X410

### Linux/macOS Quick Start

```bash
# Allow X11 forwarding
xhost +local:docker

# Run with Docker Compose
docker-compose -f docker-compose.desktop.yml up

# Or run directly
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $HOME/.Xauthority:/tmp/.Xauthority \
  --network host \
  foamai-desktop
```

### Windows Quick Start

1. **Install and start VcXsrv**:
   - Download from: https://sourceforge.net/projects/vcxsrv/
   - Start XLaunch with "Disable access control" checked

2. **Run the container**:
```powershell
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  foamai-desktop
```

## Building the Container

### Build from Source

```bash
# Build the desktop container
docker build -f docker/desktop/Dockerfile -t foamai-desktop .

# Or use Docker Compose
docker-compose -f docker-compose.desktop.yml build
```

### Build Arguments

The Dockerfile supports several build arguments:

```bash
docker build \
  --build-arg PYTHON_VERSION=3.12 \
  --build-arg PARAVIEW_VERSION=6.0.0 \
  -f docker/desktop/Dockerfile \
  -t foamai-desktop .
```

## Configuration

### Environment Variables

The container can be configured using environment variables:

#### Server Configuration
- `SERVER_HOST`: FoamAI server hostname (default: `host.docker.internal`)
- `SERVER_PORT`: FoamAI server port (default: `8000`)
- `PARAVIEW_SERVER_HOST`: ParaView server hostname (default: `host.docker.internal`)
- `PARAVIEW_SERVER_PORT`: ParaView server port (default: `11111`)

#### Application Settings
- `WINDOW_WIDTH`: Application window width (default: `1200`)
- `WINDOW_HEIGHT`: Application window height (default: `800`)
- `CHAT_HISTORY_LIMIT`: Chat history limit (default: `100`)
- `PARAVIEW_TIMEOUT`: ParaView connection timeout (default: `30`)
- `REQUEST_TIMEOUT`: API request timeout (default: `60`)

#### Display Settings
- `DISPLAY`: X11 display (default: `:0`)
- `QT_X11_NO_MITSHM`: Disable shared memory for Qt (default: `1`)

### Configuration File

Create a `.env` file in the `docker/desktop/` directory:

```env
# FoamAI Desktop Configuration
SERVER_HOST=your-server-host
SERVER_PORT=8000
PARAVIEW_SERVER_HOST=your-paraview-host
PARAVIEW_SERVER_PORT=11111

# Application Settings
WINDOW_WIDTH=1400
WINDOW_HEIGHT=900
CHAT_HISTORY_LIMIT=200
PARAVIEW_TIMEOUT=45
REQUEST_TIMEOUT=120
```

## Usage Examples

### Development Setup

```bash
# Start with local servers
docker-compose -f docker-compose.desktop.yml up

# Start with external servers
SERVER_HOST=my-server.com \
PARAVIEW_SERVER_HOST=my-paraview.com \
docker-compose -f docker-compose.desktop.yml up
```

### Production Deployment

```bash
# Run with specific configuration
docker run -d \
  --name foamai-desktop \
  -e DISPLAY=$DISPLAY \
  -e SERVER_HOST=production-server.com \
  -e SERVER_PORT=8000 \
  -e PARAVIEW_SERVER_HOST=paraview-server.com \
  -e PARAVIEW_SERVER_PORT=11111 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v foamai-logs:/app/logs \
  --network host \
  foamai-desktop
```

### Custom Python Scripts

```bash
# Run custom Python script in the container
docker run -it --rm \
  -v $(pwd)/my_script.py:/app/my_script.py \
  foamai-desktop \
  python3.12 /app/my_script.py
```

## Platform-Specific Instructions

### Linux

```bash
# Install Docker and Docker Compose
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Allow X11 forwarding
xhost +local:docker

# Run the application
docker-compose -f docker-compose.desktop.yml up
```

### macOS

```bash
# Install XQuartz
brew install --cask xquartz

# Start XQuartz and allow connections
open -a XQuartz
# In XQuartz preferences, enable "Allow connections from network clients"

# Set display and run
export DISPLAY=host.docker.internal:0
docker-compose -f docker-compose.desktop.yml up
```

### Windows

1. **Install VcXsrv**:
   - Download and install VcXsrv
   - Run XLaunch with settings:
     - Multiple windows
     - Display number: 0
     - Start no client
     - **Important**: Check "Disable access control"

2. **Run the container**:
```powershell
# PowerShell
$env:DISPLAY = "host.docker.internal:0"
docker-compose -f docker-compose.desktop.yml up
```

## Troubleshooting

### GUI Not Displaying

1. **Check X11 server is running**:
   - Linux: `echo $DISPLAY`
   - macOS: Ensure XQuartz is running
   - Windows: Ensure VcXsrv is running

2. **Check X11 permissions**:
   ```bash
   # Linux/macOS
   xhost +local:docker
   
   # Or for specific IP
   xhost +192.168.1.100
   ```

3. **Verify display forwarding**:
   ```bash
   # Test with simple GUI app
   docker run -it --rm \
     -e DISPLAY=$DISPLAY \
     -v /tmp/.X11-unix:/tmp/.X11-unix \
     ubuntu:22.04 \
     bash -c "apt-get update && apt-get install -y x11-apps && xclock"
   ```

### Connection Issues

1. **Server not reachable**:
   - Check `SERVER_HOST` and `SERVER_PORT` settings
   - Verify network connectivity
   - Use `host.docker.internal` for services running on host

2. **ParaView connection fails**:
   - Verify ParaView server is running
   - Check `PARAVIEW_SERVER_HOST` and `PARAVIEW_SERVER_PORT`
   - Ensure firewall allows connections

### Performance Issues

1. **Slow GUI response**:
   - Enable hardware acceleration: `--device /dev/dri:/dev/dri`
   - Increase shared memory: `--shm-size=1g`
   - Use host networking: `--network host`

2. **Memory issues**:
   - Increase container memory limit
   - Monitor with `docker stats`

### Container Issues

1. **Permission errors**:
   ```bash
   # Run with correct user ID
   docker run --user $(id -u):$(id -g) ...
   ```

2. **Python import errors**:
   ```bash
   # Check Python path
   docker run -it foamai-desktop python3.12 -c "import sys; print(sys.path)"
   ```

3. **ParaView not found**:
   ```bash
   # Verify ParaView installation
   docker run -it foamai-desktop ls -la /opt/paraview/
   ```

## Development

### Extending the Container

To add new dependencies:

1. Modify `docker/desktop/requirements.txt`
2. Rebuild the container:
   ```bash
   docker-compose -f docker-compose.desktop.yml build --no-cache
   ```

### Debugging

```bash
# Run interactive shell
docker run -it --rm foamai-desktop bash

# Check logs
docker logs foamai-desktop

# Monitor resources
docker stats foamai-desktop
```

## Security Considerations

- The container runs as a non-root user (`foamuser`)
- X11 forwarding should be used with caution in production
- Consider using VNC or remote desktop solutions for production deployments
- Limit network access with appropriate firewall rules

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Verify your X11 server configuration
3. Check Docker logs: `docker logs foamai-desktop`
4. Test with minimal examples provided

## License

This container configuration is part of the FoamAI project and follows the same license terms. 