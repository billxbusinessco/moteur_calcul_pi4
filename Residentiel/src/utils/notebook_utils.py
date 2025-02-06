import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
import importlib

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import DATA_FILES, PROCESSED_DATA_DIR, RESULTS_DIR

class NotebookHelper:
    def __init__(self):
        """Initialise le helper pour les notebooks"""
        self.data_dir = Path(DATA_FILES['ARCHETYPES_FILE']).parent
        
        # Information sur les zones
        self.zone_info = {
            448.0: {'station': 'HIGH FALLS', 'count': 35, 'color': '#1f77b4'},
            462.0: {'station': 'LAC BENOIT', 'count': 7, 'color': '#ff7f0e'},
            477.0: {'station': 'MONTREAL INTL A', 'count': 734, 'color': '#2ca02c'},
            479.0: {'station': 'MONTREAL-ST-HUBERT', 'count': 67, 'color': '#d62728'},
            491.0: {'station': 'QUEBEC INTL A', 'count': 801, 'color': '#9467bd'}
        }
        
    def load_archetype_data(self) -> pd.DataFrame:
        """
        Charge les données des archétypes
        Returns:
            DataFrame: Données des archétypes
        """
        try:
            df = pd.read_csv(DATA_FILES['ARCHETYPES_FILE'])
            print(f"Archétypes chargés : {len(df)} entrées")
            return df
        except Exception as e:
            print(f"Erreur chargement archétypes : {e}")
            return pd.DataFrame()
    
    def load_building_stock(self) -> pd.DataFrame:
        """
        Charge les données du parc immobilier
        Returns:
            DataFrame: Données du parc immobilier
        """
        try:
            df = pd.read_csv(DATA_FILES['RESIDENTIAL_DATA_FILE'])
            print(f"Bâtiments chargés : {len(df)} entrées")
            return df
        except Exception as e:
            print(f"Erreur chargement bâtiments : {e}")
            return pd.DataFrame()

    def load_hydro_data(self, year: int = 2022) -> pd.DataFrame:
        """
        Charge les données Hydro-Québec
        Args:
            year: Année désirée
        Returns:
            DataFrame: Données de consommation
        """
        try:
            file_path = DATA_FILES['HYDRO_QUEBEC_FILES'][year]
            df = pd.read_csv(file_path)
            df['Intervalle15Minutes'] = pd.to_datetime(df['Intervalle15Minutes'])
            print(f"Données Hydro-Q {year} chargées : {len(df)} entrées")
            return df
        except Exception as e:
            print(f"Erreur chargement Hydro-Q : {e}")
            return pd.DataFrame()

    def plot_zone_distribution(self, data: pd.DataFrame) -> go.Figure:
        """
        Crée un graphique de distribution par zone
        Args:
            data: DataFrame avec colonne 'weather_zone'
        """
        try:
            zone_counts = data['weather_zone'].value_counts().sort_index()
            
            # Créer le graphique
            fig = go.Figure(data=[
                go.Bar(
                    x=[f"Zone {int(zone)} <br>{self.zone_info[zone]['station']}" 
                       for zone in zone_counts.index],
                    y=zone_counts.values,
                    text=zone_counts.values,
                    textposition='auto',
                    marker_color=[self.zone_info[zone]['color'] 
                                for zone in zone_counts.index]
                )
            ])
            
            # Mise en page
            fig.update_layout(
                title='Distribution par Zone Climatique',
                xaxis_title='Zone',
                yaxis_title='Nombre d\'archétypes',
                showlegend=False,
                height=500
            )
            
            return fig
            
        except Exception as e:
            print(f"Erreur création graphique : {e}")
            return None

    def plot_temporal_profile(self, hydro_data: pd.DataFrame) -> go.Figure:
        """
        Crée un graphique du profil temporel de consommation
        Args:
            hydro_data: DataFrame avec données Hydro-Q
        """
        try:
            fig = go.Figure()
            
            # Ajouter la série temporelle
            fig.add_trace(go.Scatter(
                x=hydro_data['Intervalle15Minutes'],
                y=hydro_data['energie_sum_secteur'],
                mode='lines',
                name='Consommation',
                hovertemplate=(
                    'Date: %{x}<br>'
                    'Consommation: %{y:.0f} kWh<br>'
                    '<extra></extra>'
                )
            ))
            
            # Mise en page
            fig.update_layout(
                title='Profil de Consommation',
                xaxis_title='Date',
                yaxis_title='Consommation (kWh)',
                height=500,
                hovermode='x unified'
            )
            
            return fig
            
        except Exception as e:
            print(f"Erreur création graphique : {e}")
            return None
    
    def plot_weather_zones_map(self) -> go.Figure:
        """
        Crée une carte du Québec avec les zones météo
        L'intensité des couleurs représente le nombre d'archétypes
        """
        try:
            # Vérifier si geopandas est disponible
            gpd = importlib.import_module('geopandas')
            
            # Lire le shapefile des MRC
            mrc_gdf = gpd.read_file(DATA_FILES['MRC_SHP_FILE'])
            
            # Calculer l'intensité relative pour chaque zone
            max_count = max(info['count'] for info in self.zone_info.values())
            min_count = min(info['count'] for info in self.zone_info.values())
            
            def get_color_with_intensity(base_color: str, count: int) -> str:
                # Normaliser le nombre d'archétypes entre 0.3 et 1.0
                # On garde un minimum de 0.3 pour que les zones restent visibles
                intensity = 0.3 + 0.7 * (count - min_count) / (max_count - min_count)
                
                # Convertir la couleur hex en RGB
                rgb = tuple(int(base_color[i:i+2], 16) for i in (1, 3, 5))
                
                # Créer une couleur RGBA
                return f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {intensity})'
            
            # Créer la figure
            fig = go.Figure()
            
            # Pour chaque zone météo
            for zone, info in self.zone_info.items():
                zone_data = mrc_gdf[mrc_gdf['weather_zo'] == zone]
                base_color = info['color'].lstrip('#')
                
                # Collecter toutes les coordonnées pour cette zone
                x_all = []
                y_all = []
                names = []
                
                # Pour chaque MRC dans la zone
                for _, row in zone_data.iterrows():
                    # Gérer MultiPolygons et Polygons
                    if row.geometry.type == 'MultiPolygon':
                        polygon = max(row.geometry.geoms, key=lambda x: x.area)
                    else:
                        polygon = row.geometry
                        
                    # Extraire les coordonnées
                    x, y = polygon.exterior.xy
                    x_all.extend(list(x) + [None])
                    y_all.extend(list(y) + [None])
                    names.extend([row["CDNAME"]] * (len(x) + 1))
                
                # Ajouter la zone avec la couleur ajustée selon le nombre d'archétypes
                fig.add_trace(go.Scatter(
                    x=x_all,
                    y=y_all,
                    fill='toself',
                    fillcolor=get_color_with_intensity(base_color, info['count']),
                    line=dict(color='white', width=0.5),
                    mode='lines',
                    name=(
                        f"Zone {int(zone)} - {info['station']}<br>"
                        f"({info['count']} archétypes)"
                    ),
                    showlegend=True,
                    hovertemplate=(
                        'MRC: %{customdata}<br>'
                        f'Zone: {int(zone)} ({info["station"]})<br>'
                        f'Nombre d\'archétypes: {info["count"]}'
                        '<extra></extra>'
                    ),
                    customdata=names
                ))

            # Mise en page
            fig.update_layout(
                title={
                    'text': 'Distribution des Archétypes par Zone Météorologique',
                    'y': 0.95,
                    'x': 0.5,
                    'xanchor': 'center',
                    'yanchor': 'top',
                    'font': dict(size=20)
                },
                showlegend=True,
                legend_title_text='Zones et Nombre d\'archétypes',
                width=1000,
                height=800,
                geo=dict(
                    scope='north america',
                    showland=True,
                    landcolor='rgb(240, 240, 240)',
                    showocean=True,
                    oceancolor='rgb(220, 240, 255)',
                    projection=dict(
                        type='mercator',
                        scale=20
                    ),
                    center=dict(
                        lat=48,
                        lon=-72
                    )
                )
            )

            # Ajouter une note explicative
            fig.add_annotation(
                text=(
                    'Note: L\'intensité des couleurs représente le nombre d\'archétypes<br>'
                    'Plus la couleur est foncée, plus il y a d\'archétypes'
                ),
                xref='paper',
                yref='paper',
                x=0,
                y=-0.1,
                showarrow=False,
                font=dict(size=12),
                align='left'
            )

            return fig
            
        except Exception as e:
            print(f"Erreur création carte : {e}")
            print("Affichage d'une visualisation alternative...")
            return self.plot_zone_distribution(self.load_archetype_data())