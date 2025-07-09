#!/usr/bin/env python3
"""
Check Visualization Capabilities
Tests what visualization options are available for the OpenFOAM Desktop Assistant
"""
import sys

def check_paraview():
    """Check ParaView availability"""
    try:
        import paraview.simple
        print("✅ ParaView: Available")
        return True
    except ImportError as e:
        print("❌ ParaView: Not available")
        print(f"   Error: {e}")
        return False

def check_vtk():
    """Check VTK availability"""
    try:
        import vtk
        version = vtk.vtkVersion.GetVTKVersion()
        print(f"✅ VTK: Available (version {version})")
        return True
    except ImportError as e:
        print("❌ VTK: Not available")
        print(f"   Error: {e}")
        return False

def check_vtk_qt():
    """Check VTK-Qt integration"""
    try:
        import vtk
        # Try different import paths
        qt_available = False
        qt_module = None
        
        try:
            from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
            qt_available = True
            qt_module = "vtk.qt"
        except ImportError:
            try:
                from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
                qt_available = True
                qt_module = "vtkmodules.qt"
            except ImportError:
                try:
                    from vtk.qt5.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
                    qt_available = True
                    qt_module = "vtk.qt5"
                except ImportError:
                    pass
        
        if qt_available:
            print(f"✅ VTK-Qt Integration: Available (using {qt_module})")
            return True
        else:
            print("❌ VTK-Qt Integration: Not available")
            print("   VTK is installed but Qt integration is missing")
            return False
            
    except ImportError:
        print("❌ VTK-Qt Integration: VTK not available")
        return False

def check_pyside6():
    """Check PySide6 availability"""
    try:
        import PySide6
        from PySide6.QtWidgets import QApplication
        print("✅ PySide6: Available")
        return True
    except ImportError as e:
        print("❌ PySide6: Not available")
        print(f"   Error: {e}")
        return False

def main():
    """Main check function"""
    print("OpenFOAM Desktop Assistant - Visualization Check")
    print("=" * 60)
    print()
    
    # Check all components
    paraview_ok = check_paraview()
    vtk_ok = check_vtk()
    vtk_qt_ok = check_vtk_qt()
    pyside6_ok = check_pyside6()
    
    print()
    print("=" * 60)
    print("VISUALIZATION CAPABILITIES SUMMARY")
    print("=" * 60)
    
    if vtk_ok and vtk_qt_ok and pyside6_ok:
        print("🎉 BEST: Embedded VTK Rendering Available!")
        print("   Your OpenFOAM visualizations will appear directly")
        print("   inside the desktop application window.")
        print()
        
    elif paraview_ok and pyside6_ok:
        print("⚡ GOOD: ParaView Server Mode Available!")
        print("   Your visualizations will work via ParaView server.")
        print("   Note: Visualizations may appear in separate windows.")
        print()
        
    else:
        print("⚠️  LIMITED: No visualization available")
        print("   You'll need to install additional packages.")
        print()
    
    print("INSTALLATION RECOMMENDATIONS:")
    print("-" * 40)
    
    if not pyside6_ok:
        print("1. Install PySide6 (required for GUI):")
        print("   pip install PySide6")
        print()
    
    if not vtk_ok:
        print("2. Install VTK (recommended for embedded visualization):")
        print("   pip install vtk")
        print()
    elif not vtk_qt_ok:
        print("2. VTK-Qt integration missing:")
        print("   Try: pip install --upgrade vtk")
        print("   Or: pip install vtk[qt]")
        print()
    
    if not paraview_ok:
        print("3. Install ParaView (alternative visualization):")
        print("   Option A: pip install paraview")
        print("   Option B: Download from https://www.paraview.org/download/")
        print()
    
    print("QUICK INSTALL (all packages):")
    print("pip install PySide6 vtk paraview requests python-dotenv numpy Flask Flask-CORS")
    print()
    
    # Test the application
    if pyside6_ok and (vtk_qt_ok or paraview_ok):
        print("✅ Ready to run the application!")
        print("   Use: python main.py")
        print("   Or:  python start_all_servers.py")
    else:
        print("❌ Install missing packages before running the application")
    
    print("=" * 60)

if __name__ == "__main__":
    main() 