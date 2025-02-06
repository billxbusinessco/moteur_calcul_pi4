import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.mapping_config import (
    ArchetypeToHPXMLMapper,
    m2_to_ft2,
    c_to_f
)

def test_unit_conversions():
    """Test des conversions d'unités de base"""
    print("\nTest 1: Conversions d'unités")
    print("-" * 50)
    
    # Test m² → ft²
    test_area = 100  # m²
    converted_area = m2_to_ft2(test_area)
    print(f"Conversion 100 m² → {converted_area:.1f} ft²")
    
    # Test °C → °F
    test_temp = 21  # °C
    converted_temp = c_to_f(test_temp)
    print(f"Conversion 21°C → {converted_temp:.1f}°F")

def test_simple_mapping():
    """Test d'un mapping simple d'archétype"""
    print("\nTest 2: Mapping simple")
    print("-" * 50)
    
    # Créer un archétype test
    test_archetype = {
        'houseType': 'House',
        'houseSubType': 'Single Detached',
        'totFloorArea': 200.0,  # m²
        'dayHeatingSetPoint': 21.0,  # °C
        'coolingSetPoint': 25.0  # °C
    }
    
    # Tester le mapping
    mapper = ArchetypeToHPXMLMapper()
    hpxml_params = mapper.convert_archetype(test_archetype)
    
    # Afficher résultats
    print("Paramètres HPXML générés :")
    for param, value in hpxml_params.items():
        print(f"- {param}: {value}")

def test_murb_mapping():
    """Test du mapping d'un bâtiment multilogement"""
    print("\nTest 3: Mapping MURB")
    print("-" * 50)
    
    # Archétype MURB test
    test_murb = {
        'houseType': 'Multi-unit: whole building',
        'houseSubType': 'Attached Triplex',
        'totFloorArea': 300.0,  # m²
        'murbDwellingCount': 3,
        'dayHeatingSetPoint': 21.0,  # °C
        'coolingSetPoint': 25.0,  # °C
    }
    
    # Tester le mapping
    mapper = ArchetypeToHPXMLMapper()
    hpxml_params = mapper.convert_archetype(test_murb)
    
    # Afficher résultats
    print("Paramètres HPXML générés pour MURB:")
    for param, value in hpxml_params.items():
        print(f"- {param}: {value}")

if __name__ == "__main__":
    print("Tests du système de mapping HPXML")
    print("=" * 50)
    
    test_unit_conversions()
    test_simple_mapping()
    test_murb_mapping()  # Ajout du nouveau test