# Development Directory

This directory contains development-specific files and configurations.

## Contents

- `docker-compose.local.yml` - Local development Docker Compose configuration

## Local Development

### Using Local Docker Compose

For local development with custom configurations:

```bash
# Start services locally
docker-compose -f dev/docker-compose.local.yml up -d

# Stop local services  
docker-compose -f dev/docker-compose.local.yml down
```

### Differences from Production

The local compose file typically includes:
- Volume mounts for live code editing
- Debug configurations
- Different port mappings
- Development environment variables

## Adding Development Tools

Place development-specific scripts, configurations, and utilities here:
- Local database seeds
- Development scripts
- Testing configurations
- IDE configurations (if not in root)

## Note

Files in this directory should **not** be used in production deployments. 