# src/core/bayesian_optimizer.py

from dataclasses import dataclass
from typing import Tuple, Optional, Callable
import numpy as np
from scipy.stats import norm, beta, gamma
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern

@dataclass
class Parameter:
    """Paramètre à optimiser avec métadonnées enrichies"""
    name: str
    range: Tuple[float, float]
    prior_mean: float
    prior_std: float
    hpxml_path: str
    transform: Optional[Callable] = None
    description: str = ""  # Description du paramètre
    unit: str = ""        # Unité de mesure
    
    def sample(self) -> float:
        """Échantillonne une valeur selon le prior"""
        value = np.random.normal(self.prior_mean, self.prior_std)
        return np.clip(value, self.range[0], self.range[1])

class BayesianOptimizer:
    """Optimiseur utilisant Gaussian Process"""
    def __init__(self):
        self.parameters = {
            'heating_system_efficiency': Parameter(
                name='heating_system_efficiency',
                range=(0.90, 0.95),        # Réduit (anciennement 0.85, 0.95)
                prior_mean=0.92,           # Ajusté au centre du nouvel intervalle
                prior_std=0.01,            # Réduit pour plus de précision
                hpxml_path='heating_system.heating_efficiency',
                description="Efficacité système chauffage",
                unit="fraction"
            ),
            'air_leakage_value': Parameter(
                name='air_leakage_value',
                range=(3.0, 4.0),          # Réduit (anciennement 3, 7)
                prior_mean=3.5,
                prior_std=0.2,             # Réduit pour plus de précision
                hpxml_path='air_leakage_value',
                description="Taux d'infiltration",
                unit="ACH@50Pa"
            ),
            # Les autres paramètres restent inchangés pour l'instant
            'heating_setpoint': Parameter(
                name='heating_setpoint',
                range=(19, 21),
                prior_mean=20,
                prior_std=0.5,
                hpxml_path='hvac_control.heating_setpoint'
            ),
            'cooling_setpoint': Parameter(
                name='cooling_setpoint',
                range=(24, 26),
                prior_mean=25,
                prior_std=0.5,
                hpxml_path='hvac_control.cooling_setpoint'
            ),
            'wall_assembly_r': Parameter(
                name='wall_assembly_r',
                range=(2.5, 4.5),
                prior_mean=3.5,
                prior_std=0.3,
                hpxml_path='wall_assembly_r'
            )
        }
        # Initialisation du GP
        self.kernel = Matern(nu=2.5)
        self.gp = GaussianProcessRegressor(
            kernel=self.kernel,
            n_restarts_optimizer=10,
            random_state=42
        )
        
        # Historique des observations
        self.X = []  # Points évalués
        self.y = []  # Scores observés

    def suggest_parameters(self) -> dict:
        """Suggère le prochain point à évaluer en utilisant Expected Improvement"""
        if len(self.X) < 3:  # Phase d'exploration initiale
            return {
                name: param.sample() 
                for name, param in self.parameters.items()
            }
        
        try:
            # Créer grille de recherche
            param_space = self._create_parameter_grid()
            
            # Prédictions GP
            mu, sigma = self.gp.predict(param_space, return_std=True)
            
            # Calculer Expected Improvement
            best_f = min(self.y)  # Minimisation du score
            improvement = best_f - mu
            z = improvement / (sigma + 1e-9)
            ei = improvement * norm.cdf(z) + sigma * norm.pdf(z)
            
            # Sélectionner meilleur point
            best_idx = np.argmax(ei)
            
            # Convertir en dictionnaire de paramètres
            return {
                name: param_space[best_idx, i]
                for i, name in enumerate(self.parameters.keys())
            }
            
        except Exception as e:
            print(f"Erreur suggestion paramètres : {str(e)}")
            return self._random_sample()
    
    def update(self, parameters: dict, score: float):
        """Met à jour le GP avec une nouvelle observation"""
        # Convertir paramètres en point X
        x = np.array([[parameters[name] for name in self.parameters.keys()]])
        
        # Ajouter à l'historique
        self.X.append(x[0])
        self.y.append(score)
        
        # Réentraîner le GP
        if len(self.X) > 2:  # Au moins 3 points pour le GP
            X = np.vstack(self.X)
            y = np.array(self.y)
            self.gp.fit(X, y)
    
    def check_convergence(self) -> bool:
        """Vérifie si l'optimisation a convergé"""
        if len(self.X) < 5:
            return False
                
        # Vérifier variation du score sur les 3 dernières itérations
        recent_scores = self.y[-3:]
        score_std = np.std(recent_scores)
        
        # Vérifier stabilité des paramètres
        recent_params = self.X[-3:]
        param_stds = np.std(recent_params, axis=0)
        params_stable = all(std < 0.01 for std in param_stds)
        
        # Vérifier si le meilleur score s'améliore encore
        best_score_improving = min(recent_scores) < min(self.y[:-3]) if len(self.y) > 3 else True
        
        return score_std < 0.01 and params_stable and not best_score_improving
    
    def _create_parameter_grid(self, n_points=1000) -> np.ndarray:
        """Crée une grille de points pour la recherche"""
        param_ranges = [param.range for param in self.parameters.values()]
        
        # Créer grille latin hypercube
        from scipy.stats import qmc
        sampler = qmc.LatinHypercube(d=len(param_ranges))
        grid = sampler.random(n=n_points)
        
        # Mettre à l'échelle dans les ranges
        for i, (low, high) in enumerate(param_ranges):
            grid[:, i] = grid[:, i] * (high - low) + low
            
        return grid
    
    def _random_sample(self) -> dict:
        """Échantillonnage aléatoire des paramètres"""
        return {
            name: param.sample()
            for name, param in self.parameters.items()
        }