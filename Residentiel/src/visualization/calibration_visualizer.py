import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import logging
from pathlib import Path
import sys
import json
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import RESULTS_DIR

class CalibrationVisualizer:
    """Visualisation temps réel du processus de calibration"""
    def __init__(self):
        self.logger = self._setup_logger()
        self.fig = None
        self.axes = {}
        
        # Stockage des données
        self.history = {
            'iterations': [],
            'scores': [],
            'parameters': {},
            'convergence': []
        }
        
        # État
        self.is_initialized = False
        self.animation = None

    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('CalibrationVisualizer')

    def setup_display(self, parameters: list):
        """
        Initialise l'affichage avec les paramètres à suivre
        """
        plt.ion()  # Mode interactif
        self.fig = plt.figure(figsize=(15, 10))
        
        # Graphique des scores
        self.axes['score'] = self.fig.add_subplot(221)
        self.axes['score'].set_title('Évolution du Score')
        self.axes['score'].set_xlabel('Itération')
        self.axes['score'].set_ylabel('Score')
        
        # Graphique des paramètres
        self.axes['params'] = self.fig.add_subplot(222)
        self.axes['params'].set_title('Évolution des Paramètres')
        self.axes['params'].set_xlabel('Itération')
        self.axes['params'].set_ylabel('Valeur')
        
        # Initialiser le suivi des paramètres
        self.history['parameters'] = {param: [] for param in parameters}
        
        # Graphique de convergence
        self.axes['convergence'] = self.fig.add_subplot(223)
        self.axes['convergence'].set_title('Critères de Convergence')
        
        # Graphique comparaison Hydro-Québec
        self.axes['comparison'] = self.fig.add_subplot(224)
        self.axes['comparison'].set_title('Comparaison avec Hydro-Québec')
        
        plt.tight_layout()
        self.is_initialized = True

    def update(self, iteration_data: dict):
        """
        Met à jour les visualisations avec les nouvelles données
        """
        if not self.is_initialized:
            self.setup_display(list(iteration_data['parameters'].keys()))

        # Mettre à jour l'historique
        self.history['iterations'].append(iteration_data['iteration'])
        self.history['scores'].append(iteration_data['score'])
        
        for param, value in iteration_data['parameters'].items():
            self.history['parameters'][param].append(value)
        
        self.history['convergence'].append(iteration_data.get('converged', False))
        
        # Mettre à jour les graphiques
        self._update_score_plot()
        self._update_params_plot()
        self._update_convergence_plot()
        self._update_comparison_plot(iteration_data.get('comparison', None))
        
        plt.draw()
        plt.pause(0.1)

    def _update_score_plot(self):
        """Met à jour le graphique des scores"""
        ax = self.axes['score']
        ax.clear()
        ax.plot(self.history['iterations'], self.history['scores'], 'b-')
        ax.set_title('Évolution du Score')
        ax.set_xlabel('Itération')
        ax.set_ylabel('Score')
        ax.grid(True)

    def _update_params_plot(self):
        """Met à jour le graphique des paramètres"""
        ax = self.axes['params']
        ax.clear()
        
        for param, values in self.history['parameters'].items():
            ax.plot(self.history['iterations'], values, 'o-', label=param)
        
        ax.set_title('Évolution des Paramètres')
        ax.set_xlabel('Itération')
        ax.set_ylabel('Valeur')
        ax.legend()
        ax.grid(True)

    def _update_convergence_plot(self):
        """Met à jour le graphique de convergence"""
        ax = self.axes['convergence']
        ax.clear()
        
        convergence_rate = sum(self.history['convergence']) / len(self.history['convergence'])
        ax.bar(['Convergence'], [convergence_rate])
        ax.set_ylim(0, 1)
        ax.set_title('Taux de Convergence')

    def _update_comparison_plot(self, comparison_data):
        """Met à jour le graphique de comparaison"""
        if comparison_data is None:
            return
                
        ax = self.axes['comparison']
        ax.clear()
        
        # Comparaison des profils horaires
        if 'hydro' in comparison_data and 'simulation' in comparison_data:
            # Convertir en valeurs horaires uniquement
            hydro_values = comparison_data['hydro'].values
            sim_values = comparison_data['simulation'].values
            
            # Créer un index horaire de 0 à 8759 (8760 heures)
            hours = range(len(hydro_values))
            
            ax.plot(hours, hydro_values, 'b-', label='Hydro-Québec', alpha=0.6)
            ax.plot(hours, sim_values, 'r-', label='Simulation', alpha=0.6)
            ax.set_title('Comparaison des Profils')
            ax.set_xlabel('Heure')
            ax.set_ylabel('Consommation (kWh)')
            ax.legend()
            ax.grid(True)

    def save_results(self):
        """Sauvegarde les résultats de visualisation"""
        output_dir = RESULTS_DIR / 'visualization'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Sauvegarder l'image finale
        plt.savefig(output_dir / f'calibration_results_{datetime.now():%Y%m%d_%H%M%S}.png')
        
        # Sauvegarder les données
        history_data = {
            'iterations': self.history['iterations'],
            'scores': self.history['scores'],
            'parameters': self.history['parameters'],
            'convergence': self.history['convergence']
        }
        
        with open(output_dir / f'calibration_history_{datetime.now():%Y%m%d_%H%M%S}.json', 'w') as f:
            json.dump(history_data, f, indent=2)

    def keep_display_open(self):
        """Garde la fenêtre ouverte"""
        if self.is_initialized:
            plt.show(block=True)

if __name__ == "__main__":
    visualizer = CalibrationVisualizer()
    
    # Simuler quelques itérations
    test_params = ['heating_setpoint', 'cooling_setpoint']
    visualizer.setup_display(test_params)
    
    try:
        for i in range(10):
            data = {
                'iteration': i,
                'score': np.random.rand() * (10 - i) / 10,
                'parameters': {
                    'heating_setpoint': 21 + np.random.rand(),
                    'cooling_setpoint': 25 + np.random.rand()
                },
                'converged': i > 7,
                'comparison': {
                    'hydro': np.sin(np.linspace(0, 2*np.pi, 24)) + np.random.rand(24)*0.1,
                    'simulation': np.sin(np.linspace(0, 2*np.pi, 24)) + np.random.rand(24)*0.1
                }
            }
            
            visualizer.update(data)
            plt.pause(0.5)
            
        # Garder la fenêtre ouverte
        visualizer.keep_display_open()
        
    except KeyboardInterrupt:
        print("\nArrêt de la visualisation")
        visualizer.save_results()