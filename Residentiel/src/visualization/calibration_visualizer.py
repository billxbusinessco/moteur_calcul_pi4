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

from config.paths_config import RESULTS_STRUCTURE

class CalibrationVisualizer:
    """Visualisation temps réel du processus de calibration"""
    def __init__(self):
        self.logger = self._setup_logger()
        self.fig = None
        self.axes = {}
        
        # Créer le dossier de visualisation
        self.output_dir = RESULTS_STRUCTURE['VISUALIZATION_DIR']
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Stockage des données enrichi
        self.history = {
            'iterations': [],
            'scores': [],
            'parameters': {},
            'convergence': [],
            'metrics': [],
            'sensitivities': []
        }
        
        # État
        self.is_initialized = False
        self.animation = None

    def _setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('CalibrationVisualizer')

    def setup_display(self, parameters: list):
        """Initialise l'affichage avec les paramètres à suivre"""
        plt.ion()  # Mode interactif
        
        # Figure 1 : Calibration temps réel
        self.fig1 = plt.figure(figsize=(15, 10))
        
        # Graphique des scores
        self.axes['score'] = self.fig1.add_subplot(221)
        self.axes['score'].set_title('Évolution du Score')
        self.axes['score'].set_xlabel('Itération')
        self.axes['score'].set_ylabel('Score')
        
        # Graphique des paramètres
        self.axes['params'] = self.fig1.add_subplot(222)
        self.axes['params'].set_title('Évolution des Paramètres')
        self.axes['params'].set_xlabel('Itération')
        self.axes['params'].set_ylabel('Valeur Normalisée')
        
        # Graphique de convergence
        self.axes['convergence'] = self.fig1.add_subplot(223)
        self.axes['convergence'].set_title('Critères de Convergence')
        
        # Graphique profil temps réel
        self.axes['profile'] = self.fig1.add_subplot(224)
        self.axes['profile'].set_title('Comparaison Profils (48h)')
        
        plt.tight_layout()
        
        # Figure 2 : Comparaison annuelle
        self.fig2 = plt.figure(figsize=(12, 6))
        self.axes['annual'] = self.fig2.add_subplot(111)
        self.axes['annual'].set_title('Comparaison Consommation Annuelle')
        
        # Figure 3 : Analyse détaillée
        self.fig3 = plt.figure(figsize=(15, 10))
        
        # Impact des paramètres
        self.axes['sensitivity'] = self.fig3.add_subplot(221)
        self.axes['sensitivity'].set_title('Impact des Paramètres')
        
        # Évolution des métriques
        self.axes['metrics'] = self.fig3.add_subplot(222)
        self.axes['metrics'].set_title('Évolution des Métriques')
        
        plt.tight_layout()
        self.is_initialized = True

    def _update_comparison_plot(self, comparison_data):
        """Met à jour les graphiques de comparaison"""
        if comparison_data is None:
            return
                
        if 'hydro' in comparison_data and 'simulation' in comparison_data:
            # 1. Profil d'une semaine (milieu d'hiver)
            ax = self.axes['profile']
            ax.clear()
            
            # Prendre une semaine au milieu de l'hiver (168 heures)
            start_idx = 360  # 15 janvier approximativement
            hydro_week = comparison_data['hydro'].iloc[start_idx:start_idx+168]
            sim_week = comparison_data['simulation'].iloc[start_idx:start_idx+168]
            
            hours = range(168)  # Une semaine = 168 heures
            
            # Une seule ligne pour chaque
            ax.plot(hours, hydro_week.values, 'b-', label='Hydro-Québec', alpha=0.6)
            ax.plot(hours, sim_week.values, 'r-', label='Simulation', alpha=0.6)
            
            # Ajouter des repères pour les jours
            day_ticks = range(0, 169, 24)  # Marquer chaque jour
            day_labels = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim', 'Lun']
            ax.set_xticks(day_ticks)
            ax.set_xticklabels(day_labels)
            
            ax.set_title('Profil Semaine (15-21 janvier)')
            ax.set_xlabel('Jour')
            ax.set_ylabel('Consommation (kWh)')
            ax.legend()
            ax.grid(True)
            
            # 2. Comparaison horaire annuelle (reste inchangé)
            ax = self.axes['annual']
            ax.clear()
            
            # Utiliser toutes les heures de l'année
            hours_year = range(8760)
            
            # Tracer les données horaires complètes
            ax.plot(hours_year, comparison_data['hydro'].values, 'b-', label='Hydro-Québec', alpha=0.4, linewidth=0.5)
            ax.plot(hours_year, comparison_data['simulation'].values, 'r-', label='Simulation', alpha=0.4, linewidth=0.5)
            
            ax.set_title('Consommation Horaire Annuelle')
            ax.set_xlabel('Heure de l\'année')
            ax.set_ylabel('Consommation (kWh)')
            
            # Ajouter des repères pour les mois
            month_ticks = range(0, 8760, 730)
            month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
            ax.set_xticks(month_ticks)
            ax.set_xticklabels(month_labels, rotation=45)
            
            ax.legend()
            ax.grid(True)

    def _update_convergence_plot(self):
        """Met à jour le graphique de convergence"""
        ax = self.axes['convergence']
        ax.clear()
        
        # Pour chaque itération, tracer le taux de convergence
        convergence_values = [0]  # Commencer à 0
        for i in range(1, len(self.history['iterations'])):
            # Calculer le taux basé sur la variation du score
            score_variation = abs(self.history['scores'][i] - self.history['scores'][i-1])
            is_converged = score_variation < 0.01  # Seuil de convergence
            convergence_values.append(1.0 if is_converged else 0.0)
        
        # Tracer la courbe de convergence
        ax.plot(self.history['iterations'], convergence_values, 'b-')
        ax.set_title('Taux de Convergence')
        ax.set_xlabel('Itération')
        ax.set_ylabel('Convergence (0/1)')
        ax.grid(True)
        ax.set_ylim(-0.1, 1.1)  # Pour bien voir les valeurs 0 et 1

    def _update_sensitivity_plot(self):
        """Met à jour le graphique d'impact des paramètres"""
        if not self.history['sensitivities']:
            return
                
        ax = self.axes['sensitivity']
        ax.clear()
        
        # Prendre la dernière entrée non vide des sensitivités
        last_sensitivity = None
        for sensitivity in reversed(self.history['sensitivities']):
            if sensitivity:  # Si non vide
                last_sensitivity = sensitivity
                break
                
        if last_sensitivity:
            # Trier par impact décroissant
            sorted_impacts = sorted(last_sensitivity.items(), key=lambda x: x[1], reverse=True)
            params = [item[0] for item in sorted_impacts]
            impacts = [item[1] for item in sorted_impacts]
            
            # Tracer barres horizontales
            y_pos = np.arange(len(params))
            ax.barh(y_pos, impacts)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(params)
            ax.set_xlabel('Impact Relatif')
            ax.grid(True)

    def _update_metrics_plot(self):
        """Met à jour le graphique des métriques"""
        if not self.history['metrics']:
            return
                
        ax = self.axes['metrics']
        ax.clear()
        
        iterations = self.history['iterations']
        
        # Tracer seulement les métriques principales
        metrics_to_plot = ['rmse', 'ratio_means', 'seasonal_bias']
        for metric in metrics_to_plot:
            values = [m[metric] for m in self.history['metrics']]
            # Normaliser les valeurs pour une meilleure visualisation
            normalized = [v/max(values) for v in values]
            ax.plot(iterations, normalized, 'o-', label=metric)
        
        ax.legend()
        ax.grid(True)
        ax.set_xlabel('Itération')
        ax.set_ylabel('Valeur Normalisée')


    def _update_error_distribution(self, comparison_data):
        """Met à jour la distribution des erreurs"""
        if comparison_data is None:
            return
            
        ax = self.axes['error_dist']
        ax.clear()
        
        hydro = comparison_data['hydro']
        sim = comparison_data['simulation']
        errors = sim - hydro
        
        ax.hist(errors, bins=50, density=True, alpha=0.7)
        ax.set_xlabel('Erreur (kWh)')
        ax.set_ylabel('Densité')
        ax.grid(True)

    def _update_correlation_plot(self):
        """Met à jour la matrice de corrélation"""
        if not self.history['parameters'] or not self.history['metrics']:
            return
            
        ax = self.axes['correlations']
        ax.clear()
        
        # Construire matrices de données
        param_matrix = []
        metric_names = ['rmse', 'ratio_means', 'seasonal_bias']
        param_names = list(self.history['parameters'].keys())
        
        for param in param_names:
            param_matrix.append(self.history['parameters'][param])
        param_matrix = np.array(param_matrix).T
        
        metric_matrix = []
        for metric in metric_names:
            metric_matrix.append([m[metric] for m in self.history['metrics']])
        metric_matrix = np.array(metric_matrix).T
        
        # Calculer corrélations
        correlations = np.zeros((len(param_names), len(metric_names)))
        for i, param in enumerate(param_names):
            for j, metric in enumerate(metric_names):
                correlations[i, j] = np.corrcoef(param_matrix[:, i], metric_matrix[:, j])[0, 1]
        
        # Afficher heatmap
        im = ax.imshow(correlations, cmap='RdBu', aspect='auto')
        plt.colorbar(im, ax=ax)
        
        # Labels
        ax.set_xticks(np.arange(len(metric_names)))
        ax.set_yticks(np.arange(len(param_names)))
        ax.set_xticklabels(metric_names, rotation=45)
        ax.set_yticklabels(param_names)

    def save_results(self, output_dir=None, prefix='calibration'):
        try:
            if output_dir is None:
                output_dir = RESULTS_STRUCTURE['VISUALIZATION_DIR']
                
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Sauvegarder toutes les figures
            self.fig1.savefig(output_dir / f'{prefix}_monitoring_{timestamp}.png')
            self.fig2.savefig(output_dir / f'{prefix}_consumption_{timestamp}.png')
            self.fig3.savefig(output_dir / f'{prefix}_analysis_{timestamp}.png')
            
            # Sauvegarder historique enrichi
            history_data = {
                'iterations': self.history['iterations'],
                'scores': self.history['scores'],
                'parameters': self.history['parameters'],
                'convergence': self.history['convergence'],
                'metrics': self.history['metrics'],
                'sensitivities': self.history['sensitivities']
            }
            
            with open(output_dir / f'{prefix}_history_{timestamp}.json', 'w') as f:
                json.dump(history_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde : {str(e)}")

    def keep_display_open(self):
        """Garde la fenêtre ouverte"""
        if self.is_initialized:
            plt.show(block=True)

    def _update_params_plot(self):
        """Met à jour le graphique des paramètres"""
        ax = self.axes['params']
        ax.clear()
        
        # Pour chaque paramètre, créer un sous-graphique décalé
        n_params = len(self.history['parameters'])
        param_names = list(self.history['parameters'].keys())
        
        for i, (param, values) in enumerate(self.history['parameters'].items()):
            # Ajouter un décalage vertical pour séparer les paramètres
            offset = i * 1.0
            
            # Calculer valeurs normalisées entre 0 et 1 pour la ligne
            min_val = min(values)
            max_val = max(values)
            if max_val > min_val:
                normalized = [(v - min_val)/(max_val - min_val) + offset for v in values]
            else:
                normalized = [offset] * len(values)
                
            # Tracer la ligne avec les valeurs réelles dans les annotations
            line = ax.plot(self.history['iterations'], normalized, 'o-', label=param)
            color = line[0].get_color()
            
            # Ajouter les valeurs réelles comme annotations
            for x, y, val in zip(self.history['iterations'][-1:], normalized[-1:], values[-1:]):
                ax.annotate(f'{val:.3f}', 
                        (x, y),
                        xytext=(5, 0),
                        textcoords='offset points',
                        color=color)
        
        # Configurer l'apparence
        ax.set_title('Évolution des Paramètres')
        ax.set_xlabel('Itération')
        ax.set_yticks([i * 1.0 for i in range(n_params)])
        ax.set_yticklabels(param_names)
        ax.grid(True, alpha=0.3)
        
        # Ajuster les limites pour l'espacement
        ax.set_ylim(-0.5, n_params * 1.0 + 0.5)

    def _update_score_plot(self):
        """Met à jour le graphique des scores"""
        try:
            # Récupérer l'axe
            ax = self.axes['score']
            if ax is None:
                return
                
            ax.clear()
            
            # Tracer l'évolution du score
            if self.history['iterations'] and self.history['scores']:
                ax.plot(
                    self.history['iterations'],
                    self.history['scores'],
                    'bo-',
                    label='Score'
                )
                
                ax.set_xlabel('Itération')
                ax.set_ylabel('Score')
                ax.set_title('Évolution du Score')
                ax.grid(True)
                
        except Exception as e:
            self.logger.error(f"Erreur mise à jour score plot: {str(e)}")
    
    def update(self, viz_data: dict):
        """Met à jour toutes les visualisations"""
        try:
            if not self.is_initialized:
                self.setup_display(list(viz_data['parameters'].keys()))

            # 1. Mettre à jour l'historique
            self.history['iterations'].append(viz_data['iteration'])
            self.history['scores'].append(viz_data['score'])
            
            # 2. Mettre à jour paramètres
            for param, value in viz_data['parameters'].items():
                if param not in self.history['parameters']:
                    self.history['parameters'][param] = []
                self.history['parameters'][param].append(value)

            # 3. Mettre à jour métriques et sensibilités
            if 'metrics' in viz_data:
                self.history['metrics'].append(viz_data['metrics'])
            if 'sensitivity' in viz_data:
                self.history['sensitivities'].append(viz_data['sensitivity'])

            # 4. Mettre à jour tous les graphiques
            self._update_score_plot()
            self._update_params_plot()
            self._update_convergence_plot()
            
            if 'comparison' in viz_data:
                self._update_comparison_plot(viz_data['comparison'])
                
            # IMPORTANT : Appeler ces méthodes ici        
            self._update_sensitivity_plot()
            self._update_metrics_plot()

            # 5. Rafraîchir l'affichage
            for fig in [self.fig1, self.fig2, self.fig3]:
                if fig:  # Vérifier que la figure existe
                    fig.canvas.draw()
                    plt.pause(0.1)
                    
        except Exception as e:
            self.logger.error(f"Erreur mise à jour visualisation: {str(e)}")




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


