import sys
from pathlib import Path
import pandas as pd
import logging
import json
import time
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.preprocessing.simulation_preparator import SimulationPreparator
from src.simulation.simulation_manager import SimulationManager
from src.simulation.results_manager import ResultsManager
from src.analysis.building_stock_aggregator import BuildingStockAggregator
from src.analysis.validation_system import ValidationSystem
from config.paths_config import get_iteration_dirs, PROCESSED_DATA_DIR

def setup_logger():
    """Configure le logger"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('IntegrationTest')

def test_single_archetype(archetype: pd.Series, iteration: int) -> bool:
    """Test un archétype spécifique"""
    logger = setup_logger()
    
    try:
        # Initialisation
        preparator = SimulationPreparator()
        simulator = SimulationManager()
        results_manager = ResultsManager()
        
        # Paramètres de test
        test_params = {
            'heating_setpoint': 21.0,
            'cooling_setpoint': 25.0
        }
        
        # Préparation et simulation
        start_time = time.time()
        
        if not preparator.prepare_provincial_iteration(
            iteration=iteration,
            parameters=test_params,
            archetypes_df=pd.DataFrame([archetype])
        ):
            raise Exception(f"Échec préparation pour {archetype['filename']}")
            
        if not simulator.run_provincial_simulations(iteration):
            raise Exception(f"Échec simulation pour {archetype['filename']}")
            
        if not results_manager.process_iteration_results(iteration):
            raise Exception(f"Échec traitement pour {archetype['filename']}")
            
        duration = time.time() - start_time
        
        # Log des résultats
        logger.info(f"\nRésultats pour {archetype['filename']}:")
        logger.info(f"- Type: {archetype['houseSubType']}")
        logger.info(f"- Zone: {archetype['weather_zone']}")
        logger.info(f"- Temps d'exécution: {duration:.2f} secondes")
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur test archétype {archetype['filename']}: {str(e)}")
        return False

def test_archetype_types():
    """Test avec différents types d'archétypes"""
    logger = setup_logger()
    
    try:
        # Charger archétypes
        archetypes = pd.read_csv(PROCESSED_DATA_DIR / 'selected_archetypes.csv')
        
        # Sélectionner un archétype par type
        test_archetypes = []
        for house_type in archetypes['houseSubType'].unique():
            arch = archetypes[archetypes['houseSubType'] == house_type].iloc[0]
            test_archetypes.append(arch)
        
        logger.info(f"\nTest sur {len(test_archetypes)} types d'archétypes:")
        for type_ in archetypes['houseSubType'].unique():
            logger.info(f"- {type_}")
            
        # Tester chaque archétype
        results = []
        for i, arch in enumerate(test_archetypes):
            iteration = 900 + i  # Pour avoir des itérations uniques
            success = test_single_archetype(arch, iteration)
            results.append({
                'archetype': arch['filename'],
                'type': arch['houseSubType'],
                'success': success
            })
        
        # Résumé
        success_rate = sum(r['success'] for r in results) / len(results) * 100
        logger.info(f"\nRésultats des tests:")
        logger.info(f"- Taux de succès: {success_rate:.1f}%")
        for result in results:
            status = '✓' if result['success'] else '✗'
            logger.info(f"- {status} {result['type']} ({result['archetype']})")
            
        return success_rate > 80  # Succès si plus de 80% réussissent
        
    except Exception as e:
        logger.error(f"Erreur test types: {str(e)}")
        return False

def test_hydro_quebec_validation(iteration: int = 999) -> bool:
    """Valide les résultats avec les données Hydro-Québec"""
    logger = setup_logger()
    
    try:
        validator = ValidationSystem()
        aggregator = BuildingStockAggregator()
        
        # Charger données Hydro-Québec
        if not validator.load_hydro_quebec_data(2022):
            raise Exception("Échec chargement données Hydro-Québec")
        
        # Charger résultats agrégés
        if not validator.load_simulation_results(iteration):
            raise Exception("Échec chargement résultats simulation")
            
        # Calculer métriques
        metrics = validator.calculate_metrics()
        if metrics is None:
            raise Exception("Échec calcul métriques")
            
        # Sauvegarder résultats
        report = {
            'timestamp': datetime.now().isoformat(),
            'iteration': iteration,
            'metrics': metrics
        }
        
        report_file = get_iteration_dirs(iteration)['validation_file']
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info("\nRapport de validation sauvegardé:")
        logger.info(f"- Fichier: {report_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur validation: {str(e)}")
        return False

def print_simulation_report(iteration: int):
    """Affiche un rapport détaillé de la simulation"""
    logger = logging.getLogger('IntegrationTest')
    
    try:
        iteration_dir = get_iteration_dirs(iteration)['simulation_dir']
        
        logger.info("\nRapport de simulation :")
        logger.info("-" * 50)
        
        if iteration_dir.exists():
            # Fichiers
            workflow_files = list(iteration_dir.glob("**/workflow.osw"))
            results_files = list(iteration_dir.glob("**/results_timeseries.csv"))
            log_files = list(iteration_dir.glob("**/*.log"))
            
            logger.info("Fichiers générés :")
            logger.info(f"- Workflows : {len(workflow_files)}")
            logger.info(f"- Résultats : {len(results_files)}")
            logger.info(f"- Logs : {len(log_files)}")
            
            # Taille des fichiers
            total_size = sum(f.stat().st_size for f in results_files) / (1024*1024)
            logger.info(f"Taille totale des résultats: {total_size:.1f} MB")
            
        else:
            logger.error(f"Dossier d'itération non trouvé : {iteration_dir}")
            
    except Exception as e:
        logger.error(f"Erreur génération rapport : {str(e)}")

if __name__ == "__main__":
    print("\nTests d'intégration du système de simulation")
    print("=" * 50)
    
    # 1. Test des différents types d'archétypes
    print("\nTest 1: Différents types d'archétypes")
    success_types = test_archetype_types()
    
    # 2. Test de validation Hydro-Québec
    print("\nTest 2: Validation Hydro-Québec")
    success_validation = test_hydro_quebec_validation(999)
    
    # Résumé global
    print("\nRésumé des tests:")
    print(f"- Types d'archétypes: {'✓' if success_types else '✗'}")
    print(f"- Validation Hydro-Q: {'✓' if success_validation else '✗'}")
    
    if success_types and success_validation:
        print("\n✓ Tests d'intégration réussis")
    else:
        print("\n✗ Échec des tests d'intégration")
        print_simulation_report(999)