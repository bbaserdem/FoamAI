# FoamAI Modular User Data Scripts

This directory contains the modular components that are **embedded into the main `user_data.sh` script** for FoamAI EC2 instance deployment. These modules are maintained separately for development, testing, and maintenance purposes, but the actual deployment uses a single, self-contained script.

## 🚀 **Deployment Note**

**For actual deployment**, Terraform uses the unified `../user_data.sh` script which embeds all these modules. This ensures:
- ✅ Single file deployment (no file transfer issues)  
- ✅ All modules guaranteed to be available
- ✅ Maintains modular structure for development
- ✅ No changes needed to Terraform configuration

## 🏗️ Architecture Overview

The deployment process is now split into **6 modular components** plus a **utilities library**, orchestrated by a main script:

```
infra/user_data_improved.sh          # Main orchestrator
├── user_data_modules/
│   ├── utils.sh                     # Utility functions & logging
│   ├── 01_system_update.sh          # System packages & AWS metadata
│   ├── 02_docker_setup.sh           # Docker & Docker Compose installation
│   ├── 03_ebs_volume_setup.sh       # Robust EBS volume mounting
│   ├── 04_application_setup.sh      # Repository & environment setup
│   ├── 05_service_setup.sh          # Systemd services & monitoring
│   └── 06_docker_operations.sh      # Image pulling & service startup
```

## 🔥 Key Improvements

### 1. **Robust Error Handling**
- **Retry logic** with exponential backoff for network operations
- **Comprehensive validation** after each critical step
- **Graceful failure handling** with detailed error reporting
- **Cleanup procedures** for failed deployments

### 2. **EBS Volume Mounting (Major Fix)**
- **Multiple discovery strategies** (size-based, metadata-based, unused device)
- **Flexible device naming** support for different instance types
- **Waiting logic** for volume attachment timing
- **Fallback mechanisms** when volumes are not available

### 3. **Docker Group Membership (Major Fix)**
- **Proper group membership** using `newgrp` command
- **Validation** of Docker access before proceeding
- **Immediate group activation** without logout/login

### 4. **Comprehensive Logging**
- **Structured logging** with timestamps and levels
- **Color-coded output** for better visibility
- **Debug mode** support for troubleshooting
- **Automatic log rotation** setup

### 5. **Service Management**
- **Systemd integration** with proper service files
- **Health checking** and monitoring
- **Service validation** before considering deployment complete
- **Management scripts** for easy operation

## 📋 Module Details

### `utils.sh` - Utility Functions
**Purpose**: Provides core functionality used by all modules

**Key Functions**:
- `log_info()`, `log_warn()`, `log_error()`, `log_debug()` - Structured logging
- `retry_command()` - Retry logic with exponential backoff
- `check_network()` - Network connectivity validation
- `check_service_status()` - Service health checking
- `wait_for_file()`, `wait_for_block_device()` - Resource waiting

### `01_system_update.sh` - System Setup
**Purpose**: Updates system packages and retrieves AWS metadata

**Key Features**:
- Network connectivity check before updates
- Disk space validation
- Essential package installation with verification
- AWS metadata retrieval (region, instance ID, instance type)
- Retry logic for package operations

### `02_docker_setup.sh` - Docker Installation
**Purpose**: Installs Docker and Docker Compose with proper configuration

**Key Features**:
- Docker CE installation with official repositories
- Docker Compose standalone installation
- Service startup and validation
- User group management with immediate activation
- Optimized daemon configuration
- Functionality testing with hello-world container

### `03_ebs_volume_setup.sh` - Storage Setup
**Purpose**: Handles EBS volume detection, formatting, and mounting

**Key Features**:
- **Multi-strategy volume discovery**:
  - Size-based discovery (most flexible)
  - AWS metadata-based discovery (most authoritative)
  - Unused device discovery (fallback)
- **Flexible device naming** support for all instance types
- **Waiting logic** for volume attachment
- **UUID-based persistent mounting**
- **Fallback to root volume** when no EBS volume is available

### `04_application_setup.sh` - Application Setup
**Purpose**: Clones repository and sets up application environment

**Key Features**:
- Repository cloning with validation
- Environment configuration generation
- Data directory structure creation
- Permission management
- Application logging setup
- Repository structure validation

### `05_service_setup.sh` - Service Management
**Purpose**: Creates systemd services and monitoring infrastructure

**Key Features**:
- Systemd service file creation with security settings
- Log rotation configuration
- Status monitoring script (`foamai-status`)
- Health checking script (`foamai-health`)
- Service management scripts (`foamai-start`, `foamai-stop`, `foamai-restart`)
- Automated monitoring with cron jobs

### `06_docker_operations.sh` - Docker Operations
**Purpose**: Pulls images and starts services with validation

**Key Features**:
- Docker readiness validation
- Docker Compose configuration validation
- Image pulling with retry logic
- Service startup with proper group membership
- Service health monitoring
- Endpoint testing
- Cleanup procedures for failed deployments

## 🚀 Usage

### Basic Usage
```bash
# As root on EC2 instance
./user_data_improved.sh
```

### With Custom Configuration
```bash
# Set environment variables to customize deployment
export DATA_VOLUME_SIZE_GB=200
export FILESYSTEM_TYPE=xfs
export MOUNT_POINT=/mnt/data
export DEBUG=true
export FOAMAI_REPO_URL=https://github.com/yourusername/FoamAI.git

./user_data_improved.sh
```

### Testing Individual Modules
```bash
# Test a specific module
cd user_data_modules
sudo ./01_system_update.sh

# With debug logging
sudo DEBUG=true ./03_ebs_volume_setup.sh
```

## 🔧 Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_VOLUME_SIZE_GB` | `100` | Expected EBS volume size in GB |
| `FILESYSTEM_TYPE` | `ext4` | Filesystem type (`ext4` or `xfs`) |
| `MOUNT_POINT` | `/data` | Mount point for data volume |
| `EBS_WAIT_TIMEOUT` | `300` | Timeout for EBS volume detection |
| `FOAMAI_REPO_URL` | `https://github.com/bbaserdem/FoamAI.git` | Repository URL |
| `FOAMAI_INSTALL_DIR` | `/opt/FoamAI` | Installation directory |
| `GITHUB_ORG` | `bbaserdem` | GitHub organization for images |
| `DEBUG` | `false` | Enable debug logging |

## 📊 Monitoring & Management

### Status Checking
```bash
# Comprehensive status check
sudo foamai-status

# Health check (returns 0 if healthy)
sudo foamai-health

# Service management
sudo foamai-start
sudo foamai-stop
sudo foamai-restart
```

### Log Files
- `/var/log/foamai-startup.log` - Deployment log
- `/var/log/foamai-deployment-summary.log` - Deployment summary
- `/var/log/foamai-deployment-failure.log` - Failure report (if deployment fails)
- `/var/log/foamai-health.log` - Health check log
- `/var/log/foamai-status.log` - Status check log

### Service Status
```bash
# Check systemd services
systemctl status docker
systemctl status foamai

# Check containers
docker ps

# Check logs
journalctl -u foamai
```

## 🛠️ Troubleshooting

### Common Issues

1. **EBS Volume Not Found**
   - Check volume attachment in AWS console
   - Verify instance type and device naming
   - Enable debug logging: `DEBUG=true`

2. **Docker Access Issues**
   - Check group membership: `groups ubuntu`
   - Verify Docker daemon: `systemctl status docker`
   - Check permissions: `ls -la /var/run/docker.sock`

3. **Service Startup Failures**
   - Check logs: `journalctl -u foamai`
   - Validate compose file: `docker-compose config`
   - Check image availability: `docker images`

### Debug Mode
```bash
# Enable debug logging
export DEBUG=true
./user_data_improved.sh
```

### Manual Module Testing
```bash
# Test EBS volume detection
cd user_data_modules
sudo DEBUG=true ./03_ebs_volume_setup.sh

# Test Docker operations
sudo DEBUG=true ./06_docker_operations.sh
```

## 🔐 Security Features

- **Service isolation** with systemd security settings
- **Minimal privileges** for service execution
- **Secure file permissions** for sensitive configurations
- **Read-only system paths** where possible
- **Private temporary directories**

## 🔄 Compatibility

- **Instance Types**: All EC2 instance types (Nitro, Xen, T2, T3, C5, C6, C7, etc.)
- **Device Naming**: Automatic detection of `/dev/nvme*`, `/dev/xvd*`, `/dev/sd*`
- **Filesystems**: `ext4` and `xfs` support
- **Ubuntu Versions**: 20.04, 22.04, and newer

## 📈 Performance Improvements

- **Parallel operations** where possible
- **Caching** of repeated operations
- **Optimized Docker daemon** configuration
- **Efficient log rotation** to prevent disk issues
- **Health checking** to prevent unnecessary restarts

## 🤝 Contributing

When modifying the modules:

1. **Test individual modules** before testing the full deployment
2. **Follow the logging conventions** using the utility functions
3. **Add proper error handling** with meaningful error messages
4. **Update this README** if adding new features or changing behavior
5. **Test on different instance types** to ensure compatibility

## 📄 License

This deployment script is part of the FoamAI project and follows the same licensing terms. 