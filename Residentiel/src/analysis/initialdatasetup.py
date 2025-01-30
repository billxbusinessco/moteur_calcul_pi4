import pandas as pd
import shutil
from pathlib import Path
import logging
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR, RESULTS_DIR

class InitialDataSetup:
    """Utilitaire temporaire pour organiser les données de simulation existantes"""
    
    def __init__(self):
        self.logger = self._setup_logger()
        self.source_dir = DATA_FILES['H2K_STOCK_DIR']
        self.target_dir = RESULTS_DIR / 'processed_results'
        self.target_dir.mkdir(parents=True, exist_ok=True)
        
    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('InitialDataSetup')
    
    def copy_initial_results(self):
        """Copie les résultats existants vers la structure attendue"""
        try:
            # 1. Charger liste des archétypes sélectionnés
            selected_file = PROCESSED_DATA_DIR / 'selected_archetypes.csv'
            selected_df = pd.read_csv(selected_file)
            
            processed_count = 0
            
            # 2. Pour chaque archétype
            for _, archetype in selected_df.iterrows():
                arch_name = archetype['filename'].replace('.H2K', '').replace('.h2k', '')
                zone = archetype['weather_zone']
                
                # Créer dossier zone si nécessaire
                zone_dir = self.target_dir / f"zone_{zone}"
                zone_dir.mkdir(exist_ok=True)
                
                # Chercher résultats dans individual_stock
                source_results = None
                for h2k_dir in self.source_dir.rglob(archetype['filename']):
                    results_path = h2k_dir.parent / 'output' / arch_name / 'run' / 'results_timeseries.csv'
                    if results_path.exists():
                        source_results = results_path
                        break
                
                if source_results:
                    # Copier vers structure cible
                    target_file = zone_dir / f"{arch_name}_results.csv"
                    shutil.copy2(source_results, target_file)
                    processed_count += 1
                    self.logger.info(f"Copié {arch_name} vers zone {zone}")
                else:
                    self.logger.warning(f"Résultats non trouvés pour {arch_name}")
                
                # Log progression
                if processed_count % 10 == 0:
                    self.logger.info(f"Progression : {processed_count}/{len(selected_df)} archétypes")
            
            self.logger.info(f"\nTraitement terminé : {processed_count}/{len(selected_df)} archétypes copiés")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la copie des résultats : {str(e)}")
            return False
    
    def validate_setup(self):
        """Vérifie que la structure est correcte"""
        try:
            issues = []
            
            # 1. Vérifier dossiers zones
            zone_dirs = list(self.target_dir.glob("zone_*"))
            if not zone_dirs:
                issues.append("Aucun dossier zone trouvé")
            
            # 2. Vérifier présence de résultats
            for zone_dir in zone_dirs:
                results = list(zone_dir.glob("*_results.csv"))
                if not results:
                    issues.append(f"Aucun résultat dans {zone_dir.name}")
                else:
                    # Vérifier format des fichiers
                    for result in results:
                        try:
                            df = pd.read_csv(result)
                            if 'Time' not in df.columns or 'Energy Use: Total' not in df.columns:
                                issues.append(f"Colonnes manquantes dans {result.name}")
                        except Exception as e:
                            issues.append(f"Erreur lecture {result.name}: {str(e)}")
            
            if issues:
                self.logger.warning("Problèmes détectés :")
                for issue in issues:
                    self.logger.warning(f"- {issue}")
                return False
            
            self.logger.info("Structure validée avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la validation : {str(e)}")
            return False

if __name__ == "__main__":
    setup = InitialDataSetup()
    
    print("\nPréparation des données initiales :")
    print("-" * 50)
    
    if setup.copy_initial_results():
        print("\nCopie terminée, validation de la structure...")
        setup.validate_setup()