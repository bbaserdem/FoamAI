# GitHub Container Registry Deployment Guide

This guide explains how to configure your GitHub Container Registry (ghcr.io) images for deployment without authentication issues.

## Option 1: Make Images Public (Recommended for Open Source)

This is the simplest approach and works perfectly for open-source projects.

### Step-by-Step Instructions

1. **Navigate to Your Packages**
   - Go to https://github.com/bbaserdem?tab=packages
   - You'll see your container images listed

2. **Make Each Package Public**
   
   For each of these packages:
   - `foamai/api`
   - `foamai/openfoam`
   - `foamai/pvserver`
   
   Do the following:
   
   a. Click on the package name
   b. Click "Package settings" (gear icon) on the right
   c. Scroll down to "Danger Zone"
   d. Click "Change visibility"
   e. Select "Public" and confirm

3. **Verify Public Access**
   
   Run the test script we created:
   ```bash
   ./test-public-access.sh
   ```
   
   You should see "✓ PUBLIC ACCESS CONFIRMED" for each image.

### Benefits of Public Images
- No authentication needed on EC2 instances
- Simpler deployment configuration
- No token management required
- Works immediately after making images public

## Option 2: Use Authentication Token (For Private Images)

If you prefer to keep your images private, you'll need to configure authentication.

### Create a Personal Access Token (PAT)

1. **Generate Token**
   - Go to https://github.com/settings/tokens/new
   - Give it a descriptive name like "FoamAI Deployment Read Token"
   - Set expiration (recommend 90 days for production)
   - Select only this scope:
     - `read:packages` - Download packages from GitHub Package Registry

2. **Save the Token**
   - Copy the generated token immediately (you won't see it again)
   - Store it securely

### Configure EC2 Instance for Authentication

Update your deployment scripts to include authentication:

1. **Update the Application Setup Script**
   ```bash
   # In infra/user_data_modules/04_application_setup.sh
   # Add to the create_environment_config() function:
   
   # GitHub Registry Authentication
   GITHUB_TOKEN=${GITHUB_TOKEN:-}
   GITHUB_USERNAME=${GITHUB_USERNAME:-bbaserdem}
   ```

2. **Update the Docker Operations Script**
   ```bash
   # In infra/user_data_modules/06_docker_operations.sh
   # Add before pull_docker_images() function:
   
   # Authenticate with GitHub Container Registry
   authenticate_github_registry() {
       log_info "Authenticating with GitHub Container Registry..."
       
       if [[ -n "${GITHUB_TOKEN}" ]]; then
           echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${GITHUB_USERNAME}" --password-stdin
           if [[ $? -eq 0 ]]; then
               log_info "Successfully authenticated with GitHub Container Registry"
               return 0
           else
               log_error "Failed to authenticate with GitHub Container Registry"
               return 1
           fi
       else
           log_warn "No GitHub token provided, pulling without authentication"
           return 0
       fi
   }
   ```

3. **Pass Token During Deployment**
   
   Update your Terraform variables:
   ```hcl
   # In terraform.tfvars
   github_token = "ghp_your_token_here"
   github_username = "bbaserdem"
   ```
   
   And in your user_data template:
   ```bash
   export GITHUB_TOKEN="${github_token}"
   export GITHUB_USERNAME="${github_username}"
   ```

### Security Considerations for Tokens

- Use read-only tokens (`read:packages` scope only)
- Rotate tokens regularly (every 90 days)
- Never commit tokens to version control
- Use AWS Secrets Manager for production deployments

## Option 3: Use AWS ECR Instead

If you want to avoid GitHub authentication entirely, consider migrating to AWS ECR:

1. **Create ECR Repositories**
   ```bash
   aws ecr create-repository --repository-name foamai/api --region us-east-1
   aws ecr create-repository --repository-name foamai/openfoam --region us-east-1
   aws ecr create-repository --repository-name foamai/pvserver --region us-east-1
   ```

2. **Tag and Push Images**
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL
   
   # Tag and push each image
   docker tag ghcr.io/bbaserdem/foamai/api:latest $ECR_URL/foamai/api:latest
   docker push $ECR_URL/foamai/api:latest
   ```

3. **Update docker-compose.yml**
   Replace ghcr.io URLs with ECR URLs

## Troubleshooting

### Common Issues

1. **"unauthorized" error when pulling**
   - Images are still private
   - Token has expired
   - Token doesn't have `read:packages` permission

2. **"manifest unknown" error**
   - Images haven't been pushed yet
   - Wrong image name or tag

3. **Rate limiting issues**
   - GitHub has rate limits for unauthenticated pulls
   - Solution: Use authentication or make images public

### Testing Deployment Locally

Before deploying to EC2, test locally:

```bash
# Test without authentication (for public images)
docker logout ghcr.io
docker pull ghcr.io/bbaserdem/foamai/api:latest

# Test with authentication (for private images)
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin
docker pull ghcr.io/bbaserdem/foamai/api:latest
```

## Recommendation

For open-source projects like FoamAI, **making images public (Option 1) is the recommended approach** because:

1. Simplifies deployment significantly
2. No token management overhead
3. Allows community contributions and testing
4. Aligns with open-source principles
5. No authentication failures during deployment

The images contain no sensitive data - they're just packaged versions of your open-source code. 