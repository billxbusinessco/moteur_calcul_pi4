import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Callable
import pandas as pd

# Fonctions de conversion globales
def c_to_f(value: float) -> float:
    """Convertit Celsius en Fahrenheit"""
    return value * 1.8 + 32

def m2_to_ft2(value: float) -> float:
    """Convertit mètres carrés en pieds carrés"""
    return value * 10.7639

def m_to_ft(value: float) -> float:
    """Convertit mètres en pieds"""
    return value * 3.28084

def l_to_gal(value: float) -> float:
    """Convertit litres en gallons"""
    return value * 0.264172

def rsi_to_rvalue(value: float) -> float:
    """Convertit RSI (m²·K/W) en R-value (h·ft²·°F/Btu)"""
    return value * 5.678263337

def w_to_btu_hr(value: float) -> float:
    """Convertit Watts en BTU/hr"""
    return value * 3.412142

class UnitConverter:
    """Classe utilitaire pour les conversions d'unités"""
    c_to_f = staticmethod(c_to_f)
    m2_to_ft2 = staticmethod(m2_to_ft2)
    m_to_ft = staticmethod(m_to_ft)
    l_to_gal = staticmethod(l_to_gal)
    rsi_to_rvalue = staticmethod(rsi_to_rvalue)
    w_to_btu_hr = staticmethod(w_to_btu_hr)

@dataclass
class BuildingConfig:
    """Configuration pour un bâtiment HPXML"""
    building_type: str
    geometry_building_num_units: int = 1
    whole_sfa_or_mf_building_sim: bool = False

class BuildingTypeMapper:
    """Gère la détermination du type de bâtiment HPXML"""
    def __init__(self):
        self.type_mapping = {
            'House': {
                'Single Detached': 'single-family detached',
                'Double/Semi-detached': 'single-family attached',
                'Row house, end unit': 'single-family attached',
                'Row house, middle unit': 'single-family attached',
                'Mobile Home': 'manufactured home'
            },
            'Multi-unit: one unit': {
                'Apartment': 'apartment unit',
                'Apartment Row': 'apartment unit'
            }
        }

    def get_building_types(self):  # Suppression du underscore
        """Retourne tous les types de bâtiments possibles"""
        types = set()
        for main_types in self.type_mapping.values():
            types.update(main_types.values())
        return types

    def get_building_hpxml_config(self, archetype: dict) -> BuildingConfig:
        """Détermine la configuration HPXML pour un archetype"""
        house_type = archetype['houseType']
        sub_type = archetype['houseSubType']

        # 1. Maisons unifamiliales (House)
        if house_type == 'House':
            if sub_type == 'Single Detached':
                return BuildingConfig(
                    building_type='single-family detached',
                    geometry_building_num_units=1
                )
            elif sub_type == 'Mobile Home':
                return BuildingConfig(
                    building_type='manufactured home',
                    geometry_building_num_units=1
                )
            else:  # Double/Semi-detached, Row houses
                return BuildingConfig(
                    building_type='single-family attached',
                    geometry_building_num_units=2  # Double = 2 unités
                )

        # 2. Multi-unit: one unit
        if house_type == 'Multi-unit: one unit':
            return BuildingConfig(
                building_type='apartment unit',
                geometry_building_num_units=int(archetype.get('murbDwellingCount', 1))
            )

        # 3. Multi-unit: whole building
        if house_type == 'Multi-unit: whole building':
            num_units = int(archetype.get('murbDwellingCount', 1))
            if 'Duplex' in sub_type:
                return BuildingConfig(
                    building_type='single-family attached',
                    geometry_building_num_units=2
                )
            return BuildingConfig(
                building_type='apartment unit',
                geometry_building_num_units=num_units
            )

@dataclass
class HPXMLMapping:
    """Définit le mapping d'une variable archetype vers HPXML"""
    hpxml_name: str
    archetype_name: str
    conversion_func: Callable = None
    mapping_dict: Dict = None
    default_value: Any = None

class ArchetypeToHPXMLMapper:
    """Convertit les archétypes en paramètres HPXML"""
    def __init__(self):
        self.converter = UnitConverter()
        self.type_mapper = BuildingTypeMapper()
        self.mappings = self._init_mappings()

    def _init_mappings(self) -> Dict[str, HPXMLMapping]:

        def cop_to_efficiency(cop: float, system_type: str) -> float:
            """Convertit COP en SEER/EER selon le type de système
            COP -> SEER : multiplier par ~3.792
            COP -> EER : multiplier par ~3.412
            """
            if system_type in ['Central split system', 'Mini-split']:
                return cop * 3.792  # Conversion approximative COP -> SEER
            else:  # Room AC, PTAC
                return cop * 3.412  # Conversion approximative COP -> EER

        def calculate_occupants(archetype_data: dict) -> float:
            """Calcule le nombre total d'occupants (adultes + enfants)"""
            n_adults = float(archetype_data.get('numAdults', 0))
            n_children = float(archetype_data.get('numChildren', 0))
            return n_adults + n_children
    
        """Initialise tous les mappings archetype → HPXML"""
        return {

            'year_built': HPXMLMapping(
                hpxml_name='year_built',
                archetype_name='vintageExact',
                conversion_func=lambda x: int(x) if x > 0 else None  # Convertit en entier si > 0
            ),
            'geometry_unit_num_occupants': HPXMLMapping(
                hpxml_name='geometry_unit_num_occupants',
                archetype_name=['numAdults', 'numChildren'],  # Requiert les deux colonnes
                conversion_func=calculate_occupants
            ),

            # Géométrie de base
            'geometry_unit_cfa': HPXMLMapping(
                hpxml_name='geometry_unit_cfa',
                archetype_name='totFloorArea', # En m2
                conversion_func=self.converter.m2_to_ft2
            ),
            'geometry_average_ceiling_height': HPXMLMapping(
                hpxml_name='geometry_average_ceiling_height',
                archetype_name='highestCeiling', # En m
                conversion_func=self.converter.m_to_ft
            ),

            # Points de consigne (ajouter conversion string)
            'hvac_control_heating_weekday_setpoint': HPXMLMapping(
                hpxml_name='hvac_control_heating_weekday_setpoint',  
                archetype_name='dayHeatingSetPoint', # En °C
                conversion_func=lambda x: str(self.converter.c_to_f(x)),  # Ajout str()
            ),
            'hvac_control_heating_weekend_setpoint': HPXMLMapping(
                hpxml_name='hvac_control_heating_weekend_setpoint',
                archetype_name='dayHeatingSetPoint', # En °C
                conversion_func=lambda x: str(self.converter.c_to_f(x))  # Ajout str()
            ),
            'hvac_control_cooling_weekday_setpoint': HPXMLMapping(
                hpxml_name='hvac_control_cooling_weekday_setpoint',
                archetype_name='coolingSetPoint', # En °C
                conversion_func=lambda x: str(self.converter.c_to_f(x))  # Ajout str()
            ),
            'hvac_control_cooling_weekend_setpoint': HPXMLMapping(
                hpxml_name='hvac_control_cooling_weekend_setpoint',
                archetype_name='coolingSetPoint', # En °C
                conversion_func=lambda x: str(self.converter.c_to_f(x))  # Ajout str()
            ),

            # Chauffage principal
            'heating_system_type': HPXMLMapping(
                hpxml_name='heating_system_type',
                archetype_name='spaceHeatingType',
                mapping_dict={
                    'Baseboards': 'ElectricResistance',
                    'Furnace': 'Furnace',
                    'Boiler': 'Boiler',
                    'ComboHeatDhw': 'Boiler'
                }
            ),
            'heating_system_fuel': HPXMLMapping(
                hpxml_name='heating_system_fuel',
                archetype_name='spaceHeatingFuel',
                mapping_dict={
                    'Electric': 'electricity',
                    'Natural gas': 'natural gas',
                    'Oil': 'fuel oil',
                    'Mixed Wood': 'wood',
                    'Hardwood': 'wood',
                    'Wood Pellets': 'wood pellets'
                }
            ),
            # Chauffage principal (garder en float)
            'heating_system_heating_efficiency': HPXMLMapping(
                hpxml_name='heating_system_heating_efficiency',
                archetype_name='spaceHeatingEff',
                conversion_func=lambda x: float(x/100)  # Conversion explicite en float
            ),
            'heating_system_heating_capacity': HPXMLMapping(
                hpxml_name='heating_system_heating_capacity',
                archetype_name='spaceHeatingCapacity',  # En kW
                conversion_func=lambda x: self.converter.w_to_btu_hr(x * 1000)  # kW à BTU/hr
            ),

            # Climatisation
            'cooling_system_type': HPXMLMapping(
                hpxml_name='cooling_system_type',
                archetype_name='coolingEquipType',
                mapping_dict={
                    'Central split system': 'central air conditioner',
                    'Mini-split ductless': 'mini-split',
                    'Central single package system': 'packaged terminal air conditioner'
                    }
            ),
            'cooling_system_cooling_efficiency_type': HPXMLMapping(
                hpxml_name='cooling_system_cooling_efficiency_type',
                archetype_name='coolingEquipType',
                mapping_dict={
                    'Central split system': 'SEER',
                    'Mini-split ductless': 'SEER',
                    'Central single package system': 'EER'
                }
            ),
            'cooling_system_cooling_efficiency': HPXMLMapping(
                hpxml_name='cooling_system_cooling_efficiency',
                archetype_name=['coolingEff', 'coolingEquipType'],
                conversion_func=cop_to_efficiency
            ),
            'cooling_system_cooling_capacity': HPXMLMapping(
                hpxml_name='cooling_system_cooling_capacity',
                archetype_name='coolingCapacity',
                conversion_func=lambda x: self.converter.w_to_btu_hr(x * 1000)  # kW à BTU/hr
            ),

            # Pompe à chaleur
            # 'heat_pump_type': HPXMLMapping(
            #     hpxml_name='heat_pump_type',
            #     archetype_name='heatPumpType',
            #     mapping_dict={
            #         'AirHeatPump': 'air-to-air',
            #         'GroundHeatPump': 'ground-to-air',
            #         'WaterHeatPump': 'water-loop-to-air'
            #     }
            # ),


            # Eau chaude sanitaire
            'water_heater_type': HPXMLMapping(
                hpxml_name='water_heater_type',
                archetype_name='primaryDhwTankType',
                mapping_dict={
                    'Conventional tank': 'storage water heater',
                    'Conserver tank': 'storage water heater',
                    'Instantaneous': 'instantaneous water heater',
                    'Instantaneous (condensing)': 'instantaneous water heater',
                    'Induced draft fan': 'storage water heater',
                    'Conventional tank (pilot)': 'storage water heater',
                    'Direct vent (sealed)': 'storage water heater'
                }
            ),
            'water_heater_fuel_type': HPXMLMapping(
                hpxml_name='water_heater_fuel_type',
                archetype_name='primaryDhwFuel',
                mapping_dict={
                    'Electricity': 'electricity',
                    'Natural gas': 'natural gas',
                    'Oil': 'fuel oil'
                }
            ),
            'water_heater_tank_volume': HPXMLMapping(
                hpxml_name='water_heater_tank_volume',
                archetype_name='primaryDhwTankVolume',
                conversion_func=self.converter.l_to_gal
            ),

            # Ventilation mécanique
            'mech_vent_fan_type': HPXMLMapping(
                hpxml_name='mech_vent_fan_type',
                archetype_name='hrvPresent',
                mapping_dict={
                    True: 'heat recovery ventilator',
                    False: 'none'
                }
            ),
            'mech_vent_flow_rate': HPXMLMapping(
                hpxml_name='mech_vent_flow_rate',
                archetype_name='hrvTotalSupply',
                conversion_func=lambda x: x * 2.11888  # L/s à CFM
            ),
                    
            # Infiltration d'air

            'air_leakage_value': HPXMLMapping(
                hpxml_name='air_leakage_value',
                archetype_name='ach',  # ACH à 50 Pascals
                mapping_dict=None  # Valeur directe
            ),

            # Murs
            # 'wall_type': HPXMLMapping(
            #     hpxml_name='wall_type',
            #     archetype_name='dominantWallType',
            #     mapping_dict={
            #         'WoodStud': 'WoodStud',
            #         'SteelFrame': 'SteelFrame',
            #         'ConcreteMasonryUnit': 'ConcreteMasonryUnit',
            #         'StructuralInsulatedPanel': 'StructuralInsulatedPanel',
            #         'InsulatedConcreteForms': 'InsulatedConcreteForms'
            #     }
            # ),

            'wall_assembly_r': HPXMLMapping(
                hpxml_name='wall_assembly_r',
                archetype_name='dominantWallRVal',
                conversion_func=self.converter.rsi_to_rvalue  # Conversion RSI à R-value
            ),

            # Fenêtres
            'window_ufactor': HPXMLMapping(
                hpxml_name='window_ufactor',
                archetype_name='dominantWindowRVal',
                conversion_func=lambda x: 1.0 / self.converter.rsi_to_rvalue(x)  # Conversion RSI à U-factor
            ),

            'window_shgc': HPXMLMapping(
                hpxml_name='window_shgc',
                archetype_name='dominantWindowShgc',
                mapping_dict=None  # Valeur directe
            ),

            # Plafond/Toit
            'ceiling_assembly_r': HPXMLMapping(
                hpxml_name='ceiling_assembly_r',
                archetype_name= 'dominantCeilingRVal',
                conversion_func=self.converter.rsi_to_rvalue  # Conversion RSI à R-value
            ),

            # Plancher/Dalle
            # 'slab_type': HPXMLMapping(
            #     hpxml_name='slab_type',
            #     archetype_name='dominantSlabType',
            #     mapping_dict={
            #         'slab-on-grade': 'SlabOnGrade'
            #     }
            # ),

            'slab_perimeter_insulation_r': HPXMLMapping(
                hpxml_name='slab_perimeter_insulation_r',
                archetype_name='dominantSlabRVal',
                conversion_func=self.converter.rsi_to_rvalue
            ),

            # Fondation
            # 'foundation_type': HPXMLMapping(
            #     hpxml_name='foundation_type',
            #     archetype_name='basementConfig',
            #     mapping_dict={
            #         'BCCB_4': 'ConditionedBasement', 
            #         'SCN_17': 'UnconditionedBasement'
            #     }
            # ),

            'foundation_wall_assembly_r': HPXMLMapping(
                hpxml_name='foundation_wall_assembly_r',
                archetype_name='dominantBasementWallRVal',
                conversion_func=self.converter.rsi_to_rvalue
            ),

            # Surface vitrée
            # 'window_area_front': HPXMLMapping(
            #     hpxml_name='window_area_front',
            #     archetype_name='windowAreaS',  # Sud est considéré comme façade avant
            #     conversion_func=self.converter.m2_to_ft2
            # ),

            # 'window_area_back': HPXMLMapping(
            #     hpxml_name='window_area_back',
            #     archetype_name='windowAreaN',  # Nord est considéré comme façade arrière
            #     conversion_func=self.converter.m2_to_ft2
            # ),

            # 'window_area_left': HPXMLMapping(
            #     hpxml_name='window_area_left',
            #     archetype_name='windowAreaW',  # Ouest est considéré comme côté gauche
            #     conversion_func=self.converter.m2_to_ft2
            # ),

            # 'window_area_right': HPXMLMapping(
            #     hpxml_name='window_area_right',
            #     archetype_name='windowAreaE',  # Est est considéré comme côté droit
            #     conversion_func=self.converter.m2_to_ft2
            # ),

            # Door
            'door_rvalue': HPXMLMapping(
                hpxml_name='door_rvalue',
                archetype_name='dominantDoorRVal',
                conversion_func=self.converter.rsi_to_rvalue  # Conversion RSI à R-value
            ),
        }

    def convert_archetype(self, archetype: dict) -> dict:
        """Convertit un archetype en paramètres HPXML"""
        try:
            # 1. Configuration du bâtiment
            building_config = self.type_mapper.get_building_hpxml_config(archetype)

            # 2. Initialiser paramètres HPXML
            hpxml_params = {
                'geometry_unit_type': building_config.building_type,
                'geometry_building_num_units': building_config.geometry_building_num_units,  # Ajout ici
                'air_leakage_units': 'ACH',
                'air_leakage_house_pressure': 50.0
            }

            # Ajouter air_leakage_type pour les bâtiments qui en ont besoin
            if building_config.building_type in ['single-family attached', 'apartment unit']:
                hpxml_params['air_leakage_type'] = 'unit total'

            # Ajouter le geometry_unit_num_floors_above_grade pour les appartements unit
            if building_config.building_type == 'apartment unit':
                hpxml_params['geometry_unit_num_floors_above_grade'] = 1

            # 3. Ajouter configuration building sim si nécessaire
            if building_config.whole_sfa_or_mf_building_sim:
                hpxml_params.update({
                    'whole_sfa_or_mf_building_sim': True
                })

            # 4. Appliquer les autres mappings
            for mapping in self.mappings.values():
                try:
                    if isinstance(mapping.archetype_name, list):
                        # Cas où on a besoin de plusieurs valeurs d'entrée
                        values = [archetype.get(name) for name in mapping.archetype_name]
                        if any(pd.isna(v) for v in values):
                            continue  # Skip si une des valeurs est NaN
                        value = mapping.conversion_func(*values)
                    else:
                        # Cas simple avec une seule valeur d'entrée
                        if mapping.archetype_name not in archetype:
                            continue
                        value = archetype[mapping.archetype_name]
                        if pd.isna(value):
                            continue  # Skip si la valeur est NaN
                        
                        # Vérification spéciale pour ceiling_assembly_r
                        if mapping.hpxml_name == 'ceiling_assembly_r' and value == 0:
                            continue  # Skip si la valeur est 0
                            
                        if mapping.mapping_dict is not None:
                            value = mapping.mapping_dict[value]
                        
                        if mapping.conversion_func is not None:
                            value = mapping.conversion_func(value)
                    
                    # N'ajouter la valeur que si elle n'est pas NaN
                    if not pd.isna(value):
                        hpxml_params[mapping.hpxml_name] = value

                except (KeyError, ValueError, TypeError) as e:
                    if mapping.default_value is not None:
                        hpxml_params[mapping.hpxml_name] = mapping.default_value

            return hpxml_params

        except Exception as e:
            raise Exception(f"Erreur conversion archetype: {str(e)}")