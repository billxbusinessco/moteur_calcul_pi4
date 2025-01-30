import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging

# Ajout du chemin racine au PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES

class BuildingStockAnalyzer:
    def __init__(self):
        self.logger = self._setup_logger()
        self.residential_df = None
        
    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('BuildingStockAnalyzer')

    def load_data(self):
        """Charge les données de l'évaluation foncière"""
        try:
            self.logger.info("Chargement des données résidentielles...")
            self.residential_df = pd.read_csv(
                DATA_FILES['RESIDENTIAL_DATA_FILE'],
                dtype={'code_geografique': str, 'lien_physique_code': str}
            )
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement : {str(e)}")
            raise

    def analyze_physical_links(self):
        """Analyse la distribution des liens physiques par zone"""
        if self.residential_df is None:
            self.load_data()

        # Distribution globale des liens physiques
        global_dist = self.residential_df['lien_physique_description'].value_counts()
        
        # Distribution par zone
        zone_dist = pd.crosstab(
            self.residential_df['weather_zone'],
            self.residential_df['lien_physique_description'],
            normalize='index'
        ) * 100  # Pour avoir des pourcentages
        
        # Calcul des ratios cibles par type et par zone
        target_ratios = {}
        for zone in zone_dist.index:
            target_ratios[zone] = {
                'detached': zone_dist.loc[zone, 'Détaché'],
                'semi_detached': zone_dist.loc[zone, 'Jumelé'],
                'row': zone_dist.loc[zone, 'En rangée 1 côté'] + 
                       zone_dist.loc[zone, 'En rangée plus de 1 côté'],
                'integrated': zone_dist.loc[zone, 'Intégré']
            }
        
        return {
            'global_distribution': global_dist,
            'zone_distribution': zone_dist,
            'target_ratios': target_ratios
        }

if __name__ == "__main__":
    analyzer = BuildingStockAnalyzer()
    
    try:
        print("\nAnalyse de la distribution des types de bâtiments :")
        print("-" * 50)
        results = analyzer.analyze_physical_links()
        
        print("\nDistribution globale des liens physiques :")
        print(results['global_distribution'])
        
        print("\nDistribution par zone (%) :")
        print(results['zone_distribution'])
        
        print("\nRatios cibles par zone :")
        for zone, ratios in results['target_ratios'].items():
            print(f"\nZone {zone}:")
            for type_, ratio in ratios.items():
                print(f"{type_}: {ratio:.1f}%")
        
    except Exception as e:
        print(f"Erreur lors de l'analyse : {str(e)}")