#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio para manejar LM Studio y modelos de lenguaje
"""
import subprocess
import requests
import logging
from typing import List, Dict, Optional
from config.settings import LM_CONFIG


class LMStudioService:
    """Servicio para interactuar con LM Studio"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or LM_CONFIG['DEFAULT_URL']
        self.cli_command = LM_CONFIG['CLI_COMMAND']
        self.timeout = LM_CONFIG['TIMEOUT']
        
    def get_available_models(self) -> List[Dict[str, str]]:
        """Obtiene la lista de modelos disponibles en LM Studio"""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            if 'data' in data:
                for model in data['data']:
                    models.append({
                        'id': model.get('id', ''),
                        'name': model.get('id', '').split('/')[-1],
                        'owned_by': model.get('owned_by', 'unknown')
                    })
            
            return models
            
        except requests.RequestException as e:
            logging.error(f"Error connecting to LM Studio: {e}")
            return []
        except Exception as e:
            logging.error(f"Error parsing LM Studio response: {e}")
            return []
    
    def check_model_loaded(self, model_id: str) -> bool:
        """Verifica si un modelo específico está cargado"""
        models = self.get_available_models()
        return any(model['id'] == model_id for model in models)
    
    def get_loaded_models(self) -> List[Dict[str, str]]:
        """Obtiene la lista de modelos actualmente cargados/disponibles"""
        return self.get_available_models()
    
    def unload_current_model(self) -> bool:
        """Descarga el modelo actualmente cargado usando CLI"""
        try:
            cmd = [self.cli_command, "unload"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logging.info("Model unloaded successfully")
                return True
            else:
                logging.warning(f"Failed to unload model: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logging.error("Timeout unloading model")
            return False
        except Exception as e:
            logging.error(f"Error unloading model via CLI: {e}")
            return False
    
    def unload_all_models(self) -> Dict[str, any]:
        """Descarga todos los modelos usando 'lms unload all'"""
        try:
            logging.info("🧠 Ejecutando 'lms unload all' para descargar todos los modelos...")
            
            cmd = [self.cli_command, "unload", "all"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # Timeout más largo para descargar todos
            )
            
            if result.returncode == 0:
                logging.info("✅ Todos los modelos descargados exitosamente")
                return {
                    'success': True,
                    'message': 'Todos los modelos descargados exitosamente',
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                logging.warning(f"⚠️ Comando completado con advertencias: {result.stderr}")
                return {
                    'success': True,  # Aún consideramos éxito si el comando se ejecutó
                    'message': f'Comando ejecutado con advertencias: {result.stderr}',
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
                
        except subprocess.TimeoutExpired:
            logging.error("⏱️ Timeout descargando todos los modelos")
            return {
                'success': False,
                'message': 'Timeout descargando todos los modelos (>60s)',
                'stdout': '',
                'stderr': 'Timeout'
            }
        except Exception as e:
            logging.error(f"❌ Error ejecutando 'lms unload all': {e}")
            return {
                'success': False,
                'message': f'Error ejecutando comando: {str(e)}',
                'stdout': '',
                'stderr': str(e)
            }
    
    def stop_server(self) -> Dict[str, any]:
        """Parar completamente el servidor LM Studio usando 'lms stop server'"""
        try:
            logging.info("🛑 Ejecutando 'lms stop server' para parar completamente LM Studio...")
            
            cmd = [self.cli_command, "stop", "server"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # Timeout para parar el servidor
            )
            
            if result.returncode == 0:
                logging.info("✅ Servidor LM Studio parado exitosamente")
                return {
                    'success': True,
                    'message': 'Servidor LM Studio parado exitosamente',
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                logging.warning(f"⚠️ Comando completado con advertencias: {result.stderr}")
                return {
                    'success': True,  # Aún consideramos éxito si el comando se ejecutó
                    'message': f'Servidor parado con advertencias: {result.stderr}',
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
                
        except subprocess.TimeoutExpired:
            logging.error("⏱️ Timeout parando el servidor LM Studio")
            return {
                'success': False,
                'message': 'Timeout parando el servidor LM Studio (>30s)',
                'stdout': '',
                'stderr': 'Timeout'
            }
        except Exception as e:
            logging.error(f"❌ Error ejecutando 'lms stop server': {e}")
            return {
                'success': False,
                'message': f'Error ejecutando comando: {str(e)}',
                'stdout': '',
                'stderr': str(e)
            }
    
    def force_stop_server_and_unload(self) -> Dict[str, any]:
        """Parada forzada completa: descargar modelos + parar servidor"""
        try:
            logging.info("🚫 PARADA FORZADA: Descargando modelos y parando servidor LM Studio...")
            
            # Paso 1: Descargar todos los modelos primero
            unload_result = self.unload_all_models()
            
            # Paso 2: Parar el servidor completamente
            stop_result = self.stop_server()
            
            # Evaluar resultado combinado
            overall_success = unload_result.get('success', False) and stop_result.get('success', False)
            
            result = {
                'success': overall_success,
                'message': f"Unload: {unload_result.get('message', 'N/A')} | Stop: {stop_result.get('message', 'N/A')}",
                'unload_details': unload_result,
                'stop_details': stop_result
            }
            
            if overall_success:
                logging.info("✅ PARADA FORZADA COMPLETA: Modelos descargados y servidor parado")
            else:
                logging.warning("⚠️ PARADA FORZADA PARCIAL: Algunos comandos fallaron")
            
            return result
            
        except Exception as e:
            logging.error(f"❌ Error en parada forzada completa: {e}")
            return {
                'success': False,
                'message': f'Error en parada forzada: {str(e)}',
                'unload_details': {},
                'stop_details': {}
            }
    
    def test_connection(self, url: str = None) -> Dict[str, any]:
        """Prueba la conexión con LM Studio"""
        test_url = url or self.base_url
        
        try:
            response = requests.get(
                f"{test_url}/models",
                timeout=5.0
            )
            response.raise_for_status()
            
            return {
                'success': True,
                'url': test_url,
                'status_code': response.status_code,
                'models_count': len(response.json().get('data', []))
            }
            
        except requests.RequestException as e:
            return {
                'success': False,
                'url': test_url,
                'error': str(e)
            }
    
    def load_model_via_cli(self, model_path: str) -> bool:
        """Carga un modelo usando el CLI de LM Studio con gestión inteligente"""
        try:
            # Primero verificar qué modelos están cargados
            current_models = self.get_loaded_models()
            
            # Si ya hay un modelo cargado y es diferente, descargarlo primero
            if current_models:
                current_model_id = current_models[0].get('id', '')
                # Comparar solo el nombre del modelo sin el path completo
                current_model_name = current_model_id.split('/')[-1] if current_model_id else ''
                new_model_name = model_path.split('/')[-1] if model_path else ''
                
                if current_model_name and current_model_name != new_model_name:
                    logging.info(f"Different model loaded ({current_model_name}), unloading first...")
                    self.unload_current_model()
                elif current_model_name == new_model_name:
                    logging.info(f"Model {new_model_name} already loaded, skipping...")
                    return True
            
            # Cargar el nuevo modelo
            cmd = [self.cli_command, "load", model_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logging.info(f"Model loaded successfully: {model_path}")
                return True
            else:
                logging.error(f"Failed to load model: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logging.error(f"Timeout loading model: {model_path}")
            return False
        except Exception as e:
            logging.error(f"Error loading model via CLI: {e}")
            return False
    
    def get_server_info(self) -> Dict[str, any]:
        """Obtiene información del servidor LM Studio"""
        try:
            # Intentar obtener información básica
            models_response = requests.get(
                f"{self.base_url}/models",
                timeout=5.0
            )
            
            if models_response.status_code == 200:
                models_data = models_response.json()
                return {
                    'status': 'running',
                    'url': self.base_url,
                    'models_available': len(models_data.get('data', [])),
                    'models': models_data.get('data', [])
                }
            else:
                return {
                    'status': 'error',
                    'url': self.base_url,
                    'error': f"HTTP {models_response.status_code}"
                }
                
        except requests.ConnectionError:
            return {
                'status': 'offline',
                'url': self.base_url,
                'error': 'Connection refused - LM Studio may not be running'
            }
        except Exception as e:
            return {
                'status': 'error',
                'url': self.base_url,
                'error': str(e)
            }


# Alias para compatibilidad
LMStudio = LMStudioService