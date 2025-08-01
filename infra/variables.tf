# Variable definitions for FoamAI Terraform configuration

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type for the FoamAI server"
  type        = string
  default     = "c7i.2xlarge"

  validation {
    condition = contains([
      "c7i.large", "c7i.xlarge", "c7i.2xlarge", "c7i.4xlarge",
      "c6i.large", "c6i.xlarge", "c6i.2xlarge", "c6i.4xlarge",
      "c5.large", "c5.xlarge", "c5.2xlarge", "c5.4xlarge"
    ], var.instance_type)
    error_message = "Instance type must be a compute-optimized instance suitable for CFD workloads."
  }
}

variable "key_name" {
  description = "Name for the AWS key pair (will be created)"
  type        = string
  default     = "foamai-key"
}

variable "public_key_content" {
  description = "Content of the SSH public key for EC2 access"
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^ssh-(rsa|ed25519|ecdsa)", var.public_key_content))
    error_message = "The public_key_content must be a valid SSH public key starting with ssh-rsa, ssh-ed25519, or ssh-ecdsa."
  }
}

variable "root_volume_size" {
  description = "Size of the root EBS volume in GB"
  type        = number
  default     = 50

  validation {
    condition     = var.root_volume_size >= 20 && var.root_volume_size <= 500
    error_message = "Root volume size must be between 20 and 500 GB."
  }
}

variable "data_volume_size" {
  description = "Size of the additional data EBS volume in GB for simulation files"
  type        = number
  default     = 100

  validation {
    condition     = var.data_volume_size >= 50 && var.data_volume_size <= 1000
    error_message = "Data volume size must be between 50 and 1000 GB."
  }
}

variable "project_name" {
  description = "Name of the project for resource tagging"
  type        = string
  default     = "FoamAI"
}

variable "environment" {
  description = "Environment name for resource tagging"
  type        = string
  default     = "mvp"

  validation {
    condition     = contains(["dev", "staging", "prod", "mvp"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod, mvp."
  }
}

variable "allowed_ssh_cidrs" {
  description = "List of CIDR blocks allowed to SSH to the instance"
  type        = list(string)
  default     = ["0.0.0.0/0"] # WARNING: Open to all - restrict in production
}

variable "docker_hub_username" {
  description = "Docker Hub username for pulling images (optional)"
  type        = string
  default     = "foamai"
}

variable "github_repo_url" {
  description = "GitHub repository URL for the FoamAI project"
  type        = string
  default     = "https://github.com/yourusername/FoamAI.git"
}

variable "enable_detailed_monitoring" {
  description = "Enable detailed CloudWatch monitoring for the EC2 instance"
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Number of days to retain EBS volume snapshots"
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 365
    error_message = "Backup retention must be between 1 and 365 days."
  }
}

# ========================================================================
# EBS Volume Configuration Variables
# ========================================================================

variable "data_volume_filesystem" {
  description = "Filesystem type for the data volume"
  type        = string
  default     = "ext4"

  validation {
    condition     = contains(["ext4", "xfs"], var.data_volume_filesystem)
    error_message = "Filesystem must be ext4 or xfs."
  }
}

variable "data_volume_mount_point" {
  description = "Mount point for the data volume"
  type        = string
  default     = "/data"

  validation {
    condition     = can(regex("^/[a-zA-Z0-9_/-]+$", var.data_volume_mount_point))
    error_message = "Mount point must be a valid absolute path."
  }
}

variable "data_volume_mount_options" {
  description = "Mount options for the data volume"
  type        = string
  default     = "defaults,nofail"
}

variable "ebs_wait_timeout" {
  description = "Timeout in seconds to wait for EBS volume attachment"
  type        = number
  default     = 300

  validation {
    condition     = var.ebs_wait_timeout >= 60 && var.ebs_wait_timeout <= 1800
    error_message = "EBS wait timeout must be between 60 and 1800 seconds (1-30 minutes)."
  }
}

variable "deployment_profile" {
  description = "Deployment configuration profile"
  type        = string
  default     = "standard"

  validation {
    condition     = contains(["minimal", "standard", "performance", "development"], var.deployment_profile)
    error_message = "Deployment profile must be one of: minimal, standard, performance, development."
  }
}

variable "github_org" {
  description = "GitHub organization/owner for container images"
  type        = string
  default     = "bbaserdem"

  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$", var.github_org))
    error_message = "GitHub organization must be a valid GitHub username or organization name."
  }
} 