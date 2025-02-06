import sys
import unittest
import pandas as pd
import logging
from pathlib import Path
import matplotlib.pyplot as plt

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root)) 

from src.core.calibration_manager import CalibrationManager
import matplotlib.pyplot as plt

def test_bayesian_calibration():
    print("\nTest de la calibration bayésienne")
    print("-" * 50)

    try:
        # Configuration du logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Initialisation
        calibrator = CalibrationManager()
        
        # Lancer la calibration
        results = calibrator.run_calibration_campaign(
            max_iterations=40,  # 20 itérations pour une bonne convergence
            convergence_threshold=0.01
        )
        
        # Afficher résultats si succès
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
        
        # Garder les figures ouvertes
        plt.show()
        
    except Exception as e:
        print(f"Erreur : {str(e)}")
        raise

if __name__ == "__main__":
    test_bayesian_calibration()