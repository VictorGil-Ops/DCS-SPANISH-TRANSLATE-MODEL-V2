#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traductor de dictionaries.lua (DCS) usando LLMs externos (ChatGPT, DeepSeek, Azure OpenAI,
OpenRouter, Anthropic). Análisis local de propiedades objetivo; traducción vía proveedor elegido.

Claves en fichero tipo "k: v":
  # OpenAI (ChatGPT)
  API_CHATGPT: sk-...
  OPENAI_BASE_URL: https://api.openai.com/v1
  OPENAI_MODEL: gpt-4o-mini

  # DeepSeek
  API_DEEPSEEK: sk-...
  DEEPSEEK_BASE_URL: https://api.deepseek.com/v1
  DEEPSEEK_MODEL: deepseek-chat

  # Azure OpenAI (usa deployments)
  API_AZURE_OPENAI: az-xxxxx
  AZURE_OPENAI_ENDPOINT: https://<tu-recurso>.openai.azure.com
  AZURE_OPENAI_DEPLOYMENT: mi-deployment-chat
  AZURE_OPENAI_API_VERSION: 2024-02-15-preview

  # OpenRouter
  API_OPENROUTER: or-xxxxx
  OPENROUTER_BASE_URL: https://openrouter.ai/api/v1
  OPENROUTER_MODEL: openrouter/auto

  # Anthropic (Claude)
  API_ANTHROPIC: sk-ant-...
  ANTHROPIC_BASE_URL: https://api.anthropic.com
  ANTHROPIC_MODEL: claude-3-haiku-20240307
  ANTHROPIC_VERSION: 2023-06-01

Uso:
  python traducir_dcs_dictionary_llm_v2.py <dictionary.lua> --engine chatgpt   --keys keys.txt
  python traducir_dcs_dictionary_llm_v2.py <dictionary.lua> --engine deepseek  --keys keys.txt
  python traducir_dcs_dictionary_llm_v2.py <dictionary.lua> --engine azure     --keys keys.txt
  python traducir_dcs_dictionary_llm_v2.py <dictionary.lua> --engine openrouter--keys keys.txt
  python traducir_dcs_dictionary_llm_v2.py <dictionary.lua> --engine anthropic --keys keys.txt

Opciones:
  --model NOMBRE           # sobreescribe el modelo/deployment
  --style formal|brevity|neutral   (default formal)
  --translate-all
  --batch-size N           (default 40)
  --dry-run                (muestra payload sin llamar a la IA)
  --quiet

Requisitos: requests
"""

import argparse, json, os, re, sys, time
from pathlib import Path

try:
    import requests  # type: ignore
except Exception:
    print("[ERROR] Falta 'requests'. Instálalo con: pip install requests")
    sys.exit(2)

# =============================================================================

# --- Prefijos (minúsculas) ---
TARGET_PREFIXES = (
    'dictkey_actiontext_',
    'dictkey_actiontex_',          # tolerancia
    'dictkey_actionradiotext_',
    'dictkey_actionradiotex_',     # tolerancia
    'dictkey_descriptiontext_',
    'dictkey_descriptionbluetask_',
)
EXCLUDE_PREFIXES = (
    'dictkey_unitname_',
    'dictkey_groupname_',
    'dictkey_wptname_',
    'dictkey_sortie_',
    'dictkey_subtitle_',
    
)

PLACE_OPEN = '\u27EA'  # ⟪
PLACE_CLOSE = '\u27EB' # ⟫

# Palabras/términos que no se deben traducir (protección previa)
PROTECT_WORDS = (
    'ENFIELD','SPRINGFIELD','COLT','TOWER','OVERLORD','AWACS','HUMMER','E-2C',
    'F-5','F4','F5','F-4','SU-24','S-24','MiG','MIG','MiG-21','MIG-21','MIG21',
    'KRYMSK','TACAN','RSBN','QNH','KW','KRM','BRAA','BULLSEYE','BULL','RTB',
    'WINCHESTER','BINGO','JOKER','COLT','SPRINGFIELD','ENFIELD'
)
NO_TRANSLATE_TERMS = (
    'Scramble','Splash','Fox 1','Fox 2','Fox 3','Fox1','Fox2','Fox3',
    'Tally','No Joy','Picture','Declare',
    'Bandit',
    'Spike','Spiked','Nails','Mud','Merged','Commit','Flow','Push',
    'Bingo','Joker','Winchester','Sanitize','Pickle',
    'CAP','CAS','SEAD','DEAD','JTAC','FAC','AWACS','SAR',
    'BRAA','Bullseye','BRA','IP','TOT','TACAN','RSBN','QNH',
    'RTB','Roger','Wilco'
)

FIXED_FULL_REPLACEMENTS = {
    'IMMORTAL ON':  'INMORTAL ACTIVADO',
    'IMMORTAL OFF': 'INMORTAL DESACTIVADO',
}

PHRASEOLOGY_RULES = [
    (r'\broger that\b', 'Recibido'),
    (r'\broger\b', 'Recibido'),
    (r'\bwilco\b', 'Recibido, cumpliré'),
    (r'\brtb\b', 'Vuelva a base'),
    (r'\bgood\s+show\s*!', '¡Buen trabajo!'),
    (r'\bgood\s+job\s*!', '¡Buen trabajo!'),
    (r'\bgood\s+kill\s*!', '¡Blanco derribado!'),
    (r'^\s*(the\s+)?mi[gq]\'?s?\s+are\s+down\s*!', '¡Todos los MiGs derribados!'),
    (r'\ball\s+clear\b', 'Todo despejado'),
    (r'\bno\s+other\s+fighters\b', 'no hay más cazas'),
    (r'\bfighters?\b', 'cazas'),
    (r'\bbogies?\s+incoming\b', 'Bogies entrantes'),
]

# =============================================================================
# GLOSARIO OTAN - Reporting names con sus modelos reales
# =============================================================================
GLOSSARY_OTAN = {
    # --------------------------------------------------------------------------
    # FIGHTERS / INTERCEPTORS (Cazas / Interceptores)
    # --------------------------------------------------------------------------
    "Fishbed": "MiG-21",
    "Fulcrum": "MiG-29",
    "Foxbat": "MiG-25",
    "Foxhound": "MiG-31",
    "Flanker": "Su-27",  # Incluye variantes como Su-27, Su-33, Su-35, Su-37
    "Flanker-E": "Su-27", # Especificación común para variantes modernas
    "Flogger": "MiG-23",
    "Fagot": "MiG-15",
    "Fresco": "MiG-17",
    "Finback": "J-8", # Chino, pero aparece en algunos escenarios

    # --------------------------------------------------------------------------
    # ATTACK / BOMBERS (Aviones de Ataque / Bombarderos)
    # --------------------------------------------------------------------------
    "Frogfoot": "Su-25",
    "Fencer": "Su-24",
    "Fullback": "Su-34",
    "Blinder": "Tu-22",
    "Backfire": "Tu-22M",
    "Badger": "Tu-16",
    "Bear": "Tu-95",
    "Blackjack": "Tu-160",

    # --------------------------------------------------------------------------
    # HELICOPTERS (Helicópteros)
    # --------------------------------------------------------------------------
    "Hind": "Mi-24",
    "Hip": "Mi-8",
    "Havoc": "Mi-28",
    "Hokum": "Ka-50", # Black Shark
    "Helix": "Ka-27 / Ka-29",

    # --------------------------------------------------------------------------
    # AIR DEFENSE / SAM SYSTEMS (Defensa Aérea / Sistemas SAM)
    # --------------------------------------------------------------------------
    # Sistemas de Misiles Superficie-Aire (SAM)
    "Gainful": "SA-6", # Sistema Kub/Kvadrat
    "Gadfly": "SA-11", # Sistema Buk
    "Grumble": "SA-10", # Sistema S-300
    "Giant": "SA-5", # Sistema S-200
    "Goa": "SA-3", # Sistema S-125 Neva/Pechora
    "Guideline": "SA-2", # Sistema S-75 Dvina
    "Gaskin": "SA-9",
    "Grail": "SA-7", # MANPADS Strela-2
    "Gopher": "SA-13",

    # Radares y AAA (Artillería Antiaérea)
    "Dog Ear": "Radar del ZSU-23-4",
    "Fire Can": "Radar de control de tiro SON-9",
    "Straight Flush": "Radar de adquisición 1S91 (SA-6)",
    "Snow Drift": "Radar P-15 (SA-3)",
    "Fan Song": "Radar RSNA-75 (SA-2)",
    "Shilka": "ZSU-23-4",

    # --------------------------------------------------------------------------
    # AIR-TO-AIR MISSILES (Misiles Aire-Aire)
    # --------------------------------------------------------------------------
    "Alamo": "R-27R/T (AA-10)",
    "Adder": "R-77 (AA-12)",
    "Aphid": "R-60 (AA-8)",
    "Archer": "R-73 (AA-11)",
    "Acrid": "R-40 (AA-6)",
    "Anab": "R-13 (AA-2)",

    # --------------------------------------------------------------------------
    # AIR-TO-GROUND MISSILES (Misiles Aire-Superficie)
    # --------------------------------------------------------------------------
    "Krypton": "Kh-31P (AS-17)",
    "Kingbolt": "Kh-59 (AS-13)",
    "Karen": "Kh-28 (AS-9)",
    "Kegler": "Kh-29 (AS-14)",
    "Kelly": "Kh-25 (AS-10)",
    "Kerry": "Kh-25MP (AS-12)",
    "Kilter": "Kh-22 (AS-4)",
    "Kitchen": "Kh-22 (AS-4)", # Alternativo

    # --------------------------------------------------------------------------
    # GENERAL TERMS (Términos Generales - NO traducir)
    # --------------------------------------------------------------------------
    # Añade términos de procedimiento que deben permanecer en inglés
    "Overlord": "Overlord", # Indicativo típico de AWACS o comando
    "Magnum": "Magnum", # Código de lanzamiento de misil anti-radar
    "Pickle": "Pickle", # Jerga para soltar bombas
    "Winchester": "Winchester", # Sin munición aire-aire
    "Bingo": "Bingo", # Combustible mínimo para RTB
    "Joker": "Joker", # Combustible para inicio de re-abastecimiento o RTB planificado
    "Splash": "Splash", # Blanco derribado/impactado
    "Tally": "Tally", # Visual contacto con el blanco
    "Bandit": "Bandit", # Avión enemigo identificado
    "Bogey": "Bogey", # Contacto aéreo no identificado
    "Fox": "Fox", # Anuncio de disparo de misil (Fox 1, Fox 2, Fox 3)
}

# === Utilidades ===
def load_keys(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        data[k.strip()] = v.strip()
    return data

def build_output_path(inp_path: Path) -> Path:
    suffix = ''.join(inp_path.suffixes) or '.lua'
    stem = inp_path.name[:-len(suffix)] if suffix else inp_path.name
    return inp_path.with_name(f"{stem}_traducido{suffix}")

def find_closing_quote_pos(s: str) -> int:
    i = 0
    while i < len(s):
        if s[i] == '"':
            back = 0; j = i - 1
            while j >= 0 and s[j] == '\\':
                back += 1; j -= 1
            if back % 2 == 0:
                return i
        i += 1
    return -1

def split_string_content(lines, start_idx, start_pos):
    first_line = lines[start_idx]
    first_prefix = first_line[:start_pos+1]
    rest = first_line[start_pos+1:]
    content_lines = []
    close_pos = find_closing_quote_pos(rest)
    if close_pos != -1:
        content_lines.append(rest[:close_pos])
        last_suffix = rest[close_pos+1:]
        return start_idx, start_pos + 1 + close_pos, content_lines, first_prefix, last_suffix
    content_lines.append(rest)
    i = start_idx + 1
    while i < len(lines):
        ln = lines[i]
        cpos = find_closing_quote_pos(ln)
        if cpos == -1:
            content_lines.append(ln)
            i += 1; continue
        content_lines.append(ln[:cpos] if cpos > 0 else "")
        last_suffix = ln[cpos+1:]
        return i, cpos, content_lines, first_prefix, last_suffix
    return start_idx, start_pos, [rest], first_prefix, ''

def preserve_backslash_endings(s: str):
    m = re.match(r'^(.*?)(\s*\\+)?$', s, flags=re.DOTALL)
    core = m.group(1); trailer = m.group(2) or ''
    return core, trailer

def normalize_source_typos(s: str) -> str:
    repls = [
        (r'\bflght\b', 'flight'),
        (r'\bScarmble\b', 'Scramble'),
        (r'\bBird Dong\b', 'Bird Dog'),
        (r"\bMig's\b", 'MiGs'),
    ]
    out = s
    for pat, repl in repls:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out

def apply_fixed_full_replacements(text: str) -> str:
    for src, dst in FIXED_FULL_REPLACEMENTS.items():
        pattern = r'(?i)\b' + re.escape(src) + r'\b'
        text = re.sub(pattern, dst, text)
    return text

def apply_phraseology(text: str) -> str:
    out = text
    for pat, repl in PHRASEOLOGY_RULES:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE | re.MULTILINE)
    return out

def protect_tokens(text: str):
    protected = {}
    # 1) [ ... ]
    def protect_bracket(m):
        idx = len(protected); key = f"{PLACE_OPEN}{idx}{PLACE_CLOSE}"
        protected[key] = m.group(0); return key
    tmp = re.sub(r'\[[^\]\n]+\]', protect_bracket, text)
    # 2) NO traducibles
    if NO_TRANSLATE_TERMS:
        pattern = r'\b(' + '|'.join([re.escape(w) for w in NO_TRANSLATE_TERMS]) + r')\b'
        def protect_term(m):
            idx = len(protected); key = f"{PLACE_OPEN}{idx}{PLACE_CLOSE}"
            protected[key] = m.group(0); return key
        tmp = re.sub(pattern, protect_term, tmp, flags=re.IGNORECASE)
    # 3) Callsigns/acrónimos
    if PROTECT_WORDS:
        pattern2 = r'\b(' + '|'.join(map(re.escape, PROTECT_WORDS)) + r')\b'
        def protect_word(m):
            idx = len(protected); key = f"{PLACE_OPEN}{idx}{PLACE_CLOSE}"
            protected[key] = m.group(0); return key
        tmp = re.sub(pattern2, protect_word, tmp, flags=re.IGNORECASE)
    return tmp, protected

def unprotect_tokens(text: str, protected: dict) -> str:
    for k, v in protected.items():
        if k in text:
            text = text.replace(k, v)
        else:
            inner = re.escape(k[len(PLACE_OPEN):-len(PLACE_CLOSE)])
            pattern = re.escape(PLACE_OPEN) + r'\s*' + inner + r'\s*' + re.escape(PLACE_CLOSE)
            text = re.sub(pattern, lambda m: v, text)
    return text

def should_translate_key(raw_key: str, translate_all=False):
    key = raw_key.lower()

     # Lista de claves específicas a excluir (case-insensitive)
    EXCLUDE_SPECIFIC_KEYS = {
        "dictkey_sortie_4",
    }

    if key in EXCLUDE_SPECIFIC_KEYS:
        return False, 'excluida-específica'
    
    if translate_all:
        blocked = any(key.startswith(p) for p in EXCLUDE_PREFIXES)
        return not blocked, ('incluida' if not blocked else 'excluida')
    
    ok = any(key.startswith(p) for p in TARGET_PREFIXES)
    return ok, ('objetivo' if ok else 'no-objetivo')

def clarify_otan_terms(text: str) -> str:
    """
    Añade aclaraciones entre paréntesis a los términos del glosario OTAN.
    Usa regex para coincidencias exactas y evita reemplazos dentro de otras palabras.
    """
    if not text:
        return text
        
    for code_name, real_name in GLOSSARY_OTAN.items():
        pattern = r'\b' + re.escape(code_name) + r'\b'
        replacement = f"{code_name} ({real_name})"
        text = re.sub(pattern, replacement, text)
    return text

# === Prompts ===

def build_prompt(items: list, style: str) -> dict:
    """
    Construye estructura independiente del proveedor.
    Devuelve {system_text, user_text_json_string}
    """
    # Importante: NO usar .format() con llaves JSON, para evitar KeyError por sustitución.
    system = (
        f"Eres un traductor especializado en frases de aviación militar para el simulador DCS World. "
        f"Traduce del inglés al español de España (es-ES) utilizando la fraseología técnica y militar aeronáutica adecuada. "
        f"**RESPETA Y NO TRADUZCAS BAJO NINGÚN CONCEPTO:** "
        f"- Todo el texto contenido entre corchetes [ej: [OVERLORD], [YOU]]. "
        f"- Acrónimos, códigos y términos breves OTAN/OTAN (ej: Scramble, Splash, Fox 1/2/3, SAR, CAP, SEAD, CAS, JTAC, AWACS, RTB, Bingo, Joker, Winchester, BRAA, Bullseye, Tally, Blind, No Joy, Spike, Magnum, Guns Guns Guns). "
        f"- Nombres en clave de la OTAN para equipos y aeronaves (ej: MiG-21 'Fishbed', Su-27 'Flanker', MiG-29 'Fulcrum', SA-6 'Gainful', ZSU-23-4 'Shilka'). "
        f"- Indicativos de radio (ej: ENFIELD 1-1, OVERLORD, HUMMER, TOWER, KNIFE 1-1). "
        f"- Modelos de aeronaves, armamento y sistemas (ej: F-5E, F-16C, Su-25T, AIM-9M, R-73, R-27ER, KH-25ML). "
        f"- Números, valores, unidades de medida y coordenadas (ej: 270 for 40, Angels 15, 450 knots, 15 NM, 350°). "
        f"- Nombres propios de lugares y calles (ej: Batumi, Kutaisi, Senaki, Gudauta). "
        f"**TRADUCCIÓN:** El estilo de la traducción debe ser {style}. "
        f"**PRECISIÓN:** La traducción debe ser extremadamente fiel al original. No inventes, añadas, omitas ni interpretes información. "
        f"**FORMATO:** Mantén escrupulosamente todos los caracteres de escape (\), saltos de línea, guiones y signos de puntuación del texto original. "
        f"**SALIDA:** Devuelve ÚNICA y EXCLUSIVAMENTE un objeto JSON válido, sin ningún otro texto antes o después, con la siguiente estructura exacta: "
        r'{"translations":[{"key":"DictKey_ActionText_1234", "text":"Texto traducido aquí."}]}'
    )
    user_payload = {"translations":[{"key":it["key"], "text":it["text"]} for it in items]}
    user = (
        "Traduce los 'text' a español (es-ES). No modifiques lo entre corchetes ni los acrónimos indicados. "
        "Mantén las barras invertidas \\ tal cual. Responde ÚNICAMENTE con JSON en el formato indicado.\n"
        + json.dumps(user_payload, ensure_ascii=False)
    )
    return {"system": system, "user": user}
def call_openai_like(api_base: str, api_key: str, model: str, system_text: str, user_text: str, timeout=60):
    url = api_base.rstrip('/') + "/chat/completions"
    headers = {"Content-Type":"application/json","Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "messages": [{"role":"system","content":system_text},{"role":"user","content":user_text}], "temperature": 0.2}
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def call_azure_openai(endpoint: str, api_key: str, deployment: str, api_version: str, system_text: str, user_text: str, timeout=60):
    url = endpoint.rstrip('/') + f"/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    headers = {"Content-Type":"application/json","api-key": api_key}
    payload = {"messages":[{"role":"system","content":system_text},{"role":"user","content":user_text}], "temperature":0.2}
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def call_openrouter(api_base: str, api_key: str, model: str, system_text: str, user_text: str, timeout=60):
    url = api_base.rstrip('/') + "/chat/completions"
    headers = {
        "Content-Type":"application/json",
        "Authorization": f"Bearer {api_key}",
        # Opcional, pero recomendado por OpenRouter:
        "HTTP-Referer": "https://local.tool/",
        "X-Title": "DCS Dictionary Translator"
    }
    payload = {"model": model, "messages":[{"role":"system","content":system_text},{"role":"user","content":user_text}], "temperature":0.2}
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def call_anthropic(api_base: str, api_key: str, model: str, system_text: str, user_text: str, version: str, timeout=60):
    url = api_base.rstrip('/') + "/v1/messages"
    headers = {
        "Content-Type":"application/json",
        "x-api-key": api_key,
        "anthropic-version": version
    }
    payload = {
        "model": model,
        "max_tokens": 2000,
        "system": system_text,
        "messages": [
            {"role":"user", "content": user_text}
        ]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    # Anthropic devuelve lista de bloques; concatenamos textos
    parts = data.get("content", [])
    text = "".join(p.get("text","") for p in parts if p.get("type")=="text")
    return text

def call_llm(engine: str, cfg: dict, model_override: str, messages: dict, timeout=60, retries=3, sleep=2) -> dict:
    system_text, user_text = messages["system"], messages["user"]
    last_err = None
    for _ in range(retries):
        try:
            if engine == 'chatgpt':
                api_key = cfg.get('API_CHATGPT') or os.getenv('API_CHATGPT')
                api_base = cfg.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
                model = model_override or cfg.get('OPENAI_MODEL', 'gpt-4o-mini')
                content = call_openai_like(api_base, api_key, model, system_text, user_text, timeout)
            elif engine == 'deepseek':
                api_key = cfg.get('API_DEEPSEEK') or os.getenv('API_DEEPSEEK')
                api_base = cfg.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
                model = model_override or cfg.get('DEEPSEEK_MODEL', 'deepseek-chat')
                content = call_openai_like(api_base, api_key, model, system_text, user_text, timeout)
            elif engine == 'azure':
                api_key = cfg.get('API_AZURE_OPENAI') or os.getenv('API_AZURE_OPENAI')
                endpoint = cfg.get('AZURE_OPENAI_ENDPOINT')
                deployment = model_override or cfg.get('AZURE_OPENAI_DEPLOYMENT')
                api_version = cfg.get('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
                if not endpoint or not deployment:
                    raise RuntimeError("Faltan AZURE_OPENAI_ENDPOINT o AZURE_OPENAI_DEPLOYMENT en keys.")
                content = call_azure_openai(endpoint, api_key, deployment, api_version, system_text, user_text, timeout)
            elif engine == 'openrouter':
                api_key = cfg.get('API_OPENROUTER') or os.getenv('API_OPENROUTER')
                api_base = cfg.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
                model = model_override or cfg.get('OPENROUTER_MODEL', 'openrouter/auto')
                content = call_openrouter(api_base, api_key, model, system_text, user_text, timeout)
            elif engine == 'anthropic':
                api_key = cfg.get('API_ANTHROPIC') or os.getenv('API_ANTHROPIC')
                api_base = cfg.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
                version = cfg.get('ANTHROPIC_VERSION', '2023-06-01')
                model = model_override or cfg.get('ANTHROPIC_MODEL', 'claude-3-haiku-20240307')
                content = call_anthropic(api_base, api_key, model, system_text, user_text, version, timeout)
            else:
                raise RuntimeError(f"Engine no soportado: {engine}")
            return {"ok": True, "content": content}
        except Exception as e:
            last_err = str(e)
        time.sleep(sleep)
    return {"ok": False, "error": last_err}

# === Post-edición ES ===
def post_edit_spanish(text: str, style: str) -> str:
    out = text
    cardinals = {
        r'\bfrom\s+the\s+north\b': 'desde el norte',
        r'\bfrom\s+the\s+south\b': 'desde el sur',
        r'\bfrom\s+the\s+east\b': 'desde el este',
        r'\bfrom\s+the\s+west\b': 'desde el oeste',
        r'\bfrom\s+south\s+low\s+alt(?:itude)?\b': 'desde el sur a baja altitud',
    }
    for pat, repl in cardinals.items():
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    common = [
        (r'\blow\s+alt(itude)?\b', 'baja altitud'),
        (r'\bmedium\s+alt(itude)?\b', 'media altitud'),
        (r'\bhigh\s+alt(itude)?\b', 'alta altitud'),
        (r'\bcoming\s+in\s+fast\b', 'se acercan rápido'),
        (r'\bcoming\s+in\s+hot\b', 'se aproximan rápido'),
        (r'\bincoming\b', 'entrantes'),
        (r'\bbogies?\s+incoming\b', 'Bogies entrantes'),
        (r'^\s*(the\s+)?mi[gq]\'?s?\s+are\s+down\s*!', '¡Todos los MiGs derribados!'),
        (r'\ball\s+clear\b', 'Todo despejado'),
        (r'\bno\s+other\s+fighters\b', 'no hay más cazas'),
        (r'\bfighters?\b', 'cazas'),
    ]
    for pat, repl in common:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE | re.MULTILINE)
    if style == 'formal':
        style_rules = [
            (r'\bturn\s+left\b', 'Vire a la izquierda'),
            (r'\bturn\s+right\b', 'Vire a la derecha'),
            (r'\bcheck\s+your\s+heading\b', 'Verifique el rumbo'),
        ]
    elif style == 'brevity':
        style_rules = [
            (r'\bturn\s+left\b', 'Vire a la izquierda'),
            (r'\bturn\s+right\b', 'Vire a la derecha'),
            (r'\bcheck\s+(your\s+)?heading\b', 'corrige rumbo'),
        ]
    else:
        style_rules = [
            (r'\bturn\s+left\b', 'Gire a la izquierda'),
            (r'\bturn\s+right\b', 'Gire a la derecha'),
            (r'\bcheck\s+(your\s+)?heading\b', 'comprueba el rumbo'),
        ]
    for pat, repl in style_rules:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    out = re.sub(r'\s+,', ',', out)
    out = re.sub(r'\s+!', '!', out)
    out = re.sub(r'\s+\.', '.', out)
    return out

# === Flujo principal ===
def main():
    ap = argparse.ArgumentParser(description="Traductor DCS con LLM externo (OpenAI/DeepSeek/Azure/OpenRouter/Anthropic).")
    ap.add_argument('input')
    ap.add_argument('--engine', required=True, choices=['chatgpt','deepseek','azure','openrouter','anthropic'])
    ap.add_argument('--keys', required=True, help='Fichero con API keys y parámetros')
    ap.add_argument('--model', default=None, help='Modelo o deployment a usar')
    ap.add_argument('--style', default='formal', choices=['brevity','neutral','formal'])
    ap.add_argument('--translate-all', action='store_true')
    ap.add_argument('--batch-size', type=int, default=40)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        print(f"ERROR: no existe el archivo: {inp}"); sys.exit(2)

    keyfile = Path(args.keys)
    if not keyfile.exists():
        print(f"ERROR: no existe el fichero de keys: {keyfile}"); sys.exit(2)

    cfg = load_keys(keyfile)

    lines = inp.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
    out_lines = list(lines)
    n_lines = len(lines)

    key_re = re.compile(r'\["(?P<key>dictkey_[^"]+)"\]\s*=\s*', flags=re.IGNORECASE)

    # Recopilar objetivos
    to_process = []
    texts_for_api = []
    for i, line in enumerate(lines):
        m = key_re.search(line)
        if not m:
            continue
        raw_key = m.group('key')
        should, why = should_translate_key(raw_key, args.translate_all)
        if not should:
            continue
        eq_end_pos = m.end()
        start_quote_pos = line.find('"', eq_end_pos)
        start_idx = i
        base_line = line
        while start_quote_pos == -1 and start_idx + 1 < n_lines:
            start_idx += 1
            base_line = lines[start_idx]
            start_quote_pos = base_line.find('"')
            if start_quote_pos != -1:
                break
        if start_quote_pos == -1:
            continue
        end_idx, end_pos, content_lines, first_prefix, last_suffix = split_string_content(lines, start_idx, start_quote_pos)
        original_concat = ''.join(cl.rstrip('\n') for cl in content_lines)

        prepared_lines = []
        protected_maps = []
        for cl in content_lines:
            core, trailer = preserve_backslash_endings(cl.rstrip('\n'))
            core_norm = normalize_source_typos(core)
            if '[' not in core_norm and ']' not in core_norm:
                core_norm = apply_fixed_full_replacements(core_norm)
                core_norm = apply_phraseology(core_norm)
            tmp, protected = protect_tokens(core_norm)
            prepared_lines.append((tmp, trailer))
            protected_maps.append(protected)

        to_process.append({
            "raw_key": raw_key,
            "i": i,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "first_prefix": first_prefix,
            "last_suffix": last_suffix,
            "content_lines": content_lines,
            "prepared_lines": prepared_lines,
            "protected_maps": protected_maps
        })

        for li, (tmp, trailer) in enumerate(prepared_lines):
            tmp_key = f"{raw_key}__line{li}"
            texts_for_api.append({"key": tmp_key, "text": tmp})

    if not texts_for_api:
        print("[INFO] No se encontraron propiedades objetivo que traducir (¿ya estaban en español?).")
        sys.exit(0)

    def chunks(lst, n):
        for x in range(0, len(lst), n):
            yield lst[x:x+n]

    translations = {}

    if args.dry_run:
        print("[DRY-RUN] Ejemplo de payload que se enviaría al modelo:")
        sample = list(chunks(texts_for_api, min(args.batch_size, len(texts_for_api))))[0]
        prompt = build_prompt(sample, args.style)
        print(json.dumps({"engine": args.engine, "model": args.model, "messages": prompt}, ensure_ascii=False, indent=2))
        print("No se realizaron llamadas a la IA (--dry-run).")
        sys.exit(0)

    batch_id = 0
    for batch in chunks(texts_for_api, args.batch_size):
        batch_id += 1
        prompt = build_prompt(batch, args.style)
        if not args.quiet:
            print(f"[API] Lote {batch_id}: {len(batch)} items -> {args.engine}/{args.model or 'default'}")
        resp = call_llm(args.engine, cfg, args.model, prompt)
        if not resp["ok"]:
            print(f"[ERROR] Falló la llamada LLM: {resp['error']}")
            sys.exit(3)
        content = resp["content"].strip()
        if not content.startswith('{'):
            m = re.search(r'\{.*\}', content, flags=re.DOTALL)
            content = m.group(0) if m else content
        try:
            data = json.loads(content)
            for t in data.get("translations", []):
                translations[t["key"]] = t["text"]
        except Exception as e:
            print("[WARN] No se pudo parsear JSON devuelto. Contenido crudo:\n", content[:500])
            raise

    # Reconstruir
    for item in to_process:
        start_idx = item["start_idx"]
        end_idx = item["end_idx"]
        first_prefix = item["first_prefix"]
        last_suffix = item["last_suffix"]
        prepared_lines = item["prepared_lines"]
        protected_maps = item["protected_maps"]
        raw_key = item["raw_key"]

        rebuilt_lines = []
        for li, ((tmp, trailer), prot) in enumerate(zip(prepared_lines, protected_maps)):
            tmp_key = f"{raw_key}__line{li}"
            translated = translations.get(tmp_key, tmp)
            translated = unprotect_tokens(translated, prot)
            translated = post_edit_spanish(translated, args.style)
            # Añadir aclaraciones OTAN después de todo el procesamiento
            translated = clarify_otan_terms(translated)
            translated = translated.replace('"', r'\"')
            rebuilt_lines.append(translated + trailer)

        out_lines[start_idx] = first_prefix + rebuilt_lines[0] + ("\n" if out_lines[start_idx].endswith("\n") else "")
        for k in range(1, len(rebuilt_lines)-1):
            idx = start_idx + k
            out_lines[idx] = rebuilt_lines[k] + ("\n" if out_lines[idx].endswith("\n") else "")
        if end_idx > start_idx:
            out_lines[end_idx] = rebuilt_lines[-1] + '"' + last_suffix
            if out_lines[end_idx].endswith("\n") is False and (last_suffix.endswith("\n") or True):
                out_lines[end_idx] += "\n"
        else:
            out_lines[start_idx] = first_prefix + rebuilt_lines[0] + '"' + last_suffix
            if out_lines[start_idx].endswith("\n") is False and (last_suffix.endswith("\n") or True):
                out_lines[start_idx] += "\n"

    assert len(out_lines) == len(lines), f"ERROR: número de líneas cambió {len(lines)} -> {len(out_lines)}"

    outp = build_output_path(inp)
    Path(outp).write_text(''.join(out_lines), encoding='utf-8', newline='')
    if not args.quiet:
        print(f"[OK] Archivo escrito: {outp}")
        print(f"[INFO] Traducciones recibidas: {len(translations)} entradas")

if __name__ == '__main__':
    main()