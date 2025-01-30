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
    
    def optimize_with_validation(
        self,
        simulation_preparator,
        simulation_manager,
        results_manager,           # Ajout du ResultsManager
        building_stock_aggregator,
        validation_system,
        max_iterations=20
    ) -> dict:
        """
        Optimise les paramètres en utilisant la chaîne complète
        
        Args:
            simulation_preparator: Prépare les fichiers H2K
            simulation_manager: Lance les simulations
            results_manager: Traite les résultats bruts
            building_stock_aggregator: Agrège au niveau provincial
            validation_system: Calcule le score objectif
        """
        def calibration_objective(params: dict) -> float:
            try:
                # 1. Préparation des fichiers
                if not simulation_preparator.prepare_provincial_iteration(self.iteration, params):
                    return float('inf')
                
                # 2. Lancement des simulations
                if not simulation_manager.run_provincial_simulations(self.iteration):
                    return float('inf')
                
                # 3. Traitement des résultats bruts
                if not results_manager.process_iteration_results(self.iteration):
                    return float('inf')
                    
                # 4. Agrégation provinciale
                if not building_stock_aggregator.aggregate_provincial_results(self.iteration):
                    return float('inf')
                
                # 5. Validation et score
                if not validation_system.load_simulation_results(self.iteration):
                    return float('inf')
                
                score = validation_system.calculate_objective_function()
                
                # Log détaillé
                self.logger.info("\nRésultats de l'itération :")
                self.logger.info(f"- Score calculé : {score:.4f}")
                self.logger.info(f"- Paramètres testés :")
                for name, value in params.items():
                    self.logger.info(f"  * {name}: {value:.2f}")
                
                return score
                
            except Exception as e:
                self.logger.error(f"Erreur dans l'objectif de calibration : {str(e)}")
                return float('inf')
        
        return self.optimize(calibration_objective, max_iterations)

    def optimize(self, objective_function, max_iterations=20) -> dict:
        """Lance l'optimisation complète"""
        try:
            self.logger.info(f"Démarrage optimisation (max {max_iterations} itérations)")
            
            for i in range(max_iterations):
                # 1. Suggérer paramètres
                params = self.suggest_parameters()
                if not params:
                    break
                
                # 2. Évaluer
                score = objective_function(params)
                
                # 3. Mettre à jour
                self.update(params, score)
                
                # 4. Vérifier convergence
                if self.check_convergence():
                    self.logger.info(f"Convergence atteinte à l'itération {i}")
                    break
                    
                # 5. Log progression
                self.logger.info(f"Itération {i}: score = {score:.4f}")
            
            return self.best_params
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'optimisation : {str(e)}")
            return None
    
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
        """
        Met à jour l'optimiseur avec les résultats d'une itération
        """
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
                self.logger.info(f"Pas d'amélioration depuis {self.no_improvement_count} itérations")
            
            # Sauvegarder l'historique
            self._save_history()
            
            self.iteration += 1
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour : {str(e)}")

    def _save_history(self):
        """Sauvegarde l'historique d'optimisation"""
        output_file = self.results_dir / 'optimization_history.json'
        history = {
            'parameters': self.parameters,
            'observations': self.observations,
            'best_score': self.best_score,
            'best_params': self.best_params,
            'convergence_count': self.convergence_count,
            'no_improvement_count': self.no_improvement_count
        }
        with open(output_file, 'w') as f:
            json.dump(history, f, indent=2)

    def check_convergence(self) -> bool:
        """Vérifie si l'optimisation a convergé"""
        if len(self.observations) < 3:
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
    
    def get_optimization_status(self) -> dict:
        """
        Retourne l'état actuel de l'optimisation
        Returns:
            dict: État détaillé de l'optimisation
        """
        try:
            status = {
                'current_iteration': self.iteration,
                'best_score': float(self.best_score),
                'best_params': self.best_params,
                'convergence': {
                    'count': self.convergence_count,
                    'no_improvement_count': self.no_improvement_count,
                    'is_converged': self.check_convergence()
                },
                'history': [
                    {
                        'iteration': obs['iteration'],
                        'score': float(obs['score']),
                        'parameters': obs['parameters'],
                        'timestamp': obs['timestamp']
                    }
                    for obs in self.observations
                ],
                'current_state': {
                    'exploration_rate': min(0.5, 1.0 / (1.0 + self.iteration)),
                    'thresholds': self.calibration_thresholds
                }
            }
            
            # Log du statut
            self.logger.info("\nStatut de l'optimisation :")
            self.logger.info(f"- Itération courante : {self.iteration}")
            self.logger.info(f"- Meilleur score : {self.best_score:.4f}")
            if self.best_params:
                self.logger.info("- Meilleurs paramètres :")
                for param, value in self.best_params.items():
                    self.logger.info(f"  * {param}: {value:.2f}")
            self.logger.info(f"- Convergence : {'Oui' if status['convergence']['is_converged'] else 'Non'}")
            
            return status
            
        except Exception as e:
            self.logger.error(f"Erreur récupération statut : {str(e)}")
            return None
    

if __name__ == "__main__":
    print("\nTest de l'optimiseur de paramètres :")
    print("-" * 50)
    
    # 1. Test avec fonction simple
    optimizer = ParamsOptimizer()
    def objective(params):
        return np.sqrt(
            (params['heating_setpoint'] - 21)**2 + 
            (params['cooling_setpoint'] - 25)**2
        )
    
    print("\n1. Test optimisation simple...")
    best_params = optimizer.optimize(objective, max_iterations=5)
    
    # 2. Test du statut
    print("\n2. Vérification du statut d'optimisation :")
    status = optimizer.get_optimization_status()
    if status:
        print("\nRésumé de l'optimisation :")
        print(f"- Itérations effectuées : {status['current_iteration']}")
        print(f"- Meilleur score : {status['best_score']:.4f}")
        print("\nHistorique des scores :")
        for obs in status['history']:
            print(f"- Itération {obs['iteration']}: {obs['score']:.4f}")
        print(f"\nConvergence : {'Atteinte' if status['convergence']['is_converged'] else 'Non atteinte'}")
        
        # 3. Test sauvegarde historique
        history_file = optimizer.results_dir / 'optimization_history.json'
        if history_file.exists():
            print("\n3. Historique sauvegardé avec succès")