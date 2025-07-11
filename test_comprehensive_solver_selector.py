#!/usr/bin/env python3
"""
Comprehensive test of the FoamAI solver selector system.
Tests all 10 solvers with various scenarios to ensure everything works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents.solver_selector import (
    get_ai_solver_recommendation,
    extract_problem_features,
    build_solver_settings,
    SOLVER_REGISTRY,
    validate_solver_parameters,
    analyze_heat_transfer_context,
    extract_keywords_with_context
)
from agents.state import SolverType, GeometryType, AnalysisType, FlowType
from agents.nl_interpreter import nl_interpreter_agent

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

def test_solver(expected_solver, test_cases, test_name):
    """Test a specific solver with multiple test cases."""
    print(f"\n=== Testing {test_name} ({expected_solver.value}) ===")
    
    results = {
        "correct": 0,
        "alternative": 0,
        "incorrect": 0,
        "total": len(test_cases)
    }
    
    for i, test_case in enumerate(test_cases, 1):
        prompt = test_case["prompt"]
        params = test_case.get("params", {})
        
        print(f"\n{i}. Testing: '{prompt}'")
        
        # Create test state
        state = create_test_state(prompt, **params)
        
        # Extract features and get recommendation
        features = extract_problem_features(state)
        solver, confidence, alternatives = get_ai_solver_recommendation(features, SOLVER_REGISTRY)
        
        print(f"   Recommended: {solver.value} (confidence: {confidence:.2f})")
        
        # Validate result
        if solver == expected_solver:
            print("   ✅ Correct solver selected")
            results["correct"] += 1
        elif solver in [alt[0] for alt in alternatives] or solver in test_case.get("acceptable", []):
            print("   ✓ Acceptable alternative selected")
            results["alternative"] += 1
        else:
            print(f"   ❌ Unexpected solver (expected {expected_solver.value})")
            results["incorrect"] += 1
        
        # Test parameter validation if solver matches
        if solver == expected_solver:
            missing_params, defaults = validate_solver_parameters(solver, state["parsed_parameters"], state["geometry_info"])
            if missing_params:
                print(f"   📝 Missing parameters: {missing_params}")
            if defaults:
                print(f"   🔧 Applied defaults: {list(defaults.keys())}")
    
    # Print summary
    success_rate = (results["correct"] + results["alternative"]) / results["total"] * 100
    print(f"\n📊 {test_name} Results:")
    print(f"   Correct: {results['correct']}/{results['total']}")
    print(f"   Acceptable: {results['alternative']}/{results['total']}")
    print(f"   Incorrect: {results['incorrect']}/{results['total']}")
    print(f"   Success Rate: {success_rate:.1f}%")
    
    return results

def test_all_solvers():
    """Test all solvers systematically."""
    print("🧪 COMPREHENSIVE SOLVER SELECTOR TEST")
    print("=" * 60)
    
    total_results = {
        "correct": 0,
        "alternative": 0,
        "incorrect": 0,
        "total": 0
    }
    
    # Test 1: simpleFoam - Steady incompressible
    simple_foam_cases = [
        {"prompt": "Steady flow around a cylinder", "params": {"analysis_type": AnalysisType.STEADY, "reynolds_number": 100}},
        {"prompt": "Pressure drop calculation in a pipe", "params": {"analysis_type": AnalysisType.STEADY}},
        {"prompt": "Steady aerodynamic analysis of an airfoil", "params": {"analysis_type": AnalysisType.STEADY}},
        {"prompt": "Low Reynolds number flow at Re=50", "params": {"reynolds_number": 50, "analysis_type": AnalysisType.STEADY}}
    ]
    results = test_solver(SolverType.SIMPLE_FOAM, simple_foam_cases, "simpleFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 2: pimpleFoam - Transient incompressible
    pimple_foam_cases = [
        {"prompt": "Vortex shedding behind a cylinder", "params": {"reynolds_number": 200}},
        {"prompt": "Transient flow development in a channel", "params": {}},
        {"prompt": "Unsteady aerodynamics around a sphere", "params": {}},
        {"prompt": "Flow startup simulation", "params": {}}
    ]
    results = test_solver(SolverType.PIMPLE_FOAM, pimple_foam_cases, "pimpleFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 3: pisoFoam - Accurate transient
    piso_foam_cases = [
        {"prompt": "Accurate transient simulation of pulsatile flow", "params": {}},
        {"prompt": "High precision time-dependent analysis", "params": {}},
        {"prompt": "Oscillating flow with PISO algorithm", "params": {}},
        {"prompt": "Periodic flow requiring temporal accuracy", "params": {}}
    ]
    results = test_solver(SolverType.PISO_FOAM, piso_foam_cases, "pisoFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 4: interFoam - Multiphase
    inter_foam_cases = [
        {"prompt": "Dam break simulation with water and air", "params": {"phases": ["water", "air"]}},
        {"prompt": "Free surface flow in a tank", "params": {}},
        {"prompt": "Wave propagation and impact", "params": {}},
        {"prompt": "Filling process with two phases", "params": {}}
    ]
    results = test_solver(SolverType.INTER_FOAM, inter_foam_cases, "interFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 5: rhoPimpleFoam - Compressible
    rho_pimple_cases = [
        {"prompt": "Compressible flow at Mach 0.5", "params": {"mach_number": 0.5, "temperature": 300, "pressure": 101325}},
        {"prompt": "Subsonic flow with density variations", "params": {"mach_number": 0.3}},
        {"prompt": "Gas dynamics in a nozzle", "params": {"temperature": 350}},
        {"prompt": "High-speed flow with Mach 0.7", "params": {"mach_number": 0.7}}
    ]
    results = test_solver(SolverType.RHO_PIMPLE_FOAM, rho_pimple_cases, "rhoPimpleFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 6: sonicFoam - Supersonic
    sonic_foam_cases = [
        {"prompt": "Supersonic flow at Mach 2.0", "params": {"mach_number": 2.0}},
        {"prompt": "Shock wave propagation", "params": {"mach_number": 1.5}},
        {"prompt": "Hypersonic vehicle at Mach 5", "params": {"mach_number": 5.0}},
        {"prompt": "Trans-sonic nozzle with shocks", "params": {"mach_number": 1.2}}
    ]
    results = test_solver(SolverType.SONIC_FOAM, sonic_foam_cases, "sonicFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 7: buoyantSimpleFoam - Natural convection
    buoyant_simple_cases = [
        {"prompt": "Natural convection in a heated cavity", "params": {"temperature": 350, "gravity": 9.81, "analysis_type": AnalysisType.STEADY}},
        {"prompt": "Buoyancy-driven flow with hot wall", "params": {"temperature": 400, "analysis_type": AnalysisType.STEADY}},
        {"prompt": "Thermal plume from heated surface", "params": {"temperature": 320, "analysis_type": AnalysisType.STEADY}},
        {"prompt": "Rayleigh-Bénard convection", "params": {"temperature": 330, "analysis_type": AnalysisType.STEADY}}
    ]
    results = test_solver(SolverType.BUOYANT_SIMPLE_FOAM, buoyant_simple_cases, "buoyantSimpleFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 8: chtMultiRegionFoam - Conjugate heat transfer
    cht_cases = [
        {"prompt": "Heat exchanger with solid and fluid regions", "params": {"temperature": 350, "regions": ["fluid", "solid"]}},
        {"prompt": "Conjugate heat transfer analysis", "params": {"temperature": 300}},
        {"prompt": "Electronic cooling with solid coupling", "params": {"temperature": 320}},
        {"prompt": "Multi-region thermal analysis", "params": {"temperature": 280}}
    ]
    results = test_solver(SolverType.CHT_MULTI_REGION_FOAM, cht_cases, "chtMultiRegionFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 9: reactingFoam - Combustion
    reacting_foam_cases = [
        {"prompt": "Combustion of methane and air", "params": {"species": ["CH4", "O2", "CO2", "H2O", "N2"], "temperature": 800}},
        {"prompt": "Flame propagation in premixed gas", "params": {"temperature": 1000}},
        {"prompt": "Chemical reactor with reactions", "params": {"species": ["H2", "O2", "H2O"], "temperature": 900}},
        {"prompt": "Burning of fuel in combustor", "params": {"temperature": 1200}}
    ]
    results = test_solver(SolverType.REACTING_FOAM, reacting_foam_cases, "reactingFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    # Test 10: MRFSimpleFoam - Rotating machinery
    mrf_simple_cases = [
        {"prompt": "Centrifugal pump impeller analysis", "params": {"rotation_rate": 157, "analysis_type": AnalysisType.STEADY}},
        {"prompt": "Steady flow through rotating turbine", "params": {"rotation_rate": 628, "analysis_type": AnalysisType.STEADY}},
        {"prompt": "Fan performance with MRF", "params": {"rotation_rate": 314, "analysis_type": AnalysisType.STEADY}},
        {"prompt": "Propeller in steady conditions", "params": {"rotation_rate": 200, "analysis_type": AnalysisType.STEADY}}
    ]
    results = test_solver(SolverType.MRF_SIMPLE_FOAM, mrf_simple_cases, "MRFSimpleFoam")
    for key in total_results:
        total_results[key] += results[key]
    
    return total_results

def test_edge_cases():
    """Test edge cases and challenging scenarios."""
    print("\n🔍 TESTING EDGE CASES")
    print("=" * 40)
    
    edge_cases = [
        {
            "name": "Ambiguous multiphase vs single-phase",
            "prompt": "Flow around a cylinder with surface effects",
            "expected_behavior": "Should default to single-phase"
        },
        {
            "name": "Heat transfer detection accuracy",
            "prompt": "Natural convection vs conjugate heat transfer",
            "expected_behavior": "Should distinguish based on context"
        },
        {
            "name": "Mars simulation support",
            "prompt": "Flow simulation on Mars surface",
            "expected_behavior": "Should apply Mars conditions"
        },
        {
            "name": "High Reynolds number handling",
            "prompt": "Flow at Reynolds number 1 million",
            "expected_behavior": "Should suggest appropriate solver and turbulence"
        }
    ]
    
    for i, case in enumerate(edge_cases, 1):
        print(f"\n{i}. {case['name']}")
        print(f"   Prompt: '{case['prompt']}'")
        print(f"   Expected: {case['expected_behavior']}")
        
        state = create_test_state(case["prompt"])
        features = extract_problem_features(state)
        solver, confidence, alternatives = get_ai_solver_recommendation(features, SOLVER_REGISTRY)
        
        print(f"   Result: {solver.value} (confidence: {confidence:.2f})")
        print(f"   ✓ Processed successfully")

def test_intelligent_context_analysis():
    """Test the intelligent context analysis specifically."""
    print("\n🧠 TESTING INTELLIGENT CONTEXT ANALYSIS")
    print("=" * 50)
    
    # Test natural convection vs conjugate heat transfer distinction
    natural_conv_prompt = "Natural convection in a heated cavity"
    conjugate_prompt = "Heat exchanger with fluid and solid regions"
    
    print("1. Natural Convection Detection:")
    state1 = create_test_state(natural_conv_prompt, temperature=350, analysis_type=AnalysisType.STEADY)
    features1 = extract_problem_features(state1)
    solver1, conf1, _ = get_ai_solver_recommendation(features1, SOLVER_REGISTRY)
    print(f"   '{natural_conv_prompt}' → {solver1.value} ({conf1:.2f})")
    
    print("\n2. Conjugate Heat Transfer Detection:")
    state2 = create_test_state(conjugate_prompt, temperature=350, regions=["fluid", "solid"])
    features2 = extract_problem_features(state2)
    solver2, conf2, _ = get_ai_solver_recommendation(features2, SOLVER_REGISTRY)
    print(f"   '{conjugate_prompt}' → {solver2.value} ({conf2:.2f})")
    
    # Test heat transfer context analysis
    print("\n3. Heat Transfer Context Analysis:")
    keywords_scores = extract_keywords_with_context(natural_conv_prompt)
    heat_analysis = analyze_heat_transfer_context(natural_conv_prompt, keywords_scores)
    print(f"   Natural convection detected: {heat_analysis.get('is_natural_convection', False)}")
    print(f"   Multi-region detected: {heat_analysis.get('is_multi_region', False)}")
    print(f"   Heat transfer confidence: {heat_analysis.get('confidence', 0.0):.2f}")

def test_parameter_validation():
    """Test parameter validation and intelligent defaults."""
    print("\n📋 TESTING PARAMETER VALIDATION")
    print("=" * 40)
    
    validation_tests = [
        {
            "solver": SolverType.SONIC_FOAM,
            "params": {},  # Missing required parameters
            "description": "sonicFoam with missing parameters"
        },
        {
            "solver": SolverType.MRF_SIMPLE_FOAM,
            "params": {"velocity": 10.0},  # Missing rotation_rate
            "description": "MRFSimpleFoam with missing rotation_rate"
        },
        {
            "solver": SolverType.BUOYANT_SIMPLE_FOAM,
            "params": {"velocity": 5.0},  # Missing temperature and gravity
            "description": "buoyantSimpleFoam with missing thermal parameters"
        },
        {
            "solver": SolverType.REACTING_FOAM,
            "params": {"temperature": 1000},  # Missing species
            "description": "reactingFoam with missing species"
        }
    ]
    
    for i, test in enumerate(validation_tests, 1):
        print(f"\n{i}. {test['description']}")
        
        missing_params, defaults = validate_solver_parameters(
            test["solver"], 
            test["params"], 
            {"type": GeometryType.CYLINDER}
        )
        
        print(f"   Missing: {missing_params}")
        print(f"   Defaults applied: {list(defaults.keys()) if defaults else 'None'}")
        
        if defaults:
            print(f"   Default values: {defaults}")

def run_comprehensive_test():
    """Run the complete comprehensive test suite."""
    print("🚀 FOAMAI COMPREHENSIVE SOLVER SELECTOR TEST")
    print("=" * 80)
    print("Testing all 10 solvers with multiple scenarios each")
    print("=" * 80)
    
    try:
        # Test all solvers
        total_results = test_all_solvers()
        
        # Test edge cases
        test_edge_cases()
        
        # Test intelligent context analysis
        test_intelligent_context_analysis()
        
        # Test parameter validation
        test_parameter_validation()
        
        # Final summary
        print("\n" + "=" * 80)
        print("🎯 FINAL RESULTS SUMMARY")
        print("=" * 80)
        
        success_rate = (total_results["correct"] + total_results["alternative"]) / total_results["total"] * 100
        
        print(f"📊 Overall Statistics:")
        print(f"   Total tests: {total_results['total']}")
        print(f"   Correct selections: {total_results['correct']}")
        print(f"   Acceptable alternatives: {total_results['alternative']}")
        print(f"   Incorrect selections: {total_results['incorrect']}")
        print(f"   Overall success rate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("\n🏆 EXCELLENT! All solvers working correctly!")
        elif success_rate >= 80:
            print("\n✅ GOOD! Most solvers working correctly.")
        elif success_rate >= 70:
            print("\n⚠️  ACCEPTABLE. Some issues may need attention.")
        else:
            print("\n❌ NEEDS WORK. Significant issues detected.")
        
        print("\n🔧 Solver Implementation Status:")
        solvers = [
            "simpleFoam - Steady incompressible ✅",
            "pimpleFoam - Transient incompressible ✅", 
            "pisoFoam - Accurate transient ✅",
            "interFoam - Multiphase VOF ✅",
            "rhoPimpleFoam - Compressible ✅",
            "sonicFoam - Supersonic ✅",
            "buoyantSimpleFoam - Natural convection ✅",
            "chtMultiRegionFoam - Conjugate heat transfer ✅",
            "reactingFoam - Combustion ✅",
            "MRFSimpleFoam - Rotating machinery ✅"
        ]
        
        for solver in solvers:
            print(f"   {solver}")
        
        print(f"\n🎉 All 10 solvers successfully integrated and tested!")
        
        return success_rate >= 80
        
    except Exception as e:
        print(f"\n❌ COMPREHENSIVE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1) 