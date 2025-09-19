#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import zipfile
import subprocess
import logging
import threading
import sys
import json
from typing import List, Tuple, Dict
import shutil
import re, unicodedata, os
import shlex
import requests
import time
import glob
from datetime import datetime

# =========================
#  Logging global
# =========================
# =========================
#  Logging global
# =========================
GLOBAL_BASE = os.getcwd()
GLOBAL_OUT = os.path.join(GLOBAL_BASE, "log_orquestador")  # <— nombre pedido
os.makedirs(GLOBAL_OUT, exist_ok=True)

log_file_path = os.path.join(GLOBAL_OUT, f"orquestador_{os.getpid()}.log")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.findall(r'\d+|\D+', s)]

def _mission_num(name: str) -> int:
    # Normaliza, NBSP→espacio, tolera "C21 .miz" con espacio
    base = unicodedata.normalize("NFKC", name).replace("\u00A0", " ")
    m = re.search(r'-C\s*(\d+)', base, flags=re.I)
    return int(m.group(1)) if m else float('inf')

def _mission_sort_key(path: str):
    base = os.path.basename(path)
    num = _mission_num(base)
    # desempate estable y “natural”
    compact = re.sub(r'\s+', '', base)
    return (num, _natural_key(compact))

def find_miz_files_grouped(campaign_path: str):
    """Devuelve (normales, fc) ya ordenadas por C#."""
    all_miz = [os.path.join(campaign_path, f)
               for f in os.listdir(campaign_path)
               if f.lower().endswith(".miz")]
    normals = [p for p in all_miz if "-FC-" not in os.path.basename(p)]
    fcs     = [p for p in all_miz if "-FC-" in  os.path.basename(p)]

    normals.sort(key=_mission_sort_key)
    fcs.sort(key=_mission_sort_key)
    return normals, fcs

def ask_include_fc() -> bool:
    while True:
        ans = input("¿Incluir misiones Flaming Cliffs (-FC-)? [s/N]: ").strip().lower()
        if ans in ("", "n", "no"): return False
        if ans in ("s", "si", "sí", "y", "yes"): return True
        print("Responde 's' o 'n'.")

def pick_missions_grouped(normals, fcs, include_fc: bool):
    """
    Muestra dos bloques. Si include_fc=False, solo muestra normales.
    Devuelve índices sobre la lista combinada (normales + fcs si procede).
    """
    combined = list(normals)
    print("\n--- Misiones ---")
    # Bloque 1: normales
    for i, p in enumerate(normals, 1):
        print(f"{i}. {os.path.basename(p)}")

    start_fc_idx = len(normals) + 1
    if include_fc and fcs:
        print("\n--- Flaming Cliffs ---")
        for i, p in enumerate(fcs, start_fc_idx):
            print(f"{i}. {os.path.basename(p)}")
        combined.extend(fcs)

    print("A. Todas")

    # Reutiliza tu parseador de rangos existente
    while True:
        sel = input("Elige misiones (ej. 1 o 1,3-5 o A): ").strip().upper()
        if sel == "A":
            return list(range(len(combined))), combined
        idxs = parse_index_list(sel, len(combined))
        if idxs:
            return idxs, combined
        print("Selección no válida.")

def get_deploy_base_dir(cfg: dict, campaign_name: str, campaign_path: str) -> str:
    """
    Base destino de despliegue:
      - Si config.txt tiene DEPLOY_DIR: usar DEPLOY_DIR/<campaign_name>
      - Si no: usar la propia carpeta de campaña del juego (campaign_path)
    """
    base = cfg.get("DEPLOY_DIR", "").strip()
    if base:
        return os.path.join(base, campaign_name)
    return campaign_path

def ensure_deploy_dirs(base_dir: str, overwrite: bool) -> Tuple[str, str]:
    """
    Devuelve (deploy_dir, backup_dir). 
    - Si overwrite=False → deploy_dir = base_dir/Translated_ES
    - Si overwrite=True  → deploy_dir = base_dir
    backup_dir = base_dir/_deploy_backup
    """
    deploy_dir = base_dir if overwrite else os.path.join(base_dir, "Translated_ES")
    backup_dir = os.path.join(base_dir, "_deploy_backup")
    os.makedirs(deploy_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)
    return deploy_dir, backup_dir

def list_translated_outputs(finalizado_dir: str) -> List[str]:
    """Devuelve la lista de .miz reempaquetados disponibles en finalizado/."""
    if not os.path.isdir(finalizado_dir):
        return []
    out = [os.path.join(finalizado_dir, f) for f in os.listdir(finalizado_dir) if f.lower().endswith(".miz")]
    # Orden natural por nombre
    out.sort(key=_natural_key)
    return out

def pick_translated_to_deploy(translated_list: List[str]) -> List[int]:
    """Selector similar al de misiones, pero sobre finalizado/."""
    if not translated_list:
        print("No hay misiones reempaquetadas en 'finalizado/'.")
        return []

    print("\n--- Misiones traducidas disponibles (finalizado/) ---")
    for i, p in enumerate(translated_list, 1):
        print(f"{i}. {os.path.basename(p)}")
    print("A. Todas")

    while True:
        sel = input("Elige para desplegar (ej. 1 o 1,3-5 o A): ").strip().upper()
        if sel == "A":
            return list(range(len(translated_list)))
        idxs = parse_index_list(sel, len(translated_list))
        if idxs:
            return idxs
        print("Selección no válida.")

def deploy_missions(files: List[str], deploy_dir: str, backup_dir: str, overwrite: bool) -> None:
    """
    Copia las .miz al directorio de despliegue.
    - overwrite=False: siempre copia (no hay colisión, porque van a Translated_ES)
    - overwrite=True : si existe, hace backup con timestamp antes de sobrescribir
    """
    for src in files:
        base = os.path.basename(src)
        dst = os.path.join(deploy_dir, base)

        if overwrite and os.path.exists(dst):
            ts = time.strftime("%Y%m%d_%H%M%S")
            bak_name = f"{base}.{ts}.bak"
            bak_path = os.path.join(backup_dir, bak_name)
            logging.info("Backup previo de %s → %s", dst, bak_path)
            shutil.copy2(dst, bak_path)

        logging.info("Desplegando %s → %s", base, deploy_dir)
        shutil.copy2(src, dst)

    logging.info("Despliegue completado en: %s", deploy_dir)

# =========================
#  Utilidades de config simple
# =========================
def parse_simple_config(path: str) -> Dict[str, str]:
    """
    Lee un fichero de texto KEY: VALUE (líneas con '#...' se ignoran).
    Claves esperadas: ROOT_DIR, FILE_TARGET, ARGS
    """
    cfg = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip().upper()
            v = v.strip().strip('"').strip("'")
            cfg[k] = v
    missing = [k for k in ["ROOT_DIR", "FILE_TARGET"] if k not in cfg]
    if missing:
        raise ValueError(f"Faltan claves en {path}: {', '.join(missing)}")
    return cfg

def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s\-\.áéíóúüñÁÉÍÓÚÜÑ]", "_", name, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s)
    return s

def list_campaigns(root_dir: str) -> List[Tuple[str, str]]:
    """
    Devuelve [(nombre_campaña, ruta_abs)] para cada subcarpeta que contenga .miz
    """
    out = []
    if not os.path.isdir(root_dir):
        return out
    for entry in sorted(os.listdir(root_dir)):
        p = os.path.join(root_dir, entry)
        if os.path.isdir(p):
            mizs = [f for f in os.listdir(p) if f.lower().endswith(".miz")]
            if mizs:
                out.append((entry, p))
    return out

def find_miz_files(campaign_path: str) -> list[str]:
    miz_list = [os.path.join(campaign_path, f)
                for f in os.listdir(campaign_path)
                if f.lower().endswith(".miz")]
    miz_list.sort(key=_mission_sort_key)
    return miz_list

def ensure_campaign_local_dirs(campaign_name: str) -> Dict[str, str]:
    base = os.path.join(GLOBAL_BASE, "campaings", slugify(campaign_name))
    paths = {
        "base": base,
        "extracted": os.path.join(base, "extracted"),
        "out_lua": os.path.join(base, "out_lua"),
        "finalizado": os.path.join(base, "finalizado"),
        "backup": os.path.join(base, "backup"),
        "misiones_txt": os.path.join(base, "misiones.txt"),
    }
    for k, p in paths.items():
        if k == "misiones_txt":
            continue
        os.makedirs(p, exist_ok=True)

    # Ya NO añadimos otro handler de log por campaña
    return paths

def harvest_translator_logs(from_output_dir: str, campaign_name: str, mission_base: str):
    """
    Mueve logs dcs_translate_*.log desde el output_dir del traductor a GLOBAL_OUT,
    renombrándolos con campaña y misión para evitar colisiones.
    """
    if not from_output_dir or not os.path.isdir(from_output_dir):
        return
    pattern = os.path.join(from_output_dir, "dcs_translate_*.log")
    for src in glob.glob(pattern):
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_campaign = slugify(campaign_name)
            safe_mission = slugify(mission_base)
            dst_name = f"{safe_campaign}__{safe_mission}__{os.path.basename(src)}"
            dst = os.path.join(GLOBAL_OUT, dst_name)
            shutil.move(src, dst)
            logging.info("Log del traductor movido a: %s", dst)
        except Exception as e:
            logging.warning("No se pudo mover log del traductor %s → %s: %s", src, GLOBAL_OUT, e)

def zip_campaign_logs(campaign_name: str, orchestrator_log_path: str, remove_after: bool = False) -> str:
    """
    Crea un ZIP por campaña con:
      - Todos los logs del traductor recolectados en GLOBAL_OUT (prefijo <campaña>__*)
      - El log del orquestador de esta sesión.
    Devuelve la ruta del .zip generado.
    Si remove_after=True, elimina los .log originales tras comprimir.
    """
    safe_campaign = slugify(campaign_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(GLOBAL_OUT, f"logs_{safe_campaign}_{timestamp}.zip")

    # Reunir candidatos
    pattern = os.path.join(GLOBAL_OUT, f"{safe_campaign}__*.log")
    candidates = glob.glob(pattern)

    # Incluye también el log del orquestador
    include_orq = []
    if orchestrator_log_path and os.path.isfile(orchestrator_log_path):
        include_orq = [orchestrator_log_path]

    if not candidates and not include_orq:
        logging.info("No hay logs que comprimir para la campaña %s.", campaign_name)
        return ""

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Logs del traductor (guardamos con su mismo nombre)
        for src in candidates:
            arcname = os.path.basename(src)
            zf.write(src, arcname)

        # Log del orquestador (nombre fijo dentro del zip)
        for src in include_orq:
            zf.write(src, arcname="orquestador_session.log")

    logging.info("ZIP de logs creado: %s", zip_path)

    if remove_after:
        for src in candidates + include_orq:
            try:
                os.remove(src)
            except Exception as e:
                logging.warning("No se pudo eliminar %s tras zip: %s", src, e)

    return zip_path


# =========================
#  ZIP helpers
# =========================
def extract_miz(miz_path: str, dest_dir: str):
    """
    Extrae un .miz en dest_dir (limpia antes si existía).
    """
    logging.info(f"Descomprimiendo: {miz_path} → {dest_dir}")
    try:
        if os.path.isdir(dest_dir):
            shutil.rmtree(dest_dir, ignore_errors=True)
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(miz_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        logging.info("Descompresión completada.")
    except Exception as e:
        logging.error(f"Error al descomprimir {miz_path}: {e}")
        raise

def compress_miz(src_dir: str, output_miz_path: str):
    """
    Comprime el contenido de src_dir → output_miz_path (.miz)
    """
    logging.info(f"Comprimiendo {src_dir} → {output_miz_path}")
    try:
        os.makedirs(os.path.dirname(output_miz_path), exist_ok=True)
        with zipfile.ZipFile(output_miz_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            for root, _, files in os.walk(src_dir):
                for file in files:
                    fp = os.path.join(root, file)
                    arcname = os.path.relpath(fp, src_dir)
                    zip_ref.write(fp, arcname)
        logging.info("Compresión completada.")
    except Exception as e:
        logging.error(f"Error al comprimir {output_miz_path}: {e}")
        raise

def backup_miz(miz_path: str, backup_dir: str):
    try:
        os.makedirs(backup_dir, exist_ok=True)
        dst = os.path.join(backup_dir, os.path.basename(miz_path))
        logging.info(f"Backup: {miz_path} → {dst}")
        shutil.copy2(miz_path, dst)
    except Exception as e:
        logging.error(f"Error creando backup: {e}")
        raise

# =========================
#  LM Studio helpers (auto-load modelo)
# =========================
DEFAULT_LM_URL = "http://localhost:1234/v1"
LMSTUDIO_CLI = os.environ.get("LMSTUDIO_CLI", "lms")  # cambia si usas otra ruta

def list_lmstudio_models(lm_url: str) -> list:
    try:
        r = requests.get(f"{lm_url.rstrip('/')}/models", timeout=5)
        r.raise_for_status()
        js = r.json() or {}
        return [m.get("id", "") for m in (js.get("data") or [])]
    except Exception as e:
        logging.debug("list_lmstudio_models fallo: %s", e)
        return []

def resolve_model_id(lm_url: str, requested: str) -> str | None:
    """Devuelve el id exacto si existe; si no, mejor coincidencia por substring (útil para -it / -instruct)."""
    ids = list_lmstudio_models(lm_url)
    if not ids:
        return None
    if requested in ids:
        return requested
    req = (requested or "").lower()
    cands = [mid for mid in ids if req and req in mid.lower()]
    if not cands:
        return None
    # Prioriza instruct (-it, -instruct) y cadenas más cortas
    cands.sort(key=lambda s: (("it" not in s.lower() and "instruct" not in s.lower()), len(s)))
    return cands[0]

def ensure_lmstudio_model_loaded(
    lm_url: str,
    lm_model: str | None,
    identifier: str | None,
    timeout_s: int = 180,
    cli_path: str | None = None
) -> str | None:
    """
    Política estricta:
    - Si lm_model está cargado → devuelve EXACTAMENTE ese id (coincidencia exacta o por normalización).
    - Si no está cargado:
        * si hay identifier → lms load --identifier <identifier> (silencioso).
        * si NO hay identifier pero hay lm_model → lms load <lm_model>.
    - Tras cargar, valida de nuevo que 'lm_model' (o un alias casi idéntico) está en /models.
    - NO hace fallback al “primer modelo disponible”.
    - NO pregunta nada al usuario.
    """
    cli = cli_path or LMSTUDIO_CLI

    def _normalize(s: str) -> str:
        # Normaliza separadores y mayúsculas para comparar IDs equivalentes
        return (s or "").strip().replace("\\", "/").lower()

    want = _normalize(lm_model) if lm_model else None

    # 1) ¿ya está cargado?
    current = list_lmstudio_models(lm_url)
    if current:
        # Coincidencia exacta o normalizada
        for mid in current:
            if mid == (lm_model or "") or _normalize(mid) == want:
                logging.info("Modelo ya cargado en LM Studio: '%s'", mid)
                return mid

    # 2) Cargar SIN preguntar (si nos diste cómo)
    try:
        if identifier:
            logging.info("Cargando modelo con --identifier (silencioso): %s", identifier)
            subprocess.run([cli, "load", "--identifier", identifier], check=True)
        elif lm_model:
            logging.info("Cargando modelo por --lm-model (silencioso): %s", lm_model)
            subprocess.run([cli, "load", lm_model], check=True)
        else:
            logging.error("No se proporcionó --lm-model ni --identifier; imposible cargar modelo.")
            return None
    except FileNotFoundError:
        logging.error("CLI '%s' no encontrado en PATH. Carga el modelo manualmente o define LMSTUDIO_CLI.", cli)
        return None
    except subprocess.CalledProcessError as e:
        logging.error("Fallo al cargar el modelo (%s). Revisa el nombre/identifier.", e)
        return None

    # 3) Polling hasta que esté cargado el modelo solicitado (sin listar en INFO)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ids = list_lmstudio_models(lm_url)
        # Busca coincidencia exacta o normalizada con lo pedido
        for mid in ids:
            if lm_model and (mid == lm_model or _normalize(mid) == want):
                logging.info("Modelo cargado y listo: '%s'", mid)
                return mid
        time.sleep(1.5)

    logging.error("Tiempo de espera agotado. No aparece '%s' en /models.", lm_model or identifier or "(sin nombre)")
    return None

def parse_lm_flags(args_str: str, fallback_url: str = DEFAULT_LM_URL) -> tuple[str | None, str, str | None]:
    """
    Extrae --lm-model, --lm-url y --identifier de una cadena de ARGS. Devuelve (model, url, identifier).
    Soporta '--flag valor' y '--flag=valor'.
    """
    if not args_str:
        return (None, fallback_url, None)

    try:
        tokens = shlex.split(args_str, posix=(os.name != "nt"))
    except Exception:
        tokens = args_str.split()

    model = None
    url = None
    ident = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--lm-model" and i + 1 < len(tokens):
            model = tokens[i + 1]; i += 2; continue
        if tok.startswith("--lm-model="):
            model = tok.split("=", 1)[1]; i += 1; continue
        if tok == "--lm-url" and i + 1 < len(tokens):
            url = tokens[i + 1]; i += 2; continue
        if tok.startswith("--lm-url="):
            url = tok.split("=", 1)[1]; i += 1; continue
        if tok == "--identifier" and i + 1 < len(tokens):
            ident = tokens[i + 1]; i += 2; continue
        if tok.startswith("--identifier="):
            ident = tok.split("=", 1)[1]; i += 1; continue
        i += 1

    return (model, url or fallback_url, ident)

def remove_arg(tokens: list[str], name: str) -> list[str]:
    """Elimina --name valor y --name=valor."""
    out = []
    skip = False
    for i, t in enumerate(tokens):
        if skip:
            skip = False
            continue
        if t == name:
            skip = True
            continue
        if t.startswith(name + "="):
            continue
        out.append(t)
    return out

def upsert_arg(args_str: str, name: str, value: str) -> str:
    """Añade o reemplaza un argumento. Devuelve string de ARGS listo para pasar a translate_lua."""
    try:
        tokens = shlex.split(args_str or "", posix=(os.name != "nt"))
    except Exception:
        tokens = (args_str or "").split()
    tokens = remove_arg(tokens, name)
    tokens += [name, value]

    # Reconstrucción: evita comillas POSIX en Windows
    if os.name == "nt":
        def q(x: str) -> str:
            return f"\"{x}\"" if (" " in x and not x.startswith('"')) else x
        return " ".join(q(t) for t in tokens)
    else:
        return shlex.join(tokens)

# =========================
#  Traducción (subproceso)
# =========================
def _remove_output_dir_tokens(argv: list) -> list:
    """Elimina cualquier --output-dir previo (formas '--output-dir valor' y '--output-dir=valor')."""
    res = []
    skip_next = False
    for i, tok in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if tok == "--output-dir":
            skip_next = True  # saltar el valor
            continue
        if tok.startswith("--output-dir="):
            continue
        res.append(tok)
    return res

def _pick_latest_log(log_dir: str) -> str | None:
    """
    Devuelve la ruta del dcs_translate_*.log más reciente en log_dir, o None si no hay.
    """
    try:
        files = glob.glob(os.path.join(log_dir, "dcs_translate_*.log"))
        if not files:
            return None
        files.sort(key=lambda p: os.path.getmtime(p))
        return files[-1]
    except Exception:
        return None

def _tail_file_worker(stop_evt: threading.Event, file_getter, prefix: str = "[TAIL] "):
    """
    Hace tail continuo sobre el fichero devuelto por file_getter().
    Si el fichero cambia (nuevo log), salta al nuevo.
    """
    current_path = None
    fp = None
    pos = 0

    while not stop_evt.is_set():
        try:
            new_path = file_getter()
            if new_path and new_path != current_path:
                # Cierra el anterior y abre el nuevo desde el final
                if fp:
                    try:
                        fp.close()
                    except Exception:
                        pass
                current_path = new_path
                try:
                    fp = open(current_path, "r", encoding="utf-8", errors="replace")
                    fp.seek(0, os.SEEK_END)
                    pos = fp.tell()
                except Exception:
                    fp = None

            if fp:
                line = fp.readline()
                if not line:
                    # no hay nuevas líneas aún
                    time.sleep(0.3)
                else:
                    # imprime en consola sin romper el logger
                    sys.stdout.write(prefix + line)
                    sys.stdout.flush()
            else:
                time.sleep(0.3)

        except Exception:
            time.sleep(0.5)

    # limpieza
    if fp:
        try:
            fp.close()
        except Exception:
            pass

def translate_lua(lua_path: str,
                  dcs_translate_script: str,
                  extra_args: str = "",
                  force_output_dir: str | None = None) -> bool:
    """
    Llama al script dcs_lua_translate.py como subproceso y hace tail en vivo de dcs_translate_*.log
    del directorio --output-dir (forzado si se pasa force_output_dir).
    """
    logging.info("Iniciando traducción para: %s", lua_path)

    # Comando base
    cmd = ["python", dcs_translate_script, lua_path]

    # Parseo robusto de ARGS (respeta comillas y espacios)
    parsed_args = []
    if extra_args:
        try:
            parsed_args = shlex.split(extra_args, posix=(os.name != "nt"))
        except ValueError as e:
            logging.error("No se pudieron parsear ARGS con shlex.split: %s", e)
            logging.warning("Fallback a .split(); puede romper comillas.")
            parsed_args = extra_args.split()

    # Forzar --output-dir si se nos dio paths["out_lua"]
    if force_output_dir:
        parsed_args = _remove_output_dir_tokens(parsed_args)
        parsed_args += ["--output-dir", force_output_dir]

    cmd.extend(parsed_args)

    # Bonito para log
    try:
        pretty_cmd = " ".join([shlex.quote(x) if os.name != "nt" else x for x in cmd])
    except Exception:
        pretty_cmd = " ".join(cmd)
    logging.info("Comando de traducción: %s", pretty_cmd)

    # ------ Tail en vivo del log del traductor ------
    # Resolver el directorio donde el traductor escribirá sus logs.
    # Por convención, dcs_lua_translate.py crea dcs_translate_*.log en --output-dir.
    tail_dir = force_output_dir if force_output_dir else (
        # Si no forzamos, intenta deducir de --output-dir en extra_args
        (lambda toks: toks[toks.index("--output-dir")+1] if "--output-dir" in toks else None)(
            parsed_args if parsed_args else []
        )
    )
    # Si no hay manera de saberlo, no hacemos tail (pero seguimos traduciendo)
    stop_evt = threading.Event()
    tail_thread = None
    if tail_dir and os.path.isdir(tail_dir):
        # función que dice “cuál es el último log ahora”
        getter = lambda: _pick_latest_log(tail_dir)
        tail_thread = threading.Thread(target=_tail_file_worker, args=(stop_evt, getter), daemon=True)
        tail_thread.start()
        logging.info("Tail de logs activado en: %s", tail_dir)
    else:
        logging.info("Tail de logs no disponible (no se resolvió --output-dir).")

    # ------ Ejecutar el traductor en Popen para permitir tail paralelo ------
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        # lee stdout/err sin bloquear el tail (polling suave)
        out_buf, err_buf = [], []
        while True:
            ret = proc.poll()
            # lee todo lo disponible (línea a línea)
            if proc.stdout:
                line = proc.stdout.readline()
                if line:
                    out_buf.append(line)
                    # baja a DEBUG para no ensuciar consola: ya ves el tail
                    logging.debug("[TRAD-STDOUT] %s", line.rstrip("\n"))
            if proc.stderr:
                line = proc.stderr.readline()
                if line:
                    err_buf.append(line)
                    logging.debug("[TRAD-STDERR] %s", line.rstrip("\n"))

            if ret is not None:
                break
            time.sleep(0.15)

        # asegurar vaciado
        if proc.stdout:
            rest = proc.stdout.read()
            if rest: out_buf.append(rest)
        if proc.stderr:
            rest = proc.stderr.read()
            if rest: err_buf.append(rest)

        ok = (proc.returncode == 0)
        if not ok:
            logging.error("El traductor falló (exit %s).", proc.returncode)
            if out_buf:
                logging.error("stdout (≤4000 chars):\n%s", "".join(out_buf)[:4000])
            if err_buf:
                logging.error("stderr (≤4000 chars):\n%s", "".join(err_buf)[:4000])
            logging.error("Revisa el log de 'dcs_lua_translate.py' para más detalles.")
            return False

        logging.info("Traducción completada exitosamente.")
        return True

    except FileNotFoundError:
        logging.error("No se encontró el script de traducción: %s", dcs_translate_script)
        return False

    except Exception as e:
        logging.exception("Error al ejecutar traductor: %s", e)
        return False

    finally:
        # parar tail si estaba activo
        if stop_evt:
            stop_evt.set()
        if tail_thread and tail_thread.is_alive():
            tail_thread.join(timeout=2.0)

# =========================
#  CLI / selección
# =========================
def read_config_args() -> Tuple[str, str, str, str]:
    """
    Parsea CLI: --config y --translator opcional.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Orquestador de traducciones DCS por campañas.")
    parser.add_argument("--config", required=True, help="Ruta a config.txt (con ROOT_DIR, FILE_TARGET, ARGS).")
    parser.add_argument("--translator", default="dcs_lua_translate.py", help="Ruta al script traductor.")
    args = parser.parse_args()
    return args.config, args.translator, os.path.abspath(args.translator), os.path.abspath(args.config)

def pick_mode() -> str:
    print("--- Elige modo ---")
    print("1) translate  (extrae y traduce; NO reempaqueta)")
    print("2) miz        (NO traduce; reempaqueta; inserta traducción si existe)")
    print("3) all        (traduce y reempaqueta)")
    print("4) deploy     (copiar .miz finalizados al directorio del juego)")
    while True:
        c = input("Opción (1/2/3/4): ").strip()
        if c == "1": return "translate"
        if c == "2": return "miz"
        if c == "3": return "all"
        if c == "4": return "deploy"
        print("Opción no válida.")

def pick_campaign(campaigns: List[Tuple[str, str]]) -> List[int]:
    """
    Muestra campañas y permite elegir una/s.
    Devuelve lista de índices seleccionados (0-based).
    """
    print("\n--- Campañas detectadas ---")
    for i, (name, _) in enumerate(campaigns, 1):
        print(f"{i}. {name}")
    print("A. Todas")

    while True:
        sel = input("Elige campaña(s) (por ej. 1 o 1,3-4 o A): ").strip().upper()
        if sel == "A":
            return list(range(len(campaigns)))
        idxs = parse_index_list(sel, len(campaigns))
        if idxs:
            return idxs
        print("Selección no válida.")

def pick_missions(miz_list: List[str]) -> List[int]:
    print("\n--- Misiones ---")
    for i, p in enumerate(miz_list, 1):
        print(f"{i}. {os.path.basename(p)}")
    print("A. Todas")
    while True:
        sel = input("Elige misiones (ej. 1 o 1,3-5 o A): ").strip().upper()
        if sel == "A":
            return list(range(len(miz_list)))
        idxs = parse_index_list(sel, len(miz_list))
        if idxs:
            return idxs
        print("Selección no válida.")

def parse_index_list(s: str, max_len: int) -> List[int]:
    """
    '1,3-5,8' → [0,2,3,4,7] (0-based). Devuelve [] si inválido.
    """
    try:
        out = set()
        for part in s.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                a = int(a); b = int(b)
                if a < 1 or b < 1 or a > b or b > max_len: return []
                out.update(range(a-1, b))
            else:
                i = int(part)
                if i < 1 or i > max_len: return []
                out.add(i-1)
        return sorted(out)
    except Exception:
        return []

def show_help():
    print("\n--- AYUDA ---")
    print("Ejemplo de config.txt:")
    print(r"""ROOT_DIR: D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns
FILE_TARGET: l10n/DEFAULT/dictionary
ARGS: --config D:\ruta\mi_config.yaml --lm-url http://localhost:1234/v1 --lm-model qwen1.5-72b-chat-abliterated-i1 --identifier huggingface://Qwen/Qwen1.5-72B-Chat-GGUF/Q8_0 --lm-compat chat --batch-size 12 --timeout 240""")
    print("\nEjecución:")
    print(r'  python orquestador.py --config "D:\ruta\config.txt"')
    print("El script crea ./campaings/<campaña>/ con extracted/, out_lua/, finalizado/, backup/ y misiones.txt\n")

# =========================
#  MAIN
# =========================
def main():
    # 1) CLI: --config y --translator
    try:
        config_txt, translator_cli, translator_abs, config_abs = read_config_args()
    except SystemExit:
        return
    except Exception as e:
        logging.error("Error de argumentos: %s", e)
        return

    # 2) Cargar config.txt (ROOT_DIR, FILE_TARGET, ARGS, opcional DEPLOY_*)
    try:
        cfg = parse_simple_config(config_txt)
    except Exception as e:
        logging.error("No se pudo leer config: %s", e)
        show_help()
        return

    ROOT_DIR   = cfg.get("ROOT_DIR")
    FILE_TARGET= cfg.get("FILE_TARGET")
    ARGS       = cfg.get("ARGS", "")

    logging.info("CONFIG:")
    logging.info("  ROOT_DIR   = %s", ROOT_DIR)
    logging.info("  FILE_TARGET= %s", FILE_TARGET)
    logging.info("  ARGS       = %s", ARGS)
    logging.info("  TRANSLATOR = %s", translator_abs)

    # 3) Descubrir campañas
    campaigns = list_campaigns(ROOT_DIR)
    if not campaigns:
        logging.error("No se encontraron campañas con .miz en: %s", ROOT_DIR)
        return

    # 4) Elegir modo y campañas
    mode = pick_mode()   # translate | miz | all | deploy
    sel_camps = pick_campaign(campaigns)

    # 5) Procesar campañas seleccionadas
    for idx in sel_camps:
        campaign_name, campaign_path = campaigns[idx]
        paths = ensure_campaign_local_dirs(campaign_name)
        
        # Generar listado agrupado (normales y FC), ordenado por número C#
        normals, fcs = find_miz_files_grouped(campaign_path)

        # misiones.txt informativo: primero normales, luego FC (si hay)
        with open(paths["misiones_txt"], "w", encoding="utf-8") as f:
            for p in normals:
                f.write(os.path.basename(p) + "\n")
            if fcs:
                f.write("\n# --- Flaming Cliffs ---\n")
                for p in fcs:
                    f.write(os.path.basename(p) + "\n")

        total = len(normals) + len(fcs)
        logging.info("Misiones detectadas en %s: %d (normales=%d, FC=%d)",
                    campaign_name, total, len(normals), len(fcs))

        # =============== NUEVO MODO: DEPLOY ===============
        if mode == "deploy":
            translated = list_translated_outputs(paths["finalizado"])
            sel = pick_translated_to_deploy(translated)
            if not sel:
                logging.info("Nada que desplegar en %s.", campaign_name)
                continue

            overwrite_flag = str(cfg.get("DEPLOY_OVERWRITE", "false")).strip().lower() in ("1","true","yes","y","si","sí")
            base_dest = get_deploy_base_dir(cfg, campaign_name, campaign_path)
            deploy_dir, backup_dir = ensure_deploy_dirs(base_dest, overwrite_flag)

            chosen = [translated[i] for i in sel]
            deploy_missions(chosen, deploy_dir, backup_dir, overwrite_flag)
            continue
        # ===================================================

        if total == 0:
            logging.warning("Sin misiones .miz en %s", campaign_path)
            continue

        # Pregunta si mostrar el bloque FC y selector agrupado
        include_fc = ask_include_fc()
        sel_indices, combined = pick_missions_grouped(normals, fcs, include_fc)
        if not sel_indices:
            logging.info("No se seleccionaron misiones en %s.", campaign_name)
            continue

        # 6) Bucle por misiones seleccionadas (usando la lista combinada que vio el usuario)
        for j in sel_indices:
            miz_path = combined[j]
            miz_base = os.path.splitext(os.path.basename(miz_path))[0]
            extract_dir = os.path.join(paths["extracted"], miz_base)

            try:
                if mode in ("miz", "all"):
                    backup_miz(miz_path, paths["backup"])

                extract_miz(miz_path, extract_dir)

                lua_source_path = os.path.join(extract_dir, FILE_TARGET)
                if not os.path.exists(lua_source_path):
                    logging.error("No existe %s dentro de %s. Se salta misión.", FILE_TARGET, miz_path)
                    continue

                if mode == "translate":
                    lua_temp_path = os.path.join(paths["out_lua"], f"{miz_base}.lua")
                    shutil.copy(lua_source_path, lua_temp_path)
                    logging.info("Preparado para traducir: %s", lua_temp_path)

                    ok = translate_lua(lua_temp_path, translator_abs, ARGS, paths["out_lua"])
                    if not ok:
                        logging.warning("Falló traducción de %s", miz_base)
                    else:
                        logging.info("Traducción completa (no se reempaqueta en 'translate').")

                elif mode == "miz":
                    translated_file = os.path.join(paths["out_lua"], f"{miz_base}.translated.lua")
                    if os.path.exists(translated_file):
                        logging.info("Traducción previa encontrada: %s", translated_file)
                        shutil.copy(translated_file, lua_source_path)
                        logging.info("Insertado %s en el .miz extraído.", os.path.basename(translated_file))
                    else:
                        logging.info("Sin traducción previa; se deja el original.")

                    out_miz = os.path.join(paths["finalizado"], os.path.basename(miz_path))
                    compress_miz(extract_dir, out_miz)

                elif mode == "all":
                    lua_temp_path = os.path.join(paths["out_lua"], f"{miz_base}.lua")
                    shutil.copy(lua_source_path, lua_temp_path)
                    logging.info("Preparado para traducir: %s", lua_temp_path)

                    ok = translate_lua(lua_temp_path, translator_abs, ARGS, paths["out_lua"])
                    if not ok:
                        logging.warning("Falló traducción de %s; no se reempaqueta.", miz_base)
                        continue

                    translated_file = os.path.join(paths["out_lua"], f"{miz_base}.translated.lua")
                    if not os.path.exists(translated_file):
                        logging.error("No se encontró salida traducida: %s", translated_file)
                        continue

                    shutil.copy(translated_file, lua_source_path)
                    out_miz = os.path.join(paths["finalizado"], os.path.basename(miz_path))
                    compress_miz(extract_dir, out_miz)

            except Exception as e:
                logging.error("Error procesando %s: %s", miz_path, e)

            logging.info("=== FIN ORQUESTADOR ===")
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Interrumpido por el usuario.")