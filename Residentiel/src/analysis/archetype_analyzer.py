import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging

# Ajout du chemin racine au PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES

class ArchetypeAnalyzer:
    def __init__(self):
        self.logger = self._setup_logger()
        self.archetypes_df = None
        
    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('ArchetypeAnalyzer')

    def load_archetypes(self):
        """Charge le fichier des archétypes"""
        try:
            self.logger.info("Chargement des archétypes...")
            self.archetypes_df = pd.read_csv(DATA_FILES['ARCHETYPES_FILE'])
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement des archétypes: {str(e)}")
            raise

    def analyze_basic_characteristics(self):
        """Analyse les caractéristiques de base des archétypes"""
        if self.archetypes_df is None:
            self.load_archetypes()

        results = {}
        
        # 1. Distribution par type de maison et zone météo
        house_type_dist = pd.crosstab(
            self.archetypes_df['weather_zone'],
            self.archetypes_df['houseType']
        )
        results['house_type_distribution'] = house_type_dist
        
        # 2. Distribution par décennie et zone météo
        decade_dist = pd.crosstab(
            self.archetypes_df['weather_zone'],
            self.archetypes_df['decade']
        )
        results['decade_distribution'] = decade_dist
        
        # 3. Statistiques de surface par zone
        area_stats = self.archetypes_df.groupby('weather_zone')['totFloorArea'].describe()
        results['floor_area_stats'] = area_stats
        
        # 4. Distribution par nombre d'étages et zone météo
        storey_dist = pd.crosstab(
            self.archetypes_df['weather_zone'],
            self.archetypes_df['storeys']
        )
        results['storey_distribution'] = storey_dist
        
        return results

if __name__ == "__main__":
    analyzer = ArchetypeAnalyzer()
    
    try:
        results = analyzer.analyze_basic_characteristics()
        
        print("\nDistribution par type de maison et zone météo :")
        print("-" * 50)
        print(results['house_type_distribution'])
        
        print("\nDistribution par décennie et zone météo :")
        print("-" * 50)
        print(results['decade_distribution'])
        
        print("\nStatistiques de surface par zone :")
        print("-" * 50)
        print(results['floor_area_stats'])
        
        print("\nDistribution par nombre d'étages et zone météo :")
        print("-" * 50)
        print(results['storey_distribution'])
        
    except Exception as e:
        print(f"Erreur lors de l'analyse : {str(e)}")