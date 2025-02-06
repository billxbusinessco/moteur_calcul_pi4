import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys
import json
from datetime import datetime
from typing import Optional

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import (
    DATA_FILES, 
    PROCESSED_DATA_DIR, 
    RESULTS_DIR, 
    get_iteration_dirs,
    RESULTS_STRUCTURE
)

class ResultsManager:
    """Gère le traitement des résultats de simulation OpenStudio"""
    
    def __init__(self):
        self.logger = self._setup_logger()
        
        # Colonnes à extraire des résultats OpenStudio
        self.column_mapping = {
            'total_electricity': 'Fuel Use: Electricity: Total',
            'heating': 'End Use: Electricity: Heating',
            'cooling': 'End Use: Electricity: Cooling',
            'dhw': 'End Use: Electricity: Hot Water'
        }
        
        # État du traitement
        self.current_iteration = 0

    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('ResultsManager')

    def process_iteration_results(self, iteration: int) -> bool:
        """Traite les résultats d'une itération complète"""
        try:
            self.current_iteration = iteration
            paths = get_iteration_dirs(iteration)
            
            # Créer les dossiers nécessaires
            paths['processed_dir'].mkdir(parents=True, exist_ok=True)
            
            # Traiter chaque archétype
            processed = 0
            errors = 0
            
            for arch_dir in paths['simulation_dir'].iterdir():
                if not arch_dir.is_dir() or arch_dir.name.startswith('_'):
                    continue
                    
                try:
                    # Chercher résultats
                    results_file = arch_dir / 'run' / 'results_timeseries.csv'
                    if not results_file.exists():
                        self.logger.warning(f"Fichier non trouvé : {results_file}")
                        continue

                    # Traiter les données
                    processed_data = self._process_results_file(results_file)
                    if processed_data is not None:
                        # Sauvegarder résultats traités
                        output_file = paths['processed_dir'] / f"{arch_dir.name}_processed.csv"
                        processed_data.to_csv(output_file)
                        # self.logger.info(f"Résultats sauvegardés : {output_file}")
                        processed += 1
                    
                except Exception as e:
                    self.logger.error(f"Erreur traitement {arch_dir.name}: {str(e)}")
                    errors += 1
                    continue

            # Sauvegarder métadonnées
            if processed > 0:
                metadata = {
                    'timestamp': datetime.now().isoformat(),
                    'iteration': iteration,
                    'processed': processed,
                    'errors': errors,
                    'success_rate': (processed / (processed + errors)) * 100 if (processed + errors) > 0 else 0,
                    'columns_processed': list(self.column_mapping.keys())
                }
                
                metadata_file = paths['processed_dir'] / 'processing_metadata.json'
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                self.logger.info(f"\nTraitement terminé:")
                self.logger.info(f"- Archétypes traités: {processed}")
                self.logger.info(f"- Erreurs: {errors}")
                
            return processed > 0

        except Exception as e:
            self.logger.error(f"Erreur traitement itération {iteration}: {str(e)}")
            return False

    def _process_results_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Traite un fichier de résultats OpenStudio"""
        try:
            # 1. Lecture avec gestion explicite des types
            df = pd.read_csv(file_path, low_memory=False)
            
            # 2. Nettoyer et extraire les données numériques (après la ligne d'unités)
            result_df = pd.DataFrame()
            
            # Traitement du temps
            result_df.index = pd.to_datetime(df['Time'].values[1:])
            result_df.index.name = 'timestamp'
            
            # Traitement des colonnes d'énergie
            for our_col, os_col in self.column_mapping.items():
                if os_col in df.columns:
                    # Extraction et nettoyage des valeurs
                    values = df[os_col].values[1:]  # Ignorer ligne d'unités
                    numerical_values = []
                    
                    for val in values:
                        try:
                            clean_val = str(val).strip().replace(',', '.')
                            num_val = float(clean_val)
                            numerical_values.append(num_val)
                        except (ValueError, TypeError):
                            numerical_values.append(0.0)
                    
                    result_df[our_col] = numerical_values
            
                else:
                    # self.logger.warning(f"Colonne manquante : {os_col}")
                    result_df[our_col] = 0.0
            
            # 3. Validation du nombre d'heures
            if len(result_df) != 8760:
                self.logger.warning(f"Ajustement nombre d'heures : {len(result_df)} -> 8760")
                result_df = self._adjust_hours(result_df)
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Erreur traitement fichier {file_path.name}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _log_column_statistics(self, values: list, column_name: str):
        """Log des statistiques pour une colonne"""
        self.logger.info(f"\nStatistiques pour {column_name}:")
        self.logger.info(f"- Nombre de valeurs: {len(values)}")
        self.logger.info(f"- Min: {min(values):.3f}")
        self.logger.info(f"- Max: {max(values):.3f}")
        self.logger.info(f"- Moyenne: {sum(values)/len(values):.3f}")

    def _adjust_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ajuste le nombre d'heures à 8760"""
        if len(df) > 8760:
            return df[:8760]
        
        # Compléter avec interpolation
        last_time = df.index[-1]
        next_hour = last_time + pd.Timedelta(hours=1)
        while len(df) < 8760:
            df.loc[next_hour] = df.iloc[-1]
            next_hour += pd.Timedelta(hours=1)
        
        return df

    def get_iteration_results(self, iteration: int) -> Optional[pd.DataFrame]:
        """Récupère les résultats d'une itération"""
        try:
            paths = get_iteration_dirs(iteration)
            
            # Chercher les fichiers de résultats
            result_files = list(paths['processed_dir'].glob('*_processed.csv'))
            if not result_files:
                raise FileNotFoundError(f"Aucun résultat trouvé dans {paths['processed_dir']}")
            
            # Mode test (un seul archétype)
            if len(result_files) == 1:
                return pd.read_csv(result_files[0], index_col='timestamp', parse_dates=['timestamp'])
            
            # Combiner tous les résultats
            dfs = []
            for result_file in result_files:
                df = pd.read_csv(result_file, index_col='timestamp', parse_dates=['timestamp'])
                dfs.append(df)
            
            return pd.concat(dfs).groupby(level=0).sum()

        except Exception as e:
            self.logger.error(f"Erreur lecture résultats : {str(e)}")
            return None