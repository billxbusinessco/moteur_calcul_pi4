import numpy as np
import logging
from pathlib import Path
import sys
import json
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR, RESULTS_DIR

class ParamsOptimizer:
    def __init__(self):
        """Initialise l'optimiseur de paramètres"""
        self.logger = self._setup_logger()
        self.iteration = 0
        self.observations = []
        self.results_dir = RESULTS_DIR / 'optimization_results'
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Définition des paramètres
        self.parameters = {
            'heating_setpoint': {
                'range': (18, 22),
                'initial': 21,
                'step': 0.5,
                'description': 'Point de consigne chauffage (°C)'
            },
            'cooling_setpoint': {
                'range': (23, 27),
                'initial': 25,
                'step': 0.5,
                'description': 'Point de consigne climatisation (°C)'
            }
        }
        
        # État de l'optimisation
        self.best_score = float('inf')
        self.best_params = None
        self.convergence_count = 0
        self.no_improvement_count = 0
        
        # Seuils de calibration et métriques
        self.calibration_thresholds = {
            'convergence': 0.01,        # Seuil de variation pour convergence
            'max_no_improvement': 10,   # Nombre max d'itérations sans amélioration
            'min_iterations': 3,        # Nombre minimum d'itérations avant convergence
            'exploration_decay': 0.5    # Taux de décroissance de l'exploration
        }

    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('ParamsOptimizer')

    def _explore(self) -> dict:
        """Stratégie d'exploration : recherche plus large"""
        params = {}
        for name, info in self.parameters.items():
            min_val, max_val = info['range']
            # Exploration gaussienne autour du meilleur point
            if self.best_params:
                current = self.best_params[name]
                std = (max_val - min_val) / 4  # Large écart-type
                value = np.random.normal(current, std)
                params[name] = max(min_val, min(max_val, value))
            else:
                # Première exploration : uniforme
                params[name] = np.random.uniform(min_val, max_val)
        return params
    
    def _exploit(self) -> dict:
        """Stratégie d'exploitation : recherche locale"""
        if not self.best_params:
            return {name: info['initial'] for name, info in self.parameters.items()}
        
        params = {}
        for name, info in self.parameters.items():
            current = self.best_params[name]
            min_val, max_val = info['range']
            
            # Réduction progressive du pas
            step = info['step'] * (0.5 ** (self.no_improvement_count // 3))
            
            # Changement local
            change = np.random.choice([-step, 0, step], p=[0.4, 0.2, 0.4])
            value = current + change
            params[name] = max(min_val, min(max_val, value))
        
        return params

    def suggest_parameters(self) -> dict:
        """Suggère les prochains paramètres à tester"""
        try:
            # Taux d'exploration dynamique
            exploration_rate = min(0.5, 1.0 / (1.0 + self.iteration))
            
            # Choisir stratégie
            if np.random.random() < exploration_rate:
                params = self._explore()
                self.logger.info("Mode: Exploration")
            else:
                params = self._exploit()
                self.logger.info("Mode: Exploitation")
            
            self.logger.info(f"Paramètres suggérés pour itération {self.iteration}:")
            for name, value in params.items():
                self.logger.info(f"- {name}: {value:.2f}")
            
            return params
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la suggestion des paramètres : {str(e)}")
            return None

    def update(self, parameters: dict, score: float):
        """Met à jour l'optimiseur avec les résultats d'une itération"""
        try:
            # Sauvegarder l'observation
            observation = {
                'iteration': self.iteration,
                'parameters': parameters,
                'score': score,
                'timestamp': datetime.now().isoformat()
            }
            self.observations.append(observation)
            
            # Mettre à jour le meilleur score
            if score < self.best_score:
                self.best_score = score
                self.best_params = parameters.copy()
                self.no_improvement_count = 0
                self.logger.info(f"Nouveau meilleur score : {score:.4f}")
            else:
                self.no_improvement_count += 1
            
            # Sauvegarder l'historique
            self._save_history()
            
            self.iteration += 1
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour : {str(e)}")

    def check_convergence(self) -> bool:
        """Vérifie si l'optimisation a convergé"""
        if len(self.observations) < self.calibration_thresholds['min_iterations']:
            return False
            
        # Vérifier la variation sur les 3 dernières itérations
        recent_scores = [obs['score'] for obs in self.observations[-3:]]
        variation = max(recent_scores) - min(recent_scores)
        
        if variation < self.calibration_thresholds['convergence']:
            self.convergence_count += 1
        else:
            self.convergence_count = 0
            
        return (self.convergence_count >= 3 or 
                self.no_improvement_count >= self.calibration_thresholds['max_no_improvement'])
    
    def _save_history(self):
        """Sauvegarde l'historique d'optimisation"""
        output_file = self.results_dir / 'optimization_history.json'
        history = {
            'parameters': self.parameters,
            'observations': self.observations,
            'best_score': float(self.best_score),
            'best_params': self.best_params,
            'convergence_count': self.convergence_count,
            'no_improvement_count': self.no_improvement_count,
            'timestamp': datetime.now().isoformat()
        }
        with open(output_file, 'w') as f:
            json.dump(history, f, indent=2)