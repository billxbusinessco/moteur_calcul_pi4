import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys
import json
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, RESULTS_DIR, get_iteration_dirs  # Ajout de l'import ici

class ValidationSystem:
    def __init__(self):
        self.logger = self._setup_logger()
        self.results_dir = RESULTS_DIR / 'validation_results'
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.hydro_data = None
        self.simulation_results = None
        
    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('ValidationSystem')

    def load_hydro_quebec_data(self, year: int = 2022) -> bool:
        try:
            file_path = DATA_FILES['HYDRO_QUEBEC_FILES'][year]
            df = pd.read_csv(file_path)
            
            # Convertir temps
            df['Intervalle15Minutes'] = pd.to_datetime(df['Intervalle15Minutes'])
            df.set_index('Intervalle15Minutes', inplace=True)
            
            # Agréger en horaire
            hourly = df['energie_sum_secteur'].resample('h').mean()
            
            # Créer un index générique
            hourly.index = pd.date_range(start='2000-01-01', periods=len(hourly), freq='h')
            
            self.hydro_data = hourly
            
            # Log des statistiques
            self.logger.info("\nStatistiques Hydro-Québec :")
            self.logger.info(f"- Min : {hourly.min():.2f} kWh")
            self.logger.info(f"- Max : {hourly.max():.2f} kWh")
            self.logger.info(f"- Moyenne : {hourly.mean():.2f} kWh")
            self.logger.info(f"- Total annuel : {hourly.sum():.2f} kWh")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur chargement Hydro-Q: {str(e)}")
            return False

    def load_simulation_results(self, iteration: int) -> bool:
        """
        Charge les résultats de simulation pour une itération donnée
        
        Args:
            iteration: Numéro de l'itération à charger
        Returns:
            bool: True si chargement réussi, False sinon
        """
        try:
            # Utiliser les chemins centralisés
            paths = get_iteration_dirs(iteration)
            provincial_file = paths['provincial_file']
            
            if not provincial_file.exists():
                raise FileNotFoundError(f"Résultats non trouvés : {provincial_file}")
            
            df = pd.read_csv(provincial_file)
            
            # Convertir temps
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Créer un index générique (comme Hydro-Q)
            df.index = pd.date_range(start='2000-01-01', periods=len(df), freq='h')
            
            self.simulation_results = df['total_electricity'] 
            
            # Log des statistiques
            self.logger.info("\nStatistiques Simulation :")
            self.logger.info(f"- Min : {self.simulation_results.min():.2f} kWh")
            self.logger.info(f"- Max : {self.simulation_results.max():.2f} kWh")
            self.logger.info(f"- Moyenne : {self.simulation_results.mean():.2f} kWh")
            self.logger.info(f"- Total annuel : {self.simulation_results.sum():.2f} kWh")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Erreur chargement simulation: {str(e)}")
            return False
            
    def calculate_metrics(self, year: int = 2022) -> dict:
        try:
            if self.hydro_data is None or self.simulation_results is None:
                raise ValueError("Données manquantes")
            
            # Normalisation des séries (0-1)
            hydro_norm = (self.hydro_data - self.hydro_data.min()) / (self.hydro_data.max() - self.hydro_data.min())
            sim_norm = (self.simulation_results - self.simulation_results.min()) / (self.simulation_results.max() - self.simulation_results.min())
            
            # Métriques sur données brutes
            metrics_raw = {
                'rmse': float(np.sqrt(((self.hydro_data - self.simulation_results) ** 2).mean())),
                'ratio_means': float(self.simulation_results.mean() / self.hydro_data.mean())
            }
            
            # Métriques sur données normalisées
            metrics_norm = {
                'rmse_norm': float(np.sqrt(((hydro_norm - sim_norm) ** 2).mean())),
                'r2_norm': float(np.corrcoef(hydro_norm, sim_norm)[0,1]**2)
            }
            
            # Log des résultats
            self.logger.info("\nMétriques brutes :")
            self.logger.info(f"- RMSE : {metrics_raw['rmse']:.2f} kWh")
            self.logger.info(f"- Ratio moyennes : {metrics_raw['ratio_means']:.6f}")
            
            self.logger.info("\nMétriques normalisées (0-1) :")
            self.logger.info(f"- RMSE : {metrics_norm['rmse_norm']:.3f}")
            self.logger.info(f"- R² : {metrics_norm['r2_norm']:.3f}")
            
            return {**metrics_raw, **metrics_norm}

        except Exception as e:
            self.logger.error(f"Erreur calcul métriques : {str(e)}")
            return None
        
    def calculate_objective_function(self, metrics: dict = None) -> float:
        """
        Calcule un score objectif unique à partir des métriques
        Plus le score est bas, meilleur est le résultat
        """
        try:
            # Si metrics non fourni, calculer les métriques
            if metrics is None:
                metrics = self.calculate_metrics()
            
            if metrics is None:
                raise ValueError("Impossible de calculer les métriques")
                
            # Extraire les composantes avec les bonnes clés
            rmse_component = metrics['rmse'] / 1e6  # Normalisation du RMSE
            ratio_component = abs(metrics['ratio_means'] - 1)  # Écart au ratio idéal
            rmse_norm_component = metrics['rmse_norm']  # RMSE normalisé (déjà entre 0-1)

            # Score composite pondéré
            score = (
                0.4 * rmse_component +      # RMSE normalisé (40%)
                0.3 * ratio_component +     # Écart au ratio idéal (30%)
                0.3 * rmse_norm_component   # RMSE normalisé 0-1 (30%)
            )
            
            # Log détaillé
            self.logger.info("\nCalcul du score objectif :")
            self.logger.info(f"- Composante RMSE : {rmse_component:.4f}")
            self.logger.info(f"- Composante ratio : {ratio_component:.4f}")
            self.logger.info(f"- Composante RMSE norm : {rmse_norm_component:.4f}")
            self.logger.info(f"Score final : {score:.4f}")
            
            return score

        except Exception as e:
            self.logger.error(f"Erreur calcul score objectif : {str(e)}")
            return float('inf')
        
    def get_latest_score(self) -> float:
        """
        Retourne le dernier score calculé
        Returns:
            float: Dernier score calculé ou inf si erreur
        """
        if self.simulation_results is None:
            self.logger.warning("Pas de résultats de simulation chargés")
            return float('inf')

        try:
            metrics = self.calculate_metrics()
            if metrics is None:
                raise ValueError("Impossible de calculer les métriques")
                
            score = self.calculate_objective_function(metrics)
            
            # Sauvegarder les résultats
            validation_results = {
                'timestamp': datetime.now().isoformat(),
                'score': float(score),
                'metrics': metrics,
                'status': 'success'
            }
            
            # Créer dossier si nécessaire
            validation_file = self.results_dir / 'latest_validation.json'
            with open(validation_file, 'w') as f:
                json.dump(validation_results, f, indent=2)
                
            return score

        except Exception as e:
            self.logger.error(f"Erreur calcul score : {str(e)}")
            return float('inf')

    def get_validation_history(self) -> dict:
        """
        Retourne l'historique des validations
        """
        try:
            history_file = self.results_dir / 'validation_history.json'
            if history_file.exists():
                with open(history_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Erreur lecture historique : {str(e)}")
            return {}
    
if __name__ == "__main__":
    validator = ValidationSystem()
    
    print("\nTest du système de validation :")
    print("-" * 50)
    
    # 1. Test chargement données
    if validator.load_hydro_quebec_data(2022):
        print("✓ Données Hydro-Québec chargées")
        
        # 2. Test chargement simulation (itération 0)
        if validator.load_simulation_results(iteration=0):
            print("✓ Résultats simulation chargés")
            
            # 3. Test calcul score
            latest_score = validator.get_latest_score()
            print(f"\nDernier score calculé : {latest_score:.4f}")
            
            # 4. Test historique
            history = validator.get_validation_history()
            if history:
                print("\nHistorique des validations :")
                for timestamp, data in history.items():
                    print(f"- {timestamp}: {data['score']:.4f}")