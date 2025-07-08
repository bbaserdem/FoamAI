# FoamAI Backend API - Validation Guide

Simple validation scripts to test your EC2 deployment.

## Quick Start

### 1. On Your EC2 Instance

```bash
# Make the script executable
chmod +x ec2_validation.sh

# Run the validation
./ec2_validation.sh
```

This will:
- ✅ Test OpenFOAM installation
- ✅ Run the cavity case at `/home/ubuntu/cavity_tutorial`
- ✅ Test ParaView server startup
- ✅ Check all dependencies

### 2. From Your Local Machine

```bash
# Install dependencies
pip install requests

# Run remote validation (replace with your EC2 host)
python3 validate_deployment.py your-ec2-host.amazonaws.com
```

This will:
- ✅ Test API endpoints
- ✅ Test full workflow (submit → poll → approve → complete)
- ✅ Test ParaView server connectivity

## Expected Workflow

1. **Deploy your backend API** on EC2
2. **Run `ec2_validation.sh`** on the EC2 instance
3. **Start your services**:
   ```bash
   # Start API server
   cd /path/to/backend_api
   python3 main.py &
   
   # Start Celery worker
   celery -A celery_worker worker --loglevel=info &
   
   # Start pvserver
   nohup pvserver --server-port=11111 --disable-xdisplay-test > pvserver.log 2>&1 &
   ```
4. **Run `validate_deployment.py`** from your local machine
5. **Connect ParaView** locally to your EC2 instance

## ParaView Connection

From your local ParaView:
1. **File → Connect**
2. **Add Server**
3. **Host**: `your-ec2-host.amazonaws.com`
4. **Port**: `11111`
5. **Connect**

Then open the cavity case:
1. **File → Open**
2. Navigate to `/home/ubuntu/cavity_tutorial/cavity.foam`
3. **Apply** to load the data

## Troubleshooting

### Common Issues

**API not responding:**
```bash
# Check if FastAPI is running
ps aux | grep python3
netstat -ln | grep 8000
```

**ParaView connection fails:**
```bash
# Check if pvserver is running
netstat -ln | grep 11111
tail -f pvserver.log
```

**OpenFOAM case fails:**
```bash
# Check logs
cd /home/ubuntu/cavity_tutorial
cat blockMesh.log
cat foamRun.log
```

### Security Groups

Make sure your EC2 security group allows:
- **Port 8000** (API server)
- **Port 11111** (ParaView server)
- **Port 6379** (Redis - internal only)

## What These Scripts Don't Test

These are **basic smoke tests**. They don't test:
- Load handling
- Error recovery
- Complex scenarios
- Performance under stress

For production, you'll want more comprehensive testing.

## File Structure

```
backend_api/
├── validate_deployment.py  # Run from local machine
├── ec2_validation.sh      # Run on EC2 instance
├── VALIDATION_README.md   # This file
├── main.py               # Your FastAPI app
├── celery_worker.py      # Your Celery worker
└── requirements.txt      # Python dependencies
```

## Success Criteria

✅ **EC2 validation passes** - OpenFOAM and ParaView work  
✅ **Remote validation passes** - API endpoints respond correctly  
✅ **ParaView connects** - You can visualize the cavity case  
✅ **End-to-end workflow** - Submit scenario → approve mesh → view results

When all these work, your deployment is ready for desktop app integration! 🚀 