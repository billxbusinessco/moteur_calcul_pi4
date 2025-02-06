import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys
import json
from datetime import datetime
import os

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, RESULTS_DIR, get_iteration_dirs, RESULTS_STRUCTURE

class ValidationSystem:
    """Système de validation des résultats de simulation avec données Hydro-Québec"""
    
    def __init__(self):
        self.logger = self._setup_logger()
        self.hydro_data = None
        self.simulation_results = None
        
    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('ValidationSystem')

    def load_hydro_quebec_data(self, year: int = 2022) -> bool:
        """Charge les données Hydro-Québec pour l'année spécifiée"""
        try:
            file_path = DATA_FILES['HYDRO_QUEBEC_FILES'][year]
            df = pd.read_csv(file_path)
            
            # Convertir temps
            df['Intervalle15Minutes'] = pd.to_datetime(df['Intervalle15Minutes'])
            df.set_index('Intervalle15Minutes', inplace=True)
            
            # Agréger les données en horaires (somme de la consommation uniquement)
            hourly = df['energie_sum_secteur'].resample('h').sum()
            
             # Créer un index générique
            hourly.index = pd.date_range(start='2000-01-01', periods=len(hourly), freq='h')
            
            self.hydro_data = hourly
            
            # Log des statistiques
            self.logger.info("\nStatistiques Hydro-Québec :")
            self.logger.info(f"- Min : {self.hydro_data.min():.2f} kWh")
            self.logger.info(f"- Max : {self.hydro_data.max():.2f} kWh")
            self.logger.info(f"- Moyenne : {self.hydro_data.mean():.2f} kWh")
            self.logger.info(f"- Total annuel : {self.hydro_data.sum():.2f} kWh")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur chargement Hydro-Q: {str(e)}")
            return False

    def load_simulation_results(self, iteration: int) -> bool:
        """Charge les résultats provinciaux d'une itération"""
        try:
            paths = get_iteration_dirs(iteration)
            results_file = paths['provincial_file']
            
            if not results_file.exists():
                raise FileNotFoundError(f"Résultats non trouvés : {results_file}")

            # Charger données
            df = pd.read_csv(results_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

            # Extraire la série total_electricity
            if 'total_electricity' in df.columns:
                self.simulation_results = df['total_electricity'].astype(float)
            else:
                # Si pas de total, sommer les composantes
                energy_cols = ['heating', 'cooling', 'dhw']
                self.simulation_results = df[energy_cols].sum(axis=1).astype(float)

            # Log statistiques
            self.logger.info("\nStatistiques Simulation :")
            self.logger.info(f"- Min : {self.simulation_results.min():.2f} kWh")
            self.logger.info(f"- Max : {self.simulation_results.max():.2f} kWh")
            self.logger.info(f"- Moyenne : {self.simulation_results.mean():.2f} kWh")
            self.logger.info(f"- Total annuel : {self.simulation_results.sum():.2f} kWh")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur chargement simulation: {str(e)}")
            return False

    def calculate_metrics(self) -> dict:
        """Calcule les métriques de validation"""
        try:
            if self.hydro_data is None or self.simulation_results is None:
                raise ValueError("Données manquantes")

            # 1. S'assurer que les données sont au bon format
            hydro_series = self.hydro_data.astype(float)
            
            # Extraire total_electricity des résultats de simulation
            if isinstance(self.simulation_results, pd.DataFrame):
                sim_series = self.simulation_results['total_electricity'].astype(float)
            else:
                sim_series = pd.Series(self.simulation_results).astype(float)

            # 2. Aligner les index des séries
            hydro_series.index = pd.date_range(start='2000-01-01', periods=len(hydro_series), freq='h')
            sim_series.index = pd.date_range(start='2000-01-01', periods=len(sim_series), freq='h')

            # 3. Calculer les métriques
            # Métriques brutes avec gestion explicite des NaN
            metrics_raw = {
                'rmse': float(np.sqrt(((hydro_series - sim_series) ** 2).mean())),
                'mae': float(np.abs(hydro_series - sim_series).mean()),
                'ratio_means': float(sim_series.mean() / hydro_series.mean())
            }

            # Métriques saisonnières avec gestion explicite des NaN
            winter_mask = hydro_series.index.month.isin([12, 1, 2])
            summer_mask = hydro_series.index.month.isin([6, 7, 8])
            
            winter_hydro = hydro_series[winter_mask].fillna(0)
            winter_sim = sim_series[winter_mask].fillna(0)
            summer_hydro = hydro_series[summer_mask].fillna(0)
            summer_sim = sim_series[summer_mask].fillna(0)
            
            winter_error = float(np.mean((winter_hydro - winter_sim)**2))
            summer_error = float(np.mean((summer_hydro - summer_sim)**2))
            
            metrics_seasonal = {
                'winter_mse': winter_error,
                'summer_mse': summer_error,
                'seasonal_bias': abs(winter_error - summer_error)
            }

            # Log des résultats
            self.logger.info("\nMétriques de validation :")
            self.logger.info(f"- RMSE : {metrics_raw['rmse']:.2f} kWh")
            self.logger.info(f"- MAE : {metrics_raw['mae']:.2f} kWh")
            self.logger.info(f"- Ratio moyennes : {metrics_raw['ratio_means']:.3f}")
            self.logger.info(f"- Biais saisonnier : {metrics_seasonal['seasonal_bias']:.2f}")
            
            return {**metrics_raw, **metrics_seasonal}

        except Exception as e:
            self.logger.error(f"Erreur calcul métriques : {str(e)}")
            return None

    def save_validation_results(self, iteration: int, metrics: dict) -> bool:
        """Sauvegarde les résultats de validation"""
        try:
            paths = get_iteration_dirs(iteration)
            validation_file = paths['validation_file']
            
            validation_results = {
                'iteration': iteration,
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics,
                'hydro_stats': {
                    'mean': float(self.hydro_data.mean()),
                    'std': float(self.hydro_data.std()),
                    'total': float(self.hydro_data.sum())
                },
                'simulation_stats': {
                    'mean': float(self.simulation_results.mean()),
                    'std': float(self.simulation_results.std()),
                    'total': float(self.simulation_results.sum())
                }
            }
            
            # S'assurer que le dossier existe
            validation_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(validation_file, 'w') as f:
                json.dump(validation_results, f, indent=2)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde validation : {str(e)}")
            return False

    def calculate_objective_function(self) -> float:
        """Calcule un score objectif unique pour la calibration"""
        try:
            metrics = self.calculate_metrics()
            if metrics is None:
                raise ValueError("Impossible de calculer les métriques")
                        
            # Normalisation plus robuste des composantes
            rmse_component = metrics['rmse'] / (self.hydro_data.mean() or 1.0)  # Normaliser par la moyenne
            ratio_component = abs(metrics['ratio_means'] - 1)  # Écart au ratio idéal
            seasonal_component = (metrics['seasonal_bias'] / 
                            ((self.hydro_data.max() - self.hydro_data.min()) ** 2 or 1.0))  # Normaliser par la variance max possible
            
            # Score composite pondéré avec meilleure mise à l'échelle
            # Augmenter le poids du ratio pour réduire la surestimation
            # Réduire le poids du biais saisonnier qui est très élevé
            score = (
                0.35 * rmse_component +      # RMSE normalisé (35%)
                0.45 * ratio_component +     # Ratio des moyennes (45%)
                0.20 * seasonal_component    # Biais saisonnier (20%)
            )
            
            # Log détaillé
            self.logger.info("\nCalcul du score objectif :")
            self.logger.info(f"- Composante RMSE : {rmse_component:.4f}")
            self.logger.info(f"- Composante ratio : {ratio_component:.4f}")
            self.logger.info(f"- Composante saisonnière : {seasonal_component:.4f}")
            self.logger.info(f"Score final : {score:.4f}")
            
            return score

        except Exception as e:
            self.logger.error(f"Erreur calcul score objectif : {str(e)}")
            return float('inf')
        
    def calculate_parameter_contributions(self, params: dict) -> dict:
        """Calcule la contribution de chaque paramètre au score final"""
        contributions = {}
        metrics = self.calculate_metrics()
        
        if metrics is None:
            return {}
            
        for param_name, param_value in params.items():
            # Calculer sensibilité locale
            param_contribution = self._calculate_parameter_sensitivity(
                param_name, param_value, metrics
            )
            contributions[param_name] = param_contribution
            
        return contributions