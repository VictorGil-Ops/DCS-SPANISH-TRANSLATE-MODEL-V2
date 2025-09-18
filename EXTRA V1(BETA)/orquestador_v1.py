#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para procesamiento en lote de traducción de misiones .miz de DCS.
Lee una lista de archivos desde un fichero de input y procesa cada uno.

Uso:
  python translate_miz_bulk.py --input-file lista_misiones.txt --input-path misiones_origen --output-path misiones_traducidas --engine deepseek --keys keys.txt

Formato del fichero de input (lista_misiones.txt):
  F5-E-C10.miz
  A-10C-CAP.miz
  Su-33-Intercept.miz
  # Líneas comentadas con #
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

def load_file_list(input_file: Path):
    """Carga la lista de archivos .miz desde el fichero de input"""
    files = []
    if not input_file.exists():
        print(f"[ERROR] Fichero de input no encontrado: {input_file}")
        return files
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Saltar líneas vacías y comentarios
                if not line or line.startswith('#'):
                    continue
                # Asegurar que tiene extensión .miz
                if not line.lower().endswith('.miz'):
                    line += '.miz'
                files.append(line)
        return files
    except Exception as e:
        print(f"[ERROR] Error leyendo fichero de input: {e}")
        return []

def extract_miz_python(miz_file: Path, extract_dir: Path):
    """Extrae un archivo .miz usando zipfile de Python"""
    try:
        with zipfile.ZipFile(miz_file, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        return True
    except Exception as e:
        print(f"[ERROR] Error al extraer {miz_file}: {e}")
        return False

def create_miz_python(source_dir: Path, miz_file: Path):
    """Crea un archivo .miz usando zipfile de Python"""
    try:
        # Asegurarse de que el directorio de destino existe
        miz_file.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(miz_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)
        return True
    except Exception as e:
        print(f"[ERROR] Error al crear {miz_file}: {e}")
        return False

def find_dictionary_file(extract_dir: Path):
    """Busca el archivo dictionary en la estructura descomprimida"""
    possible_paths = [
        extract_dir / 'l10n' / 'DEFAULT' / 'dictionary',
        extract_dir / 'l10n' / 'DEFAULT' / 'dictionary.lua',
        extract_dir / 'dictionary',
        extract_dir / 'dictionary.lua',
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    return None

def translate_single_miz(miz_filename, input_path, output_path, args, translator_script):
    """Procesa una sola misión .miz"""
    miz_path = input_path / miz_filename
    output_miz_path = output_path / miz_filename
    
    if not miz_path.exists():
        print(f"[WARNING] Archivo no encontrado en input-path: {miz_filename}")
        return False
    
    print(f"\n[PROCESANDO] {miz_filename}")
    print("-" * 50)
    
    # Crear directorio temporal para esta misión
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        extract_dir = temp_path / 'extracted'
        extract_dir.mkdir()
        
        # Extraer .miz
        if not extract_miz_python(miz_path, extract_dir):
            print(f"[ERROR] No se pudo extraer: {miz_filename}")
            return False
        
        # Buscar archivo dictionary
        dict_file = find_dictionary_file(extract_dir)
        if not dict_file:
            print(f"[WARNING] No se encontró dictionary en: {miz_filename}")
            return False
        
        print(f"[INFO] Dictionary encontrado: {dict_file.name}")
        
        # Crear nombre para el dictionary basado en el .miz
        dict_new_name = miz_path.stem + '.lua'
        dict_temp_path = temp_path / dict_new_name
        
        # Copiar el dictionary al directorio temporal
        shutil.copy2(dict_file, dict_temp_path)
        
        # Traducir el dictionary
        print(f"[INFO] Traduciendo {dict_new_name}...")
        
        # Construir comando para el script de traducción
        cmd = [
            sys.executable, str(translator_script),
            str(dict_temp_path),
            '--engine', args.engine,
            '--keys', args.keys,
            '--style', args.style,
            '--batch-size', str(args.batch_size)
        ]
        
        if args.model:
            cmd.extend(['--model', args.model])
        if args.translate_all:
            cmd.append('--translate-all')
        if args.quiet:
            cmd.append('--quiet')
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("[INFO] Traducción completada")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Error en la traducción: {e}")
            if e.stderr:
                print(f"Stderr: {e.stderr[:200]}...")  # Mostrar solo parte del error
            return False
        
        # Verificar que el archivo traducido existe
        translated_file = dict_temp_path.with_name(f"{dict_temp_path.stem}_traducido{dict_temp_path.suffix}")
        if not translated_file.exists():
            print(f"[ERROR] No se generó el archivo traducido")
            return False
        
        # Reemplazar el dictionary original con el traducido
        shutil.copy2(translated_file, dict_file)
        
        # Reempaquetar la misión
        print(f"[INFO] Recomprimiendo misión...")
        
        if create_miz_python(extract_dir, output_miz_path):
            print(f"[SUCCESS] Misión traducida: {output_miz_path.name}")
            return True
        else:
            print("[ERROR] No se pudo recomprimir la misión")
            return False

def main():
    parser = argparse.ArgumentParser(description="Procesamiento en lote de traducción de misiones .miz de DCS")
    parser.add_argument('--input-file', required=True, help='Fichero con lista de misiones .miz a procesar')
    parser.add_argument('--input-path', required=True, help='Directorio donde buscar los archivos .miz originales')
    parser.add_argument('--output-path', required=True, help='Directorio donde guardar las misiones traducidas')
    parser.add_argument('--engine', required=True, choices=['chatgpt','deepseek','azure','openrouter','anthropic'])
    parser.add_argument('--keys', required=True, help='Fichero con API keys y parámetros')
    parser.add_argument('--model', default=None, help='Modelo o deployment a usar')
    parser.add_argument('--style', default='formal', choices=['brevity','neutral','formal'])
    parser.add_argument('--translate-all', action='store_true')
    parser.add_argument('--batch-size', type=int, default=40)
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--skip-errors', action='store_true', help='Continuar con siguientes archivos si hay errores')
    
    args = parser.parse_args()
    
    # Verificar paths
    input_path = Path(args.input_path)
    output_path = Path(args.output_path)
    input_file = Path(args.input_file)
    
    if not input_path.exists():
        print(f"[ERROR] Input path no existe: {input_path}")
        sys.exit(1)
    
    if not input_file.exists():
        print(f"[ERROR] Input file no existe: {input_file}")
        sys.exit(1)
    
    # Crear output path si no existe
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Verificar script de traducción
    translator_script = Path(__file__).parent / 'traducir_dcs_dictionary_v1.py'
    if not translator_script.exists():
        print(f"[ERROR] No se encuentra el script de traducción: {translator_script}")
        sys.exit(1)
    
    # Cargar lista de archivos
    miz_files = load_file_list(input_file)
    if not miz_files:
        print("[ERROR] No se encontraron archivos para procesar en el input file")
        sys.exit(1)
    
    print(f"[INFO] Iniciando procesamiento de {len(miz_files)} misiones")
    print(f"[INFO] Input path: {input_path}")
    print(f"[INFO] Output path: {output_path}")
    
    # Procesar cada archivo
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for i, miz_filename in enumerate(miz_files, 1):
        print(f"\n[{i}/{len(miz_files)}] ", end="")
        
        try:
            if translate_single_miz(miz_filename, input_path, output_path, args, translator_script):
                success_count += 1
            else:
                error_count += 1
                if not args.skip_errors:
                    print("[ERROR] Deteniendo procesamiento por error")
                    break
        except Exception as e:
            print(f"[ERROR] Error inesperado procesando {miz_filename}: {e}")
            error_count += 1
            if not args.skip_errors:
                break
    
    # Mostrar resumen
    print("\n" + "="*60)
    print("[RESUMEN DEL PROCESAMIENTO]")
    print(f"Misiones procesadas: {len(miz_files)}")
    print(f"✓ Traducidas exitosamente: {success_count}")
    print(f"✗ Con errores: {error_count}")
    print(f"⏭️  Saltadas: {skipped_count}")
    
    if success_count > 0:
        print(f"\nMisiones traducidas guardadas en: {output_path}")
    
    if error_count > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()