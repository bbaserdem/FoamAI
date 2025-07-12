# Terraform Configuration for FoamAI CFD Assistant MVP
# Provisions AWS EC2 instance with Docker and required networking

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region
}

# Data source to get the latest Ubuntu 22.04 LTS AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Create VPC
resource "aws_vpc" "foamai_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "foamai-vpc"
    Project     = "FoamAI"
    Environment = "mvp"
  }
}

# Create Internet Gateway
resource "aws_internet_gateway" "foamai_igw" {
  vpc_id = aws_vpc.foamai_vpc.id

  tags = {
    Name        = "foamai-igw"
    Project     = "FoamAI"
    Environment = "mvp"
  }
}

# Create public subnet
resource "aws_subnet" "foamai_public_subnet" {
  vpc_id                  = aws_vpc.foamai_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name        = "foamai-public-subnet"
    Project     = "FoamAI"
    Environment = "mvp"
  }
}

# Create route table
resource "aws_route_table" "foamai_public_rt" {
  vpc_id = aws_vpc.foamai_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.foamai_igw.id
  }

  tags = {
    Name        = "foamai-public-rt"
    Project     = "FoamAI"
    Environment = "mvp"
  }
}

# Associate route table with subnet
resource "aws_route_table_association" "foamai_public_rta" {
  subnet_id      = aws_subnet.foamai_public_subnet.id
  route_table_id = aws_route_table.foamai_public_rt.id
}

# Create security group
resource "aws_security_group" "foamai_sg" {
  name        = "foamai-security-group"
  description = "Security group for FoamAI CFD Assistant"
  vpc_id      = aws_vpc.foamai_vpc.id

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP access
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS access
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # ParaView server port
  ingress {
    description = "ParaView Server"
    from_port   = 11111
    to_port     = 11111
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # FastAPI port
  ingress {
    description = "FastAPI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "foamai-sg"
    Project     = "FoamAI"
    Environment = "mvp"
  }
}

# Create EC2 key pair (optional - can be created manually)
resource "aws_key_pair" "foamai_key" {
  key_name   = var.key_name
  public_key = var.public_key_content

  tags = {
    Name        = "foamai-key"
    Project     = "FoamAI"
    Environment = "mvp"
  }
}

# Create EC2 instance
resource "aws_instance" "foamai_instance" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  key_name      = aws_key_pair.foamai_key.key_name
  
  vpc_security_group_ids = [aws_security_group.foamai_sg.id]
  subnet_id              = aws_subnet.foamai_public_subnet.id
  
  # User data script - minimal bootstrap that downloads full deployment script
  user_data = base64encode(templatefile("${path.module}/user_data.sh.tpl", {
    data_volume_size_gb = var.data_volume_size
    filesystem_type     = var.data_volume_filesystem
    mount_point         = var.data_volume_mount_point
    wait_timeout        = var.ebs_wait_timeout
    deployment_profile  = "mvp"
  }))

  # Storage configuration
  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size
    encrypted   = true
    
    tags = {
      Name        = "foamai-root-volume"
      Project     = "FoamAI"
      Environment = "mvp"
    }
  }

  # Additional EBS volume for simulation data
  ebs_block_device {
    device_name = "/dev/sdf"
    volume_type = "gp3"
    volume_size = var.data_volume_size
    encrypted   = true
    
    tags = {
      Name        = "foamai-data-volume"
      Project     = "FoamAI"
      Environment = "mvp"
    }
  }

  tags = {
    Name        = "foamai-instance"
    Project     = "FoamAI"
    Environment = "mvp"
    Purpose     = "CFD Assistant MVP"
  }
}

# Create and associate Elastic IP
resource "aws_eip" "foamai_eip" {
  instance = aws_instance.foamai_instance.id
  domain   = "vpc"

  # Ensure the instance is fully created before associating the EIP
  depends_on = [aws_internet_gateway.foamai_igw]

  tags = {
    Name        = "foamai-eip"
    Project     = "FoamAI"
    Environment = "mvp"
  }
}

# ========================================================================
# ECR (Elastic Container Registry) - Alternative to Docker Hub
# ========================================================================

# ECR Repository for FastAPI Backend
resource "aws_ecr_repository" "foamai_api" {
  name                 = "foamai/api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "foamai-api-ecr"
    Project     = "FoamAI"
    Environment = "mvp"
    Service     = "api"
  }
}

# ECR Repository for OpenFOAM Solver
resource "aws_ecr_repository" "foamai_openfoam" {
  name                 = "foamai/openfoam"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "foamai-openfoam-ecr"
    Project     = "FoamAI"
    Environment = "mvp"
    Service     = "openfoam"
  }
}

# ECR Repository for ParaView Server
resource "aws_ecr_repository" "foamai_pvserver" {
  name                 = "foamai/pvserver"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "foamai-pvserver-ecr"
    Project     = "FoamAI"
    Environment = "mvp"
    Service     = "pvserver"
  }
}

# ECR Lifecycle Policy for API Repository
resource "aws_ecr_lifecycle_policy" "foamai_api_policy" {
  repository = aws_ecr_repository.foamai_api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 5 untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECR Lifecycle Policy for OpenFOAM Repository
resource "aws_ecr_lifecycle_policy" "foamai_openfoam_policy" {
  repository = aws_ecr_repository.foamai_openfoam.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 3 untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECR Lifecycle Policy for PVServer Repository
resource "aws_ecr_lifecycle_policy" "foamai_pvserver_policy" {
  repository = aws_ecr_repository.foamai_pvserver.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 3 untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
} 