import pandas as pd
import logging
from pathlib import Path
import sys
import subprocess
import os
import json
from datetime import datetime
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.paths_config import (
    DATA_FILES, 
    PROCESSED_DATA_DIR, 
    RESULTS_DIR, 
    get_iteration_dirs,
    RESULTS_STRUCTURE
)

class SimulationManager:
    def __init__(self):
        """Initialise le gestionnaire de simulations"""
        self.logger = self._setup_logger()
        self.simulation_dir = RESULTS_STRUCTURE['SIMULATIONS_DIR']  # Utiliser RESULTS_STRUCTURE
        self.docker_image = "canmet/model_dev_container:3.7.0"
        
        # État de la simulation
        self.current_iteration = 0
        self.simulation_status = {}
        
        # Suivi des performances
        self.performance_metrics = {
            'simulation_times': [],
            'success_rate': [],
            'error_counts': {}
        }
        
    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('SimulationManager')

    def run_provincial_simulations(self, iteration: int = 0) -> bool:
        """
        Lance les simulations pour toute la province
        
        Args:
            iteration: Numéro de l'itération actuelle
        """
        try:
            self.current_iteration = iteration
            iteration_dir = self.simulation_dir / f'iteration_{iteration}'
            
            if not iteration_dir.exists():
                self.logger.error(f"Dossier d'itération non trouvé: {iteration_dir}")
                return False
                
            # Récupérer la liste des archétypes à simuler
            archetypes = []
            for arch_dir in iteration_dir.iterdir():
                if arch_dir.is_dir() and not arch_dir.name.startswith('_'):
                    archetypes.append(arch_dir)
            
            total = len(archetypes)
            if total == 0:
                self.logger.error("Aucun archétype trouvé pour simulation")
                return False
            
            self.logger.info(f"\nDémarrage des simulations pour {total} archétypes")
            processed = 0
            successful = 0
            start_time = datetime.now()

            # Pour chaque archétype
            for arch_dir in archetypes:
                try:
                    # Préparer la commande Docker
                    cmd = f'docker run --rm -v "{arch_dir}:/shared" {self.docker_image} cli run --hourly ALL'
                    
                    # Log détaillé
                    simulation_log = arch_dir / f'simulation_{iteration}.log'
                    
                    # Lancer la simulation
                    self.logger.info(f"\nSimulation de {arch_dir.name} ({processed+1}/{total})")
                    process = subprocess.run(
                        cmd, 
                        shell=True,
                        capture_output=True,
                        text=True
                    )
                    
                    # Sauvegarder le log
                    with open(simulation_log, 'w') as f:
                        f.write(f"STDOUT:\n{process.stdout}\n\nSTDERR:\n{process.stderr}")
                    
                    # Vérifier le résultat
                    if process.returncode == 0:
                        successful += 1
                        self._update_simulation_status(arch_dir.name, 'success')
                    else:
                        self._update_simulation_status(arch_dir.name, 'error', process.stderr)
                        
                    processed += 1
                    
                    # Log progression
                    progress = (processed / total) * 100
                    success_rate = (successful / processed) * 100
                    self.logger.info(f"Progression : {progress:.1f}% ({processed}/{total})")
                    self.logger.info(f"Taux de succès : {success_rate:.1f}%")
                    
                except Exception as e:
                    self.logger.error(f"Erreur simulation {arch_dir.name}: {str(e)}")
                    self._update_simulation_status(arch_dir.name, 'error', str(e))
                    continue
            
            # Calculer métriques finales
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            success_rate = (successful / total) * 100
            
            # Sauvegarder métriques
            self.performance_metrics['simulation_times'].append(duration)
            self.performance_metrics['success_rate'].append(success_rate)
            
            # Sauvegarder rapport
            self._save_simulation_report(iteration, {
                'total_archetypes': total,
                'successful': successful,
                'duration': duration,
                'success_rate': success_rate,
                'timestamp': end_time.isoformat()
            })
            
            self.logger.info(f"\nSimulations terminées :")
            self.logger.info(f"- Réussies : {successful}/{total} ({success_rate:.1f}%)")
            self.logger.info(f"- Durée totale : {duration:.1f} secondes")
            
            return successful > 0

        except Exception as e:
            self.logger.error(f"Erreur lors des simulations : {str(e)}")
            return False

    def _update_simulation_status(self, archetype: str, status: str, error: str = None):
        """Met à jour le statut d'une simulation"""
        self.simulation_status[archetype] = {
            'iteration': self.current_iteration,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'error': error
        }

    def _save_simulation_report(self, iteration: int, metrics: dict):
        """Sauvegarde le rapport de simulation"""
        report = {
            'iteration': iteration,
            'metrics': metrics,
            'status': self.simulation_status,
            'performance': {
                'simulation_times': self.performance_metrics['simulation_times'],
                'success_rate': self.performance_metrics['success_rate']
            }
        }
        
        report_file = self.simulation_dir / f'iteration_{iteration}' / 'simulation_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

    def get_iteration_status(self, iteration: int) -> dict:
        """
        Retourne le statut détaillé d'une itération de simulation
        
        Args:
            iteration: Numéro de l'itération
        Returns:
            dict: Statut détaillé ou None si erreur
        """
        try:
            # 1. Vérifier existence du rapport
            status_file = self.simulation_dir / f'iteration_{iteration}' / 'simulation_report.json'
            if not status_file.exists():
                self.logger.warning(f"Rapport non trouvé pour itération {iteration}")
                return None
                
            # 2. Charger et analyser le rapport
            with open(status_file, 'r') as f:
                report = json.load(f)
                
            # 3. Enrichir avec informations supplémentaires
            status = {
                'iteration': iteration,
                'timestamp': report['metrics']['timestamp'],
                'success_rate': report['metrics']['success_rate'],
                'duration': report['metrics']['duration'],
                'details': {
                    'total_archetypes': report['metrics']['total_archetypes'],
                    'successful': report['metrics']['successful'],
                    'failed': report['metrics']['total_archetypes'] - report['metrics']['successful']
                },
                'performance': {
                    'avg_time_per_archetype': report['metrics']['duration'] / report['metrics']['total_archetypes']
                    if report['metrics']['total_archetypes'] > 0 else 0
                }
            }
            
            self.logger.info(f"\nStatut itération {iteration} :")
            self.logger.info(f"- Taux de succès : {status['success_rate']:.1f}%")
            self.logger.info(f"- Durée : {status['duration']:.1f} secondes")
            self.logger.info(f"- Archétypes traités : {status['details']['total_archetypes']}")
            
            return status
            
        except Exception as e:
            self.logger.error(f"Erreur lecture statut itération {iteration}: {str(e)}")
            return None

    def get_all_iterations_status(self) -> dict:
        """
        Retourne le statut de toutes les itérations effectuées
        """
        try:
            all_status = {}
            for iter_dir in self.simulation_dir.glob('iteration_*'):
                try:
                    iteration = int(iter_dir.name.split('_')[1])
                    status = self.get_iteration_status(iteration)
                    if status:
                        all_status[iteration] = status
                except ValueError:
                    continue
                    
            return all_status
            
        except Exception as e:
            self.logger.error(f"Erreur lecture statuts : {str(e)}")
            return {}

if __name__ == "__main__":
    manager = SimulationManager()
    
    print("\nTest du gestionnaire de simulations :")
    print("-" * 50)
    
    # 1. Tester le statut des itérations existantes
    print("\n1. Test statuts des itérations")
    for i in range(3):  # Tester les 3 premières itérations
        status = manager.get_iteration_status(i)
        if status:
            print(f"\nItération {i} :")
            print(f"- Taux de succès : {status['success_rate']:.1f}%")
            print(f"- Temps moyen/archetype : {status['performance']['avg_time_per_archetype']:.1f} sec")
    
    # 2. Tester le résumé global
    print("\n2. Résumé de toutes les itérations")
    all_status = manager.get_all_iterations_status()
    if all_status:
        print(f"Nombre total d'itérations : {len(all_status)}")
        average_success = np.mean([s['success_rate'] for s in all_status.values()])
        print(f"Taux de succès moyen : {average_success:.1f}%")