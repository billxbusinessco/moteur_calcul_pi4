import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys
import json
from datetime import datetime
from typing import Dict, Optional

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import (
    DATA_FILES, 
    PROCESSED_DATA_DIR, 
    RESULTS_DIR, 
    get_iteration_dirs,
    RESULTS_STRUCTURE
)

class BuildingStockAggregator:
    """Agrège les résultats de simulation au niveau provincial"""
    
    def __init__(self):
        self.logger = self._setup_logger()
        
        # Initialiser selected_archetypes
        self.selected_archetypes = None
        
        # Poids des archétypes
        self.archetype_weights = {}
        
        # État de l'agrégation
        self.aggregation_metrics = {
            'processed_iterations': [],
            'archetype_stats': {}
        }
        
    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('BuildingStockAggregator')

    def calculate_provincial_weights(self) -> bool:
        """Calcule les poids provinciaux des archétypes"""
        try:
            # 1. Charger données
            selected_file = PROCESSED_DATA_DIR / 'selected_archetypes.csv'
            residential_data = pd.read_csv(DATA_FILES['RESIDENTIAL_DATA_FILE'])
            
            if self.selected_archetypes is None:
                self.selected_archetypes = pd.read_csv(selected_file)
            total_buildings = len(residential_data)

            # Si un seul archétype, mode test
            if len(self.selected_archetypes) == 1:
                self.archetype_weights = {
                    self.selected_archetypes['filename'].iloc[0]: 1.0
                }
                self.logger.info("Mode test: Un seul archétype")
                return True

            # 2. Distribution par type de lien physique
            type_counts = residential_data['lien_physique_description'].value_counts()
            
            self.logger.info("\nDistribution provinciale par type :")
            for type_, count in type_counts.items():
                self.logger.info(f"- {type_}: {count:,} bâtiments ({count/total_buildings:.1%})")
            
            # 3. Mapping des types d'archétypes
            type_mapping = {
                'Détaché': ['Single Detached', 'Detached Duplex', 'Detached Triplex', 'Mobile Home'],
                'Jumelé': ['Double/Semi-detached'],
                'En rangée 1 côté': ['Row house, end unit'],
                'En rangée plus de 1 côté': ['Row house, middle unit'],
                'Intégré': ['Apartment']
            }
            
            # 4. Calculer nombre d'archétypes par type
            archetype_counts = {}
            for _, archetype in self.selected_archetypes.iterrows():
                subtype = archetype['houseSubType']
                for main_type, subtypes in type_mapping.items():
                    if subtype in subtypes:
                        archetype_counts[main_type] = archetype_counts.get(main_type, 0) + 1
                        break
            
            # 5. Calculer poids des archétypes
            self.archetype_weights = {}
            total_weighted = 0
            
            for _, archetype in self.selected_archetypes.iterrows():
                subtype = archetype['houseSubType']
                weight = 0
                
                for main_type, subtypes in type_mapping.items():
                    if subtype in subtypes:
                        type_count = type_counts.get(main_type, 0)
                        n_archetypes = archetype_counts[main_type]
                        if n_archetypes > 0:
                            weight = type_count / n_archetypes
                        break
                
                self.archetype_weights[archetype['filename']] = weight
                total_weighted += weight
            
            # 6. Vérification
            if not np.isclose(total_weighted, total_buildings, rtol=0.01):
                self.logger.warning(
                    f"Différence dans le total: {total_buildings - total_weighted:,.0f} "
                    f"bâtiments ({((total_weighted/total_buildings)-1)*100:.1f}% d'écart)"
                )
            else:
                self.logger.info("\nTotal vérifié avec le parc immobilier")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur calcul poids provinciaux : {str(e)}")
            return False

    def aggregate_provincial_results(self, iteration: int) -> bool:
        """Agrège les résultats au niveau provincial pour une itération"""
        try:
            # 1. Vérifier/calculer les poids
            if not self.archetype_weights:
                if not self.calculate_provincial_weights():
                    raise ValueError("Échec calcul poids provinciaux")
            
            # 2. Obtenir chemins
            paths = get_iteration_dirs(iteration)
            processed_dir = paths['processed_dir']
            
            # 3. Initialisation
            combined_results = pd.DataFrame()
            processed_count = 0
            
            # 4. Pour chaque archétype avec un poids
            for arch_name, weight in self.archetype_weights.items():
                # Construire nom base
                arch_base = arch_name.replace('.H2K', '').replace('.h2k', '')
                results_path = processed_dir / f"{arch_base}_processed.csv"
                
                if not results_path.exists():
                    # En mode test (un seul archétype), ne pas logger les avertissements
                    # pour les autres archétypes
                    if len(self.archetype_weights) == 1:
                        self.logger.error(f"Résultats non trouvés : {arch_base}")
                        return False
                    else:
                        self.logger.warning(f"Résultats non trouvés : {arch_base}")
                    continue
                
                try:
                    # Charger et pondérer résultats
                    arch_results = pd.read_csv(
                        results_path,
                        index_col='timestamp',
                        parse_dates=['timestamp']
                    )
                    
                    weighted_results = arch_results.astype(float) * float(weight)
                    
                    # Agréger
                    if combined_results.empty:
                        combined_results = weighted_results
                    else:
                        combined_results = combined_results.add(weighted_results, fill_value=0)
                    
                    processed_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Erreur traitement {arch_base}: {str(e)}")
                    continue
            
            # 5. Sauvegarder résultats provinciaux
            if not combined_results.empty:
                combined_results.to_csv(paths['provincial_file'])
                
                # Calculer et sauvegarder statistiques
                stats = self._calculate_statistics(combined_results)
                
                metadata = {
                    'iteration': iteration,
                    'timestamp': datetime.now().isoformat(),
                    'statistics': stats,
                    'processed_archetypes': processed_count,
                    'total_archetypes': len(self.archetype_weights),
                    'success_rate': (processed_count / len(self.archetype_weights)) * 100
                }
                
                metadata_path = paths['provincial_dir'] / 'metadata.json'
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur agrégation provinciale : {str(e)}")
            return False

    def _calculate_statistics(self, df: pd.DataFrame) -> dict:
        """Calcule les statistiques détaillées pour chaque colonne"""
        stats = {}
        
        for col in df.columns:
            # Masques saisonniers
            winter_mask = df.index.month.isin([12, 1, 2])
            summer_mask = df.index.month.isin([6, 7, 8])
            
            stats[col] = {
                'mean': float(df[col].mean()),
                'std': float(df[col].std()),
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'total_annual': float(df[col].sum()),
                'winter_mean': float(df.loc[winter_mask, col].mean()),
                'summer_mean': float(df.loc[summer_mask, col].mean())
            }
            
            # Log statistiques principales
            self.logger.info(f"\n{col}:")
            self.logger.info(f"- Consommation annuelle : {stats[col]['total_annual']:.2f} kWh")
            self.logger.info(f"- Moyenne hiver : {stats[col]['winter_mean']:.2f} kWh")
            self.logger.info(f"- Moyenne été : {stats[col]['summer_mean']:.2f} kWh")
        
        return stats

    def get_iteration_results(self, iteration: int) -> Optional[pd.DataFrame]:
        """Récupère les résultats provinciaux d'une itération"""
        try:
            paths = get_iteration_dirs(iteration)
            results_file = paths['provincial_file']
            
            if not results_file.exists():
                raise FileNotFoundError(f"Résultats non trouvés: {results_file}")
            
            return pd.read_csv(results_file, index_col='timestamp', parse_dates=['timestamp'])
            
        except Exception as e:
            self.logger.error(f"Erreur lecture résultats : {str(e)}")
            return None