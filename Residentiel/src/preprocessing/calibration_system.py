import logging
from pathlib import Path
import sys
import json
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR, RESULTS_DIR
from src.preprocessing.params_optimizer import ParamsOptimizer
from src.preprocessing.simulation_preparator import SimulationPreparator
from src.analysis.validation_system import ValidationSystem
from src.simulation.simulation_manager import SimulationManager

class CalibrationSystem:
    def __init__(self):
        """Initialise le système de calibration complet"""
        self.logger = self._setup_logger()
        self.optimizer = ParamsOptimizer()
        self.preparator = SimulationPreparator()
        self.validator = ValidationSystem()
        self.simulation_manager = SimulationManager()
        
        # État de calibration
        self.current_iteration = 0
        self.results_dir = RESULTS_DIR / 'calibration'
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('CalibrationSystem')

    def run_calibration(self, zone: float, max_iterations: int = 20) -> dict:
        """
        Lance le processus complet de calibration pour une zone
        """
        try:
            def objective_function(params: dict) -> float:
                # 1. Préparer simulation avec nouveaux paramètres
                if not self.preparator.prepare_iteration(self.current_iteration, params):
                    raise Exception("Échec préparation simulation")
                
                # 2. Lancer simulation
                if not self.simulation_manager.run_simulations(zone=zone):
                    raise Exception("Échec simulation")
                
                # 3. Charger et valider résultats
                if not self.validator.load_simulation_results(zone=zone):
                    raise Exception("Échec chargement résultats")
                
                metrics = self.validator.calculate_metrics()
                if not metrics:
                    raise Exception("Échec calcul métriques")
                
                # 4. Calculer score
                score = self.validator.calculate_objective_function(metrics)
                
                self.current_iteration += 1
                return score

            # Lancer optimisation
            best_params = self.optimizer.optimize(
                objective_function=objective_function,
                max_iterations=max_iterations
            )

            return best_params

        except Exception as e:
            self.logger.error(f"Erreur lors de la calibration : {str(e)}")
            return None

if __name__ == "__main__":
    calibrator = CalibrationSystem()
    
    print("\nTest du système de calibration :")
    print("-" * 50)
    
    # Tester sur zone 448.0
    zone = 448.0
    best_params = calibrator.run_calibration(zone, max_iterations=10)
    
    if best_params:
        print("\nMeilleurs paramètres trouvés :")
        for param, value in best_params.items():
            print(f"- {param}: {value:.2f}")