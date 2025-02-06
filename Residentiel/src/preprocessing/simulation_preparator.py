import pandas as pd
import logging
from pathlib import Path
import sys
import shutil
import json
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import (
    DATA_FILES, 
    PROCESSED_DATA_DIR, 
    RESULTS_DIR, 
    get_iteration_dirs,
    WORKFLOW_TEMPLATES,
    OPENSTUDIO_MEASURES,
    WEATHER_DIR
)
from config.mapping_config import ArchetypeToHPXMLMapper

class SimulationPreparator:
    """Prépare les fichiers pour simulation OpenStudio HPXML"""
    
    def __init__(self):
        """Initialise le préparateur"""
        self.logger = self._setup_logger()
        self.selected_archetypes = None
        self.mapper = ArchetypeToHPXMLMapper()
        
        # Templates
        self.base_workflow_template = WORKFLOW_TEMPLATES / "base_workflow.osw"
        self.stochastic_workflow_template = WORKFLOW_TEMPLATES / "stochastic_workflow.osw"
        
        # Chargement du mapping météo
        self.weather_mapping = self._load_weather_mapping()  # Ajout ici
        
        # État de la préparation
        self.current_iteration = 0
        self.preparation_history = {}
        self.simulation_dir = get_iteration_dirs(0)['simulation_dir'].parent  # Dossier racine des simulations
    
    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('SimulationPreparator')

    def _load_selected_archetypes(self) -> bool:
        """Charge la sélection d'archétypes"""
        try:
            selected_file = PROCESSED_DATA_DIR / 'selected_archetypes.csv'
            if not selected_file.exists():
                raise FileNotFoundError("Fichier selected_archetypes.csv non trouvé")
            
            self.selected_archetypes = pd.read_csv(selected_file)
            self.logger.info(f"Archétypes chargés : {len(self.selected_archetypes)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur chargement archétypes : {str(e)}")
            return False

    def _prepare_hpxml_parameters(self, archetype: dict, params: dict) -> dict:
        """Prépare les paramètres HPXML pour un archétype"""
        try:
            # Paramètres de base
            hpxml_params = self.mapper.convert_archetype(archetype)
            
            # S'assurer que params est un dictionnaire
            if params is None:
                params = {}
            
            # Ajouter paramètres d'optimisation avec types corrects
            if params:
                # Points de consigne (convertis en string)
                if 'heating_setpoint' in params:
                    temp_f = self.mapper.converter.c_to_f(float(params['heating_setpoint']))
                    hpxml_params['hvac_control_heating_weekday_setpoint'] = str(temp_f)
                    hpxml_params['hvac_control_heating_weekend_setpoint'] = str(temp_f)
                
                if 'cooling_setpoint' in params:
                    temp_f = self.mapper.converter.c_to_f(float(params['cooling_setpoint']))
                    hpxml_params['hvac_control_cooling_weekday_setpoint'] = str(temp_f)
                    hpxml_params['hvac_control_cooling_weekend_setpoint'] = str(temp_f)
                
                # Efficacité système (converti en float)
                if 'heating_system_efficiency' in params:
                    hpxml_params['heating_system_heating_efficiency'] = float(params['heating_system_efficiency'])

                # Résistance des murs (converti et string)
                if 'wall_assembly_r' in params:
                    r_value = self.mapper.converter.rsi_to_rvalue(float(params['wall_assembly_r']))
                    hpxml_params['wall_assembly_r'] = str(r_value)
                    
                # Infiltration (string avec unités)
                if 'air_leakage_value' in params:
                    hpxml_params['air_leakage_value'] = str(float(params['air_leakage_value']))
                    hpxml_params['air_leakage_units'] = 'ACH'
                    hpxml_params['air_leakage_house_pressure'] = 50.0

            return hpxml_params
                
        except Exception as e:
            raise Exception(f"Erreur préparation paramètres HPXML : {str(e)}")

    def _load_weather_mapping(self) -> dict:
        """Charge le mapping province/ville -> fichier EPW"""
        try:
            weather_map_file = WEATHER_DIR / "h2k_historic_epw.csv"
            if not weather_map_file.exists():
                self.logger.error(f"Fichier météo {weather_map_file} non trouvé")
                return {}
                
            weather_df = pd.read_csv(weather_map_file)
            
            # Créer un dictionnaire de mapping
            mapping = {}
            for _, row in weather_df.iterrows():
                key = (row['provinces_english'], row['cities_english'])
                # Convertir le nom du fichier ZIP en EPW
                epw_file = row['CWEC2020.zip'].replace('.zip', '.epw')
                mapping[key] = epw_file
                
            self.logger.info(f"Chargé {len(mapping)} correspondances météo")
            return mapping
            
        except Exception as e:
            self.logger.error(f"Erreur chargement mapping météo : {str(e)}")
            return {}
    
    def _get_weather_file(self, archetype: pd.Series) -> Path:
        """Détermine le fichier météo pour un archétype"""
        key = (archetype['province_std'], archetype['location_std'])
        if key not in self.weather_mapping:
            raise ValueError(f"Pas de fichier météo trouvé pour {key}")
            
        epw_file = self.weather_mapping[key]
        return WEATHER_DIR / epw_file

    def _create_workflow(self, arch_dir: Path, hpxml_params: dict, archetype: pd.Series) -> bool:
        """Crée le workflow OpenStudio pour un archétype"""
        try:
            # 1. Déterminer template à utiliser
            template_path = (self.stochastic_workflow_template 
                        if hpxml_params.get('use_stochastic_schedules', False)
                        else self.base_workflow_template)
            
            if not template_path.exists():
                template_path = WORKFLOW_TEMPLATES / "base_workflow.osw"
            
            # 2. Charger template
            with open(template_path, 'r') as f:
                workflow = json.load(f)
            
            # 3. Nettoyer les arguments du workflow de base
            base_arguments = workflow['steps'][0]['arguments']
            cleaned_arguments = {}
            
            # Ne garder que les arguments essentiels du workflow de base
            essential_args = {'hpxml_path', 'weather_station_epw_filepath'}
            for arg in essential_args:
                if arg in base_arguments:
                    cleaned_arguments[arg] = base_arguments[arg]
            
            # 4. Mettre à jour avec les arguments HPXML de l'archétype
            # Ne garder que les valeurs non-NaN
            valid_hpxml_params = {
                key: value for key, value in hpxml_params.items()
                if pd.notna(value)  # Vérifie que la valeur n'est pas NaN
            }
            cleaned_arguments.update(valid_hpxml_params)
            
            # 5. Mettre à jour le workflow
            workflow['steps'][0]['arguments'] = cleaned_arguments
            
            # 6. Ajouter le fichier météo
            weather_file = self._get_weather_file(archetype)
            workflow['steps'][0]['arguments']['weather_station_epw_filepath'] = str(weather_file)
            
            # 7. Configurer chemins de sortie
            workflow['run_directory'] = str(arch_dir / 'run')
            
            # 8. Log des différences
            if self.logger.isEnabledFor(logging.DEBUG):
                base_args_set = set(base_arguments.keys())
                final_args_set = set(cleaned_arguments.keys())
                removed_args = base_args_set - final_args_set
                added_args = final_args_set - base_args_set
                if removed_args:
                    self.logger.debug(f"Arguments supprimés: {removed_args}")
                if added_args:
                    self.logger.debug(f"Arguments ajoutés: {added_args}")
            
            # 9. Sauvegarder workflow
            workflow_path = arch_dir / 'workflow.osw'
            with open(workflow_path, 'w') as f:
                json.dump(workflow, f, indent=2)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur création workflow : {str(e)}")
            return False

    def _setup_archetype_directory(self, iteration_dir: Path, archetype_name: str) -> Path:
        """Prépare le dossier pour un archétype"""
        try:
            # Nettoyer nom fichier
            arch_name = archetype_name.replace('.H2K', '').replace('.h2k', '')
            arch_dir = iteration_dir / arch_name
            
            # Créer structure
            arch_dir.mkdir(parents=True, exist_ok=True)
            for subdir in ['run', 'output']:
                (arch_dir / subdir).mkdir(exist_ok=True)
                
            return arch_dir
            
        except Exception as e:
            self.logger.error(f"Erreur création dossier {arch_name}: {str(e)}")
            return None

    def prepare_provincial_iteration(self, iteration: int, parameters: dict = None, archetypes_df: pd.DataFrame = None) -> bool:
        """
        Prépare une itération de simulation provinciale
        Args:
            iteration: Numéro de l'itération
            parameters: Paramètres de calibration
            archetypes_df: DataFrame optionnel d'archétypes spécifiques à simuler
        """
        try:
            self.current_iteration = iteration
            paths = get_iteration_dirs(iteration)
            iteration_dir = paths['simulation_dir']
            
            # Utiliser les archétypes fournis ou charger tous les archétypes
            if archetypes_df is not None:
                self.selected_archetypes = archetypes_df
            else:
                if not self._load_selected_archetypes():
                    return False
            
            # 3. Pour chaque archétype
            processed_count = 0
            total = len(self.selected_archetypes)
            
            for _, archetype in self.selected_archetypes.iterrows():
                try:
                    # Créer dossier archétype
                    arch_dir = self._setup_archetype_directory(iteration_dir, archetype['filename'])
                    if not arch_dir:
                        continue
                    
                    # Convertir données en paramètres HPXML
                    hpxml_params = self._prepare_hpxml_parameters(archetype, parameters)
                    
                    # Créer workflow - Modification ici pour passer l'archetype
                    if not self._create_workflow(arch_dir, hpxml_params, archetype):  # <- Ajout de archetype
                        continue
                        
                    processed_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Erreur préparation {archetype['filename']}: {str(e)}")
                    continue
                
                # Log progression
                if processed_count % 5 == 0:
                    self.logger.info(f"Progression : {processed_count}/{total} archétypes")
            
            # 4. Sauvegarder métadonnées
            self._save_preparation_metadata(iteration_dir, {
                'processed': processed_count,
                'total': total,
                'success_rate': (processed_count/total) * 100 if total > 0 else 0
            })
            
            return processed_count > 0
            
        except Exception as e:
            self.logger.error(f"Erreur préparation itération {iteration}: {str(e)}")
            return False
        
    def _save_preparation_metadata(self, iteration_dir: Path, metrics: dict):
        """Sauvegarde les métadonnées de préparation"""
        metadata = {
            'iteration': self.current_iteration,
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'mapper_info': {
                'total_mappings': len(self.mapper.mappings),
                'building_types': list(self.mapper.type_mapper.get_building_types())
            }
        }
        
        metadata_file = iteration_dir / 'preparation_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)