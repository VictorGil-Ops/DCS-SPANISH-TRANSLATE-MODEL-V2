import os
import zipfile
import subprocess
import logging
import sys
import json
from typing import List, Tuple, Dict
import shutil

# --- Configuración y Logging ---
OUTPUT_DIR = "out_lua"
os.makedirs(OUTPUT_DIR, exist_ok=True)

log_file_path = os.path.join(OUTPUT_DIR, f"orquestador_{os.getpid()}.log")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- Funciones de Manejo de Archivos .miz ---

def extract_miz(miz_path: str, temp_dir: str):
    """Descomprime un archivo .miz a un directorio temporal."""
    logging.info(f"Descomprimiendo: {miz_path}")
    try:
        # Limpia el dir temporal si ya existía (para evitar residuos)
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        with zipfile.ZipFile(miz_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        logging.info("Descompresión completada.")
    except Exception as e:
        logging.error(f"Error al descomprimir {miz_path}: {e}")
        raise

def compress_miz(temp_dir: str, output_miz_path: str):
    """Comprime un directorio temporal de nuevo en un archivo .miz."""
    logging.info(f"Comprimiendo {temp_dir} a {output_miz_path}")
    try:
        # Asegura carpeta destino
        os.makedirs(os.path.dirname(output_miz_path), exist_ok=True)
        with zipfile.ZipFile(output_miz_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zip_ref.write(file_path, arcname)
        logging.info("Compresión completada.")
    except Exception as e:
        logging.error(f"Error al comprimir {output_miz_path}: {e}")
        raise

def backup_miz(miz_path: str, backup_dir: str):
    """Crea una copia de seguridad del archivo .miz original."""
    try:
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, os.path.basename(miz_path))
        logging.info(f"Creando copia de seguridad: {backup_path}")
        shutil.copy2(miz_path, backup_path)
        logging.info("Copia de seguridad creada con éxito.")
    except Exception as e:
        logging.error(f"Error al crear la copia de seguridad de {miz_path}: {e}")
        raise

# --- Función de Orquestación de Traducción ---

def translate_lua(lua_path: str, dcs_translate_script: str, extra_args: str = ""):
    """
    Llama al script dcs_lua_translate.py como un subproceso para traducir el archivo.
    Retorna True si la traducción fue exitosa, False en caso contrario.
    """
    logging.info(f"Iniciando traducción para {lua_path}...")

    cmd = ["python", dcs_translate_script, lua_path]
    if extra_args:
        cmd.extend(extra_args.split())

    logging.info(f"Comando de traducción: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        logging.info("Traducción completada exitosamente.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"El script de traducción falló con el código de salida {e.returncode}.")
        logging.error(f"Revisa el log de 'dcs_lua_translate.py' para más detalles.")
        logging.error(f"stdout: {e.stdout}")
        logging.error(f"stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error(f"No se encontró el script de traducción en la ruta: {dcs_translate_script}")
        return False

# --- Función de Lectura de Archivo de Misiones ---

def read_mission_list(file_path: str) -> Tuple[List[Tuple[str, str, str, str]], str, str]:
    """
    Lee el archivo de misiones.txt y devuelve una lista de tuplas (miz_path, lua_name, campaign_name, translate_args)
    y los argumentos globales y el directorio de salida.
    """
    missions = []
    global_args = ""
    missions_dir = ""
    output_dir = "finalizado"  # Directorio de salida por defecto
    file_target = ""

    logging.info(f"Leyendo la lista de misiones de {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if line.upper().startswith('DIR_INPUT:'):
                    missions_dir = line[10:].strip().replace('"', '')
                    if not os.path.isabs(missions_dir):
                        missions_dir = os.path.join(os.path.dirname(os.path.abspath(file_path)), missions_dir)
                    if not os.path.isdir(missions_dir):
                        logging.warning(f"La ruta de misiones '{missions_dir}' no es un directorio válido. Usando el directorio del script.")
                        missions_dir = os.path.dirname(os.path.abspath(file_path))
                    continue

                if line.upper().startswith('DIR_OUTPUT:'):
                    output_dir = line[11:].strip().replace('"', '')
                    if not os.path.isabs(output_dir):
                        output_dir = os.path.join(os.path.dirname(os.path.abspath(file_path)), output_dir)
                    logging.info(f"Directorio de salida definido: \"{output_dir}\"")
                    continue

                if line.upper().startswith('FILE_TARGET:'):
                    file_target = line[12:].strip().replace('"', '')
                    logging.info(f"Fichero de traducción objetivo encontrado: \"{file_target}\"")
                    continue

                if line.upper().startswith('ARGS:'):
                    global_args = line[5:].strip().replace('"', '')
                    logging.info(f"Argumentos globales de traducción encontrados: \"{global_args}\"")
                    continue

                parts = [p.strip() for p in line.split(',')]

                miz_file_name = parts[0]

                if not missions_dir:
                    missions_dir = os.path.dirname(os.path.abspath(file_path))
                    logging.warning("No se especificó la ruta de misiones 'DIR_INPUT:'. Usando el directorio del script.")

                if not file_target:
                    logging.warning(f"Línea {line_num}: No se especificó el fichero de traducción 'FILE_TARGET:'. Se usará 'dictionary' por defecto.")
                    file_target = "dictionary"

                miz_path = os.path.join(missions_dir, miz_file_name)

                lua_name = file_target
                campaign_name = parts[1] if len(parts) > 1 and parts[1] else "misiones_traducidas"
                translate_args = parts[2] if len(parts) > 2 and parts[2] else ""

                if not os.path.exists(miz_path):
                    logging.warning(f"Línea {line_num}: El archivo .miz '{miz_file_name}' no existe en la ruta '{miz_path}'. Saltando.")
                    continue

                missions.append((miz_path, lua_name, campaign_name, translate_args))

        logging.info(f"Se encontraron {len(missions)} misiones para procesar.")
        return missions, global_args, output_dir
    except FileNotFoundError:
        logging.error(f"El archivo '{file_path}' no se encontró. Crea uno con la lista de misiones.")
        return [], "", ""
    except Exception as e:
        logging.error(f"Error al leer el archivo de misiones: {e}")
        return [], "", ""

# --- Módulo de Ayuda ---

def show_help():
    """Muestra la información de ayuda sobre cómo usar los scripts."""
    print("\n--- MODO AYUDA ---")
    print("\nEste script es una herramienta de orquestación para traducir misiones de DCS World.")
    print("Depende de otro script, 'dcs_lua_translate.py', para la traducción real.")
    print("Asegúrate de que ambos scripts están en la misma carpeta.")

    print("\n--- misiones.txt ---")
    print("Debes crear un archivo de texto llamado 'misiones.txt' en la misma carpeta.")
    print("Este archivo debe contener la configuración y la lista de misiones.")
    print("\nFormato de configuración (opcional, al inicio del archivo):")
    print("    - DIR_INPUT: <ruta_completa_a_la_carpeta_de_misiones>")
    print("    - DIR_OUTPUT: <ruta_completa_a_la_carpeta_de_misiones_traducidas>")
    print("    - FILE_TARGET: <ruta_relativa_fichero_lua_dentro_del_miz>")
    print("    - ARGS: <argumentos_globales_para_la_traduccion>")
    print("\nFormato de cada misión:")
    print("    <nombre_archivo.miz>[, <nombre_campaña>][, <argumentos_locales>]")
    print("    - Las líneas que comienzan con '#' son ignoradas.")
    print("    - Los argumentos extra locales anularán a los argumentos globales para esa misión.")
    print("\nEjemplos:")
    print("    DIR_INPUT: C:\\Users\\TuUsuario\\DCS\\Missions\\Campaigns\\")
    print("    DIR_OUTPUT: C:\\Users\\TuUsuario\\DCS\\Missions\\Translated\\")
    print("    FILE_TARGET: l10n/DEFAULT/dictionary")
    print("    ARGS: --batch-size 16 --lm-url http://localhost:1234/v1")
    print("    F5-E-C1.miz")
    print("    F5-E-C2.miz, , --timeout 300")

    print("\n--- Modos de Operación ---")
    print("1. translate: Descomprime y traduce el fichero .lua. No re-empaqueta.")
    print("2. miz      : NO traduce; re-empaqueta el .miz. Si existe un .translated.lua previo en out_lua, lo inserta.")
    print("3. all      : Traduce y re-empaqueta todas las misiones listadas.")

    print("\n--- Errores ---")
    print("Si un paso falla, el script te lo indicará. Revisa el log en la carpeta 'out_lua' para más detalles.")
    print("----------------------------")

# --- Lógica Principal Interactiva ---

def get_interactive_mode() -> str:
    """Muestra un menú interactivo y pide al usuario que elija un modo."""
    print("--- Elige un modo de operación ---")
    print("0. Ayuda")
    print("1. translate - Solo traduce sin re-empaquetar el .miz")
    print("2. miz       - Re-empaqueta el .miz sin traducir (inserta traducción previa si existe)")
    print("3. all       - Traduce y re-empaqueta todas las misiones del fichero")

    while True:
        choice = input("Introduce el número del modo (0, 1, 2, 3): ").strip()
        if choice == '0':
            show_help()
            continue
        elif choice == '1':
            return 'translate'
        elif choice == '2':
            return 'miz'
        elif choice == '3':
            return 'all'
        else:
            print("Opción no válida. Por favor, elige 0, 1, 2 o 3.")

def main():
    mode = get_interactive_mode()

    misiones_file = "misiones.txt"
    script_trad_path = "dcs_lua_translate.py"

    logging.info(f"Modo de operación elegido: {mode}")

    miz_to_process, global_args, output_base_dir = read_mission_list(misiones_file)

    if not miz_to_process:
        logging.error("No se encontraron misiones para procesar o hubo un error al leer misiones.txt. Saliendo.")
        return

    if mode == "all":
        logging.warning("El modo 'all' solo procesará las misiones listadas en el fichero, no las del directorio.")

    for i, (miz_path, lua_name, campaign_name, translate_args) in enumerate(miz_to_process):
        logging.info("---")
        logging.info(f"Procesando misión {i+1} de {len(miz_to_process)}: {os.path.basename(miz_path)}")

        miz_base_name = os.path.splitext(os.path.basename(miz_path))[0]
        temp_dir = os.path.join("temp_missions", miz_base_name)

        try:
            # En modos que re-empaquetan, primero backup
            if mode in ["miz", "all"]:
                backup_folder_path = os.path.join(output_base_dir, "backup")
                backup_miz(miz_path, backup_folder_path)

            # Siempre extrae para trabajar
            extract_miz(miz_path, temp_dir)

            # Ruta del archivo dentro del .miz
            lua_source_path = os.path.join(temp_dir, lua_name)
            if not os.path.exists(lua_source_path):
                logging.error(f"No se encontró el archivo '{lua_name}' en la misión descomprimida. Saltando.")
                continue

            if mode == "translate":
                # Copia el archivo a out_lua y traduce (NO re-empaqueta)
                lua_temp_name = f"{miz_base_name}.lua"
                lua_temp_path = os.path.join(OUTPUT_DIR, lua_temp_name)
                shutil.copy(lua_source_path, lua_temp_path)
                logging.info(f"Archivo '{lua_name}' copiado a '{lua_temp_path}' para la traducción.")

                final_args = translate_args if translate_args else global_args
                success = translate_lua(lua_temp_path, script_trad_path, final_args)
                if not success:
                    logging.warning(f"Falló la traducción de {os.path.basename(miz_path)}. Revisa logs.")
                else:
                    logging.info("Traducción finalizada. No se re-empaqueta en modo 'translate'.")

            elif mode == "miz":
                # NO llamar al modelo. Si existe un .translated.lua previo, insertarlo; si no, dejar original.
                translated_file_name = f"{miz_base_name}.translated.lua"
                translated_file_path = os.path.join(OUTPUT_DIR, translated_file_name)

                if os.path.exists(translated_file_path):
                    logging.info(f"Traducción previa encontrada: {translated_file_path}")
                    # Sustituye el dictionary dentro de la misión con el traducido previo
                    shutil.copy(translated_file_path, lua_source_path)
                    logging.info(f"Sustituido '{lua_name}' por traducción previa.")
                else:
                    logging.info("No hay traducción previa encontrada. Se re-empaqueta sin cambios.")

                # Re-empaquetar
                output_folder_name = f"finalizado_{campaign_name}"
                output_folder_path = os.path.join(output_base_dir, output_folder_name)
                os.makedirs(output_folder_path, exist_ok=True)
                output_miz_path = os.path.join(output_folder_path, os.path.basename(miz_path))
                compress_miz(temp_dir, output_miz_path)

            elif mode == "all":
                # Traducir y re-empaquetar (comportamiento original)
                lua_temp_name = f"{miz_base_name}.lua"
                lua_temp_path = os.path.join(OUTPUT_DIR, lua_temp_name)
                shutil.copy(lua_source_path, lua_temp_path)
                logging.info(f"Archivo '{lua_name}' copiado a '{lua_temp_path}' para la traducción.")

                final_args = translate_args if translate_args else global_args
                success = translate_lua(lua_temp_path, script_trad_path, final_args)

                if success:
                    translated_file_name = f"{miz_base_name}.translated.lua"
                    translated_file_path = os.path.join(OUTPUT_DIR, translated_file_name)
                    if not os.path.exists(translated_file_path):
                        logging.error(f"No se encontró el archivo traducido en la ruta esperada: {translated_file_path}")
                        raise FileNotFoundError(f"Archivo traducido no encontrado: {translated_file_path}")

                    shutil.move(translated_file_path, lua_source_path)
                    logging.info(f"Archivo traducido '{translated_file_path}' movido a '{lua_source_path}'.")

                    # Eliminar el archivo temporal original
                    if os.path.exists(lua_temp_path):
                        os.remove(lua_temp_path)

                    # Re-empaquetar
                    output_folder_name = f"finalizado_{campaign_name}"
                    output_folder_path = os.path.join(output_base_dir, output_folder_name)
                    os.makedirs(output_folder_path, exist_ok=True)
                    output_miz_path = os.path.join(output_folder_path, os.path.basename(miz_path))
                    compress_miz(temp_dir, output_miz_path)
                else:
                    logging.warning(f"La misión {os.path.basename(miz_path)} no se re-comprimió debido a un error de traducción.")

        except Exception as e:
            logging.error(f"Proceso interrumpido para {miz_path}: {e}")

    logging.info("---")
    logging.info("Proceso de orquestación finalizado. Revisa el log para los detalles.")

if __name__ == "__main__":
    main()
