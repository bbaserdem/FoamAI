"""Command-line interface for FoamAI."""

import click
from rich.console import Console
from rich.panel import Panel

console = Console()

@click.group()
@click.version_option()
def cli():
    """FoamAI: AI-powered CFD application using OpenFOAM and ParaView."""
    pass

@cli.command()
@click.argument('prompt', type=str)
@click.option('--output-format', default='images', help='Output format (images, paraview, data)')
@click.option('--export-images', is_flag=True, help='Export visualization images')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def solve(prompt: str, output_format: str, export_images: bool, verbose: bool):
    """Solve a CFD problem from natural language description."""
    console.print(
        Panel(
            f"[bold blue]FoamAI CFD Solver[/bold blue]\n\n"
            f"[green]Problem:[/green] {prompt}\n"
            f"[green]Output Format:[/green] {output_format}\n"
            f"[green]Export Images:[/green] {export_images}\n"
            f"[green]Verbose:[/green] {verbose}\n\n"
            f"[yellow]⚠️  Implementation in progress...[/yellow]",
            title="CFD Problem Setup",
            border_style="blue"
        )
    )
    
    # TODO: Implement the actual CFD solving pipeline
    # This will be implemented in subsequent phases
    console.print("[red]Error: CFD solving pipeline not yet implemented[/red]")
    console.print("[dim]This will be implemented in Phase 2-5 of the development plan[/dim]")

def main():
    """Main entry point for the CLI."""
    cli()

if __name__ == "__main__":
    main() 