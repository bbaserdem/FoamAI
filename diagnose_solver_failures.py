#!/usr/bin/env python3
"""
Diagnostic script to identify specific solver selection failures and analyze root causes.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents.solver_selector import (
    get_ai_solver_recommendation,
    extract_problem_features,
    SOLVER_REGISTRY,
    extract_keywords_with_context
)
from agents.state import SolverType, GeometryType, AnalysisType

def create_test_state(prompt, **kwargs):
    """Create a standardized test state for consistent testing."""
    default_params = {
        "reynolds_number": 10000,
        "velocity": 10.0,
        "analysis_type": AnalysisType.UNSTEADY
    }
    default_params.update(kwargs)
    
    return {
        "user_prompt": prompt,
        "original_prompt": prompt,
        "parsed_parameters": default_params,
        "geometry_info": {
            "type": GeometryType.CYLINDER,
            "diameter": 0.1
        }
    }

def diagnose_failure(expected_solver, prompt, params, test_name):
    """Diagnose why a specific test case failed."""
    print(f"\n🔍 DIAGNOSING: {test_name}")
    print(f"   Prompt: '{prompt}'")
    print(f"   Expected: {expected_solver.value}")
    
    # Create test state and extract features
    state = create_test_state(prompt, **params)
    features = extract_problem_features(state)
    solver, confidence, alternatives = get_ai_solver_recommendation(features, SOLVER_REGISTRY)
    
    print(f"   Got: {solver.value} (confidence: {confidence:.2f})")
    
    if solver != expected_solver:
        print(f"   ❌ FAILED - Expected {expected_solver.value}")
        
        # Analyze the decision process
        print(f"\n   📊 Decision Analysis:")
        print(f"      Analysis Type: {features['analysis_type']}")
        print(f"      Reynolds Number: {features['reynolds_number']}")
        print(f"      Mach Number: {features['mach_number']}")
        print(f"      Is Multiphase: {features['is_multiphase']}")
        print(f"      Is Compressible: {features['is_compressible']}")
        print(f"      Has Heat Transfer: {features['has_heat_transfer']}")
        print(f"      Is Natural Convection: {features.get('is_natural_convection', False)}")
        print(f"      Is Multi-Region: {features['is_multi_region']}")
        print(f"      Expects Vortex Shedding: {features['expects_vortex_shedding']}")
        print(f"      Time Scale Interest: {features['time_scale_interest']}")
        print(f"      Keywords: {features['user_keywords']}")
        
        # Extract keyword scores
        keyword_scores = extract_keywords_with_context(prompt)
        if keyword_scores:
            print(f"      Keyword Scores: {keyword_scores}")
        
        # Suggest likely fix
        print(f"\n   💡 Likely Issue:")
        if solver == SolverType.PIMPLE_FOAM and expected_solver in [SolverType.PISO_FOAM, SolverType.MRF_SIMPLE_FOAM]:
            print(f"      Priority ordering - {expected_solver.value} should be checked before pimpleFoam")
        elif solver == SolverType.RHO_PIMPLE_FOAM and expected_solver == SolverType.SONIC_FOAM:
            print(f"      Mach number threshold - sonicFoam needs better supersonic detection")
        elif solver in [SolverType.SIMPLE_FOAM, SolverType.PIMPLE_FOAM] and expected_solver == SolverType.BUOYANT_SIMPLE_FOAM:
            print(f"      Natural convection detection needs improvement")
        elif solver != SolverType.CHT_MULTI_REGION_FOAM and expected_solver == SolverType.CHT_MULTI_REGION_FOAM:
            print(f"      Multi-region detection needs better keywords/patterns")
        elif solver != SolverType.REACTING_FOAM and expected_solver == SolverType.REACTING_FOAM:
            print(f"      Reactive flow detection needs better keywords")
        else:
            print(f"      Unknown issue - may need specific keyword tuning")
        
        return False
    else:
        print(f"   ✅ PASSED")
        return True

def run_diagnostic_tests():
    """Run diagnostic tests for all solver types."""
    print("🔬 DIAGNOSTIC ANALYSIS OF SOLVER SELECTION FAILURES")
    print("=" * 70)
    
    failures = []
    
    # Test cases that might be failing
    test_cases = [
        # simpleFoam cases
        (SolverType.SIMPLE_FOAM, "Steady flow around a cylinder", 
         {"analysis_type": AnalysisType.STEADY, "reynolds_number": 100}, "SimpleFoam Steady Low Re"),
        (SolverType.SIMPLE_FOAM, "Pressure drop calculation in a pipe", 
         {"analysis_type": AnalysisType.STEADY}, "SimpleFoam Pressure Drop"),
        
        # pimpleFoam cases  
        (SolverType.PIMPLE_FOAM, "Vortex shedding behind a cylinder", 
         {"reynolds_number": 200}, "PimpleFoam Vortex Shedding"),
        (SolverType.PIMPLE_FOAM, "Transient flow development in a channel", 
         {}, "PimpleFoam Transient"),
        
        # pisoFoam cases
        (SolverType.PISO_FOAM, "Accurate transient simulation of pulsatile flow", 
         {}, "PisoFoam Pulsatile"),
        (SolverType.PISO_FOAM, "High precision time-dependent analysis", 
         {}, "PisoFoam Precision"),
        
        # interFoam cases
        (SolverType.INTER_FOAM, "Dam break simulation with water and air", 
         {"phases": ["water", "air"]}, "InterFoam Dam Break"),
        (SolverType.INTER_FOAM, "Free surface flow in a tank", 
         {}, "InterFoam Free Surface"),
        
        # rhoPimpleFoam cases
        (SolverType.RHO_PIMPLE_FOAM, "Compressible flow at Mach 0.5", 
         {"mach_number": 0.5, "temperature": 300, "pressure": 101325}, "RhoPimple Mach 0.5"),
        (SolverType.RHO_PIMPLE_FOAM, "Gas dynamics in a nozzle", 
         {"temperature": 350}, "RhoPimple Gas Dynamics"),
        
        # sonicFoam cases
        (SolverType.SONIC_FOAM, "Supersonic flow at Mach 2.0", 
         {"mach_number": 2.0}, "SonicFoam Mach 2.0"),
        (SolverType.SONIC_FOAM, "Shock wave propagation", 
         {"mach_number": 1.5}, "SonicFoam Shock Wave"),
        
        # buoyantSimpleFoam cases
        (SolverType.BUOYANT_SIMPLE_FOAM, "Natural convection in a heated cavity", 
         {"temperature": 350, "gravity": 9.81, "analysis_type": AnalysisType.STEADY}, "Buoyant Natural Conv"),
        (SolverType.BUOYANT_SIMPLE_FOAM, "Thermal plume from heated surface", 
         {"temperature": 320, "analysis_type": AnalysisType.STEADY}, "Buoyant Thermal Plume"),
        
        # chtMultiRegionFoam cases
        (SolverType.CHT_MULTI_REGION_FOAM, "Heat exchanger with solid and fluid regions", 
         {"temperature": 350, "regions": ["fluid", "solid"]}, "CHT Heat Exchanger"),
        (SolverType.CHT_MULTI_REGION_FOAM, "Conjugate heat transfer analysis", 
         {"temperature": 300}, "CHT Analysis"),
        
        # reactingFoam cases
        (SolverType.REACTING_FOAM, "Combustion of methane and air", 
         {"species": ["CH4", "O2", "CO2", "H2O", "N2"], "temperature": 800}, "Reacting Combustion"),
        (SolverType.REACTING_FOAM, "Flame propagation in premixed gas", 
         {"temperature": 1000}, "Reacting Flame"),
        
        # MRFSimpleFoam cases
        (SolverType.MRF_SIMPLE_FOAM, "Centrifugal pump impeller analysis", 
         {"rotation_rate": 157, "analysis_type": AnalysisType.STEADY}, "MRF Pump"),
        (SolverType.MRF_SIMPLE_FOAM, "Steady flow through rotating turbine", 
         {"rotation_rate": 628, "analysis_type": AnalysisType.STEADY}, "MRF Turbine"),
    ]
    
    # Run diagnostics
    for expected_solver, prompt, params, test_name in test_cases:
        success = diagnose_failure(expected_solver, prompt, params, test_name)
        if not success:
            failures.append((expected_solver, prompt, test_name))
    
    # Summary
    print(f"\n📊 DIAGNOSTIC SUMMARY")
    print("=" * 30)
    print(f"Total tests: {len(test_cases)}")
    print(f"Failures: {len(failures)}")
    print(f"Success rate: {(len(test_cases) - len(failures)) / len(test_cases) * 100:.1f}%")
    
    if failures:
        print(f"\n❌ Failed Cases:")
        for expected_solver, prompt, test_name in failures:
            print(f"   {test_name}: Expected {expected_solver.value}")
    
    return failures

if __name__ == "__main__":
    failures = run_diagnostic_tests()
    
    if failures:
        print(f"\n🔧 RECOMMENDATIONS FOR FIXES:")
        print("=" * 40)
        
        # Analyze failure patterns
        solver_failures = {}
        for expected_solver, _, _ in failures:
            solver_failures[expected_solver] = solver_failures.get(expected_solver, 0) + 1
        
        for solver, count in solver_failures.items():
            print(f"{solver.value}: {count} failures - needs attention")
    else:
        print(f"\n🎉 No failures detected in diagnostic test!") 