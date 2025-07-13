# Output definitions for FoamAI Terraform configuration

output "public_ip" {
  description = "The public IP address of the FoamAI EC2 instance"
  value       = aws_eip.foamai_eip.public_ip
}

output "public_dns" {
  description = "The public DNS name of the FoamAI EC2 instance"
  value       = aws_instance.foamai_instance.public_dns
}

output "instance_id" {
  description = "The EC2 instance ID"
  value       = aws_instance.foamai_instance.id
}

output "instance_type" {
  description = "The EC2 instance type"
  value       = aws_instance.foamai_instance.instance_type
}

output "security_group_id" {
  description = "The ID of the security group"
  value       = aws_security_group.foamai_sg.id
}

output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.foamai_vpc.id
}

output "subnet_id" {
  description = "The ID of the public subnet"
  value       = aws_subnet.foamai_public_subnet.id
}

output "key_name" {
  description = "The name of the SSH key pair"
  value       = aws_key_pair.foamai_key.key_name
}

# Service endpoints
output "api_endpoint" {
  description = "FastAPI service endpoint URL"
  value       = "http://${aws_eip.foamai_eip.public_ip}:8000"
}

output "paraview_endpoint" {
  description = "ParaView server endpoint for remote visualization"
  value       = "${aws_eip.foamai_eip.public_ip}:11111"
}

output "ssh_connection" {
  description = "SSH connection command"
  value       = "ssh -i infra/keys/${var.key_name} ubuntu@${aws_eip.foamai_eip.public_ip}"
}

# Resource ARNs for reference
output "instance_arn" {
  description = "The ARN of the EC2 instance"
  value       = aws_instance.foamai_instance.arn
}

output "elastic_ip_arn" {
  description = "The ARN of the Elastic IP"
  value       = aws_eip.foamai_eip.arn
}

# Storage information
output "root_volume_id" {
  description = "The ID of the root EBS volume"
  value       = aws_instance.foamai_instance.root_block_device[0].volume_id
}

output "data_volume_device" {
  description = "The device name of the data volume"
  value       = "/dev/sdf"
}

# Connection test commands
output "connection_tests" {
  description = "Commands to test service connectivity"
  value = {
    api_health_check    = "curl -f http://${aws_eip.foamai_eip.public_ip}:8000/ping"
    paraview_port_check = "nc -zv ${aws_eip.foamai_eip.public_ip} 11111"
    ssh_test            = "ssh -i infra/keys/${var.key_name} -o ConnectTimeout=10 ubuntu@${aws_eip.foamai_eip.public_ip} 'echo Connected successfully'"
    docker_status       = "ssh -i infra/keys/${var.key_name} ubuntu@${aws_eip.foamai_eip.public_ip} 'sudo docker ps'"
  }
}

# Important URLs and access information
output "access_information" {
  description = "Important access information and URLs"
  value = {
    public_ip         = aws_eip.foamai_eip.public_ip
    api_url           = "http://${aws_eip.foamai_eip.public_ip}:8000"
    api_docs_url      = "http://${aws_eip.foamai_eip.public_ip}:8000/docs"
    paraview_server   = "${aws_eip.foamai_eip.public_ip}:11111"
    ssh_command       = "ssh -i infra/keys/${var.key_name} ubuntu@${aws_eip.foamai_eip.public_ip}"
    region            = var.aws_region
    availability_zone = aws_subnet.foamai_public_subnet.availability_zone
  }
} 