import pandas as pd
import logging
from pathlib import Path
import sys
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import shutil
import concurrent.futures
from multiprocessing import cpu_count





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
    """Gère l'exécution des simulations OpenStudio"""
    
    def __init__(self):
        """Initialise le gestionnaire de simulations"""
        self.logger = self._setup_logger()
        self.simulation_dir = RESULTS_STRUCTURE['SIMULATIONS_DIR']
        self.max_workers = max(1, int(cpu_count() * 0.8))  # ~17-18 workers sur votre machine
        self.logger.info(f"Initialisation avec {self.max_workers} workers")
        # Configuration Docker
        # self.docker_image = "nrel/openstudio"
        
        # État des simulations
        self.current_iteration = 0
        self.simulation_status = {}
        
        # Métriques de performance
        self.performance_metrics = {
            'simulation_times': [],
            'success_rates': [],
            'error_counts': {}
        }
    
    def _setup_logger(self):
        """Configure le logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('SimulationManager')

    def run_provincial_simulations(self, iteration: int) -> bool:
        """Version parallèle des simulations provinciales"""
        try:
            self.current_iteration = iteration
            paths = get_iteration_dirs(iteration)
            iteration_dir = paths['simulation_dir']
            
            # Liste des simulations à lancer
            simulations = []
            for arch_dir in iteration_dir.iterdir():
                if arch_dir.is_dir() and not arch_dir.name.startswith('_'):
                    workflow_path = arch_dir / 'workflow.osw'
                    if workflow_path.exists():
                        simulations.append((arch_dir.name, workflow_path))

            total = len(simulations)
            if total == 0:
                self.logger.error("Aucune simulation à lancer")
                return False

            start_time = datetime.now()
            successful = 0
            self.logger.info(f"\nDémarrage des simulations parallèles pour {total} archétypes")

            # Exécution parallèle
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Soumettre les tâches
                futures = [
                    executor.submit(self._run_single_simulation, name, path)
                    for name, path in simulations
                ]
                
                # Collecter les résultats au fur et à mesure
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    try:
                        arch_name, success, result = future.result()
                        
                        # Mettre à jour statut
                        if success:
                            successful += 1
                            status = 'success'
                        else:
                            status = 'error'
                        
                        self._update_simulation_status(arch_name, status, result.get('stderr'))
                        
                        # Log progression
                        progress = ((i + 1) / total) * 100
                        self.logger.info(f"Progression : {progress:.1f}% ({i+1}/{total})")
                        self.logger.info(f"Taux de succès : {(successful/(i+1))*100:.1f}%")
                        
                    except Exception as e:
                        self.logger.error(f"Erreur future : {str(e)}")

            # Sauvegarder rapport final
            duration = (datetime.now() - start_time).total_seconds()
            self._save_simulation_report(iteration, {
                'total_archetypes': total,
                'successful': successful,
                'duration': duration,
                'success_rate': (successful / total) * 100 if total > 0 else 0,
                'timestamp': datetime.now().isoformat()
            })

            return successful > 0

        except Exception as e:
            self.logger.error(f"Erreur simulations parallèles : {str(e)}")
            return False
        
    def _run_single_simulation(self, arch_name: str, workflow_path: Path) -> Tuple[str, bool, dict]:
        """Version isolée de _run_simulation pour la parallélisation"""
        try:
            # Construire la commande OpenStudio
            cmd = f"openstudio run -w {workflow_path}"
            
            # Lancer la simulation
            start_time = datetime.now()
            process = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            duration = (datetime.now() - start_time).total_seconds()

            # Préparer résultat
            result = {
                'success': process.returncode == 0,
                'duration': duration,
                'stdout': process.stdout,
                'stderr': process.stderr,
                'timestamp': datetime.now().isoformat()
            }
            
            return arch_name, result['success'], result

        except Exception as e:
            return arch_name, False, {'error': str(e)}

    # def _run_simulation(self, arch_name: str, workflow_path: Path, iteration_dir: Path) -> bool:
    #     """Lance une simulation OpenStudio"""
    #     try:
    #         arch_dir = iteration_dir / arch_name
    #         workflow_full_path = arch_dir / "workflow.osw"

    #         # Vérifier que le workflow existe
    #         if not workflow_full_path.exists():
    #             self.logger.error(f"Workflow non trouvé: {workflow_full_path}")
    #             return False

    #         # Construire la commande OpenStudio
    #         cmd = f"openstudio run -w {workflow_full_path}"

    #         # Log pour debug
    #         self.logger.info(f"Exécution: {cmd}")
            
    #         # Lancer la simulation
    #         self.logger.info(f"\nSimulation de {arch_name}")
    #         process = subprocess.run(
    #             cmd,
    #             shell=True,
    #             capture_output=True,
    #             text=True
    #         )

    #         # Log sortie complète
    #         self.logger.info(f"STDOUT:\n{process.stdout}")
    #         if process.stderr:
    #             self.logger.error(f"STDERR:\n{process.stderr}")

    #         # Sauvegarder log
    #         simulation_log = arch_dir / f'simulation_{self.current_iteration}.log'
    #         with open(simulation_log, 'w') as f:
    #             f.write(f"Commande: {cmd}\n\n")
    #             f.write(f"STDOUT:\n{process.stdout}\n\n")
    #             f.write(f"STDERR:\n{process.stderr}")

    #         # Vérifier résultat
    #         success = process.returncode == 0
    #         status = 'success' if success else 'error'
    #         error_msg = process.stderr if not success else None

    #         self._update_simulation_status(arch_name, status, error_msg)

    #         # Si succès, vérifier les résultats
    #         if success:
    #             return self._verify_simulation_outputs(arch_dir)

    #         return False

    #     except Exception as e:
    #         self.logger.error(f"Erreur exécution {arch_name}: {str(e)}")
    #         self._update_simulation_status(arch_name, 'error', str(e))
    #         return False

    def _verify_simulation_outputs(self, arch_dir: Path) -> bool:
        """
        Vérifie la présence et validité des fichiers de sortie
        """
        try:
            # Vérifier fichiers requis
            required_files = [
                arch_dir / 'run' / 'results_timeseries.csv',
                arch_dir / 'run' / 'eplusout.err',
                arch_dir / 'workflow.osw'
            ]
            
            for file_path in required_files:
                if not file_path.exists():
                    raise FileNotFoundError(f"Fichier manquant : {file_path}")
            
            # Vérifier contenu du CSV
            results_file = arch_dir / 'run' / 'results_timeseries.csv'
            df = pd.read_csv(results_file, nrows=5)  # Juste vérifier le début
            
            required_cols = ['Time', 'Fuel Use: Electricity: Total']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                raise ValueError(f"Colonnes manquantes : {missing_cols}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur vérification résultats : {str(e)}")
            return False

    def _update_simulation_status(self, archetype: str, status: str, error: str = None):
        """Met à jour le statut d'une simulation"""
        self.simulation_status[archetype] = {
            'iteration': self.current_iteration,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'error': error
        }
        
        # Mettre à jour compteurs d'erreurs
        if error:
            self.performance_metrics['error_counts'][error] = (
                self.performance_metrics['error_counts'].get(error, 0) + 1
            )

    def _save_simulation_report(self, iteration: int, metrics: dict):
        """Sauvegarde le rapport de simulation"""
        report = {
            'iteration': iteration,
            'metrics': metrics,
            'status': self.simulation_status,
            'performance': {
                'simulation_times': self.performance_metrics['simulation_times'],
                'success_rates': self.performance_metrics['success_rates'],
                'error_counts': self.performance_metrics['error_counts']
            }
        }
        
        report_file = self.simulation_dir / f'iteration_{iteration}' / 'simulation_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

    def get_iteration_status(self, iteration: int) -> Optional[Dict]:
        """
        Retourne le statut détaillé d'une itération
        
        Args:
            iteration: Numéro de l'itération
        """
        try:
            status_file = self.simulation_dir / f'iteration_{iteration}' / 'simulation_report.json'
            if not status_file.exists():
                self.logger.warning(f"Rapport non trouvé pour itération {iteration}")
                return None
            
            with open(status_file, 'r') as f:
                report = json.load(f)
            
            # Enrichir avec infos supplémentaires
            status = {
                'iteration': iteration,
                'timestamp': report['metrics']['timestamp'],
                'success_rate': report['metrics']['success_rate'],
                'duration': report['metrics']['duration'],
                'details': {
                    'total_archetypes': report['metrics']['total_archetypes'],
                    'successful': report['metrics']['successful'],
                    'failed': (report['metrics']['total_archetypes'] - 
                             report['metrics']['successful'])
                }
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Erreur lecture statut itération {iteration}: {str(e)}")
            return None

    def get_all_iterations_status(self) -> Dict:
        """Retourne le statut de toutes les itérations"""
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
    
    # 1. Test avec itération 0
    print("\n1. Test lancement simulations itération 0...")
    if manager.run_provincial_simulations(0):
        print("✓ Simulations lancées avec succès")
        
        # Vérifier statut
        status = manager.get_iteration_status(0)
        if status:
            print(f"\nRésumé de l'itération 0:")
            print(f"- Taux de succès : {status['success_rate']:.1f}%")
            print(f"- Durée totale : {status['duration']:.1f} secondes")