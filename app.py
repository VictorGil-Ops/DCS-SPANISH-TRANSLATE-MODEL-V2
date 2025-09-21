#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, unicodedata, zipfile, shutil, logging, shlex, glob, time, threading, signal
from datetime import datetime
from typing import List, Tuple, Dict
import subprocess, requests, json
from flask import Flask, request, jsonify, render_template_string, make_response

# =========================
#  Logging / rutas globales
# =========================
BASE_DIR = os.getcwd()
LOG_DIR  = os.path.join(BASE_DIR, "log_orquestador")
os.makedirs(LOG_DIR, exist_ok=True)
log_file_path = os.path.join(LOG_DIR, f"web_orquestador_{os.getpid()}.log")
ERROR_LOG_PATH = os.path.join(LOG_DIR, "error.log")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(log_file_path, encoding="utf-8"), logging.StreamHandler()]
)

# ===== Versión de la app (leer de env o archivo VERSION) =====
def _read_version():
    v = os.environ.get("ORQ_VERSION", "").strip()
    if v:
        return v
    try:
        with open(os.path.join(BASE_DIR, "VERSION"), "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return "dev"

APP_VERSION = _read_version()

DEFAULT_LM_URL = "http://localhost:1234/v1"
LMSTUDIO_CLI = os.environ.get("LMSTUDIO_CLI", "lms")  # opcional, ruta al CLI

# =========================
#  Utilidades LM Studio
# =========================
def parse_lm_flags(args_str: str, fallback_url: str = DEFAULT_LM_URL):
    if not args_str:
        return (None, fallback_url, None)
    try:
        tokens = shlex.split(args_str, posix=(os.name != "nt"))
    except Exception:
        tokens = args_str.split()

    model = None; url = None; ident = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--lm-model" and i + 1 < len(tokens):
            model = tokens[i+1]; i += 2; continue
        if tok.startswith("--lm-model="):
            model = tok.split("=", 1)[1]; i += 1; continue
        if tok == "--lm-url" and i + 1 < len(tokens):
            url = tokens[i+1]; i += 2; continue
        if tok.startswith("--lm-url="):
            url = tok.split("=", 1)[1]; i += 1; continue
        if tok == "--identifier" and i + 1 < len(tokens):
            ident = tokens[i+1]; i += 2; continue
        if tok.startswith("--identifier="):
            ident = tok.split("=", 1)[1]; i += 1; continue
        i += 1
    return (model, url or fallback_url, ident)

def _normalize_id(s: str) -> str:
    return (s or "").strip().replace("\\", "/").lower()

def list_lmstudio_models(lm_url: str) -> list[str]:
    try:
        r = requests.get(lm_url.rstrip("/") + "/models", timeout=5)
        r.raise_for_status()
        js = r.json() or {}
        return [m.get("id","") for m in (js.get("data") or []) if m.get("id")]
    except Exception:
        return []

def ensure_lm_model_loaded(lm_url: str, lm_model: str|None, identifier: str|None,
                           timeout_s: int = 180, cli: str = LMSTUDIO_CLI) -> tuple[bool,str]:
    want = _normalize_id(lm_model) if lm_model else None
    ids = list_lmstudio_models(lm_url)
    for mid in ids:
        if mid == (lm_model or "") or _normalize_id(mid) == want:
            return True, f"Modelo ya cargado: {mid}"

    if not lm_model and not identifier:
        return False, "Falta --lm-model o --identifier para autoload."

    try:
        if identifier:
            subprocess.run([cli, "load", "--identifier", identifier], check=True)
        else:
            subprocess.run([cli, "load", lm_model], check=True)
    except FileNotFoundError:
        return False, f"CLI '{cli}' no encontrado. Define LMSTUDIO_CLI o instala LM Studio CLI."
    except subprocess.CalledProcessError as e:
        return False, f"Error al cargar modelo vía CLI: {e}"

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ids = list_lmstudio_models(lm_url)
        for mid in ids:
            if lm_model and (mid == lm_model or _normalize_id(mid) == want):
                return True, f"Modelo cargado: {mid}"
        time.sleep(1.5)

    return False, f"No aparece '{lm_model or identifier}' en /models tras {timeout_s}s."

# ==== AUTO ROOT DETECTOR ====
def _windows_drives():
    letters = []
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{c}:\\"
        if os.path.exists(root):
            letters.append(f"{c}:")
    return letters

def _candidate_roots_for_drive(drive: str) -> list[str]:
    d = drive + "\\"
    cands = [
        os.path.join(d, "Program Files", "Eagle Dynamics", "DCS World", "Mods", "campaigns"),
        os.path.join(d, "Program Files (x86)", "Eagle Dynamics", "DCS World", "Mods", "campaigns"),
        os.path.join(d, "Program Files (x86)", "Steam", "steamapps", "common", "DCSWorld", "Mods", "campaigns"),
        os.path.join(d, "Program Files", "Steam", "steamapps", "common", "DCSWorld", "Mods", "campaigns"),
        os.path.join(d, "Program Files", "Eagle Dynamics", "DCS World OpenBeta", "Mods", "campaigns"),
        os.path.join(d, "Program Files (x86)", "Eagle Dynamics", "DCS World OpenBeta", "Mods", "campaigns"),
        os.path.join(d, "Program Files (x86)", "Steam", "steamapps", "common", "DCSWorldBeta", "Mods", "campaigns"),
    ]
    return cands

def _exists_dir(p: str) -> bool:
    try:
        return os.path.isdir(p)
    except Exception:
        return False

def _deep_scan_drive_for_dcs(drive: str, max_depth: int = 5, timeout_s: int = 10) -> list[str]:
    drive_root = drive + "\\"
    start = time.time()
    found = []
    target_tail_variants = [
        os.path.join("Eagle Dynamics", "DCS World", "Mods", "campaigns"),
        os.path.join("Eagle Dynamics", "DCS World OpenBeta", "Mods", "campaigns"),
    ]
    for root, dirs, files in os.walk(drive_root):
        if (time.time() - start) > timeout_s:
            break
        depth = root[len(drive_root):].count(os.sep)
        if depth > max_depth:
            dirs[:] = []
            continue
        for tail in target_tail_variants:
            cand = os.path.join(root, tail)
            if _exists_dir(cand):
                found.append(cand)
    uniq, seen = [], set()
    for p in found:
        np = os.path.normpath(p)
        if np not in seen:
            seen.add(np)
            uniq.append(np)
    return uniq

# =========================
#  Estado en memoria (web)
# =========================
RUN_STATE = {
    "running": False,
    "phase": "",
    "progress": 0,
    "detail": "",
    "error": "",
    "done": False,
    "canceled": False,
    "log_zip": "",
    "just_packaged": [],
    "errors": [],  # errores recientes para la UI (más nuevos primero)
}
CANCEL_EVT = threading.Event()
_ERRORS_LOCK = threading.Lock()
_ERRORS_MAX = 200  # tope en memoria para la UI

# =========================
#  Utilidades orquestador
# =========================
def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.findall(r"\d+|\D+", s)]

def _mission_num(name: str) -> int:
    base = unicodedata.normalize("NFKC", name).replace("\u00A0", " ")
    m = re.search(r"-C\s*(\d+)", base, flags=re.I)
    return int(m.group(1)) if m else float("inf")

def _mission_sort_key(path: str):
    base = os.path.basename(path)
    num = _mission_num(base)
    compact = re.sub(r"\s+", "", base)
    return (num, _natural_key(compact))

def find_campaigns(root_dir: str) -> List[Tuple[str, str]]:
    out = []
    if not os.path.isdir(root_dir): return out
    for entry in sorted(os.listdir(root_dir)):
        p = os.path.join(root_dir, entry)
        if os.path.isdir(p):
            mizs = [f for f in os.listdir(p) if f.lower().endswith(".miz")]
            if mizs: out.append((entry, p))
    return out

def find_miz_files_grouped(campaign_path: str):
    all_miz = [os.path.join(campaign_path, f) for f in os.listdir(campaign_path) if f.lower().endswith(".miz")]
    normals = [p for p in all_miz if "-FC-" not in os.path.basename(p)]
    fcs     = [p for p in all_miz if "-FC-" in  os.path.basename(p)]
    normals.sort(key=_mission_sort_key)
    fcs.sort(key=_mission_sort_key)
    return normals, fcs

def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s\-\.áéíóúüñÁÉÍÓÚÜÑ]", "_", name, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s)
    return s

def normalize_stem(s: str) -> str:
    if not s: return ""
    s = unicodedata.normalize("NFKC", s).replace("\u00A0", " ")
    return s.strip(" .")

def campaign_finalizado_dir(campaign_name: str) -> str:
    base = os.path.join(BASE_DIR, "campaings", slugify(campaign_name))
    return os.path.join(base, "finalizado")

def campaign_out_lua_dir(campaign_name: str) -> str:
    base = os.path.join(BASE_DIR, "campaings", slugify(campaign_name))
    return os.path.join(base, "out_lua")

def ensure_campaign_local_dirs(campaign_name: str) -> Dict[str, str]:
    base = os.path.join(BASE_DIR, "campaings", slugify(campaign_name))
    paths = {
        "base": base,
        "extracted": os.path.join(base, "extracted"),
        "out_lua": os.path.join(base, "out_lua"),
        "finalizado": os.path.join(base, "finalizado"),
        "backup": os.path.join(base, "backup"),
    }
    for p in paths.values():
        os.makedirs(p, exist_ok=True)
    return paths

def extract_miz(miz_path: str, dest_dir: str):
    if os.path.isdir(dest_dir): shutil.rmtree(dest_dir, ignore_errors=True)
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(miz_path, "r") as zf:
        zf.extractall(dest_dir)

def compress_miz(src_dir: str, output_miz_path: str):
    os.makedirs(os.path.dirname(output_miz_path), exist_ok=True)
    with zipfile.ZipFile(output_miz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, os.path.relpath(fp, src_dir))

def backup_miz(miz_path: str, backup_dir: str):
    os.makedirs(backup_dir, exist_ok=True)
    shutil.copy2(miz_path, os.path.join(backup_dir, os.path.basename(miz_path)))

# ====== Gestión de errores visibles y persistentes ======
def _prepend_text_file(path: str, text: str):
    """Escribe text al inicio del archivo 'path' (los más nuevos arriba)."""
    try:
        prev = ""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                prev = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
            if prev:
                fh.write("\n" + prev)
    except Exception as e:
        logging.error("No se pudo escribir error.log: %s", e)

def record_error(campaign: str, mission: str, message: str):
    """Guarda error en memoria (para la UI) y en log_orquestador/error.log (nuevo arriba)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"[{ts}] ERROR [{campaign}::{mission}]"
    block = f"{header}: {message}".strip()
    entry_ui = {"ts": ts, "campaign": campaign, "mission": mission, "message": message}

    with _ERRORS_LOCK:
        RUN_STATE["errors"].insert(0, entry_ui)
        if len(RUN_STATE["errors"]) > _ERRORS_MAX:
            RUN_STATE["errors"] = RUN_STATE["errors"][:_ERRORS_MAX]
        _prepend_text_file(ERROR_LOG_PATH, block)

# ===== LM Studio (autoload) =====
def ensure_model_loaded_if_needed(mode: str, ARGS: str):
    if mode not in ("translate", "all"):
        return
    lm_model, lm_url, identifier = parse_lm_flags(ARGS, DEFAULT_LM_URL)
    logging.info("LM Studio params: model=%r url=%r identifier=%r", lm_model, lm_url, identifier)
    if not (lm_model or identifier):
        return
    ids = list_lmstudio_models(lm_url)
    norm = (lm_model or "").strip().lower()
    if any((m == (lm_model or "")) or (m.strip().lower() == norm) for m in ids):
        logging.info("Modelo ya cargado: %s", lm_model); return
    try:
        if identifier:
            subprocess.run([LMSTUDIO_CLI, "load", "--identifier", identifier], check=True)
        else:
            subprocess.run([LMSTUDIO_CLI, "load", lm_model], check=True)
    except Exception as e:
        logging.error("No se pudo cargar el modelo: %s", e)

# ===== lanzar traductor =====
def _remove_output_dir_tokens(argv: list) -> list:
    res, skip = [], False
    for t in argv:
        if skip: skip = False; continue
        if t == "--output-dir": skip = True; continue
        if t.startswith("--output-dir="): continue
        res.append(t)
    return res

def translate_lua(lua_path: str, dcs_translate_script: str, ARGS: str, out_dir: str) -> bool:
    cmd = ["python", dcs_translate_script, lua_path]
    try:
        parsed = shlex.split(ARGS or "", posix=(os.name != "nt"))
    except Exception:
        parsed = (ARGS or "").split()
    parsed = _remove_output_dir_tokens(parsed) + ["--output-dir", out_dir]
    cmd.extend(parsed)

    creationflags = 0
    preexec_fn = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    else:
        preexec_fn = os.setsid

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=creationflags, preexec_fn=preexec_fn)
        while True:
            if CANCEL_EVT.is_set():
                _kill(proc)
                return False
            try:
                ret = proc.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                pass
        return ret == 0
    except Exception as e:
        logging.error("translate_lua error: %s", e)
        return False

def _kill(proc):
    try:
        if os.name == "nt":
            try: proc.send_signal(signal.CTRL_BREAK_EVENT)
            except Exception: proc.terminate()
        else:
            try: os.killpg(proc.pid, signal.SIGTERM)
            except Exception: proc.terminate()
        try: proc.wait(timeout=4)
        except Exception: proc.kill()
    except Exception:
        try: proc.kill()
        except Exception: pass

def _extract_errors_from_text(text: str) -> list[str]:
    """
    Intenta extraer bloques de ERROR de los logs del traductor.
    Busca líneas tipo: [YYYY-MM-DD HH:MM:SS] ERROR: ...
    Captura hasta la siguiente cabecera de fecha o EOF.
    """
    if not text:
        return []
    pattern = re.compile(
        r"^\[\d{4}-\d{2}-\d{2}[^]]*] *ERROR:.*?(?=^\[\d{4}-\d{2}-\d{2}| \Z)",
        flags=re.M | re.S
    )
    out = [m.group(0).strip() for m in pattern.finditer(text)]
    if not out and "ERROR:" in text:
        out = [text[text.index("ERROR:"):].strip()]
    return out

def harvest_translator_logs(from_output_dir: str, campaign_name: str, mission_base: str):
    """Mueve logs dcs_translate_*.log a LOG_DIR y registra errores extraídos con la misión."""
    if not from_output_dir or not os.path.isdir(from_output_dir): return
    pattern = os.path.join(from_output_dir, "dcs_translate_*.log")
    for src in glob.glob(pattern):
        try:
            try:
                with open(src, "r", encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
                for chunk in _extract_errors_from_text(txt):
                    record_error(campaign_name, mission_base, chunk)
            except Exception as e:
                logging.warning("No se pudo analizar %s: %s", src, e)

            safe_campaign = slugify(campaign_name)
            safe_mission  = slugify(mission_base)
            dst = os.path.join(LOG_DIR, f"{safe_campaign}__{safe_mission}__{os.path.basename(src)}")
            shutil.move(src, dst)
        except Exception as e:
            logging.warning("No se pudo mover log %s: %s", src, e)

def zip_campaign_logs(campaign_name: str) -> str:
    safe_c = slugify(campaign_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(LOG_DIR, f"logs_{safe_c}_{ts}.zip")
    candidates = glob.glob(os.path.join(LOG_DIR, f"{safe_c}__*.log"))
    if not candidates: return ""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in candidates: zf.write(src, os.path.basename(src))
    return zip_path

# =========================
#  Worker principal (thread)
# =========================
def run_orchestrator(payload: dict):
    CANCEL_EVT.clear()
    RUN_STATE.update({
        "running": True, "done": False, "error": "", "canceled": False,
        "progress": 0, "phase": "preparando", "detail": "", "just_packaged": []
    })

    try:
        ROOT_DIR    = payload["ROOT_DIR"]
        FILE_TARGET = payload["FILE_TARGET"]
        ARGS        = payload.get("ARGS", "")
        MODE        = payload["mode"]
        CAMP        = payload["campaign_name"]
        INCLUDE_FC  = bool(payload.get("include_fc", False))
        DEPLOY_DIR  = payload.get("DEPLOY_DIR", "").strip()
        DEP_OVER    = bool(payload.get("DEPLOY_OVERWRITE", False))
        translator  = os.path.abspath("dcs_lua_translate.py")

        ensure_model_loaded_if_needed(MODE, ARGS)

        camps = dict(find_campaigns(ROOT_DIR))
        if CAMP not in camps:
            raise RuntimeError(f"La campaña '{CAMP}' no se encuentra en {ROOT_DIR}")
        campaign_path = camps[CAMP]
        paths = ensure_campaign_local_dirs(CAMP)

        if MODE == "deploy":
            RUN_STATE["phase"] = "deploy"
            finalizados = [os.path.join(paths["finalizado"], f) for f in os.listdir(paths["finalizado"]) if f.lower().endswith(".miz")]
            if not finalizados:
                raise RuntimeError("No hay .miz en finalizado/ para desplegar.")
            base_dest = (os.path.join(DEPLOY_DIR, CAMP) if DEPLOY_DIR else campaign_path)
            deploy_dir = base_dest if DEP_OVER else os.path.join(base_dest, "Translated_ES")
            backup_dir = os.path.join(base_dest, "_deploy_backup")
            os.makedirs(deploy_dir, exist_ok=True)
            os.makedirs(backup_dir, exist_ok=True)
            total = len(finalizados)
            for i, src in enumerate(sorted(finalizados, key=_natural_key), 1):
                if CANCEL_EVT.is_set(): raise KeyboardInterrupt()
                dst = os.path.join(deploy_dir, os.path.basename(src))
                if DEP_OVER and os.path.exists(dst):
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    shutil.copy2(dst, os.path.join(backup_dir, f"{os.path.basename(dst)}.{ts}.bak"))
                shutil.copy2(src, dst)
                RUN_STATE.update({"progress": int(i*100/total), "detail": f"Deploy {i}/{total}: {os.path.basename(src)}"})
            RUN_STATE["log_zip"] = zip_campaign_logs(CAMP)
            RUN_STATE.update({"phase":"fin", "done": True})
            return

        normals, fcs = find_miz_files_grouped(campaign_path)
        chosen_names = set(payload.get("missions", []))
        chosen = []
        for p in normals:
            if os.path.basename(p) in chosen_names: chosen.append(p)
        if INCLUDE_FC:
            for p in fcs:
                if os.path.basename(p) in chosen_names: chosen.append(p)
        if not chosen:
            raise RuntimeError("No se seleccionaron misiones.")

        total = len(chosen)
        for idx, miz_path in enumerate(chosen, 1):
            if CANCEL_EVT.is_set(): raise KeyboardInterrupt()
            miz_file = os.path.basename(miz_path)
            miz_stem_raw = os.path.splitext(miz_file)[0]
            miz_base = normalize_stem(miz_stem_raw)
            safe_dir = slugify(miz_base) or "miz"

            RUN_STATE.update({"phase":"procesando", "detail": miz_file, "progress": int((idx-1)*100/total)})

            extract_dir = os.path.join(paths["extracted"], safe_dir)
            if MODE in ("miz", "all"):
                backup_miz(miz_path, paths["backup"])
            extract_miz(miz_path, extract_dir)

            lua_src = os.path.join(extract_dir, FILE_TARGET)
            if not os.path.exists(lua_src):
                msg = f"No existe {FILE_TARGET} dentro de {miz_file}"
                logging.warning(msg)
                record_error(CAMP, miz_file, msg)
                continue

            if MODE == "translate":
                lua_tmp = os.path.join(paths["out_lua"], f"{miz_base}.lua")
                shutil.copy(lua_src, lua_tmp)
                ok = translate_lua(lua_tmp, translator, ARGS, paths["out_lua"])
                if not ok:
                    msg = f"Traducción falló para {miz_file} (retcode != 0)."
                    logging.warning(msg)
                    record_error(CAMP, miz_file, msg)
                harvest_translator_logs(paths["out_lua"], CAMP, miz_base)

            elif MODE == "miz":
                translated = os.path.join(paths["out_lua"], f"{miz_base}.translated.lua")
                if os.path.exists(translated):
                    shutil.copy(translated, lua_src)
                out_miz = os.path.join(paths["finalizado"], miz_file)
                compress_miz(extract_dir, out_miz)
                RUN_STATE["just_packaged"].append(miz_file)

            elif MODE == "all":
                lua_tmp = os.path.join(paths["out_lua"], f"{miz_base}.lua")
                shutil.copy(lua_src, lua_tmp)
                ok = translate_lua(lua_tmp, translator, ARGS, paths["out_lua"])
                if not ok:
                    msg = f"Traducción falló para {miz_file} (no se empaqueta)."
                    logging.warning(msg)
                    record_error(CAMP, miz_file, msg)
                    harvest_translator_logs(paths["out_lua"], CAMP, miz_base)
                    continue
                translated = os.path.join(paths["out_lua"], f"{miz_base}.translated.lua")
                if os.path.exists(translated):
                    shutil.copy(translated, lua_src)
                out_miz = os.path.join(paths["finalizado"], miz_file)
                compress_miz(extract_dir, out_miz)
                harvest_translator_logs(paths["out_lua"], CAMP, miz_base)
                RUN_STATE["just_packaged"].append(miz_file)

            RUN_STATE["progress"] = min(99, int(idx*100/total))

        RUN_STATE["log_zip"] = zip_campaign_logs(CAMP)
        RUN_STATE.update({"phase":"fin", "progress":100, "done": True})

    except KeyboardInterrupt:
        RUN_STATE.update({"canceled": True, "running": False, "detail": "Cancelado por usuario"})
    except Exception as e:
        logging.exception("run_orchestrator fallo:")
        RUN_STATE.update({"error": str(e), "running": False, "done": True})
        record_error(payload.get("campaign_name","?"), payload.get("missions", ["?"])[0] if payload.get("missions") else "?", str(e))
    finally:
        RUN_STATE["running"] = False

# =========================
#  Flask app
# =========================
app = Flask(__name__)

# Favicon vacío p/ evitar 404
@app.get("/favicon.ico")
def favicon():
    resp = make_response(b"", 204)
    resp.headers["Content-Type"] = "image/x-icon"
    return resp

INDEX_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>DCS Orquestador Traductor (Web) — {{version}}</title>
<style>
  /* NUEVO: asegura que el padding y el borde cuenten dentro del 100% */
  *, *::before, *::after { box-sizing: border-box; }

  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 980px; margin: 20px auto; }
  fieldset { margin-bottom: 16px; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; }
  .row > div { flex: 1; min-width: 280px; }
  label { display:block; font-weight:600; margin: 8px 0 4px; }

  /* AJUSTADO: ya no se desbordan */
  input[type=text], select { width:100%; padding:8px; box-sizing: border-box; }

  button { padding:10px 14px; cursor:pointer; }
  .muted { color:#666; font-size: 12px; }
  .box { border:1px solid #ddd; padding:10px; border-radius:8px; }
  .missions { max-height: 260px; overflow:auto; border:1px solid #ddd; padding:8px; border-radius:8px; background:#fafafa; }
  .progress { height: 12px; background:#eee; border-radius: 8px; overflow:hidden; margin:6px 0 2px; }
  .progress > div { height:100%; background:#3b82f6; width:0%; transition: width .2s ease; }
  .badge { display:inline-block; background:#eee; border-radius:6px; padding:2px 6px; margin:2px 4px 2px 0; }
  .error { color:#b91c1c; } .ok { color:#166534; }
  .help-btn { margin-left:6px; font-weight:700; color:#2563eb; border:1px solid #2563eb; background:#fff; border-radius:999px; width:22px; height:22px; line-height:20px; text-align:center; cursor:pointer; }
  .presetbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:8px; }
  .presetbar input[type=text]{ max-width: 260px; }
  .topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
  .modal { position:fixed; inset:0; background:rgba(0,0,0,0.4); display:none; align-items:center; justify-content:center; z-index:1000; }
  .modal.open { display:flex; }
  .modal-card { background:#fff; width:min(900px, 92vw); max-height:85vh; overflow:auto; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,.25); }
  .modal-card header, .modal-card footer { padding:12px 16px; border-bottom:1px solid #eee; }
  .modal-card footer { border-top:1px solid #eee; border-bottom:none; text-align:right; }
  .modal-card .content { padding:12px 16px; }
  .pill { display:inline-block; font-size:12px; padding:2px 6px; border-radius:999px; margin-left:6px; }
  .pill-green { background:#dcfce7; color:#166534; border:1px solid #86efac; }
  .pill-amber { background:#fef3c7; color:#92400e; border:1px solid #fcd34d; }
  code { background:#f6f6f6; padding:1px 4px; border-radius:4px; }
  .errbox { border:1px solid #f2b8b5; background:#fff1f0; padding:8px; border-radius:8px; max-height:240px; overflow:auto; }
  .erritem { margin:6px 0; white-space:pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size:12px; }
  .ver-badge { display:inline-block; margin-left:8px; font-size:12px; padding:2px 8px; border-radius:999px; background:#eef2ff; color:#3730a3; border:1px solid #c7d2fe; vertical-align:middle; }
</style>
</head>
<body>
<div class="topbar">
  <h1>DCS Orquestador Traductor (Web)
    <span class="ver-badge">{{version}}</span>
  </h1>
  <div>
    <button type="button" id="openHelp">❓ Ayuda</button>
    <button type="button" id="stopServer" style="margin-left:8px;">🛑 Parar servidor</button>
  </div>
</div>

<form id="cfg">
  <fieldset class="box">
    <legend>Configuración</legend>

    <!-- Presets -->
    <div class="presetbar">
      <label>Presets</label>
      <button type="button" class="help-btn" data-help="presets">?</button>
      <select id="presetList"></select>
      <button type="button" id="btnLoadPreset">Cargar</button>
      <button type="button" id="btnDeletePreset">Borrar</button>
      <span style="flex:1"></span>
      <input type="text" id="presetName" placeholder="Nombre del preset…" />
      <button type="button" id="btnSavePreset">Guardar preset</button>
    </div>

    <div class="row" style="margin-top:10px;">
      <div>
        <label>
          ROOT_DIR
          <button type="button" class="help-btn" data-help="rootdir">?</button>
        </label>
        <div class="row" style="align-items:flex-end; gap:8px;">
          <input type="text" id="rootdir" placeholder="D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns" required />
          <button type="button" id="btnAutoRoot">🔍 Detectar</button>
        </div>
        <div class="muted" id="autoRootMsg"></div>
      </div>
      <div>
        <label>
          FILE_TARGET
          <button type="button" class="help-btn" data-help="file_target">?</button>
        </label>
        <input type="text" id="filetarget" value="l10n/DEFAULT/dictionary" required />
      </div>
    </div>

    <!-- ARGS -->
    <fieldset class="box" style="background:#fcfcfc">
      <legend>Parámetros del modelo (ARGS)
        <button type="button" class="help-btn" data-help="args">?</button>
      </legend>
      <div class="row">
        <div>
          <label>--config (PROMTS)</label>
          <select id="arg_config"></select>
        </div>
        <div>
          <label>--lm-compat</label>
          <select id="arg_compat">
            <option value="completions" selected>completions</option>
            <option value="chat">chat</option>
          </select>
        </div>
      </div>

      <div class="row">
        <div>
          <label>--batch-size</label>
          <input type="text" id="arg_batch" value="4" />
        </div>
        <div>
          <label>--timeout (s)</label>
          <input type="text" id="arg_timeout" value="200" />
        </div>
      </div>

      <label>--lm-model</label>
      <div style="max-width: 620px;">
        <input list="lm_models_list" type="text" id="arg_model" value="" />
        <datalist id="lm_models_list"></datalist>
        <div class="muted" id="lmModelsHint"></div>
        <button type="button" id="btnScanModels" style="margin-top:6px;">🔄 Escanear LM Studio</button>
      </div>

      <div class="row" style="margin-top:8px;">
        <div style="flex:1; min-width:220px;">
          <label>--lm-url</label>
          <input type="text" id="arg_url" value="http://localhost:1234/v1" />
          <div class="muted">Ej.: http://localhost:1234/v1</div>
        </div>
      </div>

      <div class="muted" id="argsPreview">(preview de ARGS)</div>
    </fieldset>

    <div class="row" style="margin-top:8px;">
      <div>
        <label>
          DEPLOY_DIR (opcional)
          <button type="button" class="help-btn" data-help="deploy_dir">?</button>
        </label>
        <input type="text" id="deploydir" placeholder="D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns" />
      </div>
      <div>
        <label>
          DEPLOY_OVERWRITE
          <button type="button" class="help-btn" data-help="deploy_overwrite">?</button>
        </label>
        <select id="deployoverwrite">
          <option value="false" selected>false</option>
          <option value="true">true</option>
        </select>
      </div>
    </div>
    <div class="muted">Logs: {{logdir}} (se genera un ZIP por campaña al finalizar).</div>
  </fieldset>

  <fieldset class="box">
    <legend>Campañas y Misiones</legend>
    <div class="row">
      <div>
        <button type="button" id="scanCampaigns">🔍 Escanear campañas</button>
        <div id="campaigns" class="missions" aria-label="Campañas detectadas"></div>
      </div>
      <div>
        <div>
          <label title="Incluye misiones de Flaming Cliffs (-FC-) en la lista">
            <input type="checkbox" id="include_fc" /> Incluir misiones -FC- (Flaming Cliffs)
            <button type="button" class="help-btn" data-help="fc">?</button>
          </label>
        </div>
        <div id="missions" class="missions" aria-label="Misiones disponibles"></div>
      </div>
    </div>
  </fieldset>

  <fieldset class="box">
    <legend>Modo
      <button type="button" class="help-btn" data-help="mode">?</button>
    </legend>
    <label><input type="radio" name="mode" value="translate" checked /> translate</label>
    <label><input type="radio" name="mode" value="miz" /> miz</label>
    <label><input type="radio" name="mode" value="all" /> all</label>
    <label><input type="radio" name="mode" value="deploy" /> deploy</label>
  </fieldset>

  <div class="row">
    <div><button type="button" id="run">▶ Ejecutar</button></div>
    <div><button type="button" id="cancel">✖ Cancelar</button></div>
  </div>
</form>

<hr/>
<h3>Estado</h3>
<div id="status" class="box">
  <div>Fase: <b id="phase">-</b></div>
  <div>Detalle: <span id="detail">-</span></div>
  <div class="progress"><div id="bar"></div></div>
  <div><span id="pct">0%</span></div>
  <div id="msg" style="margin-top:6px;"></div>
  <div style="margin-top:10px;">
    <strong>Errores recientes</strong>
    <div class="errbox" id="errList" aria-live="polite"></div>
  </div>
</div>

<!-- Modal principal LM Studio -->
<div id="modal" class="modal" role="dialog" aria-modal="true" aria-labelledby="helpTitle">
  <div class="modal-card">
    <header><strong id="helpTitle">Ayuda rápida</strong></header>
    <div class="content">
      <h3>LM Studio — Descarga e instalación</h3>
      <ol>
        <li>Descarga LM Studio desde <a href="https://lmstudio.ai" target="_blank" rel="noopener">lmstudio.ai</a>.</li>
        <li>Instálalo y ábrelo. En la pestaña de modelos, descarga uno “Instruct”.</li>
        <li>Activa la API local: menú “Developer” → “Enable Local Server”.</li>
        <li>Comprueba la URL (por defecto): <code>http://localhost:1234/v1</code>.</li>
        <li>Carga el modelo (desde LM Studio o vía CLI si lo tienes): aparecerá en “Escanear LM Studio”.</li>
      </ol>

      <h3>Configuración recomendada</h3>
      <ul>
        <li><b>--lm-compat</b>: <code>completions</code> (típico en LM Studio).</li>
        <li><b>--config</b>: elige un YAML de <code>./PROMTS</code> con tus reglas de traducción.</li>
        <li><b>--lm-model</b>: selecciona uno de la lista detectada.</li>
        <li><b>--timeout</b>: aumenta si el modelo es lento.</li>
      </ul>

      <h3>Notas</h3>
      <ul>
        <li>Si <b>DEPLOY_OVERWRITE</b> está en <code>false</code>, el deploy va a <code>Translated_ES/</code> sin tocar originales.</li>
        <li>Las misiones <b>✅ Deploy</b> ya están empaquetadas en <code>finalizado/</code>. Las <b>✨ Traducida</b> tienen solo el <code>.translated.lua</code>.</li>
      </ul>
    </div>
    <footer><button id="closeHelp">Cerrar</button></footer>
  </div>
</div>

<!-- Modal reutilizable para mini-ayudas -->
<div id="miniModal" class="modal" role="dialog" aria-modal="true" aria-labelledby="miniTitle">
  <div class="modal-card">
    <header><strong id="miniTitle">Ayuda</strong></header>
    <div class="content" id="miniContent"></div>
    <footer><button id="miniClose">Cerrar</button></footer>
  </div>
</div>

<script>
(() => {
  let selectedCampaign = null;
  let campaigns = [];
  let missions = [];
  const el = (id)=>document.getElementById(id);

  function getMode(){
    const r = document.querySelector('input[name=mode]:checked');
    return r ? r.value : 'translate';
  }

  // Botón parar servidor
  document.getElementById('stopServer').onclick = async ()=>{
    if (!confirm('¿Parar el servidor web ahora? Se cerrará esta pestaña.')) return;
    try {
      await fetch('/shutdown', { method:'POST' });
    } catch(e) {}
    // Intento de cierre/limpieza UX
    setTimeout(()=>{ window.close(); location.href='about:blank'; }, 500);
  };

  // Modal principal
  const modal = el('modal');
  document.getElementById('openHelp').onclick = ()=> modal.classList.add('open');
  document.getElementById('closeHelp').onclick = ()=> modal.classList.remove('open');
  modal.addEventListener('click', (e)=>{ if(e.target===modal) modal.classList.remove('open'); });

  // Mini modal reutilizable
  const mini = el('miniModal');
  const miniTitle = el('miniTitle');
  const miniContent = el('miniContent');
  const miniClose = el('miniClose');
  miniClose.onclick = ()=> mini.classList.remove('open');
  mini.addEventListener('click', (e)=>{ if(e.target===mini) mini.classList.remove('open'); });

  const helpContent = {
    presets: `
      <p><b>¿Qué es un preset?</b> Es una <i>captura</i> de todos los campos actuales (ROOT_DIR, ARGS, modo, etc.) guardada en tu navegador.</p>
      <ul>
        <li><b>Guardar:</b> escribe un nombre y pulsa “Guardar preset”.</li>
        <li><b>Cargar:</b> elige en la lista y pulsa “Cargar”.</li>
        <li><b>Borrar:</b> elimina el preset seleccionado (se pedirá confirmación).</li>
      </ul>
    `,
    rootdir: `
      <p>Carpeta donde el juego tiene las campañas (<code>.miz</code>), por ejemplo:</p>
      <ul>
        <li><code>D:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns</code></li>
        <li><code>D:\\Program Files (x86)\\Steam\\steamapps\\common\\DCSWorld\\Mods\\campaigns</code></li>
      </ul>
      <p>Pulsa “Detectar” para intentar localizarla automáticamente (Windows).</p>
    `,
    file_target: `
      <p>Ruta <b>dentro</b> del .miz hacia el diccionario Lua que se traduce.</p>
      <ul>
        <li>Por defecto: <code>l10n/DEFAULT/dictionary</code></li>
        <li>Si la campaña usa otro idioma base: <code>l10n/RUS/dictionary</code>, etc.</li>
      </ul>
    `,
    args: `
      <p>Parámetros que se pasan al traductor.</p>
      <ul>
        <li><code>--config &lt;archivo.yaml&gt;</code>: reglas/prompts desde <code>./PROMTS</code>.</li>
        <li><code>--lm-compat &lt;completions|chat&gt;</code>: protocolo de LM Studio (normalmente <code>completions</code>).</li>
        <li><code>--batch-size &lt;n&gt;</code>: entradas por lote.</li>
        <li><code>--timeout &lt;s&gt;</code>: tiempo máximo por llamada.</li>
        <li><code>--lm-model &lt;id&gt;</code>: nombre exacto del modelo cargado.</li>
        <li><code>--lm-url &lt;http://host:puerto/v1&gt;</code>: URL del servidor local.</li>
      </ul>
    `,
    mode: `
      <p><b>Modos de ejecución</b></p>
      <ul>
        <li><b>translate</b>: extrae Lua del .miz y genera <code>&lt;base&gt;.translated.lua</code> en <code>out_lua/</code>.</li>
        <li><b>miz</b>: si existe <code>.translated.lua</code>, lo inyecta en el .miz y empaqueta a <code>finalizado/</code>.</li>
        <li><b>all</b>: hace <i>translate</i> + <i>miz</i> en una pasada.</li>
        <li><b>deploy</b>: copia los .miz de <code>finalizado/</code> a la carpeta del juego (o <code>Translated_ES/</code> si no sobreescribes).</li>
      </ul>
    `,
    fc: `
      <p><b>Flaming Cliffs (FC)</b> es un paquete de módulos de aviones simplificados para DCS.</p>
      <p>Si marcas esta opción, se incluyen misiones cuyo nombre contiene <code>-FC-</code>.</p>
    `,
    deploy_overwrite: `
      <p>Controla <b>dónde</b> se copian los .miz en el modo <b>deploy</b>:</p>
      <ul>
        <li><b>true</b>: sobrescribe en la carpeta de la campaña destino (se hace backup en <code>_deploy_backup/</code>).</li>
        <li><b>false</b> (recomendado): deja los originales intactos y copia a <code>Translated_ES/</code> dentro de la carpeta de la campaña destino.</li>
      </ul>
    `,
    deploy_dir: `
      <p>Base de destino para el modo <b>deploy</b>. Si lo dejas vacío, se usa la carpeta original de la campaña del juego.</p>
    `
  };

  function wireHelpButtons(){
    document.querySelectorAll('.help-btn').forEach(btn=>{
      btn.onclick = ()=>{
        const key = btn.getAttribute('data-help');
        const titleMap = {
          presets:'Ayuda — Presets',
          rootdir:'Ayuda — ROOT_DIR',
          file_target:'Ayuda — FILE_TARGET',
          args:'Ayuda — ARGS',
          mode:'Ayuda — Modos',
          fc:'Ayuda — Flaming Cliffs (FC)',
          deploy_overwrite:'Ayuda — DEPLOY_OVERWRITE',
          deploy_dir:'Ayuda — DEPLOY_DIR'
        };
        document.getElementById('miniTitle').textContent = titleMap[key] || 'Ayuda';
        document.getElementById('miniContent').innerHTML = helpContent[key] || '<p>Sin contenido.</p>';
        document.getElementById('miniModal').classList.add('open');
      };
    });
  }

  // PRESETS (localStorage)
  const PRESET_KEY = 'dcs_orq_presets_v2';
  function loadStore(){ try { return JSON.parse(localStorage.getItem(PRESET_KEY)||'{}'); } catch(e){ return {}; } }
  function saveStore(s){ localStorage.setItem(PRESET_KEY, JSON.stringify(s)); }
  function renderPresetList(){
    const store = loadStore();
    const sel = el('presetList'); sel.innerHTML = '';
    Object.keys(store).sort().forEach(name=>{
      const o = document.createElement('option');
      o.value = name; o.textContent = name; sel.appendChild(o);
    });
  }
  function captureForm(){
    const mode = [...document.querySelectorAll('input[name=mode]')].find(x=>x.checked)?.value || 'translate';
    return {
      ROOT_DIR: el('rootdir').value,
      FILE_TARGET: el('filetarget').value,
      arg_config: el('arg_config').value,
      arg_compat: el('arg_compat').value,
      arg_batch: el('arg_batch').value,
      arg_timeout: el('arg_timeout').value,
      arg_model: el('arg_model').value,
      arg_url: el('arg_url').value,
      DEPLOY_DIR: el('deploydir').value,
      DEPLOY_OVERWRITE: el('deployoverwrite').value === 'true',
      include_fc: el('include_fc').checked,
      mode
    };
  }
  function applyForm(d){
    if (!d) return;
    el('rootdir').value = d.ROOT_DIR || '';
    el('filetarget').value = d.FILE_TARGET || 'l10n/DEFAULT/dictionary';
    el('arg_config').value = d.arg_config || el('arg_config').value;
    el('arg_compat').value = d.arg_compat || 'completions';
    el('arg_batch').value  = d.arg_batch  || '4';
    el('arg_timeout').value= d.arg_timeout|| '200';
    el('arg_model').value  = d.arg_model  || '';
    el('arg_url').value    = d.arg_url    || 'http://localhost:1234/v1';
    el('deploydir').value = d.DEPLOY_DIR || '';
    el('deployoverwrite').value = d.DEPLOY_OVERWRITE ? 'true' : 'false';
    el('include_fc').checked = !!d.include_fc;
    if (d.mode){
      const r = document.querySelector(`input[name=mode][value="${d.mode}"]`);
      if (r) r.checked = true;
    }
    renderArgsPreview();
  }

  // Auto ROOT
  async function autoDetectRoot(deep=false){
    const msg = document.getElementById('autoRootMsg');
    msg.textContent = deep ? 'Buscando (búsqueda profunda)…' : 'Buscando ubicaciones típicas…';
    try {
      const r = await fetch('/auto_root_scan', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({deep}) });
      const js = await r.json();
      if (!js.ok) { msg.textContent = 'No fue posible detectar (' + (js.error||'') + ')'; return; }
      const roots = js.roots || [];
      if (roots.length === 0) {
        msg.textContent = deep ? 'Sin resultados en búsqueda profunda.' : 'No se encontró en rutas típicas.';
        if (!deep && confirm('¿Probar una búsqueda más profunda (puede tardar)?')) autoDetectRoot(true);
        return;
      }
      if (roots.length === 1) {
        el('rootdir').value = roots[0]; msg.textContent = 'Detectado: ' + roots[0];
      } else {
        let list = roots.map((p,i)=>`${i+1}) ${p}`).join('\n');
        let sel = prompt('Se han encontrado varias ubicaciones:\n\n' + list + '\n\nEscribe el número a usar:', '1');
        let idx = parseInt(sel||'1', 10) - 1;
        if (isFinite(idx) && idx >= 0 && idx < roots.length) {
          el('rootdir').value = roots[idx]; msg.textContent = 'Seleccionado: ' + roots[idx];
        } else {
          msg.textContent = 'Selección cancelada.';
        }
      }
    } catch (e) {
      console.error(e);
      msg.textContent = 'Error al escanear unidades.';
    }
  }
  document.getElementById('btnAutoRoot').onclick = ()=> autoDetectRoot(false);

  // Botones presets
  document.getElementById('btnSavePreset').onclick = ()=>{
    const name = (document.getElementById('presetName').value || '').trim();
    if (!name) { alert('Pon un nombre para el preset.'); return; }
    const store = loadStore(); store[name] = captureForm(); saveStore(store); renderPresetList();
    [...document.getElementById('presetList').options].forEach(o=>{ if(o.value===name) o.selected=true; });
  };
  document.getElementById('btnLoadPreset').onclick = ()=>{
    const name = document.getElementById('presetList').value;
    if (!name) { alert('No hay preset seleccionado.'); return; }
    const store = loadStore();
    if (!store[name]) { alert('Preset no encontrado.'); return; }
    applyForm(store[name]);
  };
  document.getElementById('btnDeletePreset').onclick = ()=>{
    const name = document.getElementById('presetList').value;
    if (!name) { alert('No hay preset seleccionado.'); return; }
    if (!confirm('¿Borrar el preset "'+name+'"?')) return;
    const store = loadStore(); delete store[name]; saveStore(store); renderPresetList();
  };
  renderPresetList();

  // PROMTS
  async function loadPromts(){
    const sel = el('arg_config'); sel.innerHTML = '';
    try{
      const r = await fetch('/promts');
      const js = await r.json();
      if (!js.ok) throw new Error(js.error||'Error');
      const files = js.files||[];
      if (files.length===0){
        const o = document.createElement('option'); o.value=''; o.textContent='(no hay YAML en ./PROMTS)'; sel.appendChild(o);
      } else {
        files.forEach(f=>{ const o = document.createElement('option'); o.value = f; o.textContent = f; sel.appendChild(o); });
        const def = '2-completions-PROMT.yaml';
        if (files.includes(def)) sel.value = def;
      }
    }catch(e){
      const o = document.createElement('option'); o.value=''; o.textContent='(error leyendo /promts)'; sel.appendChild(o);
      console.error(e);
    }
  }
  loadPromts();

  // LM Studio models
  async function scanLmModels() {
    const url = document.getElementById('arg_url').value || 'http://localhost:1234/v1';
    const hint = document.getElementById('lmModelsHint');
    const list = document.getElementById('lm_models_list');
    hint.textContent = 'Consultando modelos…';
    list.innerHTML = '';
    try {
      const r = await fetch('/lm_models?lm_url=' + encodeURIComponent(url));
      const js = await r.json();
      if (!js.ok) { hint.textContent = 'LM Studio no disponible (' + (js.error||'') + ')'; return; }
      (js.models || []).forEach(m => { const opt = document.createElement('option'); opt.value = m; list.appendChild(opt); });
      hint.textContent = js.models && js.models.length ? ('Modelos disponibles: ' + js.models.length) : 'No se encontraron modelos cargados.';
      const modelInput = document.getElementById('arg_model');
      if (!modelInput.value && js.models && js.models.length) { modelInput.value = js.models[0]; renderArgsPreview(); }
    } catch (e) { hint.textContent = 'Error consultando LM Studio.'; console.error(e); }
  }
  document.getElementById('btnScanModels').onclick = scanLmModels;
  let _lmScanTimer = null;
  document.getElementById('arg_url').addEventListener('input', () => {
    clearTimeout(_lmScanTimer);
    _lmScanTimer = setTimeout(scanLmModels, 500);
  });
  scanLmModels();

  // ARGS preview
  function buildArgs(){
    const cfg = el('arg_config').value ? ('--config ' + el('arg_config').value) : '';
    const compat = el('arg_compat').value ? (' --lm-compat ' + el('arg_compat').value) : '';
    const bs = el('arg_batch').value ? (' --batch-size ' + el('arg_batch').value) : '';
    const to = el('arg_timeout').value ? (' --timeout ' + el('arg_timeout').value) : '';
    const model = el('arg_model').value ? (' --lm-model ' + el('arg_model').value) : '';
    const url = el('arg_url').value ? (' --lm-url ' + el('arg_url').value) : '';
    return (cfg + compat + bs + to + model + url).trim();
  }
  function renderArgsPreview(){ document.getElementById('argsPreview').textContent = buildArgs(); }
  ['arg_config','arg_compat','arg_batch','arg_timeout','arg_model','arg_url'].forEach(id=>{
    const n = document.getElementById(id);
    n.addEventListener('input', renderArgsPreview);
    n.addEventListener('change', renderArgsPreview);
  });
  renderArgsPreview();

  // Campañas & Misiones
  function renderCampaigns() {
    const box = document.getElementById('campaigns');
    box.innerHTML = '';
    campaigns.forEach((c)=> {
      const d = document.createElement('div');
      d.innerHTML = '<label><input type="radio" name="camp" value="'+c.name+'"> '+c.name+'</label>';
      box.appendChild(d);
    });
    box.addEventListener('change', (e)=>{
      if (e.target && e.target.name==='camp') {
        selectedCampaign = e.target.value;
        loadMissions();
      }
    });
  }

  function renderMissions(list) {
    const box = document.getElementById('missions');
    box.innerHTML = '';

    // Leyenda arriba
    const legend = document.createElement('div');
    legend.className = 'muted';
    legend.style.marginBottom = '6px';
    legend.innerHTML = 'Leyenda: <span class="pill pill-green">✅ Deploy</span> = empaquetada en <code>finalizado/</code> · ' +
                       '<span class="pill pill-amber">✨ Traducida</span> = solo <code>.translated.lua</code> en <code>out_lua/</code>.';
    box.appendChild(legend);

    if (!list || !list.length) {
      const empty = document.createElement('div');
      empty.textContent = '(sin misiones)';
      box.appendChild(empty);
      return;
    }

    const mode = getMode();

    list.forEach((m)=>{
      let badge = '';
      if (m.deploy_ready) {
        badge = '<span class="pill pill-green">✅ Deploy</span>';
      } else if (m.translated_only) {
        badge = '<span class="pill pill-amber">✨ Traducida</span>';
      }

      const d = document.createElement('div');
      const checked = (mode === 'deploy' && m.deploy_ready) ? ' checked' : '';
      d.innerHTML =
        '<label><input type="checkbox" name="miz" value="'+m.name+'"'+checked+'> ' +
        m.name + (badge ? (' ' + badge) : '') + '</label>';
      box.appendChild(d);
    });

    const note = document.createElement('div');
    note.className = 'muted';
    note.style.marginTop = '6px';
    note.innerHTML = (mode==='deploy' ? 'En modo <b>deploy</b> se preseleccionan automáticamente las ✅.' : '');
    box.appendChild(note);
  }

  document.getElementById('scanCampaigns').onclick = async ()=>{
    try {
      const ROOT_DIR = document.getElementById('rootdir').value;
      const r = await fetch('/scan_campaigns', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ROOT_DIR})});
      const js = await r.json();
      campaigns = js.campaigns || [];
      renderCampaigns();
      document.getElementById('missions').innerHTML = '';
    } catch (e) { console.error(e); alert('Fallo al escanear campañas'); }
  };

  async function loadMissions() {
    if (!selectedCampaign) return;
    try {
      const include_fc = document.getElementById('include_fc').checked;
      const ROOT_DIR = document.getElementById('rootdir').value;
      const r = await fetch('/scan_missions', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ROOT_DIR, campaign_name: selectedCampaign, include_fc})});
      const js = await r.json();
      missions = js.missions || [];
      renderMissions(missions);
    } catch (e) { console.error(e); alert('Fallo al cargar misiones'); }
  }
  document.getElementById('include_fc').onchange = loadMissions;

  // Re-render al cambiar el modo
  document.querySelectorAll('input[name=mode]').forEach(radio=>{
    radio.addEventListener('change', ()=>{
      if (missions && missions.length) renderMissions(missions);
    });
  });

  // RUN / CANCEL / POLL
  document.getElementById('run').onclick = async ()=>{
    try {
      const ROOT_DIR = document.getElementById('rootdir').value;
      const FILE_TARGET = document.getElementById('filetarget').value;
      const DEPLOY_DIR = document.getElementById('deploydir').value;
      const DEPLOY_OVERWRITE = document.getElementById('deployoverwrite').value === 'true';
      const mode = [...document.querySelectorAll('input[name=mode]')].find(x=>x.checked).value;

      if (!selectedCampaign){ alert('Selecciona una campaña.'); return; }
      const miz = [...document.querySelectorAll('input[name=miz]:checked')].map(x=>x.value);
      const ARGS = buildArgs();

      const r = await fetch('/run', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ ROOT_DIR, FILE_TARGET, ARGS, DEPLOY_DIR, DEPLOY_OVERWRITE, mode, campaign_name: selectedCampaign, missions: miz, include_fc: document.getElementById('include_fc').checked })
      });
      const js = await r.json();
      if (!js.ok) { alert(js.error || 'No se pudo iniciar.'); return; }
      poll();
    } catch (e) { console.error(e); alert('Error al lanzar la ejecución'); }
  };
  document.getElementById('cancel').onclick = async ()=>{
    try { await fetch('/cancel', {method:'POST'}); } catch(e){ console.error(e); }
  };

  function applyJustPackaged(delta){
    if (!delta || !delta.length || !missions || !missions.length) return;
    const set = new Set(delta);
    missions.forEach(m=>{
      if (set.has(m.name)) {
        m.deploy_ready = true;
        m.translated_only = false;
      }
    });
    renderMissions(missions);
  }

  function renderErrors(errs){
    const box = document.getElementById('errList');
    box.innerHTML = '';
    if (!errs || !errs.length){
      box.innerHTML = '<div class="muted">Sin errores recientes.</div>';
      return;
    }
    errs.slice(0, 50).forEach(e=>{
      const div = document.createElement('div');
      div.className = 'erritem';
      const header = `[${e.ts}] ${e.campaign}::${e.mission}`;
      div.textContent = header + '\n' + e.message;
      box.appendChild(div);
    });
  }

  async function poll(){
    try {
      const r = await fetch('/status');
      const s = await r.json();
      if (s.just_packaged && s.just_packaged.length) {
        applyJustPackaged(s.just_packaged);
      }
      document.getElementById('phase').textContent = s.phase || '-';
      document.getElementById('detail').textContent= s.detail || '-';
      document.getElementById('bar').style.width = (s.progress||0)+'%';
      document.getElementById('pct').textContent = (s.progress||0) + '%';
      let msg = '';
      if (s.error) msg += '<div class="error">'+s.error+'</div>';
      if (s.done && !s.error) msg += '<div class="ok">Completado</div>';
      if (s.log_zip) msg += '<div class="badge">Logs ZIP: '+s.log_zip+'</div>';
      document.getElementById('msg').innerHTML = msg;

      // errores recientes
      renderErrors(s.errors);

      if (!s.done && s.running) setTimeout(poll, 600);
    } catch (e) { console.error(e); }
  }

  // Inicial
  renderPresetList();
  wireHelpButtons();
})();
</script>
</body>
</html>
"""

# ----------- Endpoints -----------
@app.get("/")
def index():
    return render_template_string(INDEX_HTML, logdir=LOG_DIR, version=APP_VERSION)

@app.get("/lm_models")
def lm_models():
    lm_url = request.args.get("lm_url", "http://localhost:1234/v1").rstrip("/")
    try:
        r = requests.get(lm_url + "/models", timeout=3)
        r.raise_for_status()
        js = r.json() or {}
        ids = [m.get("id", "") for m in (js.get("data") or []) if m.get("id")]
        return jsonify(ok=True, models=sorted(ids))
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 502

@app.get("/promts")
def list_promts():
    base = os.path.join(os.getcwd(), "PROMTS")
    files = []
    try:
        for p in glob.glob(os.path.join(base, "*.y*ml")):
            files.append(os.path.basename(p))
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
    return jsonify(ok=True, files=sorted(files))

@app.post("/scan_campaigns")
def scan_campaigns():
    data = request.get_json(force=True, silent=True) or {}
    root = data.get("ROOT_DIR","")
    camps = [{"name": n, "path": p} for (n,p) in find_campaigns(root)]
    return jsonify({"campaigns": camps})

@app.post("/scan_missions")
def scan_missions():
    data = request.get_json(force=True, silent=True) or {}
    root = data.get("ROOT_DIR","")
    camp = data.get("campaign_name","")
    include_fc = bool(data.get("include_fc", False))

    camps = dict(find_campaigns(root))
    if camp not in camps:
        return jsonify({"missions": []})

    normals, fcs = find_miz_files_grouped(camps[camp])
    miz_paths = normals + (fcs if include_fc else [])
    miz_names_real = [os.path.basename(p) for p in miz_paths]

    stem_to_real = {}
    for name in miz_names_real:
        stem = os.path.splitext(name)[0]
        stem_to_real.setdefault(normalize_stem(stem), name)

    fin_dir = campaign_finalizado_dir(camp)
    deploy_ready = set()
    if os.path.isdir(fin_dir):
        for f in os.listdir(fin_dir):
            if f.lower().endswith(".miz"):
                deploy_ready.add(f)

    out_dir = campaign_out_lua_dir(camp)
    translated_only_realnames = set()
    if os.path.isdir(out_dir):
        for f in os.listdir(out_dir):
            fl = f.lower()
            if fl.endswith(".translated.lua"):
                base = f[:-len(".translated.lua")]
                real = stem_to_real.get(normalize_stem(base))
                if real:
                    translated_only_realnames.add(real)

    items = []
    for real in miz_names_real:
        is_ready = (real in deploy_ready)
        is_translated = (real in translated_only_realnames)
        items.append({
            "name": real,
            "deploy_ready": bool(is_ready),
            "translated_only": bool(is_translated and not is_ready)
        })

    return jsonify({"missions": items})

@app.post("/run")
def run():
    if RUN_STATE["running"]:
        return jsonify({"ok": False, "error": "Ya hay una ejecución en curso."})
    data = request.get_json(force=True, silent=True) or {}
    RUN_STATE.update({"running": True, "done": False, "error": "", "progress": 0, "phase":"inicializando", "detail": "", "just_packaged": []})
    t = threading.Thread(target=run_orchestrator, args=(data,), daemon=True)
    t.start()
    return jsonify({"ok": True})

@app.post("/cancel")
def cancel():
    CANCEL_EVT.set()
    return jsonify({"ok": True})

@app.get("/status")
def status():
    return jsonify(RUN_STATE)

@app.post("/auto_root_scan")
def auto_root_scan():
    data = request.get_json(silent=True) or {}
    deep = bool(data.get("deep", False))
    if os.name != "nt":
        return jsonify(ok=False, error="Detección automática solo implementada para Windows."), 400
    drives = _windows_drives()
    results = []
    for drv in drives:
        for cand in _candidate_roots_for_drive(drv):
            if _exists_dir(cand):
                results.append(os.path.normpath(cand))
    if deep and not results:
        for drv in drives:
            try:
                results.extend(_deep_scan_drive_for_dcs(drv, max_depth=5, timeout_s=12))
            except Exception:
                pass
    uniq = sorted(set(results), key=lambda s: s.lower())
    return jsonify(ok=True, roots=uniq)

# ----- Shutdown (parar servidor) -----
@app.post("/shutdown")
def shutdown():
    """
    Intenta apagar el servidor de forma ordenada (Werkzeug). Si no está disponible,
    programa un fallback con os._exit(0) tras un breve delay.
    """
    try:
        func = request.environ.get("werkzeug.server.shutdown")
        if func is None:
            # Fallback: terminar proceso entero
            def _die():
                time.sleep(0.25)
                os._exit(0)
            threading.Thread(target=_die, daemon=True).start()
            return jsonify(ok=True, note="Fallback shutdown iniciado.")
        func()
        return jsonify(ok=True, note="Servidor detenido.")
    except Exception as e:
        # Último recurso
        def _die2():
            time.sleep(0.25)
            os._exit(0)
        threading.Thread(target=_die2, daemon=True).start()
        return jsonify(ok=True, note=f"Fallback shutdown por excepción: {e}")

# ----------- Run -----------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
