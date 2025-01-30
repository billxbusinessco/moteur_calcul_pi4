import logging
from pathlib import Path
import sys
import json
from datetime import datetime
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR, RESULTS_DIR
from src.preprocessing.params_optimizer import ParamsOptimizer
from src.preprocessing.simulation_preparator import SimulationPreparator
from src.simulation.simulation_manager import SimulationManager
from src.simulation.results_manager import ResultsManager
from src.analysis.building_stock_aggregator import BuildingStockAggregator
from src.analysis.validation_system import ValidationSystem
from src.visualization.calibration_visualizer import CalibrationVisualizer

class CalibrationManager:
    """Gestionnaire principal de la calibration"""
    def __init__(self):
        self.logger = self._setup_logger()
        
        # Composants principaux
        self.params_optimizer = ParamsOptimizer()
        self.simulation_preparator = SimulationPreparator()
        self.simulation_manager = SimulationManager()
        self.results_manager = ResultsManager()
        self.building_stock_aggregator = BuildingStockAggregator()
        self.validation_system = ValidationSystem()
        self.visualizer = CalibrationVisualizer()
        
        # État de la calibration
        self.current_campaign = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.campaign_dir = RESULTS_DIR / f'campaign_{self.current_campaign}'
        self.campaign_dir.mkdir(parents=True, exist_ok=True)
        
        # Statut de la campagne
        self.campaign_status = {
            'started': False,
            'completed': False,
            'current_iteration': 0,  # Déjà présent dans le dictionnaire
            'best_score': float('inf'),
            'best_params': None
        }
        self.current_iteration = 0  

    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('CalibrationManager')

    def run_calibration_campaign(self, max_iterations=20, convergence_threshold=0.01) -> dict:
        try:
            # 1. Initialisation
            self.campaign_status['started'] = True
            self.current_iteration = 0

            # Charger les données Hydro-Québec AVANT de commencer
            if not self.validation_system.load_hydro_quebec_data(2022):
                raise ValueError("Impossible de charger les données Hydro-Québec")
            
            # Initialiser visualiseur avec les paramètres
            self.visualizer.setup_display(['heating_setpoint', 'cooling_setpoint'])

            # 2. Boucle principale de calibration
            while (not self.params_optimizer.check_convergence() and 
                   self.current_iteration < max_iterations):
                # Suggérer nouveaux paramètres
                params = self.params_optimizer.suggest_parameters()
                
                # Lancer simulation
                simulation_results = self._run_iteration(params)

                # Charger les résultats dans le validation system
                if not self.validation_system.load_simulation_results(self.current_iteration):
                    self.logger.error(f"Échec chargement résultats simulation {self.current_iteration}")
                    continue
                
                # Calculer score
                score = self.validation_system.calculate_objective_function()
                
                # Mettre à jour l'optimiseur
                self.params_optimizer.update(params, score)
                
                # Préparer données pour visualisation
                viz_data = {
                    'iteration': self.current_iteration,
                    'score': score,
                    'parameters': params,
                    'comparison': {
                        'hydro': self.validation_system.hydro_data,
                        'simulation': simulation_results
                    },
                    'converged': self.params_optimizer.check_convergence()
                }
                
                # Mettre à jour visualisation
                self.visualizer.update(viz_data)
                
                self.current_iteration += 1

            # 3. Sauvegarder résultats finaux
            self.visualizer.save_results()
            return self._get_final_results()

        except Exception as e:
            self.logger.error(f"Erreur lors de la calibration : {str(e)}")
            return None
        
    def _run_iteration(self, parameters: dict):
        """Exécute une itération complète de simulation"""
        try:
            # 1. Préparation des fichiers
            if not self.simulation_preparator.prepare_provincial_iteration(
                self.current_iteration, parameters
            ):
                raise ValueError("Échec préparation des fichiers")
            
            # 2. Lancement des simulations
            if not self.simulation_manager.run_provincial_simulations(
                self.current_iteration
            ):
                raise ValueError("Échec des simulations")
            
            # 3. Traitement des résultats bruts
            if not self.results_manager.process_iteration_results(
                self.current_iteration
            ):
                raise ValueError("Échec traitement des résultats")
            
            # 4. Agrégation provinciale
            if not self.building_stock_aggregator.aggregate_provincial_results(
                self.current_iteration
            ):
                raise ValueError("Échec agrégation provinciale")
            
            # 5. Retourner les résultats pour validation
            return self.building_stock_aggregator.get_iteration_results(
                self.current_iteration
            )

        except Exception as e:
            self.logger.error(f"Erreur dans l'itération {self.current_iteration}: {str(e)}")
            return None
    
        
    def _get_campaign_performance(self) -> dict:
        """Calcule les métriques de performance de la campagne"""
        try:
            # Récupérer les statuts de toutes les simulations
            simulation_stats = self.simulation_manager.get_all_iterations_status()
            
            # Calculer métriques globales
            total_duration = sum(stat['duration'] for stat in simulation_stats.values())
            avg_success_rate = np.mean([stat['success_rate'] for stat in simulation_stats.values()])
            
            return {
                'total_duration': total_duration,
                'average_success_rate': float(avg_success_rate),
                'iterations_completed': len(simulation_stats),
                'simulation_details': simulation_stats
            }
            
        except Exception as e:
            self.logger.error(f"Erreur calcul performance : {str(e)}")
            return {}

    def _save_campaign_results(self, results: dict):
        """Sauvegarde les résultats de la campagne"""
        try:
            # Rapport principal
            report_file = self.campaign_dir / 'campaign_results.json'
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
            # Sauvegarder graphiques si disponibles
            
            self.logger.info(f"\nRésultats de campagne sauvegardés : {report_file}")
            
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde résultats : {str(e)}")

    def get_campaign_status(self) -> dict:
        """Retourne l'état actuel de la campagne"""
        try:
            status = {
                'campaign_id': self.current_campaign,
                'status': 'completed' if self.campaign_status['completed'] else
                        'running' if self.campaign_status['started'] else 'not_started',
                'current_iteration': self.params_optimizer.iteration,
                'best_score': float(self.params_optimizer.best_score),
                'best_params': self.campaign_status['best_params'],
                'optimization': self.params_optimizer.get_optimization_status()
            }
            return status
        except Exception as e:
            self.logger.error(f"Erreur récupération statut : {str(e)}")
            return None
        
    def _get_final_results(self) -> dict:
        """Prépare les résultats finaux de la campagne"""
        try:
            return {
                'campaign_id': self.current_campaign,
                'best_score': float(self.params_optimizer.best_score),
                'best_parameters': self.params_optimizer.best_params,
                'iterations_completed': self.current_iteration,
                'performance': self._get_campaign_performance()
            }
        except Exception as e:
            self.logger.error(f"Erreur préparation résultats : {str(e)}")
            return None
    
if __name__ == "__main__":
    print("\nTest du gestionnaire de calibration :")
    print("-" * 50)

    calibrator = CalibrationManager()
    
    # 1. Test d'initialisation
    print("\n1. Vérification de l'initialisation :")
    initial_status = calibrator.get_campaign_status()
    if initial_status:
        print(f"- ID Campagne : {initial_status['campaign_id']}")
        print(f"- Statut : {initial_status['status']}")
    
    # 2. Test de calibration avec paramètres réduits
    print("\n2. Test calibration courte (2 itérations) :")
    results = calibrator.run_calibration_campaign(
        max_iterations=2,  # Réduit pour le test
        convergence_threshold=0.01
    )
    
    if results:
        print("\nRésultats de la campagne :")
        print(f"- Meilleur score : {results['best_score']:.4f}")
        print("\nMeilleurs paramètres :")
        for param, value in results['best_parameters'].items():
            print(f"- {param}: {value:.2f}")
            
        print("\nPerformance :")
        perf = results['performance']
        print(f"- Durée totale : {perf['total_duration']:.1f} secondes")
        print(f"- Taux de succès moyen : {perf['average_success_rate']:.1f}%")
    
    # 3. Garder la visualisation ouverte
    calibrator.visualizer.keep_display_open()

    # 4. Vérifier l'état final
    print("\n4. État final de la campagne :")
    final_status = calibrator.get_campaign_status()
    if final_status:
        print(f"- Statut : {final_status['status']}")
        print(f"- Itérations effectuées : {final_status['current_iteration']}")
        print(f"- Meilleur score atteint : {final_status['best_score']:.4f}")