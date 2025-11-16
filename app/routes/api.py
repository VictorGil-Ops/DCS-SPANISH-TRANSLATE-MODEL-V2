#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import logging
import os
import json
import glob
import requests
from datetime import datetime

# Import psutil with fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# Import yaml with fallback
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

from config.settings import PROMPTS_DIR, PRESETS_DIR, LM_CONFIG
from app.utils.mission_state_detector import get_mission_state_detector, MissionState
from app.services.orchestrator import DCSOrchestrator
from app.services.presets import PresetService
from app.services.lm_studio import LMStudioService

api_bp = Blueprint('api', __name__)

# Instancia global del orchestrator para mantener el estado
_orchestrator_instance = None

def get_orchestrator():
    """Obtiene la instancia del orchestrator (singleton pattern)"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = DCSOrchestrator()
    return _orchestrator_instance

# Ruta para manejar el bug de URL mal formada
@api_bp.route('/orchestratorapi/status', methods=['GET'])
def orchestrator_api_status_redirect():
    """Redirección para URLs mal formadas de /orchestratorapi/status"""
    logging.warning("URL mal formada detectada: /orchestratorapi/status -> /api/status")
    return jsonify({
        'ok': True,
        'status': 'running',
        'message': 'Orquestador funcionando correctamente (redirected)',
        'processes': {
            'translation': False,
            'lm_studio': False
        },
        'redirect_note': 'Esta URL era incorrecta pero fue manejada'
    })

@api_bp.route('/test')
def test():
    return jsonify({'ok': True, 'message': 'API working'})

@api_bp.route('/promts', methods=['GET'])
def get_promts():
    """Obtiene archivos YAML de prompts disponibles"""
    try:
        # Usar PROMPTS_DIR (directorio app/data/promts)
        promts_dir = PROMPTS_DIR
        
        if not os.path.exists(promts_dir):
            return jsonify({'ok': True, 'files': []})
        
        yaml_files = []
        for ext in ['*.yaml', '*.yml']:
            yaml_files.extend(glob.glob(os.path.join(promts_dir, ext)))
        
        # Obtener solo los nombres de archivo
        files = [os.path.basename(f) for f in yaml_files]
        files.sort()
        
        return jsonify({'ok': True, 'files': files})
        
    except Exception as e:
        logging.error(f"Error getting promts: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@api_bp.route('/user_config', methods=['GET', 'POST'])
def handle_user_config():
    """Obtiene o guarda la configuración del usuario"""
    if request.method == 'GET':
        return get_user_config()
    else:  # POST
        return save_user_config()

def get_user_config():
    """Obtiene la configuración actual del usuario"""
    try:
        # Cargar configuración del usuario desde archivo si existe
        from config.settings import DATA_DIR
        user_config_path = os.path.join(DATA_DIR, 'my_config', 'user_config.json')
        
        logging.info(f"Buscando configuración en: {user_config_path}")
        
        user_config = {}
        if os.path.exists(user_config_path):
            logging.info("Archivo de configuración encontrado, cargando...")
            with open(user_config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            logging.info(f"Configuración cargada: {list(user_config.keys())}")
        else:
            logging.info("No existe archivo de configuración de usuario")
        
        # Si existe configuración de usuario, usarla directamente
        # Si no existe, usar configuración mínima por defecto (campos vacíos)
        if user_config:
            # Usar la configuración guardada tal como está
            config = user_config.copy()
            
            # Solo agregar campos que pueden no existir por compatibilidad
            config.setdefault('FILE_TARGET', 'l10n/DEFAULT/dictionary')
            # Obtener URL desde configuración del usuario con fallback inteligente
            from app.services.user_config import UserConfigService
            config.setdefault('lm_url', UserConfigService.get_lm_studio_url())
            config.setdefault('DEPLOY_OVERWRITE', True)
            # Agregar configuración de cache si no existe
            config.setdefault('use_cache', True)
            config.setdefault('overwrite_cache', False)
        else:
            # Configuración mínima por defecto (campos vacíos para el modelo)
            config = {
                # Configuración General - valores por defecto mínimos
                'ROOT_DIR': '',
                'DEPLOY_DIR': '',
                'FILE_TARGET': 'l10n/DEFAULT/dictionary',
                'lm_url': LM_CONFIG['DEFAULT_URL'],
                'DEPLOY_OVERWRITE': True,
                
                # Configuración del Modelo - campos vacíos
                'lm_model': '',
                'arg_config': '',
                'arg_compat': '',
                'arg_batch': '',
                'arg_timeout': '',
                
                # Configuración de Cache - valores por defecto
                'use_cache': True,
                'overwrite_cache': False
            }
        
        # Verificar que las rutas existen
        root_dir = config.get('ROOT_DIR', '').strip()
        deploy_dir = config.get('DEPLOY_DIR', '').strip()
        
        # Si está vacío, devolver null para que JS oculte el estado
        # Si no está vacío, verificar si existe
        campaign_path_validation = None if not root_dir else bool(os.path.exists(root_dir))
        deploy_path_validation = None if not deploy_dir else bool(os.path.exists(deploy_dir))
        
        response_data = {
            'success': True,  # Cambiar de 'ok' a 'success'
            'config': config,
            'has_user_config': bool(user_config),
            'config_path': user_config_path,
            'validation': {
                'ROOT_DIR': campaign_path_validation,  # JavaScript espera este nombre
                'DEPLOY_DIR': deploy_path_validation,  # JavaScript espera este nombre
                'campaign_path_valid': campaign_path_validation,  # Mantener compatibilidad
                'deploy_path_valid': deploy_path_validation,  # Mantener compatibilidad
                'paths_valid': bool(campaign_path_validation or deploy_path_validation),
                'lm_studio_available': False  # Mock
            },
            'debug': {
                'data_dir': DATA_DIR,
                'path_exists': os.path.exists(user_config_path),
                'user_config_keys': list(user_config.keys()),
                'final_config_keys': list(config.keys())
            }
        }
        
        logging.info(f"Devolviendo respuesta con {len(config)} elementos de configuración")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Error getting user config: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def save_user_config():
    """Guarda la configuración del usuario"""
    try:
        data = request.get_json() or {}
        logging.info(f"Guardando configuración de usuario: {list(data.keys())}")
        
        # Cargar configuración existente
        from config.settings import DATA_DIR
        user_config_path = os.path.join(DATA_DIR, 'my_config', 'user_config.json')
        
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
        
        # Guardar la configuración
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Configuración guardada en: {user_config_path}")
        
        # Validar rutas si están presentes
        validation = {
            'paths_valid': False,
            'lm_studio_available': False,
            'ROOT_DIR': None,
            'DEPLOY_DIR': None,
            'campaign_path_valid': False,
            'deploy_path_valid': False
        }
        
        # Verificar rutas si están definidas (manejar diferentes formatos de campo)
        root_dir = (data.get('ROOT_DIR') or data.get('rootDir') or data.get('campaign_path') or '').strip()
        if root_dir:
            root_exists = os.path.exists(root_dir)
            validation['ROOT_DIR'] = root_exists
            validation['campaign_path_valid'] = root_exists
        else:
            validation['ROOT_DIR'] = None  # Para que JS oculte el estado
            validation['campaign_path_valid'] = False
            
        deploy_dir = (data.get('DEPLOY_DIR') or data.get('deployDir') or data.get('deploy_path') or '').strip()
        if deploy_dir:
            deploy_exists = os.path.exists(deploy_dir)
            validation['DEPLOY_DIR'] = deploy_exists
            validation['deploy_path_valid'] = deploy_exists
        else:
            validation['DEPLOY_DIR'] = None  # Para que JS oculte el estado
            validation['deploy_path_valid'] = False
            
        validation['paths_valid'] = validation['campaign_path_valid'] or validation['deploy_path_valid']
        
        return jsonify({
            'success': True,
            'message': 'Configuración guardada correctamente',
            'validation': validation,
            'config_path': user_config_path
        })
        
    except Exception as e:
        logging.error(f"Error saving user config: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/user_config/general', methods=['POST'])
def save_general_config():
    """Guarda la configuración general del usuario"""
    try:
        data = request.get_json() or {}
        logging.info(f"Guardando configuración general: {list(data.keys())}")
        logging.info(f"Datos recibidos completos: {data}")
        
        # Cargar configuración existente
        from config.settings import DATA_DIR
        user_config_path = os.path.join(DATA_DIR, 'my_config', 'user_config.json')
        
        # Cargar configuración existente o crear nueva
        existing_config = {}
        if os.path.exists(user_config_path):
            with open(user_config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
        
        # Actualizar solo los campos de configuración general
        existing_config.update({
            'ROOT_DIR': data.get('ROOT_DIR', ''),
            'FILE_TARGET': data.get('FILE_TARGET', 'l10n/DEFAULT/dictionary'),
            'lm_url': data.get('lm_url', LM_CONFIG['DEFAULT_URL']),
            'DEPLOY_DIR': data.get('DEPLOY_DIR', ''),
            'DEPLOY_OVERWRITE': data.get('DEPLOY_OVERWRITE', True)
        })
        
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
        
        # Guardar configuración actualizada
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Configuración general guardada en: {user_config_path}")
        
        return jsonify({
            'success': True,
            'message': 'Configuración general guardada correctamente'
        })
        
    except Exception as e:
        logging.error(f"Error saving general config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/user_config/model', methods=['POST'])
def save_model_config():
    """Guarda la configuración del modelo"""
    try:
        data = request.get_json() or {}
        logging.info(f"Guardando configuración de modelo: {list(data.keys())}")
        
        # Cargar configuración existente
        from config.settings import DATA_DIR
        user_config_path = os.path.join(DATA_DIR, 'my_config', 'user_config.json')
        
        # Cargar configuración existente o crear nueva
        existing_config = {}
        if os.path.exists(user_config_path):
            with open(user_config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
        
        # Actualizar solo los campos de configuración del modelo
        existing_config.update({
            'lm_model': data.get('lm_model', ''),
            'active_preset': data.get('active_preset', ''),  # Agregar preset activo
            'preset': data.get('preset', ''),  # Para perfiles
            'arg_config': data.get('arg_config', ''),
            'arg_compat': data.get('arg_compat', 'auto'),
            'arg_batch': str(data.get('arg_batch', 4)),  # Convertir a string
            'arg_timeout': str(data.get('arg_timeout', 200)),  # Convertir a string
            # Parámetros del API del modelo (¡AHORA SE GUARDAN!)
            'api_temperature': data.get('api_temperature', 0.7),
            'api_top_p': data.get('api_top_p', 0.9),
            'api_top_k': data.get('api_top_k', 40),
            'api_max_tokens': data.get('api_max_tokens', 8000),
            'api_repetition_penalty': data.get('api_repetition_penalty', 1.0),
            'api_presence_penalty': data.get('api_presence_penalty', 0.0),
            'use_cache': data.get('use_cache', True),  # Agregar configuración de caché
            'overwrite_cache': data.get('overwrite_cache', False)  # Agregar configuración de caché
        })
        
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
        
        # Guardar configuración actualizada
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Configuración de modelo guardada en: {user_config_path}")
        
        return jsonify({
            'success': True,
            'message': 'Configuración de modelo guardada correctamente'
        })
        
    except Exception as e:
        logging.error(f"Error saving model config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/user_config/general/reset', methods=['POST'])
def reset_general_config():
    """Resetea la configuración general"""
    try:
        return jsonify({
            'success': True,
            'message': 'Configuración general reseteada (mock)'
        })
    except Exception as e:
        logging.error(f"Error resetting general config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/user_config/model/reset', methods=['POST'])  
def reset_model_config():
    """Resetea la configuración del modelo"""
    try:
        return jsonify({
            'success': True,
            'message': 'Configuración de modelo reseteada (mock)'
        })
    except Exception as e:
        logging.error(f"Error resetting model config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/lm_studio_url', methods=['GET'])
def get_lm_studio_url():
    """Obtiene la URL de LM Studio configurada por el usuario"""
    try:
        from app.services.user_config import UserConfigService
        url = UserConfigService.get_lm_studio_url()
        
        return jsonify({
            'success': True,
            'lm_url': url
        })
    except Exception as e:
        logging.error(f"Error getting LM Studio URL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/file_target', methods=['GET'])
def get_file_target():
    """Obtiene el FILE_TARGET configurado por el usuario"""
    try:
        from app.services.user_config import UserConfigService
        file_target = UserConfigService.get_file_target()
        
        return jsonify({
            'success': True,
            'file_target': file_target
        })
    except Exception as e:
        logging.error(f"Error getting FILE_TARGET: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/repo_url', methods=['GET'])
def get_repo_url():
    """Obtiene la URL del repositorio detectada automáticamente"""
    try:
        from app.services.user_config import UserConfigService
        repo_url = UserConfigService.get_repo_url()
        
        return jsonify({
            'success': True,
            'repo_url': repo_url,
            'message': 'URL detectada automáticamente desde configuración Git'
        })
    except Exception as e:
        logging.error(f"Error getting repo URL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/version', methods=['GET'])
def get_version():
    """Obtiene la versión del software desde el archivo VERSION"""
    try:
        from app.services.user_config import UserConfigService
        version = UserConfigService.get_version()
        
        return jsonify({
            'success': True,
            'version': version,
            'message': 'Versión leída desde archivo VERSION'
        })
    except Exception as e:
        logging.error(f"Error getting version: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/system_info', methods=['GET'])
def get_system_info():
    """Obtiene toda la información dinámica del sistema"""
    try:
        from app.services.user_config import UserConfigService
        
        # Obtener toda la información dinámica
        version = UserConfigService.get_version()
        repo_url = UserConfigService.get_repo_url()
        lm_url = UserConfigService.get_lm_studio_url()
        file_target = UserConfigService.get_file_target()
        
        # Detectar el entorno basado en la URL del repo
        environment = 'unknown'
        if 'DEV-DCS-SPANISH-TRANSLATE-MODEL-V2-Private' in repo_url:
            environment = 'development'
        elif 'PRE-DCS-SPANISH-TRANSLATE-MODEL-V2-Private' in repo_url:
            environment = 'preproduction'
        elif 'PRO-DCS-SPANISH-TRANSLATE-MODEL-V2-Private' in repo_url:
            environment = 'production'
        elif 'DCS-Spanish-Translate-Model-V2' in repo_url:
            environment = 'public'
        
        return jsonify({
            'success': True,
            'system_info': {
                'version': version,
                'repo_url': repo_url,
                'environment': environment,
                'lm_studio_url': lm_url,
                'file_target': file_target
            },
            'detection_methods': {
                'version': 'Archivo VERSION en raíz del proyecto',
                'repo_url': 'Git remote origin URL con fallback por nombre de directorio',
                'lm_studio_url': 'Configuración de usuario con fallback',
                'file_target': 'Configuración de usuario con fallback'
            },
            'message': 'Información del sistema detectada automáticamente'
        })
        
    except Exception as e:
        logging.error(f"Error getting system info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/update_info', methods=['GET'])
def update_info():
    """Verifica si hay una versión más reciente comparando versión local vs remota del repositorio"""
    try:
        from app.services.user_config import UserConfigService
        import requests
        
        # Obtener versión actual del archivo local
        current_version = UserConfigService.get_version()
        
        # Obtener URL del repositorio
        repo_url = UserConfigService.get_repo_url()
        
        try:
            # Convertir URL de GitHub a URL de API para obtener el archivo VERSION
            if 'github.com' in repo_url:
                # Extraer owner/repo de la URL
                parts = repo_url.replace('https://github.com/', '').split('/')
                if len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1]
                    
                    # URL de la API de GitHub para obtener el contenido del archivo VERSION
                    # Intentar diferentes ramas: rama actual, main, master
                    possible_branches = []
                    
                    # Detectar rama actual
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['git', 'branch', '--show-current'],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            cwd=os.path.dirname(__file__)
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            current_branch = result.stdout.strip()
                            possible_branches.append(current_branch)
                    except:
                        pass
                    
                    # Añadir ramas comunes
                    possible_branches.extend(['main', 'master', 'develop'])
                    
                    # Remover duplicados manteniendo orden
                    branches_to_try = []
                    for branch in possible_branches:
                        if branch not in branches_to_try:
                            branches_to_try.append(branch)
                    
                    remote_version = None
                    successful_branch = None
                    
                    for branch in branches_to_try:
                        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/run/VERSION?ref={branch}"
                        
                        # Headers para la API de GitHub
                        headers = {
                            'Accept': 'application/vnd.github.v3+json',
                            'User-Agent': 'DCS-Spanish-Translate-App'
                        }
                        
                        try:
                            # Realizar petición a la API de GitHub
                            response = requests.get(api_url, headers=headers, timeout=10)
                            
                            if response.status_code == 200:
                                import base64
                                content_data = response.json()
                                
                                # Decodificar el contenido base64
                                remote_version = base64.b64decode(content_data['content']).decode('utf-8').strip()
                                successful_branch = branch
                                break
                            elif response.status_code == 404:
                                # Archivo no encontrado en esta rama, probar siguiente
                                continue
                            elif response.status_code == 403:
                                # Repositorio privado o sin acceso
                                logging.warning(f"Repositorio privado o sin acceso: {repo}")
                                break
                        except requests.RequestException:
                            # Error de conexión, probar siguiente rama
                            continue
                    
                    if remote_version and successful_branch:
                        # Comparar versiones
                        def compare_versions(local, remote):
                            """Compara versiones. Retorna True si remota es mayor que local"""
                            try:
                                # Limpiar versiones (quitar 'v' y espacios)
                                local_clean = local.replace('v', '').strip()
                                remote_clean = remote.replace('v', '').strip()
                                
                                # Dividir en partes principales y menores
                                local_parts = local_clean.split('.')
                                remote_parts = remote_clean.split('.')
                                
                                # Comparar parte por parte
                                max_len = max(len(local_parts), len(remote_parts))
                                for i in range(max_len):
                                    local_part = int(local_parts[i]) if i < len(local_parts) else 0
                                    remote_part = int(remote_parts[i]) if i < len(remote_parts) else 0
                                    
                                    if remote_part > local_part:
                                        return True
                                    elif remote_part < local_part:
                                        return False
                                
                                return False  # Son iguales
                            except Exception:
                                # Fallback: comparación simple como float
                                try:
                                    local_num = float(local.replace('v', ''))
                                    remote_num = float(remote.replace('v', ''))
                                    return remote_num > local_num
                                except:
                                    # Último fallback: comparación de strings
                                    return remote > local
                        
                        is_newer = compare_versions(current_version, remote_version)
                        
                        return jsonify({
                            'ok': True,
                            'current_version': current_version,
                            'remote_version': remote_version,
                            'latest_version': remote_version,
                            'is_newer': is_newer,
                            'repository_url': repo_url,
                            'update_available': is_newer,
                            'branch_checked': successful_branch,
                            'message': f'Local: {current_version} | Remota: {remote_version} (rama: {successful_branch})' + 
                                     (' | ¡Actualización disponible!' if is_newer else ' | Estás al día'),
                            'by': {
                                'github_api': True,
                                'branch': successful_branch
                            }
                        })
                    else:
                        # No se pudo obtener la versión remota en ninguna rama
                        logging.warning(f"No se pudo obtener versión remota del repositorio {repo}")
                        return jsonify({
                            'ok': True,
                            'current_version': current_version,
                            'remote_version': 'unknown',
                            'latest_version': current_version,
                            'is_newer': False,
                            'repository_url': repo_url,
                            'update_available': False,
                            'branches_tried': branches_to_try,
                            'message': f'No se pudo obtener versión remota (ramas probadas: {", ".join(branches_to_try)})',
                            'error': 'Archivo VERSION no encontrado en repositorio remoto',
                            'by': {
                                'github_api': False,
                                'branches_tried': branches_to_try
                            }
                        })
            
        except requests.RequestException as e:
            logging.warning(f"Error conectando con GitHub: {e}")
        except Exception as e:
            logging.error(f"Error procesando respuesta de GitHub: {e}")
        
        # Fallback: verificar estado local del repositorio git
        try:
            import subprocess
            import os
            
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # Verificar si hay commits no pusheados
            result = subprocess.run(
                ['git', 'status', '--porcelain', '--branch'],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            local_changes_info = {
                'has_unpushed_commits': False,
                'has_local_changes': False,
                'status_info': ''
            }
            
            if result.returncode == 0:
                status_output = result.stdout
                local_changes_info['status_info'] = status_output
                
                # Verificar si hay cambios locales
                lines = status_output.strip().split('\n')
                for line in lines:
                    if line.startswith('##'):
                        # Línea de información de branch
                        if '[ahead' in line:
                            local_changes_info['has_unpushed_commits'] = True
                    elif line.strip() and not line.startswith('##'):
                        # Hay cambios locales
                        local_changes_info['has_local_changes'] = True
            
            # Intentar obtener último commit local y comparar con remoto
            local_commit = None
            try:
                result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    local_commit = result.stdout.strip()[:8]  # Primeros 8 caracteres
            except:
                pass
            
            return jsonify({
                'ok': True,
                'current_version': current_version,
                'remote_version': 'unknown',
                'latest_version': current_version,
                'is_newer': False,
                'repository_url': repo_url,
                'update_available': False,
                'local_git_info': local_changes_info,
                'local_commit': local_commit,
                'message': 'No se pudo verificar versión remota - Verificando estado local del repositorio',
                'note': 'Repositorio privado o sin acceso. Mostrando información local disponible.',
                'by': {
                    'github_api': False,
                    'local_git_info': True
                }
            })
            
        except Exception as git_error:
            logging.warning(f"Error obteniendo información local de git: {git_error}")
        
        # Fallback final: no se pudo verificar nada
        return jsonify({
            'ok': True,
            'current_version': current_version,
            'remote_version': 'unknown',
            'latest_version': current_version,
            'is_newer': False,
            'repository_url': repo_url,
            'update_available': False,
            'message': 'No se pudo verificar versión remota - Sin conexión o repositorio inaccesible',
            'error': 'Conexión fallida con repositorio',
            'by': {
                'github_api': False,
                'connection_error': True
            }
        })
        
    except Exception as e:
        logging.error(f"Error in update_info: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/update_now', methods=['POST'])
def update_now():
    """Actualiza el sistema desde el repositorio Git"""
    try:
        import subprocess
        import os
        import shutil
        from app.services.user_config import UserConfigService
        
        # Obtener información del repositorio
        repo_url = UserConfigService.get_repo_url()
        
        # Obtener el directorio del proyecto
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Verificar que es un repositorio git
        git_dir = os.path.join(project_root, '.git')
        if not os.path.exists(git_dir):
            return jsonify({
                'ok': False,
                'error': 'No es un repositorio Git válido'
            }), 400
        
        # Guardar directorios importantes antes de actualizar
        protected_dirs = ['campaigns', 'log_orquestador', 'app/data/my_config', 'app/data/cache']
        backup_data = {}
        
        for protected_dir in protected_dirs:
            full_path = os.path.join(project_root, protected_dir)
            if os.path.exists(full_path):
                backup_path = f"{full_path}_backup_update"
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                shutil.copytree(full_path, backup_path)
                backup_data[protected_dir] = backup_path
                logging.info(f"Respaldo creado: {protected_dir} -> {backup_path}")
        
        try:
            # Ejecutar git pull
            result = subprocess.run(
                ['git', 'pull', 'origin'],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, ['git', 'pull'], result.stderr)
            
            # Restaurar directorios protegidos
            for protected_dir, backup_path in backup_data.items():
                full_path = os.path.join(project_root, protected_dir)
                if os.path.exists(full_path):
                    shutil.rmtree(full_path)
                shutil.move(backup_path, full_path)
                logging.info(f"Directorio restaurado: {protected_dir}")
            
            # Obtener nueva versión
            new_version = UserConfigService.get_version()
            
            return jsonify({
                'ok': True,
                'message': 'Actualización completada exitosamente',
                'new_version': new_version,
                'repo_url': repo_url,
                'git_output': result.stdout,
                'protected_dirs_restored': list(backup_data.keys())
            })
            
        except subprocess.TimeoutExpired:
            # Restaurar backups en caso de error
            for protected_dir, backup_path in backup_data.items():
                if os.path.exists(backup_path):
                    full_path = os.path.join(project_root, protected_dir)
                    if os.path.exists(full_path):
                        shutil.rmtree(full_path)
                    shutil.move(backup_path, full_path)
            
            return jsonify({
                'ok': False,
                'error': 'Timeout en la actualización (>60s)'
            }), 500
            
        except subprocess.CalledProcessError as e:
            # Restaurar backups en caso de error
            for protected_dir, backup_path in backup_data.items():
                if os.path.exists(backup_path):
                    full_path = os.path.join(project_root, protected_dir)
                    if os.path.exists(full_path):
                        shutil.rmtree(full_path)
                    shutil.move(backup_path, full_path)
            
            return jsonify({
                'ok': False,
                'error': f'Error en git pull: {e.stderr}'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in update_now: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/update_dismiss', methods=['POST'])
def update_dismiss():
    """Marca la versión actual como vista para no mostrar más la notificación"""
    try:
        from app.services.user_config import UserConfigService
        
        # Obtener versión actual
        current_version = UserConfigService.get_version()
        
        # Ruta al archivo de última versión conocida
        last_version_file = os.path.join(os.path.dirname(__file__), '..', 'data', '.last_version')
        
        # Actualizar el archivo con la versión actual
        try:
            os.makedirs(os.path.dirname(last_version_file), exist_ok=True)
            with open(last_version_file, 'w', encoding='utf-8') as f:
                f.write(current_version)
            
            logging.info(f"Versión {current_version} marcada como vista")
            
            return jsonify({
                'ok': True,
                'message': f'Notificación de actualización dismissada para versión {current_version}',
                'current_version': current_version
            })
            
        except Exception as e:
            logging.error(f"Error actualizando archivo de versión: {e}")
            return jsonify({
                'ok': False,
                'error': f'Error guardando versión: {str(e)}'
            }), 500
        
    except Exception as e:
        logging.error(f"Error in update_dismiss: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/shutdown', methods=['POST'])
def shutdown_server():
    """Apaga el servidor Flask de manera controlada"""
    try:
        logging.info("Recibida petición de apagado del servidor")
        
        # Función para apagar el servidor después de un pequeño delay
        def shutdown():
            import time
            time.sleep(1)  # Dar tiempo a que se envíe la respuesta
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                # Alternativa para cuando werkzeug.server.shutdown no está disponible
                import os
                import signal
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                func()
        
        # Programar el apagado en un hilo separado
        import threading
        threading.Thread(target=shutdown).start()
        
        return jsonify({
            'ok': True,
            'message': 'Servidor apagándose...',
            'status': 'shutdown_initiated'
        })
        
    except Exception as e:
        logging.error(f"Error in shutdown: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/lm_models')
def get_lm_models():
    """Obtiene la lista de modelos disponibles en LM Studio"""
    try:
        import requests
        lm_url = request.args.get('lm_url', LM_CONFIG['DEFAULT_URL'])
        
        # Intentar conectar con LM Studio
        try:
            response = requests.get(f"{lm_url}/models", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = []
                
                # Procesar respuesta de LM Studio
                if 'data' in data and isinstance(data['data'], list):
                    for model in data['data']:
                        if isinstance(model, dict):
                            model_id = model.get('id', model.get('name', 'unknown'))
                            models.append({
                                "id": model_id,
                                "name": model.get('name', model_id)
                            })
                
                return jsonify({
                    "ok": True,
                    "models": models,
                    "server_info": {
                        "url": lm_url,
                        "status": "connected",
                        "message": f"Conectado a LM Studio - {len(models)} modelos disponibles"
                    }
                })
            else:
                raise requests.RequestException(f"HTTP {response.status_code}")
                
        except requests.Timeout as e:
            # Caso específico de timeout - LM Studio responde muy lento
            return jsonify({
                "ok": True,
                "models": [],
                "server_info": {
                    "url": lm_url,
                    "status": "slow_response",
                    "message": "LM Studio responde muy lento",
                    "performance_issue": True,
                    "suggestions": [
                        "El modelo actual puede ser demasiado pesado para tu sistema",
                        "Considera usar un modelo más pequeño (7B en lugar de 13B+)",
                        "Prueba modelos quantizados (Q4, Q5) para mejor velocidad",
                        "Cierra otras aplicaciones para liberar RAM/GPU",
                        "Reinicia LM Studio si el problema persiste"
                    ]
                }
            })
        except requests.RequestException as e:
            # Si no se puede conectar, devolver lista vacía con mensaje informativo
            return jsonify({
                "ok": True,
                "models": [],
                "server_info": {
                    "url": lm_url,
                    "status": "disconnected",
                    "message": f"No se puede conectar a LM Studio en {lm_url} - {str(e)}"
                }
            })
        
    except Exception as e:
        logging.error(f"Error getting LM models: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@api_bp.route('/lm_loaded_model')
def get_lm_loaded_model():
    """Obtiene el modelo actualmente cargado en LM Studio usando LMStudioService"""
    try:
        lm_url = request.args.get('lm_url', LM_CONFIG['DEFAULT_URL'])
        
        # Usar LMStudioService directamente
        lm_service = LMStudioService(base_url=lm_url)
        loaded_models = lm_service.get_loaded_models()
        
        if loaded_models:
            # Tomar el primer modelo (el actualmente cargado)
            current_model = loaded_models[0]
            model_name = current_model.get('name', current_model.get('id', 'Modelo desconocido'))
            
            return jsonify({
                "ok": True,
                "loaded_model": {
                    "id": current_model.get('id', ''),
                    "name": model_name,
                    "short_name": model_name.split('/')[-1] if model_name else 'Modelo'
                },
                "server_info": {
                    "url": lm_url,
                    "status": "connected",
                    "message": f"Modelo cargado: {model_name}"
                }
            })
        else:
            return jsonify({
                "ok": True,
                "loaded_model": None,
                "server_info": {
                    "url": lm_url,
                    "status": "connected",
                    "message": "No hay modelos cargados en LM Studio"
                }
            })
            
    except Exception as e:
        logging.error(f"Error getting loaded model from LM Studio: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "server_info": {
                "url": request.args.get('lm_url', LM_CONFIG['DEFAULT_URL']),
                "status": "error",
                "message": f"Error conectando con LM Studio: {str(e)}"
            }
        }), 500


@api_bp.route('/lm_diagnostics', methods=['GET'])
def lm_diagnostics():
    """Devuelve diagnóstico y recomendaciones de rendimiento de LM Studio"""
    try:
        lm_url = request.args.get('lm_url', LM_CONFIG['DEFAULT_URL'].replace('/v1', ''))

        # Importar localmente para evitar costes de import al inicio
        from app.services.translation_engine import TranslationEngine

        engine = TranslationEngine()
        diag = engine.get_lm_studio_models_with_performance_info(lm_url)

        return jsonify({
            'ok': True,
            'lm_url': lm_url,
            'diagnostics': diag
        })

    except Exception as e:
        logging.exception("Error running lm_diagnostics")
        return jsonify({'ok': False, 'error': str(e)}), 500

@api_bp.route('/lm_studio/diagnostics', methods=['GET'])
def get_lm_studio_diagnostics():
    """Diagnóstica problemas de rendimiento con LM Studio y sugiere soluciones"""
    try:
        lm_url = request.args.get('lm_url', LM_CONFIG['DEFAULT_URL'])
        lm_model = request.args.get('lm_model', 'test')
        
        from app.services.translation_engine import TranslationEngine
        engine = TranslationEngine()
        
        # Verificar estado de LM Studio
        lm_status = engine.check_lm_studio_status(lm_url, lm_model)
        
        # Obtener información de modelos con datos de rendimiento
        models_info = engine.get_lm_studio_models_with_performance_info(lm_url)
        
        return jsonify({
            'ok': True,
            'lm_studio_status': lm_status,
            'models_info': models_info,
            'recommendations': {
                'immediate_actions': [
                    "🔍 Verifica el uso de CPU/GPU/RAM en Task Manager",
                    "🔄 Reinicia LM Studio si lleva mucho tiempo ejecutándose",
                    "💾 Asegúrate de tener al menos 8GB RAM libres",
                    "🚀 Prueba cambiar a un modelo más pequeño temporalmente"
                ],
                'long_term_solutions': [
                    "📦 Descarga modelos quantizados (Q4/Q5) para mejor rendimiento",
                    "⚡ Considera actualizar RAM si tienes menos de 16GB",
                    "🎯 Usa modelos específicos para traducción (Phi-3, Llama-8B)",
                    "🔧 Configura LM Studio para usar GPU si está disponible"
                ]
            },
            'diagnostic_url': lm_url,
            'timestamp': str(__import__('time').time())
        })
        
    except Exception as e:
        logging.error(f"Error in LM Studio diagnostics: {e}")
        return jsonify({
            'ok': False,
            'error': str(e),
            'fallback_suggestions': [
                "Verifica que LM Studio esté ejecutándose",
                "Reinicia LM Studio y prueba de nuevo",
                "Comprueba la URL de conexión en configuración"
            ]
        }), 500

@api_bp.route('/status', methods=['GET'])
def get_status():
    """Obtiene el estado actual del orquestador incluyendo el resumen de última ejecución"""
    try:
        orchestrator = get_orchestrator()
        current_status = orchestrator.get_current_status()
        # Construir respuesta base
        response = {
            'ok': True,
            'is_running': current_status.get('is_running', False),
            'phase': current_status.get('phase', 'idle'),
            'detail': current_status.get('detail', ''),
            'progress': current_status.get('progress', 0),
            'current_campaign': current_status.get('current_campaign'),
            'current_mission': current_status.get('current_mission'),
            'missions_total': current_status.get('missions_total', 0),
            'missions_processed': current_status.get('missions_processed', 0),
            'missions_successful': current_status.get('missions_successful', 0),
            'missions_failed': current_status.get('missions_failed', 0),
            'errors': current_status.get('errors', []),
            'progress_logs': current_status.get('progress_logs', []),
            'completion_time': current_status.get('completion_time'),
            'last_execution': orchestrator.last_execution,
            'timestamp': str(os.path.getmtime(__file__) if os.path.exists(__file__) else 0),
            # Datos de progreso en tiempo real
            'total_batches': current_status.get('total_batches', 0),
            'processed_batches': current_status.get('processed_batches', 0),
            'batch_progress': current_status.get('batch_progress', 0),
            'cache_hits': current_status.get('cache_hits', 0),
            'model_calls': current_status.get('model_calls', 0)
        }

        # Si se pasa lm_url como parámetro, adjuntar diagnóstico de LM Studio
        lm_url = request.args.get('lm_url')
        if lm_url:
            try:
                from app.services.translation_engine import TranslationEngine
                engine = TranslationEngine()

                lm_status = engine.check_lm_studio_status(lm_url)
                models_info = engine.get_lm_studio_models_with_performance_info(lm_url)

                response['lm_diagnostics'] = {
                    'lm_url': lm_url,
                    'status': lm_status,
                    'models_info': models_info
                }
            except Exception as e:
                logging.exception('Error fetching LM diagnostics in /api/status')
                response['lm_diagnostics'] = {
                    'lm_url': lm_url,
                    'error': str(e)
                }

        return jsonify(response)
        
    except Exception as e:
        logging.error(f"Error getting status: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/cancel', methods=['POST'])
def cancel_orchestrator():
    """Cancela la operación actual del orquestador"""
    try:
        orchestrator = get_orchestrator()
        success = orchestrator.cancel_current_operation()
        
        if success:
            return jsonify({
                'ok': True,
                'message': 'Operación cancelada exitosamente'
            })
        else:
            return jsonify({
                'ok': False,
                'message': 'No hay operación en curso para cancelar'
            })
            
    except Exception as e:
        logging.error(f"Error canceling orchestrator: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/force_kill_lm_studio', methods=['POST'])
def force_kill_lm_studio():
    """Mata el proceso de LM Studio de forma agresiva"""
    try:
        import subprocess
        killed_processes = []
        
        if PSUTIL_AVAILABLE:
            # Método preferido con psutil
            # Buscar y matar procesos de LM Studio
            lm_studio_process_names = [
                'LM Studio.exe',
                'lm-studio.exe', 
                'lms.exe',
                'Local Server - LM Studio.exe'
            ]
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_name = proc.info['name']
                    cmdline = ' '.join(proc.info.get('cmdline', [])) if proc.info.get('cmdline') else ''
                    
                    # Verificar si es un proceso de LM Studio
                    is_lm_studio = (
                        any(lm_name.lower() in proc_name.lower() for lm_name in lm_studio_process_names) or
                        'lm-studio' in cmdline.lower() or
                        'lmstudio' in cmdline.lower()
                    )
                    
                    if is_lm_studio:
                        pid = proc.info['pid']
                        logging.info(f"🔪 Matando proceso LM Studio: {proc_name} (PID: {pid})")
                        
                        # Terminar proceso
                        process = psutil.Process(pid)
                        process.terminate()
                        
                        # Esperar un poco y si no se termina, forzar kill
                        try:
                            process.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            process.kill()
                            logging.info(f"💀 Proceso forzado a terminar: {pid}")
                        
                        killed_processes.append({
                            'name': proc_name,
                            'pid': pid
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        
        # Fallback con taskkill (siempre ejecutar para asegurar)
        try:
            logging.info("🔪 Ejecutando taskkill como fallback/refuerzo...")
            
            # Intentar con diferentes nombres de proceso
            process_names = ['LM Studio.exe', 'lm-studio.exe', 'lms.exe']
            for proc_name in process_names:
                result = subprocess.run(['taskkill', '/F', '/IM', proc_name], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logging.info(f"✅ Taskkill exitoso para {proc_name}")
                    killed_processes.append({
                        'name': proc_name,
                        'method': 'taskkill'
                    })
                    
        except Exception as e:
            logging.warning(f"Taskkill fallback error: {e}")
        
        message = f'Matados {len(killed_processes)} procesos de LM Studio'
        if not PSUTIL_AVAILABLE:
            message += ' (solo taskkill - psutil no disponible)'
        
        return jsonify({
            'ok': True,
            'message': message,
            'killed_processes': killed_processes,
            'psutil_available': PSUTIL_AVAILABLE
        })
        
    except Exception as e:
        logging.error(f"Error killing LM Studio processes: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# Ruta de fallback para el problema de URL mal formada
@api_bp.route('/')
@api_bp.route('')
def api_fallback():
    """Fallback para rutas de API mal formadas"""
    logging.warning(f"Acceso a ruta API mal formada: {request.url}")
    return jsonify({
        'error': 'Ruta de API mal formada',
        'url_received': request.url,
        'suggestion': 'Verifica que las URLs comiencen con /api/'
    }), 400

@api_bp.route('/scan_campaigns', methods=['POST'])
def scan_campaigns():
    """Escanea campañas en un directorio dado"""
    try:
        data = request.get_json() or {}
        logging.info(f"Received scan_campaigns request with data: {data}")
        
        root_dir = data.get('rootDir') or data.get('root_dir') or data.get('path')
        logging.info(f"Extracted root_dir: {root_dir}")
        
        if not root_dir:
            logging.error("No rootDir provided in request")
            return jsonify({
                "success": False,
                "error": "rootDir es requerido"
            }), 400
        
        if not os.path.exists(root_dir):
            return jsonify({
                "success": False,
                "error": f"La ruta no existe: {root_dir}"
            }), 400
        
        logging.info(f"Escaneando campañas en: {root_dir}")
        
        # Buscar directorios de campañas
        campaigns = []
        try:
            # Buscar en subdirectorio campaigns si existe
            campaigns_dir = os.path.join(root_dir, "campaigns")
            if os.path.exists(campaigns_dir):
                scan_dir = campaigns_dir
            else:
                scan_dir = root_dir
                
            # Escanear directorios que contengan archivos .lua
            for item in os.listdir(scan_dir):
                item_path = os.path.join(scan_dir, item)
                if os.path.isdir(item_path):
                    # Verificar si contiene archivos .lua
                    has_lua = False
                    for root, dirs, files in os.walk(item_path):
                        if any(f.endswith('.lua') for f in files):
                            has_lua = True
                            break
                    
                    if has_lua:
                        campaigns.append({
                            'name': item,
                            'path': item_path,
                            'missions': []  # Se cargarán cuando se seleccione
                        })
        
        except Exception as e:
            logging.error(f"Error escaneando campañas: {e}")
            return jsonify({
                "success": False,
                "error": f"Error escaneando directorio: {str(e)}"
            }), 500
        
        logging.info(f"Encontradas {len(campaigns)} campañas")
        
        return jsonify({
            "success": True,
            "campaigns": campaigns,
            "total": len(campaigns),
            "scanned_path": root_dir
        })
        
    except Exception as e:
        logging.error(f"Error in scan_campaigns: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@api_bp.route('/scan_missions', methods=['POST'])
def scan_missions():
    """Escanea misiones en una campaña específica"""
    try:
        data = request.get_json() or {}
        logging.info(f"Received scan_missions request with data: {data}")
        
        root_dir = data.get('ROOT_DIR') or data.get('rootDir') or data.get('root_dir')
        campaign_name = data.get('campaign_name') or data.get('campaignName')
        include_fc = data.get('include_fc', False)
        
        if not root_dir:
            logging.error("No ROOT_DIR provided in request")
            return jsonify({
                "success": False,
                "error": "ROOT_DIR es requerido"
            }), 400
            
        if not campaign_name:
            logging.error("No campaign_name provided in request")
            return jsonify({
                "success": False,
                "error": "campaign_name es requerido"
            }), 400
        
        # Construir ruta de la campaña
        campaign_path = os.path.join(root_dir, campaign_name)
        if not os.path.exists(campaign_path):
            # Intentar en subdirectorio campaigns
            campaigns_subdir = os.path.join(root_dir, "campaigns", campaign_name)
            if os.path.exists(campaigns_subdir):
                campaign_path = campaigns_subdir
            else:
                return jsonify({
                    "success": False,
                    "error": f"No se encontró la campaña: {campaign_name}"
                }), 400
        
        logging.info(f"Escaneando misiones en: {campaign_path}")
        
        # Usar TranslationEngine para escanear misiones
        from app.services.translation_engine import TranslationEngine
        engine = TranslationEngine()
        
        normal_missions, fc_missions = engine.find_miz_files_grouped(campaign_path)
        
        missions = []
        
        # Agregar misiones normales
        for mission_path in normal_missions:
            mission_name = os.path.basename(mission_path)
            missions.append({
                'name': mission_name,
                'path': mission_path,
                'type': 'normal',
                'size': os.path.getsize(mission_path) if os.path.exists(mission_path) else 0
            })
        
        # Agregar misiones FC si se incluyen
        fc_patterns_detected = []
        if include_fc:
            for mission_path in fc_missions:
                mission_name = os.path.basename(mission_path)
                
                # Detectar qué patrón FC se usó para esta misión
                pattern_used = engine._get_fc_pattern_used(mission_name) if hasattr(engine, '_get_fc_pattern_used') else None
                
                missions.append({
                    'name': mission_name,
                    'path': mission_path,
                    'type': 'fc',
                    'size': os.path.getsize(mission_path) if os.path.exists(mission_path) else 0,
                    'fc_pattern': pattern_used
                })
                
                if pattern_used and pattern_used not in fc_patterns_detected:
                    fc_patterns_detected.append(pattern_used)
        
        logging.info(f"Encontradas {len(missions)} misiones ({len(normal_missions)} normales, {len(fc_missions)} FC)")
        if fc_patterns_detected:
            logging.info(f"Patrones FC detectados: {', '.join(fc_patterns_detected)}")
        
        return jsonify({
            "success": True,
            "missions": missions,
            "total": len(missions),
            "normal_count": len(normal_missions),
            "fc_count": len(fc_missions),
            "include_fc": include_fc,
            "campaign_path": campaign_path,
            "fc_patterns_detected": fc_patterns_detected,
            "detection_summary": {
                "total_files": len(normal_missions) + len(fc_missions),
                "normal_missions": len(normal_missions),
                "fc_missions": len(fc_missions),
                "patterns_found": fc_patterns_detected
            }
        })
        
    except Exception as e:
        logging.error(f"Error in scan_missions: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@api_bp.route('/auto_detect_roots', methods=['POST'])
def auto_detect_roots():
    """Detecta automáticamente directorios raíz de DCS usando el orchestrator"""
    try:
        data = request.get_json() or {}
        deep_scan = data.get('deep_scan', False)
        
        # Usar el orchestrator que tiene la lógica completa de detección
        orchestrator_service = get_orchestrator()
        
        detected_roots = orchestrator_service.auto_detect_dcs_roots(deep_scan)
        
        # Obtener resumen de campañas registradas y estado de unidades
        campaigns_summary = orchestrator_service.get_registered_campaigns_summary()
                    
        logging.info(f"Rutas DCS detectadas: {detected_roots}")
        
        return jsonify({
            'success': True,
            'roots': detected_roots,
            'deep_scan_used': deep_scan,
            'total': len(detected_roots),
            'campaigns_summary': campaigns_summary
        })
        
    except Exception as e:
        logging.error(f"Error detecting DCS roots: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/detect-dcs', methods=['POST'])
def detect_dcs_installation():
    """Detecta automáticamente la instalación completa de DCS World y configura rutas"""
    try:
        logging.info("🔍 Iniciando detección automática de DCS World")
        
        # Usar el orchestrator para detectar rutas
        orchestrator_service = get_orchestrator()
        
        # Detectar rutas de campañas
        detected_roots = orchestrator_service.auto_detect_dcs_roots(deep_scan=True)
        
        if not detected_roots:
            return jsonify({
                'ok': False,
                'message': 'No se encontró ninguna instalación de DCS World'
            })
        
        # Tomar la primera ruta detectada (generalmente la más probable)
        campaigns_path = detected_roots[0]
        
        # Para el deploy, usar la misma ruta que campañas por defecto
        deploy_path = campaigns_path
        
        # Verificar que la ruta de campañas existe y tiene la estructura correcta
        campaigns_dir = os.path.join(campaigns_path, 'Mods', 'campaigns')
        if os.path.exists(campaigns_dir):
            campaigns_path = campaigns_dir
        
        logging.info(f"✅ DCS detectado - Campañas: {campaigns_path}, Despliegue: {deploy_path}")
        
        return jsonify({
            'ok': True,
            'message': f'DCS World detectado en: {os.path.dirname(campaigns_path)}',
            'paths': {
                'campaigns_path': campaigns_path,
                'deploy_path': deploy_path
            },
            'detected_installations': len(detected_roots),
            'all_detected_paths': detected_roots
        })
        
    except Exception as e:
        logging.error(f"❌ Error detectando DCS: {e}")
        return jsonify({
            'ok': False,
            'message': f'Error al detectar DCS World: {str(e)}'
        }), 500

@api_bp.route('/drives/status', methods=['GET'])
def get_drives_status():
    """Obtiene el estado actual de las unidades y campañas registradas"""
    try:
        from app.services.campaign_registry import get_campaign_registry
        
        registry = get_campaign_registry()
        
        # Detectar cambios en unidades
        drive_changes = registry.detect_drive_changes()
        
        # Obtener resumen completo del estado
        status_summary = registry.get_drive_status_summary()
        
        # Obtener todas las campañas (disponibles y no disponibles)
        all_campaigns = registry.get_all_campaigns()
        unavailable_campaigns = [c for c in all_campaigns if not c.is_available]
        
        return jsonify({
            'success': True,
            'drive_changes': drive_changes,
            'status_summary': status_summary,
            'total_campaigns': len(all_campaigns),
            'unavailable_campaigns': [
                {
                    'name': c.name,
                    'path': c.path,
                    'drive_letter': c.drive_letter,
                    'missions_count': c.missions_count,
                    'last_seen': c.last_seen,
                    'total_size_mb': c.total_size_mb,
                    'detection_method': c.detection_method
                }
                for c in unavailable_campaigns
            ]
        })
        
    except Exception as e:
        logging.error(f"Error getting drives status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/campaigns/registered', methods=['GET'])
def get_registered_campaigns():
    """Obtiene todas las campañas registradas con filtros opcionales"""
    try:
        from app.services.campaign_registry import get_campaign_registry
        
        registry = get_campaign_registry()
        
        # Parámetros de filtrado
        only_available = request.args.get('available_only', 'false').lower() == 'true'
        drive_letter = request.args.get('drive')
        
        # Obtener campañas
        if drive_letter:
            campaigns = registry.get_campaigns_by_drive(drive_letter.upper())
        else:
            campaigns = registry.get_all_campaigns(only_available=only_available)
        
        # Convertir a formato JSON serializable
        campaigns_data = [
            {
                'name': c.name,
                'path': c.path,
                'drive_letter': c.drive_letter,
                'missions_count': c.missions_count,
                'last_seen': c.last_seen,
                'total_size_mb': c.total_size_mb,
                'is_available': c.is_available,
                'detection_method': c.detection_method
            }
            for c in campaigns
        ]
        
        return jsonify({
            'success': True,
            'campaigns': campaigns_data,
            'total': len(campaigns_data),
            'filters': {
                'only_available': only_available,
                'drive_letter': drive_letter
            }
        })
        
    except Exception as e:
        logging.error(f"Error getting registered campaigns: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/campaigns/cleanup', methods=['POST'])
def cleanup_old_campaigns():
    """Limpia entradas de campañas antiguas"""
    try:
        from app.services.campaign_registry import get_campaign_registry
        
        data = request.get_json() or {}
        days_old = data.get('days_old', 30)
        
        registry = get_campaign_registry()
        removed_count = registry.cleanup_old_entries(days_old)
        
        return jsonify({
            'success': True,
            'removed_count': removed_count,
            'days_old': days_old
        })
        
    except Exception as e:
        logging.error(f"Error cleaning up campaigns: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/debug/user_config', methods=['GET'])
def debug_user_config():
    """Debug endpoint para ver qué devuelve user_config"""
    try:
        from flask import current_app
        
        # Simular una request GET
        with current_app.test_request_context('/api/user_config', method='GET'):
            response_data = get_user_config()
            
        return jsonify({
            'debug_info': 'Respuesta de user_config',
            'response': response_data,
            'response_type': type(response_data).__name__
        })
        
    except Exception as e:
        logging.error(f"Error in debug endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/run', methods=['POST'])
def run_orchestrator():
    """Ejecuta el orquestador de traducción"""
    try:
        data = request.get_json() or {}
        logging.info(f"Received run request with data keys: {list(data.keys())}")
        
        # 🔍 DEBUG: Log específico para parámetros de cache
        logging.info(f"🔍 DEBUG API /run - Parámetros de cache recibidos:")
        logging.info(f"   use_cache: {data.get('use_cache')} (tipo: {type(data.get('use_cache'))})")
        logging.info(f"   overwrite_cache: {data.get('overwrite_cache')} (tipo: {type(data.get('overwrite_cache'))})")
        logging.info(f"   Payload completo: {data}")
        
        # Validar campos requeridos básicos
        required_fields = ['ROOT_DIR', 'campaign_name', 'missions']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({
                'ok': False,
                'error': f'Campos requeridos faltantes: {missing_fields}'
            }), 400
        
        # Validar que hay misiones seleccionadas
        if not data['missions'] or len(data['missions']) == 0:
            return jsonify({
                'ok': False,
                'error': 'Debe seleccionar al menos una misión'
            }), 400
        
        # Cargar configuración del usuario para completar campos faltantes
        from config.settings import DATA_DIR
        user_config_path = os.path.join(DATA_DIR, 'my_config', 'user_config.json')
        saved_config = {}
        if os.path.exists(user_config_path):
            with open(user_config_path, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
        
        # Manejar ARGS - puede ser string (desde JS) u objeto
        args_from_js = data.get('ARGS', '')
        if isinstance(args_from_js, str):
            # Si viene como string, extraer valores individuales del payload
            # Priorizar: datos enviados > configuración guardada > valores por defecto mínimos
            args_data = {
                'config': data.get('arg_config') or saved_config.get('arg_config', ''),
                'compat': data.get('arg_compat') or saved_config.get('arg_compat') or 'auto',
                'batch': int(data.get('arg_batch') or saved_config.get('arg_batch') or '4'),
                'timeout': int(data.get('arg_timeout') or saved_config.get('arg_timeout') or '200'),
                'model': data.get('lm_model') or saved_config.get('lm_model', ''),  # Vacío si no hay configuración
                'url': data.get('lm_url') or saved_config.get('lm_url') or LM_CONFIG['DEFAULT_URL']
            }
        else:
            # Si ya es un objeto, usarlo directamente
            args_data = args_from_js
        
        logging.info(f"Args construidos: {args_data}")
        logging.info(f"Configuración guardada leída: {saved_config}")
        logging.info(f"Parámetro use_cache recibido: {data.get('use_cache', True)}")
        logging.info(f"Parámetro overwrite_cache recibido: {data.get('overwrite_cache', False)}")
        
        # ✅ VALIDAR MODELO CARGADO ANTES DE INICIAR TRADUCCIÓN
        # Solo validar si el modo requiere traducción
        mode = data.get('mode', 'translate')
        if mode in ['translate', 'all', 'traducir']:
            lm_model = args_data.get('model', '').strip()
            lm_url = args_data.get('url', LM_CONFIG['DEFAULT_URL'])
            
            if not lm_model:
                return jsonify({
                    'ok': False,
                    'error': 'No se ha configurado un modelo de LM Studio. Por favor, selecciona un modelo antes de iniciar la traducción.',
                    'error_type': 'model_not_configured',
                    'suggestion': 'Ve a la configuración y selecciona un modelo de la lista disponible'
                }), 400
            
            # Verificar que LM Studio esté disponible y tenga modelos cargados
            try:
                from app.services.translation_engine import TranslationEngine
                engine = TranslationEngine()
                lm_status = engine.check_lm_studio_status(lm_url, lm_model)
                
                if not lm_status.get('available'):
                    return jsonify({
                        'ok': False,
                        'error': f'LM Studio no está disponible: {lm_status.get("error_message", "Servicio no encontrado")}',
                        'error_type': 'lm_studio_unavailable',
                        'suggestion': lm_status.get('suggestion', 'Verifica que LM Studio esté ejecutándose')
                    }), 400
                
                if not lm_status.get('models_loaded'):
                    # Intentar cargar automáticamente el modelo requerido
                    logging.info(f"🔄 Modelo {lm_model} no está cargado. Intentando carga automática...")
                    
                    try:
                        lm_service = LMStudioService(base_url=lm_url)
                        load_success = lm_service.load_model_via_cli(lm_model)
                        
                        if load_success:
                            logging.info(f"✅ Modelo {lm_model} cargado exitosamente via CLI")
                            
                            # Verificar nuevamente que el modelo esté disponible
                            import time
                            time.sleep(2)  # Dar tiempo para que LM Studio procese el modelo
                            
                            lm_status_after_load = engine.check_lm_studio_status(lm_url, lm_model)
                            if lm_status_after_load.get('models_loaded'):
                                logging.info(f"🎉 Modelo {lm_model} confirmado como cargado y listo")
                            else:
                                logging.warning(f"⚠️ Modelo {lm_model} cargado pero no aparece en la lista de disponibles")
                        else:
                            # Carga automática falló, devolver error con sugerencias
                            return jsonify({
                                'ok': False,
                                'error': f'No se pudo cargar automáticamente el modelo "{lm_model}" en LM Studio.',
                                'error_type': 'auto_load_failed',
                                'suggestion': f'Por favor, carga manualmente el modelo "{lm_model}" en LM Studio y vuelve a intentar.',
                                'details': {
                                    'requested_model': lm_model,
                                    'lm_studio_url': lm_url,
                                    'auto_load_attempted': True
                                }
                            }), 400
                            
                    except Exception as load_error:
                        logging.error(f"❌ Error en carga automática de modelo: {load_error}")
                        return jsonify({
                            'ok': False,
                            'error': f'Error al intentar cargar automáticamente el modelo "{lm_model}": {str(load_error)}',
                            'error_type': 'auto_load_error',
                            'suggestion': f'Por favor, carga manualmente el modelo "{lm_model}" en LM Studio.',
                            'details': {
                                'requested_model': lm_model,
                                'lm_studio_url': lm_url,
                                'load_error': str(load_error)
                            }
                        }), 400
                
                # Verificación adicional: comprobar si el modelo específico está cargado
                try:
                    lm_service = LMStudioService(base_url=lm_url)
                    loaded_models = lm_service.get_loaded_models()
                    
                    # Verificar si el modelo específico está en la lista de cargados
                    model_found = False
                    for model in loaded_models:
                        model_id = model.get('id', '') if isinstance(model, dict) else str(model)
                        model_name = model.get('name', '') if isinstance(model, dict) else str(model)
                        
                        # Comparar por ID completo, nombre o nombre corto
                        if (lm_model == model_id or 
                            lm_model == model_name or 
                            lm_model == model_id.split('/')[-1] or
                            lm_model == model_name.split('/')[-1]):
                            model_found = True
                            break
                    
                    if not model_found and loaded_models:
                        # Hay modelos cargados pero no el que necesitamos
                        logging.info(f"🔄 Modelo específico {lm_model} no encontrado. Intentando carga automática...")
                        
                        try:
                            load_success = lm_service.load_model_via_cli(lm_model)
                            
                            if load_success:
                                logging.info(f"✅ Modelo {lm_model} cargado exitosamente")
                                import time
                                time.sleep(3)  # Dar más tiempo para procesamiento
                            else:
                                return jsonify({
                                    'ok': False,
                                    'error': f'No se pudo cargar el modelo específico "{lm_model}". Modelos disponibles: {[m.get("name", m.get("id", "")) for m in loaded_models[:3]]}',
                                    'error_type': 'specific_model_load_failed',
                                    'suggestion': f'Verifica que el modelo "{lm_model}" existe o selecciona uno de los modelos disponibles.',
                                    'available_models': [m.get('name', m.get('id', '')) for m in loaded_models]
                                }), 400
                                
                        except Exception as specific_load_error:
                            return jsonify({
                                'ok': False,
                                'error': f'Error cargando modelo específico "{lm_model}": {str(specific_load_error)}',
                                'error_type': 'specific_model_load_error',
                                'available_models': [m.get('name', m.get('id', '')) for m in loaded_models]
                            }), 400
                    
                except Exception as model_check_error:
                    logging.warning(f"⚠️ Error verificando modelo específico: {model_check_error}")
                    # Continuar con la ejecución si la verificación específica falla
                
                logging.info(f"✅ Validación de modelo exitosa: {lm_model} está disponible en LM Studio")
                
            except Exception as e:
                logging.error(f"Error validando modelo: {e}")
                return jsonify({
                    'ok': False,
                    'error': f'Error verificando el estado del modelo: {str(e)}',
                    'error_type': 'model_check_failed',
                    'suggestion': 'Verifica que LM Studio esté ejecutándose y accesible'
                }), 500

        # Construir ruta de la campaña con búsqueda inteligente
        campaign_name_requested = data['campaign_name']
        root_dir = data['ROOT_DIR']
        
        # Función para buscar campaña por nombre (maneja nombres normalizados)
        def find_campaign_path(requested_name, base_dir):
            """Busca la campaña por nombre exacto o normalizado"""
            # Intentar nombre exacto
            exact_path = os.path.join(base_dir, requested_name)
            if os.path.exists(exact_path):
                return exact_path, requested_name
            
            # Buscar por nombres similares (manejar espacios vs guiones bajos)
            try:
                items = os.listdir(base_dir)
                for item in items:
                    if os.path.isdir(os.path.join(base_dir, item)):
                        # Comparar normalizando nombres (espacios <-> guiones bajos)
                        item_normalized = item.replace(' ', '_').replace('-', '_')
                        requested_normalized = requested_name.replace(' ', '_').replace('-', '_')
                        if item_normalized.lower() == requested_normalized.lower():
                            return os.path.join(base_dir, item), item
            except Exception:
                pass
            
            return None, None
        
        # Buscar campaña en root_dir
        campaign_path, actual_campaign_name = find_campaign_path(campaign_name_requested, root_dir)
        
        if not campaign_path:
            # Intentar en subdirectorio campaigns
            campaigns_dir = os.path.join(root_dir, "campaigns")
            if os.path.exists(campaigns_dir):
                campaign_path, actual_campaign_name = find_campaign_path(campaign_name_requested, campaigns_dir)
        
        if not campaign_path:
            return jsonify({
                'ok': False,
                'error': f'No se encontró la campaña: {campaign_name_requested} en {root_dir}'
            }), 400
        
        logging.info(f"Ruta de campaña detectada: {campaign_path}")
        
        # Construir payload para el orquestrador
        payload = {
            'ROOT_DIR': data['ROOT_DIR'],
            'DEPLOY_DIR': data.get('DEPLOY_DIR', ''),
            'DEPLOY_OVERWRITE': data.get('DEPLOY_OVERWRITE', True),
            'FILE_TARGET': data.get('FILE_TARGET', 'l10n/DEFAULT/dictionary'),
            'ARGS': args_data,
            'mode': data.get('mode', 'translate'),
            'campaigns': [{
                'name': actual_campaign_name,  # Usar el nombre real encontrado
                'path': campaign_path,
                'missions': data['missions']
            }],
            'include_fc': data.get('include_fc', False),
            'use_cache': data.get('use_cache', True),  # Pasar parámetro de cache
            'overwrite_cache': data.get('overwrite_cache', False)  # Pasar parámetro de sobrescritura
        }
        
        logging.info(f"Payload completo enviado al orquestrador: {payload}")
        
        # Importar y usar el orquestrador
        orchestrator = get_orchestrator()
        
        # 🐛 DEBUG: Agregar logging detallado DESPUÉS de inicializar
        logging.info(f"🔧 DEBUG: Orquestador inicializado correctamente")
        logging.info(f"🔧 DEBUG: Tipo de orquestador: {type(orchestrator)}")
        logging.info(f"🔧 DEBUG: Payload keys: {list(payload.keys())}")
        
        # Ejecutar en background (no bloqueante)
        import threading
        def run_in_background():
            try:
                logging.info("🚀 DEBUG: Iniciando run_orchestrator en background thread...")
                result = orchestrator.run_orchestrator(payload)
                logging.info(f"✅ DEBUG: Orquestador completado exitosamente: {result}")
            except Exception as e:
                logging.error(f"❌ BACKGROUND ERROR: Error crítico en orquestrador background: {e}")
                logging.error(f"❌ BACKGROUND ERROR: Tipo de error: {type(e).__name__}")
                import traceback
                logging.error(f"❌ BACKGROUND ERROR: Traceback completo:\n{traceback.format_exc()}")
                
                # Guardar información del error para debugging posterior
                error_info = {
                    'timestamp': datetime.now().isoformat(),
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc(),
                    'payload_summary': {
                        'mode': payload.get('mode', 'unknown'),
                        'campaign': payload.get('campaign_name', 'unknown'),
                        'missions_count': len(payload.get('missions', [])),
                        'model': payload.get('lm_model', 'unknown')
                    }
                }
                
                # Intentar guardar error en log específico
                try:
                    from config.settings import DATA_DIR
                    error_log_path = os.path.join(DATA_DIR, 'logs', 'orchestrator_errors.json')
                    os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
                    
                    # Leer errores existentes
                    existing_errors = []
                    if os.path.exists(error_log_path):
                        try:
                            with open(error_log_path, 'r', encoding='utf-8') as f:
                                existing_errors = json.load(f)
                        except:
                            existing_errors = []
                    
                    # Agregar nuevo error
                    existing_errors.append(error_info)
                    
                    # Mantener solo los últimos 50 errores
                    if len(existing_errors) > 50:
                        existing_errors = existing_errors[-50:]
                    
                    # Guardar
                    with open(error_log_path, 'w', encoding='utf-8') as f:
                        json.dump(existing_errors, f, indent=2, ensure_ascii=False)
                        
                    logging.info(f"📝 Error guardado en: {error_log_path}")
                    
                except Exception as save_error:
                    logging.error(f"❌ No se pudo guardar el error: {save_error}")
                    
                # Intentar limpiar el estado del orquestrador si está atascado
                try:
                    if hasattr(orchestrator, 'status'):
                        orchestrator.status['is_running'] = False
                        logging.info("🔧 Estado del orquestrador resetado después del error")
                except Exception as reset_error:
                    logging.error(f"❌ No se pudo resetear el estado del orquestrador: {reset_error}")
        
        thread = threading.Thread(target=run_in_background)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'ok': True,
            'message': 'Traducción iniciada exitosamente',
            'payload_summary': {
                'campaign': data['campaign_name'],
                'missions_count': len(data['missions']),
                'mode': data.get('mode', 'translate'),
                'include_fc': data.get('include_fc', False),
                'use_cache': data.get('use_cache', True)
            }
        })
        
    except Exception as e:
        logging.error(f"❌ ERROR CRÍTICO en run_orchestrator: {e}")
        logging.error(f"❌ Tipo de error: {type(e).__name__}")
        import traceback
        logging.error(f"❌ Traceback completo:\n{traceback.format_exc()}")
        
        # Determinar tipo específico de error para respuesta más útil
        error_message = str(e)
        error_type = type(e).__name__
        
        # Errores específicos de LM Studio / modelo
        if "orchestrator" in error_message.lower():
            error_response = {
                'ok': False,
                'error': 'Error de inicialización del orquestador',
                'error_type': 'orchestrator_initialization_error',
                'details': error_message,
                'suggestion': 'Verifica la configuración del sistema y reinicia la aplicación'
            }
        elif "model" in error_message.lower() or "lm" in error_message.lower():
            error_response = {
                'ok': False,
                'error': 'Error relacionado con el modelo de lenguaje',
                'error_type': 'model_error',
                'details': error_message,
                'suggestion': 'Verifica que LM Studio esté funcionando correctamente y el modelo esté cargado'
            }
        elif "connection" in error_message.lower():
            error_response = {
                'ok': False,
                'error': 'Error de conexión',
                'error_type': 'connection_error', 
                'details': error_message,
                'suggestion': 'Verifica la conectividad de red y que LM Studio esté accesible'
            }
        else:
            error_response = {
                'ok': False,
                'error': f'Error interno del servidor: {error_message}',
                'error_type': error_type,
                'details': error_message,
                'suggestion': 'Error inesperado. Revisa los logs para más información.'
            }
        
        return jsonify(error_response), 500

@api_bp.route('/validate_paths', methods=['POST'])
def validate_paths():
    """Valida rutas sin guardar configuración"""
    try:
        data = request.get_json() or {}
        
        validation = {
            'paths_valid': False,
            'ROOT_DIR': None,
            'DEPLOY_DIR': None,
            'campaign_path_valid': False,
            'deploy_path_valid': False
        }
        
        # Verificar ROOT_DIR
        root_dir = data.get('ROOT_DIR', '').strip()
        logging.info(f"Validando ROOT_DIR: '{root_dir}'")
        if root_dir:
            root_exists = os.path.exists(root_dir)
            logging.info(f"ROOT_DIR existe: {root_exists}")
            validation['ROOT_DIR'] = root_exists
            validation['campaign_path_valid'] = root_exists
        else:
            validation['ROOT_DIR'] = None
            validation['campaign_path_valid'] = False
            
        # Verificar DEPLOY_DIR
        deploy_dir = data.get('DEPLOY_DIR', '').strip()
        logging.info(f"Validando DEPLOY_DIR: '{deploy_dir}'")
        if deploy_dir:
            deploy_exists = os.path.exists(deploy_dir)
            logging.info(f"DEPLOY_DIR existe: {deploy_exists}")
            validation['DEPLOY_DIR'] = deploy_exists
            validation['deploy_path_valid'] = deploy_exists
        else:
            validation['DEPLOY_DIR'] = None
            validation['deploy_path_valid'] = False
            
        validation['paths_valid'] = validation['campaign_path_valid'] or validation['deploy_path_valid']
        
        # Debug adicional
        debug_info = {
            'received_data': data,
            'root_dir_raw': data.get('ROOT_DIR'),
            'deploy_dir_raw': data.get('DEPLOY_DIR'),
            'root_dir_processed': root_dir,
            'deploy_dir_processed': deploy_dir
        }
        logging.info(f"Debug validación: {debug_info}")
        
        return jsonify({
            'success': True,
            'validation': validation,
            'debug': debug_info
        })
        
    except Exception as e:
        logging.error(f"Error validating paths: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/auto_root_scan', methods=['POST'])
def auto_root_scan():
    """Detecta automáticamente las rutas de instalación de DCS World"""
    try:
        data = request.get_json() or {}
        deep = data.get('deep', False)
        
        # Usar el orchestrator que tiene la lógica completa de detección
        from app.services.orchestrator import DCSOrchestrator
        orchestrator = DCSOrchestrator()
        
        # La función del orchestrator ya maneja la detección automática de unidades
        found_roots = orchestrator.auto_detect_dcs_roots(deep_scan=deep)
        
        logging.info(f"Auto-detección DCS completada: {len(found_roots)} rutas encontradas (deep={deep})")
        for root in found_roots:
            logging.info(f"  - {root}")
        
        return jsonify({
            'ok': True,
            'roots': found_roots,
            'deep': deep
        })
        
    except Exception as e:
        logging.error(f"Error in auto_root_scan: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/missions_by_mode', methods=['GET'])
def get_missions_by_mode():
    """
    Obtener misiones disponibles filtradas por modo de trabajo.
    
    Integra dos fuentes:
    1. Ruta original DCS (configurada por usuario) - para obtener misiones
    2. app/data/traducciones - para determinar estados
    
    Query Parameters:
        - mode: 'traducir', 'reempaquetar', 'desplegar'
        - campaign: nombre de campaña (opcional)
    """
    try:
        mode = request.args.get('mode', 'traducir').lower()
        campaign = request.args.get('campaign', None)
        
        # Validar modo
        valid_modes = ['traducir', 'reempaquetar', 'desplegar']
        if mode not in valid_modes:
            return jsonify({
                'ok': False,
                'error': f'Modo inválido. Debe ser uno de: {valid_modes}'
            }), 400
        
        # Obtener configuración del usuario desde el archivo JSON directamente
        from config.settings import DATA_DIR
        user_config_path = os.path.join(DATA_DIR, 'my_config', 'user_config.json')
        
        user_config = {}
        if os.path.exists(user_config_path):
            try:
                with open(user_config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
            except Exception as e:
                logging.error(f"Error reading user config: {e}")
        
        root_dir = user_config.get('ROOT_DIR', '')
        
        if not root_dir or not os.path.exists(root_dir):
            logging.warning(f"ROOT_DIR validation failed: '{root_dir}' (exists: {os.path.exists(root_dir) if root_dir else 'N/A'})")
            return jsonify({
                'ok': False,
                'error': 'Ruta de DCS no configurada. Configura ROOT_DIR primero.'
            })
        
        # Obtener detector de estados
        detector = get_mission_state_detector()
        
        available_missions = []
        summary_counts = {'sin_traducir': 0, 'traducida': 0, 'reempaquetada': 0, 'desplegada': 0}
        total_missions_found = 0
        
        # Si se especifica campaña, filtrar solo esa
        campaigns_to_check = [campaign] if campaign else []
        
        # Si no se especifica campaña, obtener todas
        if not campaign:
            try:
                campaigns_to_check = [item for item in os.listdir(root_dir) 
                                    if os.path.isdir(os.path.join(root_dir, item))]
            except Exception as e:
                return jsonify({
                    'ok': False,
                    'error': f'Error accediendo a la ruta DCS: {str(e)}'
                })
        
        # Explorar campañas
        for campaign_name in campaigns_to_check:
            campaign_path = os.path.join(root_dir, campaign_name)
            
            if not os.path.exists(campaign_path) or not os.path.isdir(campaign_path):
                continue
            
            # Obtener misiones de la campaña (buscar en subcarpeta Missions/)
            missions_path = os.path.join(campaign_path, 'Missions')
            if not os.path.exists(missions_path):
                # Si no existe Missions/, buscar directamente en la carpeta de campaña
                missions_path = campaign_path
            
            try:
                for file in os.listdir(missions_path):
                    if file.endswith('.miz'):
                        total_missions_found += 1
                        
                        # Detectar estado de la misión
                        mission_state = detector.detect_mission_state(file, campaign_name)
                        state = mission_state.state.value
                        summary_counts[state] += 1
                        
                        # Aplicar filtro por modo
                        include_mission = False
                        if mode == 'traducir':
                            # Traducir: todas las misiones
                            include_mission = True
                        elif mode == 'reempaquetar':
                            # Reempaquetar: solo traducidas
                            include_mission = (state == 'traducida')
                        elif mode == 'desplegar':
                            # Desplegar: solo reempaquetadas
                            include_mission = (state == 'reempaquetada')
                        
                        if include_mission:
                            available_missions.append({
                                'name': file,
                                'campaign': campaign_name,
                                'state': state,
                                'path': os.path.join(missions_path, file)
                            })
            
            except Exception as e:
                logging.error(f"Error explorando campaña {campaign_name}: {e}")
                continue
        
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
        
        # Ordenar misiones por orden natural (numérico)
        available_missions.sort(key=natural_sort_key)

        # Preparar información detallada por modo
        mode_info = {
            'traducir': {
                'description': 'Todas las misiones disponibles para traducir',
                'icon': '🌍',
                'action': 'Extraer y traducir'
            },
            'reempaquetar': {
                'description': 'Solo misiones que ya han sido traducidas',
                'icon': '📦', 
                'action': 'Reempaquetar en .miz'
            },
            'desplegar': {
                'description': 'Solo misiones reempaquetadas listas para instalar',
                'icon': '🚀',
                'action': 'Desplegar al juego'
            }
        }
        
        return jsonify({
            'ok': True,
            'mode': mode,
            'missions': available_missions,
            'count': len(available_missions),
            'campaign': campaign,
            'mode_info': mode_info[mode],
            'summary': {
                'total_missions': total_missions_found,
                'sin_traducir': summary_counts['sin_traducir'],
                'traducidas': summary_counts['traducida'],
                'reempaquetadas': summary_counts['reempaquetada'],
                'desplegadas': summary_counts['desplegada']
            },
            'root_dir': root_dir
        })
        
    except Exception as e:
        logging.error(f"Error getting missions by mode: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/mission_states', methods=['GET'])
def get_mission_states():
    """
    Obtener estados detallados de todas las misiones.
    
    Query Parameters:
        - campaign: nombre de campaña (opcional)
    """
    try:
        campaign = request.args.get('campaign', None)
        
        # Obtener detector de estados
        detector = get_mission_state_detector()
        
        # Obtener resumen completo
        summary = detector.get_campaign_summary(campaign)
        
        # Convertir misiones a formato JSON serializable
        missions_data = []
        for mission in summary['missions']:
            missions_data.append({
                'filename': mission.filename,
                'state': mission.state.value,
                'translation_path': mission.translation_path,
                'has_lua_files': mission.has_lua_files,
                'has_repackaged_miz': mission.has_repackaged_miz,
                'has_deployment': mission.has_deployment,
                'translation_progress': mission.translation_progress,
                'last_modified': mission.last_modified,
                'error_message': mission.error_message
            })
        
        return jsonify({
            'ok': True,
            'campaign': campaign,
            'summary': summary['by_state'],
            'total_missions': summary['total_missions'],
            'missions': missions_data
        })
        
    except Exception as e:
        logging.error(f"Error getting mission states: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/campaigns_by_mode', methods=['GET'])
def get_campaigns_by_mode():
    """
    Obtener campañas que tienen misiones disponibles para el modo seleccionado.
    
    Integra dos fuentes:
    1. Ruta original DCS (configurada por usuario) - para descubrir campañas
    2. app/data/traducciones - para determinar estados de misiones
    
    Query Parameters:
        - mode: modo de trabajo (traducir, reempaquetar, desplegar)
    """
    try:
        mode = request.args.get('mode', 'traducir')
        
        # Obtener configuración del usuario
        from app.services.user_config import UserConfigService
        config_service = UserConfigService()
        user_config = config_service.load_config()
        root_dir = user_config.get('ROOT_DIR', '')
        
        if not root_dir or not os.path.exists(root_dir):
            logging.warning(f"[load_missions] ROOT_DIR validation failed: '{root_dir}' (exists: {os.path.exists(root_dir) if root_dir else 'N/A'})")
            return jsonify({
                'ok': False,
                'error': 'Ruta de DCS no configurada o no existe. Por favor configura ROOT_DIR primero.'
            })
        
        # Obtener detector de estados para analizar traducciones
        detector = get_mission_state_detector()
        
        campaigns_with_missions = []
        
        # Explorar campañas en la ruta original DCS
        try:
            for item in os.listdir(root_dir):
                campaign_path = os.path.join(root_dir, item)
                
                # Verificar que sea directorio de campaña
                if not os.path.isdir(campaign_path):
                    continue
                
                # Obtener misiones de esta campaña
                campaign_missions = []
                for file in os.listdir(campaign_path):
                    if file.endswith('.miz'):
                        campaign_missions.append(file)
                
                if not campaign_missions:
                    continue  # Campaña sin misiones
                
                # Filtrar misiones según el modo seleccionado
                available_missions = []
                state_counts = {'sin_traducir': 0, 'traducida': 0, 'reempaquetada': 0, 'desplegada': 0}
                
                for mission_file in campaign_missions:
                    # Detectar estado de la misión
                    mission_state = detector.detect_mission_state(mission_file, item)
                    state = mission_state.state.value
                    state_counts[state] += 1
                    
                    # Aplicar filtro por modo
                    if mode == 'traducir':
                        # Traducir: todas las misiones están disponibles
                        available_missions.append(mission_file)
                    elif mode == 'reempaquetar':
                        # Reempaquetar: solo misiones traducidas
                        if state == 'traducida':
                            available_missions.append(mission_file)
                    elif mode == 'desplegar':
                        # Desplegar: solo misiones reempaquetadas
                        if state == 'reempaquetada':
                            available_missions.append(mission_file)
                
                # Solo incluir campaña si tiene misiones disponibles para el modo
                if available_missions:
                    # Crear descripción del estado
                    state_parts = []
                    if state_counts['sin_traducir'] > 0:
                        state_parts.append(f"{state_counts['sin_traducir']} sin traducir")
                    if state_counts['traducida'] > 0:
                        state_parts.append(f"{state_counts['traducida']} traducidas")
                    if state_counts['reempaquetada'] > 0:
                        state_parts.append(f"{state_counts['reempaquetada']} reempaquetadas")
                    
                    state_info = " • ".join(state_parts) if state_parts else "disponibles"
                    
                    campaigns_with_missions.append({
                        'name': item,
                        'mission_count': len(available_missions),
                        'total_missions': len(campaign_missions),
                        'state_info': state_info,
                        'state_counts': state_counts,
                        'source_path': campaign_path
                    })
        
        except Exception as e:
            logging.error(f"Error explorando campañas en {root_dir}: {e}")
            return jsonify({
                'ok': False,
                'error': f'Error accediendo a la ruta DCS: {str(e)}'
            })
        
        # Ordenar por número de misiones disponibles (descendente)
        campaigns_with_missions.sort(key=lambda c: c['mission_count'], reverse=True)
        
        return jsonify({
            'ok': True,
            'mode': mode,
            'campaigns': campaigns_with_missions,
            'total_campaigns': len(campaigns_with_missions),
            'root_dir': root_dir
        })
        
    except Exception as e:
        logging.error(f"Error getting campaigns by mode: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# === ENDPOINTS DE PRESETS ===

@api_bp.route('/presets', methods=['GET'])
def get_presets():
    """Obtiene archivos YAML de presets disponibles - COPIA DE get_promts()"""
    try:
        # Usar PRESETS_DIR (directorio app/data/presets)
        presets_dir = PRESETS_DIR
        
        if not os.path.exists(presets_dir):
            return jsonify({'ok': True, 'presets': [], 'total': 0})
        
        yaml_files = []
        for ext in ['*.yaml', '*.yml']:
            yaml_files.extend(glob.glob(os.path.join(presets_dir, ext)))
        
        # Procesar cada archivo YAML para obtener metadatos
        presets = []
        for filepath in yaml_files:
            try:
                filename = os.path.basename(filepath)
                # Leer el archivo como texto simple (sin PyYAML)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extraer name y description manualmente (simple parsing)
                name = filename[:-5]  # quitar .yaml
                description = ''
                
                # Buscar líneas name: y description:
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('name:'):
                        name = line.split('name:', 1)[1].strip().strip('"\'')
                    elif line.startswith('description:'):
                        description = line.split('description:', 1)[1].strip().strip('"\'')
                
                presets.append({
                    'name': name,
                    'filename': filename,
                    'created': '',
                    'version': '1.0',
                    'type': 'predefined',
                    'description': description
                })
                
            except Exception as e:
                logging.error(f"Error reading preset {filepath}: {e}")
        
        # Ordenar por nombre
        presets.sort(key=lambda x: x['name'])
        
        logging.info(f"🚀 Presets encontrados: {len(presets)}")
        
        return jsonify({
            'ok': True,
            'presets': presets,
            'total': len(presets)
        })
        
    except Exception as e:
        logging.error(f"Error getting presets: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@api_bp.route('/presets/test', methods=['GET'])
def test_presets():
    """Endpoint de test con datos hardcodeados"""
    return jsonify({
        'ok': True,
        'presets': [
            {
                'name': 'Preset Ligero TEST',
                'filename': '1-preset-ligero.yaml',
                'created': '2025-10-12',
                'version': '1.0',
                'type': 'predefined',
                'description': 'Test preset ligero'
            },
            {
                'name': 'Preset Balanceado TEST',
                'filename': '2-preset-balanceado.yaml', 
                'created': '2025-10-12',
                'version': '1.0',
                'type': 'predefined',
                'description': 'Test preset balanceado'
            }
        ],
        'total': 2
    })

@api_bp.route('/presets/debug', methods=['GET'])
def debug_presets():
    """Debug endpoint para verificar presets"""
    try:
        import os
        
        # Debug directo
        debug_info = {
            'cwd': os.getcwd(),
            'presets_dir_calculated': os.path.join(os.getcwd(), 'app', 'data', 'presets'),
            'files_in_dir': [],
            'presets_found': []
        }
        
        # Verificar directorio
        presets_dir = os.path.join(os.getcwd(), 'app', 'data', 'presets')
        if os.path.exists(presets_dir):
            debug_info['files_in_dir'] = os.listdir(presets_dir)
        
        # Test PresetService
        preset_service = PresetService()
        debug_info['preset_service_dir'] = preset_service.presets_dir
        debug_info['preset_service_dir_exists'] = os.path.exists(preset_service.presets_dir)
        
        # Verificar YAML availability
        try:
            debug_info['yaml_available'] = True
            debug_info['yaml_version'] = yaml.__version__ if hasattr(yaml, '__version__') else 'unknown'
        except ImportError:
            debug_info['yaml_available'] = False
        
        # Verificar YAML_AVAILABLE en presets service
        from app.services.presets import YAML_AVAILABLE
        debug_info['yaml_available_in_service'] = YAML_AVAILABLE
        
        presets = preset_service.list_presets()
        debug_info['presets_found'] = presets
        
        return jsonify({
            'ok': True,
            'debug': debug_info
        })
        
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e),
            'traceback': str(e.__traceback__)
        }), 500

@api_bp.route('/presets/<preset_name>', methods=['GET'])
def get_preset(preset_name):
    """Obtiene la configuración de un preset específico incluyendo lm_api_config"""
    try:
        # Buscar el archivo del preset por nombre
        presets_dir = PRESETS_DIR
        
        if not os.path.exists(presets_dir):
            return jsonify({
                'ok': False,
                'error': f'Directorio de presets no encontrado'
            }), 404
        
        # Buscar archivo que corresponda al nombre
        preset_file = None
        for ext in ['*.yaml', '*.yml']:
            files = glob.glob(os.path.join(presets_dir, ext))
            for filepath in files:
                # Leer archivo para verificar el nombre
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Buscar línea name: 
                file_name = os.path.basename(filepath)[:-5]  # nombre sin .yaml
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('name:'):
                        yaml_name = line.split('name:', 1)[1].strip().strip('"\'')
                        if yaml_name == preset_name or file_name == preset_name:
                            preset_file = filepath
                            break
                if preset_file:
                    break
            if preset_file:
                break
        
        if not preset_file:
            return jsonify({
                'ok': False,
                'error': f'Preset "{preset_name}" no encontrado'
            }), 404
        
        # Cargar el archivo YAML completo usando yaml.safe_load
        with open(preset_file, 'r', encoding='utf-8') as f:
            try:
                import yaml
                preset_data = yaml.safe_load(f) or {}
            except ImportError:
                # Fallback al parser manual si no hay yaml
                preset_data = {}
                content = f.read()
                for line in content.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('#') and not line.startswith(' '):
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        preset_data[key] = value
        
        # Extraer configuración básica
        config = {}
        
        # Mapear campos YAML a configuración de interfaz
        if 'lm_compat' in preset_data:
            config['arg_compat'] = preset_data['lm_compat']
        if 'config' in preset_data:
            config['arg_config'] = preset_data['config']  # Usar arg_config en lugar de prompt_file
        if 'batch_size' in preset_data:
            config['arg_batch'] = preset_data['batch_size']
        if 'timeout' in preset_data:
            config['arg_timeout'] = preset_data['timeout']
        if 'name' in preset_data:
            config['preset_name'] = preset_data['name']
        if 'description' in preset_data:
            config['preset_description'] = preset_data['description']
        
        # NUEVO: Información de modelos recomendados
        if 'supported_models' in preset_data:
            config['supported_models'] = preset_data['supported_models']
            logging.info(f"🎯 Modelos recomendados para {preset_name}: {preset_data['supported_models']}")
        if 'weight' in preset_data:
            config['preset_weight'] = preset_data['weight']
        if 'hardware_profile' in preset_data:
            config['hardware_profile'] = preset_data['hardware_profile']
        
        # IMPORTANTE: Cargar lm_api_config del preset
        if 'lm_api_config' in preset_data:
            lm_api_config = preset_data['lm_api_config']
            logging.info(f"🔧 Cargando lm_api_config del preset {preset_name}: {lm_api_config}")
            
            # Mapear parámetros de lm_api_config a la interfaz
            # Estos parámetros deben mostrarse en "Parámetros del modelo (ARGS)"
            if 'temperature' in lm_api_config:
                config['api_temperature'] = lm_api_config['temperature']
            if 'top_p' in lm_api_config:
                config['api_top_p'] = lm_api_config['top_p']
            if 'top_k' in lm_api_config:
                config['api_top_k'] = lm_api_config['top_k']
            if 'max_tokens' in lm_api_config:
                config['api_max_tokens'] = lm_api_config['max_tokens']
            if 'repetition_penalty' in lm_api_config:
                config['api_repetition_penalty'] = lm_api_config['repetition_penalty']
            if 'presence_penalty' in lm_api_config:
                config['api_presence_penalty'] = lm_api_config['presence_penalty']
            if 'frequency_penalty' in lm_api_config:
                config['api_frequency_penalty'] = lm_api_config['frequency_penalty']
            
            # Incluir lm_api_config completo para uso interno
            config['lm_api_config'] = lm_api_config
        
        # Valores por defecto
        config.setdefault('arg_compat', 'completions')
        config.setdefault('arg_config', '1-instruct-ligero.yaml')
        config.setdefault('arg_batch', 8)
        config.setdefault('arg_timeout', 120)
        
        return jsonify({
            'ok': True,
            'preset_name': preset_name,
            'config': config
        })
        
    except Exception as e:
        logging.error(f"Error loading preset {preset_name}: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/presets', methods=['POST'])
def save_preset():
    """Guarda un nuevo preset (solo JSON para presets de usuario)"""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'config' not in data:
            return jsonify({
                'ok': False,
                'error': 'Se requieren campos "name" y "config"'
            }), 400
        
        preset_service = PresetService()
        success = preset_service.save_preset(data['name'], data['config'])
        
        if success:
            return jsonify({
                'ok': True,
                'message': f'Preset "{data["name"]}" guardado exitosamente'
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Error guardando preset'
            }), 500
        
    except Exception as e:
        logging.error(f"Error saving preset: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/presets/<preset_name>', methods=['DELETE'])
def delete_preset(preset_name):
    """Elimina un preset (solo presets de usuario JSON)"""
    try:
        preset_service = PresetService()
        success = preset_service.delete_preset(preset_name)
        
        if success:
            return jsonify({
                'ok': True,
                'message': f'Preset "{preset_name}" eliminado exitosamente'
            })
        else:
            return jsonify({
                'ok': False,
                'error': f'No se pudo eliminar el preset "{preset_name}"'
            }), 404
        
    except Exception as e:
        logging.error(f"Error deleting preset {preset_name}: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/models-presets', methods=['GET'])
def get_models_presets():
    """Obtiene presets existentes y recomendaciones de modelos"""
    try:
        if not YAML_AVAILABLE:
            return jsonify({
                'ok': False,
                'error': 'PyYAML no está disponible. Instala con: pip install PyYAML'
            }), 500
        
        # Cargar presets existentes
        presets_dir = PRESETS_DIR
        preset_files = glob.glob(os.path.join(presets_dir, "*.yaml"))
        
        presets = []
        for preset_file in preset_files:
            # Note: models_recommender.yaml is now in models/ subdirectory, so won't appear here
                
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    preset_data = yaml.safe_load(f)
                    preset_info = {
                        'file': os.path.basename(preset_file),
                        'name': preset_data.get('name', 'Sin nombre'),
                        'description': preset_data.get('description', 'Sin descripción'),
                        'lm_compat': preset_data.get('lm_compat', {}),
                        'config': preset_data.get('config', {}),
                        'batch_size': preset_data.get('batch_size', 1),
                        'timeout': preset_data.get('timeout', 30)
                    }
                    presets.append(preset_info)
            except Exception as e:
                logging.error(f"Error cargando preset {preset_file}: {e}")
                continue
        
        # Cargar recomendaciones de modelos
        models_recommender_file = os.path.join(presets_dir, "models", "models_recommender.yaml")
        models_recommendations = {}
        
        if os.path.exists(models_recommender_file):
            try:
                with open(models_recommender_file, 'r', encoding='utf-8') as f:
                    models_data = yaml.safe_load(f)
                    models_recommendations = models_data.get('presets', {})
            except Exception as e:
                logging.error(f"Error cargando recomendaciones de modelos: {e}")
        
        # Combinar presets con sus recomendaciones
        for preset in presets:
            preset_name = preset['name']
            if preset_name in models_recommendations:
                preset['models_recommended'] = models_recommendations[preset_name].get('models_recommended', [])
                preset['models_description'] = models_recommendations[preset_name].get('description', '')
            else:
                preset['models_recommended'] = []
                preset['models_description'] = ''
        
        return jsonify({
            'ok': True,
            'presets': presets,
            'total_presets': len(presets),
            'models_recommendations_available': len(models_recommendations) > 0
        })
        
    except Exception as e:
        logging.error(f"Error en /models-presets: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/models-presets/<preset_name>/models', methods=['GET'])
def get_preset_models(preset_name):
    """Obtiene recomendaciones de modelos para un preset específico"""
    try:
        if not YAML_AVAILABLE:
            return jsonify({
                'ok': False,
                'error': 'PyYAML no está disponible. Instala con: pip install PyYAML'
            }), 500
        
        models_recommender_file = os.path.join(PRESETS_DIR, "models", "models_recommender.yaml")
        
        if not os.path.exists(models_recommender_file):
            return jsonify({
                'ok': False,
                'error': 'Archivo de recomendaciones de modelos no encontrado'
            }), 404
        
        with open(models_recommender_file, 'r', encoding='utf-8') as f:
            models_data = yaml.safe_load(f)
            
        presets_data = models_data.get('presets', {})
        
        if preset_name not in presets_data:
            return jsonify({
                'ok': False,
                'error': f'No se encontraron recomendaciones para el preset "{preset_name}"'
            }), 404
        
        preset_models = presets_data[preset_name]
        
        return jsonify({
            'ok': True,
            'preset_name': preset_name,
            'description': preset_models.get('description', ''),
            'models': preset_models.get('models_recommended', []),
            'total_models': len(preset_models.get('models_recommended', []))
        })
        
    except Exception as e:
        logging.error(f"Error obteniendo modelos para preset {preset_name}: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/models-presets/save-models', methods=['POST'])
def save_models_recommendations():
    """Guarda las recomendaciones de modelos para un preset"""
    try:
        data = request.get_json()
        preset_name = data.get('preset_name')
        description = data.get('description', '')
        models = data.get('models', [])
        
        if not preset_name:
            return jsonify({
                'ok': False,
                'error': 'Nombre del preset requerido'
            }), 400
        
        models_recommender_file = os.path.join(PRESETS_DIR, "models", "models_recommender.yaml")
        
        # Cargar archivo existente o crear estructura inicial
        if os.path.exists(models_recommender_file):
            with open(models_recommender_file, 'r', encoding='utf-8') as f:
                models_data = yaml.safe_load(f) or {}
        else:
            models_data = {'presets': {}}
        
        # Asegurar que existe la estructura de presets
        if 'presets' not in models_data:
            models_data['presets'] = {}
        
        # Actualizar los modelos para el preset
        models_data['presets'][preset_name] = {
            'description': description,
            'models_recommended': models
        }
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(models_recommender_file), exist_ok=True)
        
        # Guardar archivo
        with open(models_recommender_file, 'w', encoding='utf-8') as f:
            yaml.dump(models_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return jsonify({
            'ok': True,
            'message': f'Modelos para "{preset_name}" guardados exitosamente',
            'models_count': len(models)
        })
        
    except Exception as e:
        logging.error(f"Error guardando modelos: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/presets/save', methods=['POST'])
def save_preset_config():
    """Guarda la configuración de un preset YAML"""
    try:
        data = request.get_json()
        file_name = data.get('fileName')
        
        if not file_name:
            return jsonify({
                'ok': False,
                'error': 'Nombre de archivo requerido'
            }), 400
        
        preset_file_path = os.path.join(PRESETS_DIR, file_name)
        
        # Cargar archivo existente
        if os.path.exists(preset_file_path):
            with open(preset_file_path, 'r', encoding='utf-8') as f:
                preset_data = yaml.safe_load(f) or {}
        else:
            preset_data = {}
        
        # Actualizar datos
        preset_data.update({
            'name': data.get('name'),
            'description': data.get('description'),
            'batch_size': data.get('batch_size'),
            'timeout': data.get('timeout'),
            'lm_compat': data.get('lm_compat')
        })
        
        # Guardar archivo
        with open(preset_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(preset_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return jsonify({
            'ok': True,
            'message': f'Preset "{data.get("name")}" guardado exitosamente'
        })
        
    except Exception as e:
        logging.error(f"Error guardando preset: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ========== ENDPOINTS PARA GESTIÓN DE PROMPTS ==========

@api_bp.route('/prompts', methods=['GET'])
def get_prompts():
    """Obtiene la lista de todos los prompts disponibles"""
    if not YAML_AVAILABLE:
        return jsonify({
            'ok': False,
            'error': 'PyYAML no está instalado'
        }), 500
    
    try:
        prompts = []
        
        if not os.path.exists(PROMPTS_DIR):
            os.makedirs(PROMPTS_DIR, exist_ok=True)
        
        # Buscar archivos YAML en el directorio de prompts
        prompt_files = glob.glob(os.path.join(PROMPTS_DIR, "*.yaml")) + \
                      glob.glob(os.path.join(PROMPTS_DIR, "*.yml"))
        
        for file_path in prompt_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    prompt_data = yaml.safe_load(f) or {}
                
                file_name = os.path.basename(file_path)
                
                # Extraer información del prompt
                prompt_info = {
                    'file': file_name,
                    'name': prompt_data.get('name', file_name.replace('.yaml', '').replace('.yml', '')),
                    'description': prompt_data.get('description', ''),
                    'type': prompt_data.get('type', 'completions'),
                    'instructions': prompt_data.get('LM_INSTRUCTIONS', '')
                }
                
                prompts.append(prompt_info)
                
            except Exception as e:
                logging.error(f"Error leyendo prompt {file_path}: {e}")
                continue
        
        # Ordenar por nombre de archivo
        prompts.sort(key=lambda x: x['file'])
        
        return jsonify({
            'ok': True,
            'prompts': prompts,
            'count': len(prompts)
        })
        
    except Exception as e:
        logging.error(f"Error cargando prompts: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/prompts/save', methods=['POST'])
def save_prompt():
    """Guarda las modificaciones de un prompt"""
    if not YAML_AVAILABLE:
        return jsonify({
            'ok': False,
            'error': 'PyYAML no está instalado'
        }), 500
    
    try:
        data = request.get_json()
        file_name = data.get('fileName')
        
        if not file_name:
            return jsonify({
                'ok': False,
                'error': 'Nombre de archivo requerido'
            }), 400
        
        prompt_file_path = os.path.join(PROMPTS_DIR, file_name)
        
        # Cargar archivo existente
        if os.path.exists(prompt_file_path):
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                prompt_data = yaml.safe_load(f) or {}
        else:
            prompt_data = {}
        
        # Actualizar datos del prompt
        prompt_data.update({
            'name': data.get('name'),
            'description': data.get('description'),
            'type': data.get('type', 'completions'),
            'LM_INSTRUCTIONS': data.get('instructions', '')
        })
        
        # Guardar archivo
        with open(prompt_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(prompt_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return jsonify({
            'ok': True,
            'message': f'Prompt "{data.get("name")}" guardado exitosamente'
        })
        
    except Exception as e:
        logging.error(f"Error guardando prompt: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/prompts/create', methods=['POST'])
def create_prompt():
    """Crea un nuevo archivo de prompt"""
    if not YAML_AVAILABLE:
        return jsonify({
            'ok': False,
            'error': 'PyYAML no está instalado'
        }), 500
    
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({
                'ok': False,
                'error': 'Nombre del prompt requerido'
            }), 400
        
        # Crear nombre de archivo seguro
        import re
        safe_name = re.sub(r'[^\w\-_.]', '_', name.lower())
        file_name = f"{safe_name}.yaml"
        
        # Verificar que no exista
        prompt_file_path = os.path.join(PROMPTS_DIR, file_name)
        if os.path.exists(prompt_file_path):
            return jsonify({
                'ok': False,
                'error': f'Ya existe un prompt con el archivo "{file_name}"'
            }), 400
        
        # Crear directorio si no existe
        os.makedirs(PROMPTS_DIR, exist_ok=True)
        
        # Estructura básica del prompt
        prompt_data = {
            'name': name,
            'description': data.get('description', ''),
            'type': data.get('type', 'completions'),
            'LM_INSTRUCTIONS': 'Eres un traductor experto de inglés a español especializado en terminología militar y de aviación.\n\nTu tarea es traducir con precisión textos relacionados con DCS World (Digital Combat Simulator), manteniendo:\n- Terminología técnica precisa\n- Nombres propios sin traducir\n- Formato original del texto\n\nTraducir el siguiente texto:'
        }
        
        # Guardar archivo
        with open(prompt_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(prompt_data, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return jsonify({
            'ok': True,
            'message': f'Prompt "{name}" creado exitosamente',
            'fileName': file_name
        })
        
    except Exception as e:
        logging.error(f"Error creando prompt: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/prompts/<path:file_name>', methods=['DELETE'])
def delete_prompt(file_name):
    """Elimina un archivo de prompt"""
    try:
        prompt_file_path = os.path.join(PROMPTS_DIR, file_name)
        
        if not os.path.exists(prompt_file_path):
            return jsonify({
                'ok': False,
                'error': 'El archivo no existe'
            }), 404
        
        # Verificar que el archivo esté en el directorio correcto
        if not os.path.commonpath([prompt_file_path, PROMPTS_DIR]) == PROMPTS_DIR:
            return jsonify({
                'ok': False,
                'error': 'Ruta de archivo no válida'
            }), 400
        
        os.remove(prompt_file_path)
        
        return jsonify({
            'ok': True,
            'message': f'Prompt "{file_name}" eliminado exitosamente'
        })
        
    except Exception as e:
        logging.error(f"Error eliminando prompt: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ========== ENDPOINTS PARA VISUALIZACIÓN DE ARCHIVOS LUA ==========

@api_bp.route('/campaigns/<campaign_name>/missions/<mission_name>/lua/view', methods=['GET'])
def view_lua_files(campaign_name, mission_name):
    """Obtiene el contenido de archivos LUA (original y traducido) para visualización"""
    try:
        from config.settings import TRANSLATIONS_DIR
        
        # Construir rutas esperadas
        campaign_dir = os.path.join(TRANSLATIONS_DIR, campaign_name)
        mission_dir = os.path.join(campaign_dir, mission_name)
        
        if not os.path.exists(mission_dir):
            return jsonify({
                'ok': False,
                'error': f'Directorio de misión no encontrado: {mission_dir}'
            }), 404
        
        result = {
            'ok': True,
            'campaign_name': campaign_name,
            'mission_name': mission_name,
            'files': {
                'original': None,
                'translated': None,
                'extracted': None
            },

        }
        
        # Buscar archivo LUA original extraído
        extracted_dir = os.path.join(mission_dir, 'extracted')

        
        def detect_language(text):
            """Detectar si el texto está en español o inglés"""
            if not text:
                return 'unknown'
            
            # Palabras indicadoras de español (comunes en contextos militares/aviación)
            spanish_indicators = [
                'español', 'castellano', 'misión', 'avión', 'vuelo', 'piloto', 'aeronave',
                'traducido', 'aterrizaje', 'despegue', 'navegación', 'combustible',
                'objetivo', 'enemigo', 'aliado', 'escuadrón', 'formación', 'maniobra',
                'radar', 'comunicación', 'frecuencia', 'canal', 'coordenadas',
                'altitud', 'velocidad', 'dirección', 'rumbo', 'distancia',
                'munición', 'armamento', 'defensa', 'ataque', 'reconocimiento',
                'patrulla', 'interceptación', 'cobertura', 'apoyo', 'evacuación',
                'reabastecimiento', 'mantenimiento', 'inspección', 'reparación'
            ]
            
            # Palabras indicadoras de inglés (comunes en contextos militares/aviación)
            english_indicators = [
                'mission', 'aircraft', 'flight', 'pilot', 'airplane', 'plane',
                'landing', 'takeoff', 'navigation', 'fuel', 'target', 'enemy',
                'allied', 'squadron', 'formation', 'maneuver', 'radar',
                'communication', 'frequency', 'channel', 'coordinates',
                'altitude', 'speed', 'heading', 'bearing', 'distance',
                'ammunition', 'weapon', 'defense', 'attack', 'reconnaissance',
                'patrol', 'intercept', 'coverage', 'support', 'evacuation',
                'refuel', 'maintenance', 'inspection', 'repair'
            ]
            
            text_lower = text.lower()
            spanish_count = sum(1 for word in spanish_indicators if word in text_lower)
            english_count = sum(1 for word in english_indicators if word in text_lower)
            
            # También buscar patrones de texto característicos
            if any(phrase in text_lower for phrase in ['sí, tengo', 'no, no lo he hecho', 'bienvenido']):
                spanish_count += 3
            
            if any(phrase in text_lower for phrase in ['yes, i have', 'no, i have not', 'welcome']):
                english_count += 3
            
            if spanish_count > english_count and spanish_count > 2:
                return 'spanish'
            elif english_count > spanish_count and english_count > 2:
                return 'english'
            else:
                return 'unknown'
        
        if os.path.exists(extracted_dir):
            logging.info(f"Buscando archivo original en: {extracted_dir}")
            
            # Buscar archivos dictionary con múltiples patrones y extensiones
            lua_patterns = [
                '**/dictionary',           # Sin extensión (más común)
                '**/dictionary.lua',       # Con extensión .lua
                '**/l10n/DEFAULT/dictionary',
                '**/l10n/DEFAULT/dictionary.lua', 
                '**/l10n/*/dictionary',
                '**/l10n/*/dictionary.lua',
                '**/*.lua',
                'dictionary',
                'dictionary.lua',
                'l10n/DEFAULT/dictionary',
                'l10n/DEFAULT/dictionary.lua'
            ]
            
            dictionary_files = []
            for pattern in lua_patterns:
                files = glob.glob(os.path.join(extracted_dir, pattern), recursive=True)

                if files:
                    logging.info(f"Patrón '{pattern}' encontró: {files}")
                dictionary_files.extend(files)
            

            
            # Filtrar archivos que realmente existen y priorizar dictionary
            valid_files = [f for f in dictionary_files if os.path.isfile(f)]
            logging.info(f"Archivos válidos encontrados: {valid_files}")
            
            # Priorizar archivos dictionary (con o sin extensión) sobre otros archivos
            priority_files = [f for f in valid_files if os.path.basename(f) in ['dictionary', 'dictionary.lua']]
            if priority_files:
                # Priorizar dictionary sin extensión sobre dictionary.lua
                no_ext_files = [f for f in priority_files if os.path.basename(f) == 'dictionary']
                original_path = no_ext_files[0] if no_ext_files else priority_files[0]
                logging.info(f"Archivo original seleccionado: {original_path}")
            elif valid_files:
                original_path = valid_files[0]
                logging.info(f"Archivo válido seleccionado: {original_path}")
            else:
                original_path = None
                logging.warning("No se encontró archivo original")
            
            if original_path:
                logging.info(f"Intentando leer archivo original: {original_path}")
                try:
                    # Verificar que el archivo existe
                    if not os.path.exists(original_path):
                        logging.error(f"El archivo original no existe: {original_path}")
                        original_path = None
                    else:
                        # Intentar múltiples codificaciones
                        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
                        original_content = None
                        used_encoding = None
                        
                        for encoding in encodings:
                            try:
                                logging.info(f"Intentando codificación: {encoding}")
                                with open(original_path, 'r', encoding=encoding) as f:
                                    original_content = f.read()
                                used_encoding = encoding
                                logging.info(f"Archivo leído exitosamente con codificación: {encoding}")
                                break
                            except UnicodeDecodeError as ude:
                                logging.warning(f"Error de codificación {encoding}: {ude}")
                                continue
                        
                        if original_content is not None:
                            # Detectar idioma del archivo original
                            detected_language = detect_language(original_content)
                            
                            result['files']['original'] = {
                                'path': original_path,
                                'content': original_content,
                                'size': len(original_content),
                                'lines': len(original_content.splitlines()),
                                'encoding': used_encoding,
                                'detected_language': detected_language,
                                'is_already_translated': detected_language == 'spanish'
                            }
                            logging.info(f"Archivo original cargado correctamente: {len(original_content)} chars, {len(original_content.splitlines())} lines, idioma: {detected_language}")
                        else:
                            logging.warning(f"No se pudo leer el archivo original con ninguna codificación: {original_path}")
                    
                except Exception as e:
                    logging.error(f"Error leyendo archivo original {original_path}: {e}")
                    import traceback
                    logging.error(f"Traceback: {traceback.format_exc()}")
        
        # Buscar archivo LUA traducido
        out_lua_dir = os.path.join(mission_dir, 'out_lua')
        if os.path.exists(out_lua_dir):
            translated_files = glob.glob(os.path.join(out_lua_dir, '*.translated.lua'))
            
            if translated_files:
                translated_path = translated_files[0]
                try:
                    with open(translated_path, 'r', encoding='utf-8') as f:
                        translated_content = f.read()
                    
                    # Detectar idioma del archivo traducido
                    translated_detected_language = detect_language(translated_content)
                    
                    result['files']['translated'] = {
                        'path': translated_path,
                        'content': translated_content,
                        'size': len(translated_content),
                        'lines': len(translated_content.splitlines()),
                        'encoding': 'utf-8',
                        'detected_language': translated_detected_language
                    }
                    
                except Exception as e:
                    logging.warning(f"Error leyendo archivo traducido {translated_path}: {e}")
        
        # Los archivos originales ahora se buscan correctamente en la carpeta extracted
        # Ya no necesitamos mostrar archivos placeholders por separado
        
        # Verificar si encontramos al menos un archivo
        if not any(result['files'].values()):
            return jsonify({
                'ok': False,
                'error': 'No se encontraron archivos LUA para esta misión'
            }), 404
        
        # Añadir advertencias si el archivo original ya está en español
        result['warnings'] = []
        if (result['files']['original'] and 
            result['files']['original'].get('is_already_translated', False)):
            result['warnings'].append({
                'type': 'already_translated',
                'message': '⚠️ ADVERTENCIA: El archivo original parece estar ya traducido al español. No es necesario volver a traducir esta misión.',
                'severity': 'warning'
            })
        
        # Si ambos archivos están en español, advertir sobre posible retradución
        if (result['files']['original'] and result['files']['translated'] and
            result['files']['original'].get('detected_language') == 'spanish' and
            result['files']['translated'].get('detected_language') == 'spanish'):
            result['warnings'].append({
                'type': 'retranslation_detected',
                'message': '🔄 ATENCIÓN: Tanto el archivo original como el traducido están en español. Esto sugiere que se ha retraducido una misión ya traducida.',
                'severity': 'error'
            })
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error obteniendo archivos LUA: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/campaigns/<campaign_name>/missions/<mission_name>/lua/compare', methods=['GET'])
def compare_lua_files(campaign_name, mission_name):
    """Compara archivos LUA original vs traducido y proporciona estadísticas"""
    try:
        from config.settings import TRANSLATIONS_DIR
        import re
        
        # Obtener archivos usando el endpoint anterior
        response_data = view_lua_files(campaign_name, mission_name)
        if isinstance(response_data, tuple):  # Error response
            return response_data
        
        files_data = response_data.get_json() if hasattr(response_data, 'get_json') else response_data
        
        if not files_data['ok']:
            return jsonify(files_data), 404
        
        original = files_data['files']['original']
        translated = files_data['files']['translated']
        
        if not original or not translated:
            return jsonify({
                'ok': False,
                'error': 'Se necesitan tanto el archivo original como el traducido para comparar'
            }), 400
        
        # Análisis de contenido
        original_content = original['content']
        translated_content = translated['content']
        
        # Regex para encontrar entradas de diccionario
        dict_entry_pattern = r'\["([^"]+)"\]\s*=\s*"([^"]*)"'
        
        original_entries = dict(re.findall(dict_entry_pattern, original_content))
        translated_entries = dict(re.findall(dict_entry_pattern, translated_content))
        
        # Estadísticas de comparación
        total_original = len(original_entries)
        total_translated = len(translated_entries)
        
        # Entradas comunes (claves que existen en ambos)
        common_keys = set(original_entries.keys()) & set(translated_entries.keys())
        
        # Entradas traducidas (donde el valor cambió)
        actually_translated = 0
        unchanged_entries = 0
        
        for key in common_keys:
            if original_entries[key] != translated_entries[key]:
                actually_translated += 1
            else:
                unchanged_entries += 1
        
        # Solo en original (perdidas)
        only_in_original = set(original_entries.keys()) - set(translated_entries.keys())
        
        # Solo en traducido (nuevas)
        only_in_translated = set(translated_entries.keys()) - set(original_entries.keys())
        
        comparison_result = {
            'ok': True,
            'campaign_name': campaign_name,
            'mission_name': mission_name,
            'statistics': {
                'original_entries': total_original,
                'translated_entries': total_translated,
                'common_entries': len(common_keys),
                'actually_translated': actually_translated,
                'unchanged_entries': unchanged_entries,
                'only_in_original': len(only_in_original),
                'only_in_translated': len(only_in_translated),
                'translation_rate': round((actually_translated / total_original * 100) if total_original > 0 else 0, 2)
            },
            'samples': {
                'translated_samples': [],
                'unchanged_samples': [],
                'missing_samples': []
            }
        }
        
        # Muestras de traducciones (primeras 5 de cada tipo)
        translated_count = 0
        unchanged_count = 0
        
        for key in list(common_keys)[:20]:  # Limitar para no sobrecargar
            if original_entries[key] != translated_entries[key] and translated_count < 5:
                comparison_result['samples']['translated_samples'].append({
                    'key': key,
                    'original': original_entries[key],
                    'translated': translated_entries[key]
                })
                translated_count += 1
            elif original_entries[key] == translated_entries[key] and unchanged_count < 3:
                comparison_result['samples']['unchanged_samples'].append({
                    'key': key,
                    'value': original_entries[key]
                })
                unchanged_count += 1
        
        # Muestras de entradas perdidas
        for key in list(only_in_original)[:3]:
            comparison_result['samples']['missing_samples'].append({
                'key': key,
                'original_value': original_entries[key]
            })
        
        return jsonify(comparison_result)
        
    except Exception as e:
        logging.error(f"Error comparando archivos LUA: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@api_bp.route('/campaigns/<campaign_name>/missions/<mission_name>/lua/download', methods=['GET'])
def download_lua_file(campaign_name, mission_name):
    """Descarga un archivo LUA específico"""
    try:
        from flask import send_file
        file_type = request.args.get('type', 'translated')  # 'original', 'translated', 'placeholders'
        
        # Obtener la información de archivos
        response_data = view_lua_files(campaign_name, mission_name)
        if isinstance(response_data, tuple):  # Error response
            return response_data
        
        files_data = response_data.get_json() if hasattr(response_data, 'get_json') else response_data
        
        if not files_data['ok']:
            return jsonify(files_data), 404
        
        # Mapear tipos a claves de archivo
        type_mapping = {
            'original': 'original',
            'translated': 'translated', 
            'placeholders': 'extracted'
        }
        
        if file_type not in type_mapping:
            return jsonify({
                'ok': False,
                'error': f'Tipo de archivo no válido: {file_type}'
            }), 400
        
        file_key = type_mapping[file_type]
        file_info = files_data['files'].get(file_key)
        
        if not file_info:
            return jsonify({
                'ok': False,
                'error': f'Archivo {file_type} no encontrado para esta misión'
            }), 404
        
        file_path = file_info['path']
        
        if not os.path.exists(file_path):
            return jsonify({
                'ok': False,
                'error': f'Archivo no existe: {file_path}'
            }), 404
        
        # Generar nombre de descarga
        base_name = f"{campaign_name}_{mission_name}_{file_type}.lua"
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=base_name,
            mimetype='text/plain'
        )
        
    except Exception as e:
        logging.error(f"Error descargando archivo LUA: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


# ========================= ENDPOINTS DE PERFILES =========================

def _validate_profile_model(profile_name):
    """
    Valida si el modelo configurado en un perfil está disponible en LM Studio
    
    Returns:
        dict: Información del warning si hay problema, None si todo está bien
    """
    try:
        from app.services.profile_service import ProfileService
        profile_service = ProfileService()
        
        # Obtener datos del perfil
        profile_data = profile_service.get_profile(profile_name)
        if not profile_data:
            return None
            
        model_config = profile_data.get('model_config', {})
        configured_model = model_config.get('lm_model', '').strip()
        lm_url = model_config.get('lm_url', LM_CONFIG['DEFAULT_URL'])
        
        # Si no hay modelo configurado, no hay problema
        if not configured_model or configured_model == 'Seleccionar modelo...':
            return None
            
        # Verificar si el modelo está disponible en LM Studio
        try:
            lm_service = LMStudioService(base_url=lm_url)
            available_models = lm_service.get_loaded_models()
            
            # Crear lista de IDs y nombres de modelos disponibles
            available_ids = []
            available_names = []
            
            for model in available_models:
                if isinstance(model, dict):
                    model_id = model.get('id', '')
                    model_name = model.get('name', '')
                    available_ids.append(model_id)
                    available_names.append(model_name)
                    # También agregar nombres cortos
                    if model_id:
                        available_names.append(model_id.split('/')[-1])
                    if model_name:
                        available_names.append(model_name.split('/')[-1])
            
            # Verificar si el modelo configurado está disponible
            model_available = (
                configured_model in available_ids or 
                configured_model in available_names or
                any(configured_model in name for name in available_names)
            )
            
            if not model_available and available_models:
                # Modelo no disponible, crear warning
                return {
                    'type': 'model_not_available',
                    'title': 'Modelo no disponible',
                    'message': f'El modelo "{configured_model}" del perfil "{profile_name}" no está cargado en LM Studio.',
                    'details': {
                        'configured_model': configured_model,
                        'available_models': [
                            model.get('name', model.get('id', 'Modelo')) 
                            for model in available_models[:3]  # Solo mostrar los primeros 3
                        ],
                        'lm_studio_url': lm_url
                    },
                    'suggestions': [
                        f'Carga el modelo "{configured_model}" en LM Studio',
                        'O selecciona uno de los modelos disponibles',
                        'O actualiza el perfil con un modelo diferente'
                    ]
                }
            elif not available_models:
                # LM Studio sin modelos
                return {
                    'type': 'lm_studio_no_models',
                    'title': 'LM Studio sin modelos',
                    'message': 'No hay modelos cargados en LM Studio.',
                    'details': {
                        'configured_model': configured_model,
                        'lm_studio_url': lm_url
                    },
                    'suggestions': [
                        'Carga un modelo en LM Studio',
                        'Verifica que LM Studio esté ejecutándose',
                        f'Verifica la conexión a {lm_url}'
                    ]
                }
                
        except Exception as e:
            # Error conectando con LM Studio
            return {
                'type': 'lm_studio_connection_error',
                'title': 'Error conectando con LM Studio',
                'message': f'No se pudo verificar la disponibilidad del modelo "{configured_model}".',
                'details': {
                    'configured_model': configured_model,
                    'lm_studio_url': lm_url,
                    'error': str(e)
                },
                'suggestions': [
                    'Verifica que LM Studio esté ejecutándose',
                    f'Verifica la conexión a {lm_url}',
                    'El perfil se cargó pero no se pudo validar el modelo'
                ]
            }
            
        # Si llegamos aquí, el modelo está disponible
        return None
        
    except Exception as e:
        logging.error(f"Error validando modelo del perfil {profile_name}: {e}")
        return {
            'type': 'validation_error',
            'title': 'Error de validación',
            'message': f'Error validando el modelo del perfil "{profile_name}": {str(e)}',
            'suggestions': ['El perfil se cargó pero no se pudo validar el modelo']
        }

@api_bp.route('/profiles', methods=['GET'])
def list_profiles():
    """Lista todos los perfiles disponibles"""
    try:
        from app.services.profile_service import ProfileService
        profile_service = ProfileService()
        
        # Solo perfiles de usuario por defecto (sin predefinidos)
        user_only = request.args.get('user_only', 'true').lower() == 'true'
        
        profiles = profile_service.list_profiles(user_only=user_only)
        
        return jsonify({
            'ok': True,
            'profiles': profiles
        })
        
    except Exception as e:
        logging.error(f"Error listando perfiles: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/profiles', methods=['POST'])
def create_profile():
    """Crea un nuevo perfil con la configuración actual"""
    try:
        from app.services.profile_service import ProfileService
        from app.services.user_config import UserConfigService
        
        profile_service = ProfileService()
        user_config_service = UserConfigService()
        
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        # Obtener configuraciones del frontend
        general_config = data.get('general_config', {})
        model_config = data.get('model_config', {})
        
        if not name:
            return jsonify({
                'ok': False,
                'error': 'El nombre del perfil es requerido'
            }), 400
        
        # Verificar si ya existe
        if profile_service.profile_exists(name):
            return jsonify({
                'ok': False,
                'error': f'Ya existe un perfil con el nombre "{name}"'
            }), 409
        
        # Crear configuración completa incluyendo el preset
        current_config = user_config_service.load_config()
        
        # Actualizar con la configuración enviada desde el frontend
        if general_config:
            current_config.update(general_config)
        
        if model_config:
            # Mapear campos del modelo
            model_mapping = {
                'userLmModel': 'lm_model',
                'presetList': 'preset'  # ¡Aquí es donde se incluye el preset!
            }
            
            for frontend_key, config_key in model_mapping.items():
                if frontend_key in model_config and model_config[frontend_key]:
                    current_config[config_key] = model_config[frontend_key]
            
            # Otros campos del modelo
            model_fields = ['arg_config', 'arg_compat', 'arg_batch', 'arg_timeout',
                          'api_temperature', 'api_top_p', 'api_top_k', 'api_max_tokens',
                          'api_repetition_penalty', 'api_presence_penalty']
            
            for field in model_fields:
                if field in model_config and model_config[field] is not None:
                    current_config[field] = model_config[field]
        
        # Guardar la configuración actualizada antes de crear el perfil
        user_config_service.save_config(current_config)
        
        # Crear el perfil con la configuración completa
        success = profile_service.create_profile(name, description)
        
        if success:
            return jsonify({
                'ok': True,
                'message': f'Perfil "{name}" creado exitosamente (incluyendo preset: {current_config.get("preset", "ninguno")})'
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Error creando el perfil'
            }), 500
            
    except Exception as e:
        logging.error(f"Error creando perfil: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/profiles/<profile_name>', methods=['GET'])
def get_profile(profile_name):
    """Obtiene los datos de un perfil específico"""
    try:
        from app.services.profile_service import ProfileService
        profile_service = ProfileService()
        
        profile_data = profile_service.get_profile(profile_name)
        
        if not profile_data:
            return jsonify({
                'ok': False,
                'error': f'Perfil "{profile_name}" no encontrado'
            }), 404
        
        return jsonify({
            'ok': True,
            'profile': profile_data
        })
        
    except Exception as e:
        logging.error(f"Error obteniendo perfil: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/profiles/<profile_name>/load', methods=['POST'])
def load_profile(profile_name):
    """Carga un perfil y aplica su configuración con validación del modelo"""
    try:
        from app.services.profile_service import ProfileService
        profile_service = ProfileService()
        
        data = request.get_json() or {}
        apply_general = data.get('apply_general', True)
        apply_model = data.get('apply_model', True)
        
        success = profile_service.load_profile(
            profile_name, 
            apply_general=apply_general, 
            apply_model=apply_model
        )
        
        if success:
            # Validar si el modelo del perfil está disponible en LM Studio
            model_warning = None
            if apply_model:
                model_warning = _validate_profile_model(profile_name)
            
            response_data = {
                'ok': True,
                'message': f'Perfil "{profile_name}" cargado exitosamente'
            }
            
            if model_warning:
                response_data['model_warning'] = model_warning
            
            return jsonify(response_data)
        else:
            return jsonify({
                'ok': False,
                'error': f'Error cargando el perfil "{profile_name}"'
            }), 500
            
    except Exception as e:
        logging.error(f"Error cargando perfil: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/profiles/<profile_name>', methods=['PUT'])
def update_profile(profile_name):
    """Actualiza un perfil con la configuración actual"""
    try:
        from app.services.profile_service import ProfileService
        profile_service = ProfileService()
        
        data = request.get_json() or {}
        description = data.get('description')
        
        success = profile_service.update_profile(profile_name, description)
        
        if success:
            return jsonify({
                'ok': True,
                'message': f'Perfil "{profile_name}" actualizado exitosamente'
            })
        else:
            return jsonify({
                'ok': False,
                'error': f'Error actualizando el perfil "{profile_name}"'
            }), 500
            
    except Exception as e:
        logging.error(f"Error actualizando perfil: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/profiles/<profile_name>', methods=['DELETE'])
def delete_profile(profile_name):
    """Elimina un perfil"""
    try:
        from app.services.profile_service import ProfileService
        profile_service = ProfileService()
        
        if not profile_service.profile_exists(profile_name):
            return jsonify({
                'ok': False,
                'error': f'Perfil "{profile_name}" no encontrado'
            }), 404
        
        success = profile_service.delete_profile(profile_name)
        
        if success:
            return jsonify({
                'ok': True,
                'message': f'Perfil "{profile_name}" eliminado exitosamente'
            })
        else:
            return jsonify({
                'ok': False,
                'error': f'Error eliminando el perfil "{profile_name}"'
            }), 500
            
    except Exception as e:
        logging.error(f"Error eliminando perfil: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@api_bp.route('/profiles/<profile_name>/validate_model', methods=['GET'])
def validate_profile_model(profile_name):
    """Valida si el modelo de un perfil está disponible en LM Studio"""
    try:
        model_warning = _validate_profile_model(profile_name)
        
        return jsonify({
            'ok': True,
            'profile_name': profile_name,
            'model_valid': model_warning is None,
            'warning': model_warning
        })
        
    except Exception as e:
        logging.error(f"Error validando modelo del perfil {profile_name}: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


# ENDPOINT DESHABILITADO - Solo perfiles de usuario
# @api_bp.route('/profiles/defaults', methods=['POST'])
# def create_default_profiles():
#     """Crea los perfiles por defecto si no existen"""
#     try:
#         from app.services.profile_service import ProfileService
#         profile_service = ProfileService()
#         
#         success = profile_service.create_default_profiles()
#         
#         if success:
#             return jsonify({
#                 'ok': True,
#                 'message': 'Perfiles por defecto creados exitosamente'
#             })
#         else:
#             return jsonify({
#                 'ok': False,
#                 'error': 'Error creando perfiles por defecto'
#             }), 500
#             
#     except Exception as e:
#         logging.error(f"Error creando perfiles por defecto: {e}")
#         return jsonify({
#             'ok': False,
#             'error': str(e)
#         }), 500

@api_bp.route('/check_translated_dict', methods=['POST'])
def check_translated_dict():
    """Verifica qué misiones tienen archivos *.translated.lua en out_lua/"""
    try:
        data = request.json
        campaign = data.get('campaign')
        missions = data.get('missions', [])
        
        logging.info(f"🔍 Verificando archivos traducidos para campaña: {campaign}, misiones: {missions}")
        
        if not campaign:
            return jsonify({
                'ok': False,
                'error': 'Nombre de campaña requerido'
            }), 400
            
        if not missions:
            return jsonify({
                'ok': False,
                'error': 'Lista de misiones requerida'
            }), 400
        
        # Directorio base de traducciones
        traducciones_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'traducciones')
        logging.info(f"🔍 Directorio base de traducciones: {traducciones_dir}")
        
        results = {}
        
        for mission_name in missions:
            # Construir ruta al directorio out_lua de la misión
            mission_out_lua_dir = os.path.join(traducciones_dir, campaign, mission_name.replace('.miz', ''), 'out_lua')
            
            # Logging para debug
            logging.info(f"🔍 Verificando misión: {mission_name}")
            logging.info(f"🔍 Ruta esperada: {mission_out_lua_dir}")
            
            # Verificar si existe algún archivo *.translated.lua
            translated_files = []
            if os.path.exists(mission_out_lua_dir):
                pattern = os.path.join(mission_out_lua_dir, '*.translated.lua')
                translated_files = glob.glob(pattern)
                all_files = os.listdir(mission_out_lua_dir) if os.path.exists(mission_out_lua_dir) else []
                logging.info(f"🔍 Archivos encontrados: {all_files}")
                logging.info(f"🔍 Archivos *.translated.lua: {translated_files}")
            else:
                logging.info(f"🔍 Directorio no existe: {mission_out_lua_dir}")
            
            # La misión se considera traducida si tiene al menos un archivo *.translated.lua
            has_translated = len(translated_files) > 0
            results[mission_name] = has_translated
            logging.info(f"🔍 Resultado para {mission_name}: {has_translated}")
            
        logging.info(f"🔍 Resultados finales: {results}")
        return jsonify({
            'ok': True,
            'results': results
        })
        
    except Exception as e:
        logging.error(f"❌ Error verificando archivos traducidos: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500