import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys
import json
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR, RESULTS_DIR, get_iteration_dirs, RESULTS_STRUCTURE

class BuildingStockAggregator:
    def __init__(self):
        self.logger = self._setup_logger()
        self.archetype_weights = {}
        self.target_dir = RESULTS_STRUCTURE['PROCESSED_DIR']  # Utiliser RESULTS_STRUCTURE
        self.results_dir = RESULTS_STRUCTURE['PROVINCIAL_DIR']
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Colonnes primaires (celles qu'on veut absolument)
        self.primary_columns = {
            'timestamp': 'Time',
            'total_electricity': 'Fuel Use: Electricity: Total'
        }

        # Colonnes secondaires (utiles mais non essentielles)
        self.secondary_columns = {
            'heating': 'End Use: Electricity: Heating',
            'cooling': 'End Use: Electricity: Cooling',
        }
        
    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('BuildingStockAggregator')

    def calculate_provincial_weights(self) -> bool:
        """Calcule les poids de chaque archétype au niveau provincial"""
        try:
            # Charger les archétypes sélectionnés
            selected_file = PROCESSED_DATA_DIR / 'selected_archetypes.csv'
            self.selected_archetypes = pd.read_csv(selected_file)
            
            # Charger données résidentielles
            residential_data = pd.read_csv(DATA_FILES['RESIDENTIAL_DATA_FILE'])
            
            # Nombre total de bâtiments
            total_buildings = len(residential_data)
            self.logger.info(f"\nNombre total de bâtiments : {total_buildings:,}")
            
            # Créer un mapping inverse pour regrouper les sous-types
            inverse_mapping = {
                'Détaché': ['Single Detached', 'Detached Duplex', 'Detached Triplex', 'Mobile Home'],
                'Jumelé': ['Double/Semi-detached'],
                'En rangée 1 côté': ['Row house, end unit'],
                'En rangée plus de 1 côté': ['Row house, middle unit'],
                'Intégré': ['Apartment']
            }
            
            # Distribution provinciale par type
            type_counts = residential_data['lien_physique_description'].value_counts()
            self.logger.info("\nDistribution provinciale par type :")
            for type_, count in type_counts.items():
                self.logger.info(f"- {type_}: {count:,} bâtiments ({count/total_buildings:.1%})")
            
            # Pour chaque archétype
            self.archetype_weights = {}
            archetype_counts = {}  # Pour compter combien d'archétypes par type
            
            # 1. Compter d'abord le nombre d'archétypes par type
            for _, archetype in self.selected_archetypes.iterrows():
                subtype = archetype['houseSubType']
                # Trouver le type principal
                for main_type, subtypes in inverse_mapping.items():
                    if subtype in subtypes:
                        if main_type not in archetype_counts:
                            archetype_counts[main_type] = 0
                        archetype_counts[main_type] += 1
                        break
            
            # 2. Calculer les poids
            for _, archetype in self.selected_archetypes.iterrows():
                subtype = archetype['houseSubType']
                # Trouver le type principal et son nombre total de bâtiments
                for main_type, subtypes in inverse_mapping.items():
                    if subtype in subtypes:
                        type_count = type_counts.get(main_type, 0)
                        n_archetypes = archetype_counts[main_type]
                        
                        if n_archetypes > 0:
                            # Diviser le nombre de bâtiments par le nombre d'archétypes de ce type
                            buildings_represented = type_count / n_archetypes
                            self.archetype_weights[archetype['filename']] = buildings_represented
                            
                            # Log détaillé
                            self.logger.debug(f"Archétype {archetype['filename']}:")
                            self.logger.debug(f"- Type: {main_type}")
                            self.logger.debug(f"- Sous-type: {subtype}")
                            self.logger.debug(f"- Bâtiments représentés: {buildings_represented:,.0f}")
                        else:
                            self.archetype_weights[archetype['filename']] = 0
                        break
            
            # Log des poids finaux
            weights_series = pd.Series(self.archetype_weights)
            self.logger.info("\nDistribution finale des poids :")
            self.logger.info(f"- Min : {weights_series.min():,.0f} bâtiments")
            self.logger.info(f"- Max : {weights_series.max():,.0f} bâtiments")
            self.logger.info(f"- Moyenne : {weights_series.mean():,.0f} bâtiments")
            self.logger.info(f"- Total : {weights_series.sum():,.0f} bâtiments")
            
            # Vérification du total
            total_weighted = weights_series.sum()
            if not np.isclose(total_weighted, total_buildings, rtol=0.01):
                self.logger.warning(f"Différence dans le total: {total_buildings - total_weighted:,.0f} bâtiments ({((total_weighted/total_buildings)-1)*100:.1f}% d'écart)")
            else:
                self.logger.info("\nTotal vérifié : concordance avec le nombre total de bâtiments")
                
            return True
                
        except Exception as e:
            self.logger.error(f"Erreur calcul poids provinciaux : {str(e)}")
            return False

    def _map_archetype_to_building_type(self, archetype: pd.Series) -> str:
        """Mappe un archétype à un type de bâtiment du recensement"""
        mapping = {
            'Single Detached': 'Détaché',
            'Double/Semi-detached': 'Jumelé',
            'Row house, end unit': 'En rangée 1 côté',
            'Row house, middle unit': 'En rangée plus de 1 côté',
            'Apartment': 'Intégré',
            'Detached Duplex': 'Détaché',
            'Detached Triplex': 'Détaché',
            'Mobile Home': 'Détaché'
        }
        return mapping.get(archetype['houseSubType'], 'Détaché')

    def _get_available_columns(self, file_path: Path) -> list:
        """Lit les en-têtes disponibles dans un fichier"""
        try:
            with open(file_path, 'r') as f:
                headers = pd.read_csv(f, nrows=0).columns.tolist()
            return headers
        except Exception as e:
            self.logger.error(f"Erreur lecture en-têtes {file_path.name}: {str(e)}")
            return []

    def _validate_columns(self, available_columns: list) -> dict:
        """Valide et retourne les colonnes à utiliser"""
        columns_to_use = {}
        
        # Vérifier colonnes primaires
        for key, col in self.primary_columns.items():
            if col not in available_columns:
                raise ValueError(f"Colonne primaire manquante: {col}")
            columns_to_use[key] = col
            
        # Ajouter colonnes secondaires si disponibles
        for key, col in self.secondary_columns.items():
            if col in available_columns:
                columns_to_use[key] = col
                
        return columns_to_use

    def aggregate_provincial_results(self, iteration: int) -> bool:
        """Agrège les résultats au niveau provincial"""
        try:
            # 1. Vérifier/calculer les poids provinciaux
            if not self.archetype_weights:
                if not self.calculate_provincial_weights():
                    raise ValueError("Échec calcul poids provinciaux")
            
            # 2. Initialisation
            provincial_results = None
            processed_count = 0
            
            # 3. Pour chaque archétype
            paths = get_iteration_dirs(iteration)  # Ajout ici
            iteration_dir = paths['iteration_dir']  # Utiliser le chemin centralisé
            
            for arch_name, weight in self.archetype_weights.items():
                # Construire le nom de base
                arch_base = arch_name.replace('.H2K', '').replace('.h2k', '')
                
                # Chercher dans les résultats traités
                results_path = iteration_dir / f"{arch_base}_processed.csv"
                
                if not results_path.exists():
                    self.logger.warning(f"Résultats non trouvés pour {arch_base}")
                    continue
                
                try:
                    # 4. Charger et traiter les données
                    arch_results = pd.read_csv(
                        results_path,
                        index_col='timestamp',
                        parse_dates=['timestamp']
                    )
                    
                    # 5. Pondérer et agréger
                    weighted_results = arch_results.astype(float) * float(weight)
                    if provincial_results is None:
                         provincial_results = weighted_results
                    else:
                        provincial_results = provincial_results.add(weighted_results, fill_value=0)
                    
                    processed_count += 1
                    
                    # Log progression
                    if processed_count % 10 == 0:  
                        self.logger.info(f"Progression : {processed_count}/{len(self.archetype_weights)}")
                    
                except Exception as e:
                    self.logger.error(f"Erreur traitement {arch_base}: {str(e)}")
                    continue
            
            # 6. Sauvegarder résultats
            if provincial_results is not None:
                # Sauvegarder DataFrame
                output_path = self.results_dir / f'provincial_results_iter_{iteration}.csv'
                provincial_results.to_csv(output_path)
                
                # Calculer et sauvegarder statistiques
                stats = self._calculate_statistics(provincial_results)
                metadata = {
                    'iteration': iteration,
                    'timestamp': datetime.now().isoformat(),
                    'statistics': stats,
                    'processed_archetypes': processed_count,
                    'total_archetypes': len(self.archetype_weights),
                    'success_rate': (processed_count / len(self.archetype_weights)) * 100
                }
                
                metadata_path = self.results_dir / f'metadata_iter_{iteration}.json'
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                return True
                
            return False

        except Exception as e:
            self.logger.error(f"Erreur lors de l'agrégation provinciale : {str(e)}")
            return False
        
    def _calculate_statistics(self, df: pd.DataFrame) -> dict:
        """
        Calcule les statistiques détaillées pour chaque colonne
        
        Args:
            df: DataFrame avec les résultats horaires
            
        Returns:
            dict: Statistiques par colonne
        """
        stats = {}
        for col in df.columns:
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
            
            # Log des statistiques principales
            self.logger.info(f"\n{col}:")
            self.logger.info(f"- Consommation annuelle : {stats[col]['total_annual']:.2f} kWh")
            self.logger.info(f"- Moyenne hiver : {stats[col]['winter_mean']:.2f} kWh")
            self.logger.info(f"- Moyenne été : {stats[col]['summer_mean']:.2f} kWh")
        
        return stats
    
    def get_iteration_results(self, iteration: int, full_data: bool = False) -> pd.DataFrame:
        """
        Récupère les résultats d'une itération spécifique
        
        Args:
            iteration: Numéro de l'itération
            full_data: Si True, retourne toutes les colonnes, sinon juste total_electricity
            
        Returns:
            DataFrame avec les résultats horaires, None si erreur
        """
        try:
            # 1. Vérifier existence du fichier
            results_file = self.results_dir / f'provincial_results_iter_{iteration}.csv'
            metadata_file = self.results_dir / f'metadata_iter_{iteration}.json'
            
            if not results_file.exists():
                raise FileNotFoundError(f"Résultats non trouvés pour itération {iteration}")
                
            # 2. Charger données
            df = pd.read_csv(results_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 3. Charger métadonnées si disponibles
            stats = None
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                stats = metadata.get('statistics', {})
            
            # 4. Log des informations
            self.logger.info(f"\nRésultats itération {iteration} :")
            self.logger.info(f"- Nombre d'heures : {len(df)}")
            if stats and 'total_electricity' in stats:
                self.logger.info(f"- Consommation totale : {stats['total_electricity']['total_annual']:.2f} kWh")
                self.logger.info(f"- Pic horaire : {stats['total_electricity']['max']:.2f} kWh")
            
            # 5. Retourner résultats
            if not full_data:
                return df['total_electricity']
            return df
            
        except Exception as e:
            self.logger.error(f"Erreur lecture résultats itération {iteration}: {str(e)}")
            return None

    def get_iteration_metadata(self, iteration: int) -> dict:
        """
        Récupère les métadonnées d'une itération
        """
        try:
            metadata_file = self.results_dir / f'metadata_iter_{iteration}.json'
            if not metadata_file.exists():
                raise FileNotFoundError(f"Métadonnées non trouvées pour itération {iteration}")
                
            with open(metadata_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"Erreur lecture métadonnées itération {iteration}: {str(e)}")
            return None

if __name__ == "__main__":
    aggregator = BuildingStockAggregator()
    
    print("\nTest de l'agrégateur provincial :")
    print("-" * 50)
    
    # Test des nouvelles méthodes
    print("\n1. Test lecture résultats par itération :")
    
    # Test itération 0 (devrait exister)
    iteration_0 = aggregator.get_iteration_results(0)
    if iteration_0 is not None:
        print("\nItération 0 :")
        print(f"- Nombre d'heures : {len(iteration_0)}")
        print(f"- Consommation moyenne : {iteration_0.mean():.2f} kWh")
        print(f"- Pic de consommation : {iteration_0.max():.2f} kWh")
        
        # Test métadonnées
        metadata_0 = aggregator.get_iteration_metadata(0)
        if metadata_0:
            print("\nMétadonnées itération 0 :")
            print(f"- Archétypes traités : {metadata_0['processed_archetypes']}")
            print(f"- Taux de succès : {metadata_0['summary']['success_rate']:.1f}%")
    else:
        print("❌ Pas de résultats pour itération 0")
    
    # Test itération 1 (peut ne pas exister)
    print("\n2. Test lecture itération 1 :")
    iteration_1 = aggregator.get_iteration_results(1)
    if iteration_1 is not None:
        print("✓ Résultats trouvés pour itération 1")
    else:
        print("❌ Pas de résultats pour itération 1 (normal si pas encore simulé)")
    
    # Test données complètes vs consommation totale
    print("\n3. Test lecture données complètes :")
    full_data = aggregator.get_iteration_results(0, full_data=True)
    if full_data is not None:
        print("Colonnes disponibles :")
        for col in full_data.columns:
            print(f"- {col}")