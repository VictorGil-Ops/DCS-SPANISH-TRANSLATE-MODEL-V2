#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidades de validación
"""
import os
import re
from typing import Dict, Tuple, List, Optional
from urllib.parse import urlparse


def validate_dcs_path(path: str) -> Tuple[bool, str]:
    """Valida que una ruta sea un directorio válido de DCS"""
    if not path:
        return False, "La ruta no puede estar vacía"
    
    if not os.path.exists(path):
        return False, "El directorio no existe"
    
    if not os.path.isdir(path):
        return False, "La ruta no es un directorio"
    
    # Verificar estructura típica de DCS
    expected_files = ["*.miz"]  # Al menos debería tener archivos .miz
    
    import glob
    miz_files = glob.glob(os.path.join(path, "**", "*.miz"), recursive=True)
    if not miz_files:
        return False, "No se encontraron archivos .miz en el directorio"
    
    return True, f"Directorio válido con {len(miz_files)} archivos .miz"


def validate_url(url: str) -> Tuple[bool, str]:
    """Valida una URL"""
    if not url:
        return False, "La URL no puede estar vacía"
    
    # Verificar formato básico
    if not url.startswith(('http://', 'https://')):
        return False, "La URL debe comenzar con http:// o https://"
    
    # Validar usando urlparse
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Formato de URL inválido"
    except Exception:
        return False, "Formato de URL inválido"
    
    return True, "URL válida"


def validate_lm_config(config: Dict) -> Tuple[bool, List[str]]:
    """Valida la configuración del modelo de lenguaje"""
    errors = []
    
    # Validar URL
    if 'url' in config:
        is_valid, msg = validate_url(config['url'])
        if not is_valid:
            errors.append(f"URL inválida: {msg}")
    
    # Validar modelo
    if not config.get('model'):
        errors.append("Debe seleccionar un modelo")
    
    # Validar batch size
    batch_size = config.get('batch_size', 0)
    if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 20:
        errors.append("Batch size debe ser un número entre 1 y 20")
    
    # Validar timeout
    timeout = config.get('timeout', 0)
    if not isinstance(timeout, (int, float)) or timeout < 10 or timeout > 600:
        errors.append("Timeout debe ser un número entre 10 y 600 segundos")
    
    # Validar compatibilidad
    valid_compat = ['completions', 'chat']
    if config.get('compat') not in valid_compat:
        errors.append(f"Compatibilidad debe ser uno de: {', '.join(valid_compat)}")
    
    return len(errors) == 0, errors


def validate_translation_config(config: Dict) -> Tuple[bool, List[str]]:
    """Valida la configuración completa de traducción"""
    errors = []
    
    # Validar ruta DCS
    if 'dcs_path' in config:
        is_valid, msg = validate_dcs_path(config['dcs_path'])
        if not is_valid:
            errors.append(f"Ruta DCS: {msg}")
    else:
        errors.append("Ruta DCS es requerida")
    
    # Validar configuración LM
    lm_config = {
        'url': config.get('lm_url'),
        'model': config.get('lm_model'),
        'batch_size': config.get('batch_size', 4),
        'timeout': config.get('timeout', 200),
        'compat': config.get('lm_compat', 'completions')
    }
    
    is_valid, lm_errors = validate_lm_config(lm_config)
    errors.extend(lm_errors)
    
    # Validar campañas seleccionadas
    campaigns = config.get('campaigns', [])
    if not campaigns:
        errors.append("Debe seleccionar al menos una campaña")
    
    # Validar prompt file
    if not config.get('prompt_file'):
        errors.append("Debe seleccionar un archivo de prompt")
    
    # Validar concurrencia
    max_concurrent = config.get('max_concurrent', 2)
    if not isinstance(max_concurrent, int) or max_concurrent < 1 or max_concurrent > 10:
        errors.append("Concurrencia máxima debe ser entre 1 y 10")
    
    return len(errors) == 0, errors


def sanitize_filename(filename: str) -> str:
    """Sanitiza un nombre de archivo"""
    # Remover caracteres peligrosos
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remover espacios extra y puntos
    filename = re.sub(r'\s+', ' ', filename).strip()
    filename = filename.strip('.')
    
    # Limitar longitud
    if len(filename) > 100:
        name, ext = os.path.splitext(filename)
        filename = name[:96] + ext
    
    return filename or "unnamed"


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """Valida la extensión de un archivo"""
    if not filename:
        return False
    
    ext = os.path.splitext(filename)[1].lower()
    return ext in [e.lower() if e.startswith('.') else f'.{e.lower()}' for e in allowed_extensions]


def validate_port(port: any) -> Tuple[bool, str]:
    """Valida un puerto"""
    try:
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            return False, "El puerto debe estar entre 1 y 65535"
        if port_num < 1024:
            return False, "Se recomienda usar puertos >= 1024 para evitar permisos"
        return True, "Puerto válido"
    except (ValueError, TypeError):
        return False, "El puerto debe ser un número entero"