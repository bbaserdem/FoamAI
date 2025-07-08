"""Command-line interface for FoamAI."""

import click
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from pathlib import Path

console = Console()

@click.group()
@click.version_option()
def cli():
    """FoamAI: AI-powered CFD application using OpenFOAM and ParaView."""
    pass

@cli.command()
@click.argument('prompt', type=str)
@click.option('--output-format', default='images', help='Output format (images, paraview, data)')
@click.option('--no-export-images', is_flag=True, help='Disable visualization image export')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--max-retries', default=3, help='Maximum retry attempts')
def solve(prompt: str, output_format: str, no_export_images: bool, verbose: bool, max_retries: int):
    """Solve a CFD problem from natural language description."""
    
    # Import here to avoid circular imports and startup time
    try:
        import sys
        sys.path.append('src')
        from agents import create_cfd_workflow, create_initial_state
    except ImportError as e:
        console.print(f"[red]Error: Could not import agent modules: {e}[/red]")
        return
    
    # Display initial problem setup
    export_images = not no_export_images  # Convert negative flag to positive
    console.print(
        Panel(
            f"[bold blue]FoamAI CFD Solver[/bold blue]\n\n"
            f"[green]Problem:[/green] {prompt}\n"
            f"[green]Output Format:[/green] {output_format}\n"
            f"[green]Export Images:[/green] {export_images}\n"
            f"[green]Verbose:[/green] {verbose}\n"
            f"[green]Max Retries:[/green] {max_retries}",
            title="CFD Problem Setup",
            border_style="blue"
        )
    )
    
    try:
        # Create initial state
        initial_state = create_initial_state(
            user_prompt=prompt,
            verbose=verbose,
            export_images=export_images,
            output_format=output_format,
            max_retries=max_retries
        )
        
        # Create workflow
        workflow = create_cfd_workflow()
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 50  # Prevent infinite loops
        }
        
        # Execute workflow with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            task = progress.add_task("Initializing CFD workflow...", total=None)
            
            # Run the workflow
            if verbose:
                console.print("[dim]Starting LangGraph workflow execution...[/dim]")
            
            final_state = workflow.invoke(initial_state, config=config)
            
            progress.update(task, description="Workflow completed")
        
        # Display results
        display_results(final_state, verbose)
        
    except Exception as e:
        console.print(f"[red]Error during execution: {str(e)}[/red]")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")


def display_results(final_state, verbose: bool):
    """Display the results of the CFD workflow."""
    
    # Check for errors
    if final_state["errors"]:
        console.print("\n[red]❌ Errors occurred during execution:[/red]")
        for error in final_state["errors"]:
            console.print(f"[red]  • {error}[/red]")
    
    # Display warnings
    if final_state.get("warnings", []):
        console.print("\n[yellow]⚠️  Warnings:[/yellow]")
        for warning in final_state["warnings"]:
            console.print(f"[yellow]  • {warning}[/yellow]")
    
    # Display workflow status
    current_step = final_state.get("current_step", "unknown")
    if current_step == "complete":
        console.print("\n[green]✅ CFD workflow completed successfully![/green]")
    elif current_step == "error":
        console.print("\n[red]❌ CFD workflow failed[/red]")
        return
    else:
        console.print(f"\n[yellow]⚠️  Workflow stopped at step: {current_step}[/yellow]")
    
    # Display summary table
    create_summary_table(final_state, verbose)
    
    # Display file locations
    display_output_locations(final_state)


def create_summary_table(final_state, verbose: bool):
    """Create a summary table of the results."""
    table = Table(title="CFD Analysis Summary")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")
    
    # Geometry information
    geometry_info = final_state.get("geometry_info", {})
    if geometry_info:
        table.add_row("Geometry Type", str(geometry_info.get("type", "N/A")))
        dimensions = geometry_info.get("dimensions", {})
        if dimensions:
            for key, value in dimensions.items():
                table.add_row(f"  {key.title()}", f"{value:.3f} m")
    
    # Flow parameters
    parsed_params = final_state.get("parsed_parameters", {})
    if parsed_params:
        table.add_row("Flow Type", str(parsed_params.get("flow_type", "N/A")))
        table.add_row("Analysis Type", str(parsed_params.get("analysis_type", "N/A")))
        
        if parsed_params.get("velocity"):
            table.add_row("Velocity", f"{parsed_params['velocity']:.2f} m/s")
        if parsed_params.get("reynolds_number"):
            table.add_row("Reynolds Number", f"{parsed_params['reynolds_number']:.0f}")
    
    # Mesh information
    mesh_config = final_state.get("mesh_config", {})
    if mesh_config:
        table.add_row("Total Cells", f"{mesh_config.get('total_cells', 0):,}")
    
    mesh_quality = final_state.get("mesh_quality", {})
    if mesh_quality:
        quality_score = mesh_quality.get("quality_score", 0)
        table.add_row("Mesh Quality", f"{quality_score:.2f}/1.0")
    
    # Solver information
    solver_settings = final_state.get("solver_settings", {})
    if solver_settings:
        table.add_row("Solver", str(solver_settings.get("solver", "N/A")))
    
    # Simulation results
    convergence_metrics = final_state.get("convergence_metrics")
    if convergence_metrics:
        converged = convergence_metrics.get("converged", False)
        table.add_row("Converged", "✅ Yes" if converged else "❌ No")
        
        execution_time = convergence_metrics.get("execution_time", 0)
        if execution_time > 0:
            table.add_row("Execution Time", f"{execution_time:.1f} seconds")
        
        # Display residuals if verbose
        if verbose and convergence_metrics.get("final_residuals"):
            residuals = convergence_metrics["final_residuals"]
            for field, residual in residuals.items():
                table.add_row(f"  {field} Residual", f"{residual:.2e}")
    
    console.print("\n")
    console.print(table)


def display_output_locations(final_state):
    """Display locations of generated files."""
    console.print("\n[bold]📁 Generated Files:[/bold]")
    
    # Case directory
    case_directory = final_state.get("case_directory", "")
    if case_directory:
        console.print(f"[cyan]OpenFOAM Case:[/cyan] {case_directory}")
    
    # Visualization files
    visualization_path = final_state.get("visualization_path", "")
    if visualization_path:
        console.print(f"[cyan]Visualizations:[/cyan] {visualization_path}")
        
        # List specific visualization files if they exist
        viz_path = Path(visualization_path)
        if viz_path.exists():
            image_files = list(viz_path.glob("*.png"))
            if image_files:
                console.print("  [green]Images generated:[/green]")
                for img_file in image_files:
                    console.print(f"    • {img_file.name}")
            
            paraview_files = list(viz_path.glob("*.foam")) + list(viz_path.glob("*.vtk"))
            if paraview_files:
                console.print("  [green]ParaView files:[/green]")
                for pv_file in paraview_files:
                    console.print(f"    • {pv_file.name}")
    
    # Recommendations
    convergence_metrics = final_state.get("convergence_metrics")
    recommendations = convergence_metrics.get("recommendations", []) if convergence_metrics else []
    if recommendations:
        console.print("\n[bold]💡 Recommendations:[/bold]")
        for rec in recommendations:
            console.print(f"  [yellow]• {rec}[/yellow]")


@cli.command()
@click.option('--case-dir', type=click.Path(exists=True), help='OpenFOAM case directory')
@click.option('--output-dir', type=click.Path(), help='Output directory for visualizations')
def visualize(case_dir: str, output_dir: str):
    """Generate visualizations from existing OpenFOAM case."""
    console.print("[yellow]Standalone visualization command not yet implemented[/yellow]")
    console.print("[dim]Use the 'solve' command which includes visualization[/dim]")


@cli.command()
def list_examples():
    """List example CFD problems that can be solved."""
    console.print("\n[bold]📋 Example CFD Problems:[/bold]\n")
    
    examples = [
        {
            "description": "Turbulent flow around a cylinder",
            "command": 'foamai solve "Turbulent flow around a cylinder at Re=1000"'
        },
        {
            "description": "Laminar flow in a pipe",
            "command": 'foamai solve "Laminar flow in a pipe with diameter 0.05m and velocity 2 m/s"'
        },
        {
            "description": "Flow over an airfoil",
            "command": 'foamai solve "Flow over NACA 0012 airfoil at 10 degrees angle of attack"'
        },
        {
            "description": "Channel flow with heat transfer",
            "command": 'foamai solve "Turbulent channel flow with heated walls"'
        },
        {
            "description": "Flow around a sphere",
            "command": 'foamai solve "Steady flow around a sphere at Re=100"'
        }
    ]
    
    for i, example in enumerate(examples, 1):
        console.print(f"[cyan]{i}. {example['description']}[/cyan]")
        console.print(f"   [dim]{example['command']}[/dim]\n")


@cli.command()
def status():
    """Check FoamAI installation and dependencies."""
    console.print("\n[bold]🔧 FoamAI Status Check[/bold]\n")
    
    # Check Python dependencies
    console.print("[cyan]Python Dependencies:[/cyan]")
    dependencies = [
        "langchain", "langchain_openai", "langgraph", 
        "pydantic", "loguru", "rich", "click"
    ]
    
    for dep in dependencies:
        try:
            __import__(dep)
            console.print(f"  ✅ {dep}")
        except ImportError:
            console.print(f"  ❌ {dep} (missing)")
    
    # Check OpenFOAM
    console.print("\n[cyan]OpenFOAM Installation:[/cyan]")
    import subprocess
    try:
        from .config import get_settings
        settings = get_settings()
        
        # Check if we're using WSL path
        if settings.openfoam_path and settings.openfoam_path.startswith("/"):
            # WSL path - run through WSL
            wsl_command = ["wsl", "-e", "bash", "-c", 
                          f"source {settings.openfoam_path}/etc/bashrc && blockMesh -help"]
            result = subprocess.run(wsl_command, capture_output=True, text=True, timeout=10)
        else:
            # Windows path - run directly
            result = subprocess.run(["blockMesh", "-help"], 
                                  capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            console.print("  ✅ OpenFOAM")
        else:
            console.print("  ❌ OpenFOAM (not working)")
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        console.print("  ❌ OpenFOAM (not found)")
    
    # Check ParaView
    console.print("\n[cyan]ParaView Installation:[/cyan]")
    paraview_found = False
    
    try:
        # Check if we have a ParaView path configured
        if settings.paraview_path:
            if settings.paraview_path.startswith("/"):
                # WSL path - check through WSL
                wsl_command = ["wsl", "-e", "bash", "-c", f"which pvpython || which paraview"]
                result = subprocess.run(wsl_command, capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    console.print("  ✅ ParaView (WSL)")
                    paraview_found = True
        
        # If not found and no WSL check, try direct commands or configured path
        if not paraview_found:
            # First try configured path if it's a Windows path
            if not settings.paraview_path.startswith("/"):
                import os
                paraview_exe = os.path.join(settings.paraview_path, "bin", "paraview.exe")
                pvpython_exe = os.path.join(settings.paraview_path, "bin", "pvpython.exe")
                
                if os.path.exists(paraview_exe):
                    console.print(f"  ✅ ParaView ({settings.paraview_path})")
                    paraview_found = True
                elif os.path.exists(pvpython_exe):
                    console.print(f"  ✅ ParaView/pvpython ({settings.paraview_path})")
                    paraview_found = True
            
            # If still not found, try direct commands
            if not paraview_found:
                paraview_commands = ["pvpython", "paraview"]
                for cmd in paraview_commands:
                    try:
                        result = subprocess.run([cmd, "--version"], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            console.print(f"  ✅ ParaView ({cmd})")
                            paraview_found = True
                            break
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
    except Exception:
        pass
    
    if not paraview_found:
        console.print("  ❌ ParaView (not found)")
    
    # Check configuration
    console.print("\n[cyan]Configuration:[/cyan]")
    try:
        from .config import get_settings
        settings = get_settings()
        
        if settings.openai_api_key:
            console.print("  ✅ OpenAI API Key")
        else:
            console.print("  ❌ OpenAI API Key (not set)")
        
        work_dir = settings.get_work_dir()
        if work_dir.exists():
            console.print(f"  ✅ Work Directory: {work_dir}")
        else:
            console.print(f"  ⚠️  Work Directory: {work_dir} (will be created)")
        
    except Exception as e:
        console.print(f"  ❌ Configuration Error: {e}")


def main():
    """Main entry point for the CLI."""
    cli()

if __name__ == "__main__":
    main() 