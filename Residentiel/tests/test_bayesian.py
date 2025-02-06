import sys
from pathlib import Path
import unittest
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root)) 


from src.core.bayesian_optimizer import BayesianOptimizer


def test_optimization_loop():
    optimizer = BayesianOptimizer()
    
    # Fonction test (paraboloïde)
    def test_function(params):
        x1 = (params['heating_setpoint'] - 20) / 2
        x2 = (params['cooling_setpoint'] - 25) / 2
        x3 = (params['heating_system_efficiency'] - 0.9) / 0.1
        return x1**2 + x2**2 + x3**2
    
    print("\nTest d'optimisation :")
    print("-" * 50)
    
    for i in range(10):
        # Suggérer paramètres
        params = optimizer.suggest_parameters()
        
        # Évaluer
        score = test_function(params)
        
        # Mettre à jour
        optimizer.update(params, score)
        
        print(f"\nItération {i+1}:")
        print(f"Paramètres : {params}")
        print(f"Score : {score:.4f}")
        
        if optimizer.check_convergence():
            print("\nConvergence atteinte!")
            break

if __name__ == '__main__':
    test_optimization_loop()