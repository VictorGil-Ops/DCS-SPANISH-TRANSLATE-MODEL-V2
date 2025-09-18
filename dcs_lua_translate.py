#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Versión 22.1 — Prompt unificado + protector de términos + reintento + PROTECT_BRACKETS conmutables.
- Unificación de /chat y /completions (plantilla Qwen/Llama-3 en completions).
- Lee SOLO LM_API del YAML y respeta --config, --lm-model, --lm-compat.
- Protector de términos seguro (sin coincidencias dentro de palabras).
- Reintento de entradas no traducidas en lotes pequeños.
- Post-proceso al final (estilo radio ES-ES).
- NUEVO: Activar/Desactivar protección de corchetes [ ... ] vía YAML (PROTECT_BRACKETS) o CLI (--protect-brackets).
"""

import argparse, hashlib, json, logging, os, re, sys, time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import requests

try:
    import yaml  # opcional
    YAML_AVAILABLE = True
except Exception:
    YAML_AVAILABLE = False

# --- CONFIGURACIÓN / REGEX ---

ENTRY_REGEX = re.compile(
    r'(?P<pre>\[\s*"(?P<key>[^"]+)"\s*\]\s*=\s*")'
    r'(?P<value>(?:[^"\\]|\\.|\\\r?\n)*)'
    r'(?P<post>")',
    flags=re.DOTALL
)
LINE_SPLIT_REGEX = re.compile(r'(?P<seg>.*?)(?P<lb>\\\r?\n|$)', flags=re.DOTALL)
BRACKET_REGEX = re.compile(r'\[[^\]\r\n]+\]')  # protege [ ... ] enteros (sin saltos de línea)
TRAIL_PUNCT_REGEX = re.compile(r'^(?P<core>.*?)(?P<punct>[\s\.\!\?\,;:\u2026]*)$', flags=re.DOTALL)
LEADING_WHITESPACE_REGEX = re.compile(r'^(?P<ws>\s*)(?P<text>.*)$', flags=re.DOTALL)
CLEAN_BAD_CHARS = re.compile(r'["\\]+')

# --- LOGGING ---

def setup_logging(output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, f"dcs_translate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(ch)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)
    logging.info("=== Inicio de ejecución ===")
    return log_path

def log_lm_api_settings(cfg: Dict, args) -> None:
    """
    Vuelca a log los parámetros relevantes de LM_API y otros ajustes clave.
    No imprime textos largos (p. ej., LM_INSTRUCTIONS), solo su longitud.
    """
    api = (cfg.get("LM_API") or {})
    allowed = {
        "temperature", "top_p", "top_k", "max_tokens", "stop",
        "repetition_penalty", "supports_system"
    }
    unknown = sorted(set(api.keys()) - allowed)

    # Previsualización de stop (sin desbordar log)
    stop = api.get("stop")
    if isinstance(stop, (list, tuple)):
        stop_preview = stop[:5]
        stop_info = f"{stop_preview} (+{len(stop)-len(stop_preview)} más)" if len(stop) > 5 else f"{stop_preview}"
    else:
        stop_info = repr(stop)

    logging.info("LM_API.temperature = %s", api.get("temperature", 0.2))
    logging.info("LM_API.top_p       = %s", api.get("top_p", 0.9))
    logging.info("LM_API.top_k       = %s", api.get("top_k", 40))
    logging.info("LM_API.max_tokens  = %s", api.get("max_tokens", 2048))
    logging.info("LM_API.stop        = %s", stop_info)
    logging.info("LM_API.repetition_penalty = %s", api.get("repetition_penalty", "(no definido)"))
    logging.info("LM_API.supports_system    = %s", api.get("supports_system", True))

    if unknown:
        logging.warning("LM_API claves no reconocidas (se ignoran en el cuerpo): %s", unknown)

    # Otros valores útiles del runtime
    instr = cfg.get("LM_INSTRUCTIONS", "")
    logging.info("LM_INSTRUCTIONS: %s caracteres", len(instr))
    logging.info("PROTECT_BRACKETS = %s", cfg.get("PROTECT_BRACKETS", True))
    logging.info("Compatibilidad (--lm-compat) = %s", getattr(args, "lm_compat", "auto"))
    logging.info("Modelo (--lm-model) = %s", getattr(args, "lm_model", "(por defecto)"))
    logging.info("Endpoint (--lm-url) = %s", getattr(args, "lm_url", "(por defecto)"))



# --- CONFIG ---

def load_config(path: Optional[str]) -> Dict:
    default_config = {}
    if path is None:
        logging.info("Sin --config: usando configuración por defecto.")
        return default_config.copy()
    if not os.path.isfile(path):
        logging.warning(f"No se encontró config en {path}. Usando configuración por defecto.")
        return default_config.copy()
    try:
        if path.lower().endswith((".yml", ".yaml")) and YAML_AVAILABLE:
            with open(path, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f)
        else:
            with open(path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
    except Exception as e:
        logging.error(f"Error cargando config {path}: {e}. Usando configuración por defecto.")
        user_cfg = {}
    cfg = default_config.copy()
    for k, v in (user_cfg or {}).items():
        cfg[k] = v
    return cfg

def key_is_target(key: str, keys_filter: Optional[List[str]], cfg: Dict) -> bool:
    if keys_filter:
        if "ALL" not in [k.strip().upper() for k in keys_filter]:
            if not any(kf in key for kf in keys_filter):
                return False
    tp = cfg.get("TARGET_PREFIXES", [])
    ep = cfg.get("EXCLUDE_PREFIXES", [])
    if tp and not any(key.startswith(p) for p in tp):
        return False
    if ep and any(key.startswith(p) for p in ep):
        return False
    return True

# --- SEGMENTO ---

class Segment:
    def __init__(self, key: str, index: int, raw_seg: str, lb: str, protect_brackets: bool = True):
        self.key = key
        self.index = index
        self.raw_seg = raw_seg
        self.lb = lb
        self.protect_brackets = protect_brackets

        ws_match = LEADING_WHITESPACE_REGEX.match(raw_seg)
        self.leading_ws = ws_match.group("ws") if ws_match else ""
        text_without_ws = ws_match.group("text") if ws_match else raw_seg

        m = TRAIL_PUNCT_REGEX.match(text_without_ws)
        self.core = m.group("core")
        self.punct = m.group("punct")
        self.br_tokens: Dict[str, str] = {}

        # Protección opcional de [ ... ]
        if self.protect_brackets:
            self.clean_for_model = self._protect_brackets(self.core)
        else:
            self.clean_for_model = self.core

        src_for_hash = f"{self.key}#{self.index}#{self.core.strip()}"
        h = hashlib.sha1(src_for_hash.encode("utf-8")).hexdigest()[:16]
        self.id = f"id_{h}"
        self.es: Optional[str] = None

    def _protect_brackets(self, text: str) -> str:
        def repl(m):
            token = f"BR_{len(self.br_tokens) + 1}"
            self.br_tokens[token] = m.group(0)
            return token
        return BRACKET_REGEX.sub(repl, text)

    @staticmethod
    def _strip_quotes_and_backslashes(s: str) -> str:
        return CLEAN_BAD_CHARS.sub("", s)

    @staticmethod
    def _condense_spaces(s: str) -> str:
        return re.sub(r'\s+', ' ', s).strip()

# --- HELPERS ---

def unprotect_tokens(text: str, mapping: Dict[str, str]) -> str:
    for tok, val in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(tok, val)
    return text

def build_rule_flags(rule: Dict) -> int:
    flags = 0
    for f in (rule.get("flags") or []):
        f = str(f).upper().strip()
        if f in ("I", "IGNORECASE"): flags |= re.IGNORECASE
        elif f in ("M", "MULTILINE"): flags |= re.MULTILINE
        elif f in ("S", "DOTALL"): flags |= re.DOTALL
    return flags

def apply_phraseology_rules(text: str, cfg: Dict) -> str:
    for rule in cfg.get("PHRASEOLOGY_RULES", []) or []:
        try:
            pat = rule.get("pattern"); rep = rule.get("replacement", "")
            if not pat: continue
            flags = build_rule_flags(rule)
            text = re.sub(pat, rep, text, flags=flags)
        except Exception:
            pass
    return text

def apply_post_rules(text: str, cfg: Dict) -> str:
    for rule in cfg.get("POST_RULES", []) or []:
        try:
            pat = rule.get("pattern")
            rep = rule.get("replacement", "")
            if not pat or not isinstance(rep, str):
                continue
            flags = build_rule_flags(rule)
            text = re.sub(pat, rep, text, flags=flags)
        except Exception as e:
            logging.warning("POST_RULES error en patrón %r: %s", rule.get("pattern"), e)
    return text

def apply_glossary_rules(text: str, cfg: Dict) -> str:
    glossary = cfg.get("GLOSSARY_OTAN", {})
    if not glossary:
        return text
    for en_term, es_translation in glossary.items():
        pattern = r"\b" + re.escape(en_term) + r"\b"
        text = re.sub(pattern, es_translation, text, flags=re.IGNORECASE)
    return text

def apply_smart_splash_rules(text: str, cfg: Dict) -> str:
    a_a_terms = set(term.lower() for term in cfg.get("A_A_TERMS", []))
    a_g_terms = set(term.lower() for term in cfg.get("A_G_TERMS", []))
    splash_pattern = re.compile(r'\bsplash\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+)?\b', re.IGNORECASE)
    if not splash_pattern.search(text):
        return text
    processed_text = text.lower()
    found_a_a = any(term in processed_text for term in a_a_terms)
    found_a_g = any(term in processed_text for term in a_g_terms)
    if found_a_a:
        def derribado_repl(m):
            num_part = m.group(0).lower().replace('splash', '').strip()
            return f"derribado {num_part}" if num_part else "derribado"
        return splash_pattern.sub(derribado_repl, text)
    elif found_a_g:
        def impacto_repl(m):
            num_part = m.group(0).lower().replace('splash', '').strip()
            return f"impacto {num_part}" if num_part else "impacto"
        return splash_pattern.sub(impacto_repl, text)
    return text

# Protector de términos (evita coincidencias dentro de palabras)
def protect_terms(text: str, terms) -> str:
    if not terms:
        return text
    for term in sorted(set(terms), key=len, reverse=True):
        pat = re.compile(rf'(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])', re.IGNORECASE)
        text = pat.sub(term, text)
    return text

# --- LLAMADAS AL MODELO ---

def call_lmstudio_batch(items, cfg, timeout, lm_url, lm_model, compat="auto") -> Dict[str, str]:
    lm_instructions = cfg.get("LM_INSTRUCTIONS", "")
    user_payload = [{"id": k, "en": v} for k, v in items]
    json_content = json.dumps(user_payload, ensure_ascii=False)

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("LMSTUDIO_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    api = (cfg.get("LM_API") or {})
    default_stop = ["</s>", "<|eot_id|>"]
    supports_system = bool(api.get("supports_system", True))  # aplanar si false

    def post_chat() -> str:
        url_chat = f"{lm_url.rstrip('/')}/chat/completions"
        if supports_system:
            messages = [
                {"role": "system", "content": lm_instructions},
                {"role": "user", "content": json_content}
            ]
        else:
            messages = [
                {"role": "user", "content": lm_instructions + "\n\n" + json_content}
            ]
        body = {
            "model": lm_model,
            "messages": messages,
            "temperature": api.get("temperature", 0.2),
            "top_p": api.get("top_p", 0.9),
            "top_k": api.get("top_k", 40),
            "max_tokens": api.get("max_tokens", 2048),
            "stop": api.get("stop", default_stop)
        }
        if "repetition_penalty" in api:
            body["repetition_penalty"] = api["repetition_penalty"]
        r = requests.post(url_chat, json=body, headers=headers, timeout=timeout)
        if r.status_code >= 400:
            logging.error("LM Studio /chat/completions %s: %s", r.status_code, r.text[:1000])
            r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def build_prompt_for_model(model_name: str, system_text: str, user_text: str) -> str:
        name = (model_name or "").lower()
        if "qwen" in name:  # ChatML (Qwen)
            return (
                f"<|im_start|>system\n{system_text}\n<|im_end|>\n"
                f"<|im_start|>user\n{user_text}\n<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
        else:  # Llama-3 default
            BOS = "<|begin_of_text|>"; EOT = "<|eot_id|>"
            S = "<|start_header_id|>"; E = "<|end_header_id|>"
            sys = f"{S}system{E}\n{system_text}{EOT}"
            usr = f"{S}user{E}\n{user_text}{EOT}"
            asst = f"{S}assistant{E}\n"
            return f"{BOS}{sys}{usr}{asst}"

    def post_comp() -> str:
        url_comp = f"{lm_url.rstrip('/')}/completions"
        prompt = build_prompt_for_model(lm_model, lm_instructions, json_content)
        body = {
            "model": lm_model,
            "prompt": prompt,
            "temperature": api.get("temperature", 0.2),
            "top_p": api.get("top_p", 0.9),
            "top_k": api.get("top_k", 40),
            "max_tokens": api.get("max_tokens", 2048),
            "stop": api.get("stop", default_stop)
        }
        if "repetition_penalty" in api:
            body["repetition_penalty"] = api["repetition_penalty"]
        r = requests.post(url_comp, json=body, headers=headers, timeout=timeout)
        if r.status_code >= 400:
            logging.error("LM Studio /completions %s: %s", r.status_code, r.text[:1000])
            r.raise_for_status()
        return r.json()["choices"][0].get("text", "")

    t0 = time.perf_counter()
    content = ""
    try:
        if compat == "chat":
            content = post_chat()
        elif compat == "completions":
            content = post_comp()
        else:
            try:
                content = post_chat()
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code in (404, 405):
                    content = post_comp()
                else:
                    raise
    except requests.exceptions.Timeout:
        logging.warning("LM Studio timed out after %d seconds.", timeout)
    except Exception as e:
        logging.exception("ERROR LM Studio: %s", e)

    if not content:
        return {}

    dt = time.perf_counter() - t0
    logging.info("Lote LM Studio: %d frases | %.2fs", len(items), dt)

    m_fence = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    clean_content = (m_fence.group(1).strip() if m_fence else content).replace('\u00a0', ' ').strip()

    out = {}
    try:
        parsed = json.loads(clean_content)
        if isinstance(parsed, dict) and "data" in parsed and isinstance(parsed["data"], list):
            items_out = parsed["data"]
        elif isinstance(parsed, list):
            items_out = parsed
        elif isinstance(parsed, dict) and "id" in parsed and "es" in parsed:
            items_out = [parsed]
        else:
            logging.error("JSON inesperado. Respuesta: %s", parsed)
            return {}
        for obj in items_out:
            _id = obj.get("id"); _es = obj.get("es"); _text = obj.get("text")
            if _id and isinstance(_es, str):
                out[_id] = _es
            elif _text and len(items) == 1:
                out[items[0][0]] = _text
    except Exception:
        m_any = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', content)
        if m_any:
            try:
                parsed = json.loads(m_any.group(1))
                if isinstance(parsed, list) and len(parsed) == 1 and "text" in parsed[0]:
                    out[items[0][0]] = parsed[0]["text"]
                else:
                    logging.error("No se pudo parsear el JSON. Respuesta cruda: %s", content[:1000])
            except Exception:
                logging.error("No se pudo parsear el JSON ni el sub-JSON. Respuesta cruda: %s", content[:1000])
        else:
            logging.error("No se pudo parsear el JSON. Respuesta cruda: %s", content[:1000])
    return out

# --- UTILIDADES DE TEXTO ---

def escape_for_lua(s: str) -> str:
    s = s.replace('\\', '\\\\')
    s = s.replace('"', r'\"')
    return s

def format_for_jsonl(en: str, es: str) -> str:
    user_prompt = f"Traduce al español: '{en}'"
    assistant_response = es
    return json.dumps({"text": f"### User: {user_prompt} ### Assistant: {assistant_response}"}, ensure_ascii=False)

# --- PROCESO PRINCIPAL ---

def process_file(lua_path, batch_size, timeout, keys_filter, cfg, output_dir, lm_url, lm_model, compat="auto"):
    with open(lua_path, "r", encoding="utf-8", newline="") as f:
        lua_text = f.read()

    lua_text = lua_text.replace("’", "'")

    # Reemplazos fijos previos (seguro)
    fixed_replacements = cfg.get("FIXED_FULL_REPLACEMENTS", {})
    if isinstance(fixed_replacements, dict):
        for en_phrase, es_phrase in fixed_replacements.items():
            if not isinstance(en_phrase, str) or not isinstance(es_phrase, str):
                logging.warning("FIXED_FULL_REPLACEMENTS mal formado: %r -> %r (ignorado)", en_phrase, es_phrase)
                continue
            logging.info(f"Aplicando reemplazo fijo: '{en_phrase}' -> '{es_phrase}'")
            lua_text = lua_text.replace(en_phrase, es_phrase)
    else:
        logging.warning("FIXED_FULL_REPLACEMENTS no es un dict; ignorando.")

    # Pre-reglas
    lua_text = apply_glossary_rules(lua_text, cfg)
    lua_text = apply_phraseology_rules(lua_text, cfg)
    lua_text = apply_smart_splash_rules(lua_text, cfg)

    total_entries_in = len(list(ENTRY_REGEX.finditer(lua_text)))
    logging.info(f"Entradas detectadas en origen: {total_entries_in}")

    segments: List[Segment] = []

    # PROTECT_BRACKETS desde YAML
    protect_brackets_flag = bool(cfg.get("PROTECT_BRACKETS", True))
    logging.info(f"PROTECT_BRACKETS = {protect_brackets_flag}")

    def replace_entry(m: re.Match) -> str:
        pre, key, value, post = m.group("pre"), m.group("key"), m.group("value"), m.group("post")
        if not key_is_target(key, keys_filter, cfg):
            return m.group(0)
        start_idx = len(segments)
        segs = []
        for i, sm in enumerate(LINE_SPLIT_REGEX.finditer(value)):
            seg_txt = sm.group("seg"); lb = sm.group("lb")
            if seg_txt == "" and lb == "": 
                continue
            seg = Segment(
                key=key,
                index=start_idx + i,
                raw_seg=seg_txt,
                lb=lb,
                protect_brackets=protect_brackets_flag
            )
            segs.append(seg); segments.append(seg)
        new_value = "".join(seg.id + seg.punct + seg.lb for seg in segs)
        return pre + new_value + post

    logging.info("Insertando marcadores id_hash en .lua temporal...")
    lua_with_placeholders = ENTRY_REGEX.sub(replace_entry, lua_text)

    os.makedirs(output_dir, exist_ok=True)
    tmp_lua_path = os.path.join(output_dir, os.path.basename(lua_path).rsplit(".",1)[0] + ".placeholders.lua")
    with open(tmp_lua_path, "w", encoding="utf-8", newline="") as f:
        f.write(lua_with_placeholders)
    logging.info(f"Guardado .lua temporal con marcadores: {tmp_lua_path}")

    id_to_seg: Dict[str, Segment] = {seg.id: seg for seg in segments}
    unique_en_to_idlist: Dict[str, List[str]] = {}
    for seg in segments:
        if seg.clean_for_model.strip() == "": continue
        unique_en_to_idlist.setdefault(seg.clean_for_model, []).append(seg.id)

    cache_path = os.path.join(output_dir, "translation_cache.json")
    try:
        cache = json.load(open(cache_path, "r", encoding="utf-8"))
    except Exception:
        cache = {}

    # Marca caché
    for clean_en, idlist in list(unique_en_to_idlist.items()):
        if clean_en in cache:
            es = cache[clean_en]
            logging.info(f"Usando caché para: '{clean_en}' -> '{es}'")
            for _id in idlist: id_to_seg[_id].es = es
            unique_en_to_idlist.pop(clean_en, None)

    to_query: List[Tuple[str, str]] = []
    for clean_en, idlist in unique_en_to_idlist.items():
        to_query.append((idlist[0], clean_en))

    # Conjunto de términos protegidos para ambos pases
    protected_terms_set = set(
        (cfg.get("PROTECT_WORDS") or [])
        + (cfg.get("NO_TRANSLATE_TERMS") or [])
        + (cfg.get("TECHNICAL_TERMS_NO_TRASLATE") or [])
    )

    # PRIMER PASE
    for i in range(0, len(to_query), batch_size):
        batch = to_query[i:i+batch_size]
        resp = call_lmstudio_batch(batch, cfg, timeout, lm_url, lm_model, compat=compat)

        for b_id, b_en in batch:
            es = resp.get(b_id)
            if not isinstance(es, str):
                continue
            translated_es = es
            translated_es = protect_terms(translated_es, protected_terms_set)

            # Desproteger [ ... ] si se protegieron
            br_map = id_to_seg[b_id].br_tokens
            if br_map:
                translated_es = unprotect_tokens(translated_es, br_map)

            translated_es = re.sub(r'\s+', ' ', translated_es).strip()

            if translated_es.strip().lower() != b_en.strip().lower() and translated_es.strip() != "":
                cache[b_en] = translated_es

            for _id in unique_en_to_idlist.get(b_en, []):
                id_to_seg[_id].es = translated_es

    # REINTENTO EN PARES
    retry_items = [(seg.id, seg.clean_for_model) for seg in segments if seg.es is None and seg.clean_for_model.strip()]
    if retry_items:
        logging.info(f"Reintentando {len(retry_items)} entradas con lotes pequeños…")
        for j in range(0, len(retry_items), 2):
            batch = retry_items[j:j+2]
            resp = call_lmstudio_batch(batch, cfg, timeout, lm_url, lm_model, compat=compat)
            for b_id, b_en in batch:
                es2 = resp.get(b_id)
                if isinstance(es2, str) and es2.strip():
                    translated_es = protect_terms(es2, protected_terms_set)
                    seg = id_to_seg[b_id]
                    if seg.br_tokens:
                        translated_es = unprotect_tokens(translated_es, seg.br_tokens)
                    translated_es = re.sub(r'\s+', ' ', translated_es).strip()
                    id_to_seg[b_id].es = translated_es
                    cache[b_en] = translated_es

    # FALLBACK: inglés limpio
    for seg in segments:
        if seg.es is None and seg.clean_for_model.strip() != "":
            es_fallback = unprotect_tokens(seg.core, seg.br_tokens)
            es_fallback = re.sub(r'\s+', ' ', es_fallback).strip()
            seg.es = es_fallback
            logging.warning(f"Translation failed for {seg.id}, using fallback: {seg.es}")

    # Guardar caché
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Export JSONL de segmentos
    jsonl_path = os.path.join(output_dir, os.path.basename(lua_path).rsplit(".", 1)[0] + ".translations.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as jf:
        for seg in segments:
            if seg.clean_for_model.strip() == "": continue
            obj = {"id": seg.id, "key": seg.key, "en": seg.clean_for_model, "es": seg.es}
            jf.write(json.dumps(obj, ensure_ascii=False) + "\n")
    logging.info(f"JSONL generado: {jsonl_path}")

    # Export fine-tuning data (acumulativo)
    training_data_path = os.path.join(output_dir, "fine_tuning_data.jsonl")
    with open(training_data_path, "a", encoding="utf-8") as tf:
        for en, es in cache.items():
            if en.strip() and es.strip():
                tf.write(format_for_jsonl(en, es) + "\n")
    logging.info(f"Datos de fine-tuning exportados a: {training_data_path}")

    # Reinsertar IDs por traducciones
    id_to_es_lua = {seg.id: f"{seg.leading_ws}{escape_for_lua(seg.es or '')}" for seg in segments}

    def reinsert_cb(m: re.Match) -> str:
        pre, key, value, post = m.group("pre"), m.group("key"), m.group("value"), m.group("post")
        new_value = value
        for pid, es in id_to_es_lua.items():
            new_value = new_value.replace(pid, es)
        return pre + new_value + post

    final_text = ENTRY_REGEX.sub(reinsert_cb, lua_with_placeholders)

    total_entries_out = len(list(ENTRY_REGEX.finditer(final_text)))
    logging.info(f"Entradas detectadas en salida: {total_entries_out} (origen {total_entries_in})")

    # Post-proceso
    final_text = apply_post_rules(final_text, cfg)

    out_lua_path = os.path.join(output_dir, os.path.basename(lua_path).rsplit(".", 1)[0] + ".translated.lua")
    with open(out_lua_path, "w", encoding="utf-8", newline="") as f:
        f.write(final_text)
    logging.info(f"¡Listo! Fichero traducido: {out_lua_path}")

# --- MAIN ---

def main():
    parser = argparse.ArgumentParser(description="Traductor de ficheros .lua de DCS con LM Studio (local).")
    parser.add_argument("fichero_lua")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--keys", type=str, default="")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default="./out_lua")
    parser.add_argument("--lm-url", type=str, default=os.environ.get("LMSTUDIO_URL", "http://localhost:1234/v1"))
    parser.add_argument("--lm-model", type=str, default=os.environ.get("LMSTUDIO_MODEL", "gpt-neo"))
    parser.add_argument("--lm-compat", type=str, choices=["auto","chat","completions"], default="auto")
    parser.add_argument("--protect-brackets", choices=["on","off","auto"], default="off",
                        help="Activa/desactiva el tokenizado de [ ... ] antes de enviar al modelo (auto=según YAML).")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    setup_logging(args.output_dir)
    cfg = load_config(args.config)

    # CLI override para PROTECT_BRACKETS
    if args.protect_brackets != "auto":
        cfg["PROTECT_BRACKETS"] = (args.protect_brackets == "on")
    
    log_lm_api_settings(cfg, args)

    keys_filter = [k.strip() for k in args.keys.split(",") if k.strip()] if args.keys else None

    logging.info(f"Archivo: {args.fichero_lua}")
    logging.info(f"Batch: {args.batch_size} | Timeout: {args.timeout}s | Keys: {keys_filter or '(por config)'}")
    logging.info(f"LM Studio: {args.lm_url} | model={args.lm_model} | compat={args.lm_compat}")

    try:
        process_file(args.fichero_lua, args.batch_size, args.timeout, keys_filter, cfg,
                     args.output_dir, args.lm_url, args.lm_model, compat=args.lm_compat)
        logging.info("=== Fin OK ===")
    except Exception as e:
        logging.exception(f"ERROR de ejecución: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
