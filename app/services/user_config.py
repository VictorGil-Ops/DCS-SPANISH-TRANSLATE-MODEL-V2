#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio para manejar la configuración general del usuario
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from config.settings import (
    USER_CONFIG_FILE, DEFAULT_USER_CONFIG, 
    USER_CONFIG_LABELS, MY_CONFIG_DIR
)


class UserConfigService:
    """Servicio para gestionar la configuración general del usuario"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_file = USER_CONFIG_FILE
        
        # Asegurar que el directorio existe
        os.makedirs(MY_CONFIG_DIR, exist_ok=True)
        
        # Crear archivo de configuración vacío si no existe
        self._ensure_config_file_exists()
    
    def _ensure_config_file_exists(self):
        """Crea el archivo de configuración vacío si no existe"""
        if not os.path.exists(self.config_file):
            try:
                # Crear archivo con configuración vacía (solo las claves, valores vacíos)
                empty_config = {}
                for key in DEFAULT_USER_CONFIG.keys():
                    if key.startswith('arg_'):
                        # Para argumentos, usar valores por defecto
                        empty_config[key] = DEFAULT_USER_CONFIG[key]
                    else:
                        # Para configuración principal, dejar vacío
                        empty_config[key] = ''
                
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(empty_config, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"Archivo de configuración inicial creado: {self.config_file}")
                
            except Exception as e:
                self.logger.error(f"Error creando archivo de configuración inicial: {e}")
    
    def load_config(self) -> Dict[str, Any]:
        """Carga la configuración del usuario desde el archivo"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                
                # Fusionar con valores por defecto para campos faltantes
                config = DEFAULT_USER_CONFIG.copy()
                config.update(user_config)
                
                self.logger.info("Configuración del usuario cargada exitosamente")
                return config
            else:
                self.logger.info("No existe configuración del usuario, usando valores por defecto")
                return DEFAULT_USER_CONFIG.copy()
                
        except Exception as e:
            self.logger.error(f"Error cargando configuración del usuario: {e}")
            return DEFAULT_USER_CONFIG.copy()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Guarda la configuración del usuario fusionando con la existente"""
        try:
            # Cargar configuración existente
            existing_config = self.load_config()
            
            # Fusionar con la nueva configuración (solo los campos proporcionados)
            for key, value in config.items():
                if key in DEFAULT_USER_CONFIG.keys():
                    existing_config[key] = value
            
            # Validar la configuración fusionada
            validated_config = self._validate_config(existing_config)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(validated_config, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Configuración guardada en: {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error guardando configuración del usuario: {e}")
            return False
    
    def get_config_with_labels(self) -> Dict[str, Any]:
        """Obtiene la configuración con etiquetas en castellano para la interfaz"""
        config = self.load_config()
        
        # Crear estructura para la interfaz
        config_with_labels = {}
        for key, value in config.items():
            label = USER_CONFIG_LABELS.get(key, key)
            config_with_labels[key] = {
                'value': value,
                'label': label,
                'type': self._get_field_type(key, value)
            }
        
        return config_with_labels
    
    def update_field(self, field: str, value: Any) -> bool:
        """Actualiza un campo específico de la configuración"""
        try:
            config = self.load_config()
            
            if field not in DEFAULT_USER_CONFIG:
                self.logger.error(f"Campo no válido: {field}")
                return False
            
            # Convertir tipos si es necesario
            config[field] = self._convert_field_type(field, value)
            
            return self.save_config(config)
            
        except Exception as e:
            self.logger.error(f"Error actualizando campo {field}: {e}")
            return False
    
    def save_general_config(self, config: Dict[str, Any]) -> bool:
        """Guarda solo la configuración general (sin afectar configuración del modelo)"""
        try:
            # Campos de configuración general
            general_fields = ['ROOT_DIR', 'FILE_TARGET', 'lm_url', 'DEPLOY_DIR', 'DEPLOY_OVERWRITE']
            
            # Cargar configuración existente
            existing_config = self.load_config()
            
            # Actualizar solo los campos generales
            for field in general_fields:
                if field in config:
                    existing_config[field] = self._convert_field_type(field, config[field])
            
            # Guardar configuración actualizada
            return self.save_config(existing_config)
            
        except Exception as e:
            self.logger.error(f"Error guardando configuración general: {e}")
            return False
    
    def save_model_config(self, config: Dict[str, Any]) -> bool:
        """Guarda solo la configuración del modelo (sin afectar configuración general)"""
        try:
            # Campos de configuración del modelo
            model_fields = ['lm_model', 'arg_config', 'arg_compat', 'arg_batch', 'arg_timeout']
            
            # Cargar configuración existente
            existing_config = self.load_config()
            
            # Actualizar solo los campos del modelo
            for field in model_fields:
                if field in config:
                    existing_config[field] = self._convert_field_type(field, config[field])
            
            # Guardar configuración actualizada
            return self.save_config(existing_config)
            
        except Exception as e:
            self.logger.error(f"Error guardando configuración del modelo: {e}")
            return False
    
    def reset_general_to_defaults(self) -> bool:
        """Resetea solo la configuración general a valores por defecto"""
        try:
            # Campos de configuración general con sus valores por defecto
            general_defaults = {
                'ROOT_DIR': '',
                'FILE_TARGET': 'l10n/DEFAULT/dictionary',
                'lm_url': 'http://localhost:1234/v1',
                'DEPLOY_DIR': '',
                'DEPLOY_OVERWRITE': False
            }
            
            return self.save_general_config(general_defaults)
            
        except Exception as e:
            self.logger.error(f"Error reseteando configuración general: {e}")
            return False
    
    def reset_model_to_defaults(self) -> bool:
        """Resetea solo la configuración del modelo a valores por defecto"""
        try:
            # Campos de configuración del modelo con sus valores por defecto
            model_defaults = {
                'lm_model': '',
                'arg_config': '',
                'arg_compat': 'completions',
                'arg_batch': '4',
                'arg_timeout': '200'
            }
            
            return self.save_model_config(model_defaults)
            
        except Exception as e:
            self.logger.error(f"Error reseteando configuración del modelo: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """Resetea la configuración completa a valores por defecto"""
        try:
            return self.save_config(DEFAULT_USER_CONFIG.copy())
        except Exception as e:
            self.logger.error(f"Error reseteando configuración: {e}")
            return False
    
    def validate_paths(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Valida las rutas en la configuración"""
        if config is None:
            config = self.load_config()
        
        validation_results = {}
        
        # Validar ROOT_DIR (ruta campañas)
        root_dir = config.get('ROOT_DIR', '')
        if root_dir:
            validation_results['ROOT_DIR'] = os.path.exists(root_dir) and os.path.isdir(root_dir)
        else:
            validation_results['ROOT_DIR'] = None  # No configurado
        
        # Validar DEPLOY_DIR (opcional)
        deploy_dir = config.get('DEPLOY_DIR', '')
        if deploy_dir:
            validation_results['DEPLOY_DIR'] = os.path.exists(deploy_dir) and os.path.isdir(deploy_dir)
        else:
            validation_results['DEPLOY_DIR'] = None  # No configurado (opcional)
        
        return validation_results
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Valida y limpia la configuración"""
        validated = {}
        
        for key in DEFAULT_USER_CONFIG.keys():
            if key in config:
                validated[key] = self._convert_field_type(key, config[key])
            else:
                validated[key] = DEFAULT_USER_CONFIG[key]
        
        return validated
    
    def _get_field_type(self, field: str, value: Any) -> str:
        """Determina el tipo de campo para la interfaz"""
        if field == 'DEPLOY_OVERWRITE':
            return 'checkbox'
        elif field in ['ROOT_DIR', 'DEPLOY_DIR']:
            return 'directory'
        elif field == 'lm_url':
            return 'url'
        else:
            return 'text'
    
    def _convert_field_type(self, field: str, value: Any) -> Any:
        """Convierte el valor al tipo correcto según el campo"""
        if field == 'DEPLOY_OVERWRITE':
            return bool(value)
        else:
            return str(value) if value is not None else ''
    
    @staticmethod
    def get_lm_studio_url() -> str:
        """
        Obtiene la URL de LM Studio desde la configuración del usuario.
        Método estático para uso fácil desde otros servicios.
        
        Returns:
            str: URL de LM Studio configurada por el usuario o valor por defecto
        """
        try:
            service = UserConfigService()
            config = service.load_config()
            url = config.get('lm_url', 'http://localhost:1234/v1')
            
            # Validar que la URL tenga formato correcto
            if url and url.strip():
                # Asegurar que termine con /v1 si no lo tiene
                url = url.strip().rstrip('/')
                if not url.endswith('/v1'):
                    url += '/v1'
                return url
            else:
                return 'http://localhost:1234/v1'
                
        except Exception:
            # En caso de error, usar valor por defecto
            return 'http://localhost:1234/v1'
    
    @staticmethod
    def get_user_config_value(key: str, default_value: Any = None) -> Any:
        """
        Obtiene un valor específico de la configuración del usuario.
        Método estático para uso fácil desde otros servicios.
        
        Args:
            key: Clave de configuración a obtener
            default_value: Valor por defecto si no se encuentra la clave
        
        Returns:
            Any: Valor configurado por el usuario o valor por defecto
        """
        try:
            service = UserConfigService()
            config = service.load_config()
            return config.get(key, default_value)
        except Exception:
            return default_value
    
    @staticmethod
    def get_file_target() -> str:
        """
        Obtiene el FILE_TARGET desde la configuración del usuario.
        Método estático para uso fácil desde otros servicios.
        
        Returns:
            str: FILE_TARGET configurado por el usuario o valor por defecto
        """
        try:
            service = UserConfigService()
            config = service.load_config()
            file_target = config.get('FILE_TARGET', 'l10n/DEFAULT/dictionary')
            
            # Validar que no esté vacío
            if file_target and file_target.strip():
                return file_target.strip()
            else:
                return 'l10n/DEFAULT/dictionary'
                
        except Exception:
            # En caso de error, usar valor por defecto
            return 'l10n/DEFAULT/dictionary'
    
    @staticmethod
    def get_repo_url() -> str:
        """
        Detecta automáticamente la URL del repositorio Git.
        Transparente para el usuario final - no requiere configuración.
        Soporta detección automática de repositorios dev/pre/pro.
        
        Returns:
            str: URL del repositorio Git o valor por defecto si no se puede detectar
        """
        try:
            import subprocess
            import os
            
            # Obtener el directorio del proyecto (donde está este archivo)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # Intentar obtener la URL remota de git
            try:
                result = subprocess.run(
                    ['git', 'config', '--get', 'remote.origin.url'],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    git_url = result.stdout.strip()
                    
                    # Convertir SSH a HTTPS si es necesario
                    if git_url.startswith('git@github.com:'):
                        # git@github.com:user/repo.git -> https://github.com/user/repo
                        git_url = git_url.replace('git@github.com:', 'https://github.com/')
                    
                    # Limpiar .git del final
                    if git_url.endswith('.git'):
                        git_url = git_url[:-4]
                    
                    return git_url
                    
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            # Fallback: detectar por nombre del directorio del proyecto
            project_name = os.path.basename(project_root).upper()
            
            # Mapeo de nombres de proyecto a URLs de repositorio
            repo_mappings = {
                'DEV-DCS-SPANISH-TRANSLATE-MODEL-V2-PRIVATE': 'https://github.com/VictorGil-Ops/DEV-DCS-SPANISH-TRANSLATE-MODEL-V2-Private',
                'PRE-DCS-SPANISH-TRANSLATE-MODEL-V2-PRIVATE': 'https://github.com/VictorGil-Ops/PRE-DCS-SPANISH-TRANSLATE-MODEL-V2-Private',
                'PRO-DCS-SPANISH-TRANSLATE-MODEL-V2-PRIVATE': 'https://github.com/VictorGil-Ops/PRO-DCS-SPANISH-TRANSLATE-MODEL-V2-Private',
                'DCS-SPANISH-TRANSLATE-MODEL-V2': 'https://github.com/VictorGil-Ops/DCS-Spanish-Translate-Model-V2',
            }
            
            # Buscar coincidencia exacta
            if project_name in repo_mappings:
                return repo_mappings[project_name]
            
            # Buscar coincidencia parcial
            for key, url in repo_mappings.items():
                if key in project_name or project_name in key:
                    return url
            
            # Último fallback: repositorio dev por defecto
            return 'https://github.com/VictorGil-Ops/DEV-DCS-SPANISH-TRANSLATE-MODEL-V2-Private'
            
        except Exception:
            # En caso de cualquier error, usar valor por defecto del repo dev
            return 'https://github.com/VictorGil-Ops/DEV-DCS-SPANISH-TRANSLATE-MODEL-V2-Private'
    
    @staticmethod
    def get_version() -> str:
        """
        Lee la versión desde el archivo VERSION en la raíz del proyecto.
        Transparente para el usuario final - no requiere configuración.
        
        Returns:
            str: Versión del software o valor por defecto si no se puede leer
        """
        try:
            import os
            
            # Obtener el directorio del proyecto (donde está este archivo)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # Intentar leer el archivo VERSION (está en la carpeta run/)
            version_file = os.path.join(project_root, 'run', 'VERSION')
            
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    version = f.read().strip()
                    
                    # Limpiar espacios y saltos de línea
                    if version:
                        return version
            
            # Fallback: versión por defecto
            return '2.0.0'
            
        except Exception:
            # En caso de cualquier error, usar versión por defecto
            return '2.0.0'