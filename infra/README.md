# FoamAI Infrastructure

This directory contains the Terraform configuration and deployment scripts for FoamAI's AWS infrastructure.

## Quick Start

1. **Initialize Terraform**:
   ```bash
   terraform init
   ```

2. **Configure Variables**:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your configuration
   ```

3. **Deploy Infrastructure**:
   ```bash
   terraform plan
   terraform apply
   ```

4. **Deploy Fresh Staging Instance**:
   ```bash
   ./deploy-fresh-instance.sh
   ```

## Key Features

### 🔧 Robust EBS Volume Mounting
- **Configurable hybrid approach** with multiple discovery strategies
- **UUID-based persistent mounting** for reliability
- **Comprehensive fallback mechanisms** for deployment continuity
- **Flexible configuration** through Terraform variables

See [EBS_VOLUME_MOUNTING.md](./EBS_VOLUME_MOUNTING.md) for detailed documentation.

### 🚀 Automated Deployment
- **Template-based user data scripts** for configuration flexibility
- **Multi-environment support** (staging, production)
- **Comprehensive logging and monitoring**
- **Docker-based service orchestration**

### 🔒 Security & Compliance
- **Encrypted EBS volumes** by default
- **VPC isolation** with security groups
- **IAM policy templates** for proper access control
- **SSH key management** through Terraform

## Configuration

### Core Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `instance_type` | `c7i.2xlarge` | EC2 instance type |
| `data_volume_size` | `100` | EBS data volume size (GB) |
| `data_volume_filesystem` | `ext4` | Filesystem type |
| `deployment_profile` | `standard` | Configuration profile |
| `ebs_wait_timeout` | `300` | Volume detection timeout (seconds) |

### Deployment Profiles

- **minimal**: Small volumes, basic setup
- **standard**: Production-ready configuration
- **performance**: Optimized for heavy workloads
- **development**: Development-specific settings

## File Structure

```
infra/
├── main.tf                    # Main Terraform configuration
├── variables.tf               # Variable definitions
├── outputs.tf                 # Output definitions
├── user_data.sh.tpl          # Templated startup script
├── deploy-fresh-instance.sh   # Staging deployment script
├── terraform.tfvars.example   # Example configuration
├── terraform.tfvars.staging   # Staging configuration
├── iam-policies/             # IAM policy templates
├── keys/                     # SSH key storage
└── EBS_VOLUME_MOUNTING.md    # Detailed EBS documentation
```

## Troubleshooting

### Common Issues

1. **Volume mounting failures**: Check [EBS_VOLUME_MOUNTING.md](./EBS_VOLUME_MOUNTING.md)
2. **SSH access issues**: Verify IAM policies in `iam-policies/`
3. **Service startup problems**: Check deployment logs: `sudo tail -f /var/log/foamai-startup.log`

### Debugging Commands

```bash
# Check deployment status
sudo foamai-status

# View deployment logs
sudo tail -f /var/log/foamai-startup.log

# Check volume status
lsblk
df -h /data
```

## Monitoring

The deployment includes:
- **Enhanced status script**: `/usr/local/bin/foamai-status`
- **Comprehensive logging**: `/var/log/foamai-startup.log`
- **Volume discovery diagnostics**: Built into startup script
- **Docker container health checks**: Via Docker Compose

## Security Considerations

- All EBS volumes are encrypted by default
- SSH access requires proper key configuration
- IAM policies follow principle of least privilege
- Security groups restrict access to necessary ports only

For detailed security configuration, see the IAM policies in `iam-policies/` directory.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review deployment logs for detailed error information
3. Refer to [EBS_VOLUME_MOUNTING.md](./EBS_VOLUME_MOUNTING.md) for volume-related issues 