# IAM Setup Guide - FoamAI Console Access

This guide will help you resolve the permission issues you're experiencing with your IAM user `baserdemb-foamai`.

## 🔍 **Issues Identified**

Your IAM user currently lacks permissions for:
- ✗ EC2 console access across regions (console home shows 0 deployments)
- ✗ Cost and Usage reporting (`ce:GetCostAndUsage`, `ce:GetCostForecast`)
- ✗ Cost Optimization Hub (`cost-optimization-hub:ListEnrollmentStatuses`)
- ✗ Security Hub access (`securityhub:DescribeHub`)

## 🎯 **Solution: Apply IAM Policies**

I've created two policy options for you:

### **Option 1: Minimal Console Access (Recommended for immediate fix)**
File: `minimal-console-access-policy.json`
- ✅ Fixes your immediate console access issues
- ✅ Provides read-only access to EC2, Cost Explorer, and Security Hub
- ✅ Least privilege approach

### **Option 2: Full FoamAI Deployment Access**
File: `foamai-console-access-policy.json`
- ✅ Includes all minimal access permissions
- ✅ Adds Terraform deployment permissions for EC2, VPC, ECR
- ✅ Comprehensive access for managing FoamAI infrastructure

## 📋 **Step-by-Step Instructions**

### **Step 1: Access AWS IAM Console**

1. **Login to AWS Console** using your root account or an admin user (not the `baserdemb-foamai` user)
2. **Navigate to IAM**: Go to Services → Security, Identity & Compliance → IAM
3. **Go to Users**: Click "Users" in the left sidebar

### **Step 2: Find Your User**

1. **Search for user**: Look for `baserdemb-foamai` in the users list
2. **Click on the username** to open the user details page

### **Step 3: Create and Attach Policy**

#### **Option A: Create Custom Policy (Recommended)**

1. **Go to Policies**: Click "Policies" in the left sidebar
2. **Create Policy**: Click "Create policy" button
3. **Use JSON Tab**: Click the "JSON" tab
4. **Copy Policy Content**: 
   - For minimal access: Copy content from `minimal-console-access-policy.json`
   - For full access: Copy content from `foamai-console-access-policy.json`
5. **Paste JSON**: Replace the default JSON with your copied content
6. **Review Policy**: Click "Next: Tags" → "Next: Review"
7. **Name the Policy**: 
   - For minimal: `FoamAI-ConsoleAccess-Minimal`
   - For full: `FoamAI-ConsoleAccess-Full`
8. **Add Description**: "Console access permissions for FoamAI user"
9. **Create Policy**: Click "Create policy"

#### **Option B: Attach Policy to User**

1. **Go back to Users** → Click on `baserdemb-foamai`
2. **Permissions Tab**: Click on the "Permissions" tab
3. **Add Permissions**: Click "Add permissions" button
4. **Attach Policies Directly**: Select "Attach policies directly"
5. **Search for Policy**: Search for the policy you just created
6. **Select Policy**: Check the box next to your policy
7. **Add Permissions**: Click "Add permissions"

### **Step 4: Verify Access**

1. **Wait 1-2 minutes** for permissions to propagate
2. **Login as baserdemb-foamai** (or refresh if already logged in)
3. **Test Access**:
   - ✅ **EC2 Console**: Should now show your existing instance
   - ✅ **Cost and Usage**: Should load without permission errors
   - ✅ **Security Hub**: Should access without errors

## 🔧 **AWS CLI v2 Method (Alternative)**

If you have admin access via AWS CLI v2, you can apply policies programmatically:

### **First, Fix Shell Configuration Issues**

Your AWS CLI seems to have shell conflicts. Try these fixes:

```bash
# Option 1: Use AWS CLI v2 directly with explicit paths
/nix/store/l7z95l195520a6v68m9xzhfybfcq6y2a-awscli2-2.27.31/bin/aws --version

# Option 2: Create a clean environment
unset AWS_PAGER
export AWS_CLI_AUTO_PROMPT=off
export AWS_DEFAULT_OUTPUT=json

# Option 3: Test basic connectivity
/nix/store/l7z95l195520a6v68m9xzhfybfcq6y2a-awscli2-2.27.31/bin/aws sts get-caller-identity --no-cli-pager --output json
```

### **AWS CLI v2 Policy Management Commands**

```bash
# Step 1: Create the minimal policy (AWS CLI v2 syntax)
aws iam create-policy \
    --policy-name FoamAI-ConsoleAccess-Minimal \
    --policy-document file://infra/iam-policies/minimal-console-access-policy.json \
    --description "Console access permissions for FoamAI user" \
    --no-cli-pager \
    --output json

# Step 2: Get your account ID 
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --no-cli-pager)
echo "Account ID: $ACCOUNT_ID"

# Step 3: Set the policy ARN
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/FoamAI-ConsoleAccess-Minimal"
echo "Policy ARN: $POLICY_ARN"

# Step 4: Attach policy to user
aws iam attach-user-policy \
    --user-name baserdemb-foamai \
    --policy-arn "$POLICY_ARN" \
    --no-cli-pager

# Step 5: Verify policy attachment
aws iam list-attached-user-policies \
    --user-name baserdemb-foamai \
    --no-cli-pager \
    --output table
```

### **Troubleshooting AWS CLI v2 Shell Issues**

If you're still getting the `head: cannot open '|'` errors:

```bash
# Check for problematic aliases or functions
type aws
which aws
alias | grep aws

# Check shell configuration
echo $SHELL
echo $AWS_PAGER
echo $PAGER

# Use explicit AWS CLI v2 path
AWS_CLI_PATH="/nix/store/l7z95l195520a6v68m9xzhfybfcq6y2a-awscli2-2.27.31/bin/aws"

# Test with explicit path and no pager
$AWS_CLI_PATH sts get-caller-identity --no-cli-pager --output json

# Test EC2 access with explicit path
$AWS_CLI_PATH ec2 describe-instances --region us-east-1 --no-cli-pager --output table
```

### **AWS CLI v2 Configuration Check**

```bash
# Check current configuration
aws configure list --no-cli-pager

# Check all profiles (if any)
aws configure list-profiles --no-cli-pager

# Verify credentials
aws sts get-caller-identity --no-cli-pager --output json

# Test specific region
aws ec2 describe-regions --no-cli-pager --output table
```

## 🚨 **Security Notes**

- **Use Minimal Policy First**: Start with `minimal-console-access-policy.json` to test
- **Upgrade if Needed**: Add the full policy only if you need deployment capabilities
- **Regular Reviews**: Review and audit permissions periodically
- **Least Privilege**: Only grant permissions actually needed

## 🔍 **Troubleshooting**

### **AWS CLI v2 Not Working in Shell?**
1. **Shell Conflicts**: Your Nix shell might have conflicting configurations
2. **Use Direct Path**: Use the full path to AWS CLI v2 binary
3. **Disable Pager**: Always use `--no-cli-pager` flag
4. **Set Output Format**: Use `--output json` or `--output table` explicitly

### **Still Can't See EC2 Instances?**
1. **Check Region**: Ensure you're looking in `us-east-1` region
2. **Instance State**: Your instance might be stopped or terminated
3. **VPC Issues**: Instance might be in a different VPC

### **Cost Explorer Still Not Working?**
1. **Account Settings**: Cost Explorer might need to be enabled in billing settings
2. **Billing Permissions**: You might need additional billing permissions
3. **Regional Service**: Try accessing from `us-east-1` region

### **Security Hub Access Issues?**
1. **Service Enablement**: Security Hub might not be enabled in your account
2. **Regional Service**: Ensure you're in the correct region
3. **Service Setup**: Security Hub requires initial setup

## 📞 **Support**

If you continue experiencing issues:
1. **Document the exact error messages** you're seeing
2. **Check the IAM policy simulator** to test permissions
3. **Review AWS CloudTrail logs** for denied API calls
4. **Contact AWS Support** if service-specific issues persist

## ✅ **Expected Results After Setup**

Once properly configured, you should see:
- ✅ **EC2 Console**: Your running FoamAI instance at IP `35.167.193.72`
- ✅ **Cost Dashboard**: Current month's usage and costs
- ✅ **Security Hub**: Security findings and compliance status
- ✅ **Full Regional Access**: All regions accessible without errors

---

**Next Step**: After fixing permissions, you can proceed with the fresh deployment testing using the staging environment setup! 