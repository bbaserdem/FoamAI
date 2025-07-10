"""Simple script to open an OpenFOAM case in ParaView."""

import subprocess
import sys
from pathlib import Path

# Get case directory from command line or use default
if len(sys.argv) > 1:
    case_dir = sys.argv[1]
else:
    case_dir = "work/20250707_213752_channel_case"

case_path = Path(case_dir)
if not case_path.exists():
    print(f"Case directory not found: {case_dir}")
    sys.exit(1)

# Create .foam file if it doesn't exist
foam_file = case_path / f"{case_path.name}.foam"
if not foam_file.exists():
    foam_file.touch()
    print(f"Created foam file: {foam_file}")

# Check for vortex shedding visualization files
viz_dir = case_path / "visualization"
has_vortex_viz = viz_dir.exists() and (viz_dir / "vorticity_field.png").exists()
has_animation = viz_dir.exists() and (viz_dir / "vortex_shedding_animation.pvsm").exists()

# Get ParaView path from environment or use default
paraview_path = r"C:\Program Files\ParaView 6.0.0"
paraview_exe = Path(paraview_path) / "bin" / "paraview.exe"

if not paraview_exe.exists():
    print(f"ParaView not found at: {paraview_exe}")
    print("Please update the paraview_path variable")
    sys.exit(1)

# Open ParaView with the foam file
print(f"Opening ParaView with case: {foam_file}")
try:
    # Use the foam file directly, not the Python script
    subprocess.Popen([str(paraview_exe), str(foam_file)])
    print("\nParaView opened successfully!")
    print("\nTo visualize the results:")
    print("1. The case should load automatically")
    print("2. Click the 'Apply' button in Properties panel")
    print("3. Select the time step you want to view")
    print("4. Choose a field to color by (e.g., U for velocity, p for pressure)")
    
    if has_vortex_viz:
        print("\n🌪️  VORTEX SHEDDING VISUALIZATION DETECTED!")
        print("Enhanced visualizations are available:")
        print("• Vorticity field - Shows actual vortex structures")
        print("• Q-criterion - Advanced vortex identification")
        print("• Enhanced streamlines - Better capture of wake flow")
        print("• Time-averaged flow - Mean flow patterns")
        
        if has_animation:
            print("\n🎬 ANIMATION AVAILABLE!")
            print("Open the ParaView state file for interactive vortex shedding animation:")
            print(f"   File > Load State > {viz_dir / 'vortex_shedding_animation.pvsm'}")
            print("   Then use the animation controls to see vortex shedding over time")
        
        print("\n📊 VISUALIZATION TIPS FOR VORTEX SHEDDING:")
        print("• Color by 'Vorticity_Magnitude' to see vortex structures")
        print("• Use time animation to see vortex shedding dynamics")
        print("• Apply the 'Plasma' or 'Viridis' color map for better contrast")
        print("• Enable streamlines to visualize flow patterns")
        print("• Use isosurfaces of Q-criterion to identify vortex cores")
        
except Exception as e:
    print(f"Error opening ParaView: {e}")
    
print("\n" + "="*60)
print("FOAMAI VORTEX SHEDDING VISUALIZATION SYSTEM")
print("="*60) 