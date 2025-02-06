# Dans src/preprocessing/archetype_selector.py

import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR

class ArchetypeSelector:
    def __init__(self):
        self.logger = self._setup_logger()
        self.archetypes_df = None
        self.selected_archetypes = None

        # Mapping des types d'archétypes vers les liens physiques
        self.type_mapping = {
            'Single Detached': 'Détaché',
            'Double/Semi-detached': 'Jumelé',
            'Row house, end unit': 'En rangée 1 côté',
            'Row house, middle unit': 'En rangée plus de 1 côté',
            'Apartment': 'Intégré',
            'Detached Duplex': 'Détaché',
            'Detached Triplex': 'Détaché',
            'Mobile Home': 'Détaché'
        }

    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('ArchetypeSelector')

    def load_selected_archetypes(self) -> bool:
        """
        Charge les archétypes précédemment sélectionnés
        
        Returns:
            bool: True si le chargement est réussi
        """
        try:
            selected_file = PROCESSED_DATA_DIR / 'selected_archetypes.csv'
            if not selected_file.exists():
                self.logger.warning("Fichier selected_archetypes.csv non trouvé")
                return False
            
            self.selected_archetypes = pd.read_csv(selected_file)
            n_archetypes = len(self.selected_archetypes)
            
            if n_archetypes == 0:
                self.logger.warning("Aucun archétype trouvé dans le fichier")
                return False
            
            # Log de la distribution par zone
            zone_dist = self.selected_archetypes['weather_zone'].value_counts()
            self.logger.info(f"Archétypes chargés : {n_archetypes} au total")
            for zone, count in zone_dist.items():
                self.logger.info(f"- Zone {zone}: {count} archétypes")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement : {str(e)}")
            return False

    def select_archetypes(self, n_per_zone: int = None) -> bool:
        """
        Sélectionne les archétypes selon la distribution du parc
        
        Args:
            n_per_zone: Nombre d'archétypes par zone. Si None, utilise la distribution prédéfinie.
        """
        try:
            # Charger les données si nécessaire
            if self.archetypes_df is None:
                if not self.load_data():
                    return False

            if n_per_zone is not None:
                # Mode simplifié : n archétypes par zone
                zone_targets = {
                    462.0: n_per_zone,
                    448.0: n_per_zone,
                    479.0: n_per_zone,
                    477.0: n_per_zone,
                    491.0: n_per_zone
                }
            else:
                # Distribution par défaut
                zone_targets = {
                    462.0: 7,    # Garder tous
                    448.0: 20,   
                    479.0: 30,   
                    477.0: 70,   
                    491.0: 70    
                }

            selected_archetypes = []
            
            # Sélection par zone
            for zone, target in zone_targets.items():
                zone_df = self.archetypes_df[self.archetypes_df['weather_zone'] == zone].copy()
                
                if len(zone_df) <= target:
                    selected_archetypes.append(zone_df)
                    self.logger.info(f"Zone {zone}: Gardé tous les {len(zone_df)} archétypes")
                    continue
                
                # Sélection aléatoire pour cette zone
                selected = zone_df.sample(n=target)
                selected_archetypes.append(selected)
                self.logger.info(f"Zone {zone}: Sélectionné {len(selected)}/{len(zone_df)} archétypes")

            # Combiner toutes les sélections
            self.selected_archetypes = pd.concat(selected_archetypes)
            
            # Sauvegarder la sélection
            output_file = PROCESSED_DATA_DIR / 'selected_archetypes.csv'
            self.selected_archetypes.to_csv(output_file, index=False)
            
            self.logger.info(f"Sélection terminée : {len(self.selected_archetypes)} archétypes au total")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sélection : {str(e)}")
            return False

    def load_data(self) -> bool:
        """Charge les données des archétypes"""
        try:
            self.logger.info("Chargement des archétypes...")
            self.archetypes_df = pd.read_csv(DATA_FILES['ARCHETYPES_FILE'])
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement : {str(e)}")
            return False

# Test direct
if __name__ == "__main__":
    # Pour 2 archétypes par zone (test rapide)
    selector = ArchetypeSelector()
    selector.select_archetypes(n_per_zone=10)

    # # Pour 10 archétypes par zone
    # selector.select_archetypes(n_per_zone=10)

    # # Pour utiliser la distribution par défaut
    # selector.select_archetypes()