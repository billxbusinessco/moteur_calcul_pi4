import pandas as pd
import logging
from pathlib import Path
import sys
import shutil
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import json

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import (
    DATA_FILES, 
    PROCESSED_DATA_DIR, 
    RESULTS_DIR, 
    get_iteration_dirs,
    RESULTS_STRUCTURE
)

class SimulationPreparator:
    def __init__(self):
        """Initialise le préparateur de simulations"""
        self.logger = self._setup_logger()
        self.selected_archetypes = None
        self.simulation_dir = RESULTS_STRUCTURE['SIMULATIONS_DIR']  # Utiliser RESULTS_STRUCTURE
        self.h2k_stock_dir = DATA_FILES['H2K_STOCK_DIR']
        self.current_iteration = 0
        self.parameter_history = {}

        # Définition des paramètres à calibrer
        self.parameters = {
            'heating_setpoint': {
                'base_path': './/MainFloors',
                'attribute': 'daytimeHeatingSetPoint',
                'range': (18, 22),
                'default': 21,
                'description': 'Point de consigne chauffage (°C)'
            },
            'cooling_setpoint': {
                'base_path': './/MainFloors',
                'attribute': 'coolingSetPoint',
                'range': (23, 27),
                'default': 25,
                'description': 'Point de consigne climatisation (°C)'
            }
        }

    def _load_selected_archetypes(self) -> bool:
        """Charge les archétypes sélectionnés"""
        try:
            selected_file = PROCESSED_DATA_DIR / 'selected_archetypes.csv'
            if not selected_file.exists():
                raise FileNotFoundError("Fichier selected_archetypes.csv non trouvé")
            
            self.selected_archetypes = pd.read_csv(selected_file)
            self.logger.info(f"Archétypes chargés : {len(self.selected_archetypes)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement des archétypes : {str(e)}")
            return False
            
    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('SimulationPreparator')

    def get_parameter_paths(self) -> dict:
        """Retourne les chemins XML validés pour les paramètres"""
        return self.parameters

    def prepare_provincial_iteration(self, iteration: int, parameters: dict = None) -> bool:
        try:
            self.current_iteration = iteration
            paths = get_iteration_dirs(iteration)
            iteration_dir = RESULTS_STRUCTURE['SIMULATIONS_DIR'] / f'iteration_{iteration}'
            
            # Créer structure pour l'itération
            if not self._setup_iteration_directory(iteration):
                return False

            # Charger les archétypes si nécessaire
            if self.selected_archetypes is None:
                if not self._load_selected_archetypes():
                    return False

            # Valider les paramètres si fournis
            if parameters:
                if not self.validate_modifications(parameters):
                    return False

            # Pour chaque archétype
            processed = 0
            for _, archetype in self.selected_archetypes.iterrows():
                if self._prepare_archetype(archetype, iteration_dir, parameters):
                    processed += 1

                # Log progression
                if processed % 10 == 0:
                    self.logger.info(f"Progression : {processed}/{len(self.selected_archetypes)} archétypes")

            return True

        except Exception as e:
            self.logger.error(f"Erreur préparation itération {iteration}: {str(e)}")
            return False

    def validate_modifications(self, parameters: dict) -> bool:
        """
        Vérifie que les paramètres sont valides
        """
        try:
            for param_name, param_value in parameters.items():
                if param_name not in self.parameters:
                    self.logger.error(f"Paramètre inconnu : {param_name}")
                    return False
                
                param_info = self.parameters[param_name]
                min_val, max_val = param_info['range']
                
                if not min_val <= float(param_value) <= max_val:
                    self.logger.error(f"Valeur {param_value} hors limites [{min_val}, {max_val}] pour {param_name}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur validation paramètres : {str(e)}")
            return False
        
    def _setup_iteration_directory(self, iteration: int) -> bool:
        """
        Prépare la structure de dossiers pour une nouvelle itération
        """
        try:
            iteration_dir = self.simulation_dir / f'iteration_{iteration}'
            iteration_dir.mkdir(parents=True, exist_ok=True)

            # Sauvegarder métadonnées de l'itération
            metadata = {
                'iteration': iteration,
                'timestamp': datetime.now().isoformat(),
                'status': 'initialized',
                'parameters': {}
            }
            
            with open(iteration_dir / 'iteration_metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2)

            return True

        except Exception as e:
            self.logger.error(f"Erreur création structure itération {iteration}: {str(e)}")
            return False

    def _prepare_archetype(self, archetype: pd.Series, iteration_dir: Path, parameters: dict = None) -> bool:
        """
        Prépare un archétype spécifique pour la simulation
        """
        try:
            arch_name = archetype['filename'].replace('.H2K', '').replace('.h2k', '')
            arch_dir = iteration_dir / arch_name
            arch_dir.mkdir(parents=True, exist_ok=True)

            # Copier les fichiers de base
            if self.current_iteration == 0:
                source_dir = None
                for path in self.h2k_stock_dir.rglob(archetype['filename']):
                    source_dir = path.parent
                    break

                if not source_dir:
                    self.logger.error(f"Source non trouvée : {archetype['filename']}")
                    return False

                # Copier tous les fichiers du dossier source
                for file in source_dir.glob('*'):
                    if file.is_file():
                        shutil.copy2(file, arch_dir)
            else:
                # Copier depuis l'itération précédente
                prev_dir = self.simulation_dir / f'iteration_{self.current_iteration-1}' / arch_name
                if prev_dir.exists():
                    for file in prev_dir.glob('*'):
                        if file.is_file():
                            shutil.copy2(file, arch_dir)
                else:
                    self.logger.error(f"Dossier précédent non trouvé : {prev_dir}")
                    return False

            # Modifier les paramètres si nécessaire
            if parameters:
                if not self._modify_parameters(arch_dir, parameters):
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Erreur préparation {arch_name}: {str(e)}")
            return False

    def _modify_parameters(self, arch_dir: Path, parameters: dict) -> bool:
        """
        Modifie les paramètres d'un fichier H2K
        """
        try:
            h2k_file = next(arch_dir.glob('*.H2K'))
            if not h2k_file.exists():
                raise FileNotFoundError(f"Fichier H2K non trouvé dans {arch_dir}")

            # Parser le XML
            tree = ET.parse(h2k_file)
            root = tree.getroot()

            changes = {}
            for param_name, param_value in parameters.items():
                param_info = self.parameters[param_name]
                
                # Trouver l'élément
                element = root.find(param_info['base_path'])
                if element is None:
                    self.logger.warning(f"Chemin non trouvé pour {param_name}")
                    continue

                # Sauvegarder l'ancienne valeur et modifier
                old_value = element.get(param_info['attribute'])
                element.set(param_info['attribute'], str(param_value))
                
                changes[param_name] = {
                    'old_value': old_value,
                    'new_value': str(param_value),
                    'description': param_info['description']
                }
                
                self.logger.info(f"Modifié {param_name}: {old_value} -> {param_value}")

            # Sauvegarder le fichier modifié
            tree.write(h2k_file)
            
            # Tracker les changements
            self._track_parameter_change(h2k_file.stem, changes)
            
            return True

        except Exception as e:
            self.logger.error(f"Erreur modification paramètres: {str(e)}")
            return False

    def _track_parameter_change(self, archetype: str, changes: dict) -> None:
        """
        Enregistre l'historique des modifications de paramètres
        """
        if archetype not in self.parameter_history:
            self.parameter_history[archetype] = []
            
        self.parameter_history[archetype].append({
            'iteration': self.current_iteration,
            'timestamp': datetime.now().isoformat(),
            'changes': changes
        })
        
        # Sauvegarder l'historique
        history_file = self.simulation_dir / 'parameter_history.json'
        with open(history_file, 'w') as f:
            json.dump(self.parameter_history, f, indent=2)

if __name__ == "__main__":
    preparator = SimulationPreparator()
    
    print("\nTest du SimulationPreparator :")
    print("-" * 50)
    
    # Test avec paramètres simples
    test_params = {
        'heating_setpoint': 19.5,
        'cooling_setpoint': 25.5
    }
    
    # 1. Préparation itération 0 (base)
    print("\n1. Test préparation itération initiale...")
    if preparator.prepare_provincial_iteration(0):
        print("Itération 0 préparée avec succès")
        
        # 2. Test avec modifications
        print("\n2. Test préparation itération avec modifications...")
        if preparator.prepare_provincial_iteration(1, test_params):
            print("\nItération 1 préparée avec succès")
            print("\nParamètres appliqués :")
            for param, value in test_params.items():
                print(f"- {param}: {value}")