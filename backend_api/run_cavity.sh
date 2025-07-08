#!/bin/bash
# Script to run the cavity tutorial

# Navigate to the run directory
cd /home/ubuntu/cavity_tutorial

# Clean the case (optional, but good practice)
foamCleanTutorials

# Run the case
blockMesh
foamRun

# Make sure the foam file is there
touch cavity.foam
