#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidades para manejo de archivos
"""
import os
import shutil
import zipfile
import logging
from typing import List, Optional
from pathlib import Path


def ensure_directory(directory: str) -> bool:
    """Asegura que un directorio existe, creándolo si es necesario"""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Error creating directory {directory}: {e}")
        return False


def safe_copy_file(src: str, dst: str, backup: bool = True) -> bool:
    """Copia un archivo de forma segura, con backup opcional"""
    try:
        # Crear directorio destino si no existe
        dst_dir = os.path.dirname(dst)
        ensure_directory(dst_dir)
        
        # Hacer backup si el archivo destino existe
        if backup and os.path.exists(dst):
            backup_path = f"{dst}.backup"
            shutil.copy2(dst, backup_path)
            logging.info(f"Backup created: {backup_path}")
        
        # Copiar archivo
        shutil.copy2(src, dst)
        logging.info(f"File copied: {src} -> {dst}")
        return True
        
    except Exception as e:
        logging.error(f"Error copying file {src} to {dst}: {e}")
        return False


def extract_from_zip(zip_path: str, file_path: str, extract_to: str) -> Optional[str]:
    """Extrae un archivo específico de un ZIP"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            if file_path in zip_file.namelist():
                extracted_path = zip_file.extract(file_path, extract_to)
                return extracted_path
        return None
    except Exception as e:
        logging.error(f"Error extracting {file_path} from {zip_path}: {e}")
        return None


def add_to_zip(zip_path: str, file_path: str, arcname: str = None) -> bool:
    """Añade un archivo a un ZIP"""
    try:
        with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zip_file:
            arcname = arcname or os.path.basename(file_path)
            zip_file.write(file_path, arcname)
        return True
    except Exception as e:
        logging.error(f"Error adding {file_path} to {zip_path}: {e}")
        return False


def get_file_size_mb(file_path: str) -> float:
    """Obtiene el tamaño de un archivo en MB"""
    try:
        size_bytes = os.path.getsize(file_path)
        return round(size_bytes / (1024 * 1024), 2)
    except Exception:
        return 0.0


def find_files_by_pattern(directory: str, pattern: str, recursive: bool = True) -> List[str]:
    """Busca archivos por patrón"""
    import glob
    
    if recursive:
        search_pattern = os.path.join(directory, "**", pattern)
        return glob.glob(search_pattern, recursive=True)
    else:
        search_pattern = os.path.join(directory, pattern)
        return glob.glob(search_pattern)


def cleanup_temp_files(temp_dir: str, max_age_hours: int = 24) -> int:
    """Limpia archivos temporales antiguos"""
    import time
    
    cleaned = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    try:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        cleaned += 1
                        logging.debug(f"Cleaned temp file: {file_path}")
                except Exception as e:
                    logging.warning(f"Could not clean {file_path}: {e}")
    except Exception as e:
        logging.error(f"Error cleaning temp directory {temp_dir}: {e}")
    
    return cleaned