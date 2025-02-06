import logging
from pathlib import Path
import sys
import json
from datetime import datetime
import numpy as np
import pandas as pd
import shutil  # Ajout de cet import

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR, RESULTS_STRUCTURE
# from src.core.params_optimizer import ParamsOptimizer
from src.preprocessing.simulation_preparator import SimulationPreparator
from src.simulation.simulation_manager import SimulationManager
from src.simulation.results_manager import ResultsManager 
from src.analysis.building_stock_aggregator import BuildingStockAggregator
from src.analysis.validation_system import ValidationSystem
from src.visualization.calibration_visualizer import CalibrationVisualizer
from src.core.bayesian_optimizer import BayesianOptimizer
from src.analysis.sensitivity_analyzer import SensitivityAnalyzer

class CalibrationManager:
    """Gestionnaire principal de la calibration"""
    def __init__(self):
        self.logger = self._setup_logger()
        
        # Composants principaux
        # self.params_optimizer = ParamsOptimizer()
        self.simulation_preparator = SimulationPreparator()
        self.simulation_manager = SimulationManager()
        self.results_manager = ResultsManager()
        self.building_stock_aggregator = BuildingStockAggregator()
        self.validation_system = ValidationSystem()
        self.visualizer = CalibrationVisualizer()
        self.optimizer = BayesianOptimizer()
        self.sensitivity_analyzer = SensitivityAnalyzer()
        
        # État de la calibration
        self.current_campaign = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.campaign_dir = RESULTS_STRUCTURE['CALIBRATION_DIR'] / f'campaign_{self.current_campaign}'
        self.campaign_dir.mkdir(parents=True, exist_ok=True)
        
        # Statut de la campagne
        self.campaign_status = {
            'started': False,
            'completed': False,
            'current_iteration': 0,
            'best_score': float('inf'),
            'best_params': None
        }
        self.current_iteration = 0
        self._clean_results_directories()

    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('CalibrationManager')

    def run_calibration_campaign(self, max_iterations=20, convergence_threshold=0.01) -> dict:
        try:
            self.logger.info(f"\nDémarrage campagne de calibration : {self.current_campaign}")
            self.campaign_status['started'] = True
            
            # Charger données Hydro-Québec
            if not self.validation_system.load_hydro_quebec_data(2022):
                raise ValueError("Impossible de charger les données Hydro-Québec")
                
            # Initialiser visualiseur avec les paramètres à optimiser
            self.visualizer.setup_display(list(self.optimizer.parameters.keys()))
            
            while (not self.optimizer.check_convergence() and self.current_iteration < max_iterations):
                try:
                    # 1. Suggérer nouveaux paramètres
                    current_params = self.optimizer.suggest_parameters()
                    if current_params is None:
                        raise ValueError("Pas de paramètres suggérés")

                    # 2. Lancer simulation complète
                    simulation_results = self._run_iteration(current_params)
                    if simulation_results is None:
                        self.current_iteration += 1
                        continue

                    # 3. Valider résultats
                    if not self.validation_system.load_simulation_results(self.current_iteration):
                        self.logger.error(f"Échec chargement résultats simulation {self.current_iteration}")
                        self.current_iteration += 1
                        continue

                    # 4. Calculer score et métriques
                    score = self.validation_system.calculate_objective_function()
                    metrics = self.validation_system.calculate_metrics()

                    # 5. Enregistrer pour analyse de sensibilité
                    self.sensitivity_analyzer.record_iteration(current_params, score, metrics)

                    # 6. Mettre à jour optimiseur
                    self.optimizer.update(current_params, score)

                    # 7. Préparer données visualisation
                    viz_data = {
                        'iteration': self.current_iteration,
                        'score': score,
                        'parameters': current_params,
                        'metrics': metrics,
                        'comparison': {
                            'hydro': self.validation_system.hydro_data,
                            'simulation': simulation_results['total_electricity']
                            if isinstance(simulation_results, pd.DataFrame)
                            else simulation_results
                        },
                        'sensitivity': self.sensitivity_analyzer.get_parameter_rankings()
                    }

                    # 8. Mettre à jour visualisation
                    self.visualizer.update(viz_data)
                    self._save_campaign_results(self.current_iteration, viz_data, score)

                    self.current_iteration += 1

                except Exception as e:
                    self.logger.error(f"Erreur dans l'itération {self.current_iteration}: {str(e)}")
                    self.current_iteration += 1
                    continue

            # Finaliser et retourner résultats
            return self._get_final_results()

        except Exception as e:
            self.logger.error(f"Erreur lors de la calibration : {str(e)}")
            return None

    def _run_iteration(self, parameters: dict):
        """Exécute une itération complète de simulation"""
        try:
            # 1. Préparation fichiers
            if not self.simulation_preparator.prepare_provincial_iteration(self.current_iteration, parameters):
                raise ValueError("Échec préparation des fichiers")
            
            # 2. Lancement simulations
            if not self.simulation_manager.run_provincial_simulations(self.current_iteration):
                raise ValueError("Échec des simulations")
            
            # 3. Traitement résultats
            if not self.results_manager.process_iteration_results(self.current_iteration):
                raise ValueError("Échec traitement des résultats")
            
            # 4. Agrégation provinciale
            if not self.building_stock_aggregator.aggregate_provincial_results(self.current_iteration):
                raise ValueError("Échec agrégation provinciale")
            
            # 5. Retourner résultats
            return self.building_stock_aggregator.get_iteration_results(self.current_iteration)

        except Exception as e:
            self.logger.error(f"Erreur dans l'itération {self.current_iteration}: {str(e)}")
            return None

    def _save_campaign_results(self, iteration: int, viz_data: dict, score: float):
        """Sauvegarde enrichie des résultats d'une itération"""
        try:
            # Créer dossier itération
            iter_dir = self.campaign_dir / f'iteration_{iteration}'
            iter_dir.mkdir(parents=True, exist_ok=True)
            
            # Sauvegarder données enrichies
            iteration_data = {
                'iteration': iteration,
                'parameters': viz_data['parameters'],
                'score': score,
                'metrics': viz_data.get('metrics', {}),
                'sensitivity': viz_data.get('sensitivity', {}),
                'timestamp': datetime.now().isoformat()
            }
            
            # Sauvegarder JSON et visualisations
            with open(iter_dir / 'iteration_results.json', 'w') as f:
                json.dump(iteration_data, f, indent=2)
            
            # Sauvegarder analyse de sensibilité
            self.sensitivity_analyzer.save_analysis(
                output_dir=iter_dir,
                prefix=f'iteration_{iteration}'
            )
                    
            self.visualizer.save_results(
                output_dir=iter_dir,
                prefix=f'iteration_{iteration}'
            )
            
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde résultats itération : {str(e)}")

    def _get_final_results(self) -> dict:
        try:
            # Si nous avons des observations
            if len(self.optimizer.X) > 0:
                best_idx = np.argmin(self.optimizer.y)
                best_params = {
                    name: self.optimizer.X[best_idx][i] 
                    for i, name in enumerate(self.optimizer.parameters.keys())
                }
            else:
                best_params = None

            return {
                'campaign_id': self.current_campaign,
                'best_score': float(min(self.optimizer.y)) if len(self.optimizer.y) > 0 else float('inf'),
                'best_parameters': best_params,
                'iterations_completed': self.current_iteration,
                'performance': self._get_campaign_performance()
            }
        except Exception as e:
            self.logger.error(f"Erreur préparation résultats finaux : {str(e)}")
            return None
        
    def _get_campaign_performance(self) -> dict:
        """Calcule les métriques de performance"""
        try:
            simulation_stats = self.simulation_manager.get_all_iterations_status()
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
        
    def _clean_results_directories(self):
        """Nettoie les dossiers de résultats avant une nouvelle campagne"""
        try:
            # Dossiers à nettoyer
            dirs_to_clean = [
                RESULTS_STRUCTURE['SIMULATIONS_DIR'],
                RESULTS_STRUCTURE['PROCESSED_DIR'],
                RESULTS_STRUCTURE['PROVINCIAL_DIR']
            ]
            
            for dir_path in dirs_to_clean:
                if dir_path.exists():
                    self.logger.info(f"Nettoyage du dossier : {dir_path}")
                    for item in dir_path.iterdir():
                        if item.name.startswith('iteration_'):
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                                
        except Exception as e:
            self.logger.warning(f"Erreur lors du nettoyage des dossiers : {str(e)}")

if __name__ == "__main__":
    print("\nTest du gestionnaire de calibration")
    print("-" * 50)

    calibrator = CalibrationManager()
    results = calibrator.run_calibration_campaign(
        max_iterations=2,
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
        print(f"- Taux de succès : {perf['average_success_rate']:.1f}%")