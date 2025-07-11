"""Intelligent Error Handler Agent - AI-powered error explanation and recovery."""

import json
import openai
import os
from typing import Dict, Any, List, Optional
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm

from .state import CFDState, CFDStep

console = Console()


def error_handler_agent(state: CFDState) -> CFDState:
    """
    Intelligent Error Handler Agent.
    
    Uses OpenAI to explain errors in user-friendly language and provide
    specific suggestions for fixes. Prompts user for next action.
    """
    try:
        if state["verbose"]:
            logger.info("Error Handler: Starting intelligent error analysis")
        
        # Get the most recent error
        if not state["errors"]:
            logger.warning("Error Handler: No errors found in state")
            return {
                **state,
                "current_step": CFDStep.COMPLETE,
                "conversation_active": False
            }
        
        current_error = state["errors"][-1]
        
        # Get AI explanation and suggestions
        error_analysis = get_ai_error_analysis(current_error, state)
        
        # Display error analysis to user
        display_error_analysis(error_analysis, state)
        
        # Get user's decision on how to proceed
        user_decision = prompt_for_error_recovery(state, error_analysis)
        
        if user_decision == "retry":
            # Clear errors and retry from appropriate step
            recovery_step = determine_recovery_step(current_error, state)
            logger.info(f"Error Handler: User chose to retry from step {recovery_step}")
            return {
                **state,
                "errors": [],
                "current_step": recovery_step,
                "retry_count": state["retry_count"] + 1
            }
        elif user_decision == "modify":
            # User wants to modify parameters - start new iteration
            new_prompt = get_modified_prompt(state, error_analysis)
            if new_prompt:
                return start_error_recovery_iteration(state, new_prompt)
            else:
                # User canceled modification
                return complete_error_session(state)
        elif user_decision == "continue":
            # User wants to continue with current results despite error
            logger.info("Error Handler: User chose to continue despite error")
            return {
                **state,
                "warnings": state["warnings"] + [f"Continued with error: {current_error}"],
                "errors": [],
                "current_step": determine_continue_step(state)
            }
        else:
            # User chose to exit
            return complete_error_session(state)
            
    except Exception as e:
        logger.error(f"Error Handler: Failed to process error: {str(e)}")
        # Fallback to original error handling
        return {
            **state,
            "errors": state["errors"] + [f"Error handler failed: {str(e)}"],
            "current_step": CFDStep.ERROR,
            "conversation_active": False
        }


def get_ai_error_analysis(error_message: str, state: CFDState) -> Dict[str, Any]:
    """Get AI-powered error analysis and suggestions."""
    
    try:
        # Get OpenAI API key from settings
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        if not settings.openai_api_key:
            logger.warning("Error Handler: No OpenAI API key found, using fallback analysis")
            return get_fallback_error_analysis(error_message, state)
        
        # Prepare context for the AI
        context = {
            "error_message": error_message,
            "current_step": state.get("current_step", "unknown"),
            "user_prompt": state.get("user_prompt", ""),
            "parsed_parameters": state.get("parsed_parameters", {}),
            "geometry_info": state.get("geometry_info", {}),
            "retry_count": state.get("retry_count", 0)
        }
        
        # Create system message for error analysis
        system_message = """You are an expert CFD engineer helping users troubleshoot OpenFOAM simulation errors.
        
        Your task is to:
        1. Explain the error in simple, non-technical language
        2. Identify the most likely causes
        3. Provide specific, actionable suggestions to fix the issue
        4. Suggest parameter changes if needed
        5. Assess if the error is recoverable or requires starting over
        
        Be encouraging and helpful. Focus on practical solutions."""
        
        user_message = f"""I encountered this error during CFD simulation:

Error: {error_message}

Current workflow step: {context['current_step']}
User's original request: {context['user_prompt']}
Parsed parameters: {json.dumps(context['parsed_parameters'], indent=2)}
Geometry info: {json.dumps(context['geometry_info'], indent=2)}
Retry attempt: {context['retry_count']}

Please provide a clear explanation and helpful suggestions."""
        
        # Call OpenAI API
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            max_tokens=800,
            temperature=0.1
        )
        
        ai_response = response.choices[0].message.content
        
        # Parse the response into structured format
        analysis = parse_ai_error_response(ai_response, error_message)
        
        logger.info("Error Handler: AI analysis completed successfully")
        return analysis
        
    except Exception as e:
        logger.error(f"Error Handler: AI analysis failed: {str(e)}")
        return get_fallback_error_analysis(error_message, state)


def get_fallback_error_analysis(error_message: str, state: CFDState) -> Dict[str, Any]:
    """Fallback error analysis when AI is not available."""
    
    error_lower = error_message.lower()
    
    # Pattern matching for common errors
    if "openfoam" in error_lower or "command not found" in error_lower:
        return {
            "explanation": "OpenFOAM software is not installed or not accessible.",
            "likely_causes": [
                "OpenFOAM is not installed on your system",
                "OpenFOAM is not in your system PATH",
                "Wrong version of OpenFOAM"
            ],
            "suggestions": [
                "Install OpenFOAM following the official installation guide",
                "Check that OpenFOAM commands are in your PATH",
                "Verify OpenFOAM installation with 'which blockMesh'"
            ],
            "severity": "high",
            "recoverable": False
        }
    elif "mesh" in error_lower or "blockmesh" in error_lower:
        return {
            "explanation": "There's a problem with the mesh generation process.",
            "likely_causes": [
                "Invalid geometry parameters",
                "Mesh resolution too fine or too coarse",
                "Geometric constraints not satisfied"
            ],
            "suggestions": [
                "Try adjusting the mesh resolution",
                "Check if geometry parameters are reasonable",
                "Simplify the geometry if it's too complex"
            ],
            "severity": "medium",
            "recoverable": True
        }
    elif "boundary" in error_lower or "patch" in error_lower:
        return {
            "explanation": "There's an issue with boundary condition setup.",
            "likely_causes": [
                "Boundary condition type mismatch",
                "Missing boundary patches",
                "Incompatible boundary conditions"
            ],
            "suggestions": [
                "Check boundary condition types match the physics",
                "Verify all patches have appropriate boundary conditions",
                "Consider using simpler boundary conditions"
            ],
            "severity": "medium",
            "recoverable": True
        }
    elif "solver" in error_lower or "converge" in error_lower:
        return {
            "explanation": "The simulation solver encountered numerical issues.",
            "likely_causes": [
                "Numerical instability",
                "Inappropriate solver settings",
                "Poor mesh quality"
            ],
            "suggestions": [
                "Try reducing time step or relaxation factors",
                "Use a more stable solver",
                "Improve mesh quality"
            ],
            "severity": "medium",
            "recoverable": True
        }
    else:
        return {
            "explanation": "An unexpected error occurred during the simulation.",
            "likely_causes": [
                "System configuration issue",
                "File permission problem",
                "Resource limitations"
            ],
            "suggestions": [
                "Check system requirements",
                "Verify file permissions",
                "Try with simpler parameters"
            ],
            "severity": "medium",
            "recoverable": True
        }


def parse_ai_error_response(ai_response: str, original_error: str) -> Dict[str, Any]:
    """Parse AI response into structured format."""
    
    # Default structure
    analysis = {
        "explanation": "Error analysis not available",
        "likely_causes": [],
        "suggestions": [],
        "severity": "medium",
        "recoverable": True,
        "ai_response": ai_response
    }
    
    # Try to extract information from AI response
    # This is a simple parser - could be enhanced with more sophisticated NLP
    try:
        lines = ai_response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for section headers
            if any(keyword in line.lower() for keyword in ['explanation', 'what this means', 'error means']):
                current_section = 'explanation'
            elif any(keyword in line.lower() for keyword in ['causes', 'why this happened', 'reasons']):
                current_section = 'causes'
            elif any(keyword in line.lower() for keyword in ['suggestions', 'solutions', 'fix', 'try']):
                current_section = 'suggestions'
            elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # Bullet point
                item = line[1:].strip()
                if current_section == 'causes':
                    analysis['likely_causes'].append(item)
                elif current_section == 'suggestions':
                    analysis['suggestions'].append(item)
            elif current_section == 'explanation' and len(line) > 20:
                # Longer line likely to be explanation
                analysis['explanation'] = line
        
        # If we didn't extract much, use the full response as explanation
        if not analysis['likely_causes'] and not analysis['suggestions']:
            analysis['explanation'] = ai_response[:300] + "..." if len(ai_response) > 300 else ai_response
        
        # Determine severity and recoverability
        if any(keyword in original_error.lower() for keyword in ['not found', 'missing', 'install']):
            analysis['severity'] = 'high'
            analysis['recoverable'] = False
        elif any(keyword in original_error.lower() for keyword in ['failed', 'error', 'exception']):
            analysis['severity'] = 'medium'
            analysis['recoverable'] = True
        
    except Exception as e:
        logger.error(f"Error parsing AI response: {str(e)}")
        analysis['explanation'] = ai_response
    
    return analysis


def display_error_analysis(error_analysis: Dict[str, Any], state: CFDState) -> None:
    """Display the error analysis to the user."""
    
    console.print("\n" + "="*60)
    console.print("🔍 Error Analysis", style="bold red")
    console.print("="*60)
    
    # Display explanation
    console.print(Panel(
        error_analysis['explanation'],
        title="🚨 What Happened",
        border_style="red"
    ))
    
    # Display likely causes
    if error_analysis['likely_causes']:
        console.print("\n🔍 Likely Causes:")
        for i, cause in enumerate(error_analysis['likely_causes'], 1):
            console.print(f"  {i}. {cause}")
    
    # Display suggestions
    if error_analysis['suggestions']:
        console.print("\n💡 Suggested Solutions:")
        for i, suggestion in enumerate(error_analysis['suggestions'], 1):
            console.print(f"  {i}. {suggestion}")
    
    # Display severity info
    severity_color = "red" if error_analysis['severity'] == 'high' else "yellow"
    recoverable_text = "✅ Recoverable" if error_analysis['recoverable'] else "❌ Requires restart"
    
    console.print(f"\n📊 Severity: [{severity_color}]{error_analysis['severity'].upper()}[/{severity_color}]")
    console.print(f"🔄 Recovery: {recoverable_text}")


def prompt_for_error_recovery(state: CFDState, error_analysis: Dict[str, Any]) -> str:
    """Prompt user for how they want to handle the error."""
    
    console.print("\n🤔 How would you like to proceed?")
    console.print()
    
    # Show current iteration info
    iteration_num = state.get("current_iteration", 0) + 1
    console.print(f"📍 Current iteration: {iteration_num}")
    console.print(f"🔄 Retry count: {state.get('retry_count', 0)}")
    console.print()
    
    # Show options based on error severity
    options = []
    if error_analysis['recoverable']:
        options.extend([
            ("1", "🔄 Retry with current settings"),
            ("2", "✏️  Modify parameters and try again"),
        ])
        
        # Only show continue option for medium severity errors
        if error_analysis['severity'] == 'medium':
            options.append(("3", "⚠️  Continue despite error (not recommended)"))
    else:
        options.extend([
            ("1", "✏️  Modify parameters and start over"),
        ])
    
    options.append(("0", "🚪 Exit the session"))
    
    console.print("Choose your next action:")
    for choice, description in options:
        console.print(f"  [bold green]{choice}[/bold green]. {description}")
    
    console.print()
    
    # Get user choice
    valid_choices = [choice for choice, _ in options]
    while True:
        choice = Prompt.ask("Enter your choice", choices=valid_choices, default="0")
        
        if choice == "1":
            if error_analysis['recoverable']:
                return "retry"
            else:
                return "modify"
        elif choice == "2":
            return "modify"
        elif choice == "3":
            confirm = Confirm.ask("⚠️  Are you sure you want to continue with the error? This may cause further issues.")
            if confirm:
                return "continue"
            else:
                continue  # Ask again
        elif choice == "0":
            return "exit"


def get_modified_prompt(state: CFDState, error_analysis: Dict[str, Any]) -> str:
    """Get modified prompt from user for error recovery."""
    
    console.print("\n✏️  Parameter Modification")
    console.print("="*50)
    
    # Show current prompt
    current_prompt = state.get("user_prompt", "")
    console.print(f"[dim]Current prompt: {current_prompt}[/dim]")
    console.print()
    
    # Show suggestions specifically for modification
    if error_analysis['suggestions']:
        console.print("💡 [bold]Suggestions for your new prompt:[/bold]")
        for i, suggestion in enumerate(error_analysis['suggestions'], 1):
            console.print(f"   {i}. {suggestion}")
        console.print()
    
    # Provide specific guidance based on error type
    guidance = get_modification_guidance(error_analysis, state)
    if guidance:
        console.print(f"📋 [bold]Specific guidance:[/bold] {guidance}")
        console.print()
    
    # Get new prompt
    console.print("Enter your modified CFD problem description:")
    console.print("(You can adjust parameters, change geometry, modify conditions, etc.)")
    console.print("Type 'cancel' to exit instead.")
    console.print()
    
    new_prompt = Prompt.ask("Modified prompt", default="")
    
    if new_prompt.lower() == "cancel" or not new_prompt.strip():
        return ""
    
    return new_prompt.strip()


def get_modification_guidance(error_analysis: Dict[str, Any], state: CFDState) -> str:
    """Get specific guidance for parameter modification."""
    
    current_step = state.get("current_step", "")
    
    if "mesh" in error_analysis['explanation'].lower():
        return "Try reducing mesh resolution, simplifying geometry, or using different dimensions."
    elif "boundary" in error_analysis['explanation'].lower():
        return "Consider using simpler boundary conditions or adjusting inlet/outlet pressures."
    elif "solver" in error_analysis['explanation'].lower():
        return "Try reducing velocity, changing from turbulent to laminar flow, or using steady-state analysis."
    elif "parameters" in error_analysis['explanation'].lower():
        return "Adjust numerical values to be within reasonable physical ranges."
    else:
        return "Try simpler parameters, lower velocities, or different geometry."


def start_error_recovery_iteration(state: CFDState, new_prompt: str) -> CFDState:
    """Start a new iteration for error recovery."""
    
    # Archive current failed attempt
    failed_attempt = {
        "iteration": state.get("current_iteration", 0),
        "user_prompt": state.get("user_prompt", ""),
        "error": state["errors"][-1] if state["errors"] else "Unknown error",
        "step_failed": state.get("current_step", "unknown"),
        "retry_count": state.get("retry_count", 0)
    }
    
    # Add to session history
    session_history = state.get("session_history", [])
    session_history.append(failed_attempt)
    
    logger.info(f"Error Handler: Starting recovery iteration {state.get('current_iteration', 0) + 1}")
    
    # Reset state for new iteration
    return {
        **state,
        "user_prompt": new_prompt,
        "parsed_parameters": {},
        "geometry_info": {},
        "mesh_config": {},
        "boundary_conditions": {},
        "solver_settings": {},
        "case_directory": "",
        "simulation_results": {},
        "visualization_path": "",
        "errors": [],
        "warnings": [],
        "current_step": CFDStep.NL_INTERPRETATION,
        "retry_count": 0,
        "user_approved": False,
        "mesh_quality": None,
        "convergence_metrics": None,
        "session_history": session_history,
        "current_iteration": state.get("current_iteration", 0) + 1,
        "conversation_active": True
    }


def complete_error_session(state: CFDState) -> CFDState:
    """Complete the session after an error."""
    
    console.print("\n👋 Session ended due to error.")
    console.print("Your progress has been saved.")
    
    return {
        **state,
        "conversation_active": False,
        "current_step": CFDStep.COMPLETE
    }


def determine_recovery_step(error_message: str, state: CFDState) -> CFDStep:
    """Determine which step to retry from based on error."""
    
    error_lower = error_message.lower()
    
    # Map error types to recovery steps
    if any(keyword in error_lower for keyword in ["mesh", "blockmesh", "geometry"]):
        return CFDStep.MESH_GENERATION
    elif any(keyword in error_lower for keyword in ["boundary", "inlet", "outlet", "patch"]):
        return CFDStep.BOUNDARY_CONDITIONS
    elif any(keyword in error_lower for keyword in ["solver", "scheme", "solution"]):
        return CFDStep.SOLVER_SELECTION
    elif any(keyword in error_lower for keyword in ["case", "file", "directory"]):
        return CFDStep.CASE_WRITING
    elif any(keyword in error_lower for keyword in ["simulation", "execution"]):
        return CFDStep.SIMULATION
    else:
        # Default to NL interpretation for unclear errors
        return CFDStep.NL_INTERPRETATION


def determine_continue_step(state: CFDState) -> CFDStep:
    """Determine next step when continuing despite error."""
    
    current_step = state.get("current_step", CFDStep.ERROR)
    
    # Try to continue to next logical step
    continue_map = {
        CFDStep.MESH_GENERATION: CFDStep.BOUNDARY_CONDITIONS,
        CFDStep.BOUNDARY_CONDITIONS: CFDStep.SOLVER_SELECTION,
        CFDStep.SOLVER_SELECTION: CFDStep.CASE_WRITING,
        CFDStep.CASE_WRITING: CFDStep.SIMULATION,
        CFDStep.SIMULATION: CFDStep.VISUALIZATION,
        CFDStep.VISUALIZATION: CFDStep.RESULTS_REVIEW,
    }
    
    return continue_map.get(current_step, CFDStep.COMPLETE) 