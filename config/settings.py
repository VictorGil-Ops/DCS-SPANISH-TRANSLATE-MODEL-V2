#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuración de la aplicación DCS Spanish Translator
"""
import os
from datetime import datetime

# Rutas base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(BASE_DIR, "app")
DATA_DIR = os.path.join(APP_DIR, "data")

# Directorios de datos
PROMPTS_DIR = os.path.join(DATA_DIR, "promts")
PRESETS_DIR = os.path.join(DATA_DIR, "presets") 
TRANSLATIONS_DIR = os.path.join(DATA_DIR, "traducciones")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
MY_CONFIG_DIR = os.path.join(DATA_DIR, "my_config")

# Directorios legacy (compatibilidad)
LOG_DIR = os.path.join(BASE_DIR, "log_orquestador")
PROMPTS_LEGACY_DIR = os.path.join(BASE_DIR, "PROMTS")
PROMPTS_EXAMPLES_DIR = os.path.join(BASE_DIR, "PROMTS_EXAMPLES")

# Alias para compatibilidad (PROMTS_DIR es usado en algunos archivos)
PROMTS_DIR = PROMPTS_LEGACY_DIR

# Asegurar que todos los directorios existen (excluimos LOG_DIR/log_orquestador por ser legacy)
for directory in [DATA_DIR, PROMPTS_DIR, PRESETS_DIR, TRANSLATIONS_DIR, LOGS_DIR, MY_CONFIG_DIR]:
    os.makedirs(directory, exist_ok=True)

# Configuración de logging
LOG_FILE_PATH = os.path.join(LOGS_DIR, f"web_orquestador_{os.getpid()}.log")
ERROR_LOG_PATH = os.path.join(LOGS_DIR, "error.log")
# Logs legacy (compatibilidad)
LOG_FILE_PATH_LEGACY = os.path.join(LOG_DIR, f"web_orquestador_{os.getpid()}.log")

# Configuración de la aplicación Flask
FLASK_CONFIG = {
    'DEBUG': os.environ.get('FLASK_DEBUG', 'False').lower() == 'true',
    'HOST': os.environ.get('FLASK_HOST', '127.0.0.1'),
    'PORT': int(os.environ.get('FLASK_PORT', 5000)),
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
}

# Configuración del modelo de lenguaje
LM_CONFIG = {
    'DEFAULT_URL': os.environ.get('LM_URL', 'http://localhost:1234/v1'),
    'CLI_COMMAND': os.environ.get('LMSTUDIO_CLI', 'lms'),
    'TIMEOUT': float(os.environ.get('LM_TIMEOUT', '30.0'))
}

# Configuración de actualización
UPDATE_CONFIG = {
    'VERSION_URL': os.environ.get('ORQ_VERSION_URL', '').strip(),
    'BRANCH': os.environ.get('ORQ_BRANCH', 'main').strip(),
    'PROTECT_PATHS': ["app/data/traducciones", "log_orquestador", "campaings"]  # Mantener campaings por compatibilidad
}

# Función para leer la versión de la aplicación
def get_app_version():
    """Obtiene la versión de la aplicación desde el archivo VERSION o variable de entorno"""
    version = os.environ.get("ORQ_VERSION", "").strip()
    if version:
        return version
    
    try:
        version_file = os.path.join(BASE_DIR, "run", "VERSION")
        with open(version_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "2.0"

APP_VERSION = get_app_version()

# Configuración de logging
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': "[%(asctime)s] %(levelname)s: %(message)s",
    'file_path': LOG_FILE_PATH,
    'error_path': ERROR_LOG_PATH
}

# Configuración del motor de traducción
TRANSLATION_CONFIG = {
    'default_batch_size': 4,
    'default_timeout': 200,
    'max_concurrent_translations': int(os.environ.get('MAX_CONCURRENT_TRANSLATIONS', '2')),
    'cache_enabled': True,
    'generate_statistics': True,
    'generate_jsonl': True
}

# Configuración de archivos soportados
SUPPORTED_FILE_TYPES = {
    'lua_scripts': ['.lua'],
    'mission_files': ['.miz'],
    'prompt_files': ['.yaml', '.yml', '.json']
}

# Configuración general del usuario (valores por defecto)
DEFAULT_USER_CONFIG = {
    'ROOT_DIR': '',  # Ruta de campañas DCS
    'FILE_TARGET': 'l10n/DEFAULT/dictionary',  # Fichero objetivo a traducir
    'lm_model': '',  # Modelo preferido
    'lm_url': 'http://localhost:1234/v1',  # URL LM Studio
    'DEPLOY_DIR': '',  # Ruta despliegue misiones traducidas (opcional)
    'DEPLOY_OVERWRITE': False,  # Sobrescribir misiones originales
    # Configuración del modelo (ARGS)
    'arg_config': '',  # Config PROMTS
    'arg_compat': 'completions',  # Compatibilidad LM
    'arg_batch': '4',  # Batch size
    'arg_timeout': '200',  # Timeout en segundos
    'preset': '',  # Preset seleccionado
    # Parámetros del API del modelo (desde presets)
    'api_temperature': 0.7,
    'api_top_p': 0.9,
    'api_top_k': 40,
    'api_max_tokens': 8000,
    'api_repetition_penalty': 1.0,
    'api_presence_penalty': 0.0,
    'active_preset': '',  # Compatibility
    'use_cache': False,
    'overwrite_cache': False
}

# Mapeo de campos internos a nombres en castellano para la interfaz
USER_CONFIG_LABELS = {
    'ROOT_DIR': 'RUTA CAMPAÑAS',
    'FILE_TARGET': 'FICHERO OBJETIVO A TRADUCIR',
    'lm_model': 'MODELO PREFERIDO', 
    'lm_url': 'URL LM STUDIO',
    'DEPLOY_DIR': 'RUTA DESPLIEGUE MISIONES TRADUCIDAS',
    'DEPLOY_OVERWRITE': 'SOBRESCRIBIR MISIONES ORIGINALES',
    'arg_config': '--config (PROMTS)',
    'arg_compat': '--lm-compat',
    'arg_batch': '--batch-size',
    'arg_timeout': '--timeout (s)',
    'preset': 'PRESET SELECCIONADO',
    'active_preset': 'PRESET ACTIVO',
    'api_temperature': 'TEMPERATURE',
    'api_top_p': 'TOP P',
    'api_top_k': 'TOP K',
    'api_max_tokens': 'MAX TOKENS',
    'api_repetition_penalty': 'REPETITION PENALTY',
    'api_presence_penalty': 'PRESENCE PENALTY',
    'use_cache': 'USAR CACHÉ',
    'overwrite_cache': 'SOBRESCRIBIR CACHÉ'
}

# Archivo de configuración del usuario
USER_CONFIG_FILE = os.path.join(MY_CONFIG_DIR, 'user_config.json')