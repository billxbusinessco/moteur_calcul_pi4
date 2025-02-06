import sys
from pathlib import Path
import unittest
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.core.calibration_manager import CalibrationManager
from src.core.params_optimizer import ParamsOptimizer
from src.analysis.validation_system import ValidationSystem

class TestCalibration(unittest.TestCase):
    
    def setUp(self):
        self.calibrator = CalibrationManager()
        self.optimizer = ParamsOptimizer()
        self.validator = ValidationSystem()

    def test_single_iteration(self):
        """Test une seule itération de calibration"""
        # 1. Charger données Hydro-Q
        self.assertTrue(
            self.validator.load_hydro_quebec_data(2022),
            "Échec chargement données Hydro-Québec"
        )
        
        # 2. Test paramètres
        params = self.optimizer.suggest_parameters()
        self.assertIsNotNone(params, "Échec suggestion paramètres")
        
        # 3. Test simulation
        results = self.calibrator._run_iteration(params)
        self.assertIsNotNone(results, "Échec simulation")
        
        # 4. Test validation
        self.validator.simulation_results = results
        score = self.validator.calculate_objective_function()
        self.assertIsInstance(score, float, "Score invalide")

if __name__ == '__main__':
    unittest.main()