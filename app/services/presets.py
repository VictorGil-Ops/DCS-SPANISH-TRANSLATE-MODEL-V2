#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio para manejar presets de configuración
Soporta tanto archivos JSON (presets de usuario) como YAML (presets predefinidos)
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from config.settings import PRESETS_DIR

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None


class PresetService:
    """Servicio para gestionar presets de configuración"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.presets_dir = PRESETS_DIR
        
    def save_preset(self, name: str, config: Dict) -> bool:
        """Guarda un preset de configuración"""
        try:
            preset_data = {
                'name': name,
                'created': datetime.now().isoformat(),
                'version': '1.0',
                'config': config
            }
            
            filename = self._sanitize_filename(name) + '.json'
            filepath = os.path.join(self.presets_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Preset saved: {name} -> {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving preset {name}: {e}")
            return False
    
    def load_preset(self, name: str) -> Optional[Dict]:
        """Carga un preset por nombre (soporta JSON y YAML)"""
        try:
            # Primero buscar por filename exacto
            preset_info = self.get_preset_by_name(name)
            if not preset_info:
                # Fallback: intentar cargar como JSON (compatibilidad)
                filename = self._sanitize_filename(name) + '.json'
                filepath = os.path.join(self.presets_dir, filename)
                
                if not os.path.exists(filepath):
                    self.logger.warning(f"Preset not found: {name}")
                    return None
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    preset_data = json.load(f)
                return preset_data.get('config', {})
            
            filepath = os.path.join(self.presets_dir, preset_info['filename'])
            
            if not os.path.exists(filepath):
                return None
            
            # Cargar según el tipo de archivo
            if preset_info['filename'].endswith('.json'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    preset_data = json.load(f)
                return preset_data.get('config', {})
                
            elif preset_info['filename'].endswith(('.yaml', '.yml')):
                if not YAML_AVAILABLE:
                    self.logger.error("PyYAML no disponible para cargar preset YAML")
                    return None
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    preset_data = yaml.safe_load(f)
                
                # Convertir formato YAML a formato de configuración esperado
                return self._convert_yaml_to_config(preset_data)
            
        except Exception as e:
            self.logger.error(f"Error loading preset {name}: {e}")
            return None
    
    def list_presets(self) -> List[Dict[str, str]]:
        """Lista todos los presets disponibles (JSON y YAML)"""
        presets = []
        
        try:
            if not os.path.exists(self.presets_dir):
                return presets
            
            for filename in os.listdir(self.presets_dir):
                filepath = os.path.join(self.presets_dir, filename)
                
                # Procesar archivos JSON (presets de usuario)
                if filename.endswith('.json'):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            preset_data = json.load(f)
                        
                        presets.append({
                            'name': preset_data.get('name', filename[:-5]),
                            'filename': filename,
                            'created': preset_data.get('created', ''),
                            'version': preset_data.get('version', '1.0'),
                            'type': 'user',
                            'description': preset_data.get('description', '')
                        })
                        
                    except Exception as e:
                        self.logger.warning(f"Error reading JSON preset {filename}: {e}")
                
                # Procesar archivos YAML (presets predefinidos)
                elif filename.endswith('.yaml') or filename.endswith('.yml'):
                    if not YAML_AVAILABLE:
                        self.logger.warning("PyYAML no disponible, ignorando presets YAML")
                        continue
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            preset_data = yaml.safe_load(f)
                        
                        preset_name = preset_data.get('name', filename[:-5])
                        
                        presets.append({
                            'name': preset_name,
                            'filename': filename,
                            'created': preset_data.get('created', ''),
                            'version': preset_data.get('version', '1.0'),
                            'type': 'predefined',
                            'description': preset_data.get('description', '')
                        })
                        
                    except Exception as e:
                        self.logger.warning(f"Error reading YAML preset {filename}: {e}")
            
            # Ordenar por tipo (predefinidos primero) y luego por nombre
            presets.sort(key=lambda x: (x['type'] != 'predefined', x['name']))
            
        except Exception as e:
            self.logger.error(f"Error listing presets: {e}")
        
        return presets
    
    def delete_preset(self, name: str) -> bool:
        """Elimina un preset"""
        try:
            filename = self._sanitize_filename(name) + '.json'
            filepath = os.path.join(self.presets_dir, filename)
            
            if not os.path.exists(filepath):
                self.logger.warning(f"Preset not found for deletion: {name}")
                return False
            
            os.remove(filepath)
            self.logger.info(f"Preset deleted: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting preset {name}: {e}")
            return False
    
    def get_preset_info(self, name: str) -> Optional[Dict]:
        """Obtiene información completa de un preset"""
        try:
            filename = self._sanitize_filename(name) + '.json'
            filepath = os.path.join(self.presets_dir, filename)
            
            if not os.path.exists(filepath):
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Añadir información del archivo
            stat = os.stat(filepath)
            preset_data['file_size'] = stat.st_size
            preset_data['file_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            return preset_data
            
        except Exception as e:
            self.logger.error(f"Error getting preset info {name}: {e}")
            return None
    
    def create_default_presets(self) -> bool:
        """Crea presets por defecto si no existen"""
        try:
            from app.services.user_config import UserConfigService
            
            default_presets = [
                {
                    'name': 'Configuración Básica',
                    'config': {
                        'lm_url': UserConfigService.get_lm_studio_url(),
                        'lm_compat': 'completions',
                        'batch_size': 4,
                        'timeout': 200,
                        'max_concurrent': 2,
                        'file_target': 'l10n/DEFAULT/dictionary'
                    }
                },
                {
                    'name': 'Configuración Segura',
                    'config': {
                        'lm_url': UserConfigService.get_lm_studio_url(),
                        'lm_compat': 'completions',
                        'batch_size': 2,
                        'timeout': 300,
                        'max_concurrent': 1,
                        'retry_limit': 5,
                        'file_target': 'l10n/DEFAULT/dictionary'
                    }
                },
                {
                    'name': 'Configuración Rápida',
                    'config': {
                        'lm_url': UserConfigService.get_lm_studio_url(),
                        'lm_compat': 'completions',
                        'batch_size': 8,
                        'timeout': 120,
                        'max_concurrent': 4,
                        'retry_limit': 2,
                        'file_target': 'l10n/DEFAULT/dictionary'
                    }
                }
            ]
            
            created = 0
            for preset in default_presets:
                if not self._preset_exists(preset['name']):
                    if self.save_preset(preset['name'], preset['config']):
                        created += 1
            
            if created > 0:
                self.logger.info(f"Created {created} default presets")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating default presets: {e}")
            return False
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitiza un nombre para usar como filename"""
        # Remover caracteres peligrosos
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        return sanitized.strip('._')
    
    def _preset_exists(self, name: str) -> bool:
        """Verifica si un preset existe"""
        filename = self._sanitize_filename(name) + '.json'
        filepath = os.path.join(self.presets_dir, filename)
        return os.path.exists(filepath)
    
    def get_preset_by_name(self, name: str) -> Optional[Dict]:
        """Busca un preset por nombre exacto"""
        presets = self.list_presets()
        for preset in presets:
            if preset['name'] == name:
                return preset
        return None
    
    def _convert_yaml_to_config(self, yaml_data: Dict) -> Dict:
        """Convierte un preset YAML al formato de configuración esperado"""
        config = {}
        
        # Mapear los 4 campos principales del YAML simplificado
        # --lm-compat
        if 'lm_compat' in yaml_data:
            config['arg_compat'] = yaml_data['lm_compat']
        
        # --config (PROMTS) 
        if 'config' in yaml_data:
            config['prompt_file'] = yaml_data['config']
        
        # --batch-size
        if 'batch_size' in yaml_data:
            config['arg_batch'] = yaml_data['batch_size']
        
        # --timeout (s)
        if 'timeout' in yaml_data:
            config['arg_timeout'] = yaml_data['timeout']
        
        # Valores por defecto para campos requeridos
        from app.services.user_config import UserConfigService
        config.setdefault('lm_url', UserConfigService.get_lm_studio_url())
        config.setdefault('lm_model', 'llama-3.2-3b-instruct')
        config.setdefault('use_cache', True)
        config.setdefault('include_fc', False)
        config.setdefault('deploy_overwrite', False)
        config.setdefault('auto_deploy', False)
        
        # Agregar metadatos del preset
        config['preset_metadata'] = {
            'name': yaml_data.get('name', 'Unknown'),
            'description': yaml_data.get('description', ''),
            'version': yaml_data.get('version', '1.0'),
            'type': 'predefined'
        }
        
        return config