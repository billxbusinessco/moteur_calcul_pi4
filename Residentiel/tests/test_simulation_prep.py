import sys
from pathlib import Path
import pandas as pd
import json
import logging

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.preprocessing.simulation_preparator import SimulationPreparator
from config.mapping_config import ArchetypeToHPXMLMapper, UnitConverter

def test_archetype_conversion():
    """Test de la conversion d'un archetype"""
    print("\nTest 1: Conversion archetype")
    print("-" * 50)
    
    # Créer mapper
    mapper = ArchetypeToHPXMLMapper()
    
    # Archetype test
    test_archetype = {
        'houseType': 'House',
        'houseSubType': 'Single Detached',
        'totFloorArea': 200.0,  # m²
        'dayHeatingSetPoint': 21.0,  # °C
        'coolingSetPoint': 25.0,  # °C
        'spaceHeatingType': 'Baseboards',
        'spaceHeatingFuel': 'Electric'
    }
    
    try:
        hpxml_params = mapper.convert_archetype(test_archetype)
        print("✓ Conversion réussie")
        print("\nParamètres HPXML générés:")
        for param, value in hpxml_params.items():
            print(f"- {param}: {value}")
    except Exception as e:
        print(f"✗ Échec de la conversion: {str(e)}")

def test_workflow_preparation():
    """Test de la préparation des workflows OpenStudio"""
    print("\nTest 2: Préparation workflow")
    print("-" * 50)
    
    # Créer preparator avec logging
    preparator = SimulationPreparator()
    preparator.logger.setLevel(logging.INFO)
    
    # Paramètres test
    test_params = {
        'heating_setpoint': 21.0,  # °C
        'cooling_setpoint': 25.0   # °C
    }
    
    # Tester préparation itération
    print("Préparation itération test (n°999)...")
    try:
        result = preparator.prepare_provincial_iteration(999, test_params)
        
        if result:
            print("✓ Préparation réussie")
            
            # Vérifier structure créée
            iteration_dir = preparator.simulation_dir / "iteration_999"
            if iteration_dir.exists():
                print("\nStructure créée :")
                for item in iteration_dir.glob("**/*"):
                    if item.is_file():
                        print(f"- {item.relative_to(iteration_dir)}")
                
                # Vérifier un workflow
                workflows = list(iteration_dir.glob("**/workflow.osw"))
                if workflows:
                    workflow_file = workflows[0]
                    print(f"\nVérification workflow: {workflow_file.name}")
                    with open(workflow_file) as f:
                        workflow = json.load(f)
                    print(f"- Nombre de steps: {len(workflow['steps'])}")
                    print("- Arguments HPXML :")
                    hpxml_args = workflow['steps'][0]['arguments']
                    for arg in ['hvac_control_heating_weekday_setpoint', 
                               'hvac_control_cooling_weekday_setpoint']:
                        if arg in hpxml_args:
                            print(f"  * {arg}: {hpxml_args[arg]}")
                else:
                    print("✗ Aucun workflow trouvé")
        else:
            print("✗ Échec de la préparation")
            
    except Exception as e:
        print(f"✗ Erreur lors de la préparation: {str(e)}")

def test_unit_conversion():
    """Test des conversions d'unités"""
    print("\nTest 3: Conversions d'unités")
    print("-" * 50)
    
    converter = UnitConverter()
    
    tests = [
        (21.0, converter.c_to_f, "21.0°C", "°F"),
        (100.0, converter.m2_to_ft2, "100m²", "ft²"),
        (1000.0, converter.w_to_btu_hr, "1000W", "BTU/hr")
    ]
    
    for value, func, input_str, unit in tests:
        try:
            result = func(value)
            print(f"✓ {input_str} → {result:.1f} {unit}")
        except Exception as e:
            print(f"✗ Erreur conversion {input_str}: {str(e)}")

if __name__ == "__main__":
    print("Tests du système de préparation des simulations")
    print("=" * 50)
    
    # Exécuter les tests dans l'ordre
    test_unit_conversion()
    test_archetype_conversion()
    test_workflow_preparation()