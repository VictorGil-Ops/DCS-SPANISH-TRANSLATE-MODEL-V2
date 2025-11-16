#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio de orquestación DCS - Migrado desde app.py original
Maneja la ejecución completa de traducción de campañas DCS
"""
import os
import sys
import logging
import subprocess
import shutil
import zipfile
import time
import signal
import glob
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

from config.settings import BASE_DIR, TRANSLATIONS_DIR, LOGS_DIR
from app.services.translation_engine import TranslationEngine
from app.services.lm_studio import LMStudioService
from app.services.campaign_registry import get_campaign_registry
from app.utils.file_utils import ensure_directory, safe_copy_file


class DCSOrchestrator:
    """Servicio principal de orquestación de traducciones DCS"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_process = None
        
        # Inicializar servicio LM Studio
        self.lm_studio_service = LMStudioService()
        
        # Cache para evitar verificaciones repetitivas de LM Studio
        self._lm_studio_cache = {
            'last_check': 0,
            'status': None,
            'cache_duration': 300,  # 5 minutos de cache durante traducciones activas
            'cache_duration_idle': 30,  # 30 segundos cuando no está traduciendo
            'translation_active': False
        }
        
        self.status = {
            'is_running': False,
            'phase': 'idle',
            'detail': '',
            'progress': 0,
            'current_campaign': None,
            'current_mission': None,
            'missions_total': 0,
            'missions_processed': 0,
            'missions_successful': 0,
            'missions_failed': 0,
            'errors': [],
            'start_time': None
        }
        
        # Información de progreso de lotes para la misión actual
        self.current_batch_info = {
            'total_batches': 0,
            'processed_batches': 0,
            'batch_progress': 0,
            'cache_hits': 0,
            'model_calls': 0
        }
        
        # Variables para simulación de progreso de lotes
        self.batch_simulation_active = False
        self.batch_simulation_thread = None
        
        # Archivo para persistir last_execution
        self.persistence_file = os.path.join(LOGS_DIR, 'last_execution.json')
        
        # Cargar último resultado de ejecución desde archivo
        self.last_execution = self._load_last_execution()
    
    def _check_lm_studio_with_cache(self, engine, lm_url: str, lm_model: str, campaign: str = None, force_check: bool = False):
        """Verificar LM Studio con cache para evitar verificaciones repetitivas"""
        import time
        
        current_time = time.time()
        
        # Determinar duración del cache según si hay traducciones activas
        cache_duration = (self._lm_studio_cache['cache_duration'] if self._lm_studio_cache['translation_active'] 
                         else self._lm_studio_cache['cache_duration_idle'])
        
        # Si tenemos cache válido y no es forzado, usar el cache
        if (not force_check and 
            self._lm_studio_cache['status'] and 
            (current_time - self._lm_studio_cache['last_check']) < cache_duration):
            
            cached_status = self._lm_studio_cache['status']
            # Solo log si es la primera vez que se usa el cache o si hay errores
            if cached_status.get('available') and cached_status.get('models_loaded'):
                # LM Studio funciona bien, no hacer log repetitivo
                return cached_status
        
        # Hacer verificación real
        self._add_progress_log(f"Verificando conexión con LM Studio en {lm_url}", 'info', campaign)
        lm_status = engine.check_lm_studio_status(lm_url, lm_model)
        
        # Actualizar cache
        self._lm_studio_cache['last_check'] = current_time
        self._lm_studio_cache['status'] = lm_status
        
        # Procesar resultado
        self._add_lm_studio_status(lm_status, campaign)
        
        return lm_status
    
    def _add_error(self, message: str, campaign: str = None, mission: str = None, error_type: str = 'general', details: Dict[str, Any] = None):
        """Agregar un error estructurado al estado con información detallada"""
        from datetime import datetime
        
        error_obj = {
            'ts': datetime.now().strftime('%H:%M:%S'),
            'campaign': campaign or self.status.get('current_campaign', 'Sin campaña'),
            'mission': mission or self.status.get('current_mission', 'Sin misión'),
            'message': message,
            'type': error_type
        }
        
        # Agregar detalles adicionales si se proporcionan
        if details:
            error_obj['details'] = details
        
        self.status['errors'].append(error_obj)
        
        # Log del error
        self.logger.error(f"[{error_type.upper()}] {message} - Campaña: {error_obj['campaign']}, Misión: {error_obj['mission']}")
        
        # Actualizar el detalle del estado según el tipo de error
        if error_type == 'lm_studio':
            self.status['detail'] = f"❌ LM Studio: {message}"
        elif error_type == 'translation':
            self.status['detail'] = f"⚠️ Traducción: {message}"
        elif error_type == 'file_operation':
            self.status['detail'] = f"📁 Archivo: {message}"
        elif error_type == 'network':
            self.status['detail'] = f"🌐 Red: {message}"
        else:
            self.status['detail'] = f"❌ {message}"
    
    def _add_progress_log(self, message: str, log_type: str = 'info', campaign: str = None, mission: str = None):
        """Agregar entrada de log de progreso"""
        from datetime import datetime
        
        log_entry = {
            'ts': datetime.now().strftime('%H:%M:%S'),
            'type': log_type,
            'message': message,
            'campaign': campaign or self.status.get('current_campaign'),
            'mission': mission or self.status.get('current_mission')
        }
        
        # Inicializar la lista de logs si no existe
        if 'progress_logs' not in self.status:
            self.status['progress_logs'] = []
        
        self.status['progress_logs'].append(log_entry)
        
        # Mantener solo los últimos 50 logs para evitar sobrecarga
        if len(self.status['progress_logs']) > 50:
            self.status['progress_logs'] = self.status['progress_logs'][-50:]
        
        # Log según el tipo
        if log_type == 'info':
            self.logger.info(f"🔄 {message}")
        elif log_type == 'success':
            self.logger.info(f"✅ {message}")
        elif log_type == 'warning':
            self.logger.warning(f"⚠️ {message}")
        elif log_type == 'error':
            self.logger.error(f"❌ {message}")
    
    def _add_lm_studio_status(self, status_info: Dict[str, Any], campaign: str = None):
        """Agregar información específica del estado de LM Studio"""
        from datetime import datetime
        
        if not status_info.get('available'):
            error_message = f"LM Studio no disponible: {status_info.get('error_message', 'Servicio no encontrado')}"
            suggestion = status_info.get('suggestion', 'Verifica que esté ejecutándose.')
            
            self._add_error(error_message, campaign, error_type='lm_studio')
            self.status['detail'] = f"❌ LM Studio no disponible"
            
            # Agregar información detallada de sugerencia
            self._add_error(f"Sugerencia: {suggestion}", campaign, error_type='lm_studio_help')
            
        elif not status_info.get('models_loaded'):
            error_message = f"Sin modelos cargados en LM Studio: {status_info.get('error_message', 'No hay modelos disponibles')}"
            suggestion = status_info.get('suggestion', 'Carga un modelo primero.')
            
            self._add_error(error_message, campaign, error_type='lm_studio')
            self.status['detail'] = f"⚠️ Intentando cargar modelo automáticamente..."
            
            # Agregar información detallada de sugerencia
            self._add_error(f"Sugerencia: {suggestion}", campaign, error_type='lm_studio_help')
            
        else:
            # LM Studio está bien, limpiar errores previos de LM Studio
            self.status['errors'] = [e for e in self.status['errors'] if e.get('type') not in ['lm_studio', 'lm_studio_help']]
            self.status['detail'] = "✅ LM Studio disponible y listo"
            
            # Solo agregar log positivo si previamente había errores de LM Studio o es la primera verificación
            previous_lm_errors = any(e.get('type', '').startswith('lm_studio') for e in self.status.get('errors', []))
            if previous_lm_errors or not hasattr(self, '_lm_studio_verified'):
                self._add_progress_log("✅ LM Studio conectado y funcionando correctamente", 'success', campaign)
                self._lm_studio_verified = True
    
    def scan_campaigns(self, root_dir: str) -> List[Dict[str, Any]]:
        """Escanea campañas en el directorio especificado"""
        campaigns = []
        
        if not os.path.exists(root_dir):
            raise ValueError(f"Directorio no encontrado: {root_dir}")
        
        try:
            # Buscar campañas principales (excluir subcarpetas de traducción)
            for item in os.listdir(root_dir):
                campaign_path = os.path.join(root_dir, item)
                
                if not os.path.isdir(campaign_path):
                    continue
                
                # Filtrar carpetas de traducción y subcarpetas
                if self._is_translation_folder(item, campaign_path):
                    continue
                
                # Buscar archivos .miz en la carpeta principal
                miz_files = glob.glob(os.path.join(campaign_path, "*.miz"))
                
                if miz_files:
                    # Obtener información de las misiones
                    missions = self._scan_missions_in_campaign(campaign_path, miz_files)
                    
                    campaigns.append({
                        'name': item,
                        'path': campaign_path,
                        'missions_count': len(missions),
                        'missions': missions,
                        'size_mb': self._calculate_campaign_size(missions)
                    })
            
            # Ordenar por nombre
            campaigns.sort(key=lambda x: x['name'].lower())
            
            self.logger.info(f"Encontradas {len(campaigns)} campañas en {root_dir}")
            return campaigns
            
        except Exception as e:
            self.logger.error(f"Error escaneando campañas: {e}")
            raise
    
    def run_orchestrator(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta la orquestación completa de traducción
        Migrado y mejorado desde la función run_orchestrator original
        """
        if self.status['is_running']:
            raise RuntimeError("Ya hay una traducción en ejecución")
        
        try:
            self._start_orchestration(payload)
            
            # Validar payload
            required_fields = ['ROOT_DIR', 'ARGS', 'mode', 'campaigns']
            missing = [field for field in required_fields if not payload.get(field)]
            if missing:
                raise ValueError(f"Campos requeridos faltantes: {missing}")
            
            # Configurar directorios (sin session_id, directo en TRANSLATIONS_DIR)
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            ensure_directory(TRANSLATIONS_DIR)
            
            # Procesar según el modo (compatibilidad con modos nuevos y antiguos)
            mode = payload['mode']
            results = {
                'session_id': session_id,
                'mode': mode,
                'campaigns': [],
                'total_missions': 0,
                'successful_missions': 0,
                'failed_missions': 0,
                'start_time': datetime.now().isoformat(),
                'errors': []
            }
            
            # El mapping de modos se hace ahora en _translate_campaign antes del workflow
            self.logger.info(f"Modo recibido: {mode} -> Procesando con orquestador")
            
            if mode in ['translate', 'all', 'traducir']:
                results.update(self._execute_translation_mode(payload))
            
            if mode in ['miz', 'all', 'reempaquetar']:
                results.update(self._execute_miz_mode(payload))
            
            if mode in ['deploy', 'desplegar']:
                results.update(self._execute_deploy_mode(payload))
            
            # Finalizar
            results['end_time'] = datetime.now().isoformat()
            results['duration'] = self._calculate_duration(results['start_time'], results['end_time'])
            
            # FIX: No generar reportes generales - solo reportes individuales por misión
            # Los reportes se generan automáticamente por cada misión en TranslationEngine
            # self._generate_session_report(results)
            
            # Finalizar con el resultado de la ejecución
            self._finish_orchestration(results)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error en orquestación: {e}")
            self._add_error(f"Error crítico: {str(e)}")
            # En caso de error, también intentar guardar el resumen
            error_result = {
                'mode': payload.get('mode', 'unknown'),
                'error': str(e),
                'campaigns': [],
                'success': False
            }
            self._finish_orchestration(error_result)
            raise
        finally:
            # Ya no llamamos _finish_orchestration aquí porque se llama antes del return
            pass
    
    def cancel_current_operation(self) -> bool:
        """Cancela la operación actual y descarga todos los modelos de forma forzada"""
        self.logger.info("🛑 Iniciando cancelación FORZADA de operación...")
        
        try:
            # 1. Marcar flag de cancelación INMEDIATAMENTE
            self.status['cancellation_requested'] = True
            self.status['phase'] = 'cancelling'
            self.status['detail'] = 'CANCELANDO FORZADAMENTE... terminando procesos y limpiando recursos'
            
            # 2. Parar proceso actual de forma agresiva
            if self.current_process:
                self.logger.info("🔪 Terminando proceso actual FORZADAMENTE...")
                try:
                    self._kill_process_aggressively(self.current_process)
                    self.current_process = None
                    self.logger.info("✅ Proceso terminado exitosamente")
                except Exception as proc_error:
                    self.logger.error(f"❌ Error terminando proceso: {proc_error}")
            
            # 3. Cancelar en motor de traducción si existe
            if hasattr(self, 'translation_engine') and self.translation_engine:
                try:
                    self.logger.info("🛑 Señalando cancelación al motor de traducción...")
                    self.translation_engine.cancel_current_translation()
                except Exception as te_error:
                    self.logger.error(f"❌ Error cancelando motor de traducción: {te_error}")
            
            # 4. PARADA FORZADA COMPLETA de LM Studio
            self.logger.info("🚫 PARANDO LM Studio completamente (modelos + servidor)...")
            try:
                from app.services.lm_studio import LMStudio
                lm_studio = LMStudio()
                
                # Usar parada forzada completa (unload + stop server)
                force_stop_result = lm_studio.force_stop_server_and_unload()
                
                if force_stop_result.get('success'):
                    self.logger.info("✅ LM Studio parado completamente (modelos descargados + servidor parado)")
                else:
                    self.logger.warning(f"⚠️ Parada parcial de LM Studio: {force_stop_result.get('message', 'Error desconocido')}")
                    
                    # Fallback: intentar solo descarga si la parada completa falló
                    self.logger.info("🔄 Intentando solo descarga de modelos como fallback...")
                    unload_result = lm_studio.unload_all_models()
                    
                    if unload_result.get('success'):
                        self.logger.info("✅ Modelos descargados como fallback")
                    else:
                        self.logger.error(f"❌ Error en fallback de descarga: {unload_result.get('message', 'Unknown error')}")
                        
            except Exception as lm_error:
                self.logger.error(f"❌ Error descargando modelos de LM Studio: {lm_error}")
            
            # 5. Limpiar TODOS los estados de ejecución
            self.status['is_running'] = False
            self.status['phase'] = 'cancelled'
            self.status['detail'] = 'Operación CANCELADA FORZADAMENTE por el usuario - Todos los recursos limpiados'
            self.status['cancellation_requested'] = False
            
            # Reset de progreso
            self.status['progress'] = 0
            self.status['current_mission'] = None
            self.status['current_campaign'] = None
            
            # Limpiar referencia al motor de traducción
            if hasattr(self, 'translation_engine') and self.translation_engine:
                self.translation_engine.orchestrator = None
                self.translation_engine = None
            
            # Limpiar contadores de lotes
            if 'batch_counters' in self.status:
                self.status['batch_counters'] = {
                    'cache_hits': 0,
                    'model_calls': 0,
                    'timestamp': 0
                }
            
            self.logger.info("✅ Operación cancelada FORZADAMENTE - TODOS los recursos limpiados")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error crítico cancelando operación: {e}")
            # Aún así marcar como no ejecutándose para evitar estados inconsistentes
            self.status['is_running'] = False
            self.status['cancellation_requested'] = False
            self.status['phase'] = 'error'
            self.status['detail'] = f'Error en cancelación forzada: {str(e)}'
            return False
    
    def _update_mission_progress(self, mission_name: str, campaign_name: str = None, success: bool = None):
        """Actualiza el progreso de procesamiento de misiones"""
        self.status['current_mission'] = mission_name
        if campaign_name:
            self.status['current_campaign'] = campaign_name
            
        if success is not None:
            self.status['missions_processed'] += 1
            if success:
                self.status['missions_successful'] += 1
                self._add_progress_log(f"✅ Misión completada: {mission_name}", 'success', campaign_name, mission_name)
            else:
                self.status['missions_failed'] += 1
                self._add_progress_log(f"❌ Misión falló: {mission_name}", 'error', campaign_name, mission_name)
            
            # Mantener información de lotes después de completar para mostrar en UI
            # Solo resetear cuando inicie una nueva misión
        else:
            # Misión iniciando - resetear y preparar información de lotes
            self._reset_batch_info()
            self._add_progress_log(f"🔄 Procesando misión: {mission_name}", 'info', campaign_name, mission_name)
            
            # Simular información de lotes basada en tamaño estimado de la misión
            # En una implementación real, esto vendría del TranslationEngine
            estimated_batches = self._estimate_mission_batches(mission_name)
            self._update_batch_progress(total_batches=estimated_batches)
                
        # Calcular progreso basado en misiones procesadas
        if self.status['missions_total'] > 0:
            self.status['progress'] = int((self.status['missions_processed'] / self.status['missions_total']) * 100)
    
    def _estimate_mission_batches(self, mission_name: str) -> int:
        """Estima el número de lotes para una misión (simulación temporal)"""
        # Simulación: misiones diferentes tienen diferentes cantidades de lotes
        base_batches = 20  # Base de lotes por misión
        
        # Ajustar según el nombre de la misión (simulación)
        if 'C1' in mission_name:
            return base_batches + 5
        elif 'C2' in mission_name:
            return base_batches + 10
        elif 'C3' in mission_name:
            return base_batches + 15
        else:
            return base_batches
    
    def _start_batch_progress_simulation(self, mission_name: str):
        """Inicia la simulación de progreso de lotes para una misión"""
        import threading
        import time
        import random
        
        # Detener cualquier simulación anterior
        self._stop_batch_progress_simulation()
        
        # Configurar nueva simulación
        self.batch_simulation_active = True
        
        def simulate_batch_progress():
            total_batches = self.current_batch_info['total_batches']
            processed = 0
            cache_hits = 0
            model_calls = 0
            
            while self.batch_simulation_active and processed < total_batches:
                # Simular procesamiento de un lote
                time.sleep(random.uniform(0.5, 2.0))  # Tiempo variable por lote
                
                if not self.batch_simulation_active:
                    break
                    
                processed += 1
                
                # Simular si este lote viene del cache o del modelo (70% cache, 30% modelo)
                if random.random() < 0.7:
                    cache_hits += 1
                else:
                    model_calls += 1
                
                # Actualizar progreso
                self._update_batch_progress(
                    processed_batches=processed,
                    cache_hits=cache_hits,
                    model_calls=model_calls
                )
                
            # Asegurar que se complete al 100%
            if self.batch_simulation_active:
                self._update_batch_progress(
                    processed_batches=total_batches,
                    cache_hits=cache_hits,
                    model_calls=model_calls
                )
        
        # Iniciar hilo de simulación
        try:
            self.batch_simulation_thread = threading.Thread(target=simulate_batch_progress, daemon=True)
            self.batch_simulation_thread.start()
        except Exception as e:
            self.logger.warning(f"Error al iniciar hilo de simulación de progreso: {e}")
            self.batch_simulation_thread = None
    
    def _stop_batch_progress_simulation(self):
        """Detiene la simulación de progreso de lotes"""
        self.batch_simulation_active = False
        if (hasattr(self, 'batch_simulation_thread') and 
            self.batch_simulation_thread is not None and 
            self.batch_simulation_thread.is_alive()):
            self.batch_simulation_thread.join(timeout=1.0)  # Esperar máximo 1 segundo
        # Limpiar referencia al hilo
        self.batch_simulation_thread = None

    def get_current_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual de la orquestación"""
        status = self.status.copy()
        
        # Agregar información de progreso de lotes si está disponible
        if hasattr(self, 'current_batch_info'):
            status.update(self.current_batch_info)
        
        return status
    
    def _reset_batch_info(self):
        """Resetea la información de lotes al iniciar una nueva misión"""
        self.current_batch_info = {
            'total_batches': 0,
            'processed_batches': 0,
            'batch_progress': 0,
            'cache_hits': 0,
            'model_calls': 0
        }
    
    def _update_batch_progress(self, total_batches: int = None, processed_batches: int = None, 
                             cache_hits: int = None, model_calls: int = None):
        """Actualiza el progreso de procesamiento de lotes"""
        if total_batches is not None:
            self.current_batch_info['total_batches'] = total_batches
        
        if processed_batches is not None:
            self.current_batch_info['processed_batches'] = processed_batches
            
        if cache_hits is not None:
            self.current_batch_info['cache_hits'] = cache_hits
            
        if model_calls is not None:
            self.current_batch_info['model_calls'] = model_calls
        
        # Calcular progreso de lotes
        if self.current_batch_info['total_batches'] > 0:
            progress = (self.current_batch_info['processed_batches'] / self.current_batch_info['total_batches']) * 100
            self.current_batch_info['batch_progress'] = min(100, max(0, int(progress)))
        
        # Log del progreso de lotes
        if total_batches or processed_batches:
            self._add_progress_log(
                f"📊 Lotes: {self.current_batch_info['processed_batches']}/{self.current_batch_info['total_batches']} "
                f"| ⚡ Cache: {self.current_batch_info['cache_hits']} | 🤖 Modelo: {self.current_batch_info['model_calls']}", 
                'info'
            )
    
    def _create_progress_callback(self):
        """Crea un callback de progreso para usar en deploy"""
        def progress_callback(mission_name: str, campaign_name: str = None, success: bool = None):
            if success is None:
                # Misión iniciando - solo actualizar la misión actual
                self.status['current_mission'] = mission_name
                if campaign_name:
                    self.status['current_campaign'] = campaign_name
                self.status['detail'] = f'Desplegando: {mission_name}'
                self.logger.info(f"🔄 Desplegando: {mission_name}")
            else:
                # Misión completada - actualizar contadores
                self._update_mission_progress(mission_name, campaign_name, success)
                if success:
                    self.logger.info(f"✅ Deploy exitoso: {mission_name}")
                else:
                    self.logger.warning(f"❌ Deploy falló: {mission_name}")
        
        return progress_callback
    
    def auto_detect_dcs_roots(self, deep_scan: bool = False) -> List[str]:
        """
        Detecta automáticamente directorios de DCS
        Usa detección automática de unidades disponibles, no rutas hardcodeadas
        y registra las campañas encontradas para uso futuro.
        """
        roots = []
        registry = get_campaign_registry()
        
        try:
            # Verificar cambios en unidades (conectadas/desconectadas)
            drive_changes = registry.detect_drive_changes()
            if drive_changes['disconnected']:
                self.logger.warning(f"Unidades desconectadas detectadas: {drive_changes['disconnected']}")
                self._add_error(f"Unidades desconectadas: {', '.join(drive_changes['disconnected'])}", 
                              error_type='drive_disconnected')
            
            if drive_changes['connected']:
                self.logger.info(f"Nuevas unidades conectadas: {drive_changes['connected']}")
            
            # Primero verificar campañas ya registradas y disponibles
            available_campaigns = registry.get_all_campaigns(only_available=True)
            if available_campaigns:
                registered_roots = list(set([
                    os.path.dirname(campaign.path) 
                    for campaign in available_campaigns
                    if os.path.exists(campaign.path)
                ]))
                if registered_roots:
                    self.logger.info(f"Usando campañas registradas disponibles: {len(registered_roots)} rutas")
                    roots.extend(registered_roots)
            
            # Primero intentar encontrar DCS usando información del sistema
            system_paths = self._get_dcs_paths_from_system()
            roots.extend(system_paths)
            
            if roots:
                self.logger.info(f"DCS encontrado via información del sistema: {roots}")
                # Registrar campañas encontradas
                self._register_found_campaigns(roots, 'system')
                return sorted(list(set(roots)))
            
            # Detectar automáticamente todas las unidades disponibles
            import string
            available_drives = []
            for drive_letter in string.ascii_uppercase:
                drive_path = f"{drive_letter}:\\"
                if os.path.exists(drive_path):
                    available_drives.append(drive_letter)
            
            self.logger.info(f"Unidades detectadas para escaneo DCS: {available_drives}")
            
            # Búsqueda rápida en ubicaciones comunes en todas las unidades detectadas
            common_locations = [
                "Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns",
                "Program Files (x86)\\Eagle Dynamics\\DCS World\\Mods\\campaigns",
                "Program Files\\Steam\\steamapps\\common\\DCSWorld\\Mods\\campaigns",
                "Program Files (x86)\\Steam\\steamapps\\common\\DCSWorld\\Mods\\campaigns",
                "Steam\\steamapps\\common\\DCSWorld\\Mods\\campaigns",
                "Games\\DCS World\\Mods\\campaigns",
                "Epic Games\\DCSWorld\\Mods\\campaigns"
            ]
            
            # Escanear todas las unidades disponibles para ubicaciones comunes
            for drive_letter in available_drives:
                for location in common_locations:
                    full_path = f"{drive_letter}:\\{location}"
                    try:
                        if os.path.exists(full_path) and self._has_campaigns(full_path):
                            roots.append(full_path)
                            self.logger.info(f"✅ DCS encontrado (búsqueda rápida): {full_path}")
                    except (OSError, PermissionError):
                        # Silenciosamente omitir rutas sin acceso
                        continue
            
            # Búsqueda profunda si se solicita O si no se encontró nada en la búsqueda rápida
            if deep_scan or not roots:
                self.logger.info("Iniciando búsqueda profunda...")
                deep_results = self._deep_scan_for_dcs()
                roots.extend(deep_results)
            
            # Registrar campañas encontradas antes de devolver resultados
            if roots:
                detection_method = 'deep_scan' if deep_scan else 'quick_scan'
                self._register_found_campaigns(roots, detection_method)
            
            # Remover duplicados y ordenar
            unique_roots = sorted(list(set(roots)))
            
            # Mostrar resumen del estado de unidades
            status_summary = registry.get_drive_status_summary()
            if status_summary['warnings']:
                for warning in status_summary['warnings']:
                    self.logger.warning(f"Estado de unidades: {warning}")
                    self._add_error(warning, error_type='drive_status')
            
            self.logger.info(f"Detección automática completada: {len(unique_roots)} rutas encontradas")
            self.logger.info(f"Estado general: {status_summary['available_campaigns']} campañas disponibles, "
                           f"{status_summary['unavailable_campaigns']} no disponibles")
            for root in unique_roots:
                self.logger.info(f"  - {root}")
            
            return unique_roots
            
        except Exception as e:
            self.logger.error(f"Error en detección automática: {e}")
            return []
    
    def _start_orchestration(self, payload: Dict[str, Any]):
        """Inicia el proceso de orquestación"""
        import time
        
        # Calcular total de misiones de todas las campañas
        total_missions = 0
        for campaign in payload.get('campaigns', []):
            total_missions += len(campaign.get('missions', []))
        
        # Marcar que las traducciones están activas para optimizar el cache de LM Studio
        self._lm_studio_cache['translation_active'] = True
        
        self.status.update({
            'is_running': True,
            'phase': 'initializing',
            'detail': 'Iniciando orquestación...',
            'progress': 0,
            'current_campaign': None,
            'current_mission': None,
            'missions_total': total_missions,
            'missions_processed': 0,
            'missions_successful': 0,
            'missions_failed': 0,
            'errors': [],
            'progress_logs': [],  # Limpiar logs previos al iniciar nueva ejecución
            'start_time': time.time()  # Usar timestamp para cálculo fácil de duración
        })
        
        # Limpiar cache de LM Studio al iniciar nueva ejecución
        self._lm_studio_cache['last_check'] = 0
        self._lm_studio_cache['status'] = None
        
        self.logger.info("Iniciando orquestación de traducción DCS")
        self.logger.info(f"Modo: {payload.get('mode', 'unknown')}")
        self.logger.info(f"Campañas: {len(payload.get('campaigns', []))}")
        self.logger.info(f"Total de misiones: {total_missions}")
        
        # Log inicial de progreso
        self._add_progress_log(f"Orquestación iniciada - Modo: {payload.get('mode', 'unknown')}", 'info')
        self._add_progress_log(f"Procesando {len(payload.get('campaigns', []))} campañas con {total_missions} misiones", 'info')
    
    def _finish_orchestration(self, execution_result: Dict[str, Any] = None):
        """Finaliza el proceso de orquestación y guarda el resultado"""
        import time
        
        # Calcular duración total
        start_time = self.status.get('start_time')
        duration = time.time() - start_time if start_time else 0
        
        # Log final de progreso
        if execution_result and execution_result.get('success', True):
            self._add_progress_log(f"✅ Orquestación completada exitosamente en {duration:.1f}s", 'success')
        else:
            self._add_progress_log(f"⚠️ Orquestación finalizada con errores en {duration:.1f}s", 'warning')
        
        # Desmarcar que las traducciones están activas
        self._lm_studio_cache['translation_active'] = False
        
        # Asegurar que el progreso de lotes esté en 100% al completar
        if hasattr(self, 'current_batch_info') and self.current_batch_info.get('total_batches', 0) > 0:
            self.current_batch_info['batch_progress'] = 100
            self.current_batch_info['processed_batches'] = self.current_batch_info['total_batches']
        
        self.status.update({
            'is_running': False,
            'phase': 'completed',
            'detail': 'Orquestación finalizada',
            'progress': 100,
            'completion_time': time.time()  # Agregar timestamp de finalización
        })
        
        # Guardar resultado de ejecución si se proporcionó
        if execution_result:
            self._save_execution_summary(execution_result, duration)
        
        self.logger.info("Orquestación finalizada")
    
    def _save_execution_summary(self, result: Dict[str, Any], duration: float):
        """Guarda el resumen de la última ejecución"""
        from datetime import datetime
        
        try:
            # Procesar campañas para extraer información detallada
            campaigns_summary = []
            total_missions = 0
            successful_missions = 0
            failed_missions = 0
            total_errors = 0
            
            for campaign_key in ['translated_campaigns', 'packaged_campaigns', 'deployed_campaigns']:
                if campaign_key in result:
                    for campaign in result[campaign_key]:
                        campaign_summary = {
                            'name': campaign.get('name', 'Unknown'),
                            'success': campaign.get('success', False),
                            'missions': [],
                            'errors': campaign.get('errors', [])
                        }
                        
                        # Procesar misiones de la campaña
                        campaign_missions = campaign.get('missions', [])
                        for mission in campaign_missions:
                            # El nombre puede estar en 'mission', 'name', o extraerlo del archivo
                            mission_name = mission.get('name', mission.get('mission', 'Unknown'))
                            # Limpiar extensión .miz si existe
                            if mission_name.endswith('.miz'):
                                mission_name = mission_name[:-4]
                            
                            mission_summary = {
                                'name': mission_name,
                                'success': mission.get('success', False),
                                'errors': mission.get('errors', []),
                                'duration': mission.get('duration', 0),
                                'cache_hits': mission.get('cache_hits', 0),
                                'api_calls': mission.get('api_calls', 0),
                                'processing_time': mission.get('processing_time', 0)
                            }
                            campaign_summary['missions'].append(mission_summary)
                            
                            total_missions += 1
                            if mission_summary['success']:
                                successful_missions += 1
                            else:
                                failed_missions += 1
                            
                            total_errors += len(mission_summary['errors'])
                        
                        total_errors += len(campaign_summary['errors'])
                        campaigns_summary.append(campaign_summary)
            
            # Calcular estadísticas globales de caché
            total_cache_hits = 0
            total_api_calls = 0
            total_processing_time = 0
            
            for campaign in campaigns_summary:
                for mission in campaign['missions']:
                    total_cache_hits += mission.get('cache_hits', 0)
                    total_api_calls += mission.get('api_calls', 0)
                    total_processing_time += mission.get('processing_time', 0)
            
            # Crear resumen de ejecución
            self.last_execution = {
                'timestamp': datetime.now().isoformat(),
                'mode': result.get('mode', 'unknown'),
                'duration': duration,
                'campaigns': campaigns_summary,
                'total_missions': total_missions,
                'successful_missions': successful_missions,
                'failed_missions': failed_missions,
                'total_errors': total_errors,
                'success': successful_missions > 0 and failed_missions == 0,
                'cache_stats': {
                    'total_cache_hits': total_cache_hits,
                    'total_api_calls': total_api_calls,
                    'total_processing_time': total_processing_time,
                    'cache_hit_rate': (total_cache_hits / (total_cache_hits + total_api_calls) * 100) if (total_cache_hits + total_api_calls) > 0 else 0
                }
            }
            
            self.logger.info(f"Resumen de ejecución guardado: {total_missions} misiones, {successful_missions} exitosas, {failed_missions} fallidas")
            
            # Guardar persistentemente
            self._save_last_execution()
            
        except Exception as e:
            self.logger.error(f"Error guardando resumen de ejecución: {e}")
            # Crear un resumen básico en caso de error
            self.last_execution = {
                'timestamp': datetime.now().isoformat(),
                'mode': result.get('mode', 'unknown') if result else 'unknown',
                'duration': duration,
                'campaigns': [],
                'total_missions': 0,
                'successful_missions': 0,
                'failed_missions': 0,
                'total_errors': 1,
                'success': False,
                'error': f"Error procesando resultado: {e}"
            }
            
            # Guardar incluso en caso de error
            self._save_last_execution()
    
    def _load_last_execution(self) -> Optional[Dict[str, Any]]:
        """Carga el último resultado de ejecución desde archivo"""
        try:
            if os.path.exists(self.persistence_file):
                with open(self.persistence_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.logger.info(f"✅ Last execution cargado desde archivo: {data.get('mode', 'unknown')} ({data.get('timestamp', 'sin fecha')})")
                    return data
            else:
                self.logger.info("ℹ️ No hay archivo de last_execution previo")
                return None
        except Exception as e:
            self.logger.warning(f"⚠️ Error cargando last_execution: {e}")
            return None
    
    def _save_last_execution(self):
        """Guarda el último resultado de ejecución en archivo"""
        try:
            if self.last_execution is None:
                return
            
            # Asegurar que el directorio existe
            ensure_directory(os.path.dirname(self.persistence_file))
            
            # Guardar en archivo JSON
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(self.last_execution, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"💾 Last execution guardado persistentemente: {self.last_execution.get('mode')} ({self.last_execution.get('timestamp')})")
            
        except Exception as e:
            self.logger.error(f"❌ Error guardando last_execution: {e}")
    
    def _execute_translation_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el modo de traducción"""
        self.status['phase'] = 'translating'
        self.status['detail'] = 'Iniciando proceso de traducción...'
        
        campaigns = payload['campaigns']
        self._add_progress_log(f"Iniciando traducción de {len(campaigns)} campaña(s)", 'info')
        
        results = {
            'translated_campaigns': [],
            'translation_errors': []
        }
        
        for i, campaign_info in enumerate(campaigns):
            try:
                campaign_name = campaign_info['name']
                campaign_path = campaign_info['path']
                
                self.status['current_campaign'] = campaign_name
                self.status['progress'] = int((i / len(campaigns)) * 50)  # 50% para traducción
                
                self._add_progress_log(f"Procesando campaña: {campaign_name}", 'info', campaign_name)
                
                # Crear directorio para esta campaña (directo en TRANSLATIONS_DIR, sin session_id)
                from config.settings import TRANSLATIONS_DIR
                campaign_output_dir = os.path.join(TRANSLATIONS_DIR, self._slugify(campaign_name))
                ensure_directory(campaign_output_dir)
                
                # Traducir misiones de la campaña
                selected_missions = campaign_info.get('missions', [])
                self.logger.info(f"🔍 DEBUG: Procesando campaña {campaign_name}")
                self.logger.info(f"   Ruta: {campaign_path}")
                self.logger.info(f"   Misiones seleccionadas: {len(selected_missions)}")
                
                self._add_progress_log(f"Encontradas {len(selected_missions)} misiones para traducir", 'info', campaign_name)
                
                for i, mission in enumerate(selected_missions):
                    self.logger.info(f"      {i+1}. {mission}")
                
                # Obtener configuración de cache del payload
                use_cache = payload.get('use_cache', True)
                overwrite_cache = payload.get('overwrite_cache', False)
                
                cache_msg = "con cache activado" if use_cache else "sin cache"
                if overwrite_cache:
                    cache_msg += " (sobrescribiendo cache existente)"
                
                self._add_progress_log(f"Iniciando traducción {cache_msg}", 'info', campaign_name)
                
                campaign_result = self._translate_campaign(
                    campaign_path, campaign_name, campaign_output_dir, payload, selected_missions, 
                    use_cache=use_cache, overwrite_cache=overwrite_cache
                )
                
                results['translated_campaigns'].append(campaign_result)
                
                # Log del resultado de la campaña
                if campaign_result.get('success', False):
                    self._add_progress_log(f"Campaña completada exitosamente", 'success', campaign_name)
                else:
                    self._add_progress_log(f"Campaña completada con errores", 'warning', campaign_name)
                
            except Exception as e:
                error_msg = f"Error traduciendo campaña {campaign_info.get('name', 'unknown')}: {e}"
                self.logger.error(error_msg)
                self._add_error(error_msg, campaign_info.get('name'), error_type='translation')
                self._add_progress_log(f"Error en campaña: {str(e)}", 'error', campaign_info.get('name'))
                results['translation_errors'].append(error_msg)
                self._add_error(error_msg, campaign_info.get('name', 'unknown'))
        
        return results
    
    def _execute_miz_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el modo de empaquetado MIZ"""
        self.status['phase'] = 'packaging'
        self.status['detail'] = 'Empaquetando archivos MIZ...'
        
        campaigns = payload['campaigns']
        results = {
            'packaged_campaigns': [],
            'packaging_errors': []
        }
        
        for i, campaign_info in enumerate(campaigns):
            try:
                campaign_name = campaign_info['name']
                campaign_path = campaign_info['path']
                
                self.status['current_campaign'] = campaign_name
                self.status['progress'] = int((i / len(campaigns)) * 50)  # 50% para empaquetado
                
                # Crear directorio para esta campaña (directo en TRANSLATIONS_DIR, sin session_id)
                from config.settings import TRANSLATIONS_DIR
                campaign_output_dir = os.path.join(TRANSLATIONS_DIR, self._slugify(campaign_name))
                ensure_directory(campaign_output_dir)
                
                # Reempaquetar misiones de la campaña
                selected_missions = campaign_info.get('missions', [])
                self.logger.info(f"🔍 DEBUG: Reempaquetando campaña {campaign_name}")
                self.logger.info(f"   Ruta: {campaign_path}")
                self.logger.info(f"   Misiones seleccionadas: {len(selected_missions)}")
                for j, mission in enumerate(selected_missions):
                    self.logger.info(f"      {j+1}. {mission}")
                
                # Obtener configuración de cache del payload  
                use_cache = payload.get('use_cache', True)
                overwrite_cache = payload.get('overwrite_cache', False)
                
                campaign_result = self._translate_campaign(
                    campaign_path, campaign_name, campaign_output_dir, payload, selected_missions, 
                    use_cache=use_cache, overwrite_cache=overwrite_cache
                )
                
                results['packaged_campaigns'].append(campaign_result)
                
            except Exception as e:
                error_msg = f"Error reempaquetando campaña {campaign_info.get('name', 'unknown')}: {e}"
                self.logger.error(error_msg)
                results['packaging_errors'].append(error_msg)
                self._add_error(error_msg, campaign_info.get('name', 'unknown'))
        
        return results
    
    def _execute_deploy_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el modo de despliegue"""
        self.status['phase'] = 'deploying'
        self.status['detail'] = 'Desplegando archivos...'
        
        campaigns = payload['campaigns']
        results = {
            'deployed_campaigns': [],
            'deployment_errors': []
        }
        
        for i, campaign_info in enumerate(campaigns):
            try:
                campaign_name = campaign_info['name']
                campaign_path = campaign_info['path']
                
                self.status['current_campaign'] = campaign_name
                self.status['progress'] = int((i / len(campaigns)) * 50)  # 50% para despliegue
                
                # Crear directorio para esta campaña (directo en TRANSLATIONS_DIR, sin session_id)
                from config.settings import TRANSLATIONS_DIR
                campaign_output_dir = os.path.join(TRANSLATIONS_DIR, self._slugify(campaign_name))
                ensure_directory(campaign_output_dir)
                
                # Desplegar misiones de la campaña
                selected_missions = campaign_info.get('missions', [])
                self.logger.info(f"🔍 DEBUG: Desplegando campaña {campaign_name}")
                self.logger.info(f"   Ruta: {campaign_path}")
                self.logger.info(f"   Misiones seleccionadas: {len(selected_missions)}")
                for j, mission in enumerate(selected_missions):
                    self.logger.info(f"      {j+1}. {mission}")
                
                # Configurar workflow para deploy
                config = {
                    'campaign_name': campaign_name,
                    'campaign_path': campaign_path,
                    'missions': selected_missions,
                    'deploy_dir': payload.get('DEPLOY_DIR', campaign_path),
                    'deploy_overwrite': payload.get('DEPLOY_OVERWRITE', False),
                    'mode': 'deploy'
                }
                
                # Crear motor de traducción y ejecutar workflow de deploy
                engine = TranslationEngine()
                
                # Establecer referencia bidireccional para cancelación
                self.translation_engine = engine
                engine.orchestrator = self
                
                # Preparar directorios de campaña
                campaign_dirs = {
                    'base': campaign_output_dir,
                    'extracted': os.path.join(campaign_output_dir, 'extracted'),
                    'finalizado': os.path.join(campaign_output_dir, 'finalizado'),
                    'out_lua': os.path.join(campaign_output_dir, 'out_lua'),
                    'backup': os.path.join(campaign_output_dir, 'backup')
                }
                
                # DEBUG: Verificar estructura de directorios
                self.logger.info(f"📁 DEBUG estructura de directorios:")
                self.logger.info(f"   Base: {campaign_dirs['base']}")
                self.logger.info(f"   Finalizado: {campaign_dirs['finalizado']}")
                self.logger.info(f"   Existe base? {os.path.exists(campaign_dirs['base'])}")
                self.logger.info(f"   Existe finalizado? {os.path.exists(campaign_dirs['finalizado'])}")
                
                # Listar contenido de directorio base si existe
                if os.path.exists(campaign_dirs['base']):
                    try:
                        base_contents = os.listdir(campaign_dirs['base'])
                        self.logger.info(f"   Contenido base: {base_contents}")
                    except Exception as e:
                        self.logger.warning(f"   Error listando base: {e}")
                
                # Ejecutar solo la fase de deploy
                deploy_result = engine._execute_deploy_phase(config, campaign_dirs, self._create_progress_callback())
                
                campaign_result = {
                    'name': campaign_name,
                    'path': campaign_path,
                    'mode': 'deploy',
                    'success': deploy_result.get('success', False),
                    'total_missions': deploy_result.get('total_deploys', 0),
                    'successful_missions': deploy_result.get('successful_deploys', 0),
                    'failed_missions': deploy_result.get('failed_deploys', 0),
                    'missions': deploy_result.get('deploy_results', []),
                    'output_directory': campaign_output_dir,
                    'errors': [],
                    'deploy_results': deploy_result
                }
                
                results['deployed_campaigns'].append(campaign_result)
                
            except Exception as e:
                error_msg = f"Error desplegando campaña {campaign_info.get('name', 'unknown')}: {e}"
                self.logger.error(error_msg)
                results['deployment_errors'].append(error_msg)
                self._add_error(error_msg, campaign_info.get('name', 'unknown'))
        
        return results
    
    def _translate_campaign(self, campaign_path: str, campaign_name: str, 
                           output_dir: str, payload: Dict[str, Any], 
                           selected_missions: List[str] = None, use_cache: bool = True, 
                           overwrite_cache: bool = False) -> Dict[str, Any]:
        """Traduce una campaña individual usando el motor de traducción integrado con utilidades del orquestador"""
        
        from app.services.translation_engine import TranslationEngine
        
        # Configurar el motor de traducción integrado
        engine = TranslationEngine()
        # Establecer referencia bidireccional para cancelación
        self.translation_engine = engine
        engine.orchestrator = self
        
        # Determinar modo de operación desde payload
        mode = payload.get('mode', 'translate')
        
        # Mapear modos nuevos a modos legacy para el workflow
        mode_mapping = {
            'traducir': 'translate',
            'reempaquetar': 'miz', 
            'desplegar': 'deploy',
            # Mantener modos legacy
            'translate': 'translate',
            'miz': 'miz',
            'all': 'all',
            'deploy': 'deploy'
        }
        
        workflow_mode = mode_mapping.get(mode, mode)
        self.logger.info(f"🔍 DEBUG: Modo original: {mode} -> Modo workflow: {workflow_mode}")
        
        # Preparar configuración completa para el workflow integrado
        workflow_config = {
            'campaign_name': campaign_name,
            'campaign_path': campaign_path,
            'missions': selected_missions or [],
            'mode': workflow_mode,
            'output_dir': output_dir,
            'lm_config': self._parse_lm_config(payload.get('ARGS', '')),
            'prompt_file': self._extract_prompt_file(payload.get('ARGS', '')),
            'batch_size': payload.get('batch_size', 4),
            'timeout': payload.get('timeout', 200),
            'file_target': self._get_file_target_from_config(payload.get('FILE_TARGET')),
            'keys_filter': payload.get('keys_filter'),
            'include_fc': payload.get('include_fc', False),
            'deploy_dir': payload.get('DEPLOY_DIR', ''),
            'deploy_overwrite': payload.get('DEPLOY_OVERWRITE', False)
        }
        
        try:
            self.status['phase'] = f'processing_{mode}'
            self.status['detail'] = f'Iniciando workflow {mode} para {campaign_name}'
            
            self._add_progress_log(f"Configurando workflow en modo {mode}", 'info', campaign_name)
            
            # Verificar estado de LM Studio si es modo de traducción
            if mode in ('translate', 'traducir'):
                lm_config = workflow_config.get('lm_config', {})
                # Obtener URL desde configuración del usuario con fallback
                from app.services.user_config import UserConfigService
                lm_url = lm_config.get('url', UserConfigService.get_lm_studio_url())
                lm_model = lm_config.get('model', 'test')
                
                # Usar verificación con cache
                lm_status = self._check_lm_studio_with_cache(engine, lm_url, lm_model, campaign_name)                # Si LM Studio no está disponible, fallar
                if not lm_status.get('available'):
                    self._add_progress_log("❌ LM Studio no está disponible", 'error', campaign_name)
                    return {
                        'name': campaign_name,
                        'path': campaign_path,
                        'mode': mode,
                        'success': False,
                        'total_missions': 0,
                        'successful_missions': 0,
                        'failed_missions': len(selected_missions or []),
                        'missions': [],
                        'output_directory': output_dir,
                        'errors': [lm_status.get('error_message', 'LM Studio no disponible')],
                        'lm_studio_status': lm_status
                    }
                
                # Si no hay modelos cargados, intentar cargar automáticamente
                if not lm_status.get('models_loaded'):
                    self._add_progress_log(f"🤖 Modelo no encontrado: {lm_model}", 'info', campaign_name)
                    self._add_progress_log(f"⏳ Iniciando carga automática del modelo... Esto puede tomar unos minutos.", 'info', campaign_name)
                    self.logger.info(f"🔄 Intentando cargar modelo desde orquestador: {lm_model}")
                    
                    # Actualizar estado para mostrar que se está cargando
                    self.status['detail'] = f'Cargando modelo {lm_model}...'
                    
                    load_success = self.lm_studio_service.load_model_via_cli(lm_model)
                    
                    if load_success:
                        self._add_progress_log(f"✅ Modelo '{lm_model}' cargado exitosamente", 'success', campaign_name)
                        self.logger.info(f"✅ Modelo '{lm_model}' cargado exitosamente")
                        
                        # Dar tiempo al modelo para estabilizarse
                        self._add_progress_log("⏳ Esperando estabilización del modelo...", 'info', campaign_name)
                        import time
                        time.sleep(3)  # Pausa de 3 segundos
                        
                        # Verificar nuevamente con verificación forzada
                        lm_status_retry = self._check_lm_studio_with_cache(engine, lm_url, lm_model, campaign_name, force_check=True)
                        lm_status = lm_status_retry
                        
                        if lm_status_retry.get('models_loaded'):
                            self._add_progress_log(f"🎯 Modelo '{lm_model}' listo para usar", 'success', campaign_name)
                            self.status['detail'] = f'Modelo cargado - Iniciando procesamiento'
                        else:
                            error_msg = f"❌ Modelo cargado pero no responde correctamente: {lm_status_retry.get('error_message', 'Error desconocido')}"
                            self._add_progress_log(error_msg, 'error', campaign_name)
                            return {
                                'name': campaign_name,
                                'path': campaign_path,
                                'mode': mode,
                                'success': False,
                                'total_missions': 0,
                                'successful_missions': 0,
                                'failed_missions': len(selected_missions or []),
                                'missions': [],
                                'output_directory': output_dir,
                                'errors': [error_msg],
                                'lm_studio_status': lm_status_retry
                            }
                    else:
                        # No se pudo cargar el modelo automáticamente
                        error_msg = f"❌ No se pudo cargar el modelo '{lm_model}'. Verifica que LM Studio esté funcionando correctamente."
                        self._add_progress_log(error_msg, 'error', campaign_name)
                        self.logger.error(f"Error cargando modelo: {lm_model}")
                        return {
                            'name': campaign_name,
                            'path': campaign_path,
                            'mode': mode,
                            'success': False,
                            'total_missions': 0,
                            'successful_missions': 0,
                            'failed_missions': len(selected_missions or []),
                            'missions': [],
                            'output_directory': output_dir,
                            'errors': [error_msg],
                            'lm_studio_status': lm_status
                        }
            
            # Usar el workflow completo integrado con callback de progreso
            self.status['detail'] = f'Procesando campaña: {campaign_name}'
            
            # Definir callback para reportar progreso en tiempo real
            def progress_callback(mission_name: str, campaign_name: str, success: bool = None):
                if success is None:
                    # Misión iniciando - solo actualizar la misión actual
                    self.status['current_mission'] = mission_name
                    self.status['current_campaign'] = campaign_name
                    self.status['detail'] = f'Procesando: {mission_name}'
                    self.logger.info(f"🔄 Iniciando procesamiento de: {mission_name}")
                    
                    # Iniciar simulación de progreso de lotes
                    self._start_batch_progress_simulation(mission_name)
                else:
                    # Misión completada - actualizar contadores
                    self._update_mission_progress(mission_name, campaign_name, success)
                    if success:
                        self.logger.info(f"✅ Completada exitosamente: {mission_name}")
                    else:
                        self.logger.warning(f"❌ Falló: {mission_name}")
                    
                    # Detener simulación de progreso de lotes
                    self._stop_batch_progress_simulation()
            workflow_result = engine.process_campaign_full_workflow(workflow_config, use_cache=use_cache, overwrite_cache=overwrite_cache, progress_callback=progress_callback)
            
            # DEBUG: Verificar resultado del workflow
            self.logger.info(f"🔍 DEBUG: Workflow completado para {campaign_name}")
            self.logger.info(f"   Success: {workflow_result.get('success', False)}")
            self.logger.info(f"   Errores: {len(workflow_result.get('errors', []))}")
            if workflow_result.get('translate_results'):
                tr = workflow_result['translate_results']
                self.logger.info(f"   Translate results - Total: {tr.get('total_missions', 0)}, Success: {tr.get('successful_missions', 0)}, Failed: {tr.get('failed_missions', 0)}")
                
                # Ya no necesitamos actualizar progreso aquí - se hizo en tiempo real con callbacks
                self.logger.info("   Progreso actualizado en tiempo real durante procesamiento")
            else:
                self.logger.info(f"   ❌ No translate_results encontrados")
                # Si no hay resultados, asumir que todas las misiones fallaron
                for mission in selected_missions or []:
                    self._update_mission_progress(mission, campaign_name, False)
            
            # Adaptar resultado al formato esperado por el orchestrator
            result = {
                'name': campaign_name,
                'path': campaign_path,
                'mode': mode,
                'success': workflow_result.get('success', False),
                'output_directory': output_dir,
                'session_id': workflow_result.get('session_id'),
                'errors': workflow_result.get('errors', []),
                'workflow_results': workflow_result
            }
            
            # Procesar resultados por fase
            total_missions = 0
            successful_missions = 0
            failed_missions = 0
            all_missions = []
            
            # Resultados de traducción
            if workflow_result.get('translate_results'):
                translate_res = workflow_result['translate_results']
                total_missions += translate_res.get('total_missions', 0)
                successful_missions += translate_res.get('successful_missions', 0)
                failed_missions += translate_res.get('failed_missions', 0)
                all_missions.extend(translate_res.get('mission_results', []))
            
            # Resultados de empaquetado MIZ
            if workflow_result.get('miz_results'):
                miz_res = workflow_result['miz_results']
                
                # Si es modo solo empaquetado, crear misiones desde miz_results
                if mode in ('miz', 'reempaquetar') and not workflow_result.get('translate_results'):
                    self.logger.info(f"🔍 DEBUG: Modo solo empaquetado - creando misiones desde miz_results")
                    for package in miz_res.get('package_results', []):
                        mission_name = package.get('mission')
                        if mission_name:
                            all_missions.append({
                                'mission': mission_name,
                                'mission_name': mission_name.replace('.miz', ''),
                                'packaged': package.get('success', False),
                                'output_miz': package.get('output_miz'),
                                'translated_file': package.get('translated_file'),
                                'success': package.get('success', False),
                                'errors': [package.get('error')] if package.get('error') else []
                            })
                            if package.get('success', False):
                                successful_missions += 1
                            else:
                                failed_missions += 1
                            total_missions += 1
                else:
                    # Agregar info de empaquetado a las misiones existentes (modo all o después de traducción)
                    for package in miz_res.get('package_results', []):
                        mission_name = package.get('mission')
                        for mission in all_missions:
                            if mission.get('mission') == mission_name:
                                mission['packaged'] = package.get('success', False)
                                mission['output_miz'] = package.get('output_miz')
            
            # Resultados de deploy
            if workflow_result.get('deploy_results'):
                deploy_res = workflow_result['deploy_results']
                
                # Si es modo solo deploy, crear misiones desde deploy_results
                if mode in ('deploy', 'desplegar') and not workflow_result.get('translate_results'):
                    self.logger.info(f"🔍 DEBUG: Modo solo deploy - creando misiones desde deploy_results")
                    for deploy in deploy_res.get('deploy_results', []):
                        mission_name = deploy.get('mission')
                        if mission_name:
                            all_missions.append({
                                'mission': mission_name,
                                'mission_name': mission_name.replace('.miz', ''),
                                'deployed': deploy.get('success', False),
                                'deployed_to': deploy.get('deployed_to'),
                                'source_file': deploy.get('source_file'),
                                'success': deploy.get('success', False),
                                'errors': [deploy.get('error')] if deploy.get('error') else []
                            })
                            if deploy.get('success', False):
                                successful_missions += 1
                            else:
                                failed_missions += 1
                            total_missions += 1
                else:
                    # Agregar info de deploy a las misiones existentes (modo all o después de traducción/empaquetado)
                    for deploy in deploy_res.get('deploy_results', []):
                        mission_name = deploy.get('mission')
                        for mission in all_missions:
                            if mission.get('mission') == mission_name:
                                mission['deployed'] = deploy.get('success', False)
                                mission['deployed_to'] = deploy.get('deployed_to')
            
            result.update({
                'total_missions': total_missions,
                'successful_missions': successful_missions,
                'failed_missions': failed_missions,
                'missions': all_missions
            })
            
            # Actualizar estado del orchestrator
            self.status['current_campaign'] = campaign_name
            self.status['progress'] = 100 if workflow_result.get('success') else 50
            
            # Agregar errores al sistema de errores del orchestrator
            for error in workflow_result.get('errors', []):
                self._add_error(error, campaign_name)
            
            # Logging de resultados
            if workflow_result.get('success'):
                self.logger.info(f"Workflow {mode} completado: {campaign_name} - {successful_missions}/{total_missions} exitosas")
                if workflow_result.get('log_zip'):
                    self.logger.info(f"ZIP de logs generado: {workflow_result['log_zip']}")
            else:
                self.logger.error(f"Workflow {mode} falló para campaña: {campaign_name}")
            
            return result
            
        except RuntimeError as e:
            # Capturar específicamente RuntimeErrors que son los que lanza el translation engine
            error_msg = f"Error en traducción de {campaign_name}: {str(e)}"
            self.logger.error(error_msg)
            
            # Detectar si es un error de LM Studio específico
            error_str = str(e)
            if any(keyword in error_str for keyword in ['LM Studio', 'modelos cargados', 'modelo no disponible', 'No models loaded']):
                self._add_error(f"Error LM Studio: {str(e)}", campaign_name, error_type='lm_studio')
                self.status['detail'] = f"❌ Error LM Studio: {str(e)}"
            else:
                self._add_error(error_msg, campaign_name, error_type='translation_error')
                self.status['detail'] = f"❌ Error de traducción: {str(e)}"
            
        except Exception as e:
            # Mensajes específicos según el modo
            if mode in ('miz', 'reempaquetar'):
                error_msg = f"No ha sido posible reempaquetar la campaña {campaign_name}: {str(e)}"
                user_friendly_detail = f"❌ No ha sido posible reempaquetar la misión"
            elif mode in ('deploy', 'desplegar'):
                error_msg = f"No ha sido posible desplegar la campaña {campaign_name}: {str(e)}"
                user_friendly_detail = f"❌ No ha sido posible desplegar la misión"
            else:
                error_msg = f"Error inesperado en workflow {mode} para campaña {campaign_name}: {e}"
                user_friendly_detail = f"❌ Error inesperado: {str(e)}"
                
            self.logger.error(error_msg)
            self._add_error(error_msg, campaign_name, error_type='general_error')
            self.status['detail'] = user_friendly_detail
            
            return {
                'name': campaign_name,
                'path': campaign_path,
                'mode': mode,
                'success': False,
                'total_missions': 0,
                'successful_missions': 0,
                'failed_missions': 1,
                'missions': [],
                'output_directory': output_dir,
                'errors': [error_msg]
            }
    
    def _process_mission_file(self, miz_file: str, mission_name: str, 
                             output_dir: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa un archivo de misión individual"""
        
        # Crear directorio temporal para extracción
        temp_dir = os.path.join(output_dir, f"temp_{self._slugify(mission_name)}")
        ensure_directory(temp_dir)
        
        try:
            # Extraer archivo MIZ
            self._extract_miz(miz_file, temp_dir)
            
            # Buscar archivo de diccionario usando configuración del usuario
            file_target = self._get_file_target_from_config(payload.get('FILE_TARGET'))
            lua_file = os.path.join(temp_dir, file_target)
            
            if not os.path.exists(lua_file):
                raise FileNotFoundError(f"Archivo de diccionario no encontrado: {file_target}")
            
            # Traducir usando el motor de traducción
            engine = TranslationEngine()
            
            # Establecer referencia bidireccional para cancelación
            self.translation_engine = engine
            engine.orchestrator = self
            
            # Crear callback de progreso real basado en segmentos procesados
            def progress_callback(progress_data):
                """Callback para actualizar el progreso real de la misión"""
                # Extraer datos del progreso
                total_segments = progress_data.get('total_segments', 0)
                processed_segments = progress_data.get('processed_segments', 0)
                cache_hits = progress_data.get('cache_hits', 0)
                model_calls = progress_data.get('model_calls', 0)
                total_batches = progress_data.get('total_batches', 0)
                processed_batches = progress_data.get('processed_batches', 0)
                segment_progress = progress_data.get('segment_progress', 0)
                phase = progress_data.get('phase', 'Procesando')
                
                # Actualizar la información de progreso con los nombres correctos que espera el JavaScript
                self.current_batch_info.update({
                    'total_batches': total_batches,
                    'processed_batches': processed_batches,
                    'batch_progress': segment_progress,  # Este es el porcentaje que usa el JS
                    'cache_hits': cache_hits,
                    'model_calls': model_calls,
                    'total_segments': total_segments,
                    'processed_segments': processed_segments
                })
                    
                # Log del progreso actual con más información
                self.logger.info(f"🔄 {phase} - {segment_progress}% ({processed_segments}/{total_segments} segmentos, {cache_hits} cache + {model_calls} modelo)")
            
            # Asignar callback al motor
            engine.progress_callback = progress_callback
            
            translation_config = {
                'file_path': lua_file,
                'output_dir': os.path.join(output_dir, 'translated'),
                'lm_config': self._parse_lm_config(payload['ARGS']),
                'prompt_file': self._extract_prompt_file(payload['ARGS']),
                'batch_size': payload.get('batch_size', 4),
                'timeout': payload.get('timeout', 200)
            }
            
            translation_result = engine.translate_file(translation_config, use_cache=payload.get('use_cache', True))
            
            return {
                'mission': mission_name,
                'success': True,
                'translation_result': translation_result,
                'output_files': [translation_result['output_file']]
            }
            
        except Exception as e:
            return {
                'mission': mission_name,
                'success': False,
                'error': str(e)
            }
        finally:
            # Limpiar directorio temporal
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _scan_missions_in_campaign(self, campaign_path: str, miz_files: List[str]) -> List[Dict[str, Any]]:
        """Escanea misiones en una campaña"""
        missions = []
        
        for miz_file in miz_files:
            try:
                mission_name = os.path.basename(miz_file)
                file_size = os.path.getsize(miz_file)
                
                # Verificar estado de traducción
                status = self._check_mission_translation_status(miz_file)
                
                missions.append({
                    'name': mission_name,
                    'path': miz_file,
                    'size': file_size,
                    'status': status
                })
                
            except Exception as e:
                self.logger.warning(f"Error escaneando misión {miz_file}: {e}")
        
        # Función para ordenación natural (numérica)
        import re
        def natural_sort_key(mission_dict):
            """
            Crear una clave de ordenación natural para nombres de misión.
            Convierte números en nombres a enteros para ordenación correcta.
            Ej: F5-E-C2 viene antes que F5-E-C10
            """
            name = mission_dict['name']
            # Separar letras y números
            parts = re.split(r'(\d+)', name.lower())
            # Convertir partes numéricas a enteros
            for i in range(len(parts)):
                if parts[i].isdigit():
                    parts[i] = int(parts[i])
            return parts
        
        # Ordenar por nombre con ordenación natural
        missions.sort(key=natural_sort_key)
        return missions
    
    def _check_mission_translation_status(self, miz_file: str) -> str:
        """Verifica el estado de traducción de una misión"""
        base_name = os.path.splitext(os.path.basename(miz_file))[0]
        
        # Construir ruta al directorio de traducciones local
        # Extraer nombre de campaña del path DCS
        miz_dir = os.path.dirname(miz_file)
        campaign_name_dcs = os.path.basename(miz_dir)
        
        # Mapear nombre de campaña DCS a nombre en traducciones
        campaign_name_local = self._map_dcs_campaign_to_local(campaign_name_dcs)
        
        # Construir ruta al directorio de traducciones (desde la raíz del proyecto)
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # app/services
        project_root = os.path.dirname(os.path.dirname(current_file_dir))  # raíz del proyecto
        translations_dir = os.path.join(project_root, "app", "data", "traducciones", campaign_name_local, base_name)
        
        # Verificar si existe directorio out_lua con archivos traducidos
        out_lua_dir = os.path.join(translations_dir, "out_lua")
        if os.path.exists(out_lua_dir):
            # Buscar archivos .translated.lua
            lua_files = [f for f in os.listdir(out_lua_dir) if f.endswith('.translated.lua')]
            if lua_files:
                return "translated"
        
        # Verificar si existe directorio finalizado
        finalized_dir = os.path.join(translations_dir, "finalizado")
        if os.path.exists(finalized_dir):
            finalized_files = [f for f in os.listdir(finalized_dir) if f.endswith('.miz')]
            if finalized_files:
                return "finalized"
        
        return "pending"
    
    def _map_dcs_campaign_to_local(self, dcs_campaign_name: str) -> str:
        """
        Mapea nombre de campaña DCS a nombre en directorio de traducciones usando reglas automáticas.
        
        Transformaciones aplicadas:
        1. Comillas simples → doble guión bajo
        2. Espacios múltiples → un solo guión bajo
        3. Caracteres especiales → guiones bajos
        4. Limpiar guiones bajos redundantes al final
        """
        import re
        
        # 1. Reemplazar comillas simples con doble guión bajo
        local_name = dcs_campaign_name.replace("'", "__")
        
        # 2. Reemplazar secuencias de espacios con un solo guión bajo
        local_name = re.sub(r'\s+', '_', local_name)
        
        # 3. Reemplazar otros caracteres especiales problemáticos con guiones bajos
        # Mantener solo letras, números, guiones, guiones bajos
        local_name = re.sub(r'[^\w\-]', '_', local_name)
        
        # 4. Limpiar múltiples guiones bajos consecutivos, PERO preservar los dobles de comillas
        # Usar lookahead y lookbehind para no tocar los __ que vienen de comillas
        # Reemplazar 3 o más guiones bajos con 2 (para casos como ___->__)
        local_name = re.sub(r'_{3,}', '__', local_name)
        # Reemplazar single guiones bajos duplicados que no sean parte de quote doubles
        # Buscar ___ y convertir a __
        while '___' in local_name:
            local_name = local_name.replace('___', '__')
        
        # 5. Limpiar guiones bajos al inicio y final
        local_name = local_name.strip('_')
        
        return local_name
    
    def _calculate_campaign_size(self, missions: List[Dict[str, Any]]) -> float:
        """Calcula el tamaño total de una campaña en MB"""
        total_size = sum(mission.get('size', 0) for mission in missions)
        return round(total_size / (1024 * 1024), 2)
    
    def _get_dcs_paths_from_system(self) -> List[str]:
        """Obtiene rutas de DCS usando información del sistema (manifests, registro, etc.)"""
        paths = []
        
        try:
            import json
            import glob as file_glob
            import string
            
            # Detectar automáticamente todas las unidades disponibles
            available_drives = []
            for drive_letter in string.ascii_uppercase:
                drive_path = f"{drive_letter}:\\"
                if os.path.exists(drive_path):
                    available_drives.append(drive_letter)
            
            # 1. Buscar en manifests de Oculus (en todas las unidades)
            for drive_letter in available_drives:
                oculus_manifests_pattern = f"{drive_letter}:\\Program Files\\Oculus\\CoreData\\Manifests\\*DCS*.json"
                oculus_manifests = file_glob.glob(oculus_manifests_pattern)
                for manifest_file in oculus_manifests:
                    try:
                        with open(manifest_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            launch_file = data.get('launchFile', '')
                            if launch_file and 'DCS' in launch_file:
                                # Extraer directorio base de DCS
                                dcs_dir = os.path.dirname(os.path.dirname(launch_file))  # Remover bin-mt/DCS.exe
                                campaigns_path = os.path.join(dcs_dir, "Mods", "campaigns")
                                if os.path.exists(campaigns_path) and self._has_campaigns(campaigns_path):
                                    paths.append(campaigns_path)
                                    self.logger.info(f"DCS encontrado via Oculus manifest: {campaigns_path}")
                    except Exception as e:
                        self.logger.debug(f"Error leyendo manifest {manifest_file}: {e}")
            
            # 2. Buscar en Steam (en todas las unidades)
            steam_locations = [
                "Program Files (x86)\\Steam\\steamapps\\common\\DCSWorld",
                "Program Files\\Steam\\steamapps\\common\\DCSWorld"
            ]
            for drive_letter in available_drives:
                for location in steam_locations:
                    steam_path = f"{drive_letter}:\\{location}"
                    if os.path.exists(steam_path):
                        campaigns_path = os.path.join(steam_path, "Mods", "campaigns")
                        if os.path.exists(campaigns_path) and self._has_campaigns(campaigns_path):
                            paths.append(campaigns_path)
                            self.logger.info(f"DCS encontrado via Steam: {campaigns_path}")
            
            # 3. Buscar en el registro de Windows (si es posible)
            try:
                import winreg
                # Buscar en uninstall entries
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                  "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall") as key:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if "DCS" in name and "World" in name:
                                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                        campaigns_path = os.path.join(install_location, "Mods", "campaigns")
                                        if os.path.exists(campaigns_path) and self._has_campaigns(campaigns_path):
                                            paths.append(campaigns_path)
                                            self.logger.info(f"DCS encontrado via registro: {campaigns_path}")
                                except FileNotFoundError:
                                    pass
                            i += 1
                        except OSError:
                            break
            except ImportError:
                self.logger.debug("winreg no disponible, omitiendo búsqueda en registro")
            except Exception as e:
                self.logger.debug(f"Error buscando en registro: {e}")
            
        except Exception as e:
            self.logger.debug(f"Error en búsqueda inteligente del sistema: {e}")
        
        return list(set(paths))  # Remover duplicados
    
    def _has_campaigns(self, path: str) -> bool:
        """Verifica si un directorio contiene campañas (excluyendo carpetas de prueba)"""
        try:
            # Filtrar carpetas de prueba
            if any(test_folder in path.lower() for test_folder in ['test_dcs', 'users\\public', 'temp']):
                self.logger.debug(f"Omitiendo carpeta de prueba: {path}")
                return False
            
            return any(
                os.path.isdir(os.path.join(path, item)) and 
                glob.glob(os.path.join(path, item, "*.miz"))
                for item in os.listdir(path)
            )
        except Exception:
            return False
    
    def _is_translation_folder(self, folder_name: str, folder_path: str) -> bool:
        """Determina si una carpeta es de traducción y debe ser excluida"""
        # Nombres comunes de carpetas de traducción
        translation_indicators = [
            'translated_es', 'translated', 'translation', 'traducciones',
            'finalizado', 'finalized', 'output', 'out_lua', 'backup',
            'doc', 'l10n', '_deploy'
        ]
        
        folder_lower = folder_name.lower()
        
        # Verificar por nombre exacto o que contenga indicadores
        for indicator in translation_indicators:
            if folder_lower == indicator or indicator in folder_lower:
                return True
        
        return False
    
    def _deep_scan_for_dcs(self) -> List[str]:
        """Búsqueda profunda de directorios DCS en todas las unidades disponibles"""
        roots = []
        
        try:
            import string
            # Detectar automáticamente todas las unidades disponibles
            available_drives = []
            for drive_letter in string.ascii_uppercase:
                drive_path = f"{drive_letter}:\\"
                if os.path.exists(drive_path):
                    available_drives.append(f"{drive_letter}:")
            
            self.logger.info(f"Unidades detectadas: {available_drives}")
            
            for drive in available_drives:
                self.logger.info(f"Escaneando unidad {drive} para DCS...")
                
                # Directorios comunes donde se instala DCS
                common_locations = [
                    'Program Files\\Eagle Dynamics',
                    'Program Files (x86)\\Eagle Dynamics', 
                    'Program Files\\Steam\\steamapps\\common',
                    'Program Files (x86)\\Steam\\steamapps\\common',
                    'Steam\\steamapps\\common',
                    'Games\\DCS World',
                    'DCS World',
                    'Games\\Eagle Dynamics',
                    'Epic Games\\DCSWorld'  # Epic Games Store
                ]
                
                for location in common_locations:
                    scan_path = os.path.join(drive + '\\', location)
                    
                    try:
                        if not os.path.exists(scan_path):
                            continue
                        
                        # Si la ubicación ya contiene "DCS World" en el path, buscar directamente
                        if 'dcs' in location.lower():
                            campaigns_path = os.path.join(scan_path, 'Mods', 'campaigns')
                            if os.path.exists(campaigns_path) and self._has_campaigns(campaigns_path):
                                roots.append(campaigns_path)
                                self.logger.info(f"✅ Encontrado DCS en: {campaigns_path}")
                        else:
                            # Buscar subdirectorios que contengan DCS
                            try:
                                for item in os.listdir(scan_path):
                                    item_path = os.path.join(scan_path, item)
                                    if os.path.isdir(item_path) and 'dcs' in item.lower():
                                        # Buscar carpeta de campañas
                                        campaigns_path = os.path.join(item_path, 'Mods', 'campaigns')
                                        if os.path.exists(campaigns_path) and self._has_campaigns(campaigns_path):
                                            roots.append(campaigns_path)
                                            self.logger.info(f"✅ Encontrado DCS en: {campaigns_path}")
                            except (OSError, PermissionError) as e:
                                # Silenciosamente omitir directorios sin acceso
                                continue
                                
                    except (OSError, PermissionError) as e:
                        # Log de errores de permisos pero continuar
                        self.logger.debug(f"Sin acceso a {scan_path}: {e}")
                        continue
                                    
            # Eliminar duplicados y ordenar
            roots = sorted(list(set(roots)))
            self.logger.info(f"Búsqueda profunda completada. Encontrados {len(roots)} directorios de campañas.")
            return roots
            
        except Exception as e:
            self.logger.error(f"Error en búsqueda profunda: {e}")
            return []
    
    def _load_user_config(self) -> Dict[str, Any]:
        """Carga la configuración del usuario con fallbacks seguros"""
        try:
            from app.services.user_config import UserConfigService
            user_service = UserConfigService()
            user_config = user_service.load_config()
            self.logger.debug(f"Configuración de usuario cargada: {list(user_config.keys())}")
            return user_config
        except Exception as e:
            self.logger.warning(f"Error cargando configuración de usuario, usando fallbacks: {e}")
            return {}

    def _get_file_target_from_config(self, payload_file_target: str = None) -> str:
        """
        Obtiene FILE_TARGET desde configuración del usuario con fallbacks robustos
        
        Prioridad:
        1. Valor del payload (si se proporciona)
        2. Configuración del usuario
        3. Fallback por defecto: 'l10n/DEFAULT/dictionary'
        """
        # 1. Si viene en el payload, usarlo directamente
        if payload_file_target:
            self.logger.debug(f"Usando FILE_TARGET del payload: {payload_file_target}")
            return payload_file_target
        
        # 2. Intentar cargar desde configuración del usuario
        try:
            user_config = self._load_user_config()
            file_target = user_config.get('FILE_TARGET', '').strip()
            
            if file_target:
                self.logger.debug(f"Usando FILE_TARGET de configuración de usuario: {file_target}")
                return file_target
            else:
                self.logger.debug("FILE_TARGET no configurado en usuario, usando fallback")
                
        except Exception as e:
            self.logger.warning(f"Error accediendo a configuración de usuario: {e}")
        
        # 3. Fallback por defecto
        fallback = 'l10n/DEFAULT/dictionary'
        self.logger.debug(f"Usando FILE_TARGET por defecto: {fallback}")
        return fallback

    def _extract_miz(self, miz_path: str, dest_dir: str):
        """Extrae un archivo MIZ"""
        with zipfile.ZipFile(miz_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
    
    def _parse_lm_config(self, args_data) -> Dict[str, Any]:
        """Parsea configuración de LM desde argumentos (dict o string)"""
        
        logging.info(f"🔧 _parse_lm_config recibió args_data: {args_data} (tipo: {type(args_data)})")
        
        # Si es un diccionario, usar directamente
        if isinstance(args_data, dict):
            logging.info(f"Usando configuración LM desde diccionario: {args_data}")
            # Obtener URL desde configuración del usuario como fallback
            from app.services.user_config import UserConfigService
            default_url = UserConfigService.get_lm_studio_url()
            
            return {
                'url': args_data.get('url', default_url),
                'model': args_data.get('model', ''),
                'compat': args_data.get('compat', 'auto'),
                'config': args_data.get('config', ''),
                'batch': args_data.get('batch', 4),
                'timeout': args_data.get('timeout', 200)
            }
        
        # Si es un string, parsear (implementación futura)
        if isinstance(args_data, str) and args_data:
            logging.info(f"Parseando configuración LM desde string: {args_data}")
            # TODO: Implementar parser de argumentos de línea de comandos
            from app.services.user_config import UserConfigService
            default_url = UserConfigService.get_lm_studio_url()
            
            return {
                'url': default_url,
                'model': '',
                'compat': 'auto'
            }
        
        # Fallback por defecto
        logging.warning("No se recibieron argumentos LM, usando valores por defecto")
        from app.services.user_config import UserConfigService
        default_url = UserConfigService.get_lm_studio_url()
        
        return {
            'url': default_url,
            'model': '',
            'compat': 'auto'
        }
    
    def _extract_prompt_file(self, args_data) -> Optional[str]:
        """Extrae el archivo de prompt desde argumentos (dict o string)"""
        
        logging.info(f"🔧 _extract_prompt_file recibió args_data: {args_data} (tipo: {type(args_data)})")
        
        # Si es un diccionario, buscar el campo 'config'
        if isinstance(args_data, dict):
            config_file = args_data.get('config', '')
            if config_file:
                logging.info(f"Archivo de configuración especificado: {config_file}")
                return config_file
        
        # Si es un string, intentar parsear (implementación futura)
        if isinstance(args_data, str) and args_data:
            # TODO: Parsear string de argumentos para extraer --config
            pass
        
        # Fallback: usar archivo por defecto
        default_config = '2-completions-PROMT.yaml'
        logging.info(f"Usando archivo de configuración por defecto: {default_config}")
        return default_config
    
    def _kill_process(self, process: subprocess.Popen):
        """Mata un proceso de forma segura"""
        try:
            if os.name == 'nt':  # Windows
                process.terminate()
            else:  # Unix/Linux
                process.send_signal(signal.SIGTERM)
            
            # Esperar un poco y forzar si es necesario
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                
        except Exception as e:
            self.logger.error(f"Error matando proceso: {e}")
    
    def _kill_process_aggressively(self, process: subprocess.Popen):
        """Mata un proceso de forma MUY agresiva para cancelaciones forzadas"""
        try:
            # Obtener PID del proceso
            pid = process.pid
            self.logger.info(f"🔪 Terminando proceso PID {pid} agresivamente...")
            
            if os.name == 'nt':  # Windows
                try:
                    # Intentar terminar con taskkill primero (más agresivo)
                    os.system(f'taskkill /F /PID {pid} /T')  # /T mata el árbol de procesos
                    self.logger.info(f"✅ Proceso {pid} terminado con taskkill")
                except Exception as tk_error:
                    self.logger.warning(f"⚠️ taskkill falló: {tk_error}")
                    
                    # Fallback a método normal
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        
            else:  # Unix/Linux
                try:
                    # Intentar usar psutil si está disponible
                    import psutil
                    proc = psutil.Process(pid)
                    proc.terminate()
                    
                    # Esperar un poco
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()  # SIGKILL
                        
                except ImportError:
                    self.logger.warning("⚠️ psutil no disponible, usando método estándar")
                    # Fallback a método normal
                    process.send_signal(signal.SIGTERM)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        
                except Exception as ps_error:
                    self.logger.warning(f"⚠️ psutil falló: {ps_error}")
                    
                    # Fallback a método normal
                    process.send_signal(signal.SIGTERM)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        
        except Exception as e:
            self.logger.error(f"❌ Error en terminación agresiva de proceso: {e}")
            
            # Último recurso - intentar kill normal
            try:
                process.kill()
            except Exception as kill_error:
                self.logger.error(f"❌ Error en kill de último recurso: {kill_error}")
    
    def _slugify(self, text: str) -> str:
        """Convierte texto a un slug válido para nombres de archivo (compatible con TranslationEngine)"""
        import re
        # Usar la misma lógica que TranslationEngine.slugify para consistencia
        s = re.sub(r"[^\w\s\-\.áéíóúüñÁÉÍÓÚÜÑ]", "_", text, flags=re.UNICODE)
        s = re.sub(r"\s+", "_", s)
        return s
    
    def _calculate_duration(self, start_time: str, end_time: str) -> str:
        """Calcula duración entre dos timestamps ISO"""
        try:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)
            duration = end - start
            
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
                
        except Exception:
            return "unknown"
    
    def _register_found_campaigns(self, roots: List[str], detection_method: str):
        """
        Registra las campañas encontradas en las rutas especificadas
        usando el servicio de registro de campañas.
        """
        registry = get_campaign_registry()
        total_registered = 0
        
        for root in roots:
            try:
                campaigns = self.scan_campaigns(root)
                if campaigns:
                    new_campaigns = registry.register_campaigns(campaigns, detection_method)
                    total_registered += new_campaigns
                    self.logger.info(f"Registradas {new_campaigns} campañas nuevas desde {root}")
            except Exception as e:
                self.logger.error(f"Error registrando campañas desde {root}: {e}")
        
        if total_registered > 0:
            self.logger.info(f"Total de campañas nuevas registradas: {total_registered}")
    
    def get_registered_campaigns_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen de las campañas registradas y el estado de las unidades.
        """
        registry = get_campaign_registry()
        
        # Detectar cambios recientes en unidades
        drive_changes = registry.detect_drive_changes()
        
        # Obtener resumen completo
        status_summary = registry.get_drive_status_summary()
        
        # Obtener campañas no disponibles
        unavailable_campaigns = registry.get_unavailable_campaigns()
        
        return {
            'drive_changes': drive_changes,
            'status_summary': status_summary,
            'unavailable_campaigns': [
                {
                    'name': c.name,
                    'path': c.path,
                    'drive_letter': c.drive_letter,
                    'missions_count': c.missions_count,
                    'last_seen': c.last_seen
                }
                for c in unavailable_campaigns
            ],
            'warnings': status_summary.get('warnings', [])
        }
    
    def _generate_session_report(self, results: Dict[str, Any]):
        """Genera reporte de sesión en el directorio apropiado"""
        from config.settings import TRANSLATIONS_DIR
        session_id = results.get('session_id', 'unknown')
        
        # Determinar dónde generar el reporte basado en las campañas procesadas
        report_dir = TRANSLATIONS_DIR  # Por defecto
        
        # Si hay resultados de traducción con campañas específicas
        translated_campaigns = results.get('translated_campaigns', [])
        if len(translated_campaigns) == 1:
            # Una sola campaña: generar reporte en el directorio de la campaña
            campaign_result = translated_campaigns[0]
            campaign_name = campaign_result.get('name', '')
            
            if campaign_name:
                # Buscar el primer directorio de misión exitoso en esta campaña
                missions = campaign_result.get('missions', [])
                for mission in missions:
                    if mission.get('success', False):
                        campaign_dir = os.path.join(TRANSLATIONS_DIR, self._slugify(campaign_name))
                        mission_name = mission.get('name', '').replace('.miz', '')
                        mission_dir = os.path.join(campaign_dir, self._slugify(mission_name))
                        
                        if os.path.exists(mission_dir):
                            report_dir = mission_dir
                            self.logger.info(f"Generando reporte en directorio de misión: {mission_dir}")
                            break
                
                # Si no hay misión específica, usar directorio de campaña
                if report_dir == TRANSLATIONS_DIR and os.path.exists(os.path.join(TRANSLATIONS_DIR, self._slugify(campaign_name))):
                    report_dir = os.path.join(TRANSLATIONS_DIR, self._slugify(campaign_name))
                    self.logger.info(f"Generando reporte en directorio de campaña: {report_dir}")
        
        report_file = os.path.join(report_dir, f"session_report_{session_id}.json")
        
        try:
            import json
            ensure_directory(report_dir)
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Reporte de sesión generado: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Error generando reporte: {e}")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Retorna el estado actual de la orquestación"""
        return self.status.copy()
    
    def is_running(self) -> bool:
        """Indica si hay una traducción en ejecución"""
        return self.status.get('is_running', False)
    
    def run_translation(self, data: Dict[str, Any]) -> None:
        """Ejecuta una traducción usando el formato del orquestador anterior"""
        self.run_orchestrator(data)