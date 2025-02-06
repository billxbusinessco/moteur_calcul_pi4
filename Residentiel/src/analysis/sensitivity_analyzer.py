import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
import json
import logging
from typing import Dict, List

class SensitivityAnalyzer:
    """Analyse la sensibilité des paramètres et leur impact"""
    
    def __init__(self):
        self.logger = self._setup_logger()
        self.history = []
        self.parameter_impacts = {}
        self.metric_correlations = None  # Ajout de cet attribut
        self.metric_history = {}
        
    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('SensitivityAnalyzer')

    def record_iteration(self, params: dict, score: float, metrics: dict):
        """Enregistre une itération pour analyse"""
        self.history.append({
            'parameters': params.copy(),
            'score': score,
            'metrics': metrics.copy(),
            'timestamp': datetime.now().isoformat()
        })
        
        if len(self.history) > 1:
            self._update_sensitivities()
            self._update_metric_correlations()
        
        # Log des impacts modifié pour gérer correctement le formatage
        if self.parameter_impacts:
            self.logger.info("\nImpacts des paramètres:")
            # Converti en liste et trie par valeur d'impact
            impacts = [(name, np.mean(values) if isinstance(values, list) else values) 
                    for name, values in self.parameter_impacts.items()]
            impacts.sort(key=lambda x: x[1], reverse=True)
            
            for param_name, impact in impacts:
                self.logger.info(f"- {param_name}: {float(impact):.4f}")

    def _update_sensitivities(self):
        """Calcule l'impact de chaque paramètre sur le score"""
        current = self.history[-1]
        previous = self.history[-2]
        
        for param_name in current['parameters']:
            param_delta = abs(
                current['parameters'][param_name] - 
                previous['parameters'][param_name]
            )
            score_delta = abs(current['score'] - previous['score'])
            
            if param_delta > 0:
                sensitivity = score_delta / param_delta
                
                if param_name not in self.parameter_impacts:
                    self.parameter_impacts[param_name] = []
                    
                self.parameter_impacts[param_name].append(sensitivity)
    
    def _update_metric_correlations(self):
        """Analyse les corrélations entre paramètres et métriques"""
        if len(self.history) < 3:
            return
            
        # Construire DataFrame des paramètres
        params_df = pd.DataFrame([
            h['parameters'] for h in self.history
        ])
        
        # Construire DataFrame des métriques
        metrics_df = pd.DataFrame([
            h['metrics'] for h in self.history
        ])
        
        # Calculer corrélations
        correlations = pd.DataFrame()
        for param in params_df.columns:
            for metric in metrics_df.columns:
                corr = params_df[param].corr(metrics_df[metric])
                correlations.loc[param, metric] = corr
                
        self.metric_correlations = correlations

    def get_parameter_rankings(self) -> Dict[str, float]:
        """Retourne le classement des paramètres par impact"""
        rankings = {}
        for param, sensitivities in self.parameter_impacts.items():
            rankings[param] = np.mean(sensitivities)
        return dict(sorted(
            rankings.items(), 
            key=lambda x: x[1], 
            reverse=True
        ))
    
    def save_analysis(self, output_dir: Path, prefix: str = "sensitivity"):
        """Sauvegarde les résultats d'analyse"""
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Préparer les résultats
            results = {
                'parameter_impacts': self.get_parameter_rankings(),
                'timestamp': timestamp,
                'history': self.history
            }
            
            # Ajouter les corrélations si elles existent
            if self.metric_correlations is not None:
                results['metric_correlations'] = self.metric_correlations.to_dict()
            
            # Sauvegarder
            output_file = output_dir / f"{prefix}_analysis_{timestamp}.json"
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
                
            self.logger.info(f"Analyse sauvegardée: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde analyse: {str(e)}")