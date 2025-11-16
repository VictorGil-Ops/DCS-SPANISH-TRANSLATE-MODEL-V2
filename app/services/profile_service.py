#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio para gestionar perfiles de configuración completos
Un perfil incluye tanto configuración general como configuración del modelo
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from config.settings import MY_CONFIG_DIR
from app.services.user_config import UserConfigService


class ProfileService:
    """Servicio para gestionar perfiles completos (configuración general + modelo)"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.profiles_dir = os.path.join(MY_CONFIG_DIR, 'profiles')
        self.user_config_service = UserConfigService()
        self._ensure_profiles_dir_exists()
    
    def _ensure_profiles_dir_exists(self):
        """Crea el directorio de perfiles si no existe"""
        try:
            os.makedirs(self.profiles_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Error creando directorio de perfiles: {e}")
    
    def create_profile(self, name: str, description: str = "") -> bool:
        """Crea un perfil nuevo con la configuración actual"""
        try:
            # Validar nombre
            if not name or not name.strip():
                raise ValueError("El nombre del perfil es requerido")
            
            name = name.strip()
            if self.profile_exists(name):
                raise ValueError(f"Ya existe un perfil con el nombre '{name}'")
            
            # Obtener configuración actual completa
            current_config = self.user_config_service.load_config()
            
            # Crear estructura del perfil
            profile_data = {
                "name": name,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "version": "1.0",
                "config": current_config
            }
            
            # Guardar perfil
            profile_file = self._get_profile_path(name)
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Perfil '{name}' creado exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creando perfil '{name}': {e}")
            return False
    
    def load_profile(self, name: str, apply_general: bool = True, apply_model: bool = True) -> bool:
        """Carga un perfil y aplica la configuración
        
        Args:
            name: Nombre del perfil
            apply_general: Si aplicar la configuración general
            apply_model: Si aplicar la configuración del modelo
        """
        try:
            if not self.profile_exists(name):
                raise ValueError(f"No existe el perfil '{name}'")
            
            # Cargar datos del perfil
            profile_data = self.get_profile(name)
            if not profile_data or 'config' not in profile_data:
                raise ValueError(f"Perfil '{name}' tiene formato inválido")
            
            profile_config = profile_data['config']
            
            # Aplicar configuración según los parámetros
            success = True
            
            if apply_general and apply_model:
                # Aplicar configuración completa
                success = self.user_config_service.save_config(profile_config)
            elif apply_general:
                # Solo configuración general
                general_fields = ['ROOT_DIR', 'FILE_TARGET', 'lm_url', 'DEPLOY_DIR', 'DEPLOY_OVERWRITE']
                general_config = {k: v for k, v in profile_config.items() if k in general_fields}
                success = self.user_config_service.save_general_config(general_config)
            elif apply_model:
                # Solo configuración del modelo
                model_fields = ['lm_model', 'arg_config', 'arg_compat', 'arg_batch', 'arg_timeout', 'use_cache', 'overwrite_cache']
                model_config = {k: v for k, v in profile_config.items() if k in model_fields}
                success = self.user_config_service.save_model_config(model_config)
            
            if success:
                # Actualizar fecha de último uso
                profile_data['last_used'] = datetime.now().isoformat()
                profile_file = self._get_profile_path(name)
                with open(profile_file, 'w', encoding='utf-8') as f:
                    json.dump(profile_data, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"Perfil '{name}' cargado exitosamente")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error cargando perfil '{name}': {e}")
            return False
    
    def update_profile(self, name: str, description: str = None) -> bool:
        """Actualiza un perfil con la configuración actual"""
        try:
            if not self.profile_exists(name):
                raise ValueError(f"No existe el perfil '{name}'")
            
            # Cargar perfil existente
            profile_data = self.get_profile(name)
            if not profile_data:
                raise ValueError(f"Error cargando perfil '{name}'")
            
            # Actualizar configuración
            current_config = self.user_config_service.load_config()
            profile_data['config'] = current_config
            profile_data['updated_at'] = datetime.now().isoformat()
            
            if description is not None:
                profile_data['description'] = description
            
            # Guardar perfil actualizado
            profile_file = self._get_profile_path(name)
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Perfil '{name}' actualizado exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error actualizando perfil '{name}': {e}")
            return False
    
    def delete_profile(self, name: str) -> bool:
        """Elimina un perfil"""
        try:
            if not self.profile_exists(name):
                return False
            
            profile_file = self._get_profile_path(name)
            os.remove(profile_file)
            
            self.logger.info(f"Perfil '{name}' eliminado exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error eliminando perfil '{name}': {e}")
            return False
    
    def list_profiles(self, user_only: bool = True) -> List[Dict[str, Any]]:
        """Lista todos los perfiles disponibles
        
        Args:
            user_only: Por defecto True, solo devuelve perfiles creados por el usuario
        """
        try:
            profiles = []
            
            if not os.path.exists(self.profiles_dir):
                return profiles
            
            for filename in os.listdir(self.profiles_dir):
                if filename.endswith('.json'):
                    profile_name = filename[:-5]  # Remover .json
                    profile_data = self.get_profile(profile_name)
                    
                    if profile_data:
                        # Solo incluir información básica en la lista
                        profile_info = {
                            'name': profile_data.get('name', profile_name),
                            'description': profile_data.get('description', ''),
                            'created_at': profile_data.get('created_at', ''),
                            'updated_at': profile_data.get('updated_at', ''),
                            'last_used': profile_data.get('last_used', ''),
                            'version': profile_data.get('version', '1.0'),
                            'is_user_created': True
                        }
                        profiles.append(profile_info)
            
            # Ordenar por fecha de última actualización (más recientes primero)
            profiles.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            
            return profiles
            
        except Exception as e:
            self.logger.error(f"Error listando perfiles: {e}")
            return []
    
    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Obtiene los datos completos de un perfil"""
        try:
            if not self.profile_exists(name):
                return None
            
            profile_file = self._get_profile_path(name)
            with open(profile_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"Error obteniendo perfil '{name}': {e}")
            return None
    
    def profile_exists(self, name: str) -> bool:
        """Verifica si existe un perfil"""
        try:
            profile_file = self._get_profile_path(name)
            return os.path.exists(profile_file)
        except:
            return False
    
    def export_profile(self, name: str, export_path: str) -> bool:
        """Exporta un perfil a un archivo específico"""
        try:
            profile_data = self.get_profile(name)
            if not profile_data:
                return False
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Perfil '{name}' exportado a '{export_path}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exportando perfil '{name}': {e}")
            return False
    
    def import_profile(self, file_path: str, new_name: str = None) -> bool:
        """Importa un perfil desde un archivo"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            # Validar estructura del perfil
            if not isinstance(profile_data, dict) or 'config' not in profile_data:
                raise ValueError("El archivo no tiene el formato correcto de perfil")
            
            # Usar nuevo nombre si se proporciona
            if new_name:
                profile_data['name'] = new_name
            
            profile_name = profile_data.get('name', 'perfil_importado')
            
            # Verificar si ya existe
            if self.profile_exists(profile_name):
                # Añadir timestamp para evitar conflictos
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                profile_name = f"{profile_name}_{timestamp}"
                profile_data['name'] = profile_name
            
            # Actualizar fechas
            profile_data['imported_at'] = datetime.now().isoformat()
            profile_data['updated_at'] = datetime.now().isoformat()
            
            # Guardar perfil importado
            profile_file = self._get_profile_path(profile_name)
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Perfil importado como '{profile_name}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Error importando perfil desde '{file_path}': {e}")
            return False
    
    def _get_profile_path(self, name: str) -> str:
        """Obtiene la ruta completa del archivo de perfil"""
        # Sanitizar nombre para uso como filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        return os.path.join(self.profiles_dir, f"{safe_name}.json")
    
    # FUNCIÓN DESHABILITADA - Solo perfiles creados por el usuario
    # def create_default_profiles(self) -> bool:
    #     """Crea perfiles por defecto si no existen"""
    #     try:
    #         default_profiles = [
    #             {
    #                 "name": "Configuración Básica",
    #                 "description": "Configuración inicial recomendada para nuevos usuarios",
    #                 "config": {
    #                     "ROOT_DIR": "",
    #                     "FILE_TARGET": "l10n/DEFAULT/dictionary",
    #                     "lm_url": "http://localhost:1234/v1",
    #                     "DEPLOY_DIR": "",
    #                     "DEPLOY_OVERWRITE": False,
    #                     "lm_model": "",
    #                     "arg_config": "",
    #                     "arg_compat": "completions",
    #                     "arg_batch": "4",
    #                     "arg_timeout": "200",
    #                     "use_cache": True,
    #                     "overwrite_cache": False
    #                 }
    #             },
    #             {
    #                 "name": "Traducción Rápida",
    #                 "description": "Configuración optimizada para traducciones rápidas con batch grande",
    #                 "config": {
    #                     "ROOT_DIR": "",
    #                     "FILE_TARGET": "l10n/DEFAULT/dictionary",
    #                     "lm_url": "http://localhost:1234/v1",
    #                     "DEPLOY_DIR": "",
    #                     "DEPLOY_OVERWRITE": False,
    #                     "lm_model": "",
    #                     "arg_config": "",
    #                     "arg_compat": "completions",
    #                     "arg_batch": "8",
    #                     "arg_timeout": "120",
    #                     "use_cache": True,
    #                     "overwrite_cache": False
    #                 }
    #             },
    #             {
    #                 "name": "Traducción de Calidad",
    #                 "description": "Configuración para obtener la mejor calidad de traducción",
    #                 "config": {
    #                     "ROOT_DIR": "",
    #                     "FILE_TARGET": "l10n/DEFAULT/dictionary",
    #                     "lm_url": "http://localhost:1234/v1",
    #                     "DEPLOY_DIR": "",
    #                     "DEPLOY_OVERWRITE": False,
    #                     "lm_model": "",
    #                     "arg_config": "",
    #                     "arg_compat": "chat",
    #                     "arg_batch": "2",
    #                     "arg_timeout": "300",
    #                     "use_cache": False,
    #                     "overwrite_cache": True
    #                 }
    #             }
    #         ]
    #         
    #         created_count = 0
    #         for profile_template in default_profiles:
    #             if not self.profile_exists(profile_template["name"]):
    #                 profile_data = {
    #                     "name": profile_template["name"],
    #                     "description": profile_template["description"],
    #                     "created_at": datetime.now().isoformat(),
    #                     "updated_at": datetime.now().isoformat(),
    #                     "version": "1.0",
    #                     "is_default": True,
    #                     "config": profile_template["config"]
    #                 }
    #                 
    #                 profile_file = self._get_profile_path(profile_template["name"])
    #                 with open(profile_file, 'w', encoding='utf-8') as f:
    #                     json.dump(profile_data, f, ensure_ascii=False, indent=2)
    #                 
    #                 created_count += 1
    #         
    #         if created_count > 0:
    #             self.logger.info(f"Creados {created_count} perfiles por defecto")
    #         
    #         return True
    #         
    #     except Exception as e:
    #         self.logger.error(f"Error creando perfiles por defecto: {e}")
    #         return False