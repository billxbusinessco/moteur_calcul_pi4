import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys

# Ajout du chemin racine au PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES

class DetailedAnalyzer:
    def __init__(self):
        self.logger = self._setup_logger()
        self.archetypes_df = None
        self.residential_df = None
        self.hydro_df = {}
        
    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('DetailedAnalyzer')

    def load_data(self):
        """Charge toutes les données nécessaires"""
        try:
            # Chargement des archétypes
            self.logger.info("Chargement des archétypes...")
            self.archetypes_df = pd.read_csv(DATA_FILES['ARCHETYPES_FILE'])
            
            # Chargement des données résidentielles
            self.logger.info("Chargement des données résidentielles...")
            self.residential_df = pd.read_csv(
                DATA_FILES['RESIDENTIAL_DATA_FILE'],
                dtype={'code_geografique': str}
            )
            
            # Chargement des données Hydro-Québec 2020-2023 (années complètes)
            self.logger.info("Chargement des données Hydro-Québec...")
            for year in range(2020, 2024):
                self.hydro_df[year] = pd.read_csv(
                    DATA_FILES['HYDRO_QUEBEC_FILES'][year],
                    parse_dates=['Intervalle15Minutes']
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement des données: {str(e)}")
            raise

    def analyze_archetype_characteristics(self):
        """Analyse les caractéristiques des archétypes par zone"""
        results = {}
        
        # Statistiques de base par zone
        zone_stats = self.archetypes_df.groupby('weather_zone').agg({
            'filename': 'count',  # Nombre d'archétypes
            'location_std': lambda x: len(x.unique())  # Nombre de locations uniques
        }).rename(columns={'filename': 'nb_archetypes'})
        
        results['zone_stats'] = zone_stats
        
        # Distribution des locations par zone
        zone_locations = self.archetypes_df.groupby(['weather_zone', 'location_std']).size()
        results['zone_locations'] = zone_locations
        
        return results

    def analyze_building_stock(self):
        """Analyse la correspondance entre archétypes et parc immobilier"""
        results = {}
        
        # Distribution des bâtiments par zone météo
        building_dist = self.residential_df['weather_zone'].value_counts()
        results['building_distribution'] = building_dist
        
        # Ratio archétypes/bâtiments par zone
        archetype_counts = self.archetypes_df['weather_zone'].value_counts()
        building_counts = self.residential_df['weather_zone'].value_counts()
        
        ratio = pd.DataFrame({
            'nb_archetypes': archetype_counts,
            'nb_buildings': building_counts
        })
        ratio['ratio_buildings_per_archetype'] = ratio['nb_buildings'] / ratio['nb_archetypes']
        
        results['coverage_ratio'] = ratio
        
        return results

    def analyze_hydro_consumption(self, year=2022):
        """Analyse les profils de consommation Hydro-Québec"""
        results = {}
        
        if year not in self.hydro_df:
            self.logger.error(f"Données non disponibles pour l'année {year}")
            return None
            
        df = self.hydro_df[year]
        
        # Statistiques de consommation
        consumption_stats = df['energie_sum_secteur'].describe()
        results['consumption_stats'] = consumption_stats
        
        # Profil journalier moyen
        df['hour'] = df['Intervalle15Minutes'].dt.hour
        hourly_profile = df.groupby('hour')['energie_sum_secteur'].mean()
        results['hourly_profile'] = hourly_profile
        
        # Variation mensuelle
        df['month'] = df['Intervalle15Minutes'].dt.month
        monthly_profile = df.groupby('month')['energie_sum_secteur'].mean()
        results['monthly_profile'] = monthly_profile
        
        return results

if __name__ == "__main__":
    analyzer = DetailedAnalyzer()
    
    try:
        # Chargement des données
        analyzer.load_data()
        
        # Analyse des archétypes
        print("\nAnalyse des caractéristiques des archétypes :")
        print("-" * 50)
        archetype_results = analyzer.analyze_archetype_characteristics()
        print("\nStatistiques par zone :")
        print(archetype_results['zone_stats'])
        
        # Analyse du parc immobilier
        print("\nAnalyse de la correspondance archétypes/bâtiments :")
        print("-" * 50)
        building_results = analyzer.analyze_building_stock()
        print("\nRatio bâtiments par archétype :")
        print(building_results['coverage_ratio'])
        
        # Analyse consommation Hydro-Québec
        print("\nAnalyse de la consommation électrique (2022) :")
        print("-" * 50)
        hydro_results = analyzer.analyze_hydro_consumption(2022)
        if hydro_results:
            print("\nStatistiques de consommation :")
            print(hydro_results['consumption_stats'])
            print("\nVariation mensuelle moyenne :")
            print(hydro_results['monthly_profile'])
            
    except Exception as e:
        print(f"Erreur lors de l'analyse : {str(e)}")