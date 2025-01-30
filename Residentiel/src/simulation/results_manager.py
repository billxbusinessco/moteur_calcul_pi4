import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys
import json
from datetime import datetime

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
    def __init__(self):
        self.logger = self._setup_logger()
        self.results_dir = RESULTS_STRUCTURE['PROCESSED_DIR']  # Utiliser RESULTS_STRUCTURE
        self.simulation_dir = RESULTS_STRUCTURE['SIMULATIONS_DIR']  
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Colonnes primaires (celles qu'on veut absolument)
        self.primary_columns = {
            'timestamp': 'Time',
            'total_electricity': 'Fuel Use: Electricity: Total',
            'heating': 'End Use: Electricity: Heating',
            'cooling': 'End Use: Electricity: Cooling'
        }

    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('ResultsManager')

    def process_iteration_results(self, iteration: int) -> bool:
        """
        Traite les résultats d'une itération complète
        """
        try:
            # 1. Localiser les résultats via chemins centralisés
            paths = get_iteration_dirs(iteration)
            iteration_dir = RESULTS_STRUCTURE['SIMULATIONS_DIR'] / f'iteration_{iteration}'
            output_dir = paths['iteration_dir']
            
            if not iteration_dir.exists():
                raise FileNotFoundError(f"Dossier d'itération non trouvé: {iteration_dir}")

            # 2. Préparer dossier de sortie
            output_dir.mkdir(parents=True, exist_ok=True)

            # 3. Traiter chaque archétype
            archetype_results = {}
            processed = 0
            errors = 0

            for arch_dir in iteration_dir.iterdir():
                if not arch_dir.is_dir() or arch_dir.name.startswith('_'):
                    continue

                try:
                    # Chercher résultats dans output/run/
                    results_file = arch_dir / 'output' / arch_dir.name / 'run' / 'results_timeseries.csv'
                    if not results_file.exists():
                        raise FileNotFoundError(f"Résultats non trouvés: {results_file}")

                    # Traiter les données
                    processed_data = self._process_results_file(results_file)
                    if processed_data is not None:
                        # Sauvegarder résultats traités
                        output_file = output_dir / f"{arch_dir.name}_processed.csv"
                        processed_data.to_csv(output_file)
                        archetype_results[arch_dir.name] = True
                        processed += 1
                    else:
                        errors += 1

                except Exception as e:
                    self.logger.error(f"Erreur traitement {arch_dir.name}: {str(e)}")
                    errors += 1
                    continue

            # 4. Sauvegarder métadonnées
            self._save_processing_metadata(iteration, {
                'processed': processed,
                'errors': errors,
                'success_rate': (processed / (processed + errors)) * 100 if (processed + errors) > 0 else 0
            })

            self.logger.info(f"\nTraitement terminé:")
            self.logger.info(f"- Archétypes traités: {processed}")
            self.logger.info(f"- Erreurs: {errors}")

            return processed > 0

        except Exception as e:
            self.logger.error(f"Erreur traitement itération {iteration}: {str(e)}")
            return False

    # def _process_results_file(self, file_path: Path) -> pd.DataFrame:
    #     try:
    #         # 1. Lecture avec gestion explicite des types et options
    #         df = pd.read_csv(file_path, low_memory=False)
            
    #         # 2. Nettoyer et extraire les vraies données numériques (après la ligne d'unités)
    #         result_df = pd.DataFrame()
            
    #         # Traitement du temps
    #         result_df['timestamp'] = pd.to_datetime(df['Time'].values[2:])
    #         result_df.set_index('timestamp', inplace=True)
            
    #         # Colonnes d'énergie - assurer la conversion en float
    #         energy_columns = {
    #             'total_electricity': 'Fuel Use: Electricity: Total',
    #             'heating': 'End Use: Electricity: Heating',
    #             'cooling': 'End Use: Electricity: Cooling'
    #         }
            
    #         for target, source in energy_columns.items():
    #             # Extraction des valeurs numériques
    #             values = df[source].values[2:]  # Ignorer les 2 premières lignes
    #             numerical_values = []
                
    #             for val in values:
    #                 try:
    #                     # Nettoyer et convertir la valeur
    #                     clean_val = str(val).strip().replace(',', '.')
    #                     num_val = float(clean_val)
    #                     numerical_values.append(num_val)
    #                 except (ValueError, TypeError):
    #                     numerical_values.append(0.0)  # ou np.nan si vous préférez
                
    #             result_df[target] = numerical_values
                
    #             # Validation et log
    #             self.logger.info(f"\nStatistiques pour {target}:")
    #             self.logger.info(f"- Nombre de valeurs: {len(numerical_values)}")
    #             self.logger.info(f"- Min: {min(numerical_values):.3f}")
    #             self.logger.info(f"- Max: {max(numerical_values):.3f}")
    #             self.logger.info(f"- Moyenne: {sum(numerical_values)/len(numerical_values):.3f}")
            
    #         # 3. Validation finale du nombre d'heures
    #         if len(result_df) != 8760:
    #             self.logger.warning(f"Ajustement du nombre d'heures : {len(result_df)} -> 8760")
    #             # Compléter ou tronquer pour avoir exactement 8760 heures
    #             if len(result_df) > 8760:
    #                 result_df = result_df[:8760]
    #             else:
    #                 # Ajouter les heures manquantes avec des valeurs interpolées
    #                 last_time = result_df.index[-1]
    #                 next_hour = last_time + pd.Timedelta(hours=1)
    #                 while len(result_df) < 8760:
    #                     result_df.loc[next_hour] = result_df.iloc[-1]
    #                     next_hour += pd.Timedelta(hours=1)
            
    #         return result_df

    #     except Exception as e:
    #         self.logger.error(f"Erreur traitement fichier {file_path.name}: {str(e)}")
    #         import traceback
    #         self.logger.error(f"Traceback: {traceback.format_exc()}")
    #         return None


    def _process_results_file(self, file_path: Path) -> pd.DataFrame:
        try:
            # 1. Lecture avec gestion explicite des types et options
            df = pd.read_csv(file_path, low_memory=False)
            
            # 2. Nettoyer et extraire les vraies données numériques (après la ligne d'unités)
            result_df = pd.DataFrame()
            
            # Traitement du temps
            result_df['timestamp'] = pd.to_datetime(df['Time'].values[1:])  # Commencer à 1 au lieu de 2
            result_df.set_index('timestamp', inplace=True)
            
            # Colonnes d'énergie - assurer la conversion en float
            energy_columns = {
                'total_electricity': 'Fuel Use: Electricity: Total',
                'heating': 'End Use: Electricity: Heating',
                'cooling': 'End Use: Electricity: Cooling'
            }
            
            for target, source in energy_columns.items():
                # Extraction des valeurs numériques
                values = df[source].values[1:]  # Commencer à 1 au lieu de 2
                numerical_values = []
                
                for val in values:
                    try:
                        # Nettoyer et convertir la valeur
                        clean_val = str(val).strip().replace(',', '.')
                        num_val = float(clean_val)
                        numerical_values.append(num_val)
                    except (ValueError, TypeError):
                        numerical_values.append(0.0)  # ou np.nan si vous préférez
                
                result_df[target] = numerical_values
                
                # Validation et log
                self.logger.info(f"\nStatistiques pour {target}:")
                self.logger.info(f"- Nombre de valeurs: {len(numerical_values)}")
                self.logger.info(f"- Min: {min(numerical_values):.3f}")
                self.logger.info(f"- Max: {max(numerical_values):.3f}")
                self.logger.info(f"- Moyenne: {sum(numerical_values)/len(numerical_values):.3f}")
            
            # 3. Validation finale du nombre d'heures
            if len(result_df) != 8760:
                self.logger.warning(f"Ajustement du nombre d'heures : {len(result_df)} -> 8760")
                if len(result_df) > 8760:
                    result_df = result_df[:8760]
                else:
                    # Ajouter les heures manquantes avec des valeurs interpolées
                    last_time = result_df.index[-1]
                    next_hour = last_time + pd.Timedelta(hours=1)
                    while len(result_df) < 8760:
                        result_df.loc[next_hour] = result_df.iloc[-1]
                        next_hour += pd.Timedelta(hours=1)
            
            return result_df

        except Exception as e:
            self.logger.error(f"Erreur traitement fichier {file_path.name}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
        
    

    def _save_processing_metadata(self, iteration: int, metrics: dict):
        """
        Sauvegarde les métadonnées du traitement
        """
        metadata = {
            'iteration': iteration,
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'processing_info': {
                'columns_processed': list(self.primary_columns.keys()),
                'target_hours': 8760,
            }
        }

        metadata_file = self.results_dir / f'iteration_{iteration}' / 'processing_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

if __name__ == "__main__":
    manager = ResultsManager()
    
    print("\nTest du ResultsManager :")
    print("-" * 50)
    
    # Test avec un seul fichier
    iteration_dir = manager.simulation_dir / 'iteration_0'
    if iteration_dir.exists():
        print(f"\nRecherche dans : {iteration_dir}")
        # Trouver le premier fichier de résultats
        for arch_dir in iteration_dir.iterdir():
            if arch_dir.is_dir():
                results_path = arch_dir / 'output' / arch_dir.name / 'run' / 'results_timeseries.csv'
                print(f"\nVérification : {results_path}")
                
                if results_path.exists():
                    print(f"\nTraitement du fichier : {results_path}")
                    
                    # Traiter le fichier
                    processed_df = manager._process_results_file(results_path)
                    
                    if processed_df is not None:
                        print("\nVérification des données traitées :")
                        print(f"Nombre de lignes : {len(processed_df)}")
                        print("\nPremières lignes :")
                        print(processed_df.head())
                        print("\nDernières lignes :")
                        print(processed_df.tail())
                        
                        print("\nStatistiques détaillées :")
                        print(processed_df.describe())
                        
                        # Sauvegarder le résultat
                        output_dir = manager.results_dir / 'iteration_0'
                        output_dir.mkdir(exist_ok=True, parents=True)
                        output_file = output_dir / f"{arch_dir.name}_processed.csv"
                        processed_df.to_csv(output_file)
                        print(f"\nRésultat sauvegardé dans : {output_file}")
                        
                        # Vérifier le fichier sauvegardé
                        print("\nVérification du fichier sauvegardé :")
                        saved_df = pd.read_csv(output_file)
                        print(f"Nombre de lignes dans le fichier : {len(saved_df)}")
                        print("Premières lignes du fichier sauvegardé :")
                        print(saved_df.head())
                        break
    else:
        print(f"\nDossier non trouvé : {iteration_dir}")
        print("Assurez-vous d'avoir lancé au moins une simulation.")