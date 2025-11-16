#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio de traducción DCS - Motor de traducción integrado
Basado en dcs_lua_translate.py v22.1
"""
import hashlib
import json
import logging
import os
import re
import time
import unicodedata
import shutil
import zipfile
from typing import Callable

# Importar el nuevo detector FC optimizado
from app.utils.fc_detector import get_fc_detector, DetectionResult
import glob
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import requests

try:
    import yaml
    YAML_AVAILABLE = True
except Exception:
    YAML_AVAILABLE = False

from config.settings import TRANSLATIONS_DIR, PROMPTS_DIR, LOGS_DIR
from app.services.centralized_cache import CentralizedCache
from app.services.lm_studio import LMStudioService
from app.utils.file_utils import ensure_directory
from app.utils.validators import validate_translation_config

# === FUNCIONES HELPER PARA EL MOTOR DE TRADUCCIÓN ===

def key_is_target(key: str, keys_filter: Optional[List[str]], cfg: Dict) -> bool:
    """Determina si una clave debe ser traducida según filtros y configuración"""
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

def unprotect_tokens(text: str, mapping: Dict[str, str]) -> str:
    """Restaura tokens protegidos en el texto"""
    for tok, val in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(tok, val)
    return text

def build_rule_flags(rule: Dict) -> int:
    """Construye flags regex desde configuración"""
    flags = 0
    for f in (rule.get("flags") or []):
        f = str(f).upper().strip()
        if f in ("I", "IGNORECASE"): flags |= re.IGNORECASE
        elif f in ("M", "MULTILINE"): flags |= re.MULTILINE
        elif f in ("S", "DOTALL"): flags |= re.DOTALL
    return flags

def apply_phraseology_rules(text: str, cfg: Dict) -> str:
    """Aplica reglas de fraseología desde configuración"""
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
    """Aplica reglas de post-procesamiento"""
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
    """Aplica glosario OTAN desde configuración"""
    glossary = cfg.get("GLOSSARY_OTAN", {})
    if not glossary:
        return text
    for en_term, es_translation in glossary.items():
        pattern = r"\b" + re.escape(en_term) + r"\b"
        text = re.sub(pattern, es_translation, text, flags=re.IGNORECASE)
    return text

def apply_smart_splash_rules(text: str, cfg: Dict) -> str:
    """Aplica reglas inteligentes para términos 'splash'"""
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

def protect_terms(text: str, terms) -> str:
    """Protege términos específicos evitando coincidencias dentro de palabras"""
    if not terms:
        return text
    for term in sorted(set(terms), key=len, reverse=True):
        pat = re.compile(rf'(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])', re.IGNORECASE)
        text = pat.sub(term, text)
    return text

def escape_for_lua(s: str) -> str:
    """Escapa texto para inserción segura en archivos Lua"""
    s = s.replace('\\', '\\\\')
    s = s.replace('"', r'\"')
    return s

def format_for_jsonl(en: str, es: str) -> str:
    """Formatea par EN-ES para datos de fine-tuning"""
    user_prompt = f"Traduce al español: '{en}'"
    assistant_response = es
    return json.dumps({"text": f"### User: {user_prompt} ### Assistant: {assistant_response}"}, ensure_ascii=False)

# === CLASE SEGMENT PARA MANEJO DE SEGMENTOS DE TRADUCCIÓN ===

class Segment:
    """Segmento de texto para traducción con manejo de metadatos y protección de tokens"""
    
    def __init__(self, key: str, index: int, raw_seg: str, lb: str, protect_brackets: bool = True):
        self.key = key
        self.index = index
        self.raw_seg = raw_seg
        self.lb = lb
        self.protect_brackets = protect_brackets

        # Regex patterns necesarios
        LEADING_WHITESPACE_REGEX = re.compile(r'^(?P<ws>\s*)(?P<text>.*)$', flags=re.DOTALL)
        TRAIL_PUNCT_REGEX = re.compile(r'^(?P<core>.*?)(?P<punct>[\s\.\!\?\,;:\u2026]*)$', flags=re.DOTALL)
        BRACKET_REGEX = re.compile(r'\[[^\]\r\n]+\]')
        
        ws_match = LEADING_WHITESPACE_REGEX.match(raw_seg)
        self.leading_ws = ws_match.group("ws") if ws_match else ""
        text_without_ws = ws_match.group("text") if ws_match else raw_seg

        m = TRAIL_PUNCT_REGEX.match(text_without_ws)
        self.core = m.group("core")
        self.punct = m.group("punct")
        self.br_tokens: Dict[str, str] = {}

        # Protección opcional de [ ... ]
        if self.protect_brackets:
            self.clean_for_model = self._protect_brackets(self.core, BRACKET_REGEX)
        else:
            self.clean_for_model = self.core

        src_for_hash = f"{self.key}#{self.index}#{self.core.strip()}"
        h = hashlib.sha1(src_for_hash.encode("utf-8")).hexdigest()[:16]
        self.id = f"id_{h}"
        self.es: Optional[str] = None

    def _protect_brackets(self, text: str, bracket_regex) -> str:
        """Protege tokens entre corchetes reemplazándolos por placeholders"""
        def repl(m):
            token = f"BR_{len(self.br_tokens) + 1}"
            self.br_tokens[token] = m.group(0)
            return token
        return bracket_regex.sub(repl, text)


class TranslationEngine:
    """Motor de traducción DCS - Servicio principal de traducción"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Inicializar servicio LM Studio
        self.lm_studio_service = LMStudioService()
        
        # Session HTTP para cancelación agresiva
        self.http_session = requests.Session()
        self.http_session.timeout = 5  # Timeout muy corto por defecto
        
        # Regex patterns del motor original
        self.entry_regex = re.compile(
            r'(?P<pre>\[\s*"(?P<key>[^"]+)"\s*\]\s*=\s*")'
            r'(?P<value>(?:[^"\\]|\\.|\\\r?\n)*)'
            r'(?P<post>")',
            flags=re.DOTALL
        )
        self.line_split_regex = re.compile(r'(?P<seg>.*?)(?P<lb>\\\r?\n|$)', flags=re.DOTALL)
        self.bracket_regex = re.compile(r'\[[^\]\r\n]+\]')
        self.trail_punct_regex = re.compile(r'^(?P<core>.*?)(?P<punct>[\s\.\!\?\,;:\u2026]*)$', flags=re.DOTALL)
        self.leading_whitespace_regex = re.compile(r'^(?P<ws>\s*)(?P<text>.*)$', flags=re.DOTALL)
        self.clean_bad_chars = re.compile(r'["\\]+')
        
        # Inicializar cache centralizado
        self.centralized_cache = CentralizedCache()
        
        # Inicializar utilidades del orquestador
        self._init_orchestrator_utils()
    
    def _init_orchestrator_utils(self):
        """Inicializa las utilidades del orquestador integradas"""
        # Configuración base del motor
        from config.settings import BASE_DIR, TRANSLATIONS_DIR
        self.base_dir = BASE_DIR
        self.campaigns_dir = TRANSLATIONS_DIR  # Usar la ruta correcta: app/data/traducciones
        ensure_directory(self.campaigns_dir)
        
        # Limpiar directorios problemáticos existentes al inicializar
        self._prevent_problematic_directories()
        
        # Referencia al orquestador para verificar cancelación
        self.orchestrator = None
        
    def _check_cancellation(self) -> bool:
        """Verifica si se ha solicitado cancelación desde el orquestador"""
        if self.orchestrator and hasattr(self.orchestrator, 'status'):
            return self.orchestrator.status.get('cancellation_requested', False)
        return False
        
    def cancel_current_translation(self):
        """Marca la cancelación de la traducción actual"""
        self.logger.info("🛑 Motor de traducción: Señal de cancelación recibida")
        if self.orchestrator and hasattr(self.orchestrator, 'status'):
            self.orchestrator.status['cancellation_requested'] = True
            self.logger.info("✅ Motor de traducción: Flag de cancelación activado")
        
        # Cerrar agresivamente la session HTTP para cancelar requests en curso
        try:
            self.logger.info("🔌 Cerrando sesión HTTP para cancelar requests en curso...")
            self.http_session.close()
            # Crear nueva sesión para futuros requests (si es necesario)
            self.http_session = requests.Session()
            self.http_session.timeout = 5
            self.logger.info("✅ Sesión HTTP reiniciada")
        except Exception as e:
            self.logger.warning(f"⚠️ Error cerrando sesión HTTP: {e}")
        
    # === UTILIDADES DEL ORQUESTADOR INTEGRADAS ===
    
    
    def _prevent_problematic_directories(self):
        """Previene directorios problemáticos y limpia archivos mal ubicados"""
        import shutil
        from datetime import datetime
        
        if not os.path.exists(self.campaigns_dir):
            return
        
        cleaned_count = 0
        
        # 1. Limpiar directorios problemáticos (concatenados)
        for item in os.listdir(self.campaigns_dir):
            item_path = os.path.join(self.campaigns_dir, item)
            
            if os.path.isdir(item_path) and "_BFM_" in item and "_-_" in item:
                self.logger.warning(f"🗑️  Eliminando directorio problemático: {item}")
                
                # Crear backup si tiene contenido
                if any(os.listdir(item_path)):
                    backup_name = f"{item}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_path = os.path.join(self.campaigns_dir, backup_name)
                    shutil.move(item_path, backup_path)
                    self.logger.info(f"📦 Backup creado: {backup_name}")
                else:
                    shutil.rmtree(item_path)
                    self.logger.info(f"✅ Directorio problemático eliminado: {item}")
                cleaned_count += 1
        
        # 2. Limpiar archivos mal ubicados (fuera de out_lua)
        self._clean_misplaced_files()
        
        # 3. Limpiar reportes de sesión mal ubicados
        self._clean_misplaced_session_reports()
        
        if cleaned_count > 0:
            self.logger.info(f"🧹 Limpieza completada: {cleaned_count} directorios problemáticos procesados")
    
    def _clean_misplaced_files(self):
        """Limpia archivos de traducción que están fuera de out_lua"""
        import glob
        
        if not os.path.exists(self.campaigns_dir):
            return
        
        moved_count = 0
        
        # Buscar todas las estructuras de campaña/misión válidas
        for campaign_dir in os.listdir(self.campaigns_dir):
            campaign_path = os.path.join(self.campaigns_dir, campaign_dir)
            
            if not os.path.isdir(campaign_path):
                continue
            
            # Buscar directorios de misión dentro de la campaña
            for mission_dir in os.listdir(campaign_path):
                mission_path = os.path.join(campaign_path, mission_dir)
                
                if not os.path.isdir(mission_path):
                    continue
                
                # Verificar si existe out_lua
                out_lua_path = os.path.join(mission_path, "out_lua")
                if not os.path.exists(out_lua_path):
                    continue
                
                # Buscar archivos problemáticos en el directorio base de misión
                problematic_files = []
                problematic_files.extend(glob.glob(os.path.join(mission_path, "*.translated.lua")))
                problematic_files.extend(glob.glob(os.path.join(mission_path, "*.translations.jsonl")))
                problematic_files.extend(glob.glob(os.path.join(mission_path, "translation_cache.json")))
                
                for src_file in problematic_files:
                    try:
                        filename = os.path.basename(src_file)
                        dst_file = os.path.join(out_lua_path, filename)
                        
                        # Mover archivo a out_lua si no existe allí
                        if not os.path.exists(dst_file):
                            shutil.move(src_file, dst_file)
                            self.logger.info(f"📁 Archivo movido: {src_file} -> {dst_file}")
                            moved_count += 1
                        else:
                            # Si ya existe en out_lua, eliminar el duplicado
                            os.remove(src_file)
                            self.logger.info(f"🗑️  Archivo duplicado eliminado: {src_file}")
                            moved_count += 1
                            
                    except Exception as e:
                        self.logger.error(f"❌ Error moviendo {src_file}: {e}")
        
        if moved_count > 0:
            self.logger.info(f"📂 Archivos reorganizados: {moved_count} archivos movidos a out_lua")
    
    def _clean_misplaced_session_reports(self):
        """Limpia reportes de sesión antiguos y mueve reportes mal ubicados"""
        import glob
        import json
        from datetime import datetime
        
        if not os.path.exists(self.campaigns_dir):
            return
        
        moved_count = 0
        removed_count = 0
        
        # 1. Limpiar reportes de sesión antiguos (session_report_*) del directorio base
        session_reports = glob.glob(os.path.join(self.campaigns_dir, "session_report_*.json"))
        
        for report_file in session_reports:
            try:
                # Crear backup antes de eliminar
                backup_name = f"session_report_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = os.path.join(self.campaigns_dir, backup_name)
                shutil.copy2(report_file, backup_path)
                
                # Eliminar el reporte de sesión antiguo
                os.remove(report_file)
                self.logger.info(f"🗑️  Reporte de sesión antiguo eliminado: {report_file} (backup: {backup_name})")
                removed_count += 1
                
            except Exception as e:
                self.logger.error(f"❌ Error eliminando reporte antiguo {report_file}: {e}")
        
        # 2. Buscar reportes mal ubicados en subdirectorios
        session_reports = glob.glob(os.path.join(self.campaigns_dir, "**", "session_report_*.json"), recursive=True)
        
        for report_file in session_reports:
            try:
                # Crear backup y eliminar reportes de sesión antiguos en subdirectorios
                parent_dir = os.path.dirname(report_file)
                backup_name = f"session_report_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = os.path.join(parent_dir, backup_name)
                
                shutil.copy2(report_file, backup_path)
                os.remove(report_file)
                self.logger.info(f"�️  Reporte de sesión antiguo eliminado: {report_file} (backup: {backup_name})")
                removed_count += 1
                    
            except Exception as e:
                self.logger.error(f"❌ Error procesando reporte {report_file}: {e}")
        
        total_cleaned = moved_count + removed_count
        if total_cleaned > 0:
            self.logger.info(f"📊 Limpieza de reportes completada: {removed_count} reportes antiguos eliminados")
    
    def _generate_mission_report(self, campaign_name: str, mission_name: str, mission_result: Dict[str, Any], 
                                workflow_config: Dict[str, Any]) -> str:
        """Genera reporte individual para una misión específica"""
        import json
        from datetime import datetime
        
        # Obtener directorio de la misión
        mission_dirs = self.ensure_mission_local_dirs(campaign_name, mission_name)
        mission_dir = mission_dirs["mission_base"]
        
        # Generar ID único para este reporte
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"mission_report_{timestamp}.json"
        report_path = os.path.join(mission_dir, report_filename)
        
        # Preparar datos del reporte
        report_data = {
            'report_type': 'mission',
            'timestamp': datetime.now().isoformat(),
            'session_id': timestamp,
            'campaign': {
                'name': campaign_name,
                'path': workflow_config.get('campaign_path', '')
            },
            'mission': {
                'name': mission_name,
                'file': mission_name if mission_name.endswith('.miz') else f"{mission_name}.miz",
                'success': mission_result.get('success', False),
                'result': mission_result
            },
            'workflow': {
                'mode': workflow_config.get('mode', 'translate'),
                'batch_size': workflow_config.get('batch_size', 4),
                'timeout': workflow_config.get('timeout', 200),
                'lm_config': workflow_config.get('lm_config', {}),
                'prompt_file': workflow_config.get('prompt_file', '')
            },
            'directories': {
                'mission_base': mission_dirs["mission_base"],
                'extracted': mission_dirs["extracted"],
                'out_lua': mission_dirs["out_lua"],
                'finalizado': mission_dirs["finalizado"],
                'backup': mission_dirs["backup"]
            }
        }
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"📄 Reporte de misión generado: {report_path}")
            return report_path
            
        except Exception as e:
            self.logger.error(f"❌ Error generando reporte de misión: {e}")
            return ""

    def _natural_key(self, s: str):
        """Genera clave natural para ordenamiento alfanumérico"""
        return [int(t) if t.isdigit() else t.lower() for t in re.findall(r"\d+|\D+", s)]
    
    def _mission_num(self, name: str) -> int:
        """Extrae número de misión desde el nombre"""
        base = unicodedata.normalize("NFKC", name).replace("\u00A0", " ")
        m = re.search(r"-C\s*(\d+)", base, flags=re.I)
        return int(m.group(1)) if m else float("inf")
    
    def _mission_sort_key(self, path: str):
        """Genera clave de ordenación para misiones"""
        base = os.path.basename(path)
        num = self._mission_num(base)
        compact = re.sub(r"\s+", "", base)
        return (num, self._natural_key(compact))
    
    def find_campaigns(self, root_dir: str) -> List[Tuple[str, str]]:
        """Encuentra campañas en un directorio"""
        out = []
        if not os.path.isdir(root_dir): 
            return out
        
        try:
            for entry in sorted(os.listdir(root_dir)):
                p = os.path.join(root_dir, entry)
                if os.path.isdir(p):
                    # Buscar archivos .miz
                    mizs = [f for f in os.listdir(p) if f.lower().endswith(".miz")]
                    if mizs:
                        out.append((entry, p))
        except (OSError, IOError) as e:
            self.logger.warning(f"Error escaneando {root_dir}: {e}")
            
        return out
    
    def find_miz_files_grouped(self, campaign_path: str):
        """Agrupa archivos .miz por tipo (normales y FC) con detección mejorada"""
        try:
            all_miz = [os.path.join(campaign_path, f) for f in os.listdir(campaign_path) if f.lower().endswith(".miz")]
        except (OSError, IOError):
            return [], []
        
        # Separar archivos FC y normales usando detección mejorada
        normals = []
        fcs = []
        
        # Logging temporal para debugging
        print(f"DEBUG: Procesando {len(all_miz)} archivos .miz en {campaign_path}")
        
        for i, miz_path in enumerate(all_miz):
            filename = os.path.basename(miz_path)
            is_fc = self._is_flaming_cliffs_mission(filename)
            
            # Mostrar algunos ejemplos para debugging
            if i < 5:  # Solo los primeros 5 archivos
                print(f"DEBUG: Archivo {i+1}: '{filename}' -> {'FC' if is_fc else 'NORMAL'}")
            
            if is_fc:
                fcs.append(miz_path)
            else:
                normals.append(miz_path)
        
        normals.sort(key=self._mission_sort_key)
        fcs.sort(key=self._mission_sort_key)
        
        return normals, fcs
    
    def _is_flaming_cliffs_mission(self, filename: str) -> bool:
        """
        Detecta si un archivo de misión es de Flaming Cliffs usando el detector optimizado.
        
        Args:
            filename: Nombre del archivo de misión
            
        Returns:
            bool: True si es una misión FC, False si es normal
        """
        try:
            detector = get_fc_detector()
            result = detector.detect(filename)
            
            if result.is_fc:
                self.logger.info(
                    f"FC detectado: '{filename}' | Patrón: {result.pattern_name} | "
                    f"Confianza: {result.confidence:.2f} | Tiempo: {result.processing_time_ms:.2f}ms"
                )
            else:
                self.logger.debug(f"Archivo normal: '{filename}' (no es FC)")
            
            return result.is_fc
            
        except Exception as e:
            self.logger.error(f"Error en detección FC para '{filename}': {e}")
            return False
    
    def _get_fc_pattern_used(self, filename: str) -> str:
        """
        Detecta qué patrón FC específico coincide usando el detector optimizado.
        
        Args:
            filename: Nombre del archivo de misión
            
        Returns:
            str: Nombre del patrón usado o "unknown"
        """
        try:
            detector = get_fc_detector()
            result = detector.detect(filename)
            
            if result.is_fc and result.pattern_name:
                return result.pattern_name
            
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"Error obteniendo patrón FC para '{filename}': {e}")
            return "unknown"
    
    def _get_base_mission_name(self, filename: str) -> str:
        """Extrae el nombre base de una misión, eliminando sufijos FC"""
        # Remover extensión
        base = os.path.splitext(filename)[0]
        
        # Patrones a remover para obtener el nombre base
        fc_suffixes = [
            r'-FC-?\d*$',      # -FC-01, -FC-, -FC
            r'_FC_?\d*$',      # _FC_01, _FC_, _FC
            r'\.FC\.?\d*$',    # .FC.01, .FC., .FC
            r'-FlamingCliff.*$', # -FlamingCliff...
            r'_FlamingCliff.*$', # _FlamingCliff...
            r'Flaming.*$',     # Flaming...
            r'Cliff.*$',       # Cliff...
        ]
        
        for pattern in fc_suffixes:
            base = re.sub(pattern, '', base, flags=re.IGNORECASE)
        
        return base.strip(' -_.')
    
    def slugify(self, name: str) -> str:
        """Convierte nombre en slug válido para archivos"""
        s = re.sub(r"[^\w\s\-\.áéíóúüñÁÉÍÓÚÜÑ]", "_", name, flags=re.UNICODE)
        s = re.sub(r"\s+", "_", s)
        return s
    
    def normalize_stem(self, s: str) -> str:
        """Normaliza nombre de archivo"""
        if not s:
            return ""
        s = unicodedata.normalize("NFKC", s).replace("\u00A0", " ")
        return s.strip(" .")
    
    def campaign_finalizado_dir(self, campaign_name: str) -> str:
        """Directorio de campañas finalizadas"""
        base = os.path.join(self.campaigns_dir, self.slugify(campaign_name))
        return os.path.join(base, "finalizado")
    
    def campaign_out_lua_dir(self, campaign_name: str) -> str:
        """Directorio de archivos Lua de salida"""
        base = os.path.join(self.campaigns_dir, self.slugify(campaign_name))
        return os.path.join(base, "out_lua")
    
    def ensure_campaign_local_dirs(self, campaign_name: str) -> Dict[str, str]:
        """Crea directorio base para una campaña (sin subcarpetas - las misiones las crean)"""
        base = os.path.join(self.campaigns_dir, self.slugify(campaign_name))
        
        # Solo crear la carpeta base de la campaña
        ensure_directory(base)
        
        # Devolver paths para compatibilidad, pero solo el base se crea realmente
        paths = {
            "base": base,
            "extracted": os.path.join(base, "extracted"),  # No se crea
            "out_lua": os.path.join(base, "out_lua"),      # No se crea  
            "finalizado": os.path.join(base, "finalizado"), # No se crea
            "backup": os.path.join(base, "backup"),        # No se crea
        }
        return paths

    def ensure_mission_local_dirs(self, campaign_name: str, mission_name: str) -> Dict[str, str]:
        """Crea directorios locales para una misión específica dentro de una campaña"""
        campaign_base = os.path.join(self.campaigns_dir, self.slugify(campaign_name))
        mission_base = os.path.join(campaign_base, self.slugify(mission_name.replace('.miz', '')))
        
        paths = {
            "campaign_base": campaign_base,
            "mission_base": mission_base,
            "extracted": os.path.join(mission_base, "extracted"),
            "out_lua": os.path.join(mission_base, "out_lua"),
            "finalizado": os.path.join(mission_base, "finalizado"),
            "backup": os.path.join(mission_base, "backup"),
        }
        
        # Crear directorio base de campaña
        ensure_directory(campaign_base)
        
        # Crear directorios específicos de la misión
        for p in paths.values():
            ensure_directory(p)
        return paths
    
    def extract_miz(self, miz_path: str, dest_dir: str):
        """Extrae archivo .miz (ZIP) a directorio"""
        if os.path.isdir(dest_dir):
            shutil.rmtree(dest_dir, ignore_errors=True)
        ensure_directory(dest_dir)
        
        try:
            with zipfile.ZipFile(miz_path, "r") as zf:
                zf.extractall(dest_dir)
        except Exception as e:
            self.logger.error(f"Error extrayendo {miz_path}: {e}")
            raise
    
    def compress_miz(self, src_dir: str, output_miz_path: str):
        """Comprime directorio a archivo .miz (ZIP)"""
        ensure_directory(os.path.dirname(output_miz_path))
        
        try:
            with zipfile.ZipFile(output_miz_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(src_dir):
                    for f in files:
                        fp = os.path.join(root, f)
                        arc_name = os.path.relpath(fp, src_dir)
                        zf.write(fp, arc_name)
        except Exception as e:
            self.logger.error(f"Error comprimiendo a {output_miz_path}: {e}")
            raise
    
    def backup_miz(self, miz_path: str, backup_dir: str):
        """Crea backup de archivo .miz"""
        ensure_directory(backup_dir)
        try:
            backup_path = os.path.join(backup_dir, os.path.basename(miz_path))
            shutil.copy2(miz_path, backup_path)
            return backup_path
        except Exception as e:
            self.logger.error(f"Error creando backup de {miz_path}: {e}")
            raise
    
    def harvest_translator_logs(self, from_output_dir: str, campaign_name: str, mission_base: str):
        """Mueve logs del traductor al directorio central de logs"""
        if not from_output_dir or not os.path.isdir(from_output_dir):
            return
        
        pattern = os.path.join(from_output_dir, "dcs_translate_*.log")
        for src in glob.glob(pattern):
            try:
                safe_campaign = self.slugify(campaign_name)
                safe_mission = self.slugify(mission_base)
                dst = os.path.join(LOGS_DIR, f"{safe_campaign}__{safe_mission}__{os.path.basename(src)}")
                shutil.move(src, dst)
                self.logger.info(f"Log movido: {src} -> {dst}")
            except Exception as e:
                self.logger.warning(f"No se pudo mover log {src}: {e}")
    
    def zip_campaign_logs(self, campaign_name: str) -> str:
        """Crea ZIP con todos los logs de una campaña"""
        safe_c = self.slugify(campaign_name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(LOGS_DIR, f"logs_{safe_c}_{ts}.zip")
        
        candidates = glob.glob(os.path.join(LOGS_DIR, f"{safe_c}__*.log"))
        if not candidates:
            return ""
        
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for src in candidates:
                    zf.write(src, os.path.basename(src))
            
            self.logger.info(f"ZIP de logs creado: {zip_path}")
            return zip_path
        except Exception as e:
            self.logger.error(f"Error creando ZIP de logs: {e}")
            return ""
    
    # === FIN UTILIDADES DEL ORQUESTADOR ===

    def check_lm_studio_status(self, lm_url: str, lm_model: str = "test") -> Dict[str, Any]:
        """
        Verifica el estado de LM Studio y si hay modelos cargados
        
        Args:
            lm_url: URL base de LM Studio
            lm_model: Modelo de prueba (por defecto "test")
            
        Returns:
            Dict con información del estado: {
                'available': bool,
                'models_loaded': bool,
                'error_message': str,
                'suggestion': str
            }
        """
        status = {
            'available': False,
            'models_loaded': False,
            'error_message': '',
            'suggestion': ''
        }
        
        try:
            # Probar conectividad básica con una petición simple
            test_url = f"{lm_url.rstrip('/')}/chat/completions"
            test_body = {
                "model": lm_model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            response = self.http_session.post(test_url, json=test_body, timeout=10)
            status['available'] = True
            
            if response.status_code == 404:
                # Verificar si es el error de "no models loaded"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "")
                    
                    if "No models loaded" in error_msg:
                        status['error_message'] = "No hay modelos cargados en LM Studio"
                        status['suggestion'] = (
                            "Abre LM Studio y carga un modelo:\n"
                            "1. Ve a 'My Models' en LM Studio\n"
                            "2. Selecciona un modelo y haz clic en 'Load Model'\n"
                            "3. O usa el comando: lms load <nombre-del-modelo>"
                        )
                    else:
                        status['error_message'] = f"Error 404: {error_msg}"
                        status['suggestion'] = "Verifica que LM Studio esté ejecutándose correctamente"
                except:
                    status['error_message'] = "Error 404 desconocido"
                    status['suggestion'] = "Verifica que LM Studio esté ejecutándose y tenga modelos cargados"
            
            elif response.status_code == 200:
                status['models_loaded'] = True
            
            else:
                status['error_message'] = f"Error HTTP {response.status_code}: {response.text[:200]}"
                status['suggestion'] = "Verifica la configuración de LM Studio"
                
        except requests.exceptions.ConnectionError:
            status['error_message'] = "No se puede conectar con LM Studio"
            status['suggestion'] = (
                "Asegúrate de que LM Studio esté ejecutándose:\n"
                "1. Abre LM Studio\n"
                "2. Verifica que esté corriendo en el puerto correcto\n"
                f"3. URL esperada: {lm_url}"
            )
        except requests.exceptions.Timeout:
            status['available'] = True
            status['models_loaded'] = False  # Asumimos que está lento porque no tiene modelo cargado
            status['error_message'] = "LM Studio responde muy lento"
            status['suggestion'] = (
                "Modelo cargado pero no disponible para uso práctico:\n"
                "💡 Soluciones recomendadas:\n"
                "1. 🚀 Descargar un modelo más pequeño y rápido\n"
                "2. ⚡ Cerrar otras aplicaciones pesadas\n"
                "3. 🔄 Reiniciar LM Studio\n"
                "4. 📊 Verificar uso de RAM/GPU en Task Manager\n"
                "5. ⏱️ Aumentar timeout en configuración (actual: 10s)\n"
                "6. 🎯 Usar un modelo quantizado (Q4, Q5) en lugar de FP16"
            )
            status['performance_issue'] = True
            status['recommended_action'] = "switch_to_faster_model"
        except Exception as e:
            status['error_message'] = f"Error inesperado: {str(e)}"
            status['suggestion'] = "Contacta al soporte técnico"
            
        return status

    def get_lm_studio_models_with_performance_info(self, lm_url: str) -> Dict[str, Any]:
        """
        Obtiene lista de modelos disponibles en LM Studio con información de rendimiento
        
        Args:
            lm_url: URL base de LM Studio
            
        Returns:
            Dict con información de modelos y rendimiento
        """
        result = {
            'available_models': [],
            'faster_alternatives': [],
            'current_model_info': None,
            'performance_tips': []
        }
        
        try:
            # Obtener lista de modelos
            response = requests.get(f"{lm_url.rstrip('/')}/v1/models", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('data', [])
                
                for model in models:
                    model_id = model.get('id', model.get('name', ''))
                    model_info = {
                        'id': model_id,
                        'name': model.get('name', model_id),
                        'size_category': self._categorize_model_size(model_id),
                        'speed_rating': self._estimate_model_speed(model_id),
                        'recommended_for': self._get_model_recommendation(model_id)
                    }
                    result['available_models'].append(model_info)
                
                # Encontrar alternativas más rápidas
                fast_models = [m for m in result['available_models'] if m['speed_rating'] >= 4]
                result['faster_alternatives'] = sorted(fast_models, key=lambda x: x['speed_rating'], reverse=True)[:3]
                
                # Tips de rendimiento
                result['performance_tips'] = [
                    "🎯 Los modelos Q4 y Q5 son hasta 3x más rápidos que FP16",
                    "🚀 Modelos de 7B parámetros son más rápidos que 13B+",
                    "⚡ Phi-3 y Llama-3.1-8B son excelentes para traducción",
                    "💾 Asegúrate de tener suficiente RAM libre (8GB+)",
                    "🔧 Cierra navegadores y aplicaciones pesadas durante traducción"
                ]
                
        except Exception as e:
            self.logger.warning(f"No se pudo obtener información de modelos: {e}")
            result['performance_tips'] = [
                "⚠️ No se pudo conectar con LM Studio para obtener lista de modelos",
                "🔄 Verifica que LM Studio esté ejecutándose correctamente"
            ]
        
        return result

    def _categorize_model_size(self, model_name: str) -> str:
        """Categoriza el tamaño del modelo basado en su nombre"""
        model_lower = model_name.lower()
        if any(size in model_lower for size in ['1b', '2b', '3b']):
            return 'very_small'
        elif any(size in model_lower for size in ['7b', '8b']):
            return 'small'
        elif any(size in model_lower for size in ['13b', '14b', '15b']):
            return 'medium'
        elif any(size in model_lower for size in ['30b', '33b', '34b', '70b']):
            return 'large'
        else:
            return 'unknown'
    
    def _estimate_model_speed(self, model_name: str) -> int:
        """Estima la velocidad del modelo del 1-5 (5 = más rápido)"""
        model_lower = model_name.lower()
        
        # Modelos muy rápidos
        if any(fast in model_lower for fast in ['phi-3', 'gemma-2b', 'tinyllama']):
            return 5
        
        # Quantization afecta velocidad
        if 'q4' in model_lower or 'q5' in model_lower:
            speed_bonus = 1
        elif 'q8' in model_lower:
            speed_bonus = 0
        elif any(slow in model_lower for slow in ['fp16', 'f16']):
            speed_bonus = -1
        else:
            speed_bonus = 0
            
        # Tamaño base
        size_category = self._categorize_model_size(model_name)
        base_speeds = {
            'very_small': 5,
            'small': 4, 
            'medium': 3,
            'large': 2,
            'unknown': 3
        }
        
        final_speed = base_speeds.get(size_category, 3) + speed_bonus
        return max(1, min(5, final_speed))  # Mantener entre 1-5
    
    def _get_model_recommendation(self, model_name: str) -> str:
        """Obtiene recomendación de uso para el modelo"""
        model_lower = model_name.lower()
        
        if 'phi-3' in model_lower:
            return "Excelente para traducción rápida y precisa"
        elif 'llama' in model_lower and any(size in model_lower for size in ['7b', '8b']):
            return "Muy bueno para traducción general"
        elif 'gemma' in model_lower:
            return "Rápido y eficiente para textos cortos"
        elif 'q4' in model_lower or 'q5' in model_lower:
            return "Optimizado para velocidad sin perder calidad"
        elif 'instruct' in model_lower or 'chat' in model_lower:
            return "Bueno para seguir instrucciones de traducción"
        else:
            return "Modelo general"

    def _detect_incomplete_translations(self, translations: Dict[str, str]) -> List[Tuple[str, str]]:
        """
        Detecta traducciones incompletas que contienen texto en inglés residual
        
        Returns:
            Lista de tuplas (id, traducción_incompleta) que necesitan ser reprocesadas
        """
        incomplete = []
        
        # Lista de términos técnicos válidos que pueden aparecer en inglés en contextos DCS
        technical_exceptions = {
            'dcs', 'f-16', 'f-18', 'f-14', 'f-5', 'a-10', 'av-8b', 'red flag', 'red flags', 
            'bvr', 'bfm', 'acm', 'cas', 'sead', 'dead', 'cap', 'bas', 'awacs', 'gci', 
            'ils', 'tacan', 'vor', 'gps', 'ins', 'hud', 'mfd', 'rwr', 'iff', 'datalink',
            'aim-9', 'aim-120', 'aim-7', 'agm-65', 'agm-88', 'agm-84', 'jdam', 'jsow',
            'mavericks', 'sidewinder', 'amraam', 'sparrow', 'harpoon', 'harm', 'slam-er'
        }
        
        # Patrones críticos que indican traducción incompleta (más específicos)
        critical_english_patterns = [
            # Frases completas en inglés comunes
            r'\bthe\s+(?:aircraft|pilot|mission|target|enemy|system|weapon|radar|flight|squadron|base|campaign|training|exercise)\b',
            r'\b(?:you|we|they|it)\s+(?:know|think|are|have|will|can|should|must|need|want)\b',
            r'\b(?:it\'s|that\'s|there\'s|here\'s|what\'s|who\'s|where\'s|when\'s|how\'s)\b',
            r'\b(?:don\'t|doesn\'t|won\'t|can\'t|shouldn\'t|wouldn\'t|couldn\'t|haven\'t|hasn\'t|hadn\'t|aren\'t|isn\'t|wasn\'t|weren\'t)\b',
            r'\b(?:then|now|here|there|when|where|how|why|what|which|who)\s+you\b',
            r'\bworth\s+it\b|\bdefinitely\s+worth\b|\bknow\s+it\'s\b|\byou\s+know\s+it\b',
        ]
        
        # Patrones de mezcla inglés-español (más precisos)
        mixed_language_indicators = [
            # Inglés al principio seguido de español
            r'^[A-Z][a-z]+(?:\s+[a-z]+){1,4}\.\s*[A-Z][a-z]*\s+(?:aprenden|vuelan|entrenan|practican|realizan|ejecutan|desarrollan)',
            # Frases específicas del ejemplo problemático
            r'Then\s+you\s+know\s+it\'s\s+definitely\s+worth\s+it',
            r'you\s+know\s+it\'s\s+(?:definitely\s+)?worth',
            r'\b(?:Then|Now|When|If|But|And|So)\s+you\s+(?:know|think|see|get|find|realize)',
            # Patrones más generales de mezcla
            r'\b(?:the|and|or|but|so|then|now|when|if|where|how|why|what)\s+[a-z]+.*\b(?:que|es|la|el|en|de|un|una|con|por|para|del|al|los|las|se|te|me|le|nos|os|les)\b',
        ]
        
        for trans_id, translation in translations.items():
            # Solo verificar si hay contenido para verificar
            if not translation or len(translation.strip()) < 10:
                continue
            
            # Crear versión sin términos técnicos válidos para el análisis
            analysis_text = translation.lower()
            for term in technical_exceptions:
                analysis_text = re.sub(r'\b' + re.escape(term) + r'\b', '', analysis_text, flags=re.IGNORECASE)
            
            # Detectar patrones críticos de inglés
            has_critical_english = False
            critical_matches = 0
            for pattern in critical_english_patterns:
                if re.search(pattern, analysis_text, re.IGNORECASE):
                    has_critical_english = True
                    critical_matches += len(re.findall(pattern, analysis_text, re.IGNORECASE))
            
            # Detectar mezclas claras de idiomas
            has_mixed_languages = False
            for pattern in mixed_language_indicators:
                if re.search(pattern, translation, re.IGNORECASE):
                    has_mixed_languages = True
                    break
            
            # Contar palabras en inglés comunes (más selectivo)
            common_english_words = r'\b(?:the|and|or|but|so|then|you|we|they|it|is|are|was|were|have|has|had|will|would|could|should|can|know|think|see|get|make|take|come|go|say|tell|give|want|need|like|work|use|find|feel|become|seem|look|turn|start|call|try|ask|keep|put|come|move|live|bring|happen|write|show|hear|play|run|move|help|talk|might|must|also|still|just|even|only|very|most|more|some|all|any|each|both|few|many|much|other|such|same|different|new|old|good|great|small|large|big|little|long|short|right|wrong|true|false|real|sure|able|ready|open|close|full|empty|easy|hard|early|late|high|low|hot|cold|fast|slow|strong|weak|safe|free|clear|dark|light|heavy|simple|special|important|possible|available|general|public|common|main|best|better|worse|last|next|first|second|third|local|social|national|political|economic|legal|medical|technical|physical|mental|personal|private|professional|commercial|industrial|natural|human|american|european)\b'
            
            english_word_matches = len(re.findall(common_english_words, analysis_text, re.IGNORECASE))
            
            # Criterios de detección más específicos
            is_incomplete = (
                has_mixed_languages or  # Mezcla clara de idiomas
                (has_critical_english and critical_matches >= 2) or  # Múltiples patrones críticos
                (english_word_matches >= 5 and has_critical_english)  # Muchas palabras inglesas + patrones críticos
            )
            
            if is_incomplete:
                self.logger.warning(f"Traducción incompleta detectada en {trans_id}: crítico={has_critical_english}({critical_matches}), mezcla={has_mixed_languages}, palabras_en={english_word_matches}")
                incomplete.append((trans_id, translation))
        
        return incomplete

    def _create_incomplete_translation_instructions(self, original_instructions: str) -> str:
        """Crea instrucciones específicas para corregir traducciones incompletas"""
        incomplete_prefix = """CORRECCIÓN DE TRADUCCIÓN INCOMPLETA - MUY IMPORTANTE:

Los textos que vas a recibir contienen traducciones INCOMPLETAS que mezclan inglés y español.
Tu trabajo es traducir COMPLETAMENTE al español TODO el texto en inglés que encuentres.

REGLAS CRÍTICAS:
- Traduce CADA palabra en inglés al español
- NO dejes NINGUNA palabra o frase en inglés
- Mantén el significado completo del texto original
- Conserva la estructura y formato (saltos de línea \\, etc.)
- NO agregues ni quites información, solo traduce

EJEMPLO:
Incompleto: "Then you know it's definitely worth it. Los pilotos aprenden más..."
Correcto: "Entonces sabes que definitivamente vale la pena. Los pilotos aprenden más..."

"""
        
        incomplete_suffix = """

CRÍTICO: Revisa que NO quede NINGUNA palabra en inglés en tu respuesta JSON.
TODO debe estar en español. Sin excepciones."""
        
        return incomplete_prefix + original_instructions + incomplete_suffix

    def _create_strict_retry_instructions(self, original_instructions: str) -> str:
        """Crea instrucciones más estrictas para reintento cuando el modelo no genera JSON"""
        strict_prefix = """FORMATO CRÍTICO: Debes responder ÚNICAMENTE con un array JSON válido. Nada más.
        
PROHIBIDO:
- Texto conversacional como "No hay texto para traducir"
- Preguntas como "¿Puedo ayudarte?"
- Explicaciones o comentarios
- Cualquier cosa que no sea el array JSON

FORMATO REQUERIDO: [{"id": "...", "es": "..."}]

"""
        
        strict_suffix = """

RECORDATORIO FINAL: Solo el array JSON. Sin texto adicional. Sin conversación. Sin excusas."""
        
        return strict_prefix + original_instructions + strict_suffix

    def call_lmstudio_batch(self, items: List[Tuple[str, str]], cfg: Dict, timeout: int, 
                           lm_url: str, lm_model: str, compat: str = "auto") -> Dict[str, str]:
        """
        Llama a LM Studio para traducir un lote de elementos con reintento automático y validación
        
        Args:
            items: Lista de tuplas (id, texto_en)
            cfg: Configuración con LM_API y LM_INSTRUCTIONS
            timeout: Timeout para requests
            lm_url: URL base de LM Studio
            lm_model: Nombre del modelo
            compat: Modo de compatibilidad ("auto", "chat", "completions")
        
        Returns:
            Dict mapeando ids a traducciones
        """
        # Verificar cancelación antes de procesar el lote
        if self._check_cancellation():
            self.logger.warning("🛑 Cancelación detectada - Abortando procesamiento de lote")
            raise Exception("Operación cancelada por el usuario - Lote cancelado")
        
        # Primer intento con configuración normal
        result = self._call_lmstudio_single_attempt(items, cfg, timeout, lm_url, lm_model, compat)
        
        # VALIDACIÓN DE TRADUCCIONES INCOMPLETAS
        if result:
            incomplete_translations = self._detect_incomplete_translations(result)
            
            if incomplete_translations:
                self.logger.warning(f"Detectadas {len(incomplete_translations)} traducciones incompletas. Re-procesando...")
                
                # Crear items para re-procesar solo las traducciones incompletas
                items_to_retry = []
                original_items_dict = dict(items)
                
                for trans_id, incomplete_text in incomplete_translations:
                    if trans_id in original_items_dict:
                        items_to_retry.append((trans_id, original_items_dict[trans_id]))
                        self.logger.info(f"Re-procesando {trans_id}: '{incomplete_text[:60]}...'")
                
                if items_to_retry:
                    # Crear prompt más específico para traducciones incompletas
                    retry_cfg = cfg.copy()
                    incomplete_instructions = self._create_incomplete_translation_instructions(cfg.get("LM_INSTRUCTIONS", ""))
                    retry_cfg["LM_INSTRUCTIONS"] = incomplete_instructions
                    
                    try:
                        retry_result = self._call_lmstudio_single_attempt(items_to_retry, retry_cfg, timeout, lm_url, lm_model, compat)
                        
                        # Reemplazar las traducciones incompletas con las nuevas
                        if retry_result:
                            for trans_id, new_translation in retry_result.items():
                                result[trans_id] = new_translation
                            self.logger.info(f"Re-procesamiento exitoso: {len(retry_result)} traducciones corregidas")
                        else:
                            self.logger.warning("Re-procesamiento falló, manteniendo traducciones originales")
                    except Exception as e:
                        self.logger.error(f"Error en re-procesamiento de incompletas: {e}")
        
        # REINTENTO AUTOMÁTICO: Si no obtuvimos resultados y hay múltiples items, intentar con prompt más estricto
        if len(result) == 0 and len(items) > 1 and len(items) <= 3:  # Solo para lotes pequeños
            self.logger.info("Reintentando con instrucciones más estrictas...")
            
            # Crear configuración con instrucciones más estrictas
            retry_cfg = cfg.copy()
            retry_cfg["LM_INSTRUCTIONS"] = self._create_strict_retry_instructions(cfg.get("LM_INSTRUCTIONS", ""))
            
            # Llamada recursiva con prompt más estricto (solo una vez)
            try:
                retry_result = self._call_lmstudio_single_attempt(items, retry_cfg, timeout, lm_url, lm_model, compat)
                if retry_result:
                    self.logger.info(f"Reintento exitoso: {len(retry_result)} traducciones recuperadas")
                    return retry_result
                else:
                    self.logger.warning("Reintento también falló. Devolviendo resultado original.")
            except Exception as e:
                self.logger.error(f"Error en reintento: {e}")
        
        return result

    def _call_lmstudio_single_attempt(self, items: List[Tuple[str, str]], cfg: Dict, timeout: int, 
                                     lm_url: str, lm_model: str, compat: str = "auto") -> Dict[str, str]:
        """
        Intento único a LM Studio sin reintento automático
        
        Args:
            items: Lista de tuplas (id, texto_en)
            cfg: Configuración con LM_API y LM_INSTRUCTIONS
            timeout: Timeout para requests
            lm_url: URL base de LM Studio
            lm_model: Nombre del modelo
            compat: Modo de compatibilidad ("auto", "chat", "completions")
        
        Returns:
            Dict mapeando ids a traducciones
        """
        # Verificar cancelación antes de procesar
        if self._check_cancellation():
            self.logger.warning("🛑 Cancelación detectada - Abortando intento de llamada")
            raise Exception("Operación cancelada por el usuario - Intento cancelado")
        
        lm_instructions = cfg.get("LM_INSTRUCTIONS", "")
        
        # NUEVO: Usar campo SYSTEM si está disponible, sino usar LM_INSTRUCTIONS
        system_message = cfg.get("SYSTEM", "").strip()
        if system_message:
            # Si hay campo SYSTEM, usar ese para el rol system
            actual_system_content = system_message
            # LM_INSTRUCTIONS va en el rol user junto con el contenido
            actual_user_content = lm_instructions + "\n\n" if lm_instructions else ""
            print(f"🔧 Usando campo SYSTEM separado para role='system'")
        else:
            # Fallback al comportamiento anterior
            actual_system_content = lm_instructions
            actual_user_content = ""
            print(f"🔧 Usando LM_INSTRUCTIONS para role='system' (sin campo SYSTEM)")
        
        user_payload = [{"id": k, "en": v} for k, v in items]
        json_content = json.dumps(user_payload, ensure_ascii=False)

        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("LMSTUDIO_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        api = (cfg.get("LM_API") or {})
        # Stop sequences específicas para modelos Llama
        default_stop = ["</s>", "<|eot_id|>", "]}", "]}\n", "]},\n]", "\n```", "```json"]
        supports_system = bool(api.get("supports_system", True))

        def post_chat() -> str:
            url_chat = f"{lm_url.rstrip('/')}/chat/completions"
            if supports_system:
                messages = [
                    {"role": "system", "content": actual_system_content},
                    {"role": "user", "content": actual_user_content + json_content}
                ]
            else:
                messages = [
                    {"role": "user", "content": actual_system_content + "\n\n" + actual_user_content + json_content}
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
            # Parámetros específicos para modelos Llama
            if "repetition_penalty" in api:
                body["repetition_penalty"] = api["repetition_penalty"]
            if "presence_penalty" in api:
                body["presence_penalty"] = api["presence_penalty"]
            if "frequency_penalty" in api:
                body["frequency_penalty"] = api["frequency_penalty"]
            
            # Verificar cancelación ANTES del request HTTP
            if self._check_cancellation():
                self.logger.warning("🛑 Cancelación detectada - Abortando llamada HTTP al modelo")
                raise Exception("Operación cancelada por el usuario - Request HTTP cancelado")
            
            r = self.http_session.post(url_chat, json=body, headers=headers, timeout=timeout)
            if r.status_code >= 400:
                self.logger.error("LM Studio /chat/completions %s: %s", r.status_code, r.text[:1000])
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
            prompt = build_prompt_for_model(lm_model, actual_system_content, actual_user_content + json_content)
            body = {
                "model": lm_model,
                "prompt": prompt,
                "temperature": api.get("temperature", 0.2),
                "top_p": api.get("top_p", 0.9),
                "top_k": api.get("top_k", 40),
                "max_tokens": api.get("max_tokens", 2048),
                "stop": api.get("stop", default_stop)
            }
            # Parámetros específicos para modelos Llama
            if "repetition_penalty" in api:
                body["repetition_penalty"] = api["repetition_penalty"]
            if "presence_penalty" in api:
                body["presence_penalty"] = api["presence_penalty"]
            if "frequency_penalty" in api:
                body["frequency_penalty"] = api["frequency_penalty"]
            
            # Verificar cancelación ANTES del request HTTP
            if self._check_cancellation():
                self.logger.warning("🛑 Cancelación detectada - Abortando llamada HTTP al modelo")
                raise Exception("Operación cancelada por el usuario - Request HTTP cancelado")
            
            r = self.http_session.post(url_comp, json=body, headers=headers, timeout=timeout)
            if r.status_code >= 400:
                self.logger.error("LM Studio /completions %s: %s", r.status_code, r.text[:1000])
                r.raise_for_status()
            
            # Extraer solo la parte JSON válida para modelos Llama
            full_text = r.json()["choices"][0].get("text", "")
            
            # Buscar JSON array al inicio de la respuesta
            import re
            json_match = re.search(r'(\[[\s\S]*?\])', full_text)
            if json_match:
                json_part = json_match.group(1)
                try:
                    # Validar que sea JSON válido
                    import json
                    json.loads(json_part)
                    self.logger.debug(f"Extraído JSON válido de completions: {json_part[:100]}...")
                    return json_part
                except json.JSONDecodeError:
                    self.logger.warning(f"JSON encontrado pero inválido: {json_part[:100]}...")
            
            # Si no encuentra JSON válido, devolver texto completo (fallback)
            self.logger.debug(f"No se encontró JSON válido, devolviendo texto completo: {full_text[:100]}...")
            return full_text

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
            self.logger.warning("LM Studio timed out after %d seconds.", timeout)
        except requests.HTTPError as e:
            # Detectar específicamente si no hay modelos cargados
            if e.response is not None and e.response.status_code == 404:
                try:
                    error_data = e.response.json()
                    if (error_data.get("error", {}).get("code") == "model_not_found" or 
                        "No models loade        self._prevent_problematic_directories()d" in error_data.get("error", {}).get("message", "")):
                        
                        error_msg = (
                            "❌ ERROR: No hay modelos cargados en LM Studio.\n\n"
                            "Para solucionar este problema:\n"
                            "1. Abre LM Studio\n"
                            "2. Ve a la página 'My Models'\n" 
                            "3. Carga un modelo haciendo clic en 'Load Model'\n"
                            "4. O usa el comando: lms load <nombre-del-modelo>\n\n"
                            "Una vez que tengas un modelo cargado, intenta la traducción nuevamente."
                        )
                        self.logger.error(error_msg)
                        raise RuntimeError("No hay modelos cargados en LM Studio. Por favor, carga un modelo primero.") from e
                except (json.JSONDecodeError, ValueError):
                    pass
            
            self.logger.exception("ERROR LM Studio: %s", e)
        except Exception as e:
            self.logger.exception("ERROR LM Studio: %s", e)

        if not content:
            return {}

        dt = time.perf_counter() - t0
        self.logger.info("Lote LM Studio: %d frases | %.2fs", len(items), dt)

        # Parse response - Mejorado para modelos Llama
        # Primero extraer JSON de bloques de código si los hay
        m_fence = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if m_fence:
            clean_content = m_fence.group(1).strip()
        else:
            # Buscar JSON inline
            m_json = re.search(r'(\[[\s\S]*?\]|\{[\s\S]*?\})', content)
            clean_content = m_json.group(1) if m_json else content.strip()
        
        # Limpiar caracteres problemáticos
        clean_content = clean_content.replace('\u00a0', ' ').strip()
        
        # Limpiar caracteres de control y finales problemáticos para Llama
        clean_content = re.sub(r'^\s*```json\s*', '', clean_content, flags=re.IGNORECASE)
        clean_content = re.sub(r'\s*```\s*$', '', clean_content)
        clean_content = re.sub(r'<\|eot_id\|>.*$', '', clean_content, flags=re.DOTALL)
        clean_content = re.sub(r'</s>.*$', '', clean_content, flags=re.DOTALL)
        
        # Filtrar contenido del sistema que algunos modelos incluyen incorrectamente
        clean_content = self._filter_system_content(clean_content)
        
        # Extracción agresiva de JSON puro
        clean_content = self._extract_pure_json(clean_content)

        out = {}
        try:
            parsed = json.loads(clean_content)
            self.logger.debug(f"JSON parseado correctamente: {type(parsed)}")
            
            # Manejar diferentes formatos de respuesta
            if isinstance(parsed, dict) and "data" in parsed and isinstance(parsed["data"], list):
                items_out = parsed["data"]
            elif isinstance(parsed, list):
                items_out = parsed
            elif isinstance(parsed, dict) and ("id" in parsed or "text" in parsed):
                items_out = [parsed]
            else:
                self.logger.error("Formato JSON inesperado. Respuesta: %s", str(parsed)[:500])
                return {}
                
            # Procesar items extraídos
            for obj in items_out:
                if not isinstance(obj, dict):
                    continue
                    
                _id = obj.get("id")
                _es = obj.get("es")
                _text = obj.get("text")
                
                if _id and isinstance(_es, str) and _es.strip():
                    out[_id] = _es.strip()
                elif _id and isinstance(_text, str) and _text.strip():
                    out[_id] = _text.strip()
                elif _text and len(items) == 1:
                    # Fallback para respuestas sin ID
                    out[items[0][0]] = _text.strip()
                    
            self.logger.info(f"Procesadas {len(out)} traducciones de {len(items_out)} respuestas")
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"No es JSON válido: {e}. Intentando parsing de texto plano...")
            
            # SOLUCIÓN ROBUSTA: Manejar respuestas en texto plano
            # Caso 1: Intentar extraer array JSON embebido
            m_array = re.search(r'\[(.*?)\]', clean_content, re.DOTALL)
            if m_array:
                try:
                    parsed = json.loads(f'[{m_array.group(1)}]')
                    if isinstance(parsed, list):
                        for obj in parsed:
                            if isinstance(obj, dict) and obj.get("id") and obj.get("es"):
                                out[obj["id"]] = obj["es"].strip()
                        self.logger.info(f"Recuperación JSON exitosa: {len(out)} traducciones")
                        return out
                except Exception:
                    pass
            
            # Caso 2: El modelo respondió en texto plano - aplicar estrategia inteligente
            self.logger.info("Modelo generó texto plano. Aplicando estrategia de recuperación...")
            
            # Si solo hay 1 item, asignar toda la respuesta
            if len(items) == 1:
                item_id, original_text = items[0]
                # Limpiar la respuesta de texto plano
                clean_response = content.strip()
                
                # Filtrar contenido del sistema primero
                clean_response = self._filter_system_content(clean_response)
                
                # Remover frases comunes que no son traducción
                noise_patterns = [
                    r"No hay texto para traducir\..*",
                    r"¿Puedo ayudarte con algo más\?.*",
                    r"¿Quieres saber sobre.*?\?.*",
                    r"^No tengo\.",
                    r"Nuestra tarea es.*"
                ]
                
                for pattern in noise_patterns:
                    clean_response = re.sub(pattern, "", clean_response, flags=re.IGNORECASE | re.DOTALL)
                
                clean_response = clean_response.strip()
                
                # Si queda contenido útil después de limpiar
                if clean_response and len(clean_response) > 10:
                    out[item_id] = clean_response
                    self.logger.info(f"Recuperación de texto plano: 1 traducción asignada")
                else:
                    # Intentar re-procesar con prompt más estricto
                    self.logger.warning(f"Respuesta no útil. Texto original: '{original_text}', Respuesta: '{content[:200]}'")
                    
            # Si hay múltiples items, intentar estrategia de mapeo
            elif len(items) > 1:
                self.logger.warning(f"Respuesta texto plano para {len(items)} items. Requiere reintento con formato JSON más estricto.")
                # En este caso, es mejor fallar y que se reintente con mejor prompt
                
        except Exception as e:
            self.logger.error(f"Error inesperado parseando respuesta: {e}. Contenido: {clean_content[:500]}")
        
        return out

    def translate_lua_file(self, lua_path: str, campaign_name: str, output_dir: str, 
                          cfg: Dict, batch_size: int = 8, timeout: int = 120,
                          keys_filter: Optional[List[str]] = None,
                          lm_url: str = None,
                          lm_model: str = "gpt-neo", compat: str = "auto", 
                          use_cache: bool = True, overwrite_cache: bool = False,
                          skip_lm_validation: bool = False,
                          progress_callback: Callable[[Dict], None] = None) -> Dict[str, Any]:
        """
        Traduce un archivo .lua siguiendo el flujo completo del motor de traducción DCS:
        
        1. Crear carpeta de la campaña en app/data/traducciones
        2. Descomprimir misiones (.miz) en la ruta, una carpeta por misión  
        3. Detectar frases que se tienen que traducir (TARGET_PREFIXES)
        4. Crear fichero temporal con placeholders
        5. Mandar frases al modelo por lotes (batches)
        6. Sustituir placeholders y crear fichero .traducido.lua
        
        Args:
            lua_path: Ruta al archivo .lua a traducir
            campaign_name: Nombre de la campaña
            output_dir: Directorio de salida (app/data/traducciones/campaign_name)
            cfg: Configuración con LM_INSTRUCTIONS, TARGET_PREFIXES, etc.
            batch_size: Tamaño de lote para llamadas al modelo
            timeout: Timeout para requests HTTP
            keys_filter: Filtro opcional de claves
            lm_url: URL de LM Studio
            lm_model: Modelo a usar
            compat: Compatibilidad ("auto", "chat", "completions")
            
        Returns:
            Dict con resultado de la traducción
        """
        self.logger.info(f"🚀🚀🚀 EJECUTANDO TRANSLATE_LUA_FILE 🚀🚀🚀")
        self.logger.info(f"=== INICIANDO TRADUCCIÓN DE {lua_path} ===")
        self.logger.info(f"🔧 Parámetro use_cache: {use_cache}")
        self.logger.info(f"🔧 Parámetro overwrite_cache: {overwrite_cache}")
        
        # Obtener URL de LM Studio desde configuración del usuario si no se proporcionó
        if lm_url is None:
            from app.services.user_config import UserConfigService
            lm_url = UserConfigService.get_lm_studio_url()
            self.logger.info(f"🔧 URL LM Studio obtenida desde configuración: {lm_url}")
        
        # Explicar qué comportamiento se aplicará
        if use_cache:
            self.logger.info("📖 MODO: Usar cache + actualizar cache (comportamiento normal)")
        elif overwrite_cache:
            self.logger.info("🆕 MODO: NO usar cache + SÍ actualizar cache (traducciones frescas + guardar mejoras)")
        else:
            self.logger.info("🚫 MODO: NO usar cache + NO actualizar cache (máximo aislamiento)")
        
        # Solo asegurar que existe el directorio de salida (ya debe estar configurado correctamente)
        ensure_directory(output_dir)
        
        # Verificar estado de LM Studio antes de proceder (solo si no se omite la validación)
        if not skip_lm_validation:
            self.logger.info("Verificando estado de LM Studio...")
            lm_status = self.check_lm_studio_status(lm_url, lm_model)
            
            if not lm_status['available']:
                error_msg = f"❌ LM Studio no disponible: {lm_status['error_message']}"
                self.logger.error(error_msg)
                self.logger.info(f"💡 Sugerencia: {lm_status['suggestion']}")
                raise RuntimeError(f"LM Studio no disponible: {lm_status['error_message']}")
                
            if not lm_status['models_loaded']:
                self.logger.warning(f"⚠️ {lm_status['error_message']}")
                
                # Intentar cargar el modelo automáticamente
                self.logger.info(f"🔄 Intentando cargar modelo automáticamente: {lm_model}")
                load_success = self.lm_studio_service.load_model_via_cli(lm_model)
                
                if load_success:
                    self.logger.info(f"✅ Modelo '{lm_model}' cargado exitosamente")
                    # Verificar nuevamente después de la carga
                    self.logger.info("Verificando estado después de cargar modelo...")
                    lm_status_retry = self.check_lm_studio_status(lm_url, lm_model)
                    
                    if not lm_status_retry['models_loaded']:
                        error_msg = f"❌ Modelo cargado pero no disponible: {lm_status_retry['error_message']}"
                        self.logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    else:
                        self.logger.info("✅ Modelo cargado y verificado correctamente")
                else:
                    error_msg = f"❌ No se pudo cargar el modelo: {lm_model}"
                    self.logger.error(error_msg)
                    self.logger.info(f"💡 Sugerencia: Carga el modelo manualmente desde LM Studio")
                    raise RuntimeError(f"No hay modelos cargados y no se pudo cargar automáticamente: {lm_model}")
            else:
                self.logger.info("✅ LM Studio disponible y con modelos cargados")
        
        # Leer archivo .lua
        with open(lua_path, "r", encoding="utf-8", newline="") as f:
            lua_text = f.read()

        # Normalizar comillas
        lua_text = lua_text.replace("'", "'")

        # Reemplazos fijos previos
        fixed_replacements = cfg.get("FIXED_FULL_REPLACEMENTS", {})
        if isinstance(fixed_replacements, dict):
            for en_phrase, es_phrase in fixed_replacements.items():
                if not isinstance(en_phrase, str) or not isinstance(es_phrase, str):
                    self.logger.warning("FIXED_FULL_REPLACEMENTS mal formado: %r -> %r (ignorado)", en_phrase, es_phrase)
                    continue
                self.logger.info(f"Aplicando reemplazo fijo: '{en_phrase}' -> '{es_phrase}'")
                lua_text = lua_text.replace(en_phrase, es_phrase)

        # Pre-reglas
        lua_text = apply_glossary_rules(lua_text, cfg)
        lua_text = apply_phraseology_rules(lua_text, cfg)
        lua_text = apply_smart_splash_rules(lua_text, cfg)

        total_entries_in = len(list(self.entry_regex.finditer(lua_text)))
        self.logger.info(f"Entradas detectadas en origen: {total_entries_in}")

        # 3. Detectar frases TARGET_PREFIXES y crear segmentos
        segments: List[Segment] = []
        
        # PROTECT_BRACKETS desde configuración
        protect_brackets_flag = bool(cfg.get("PROTECT_BRACKETS", True))
        self.logger.info(f"PROTECT_BRACKETS = {protect_brackets_flag}")

        def replace_entry(m: re.Match) -> str:
            """Reemplaza entradas lua con placeholders para traducción"""
            pre, key, value, post = m.group("pre"), m.group("key"), m.group("value"), m.group("post")
            if not key_is_target(key, keys_filter, cfg):
                return m.group(0)
            start_idx = len(segments)
            segs = []
            for i, sm in enumerate(self.line_split_regex.finditer(value)):
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

        # 4. Crear fichero temporal con placeholders
        self.logger.info("Insertando marcadores id_hash en .lua temporal...")
        lua_with_placeholders = self.entry_regex.sub(replace_entry, lua_text)

        # Guardar archivo temporal con placeholders
        tmp_lua_path = os.path.join(output_dir, os.path.basename(lua_path).rsplit(".",1)[0] + ".placeholders.lua")
        with open(tmp_lua_path, "w", encoding="utf-8", newline="") as f:
            f.write(lua_with_placeholders)
        self.logger.info(f"Guardado .lua temporal con marcadores: {tmp_lua_path}")

        # Preparar mapeos para traducción
        id_to_seg: Dict[str, Segment] = {seg.id: seg for seg in segments}
        unique_en_to_idlist: Dict[str, List[str]] = {}
        for seg in segments:
            # Verificar cancelación durante preparación de segmentos
            if self._check_cancellation():
                self.logger.warning("🛑 Cancelación detectada - Deteniendo preparación de segmentos")
                raise Exception("Operación cancelada por el usuario - Preparación de segmentos interrumpida")
                
            if seg.clean_for_model.strip() == "": continue
            unique_en_to_idlist.setdefault(seg.clean_for_model, []).append(seg.id)

        # Inicializar contadores de estadísticas
        cache_hits_count = 0
        api_calls_count = 0
        processing_start_time = time.perf_counter()
        
        # Cargar caché de traducciones (centralizado)
        cache_path = os.path.join(output_dir, "translation_cache.json")  # Para mantener cache local como intermedio
        
        # Cargar cache centralizado según configuración
        cache = self.centralized_cache.load_cache(use_cache=use_cache)
        
        if not use_cache:
            self.logger.info("🚫 CACHE DESHABILITADO - Se traducirán todas las frases desde cero")
        else:
            self.logger.info(f"✅ Cache habilitado - Cache cargado con {len(cache)} entradas")
        
        # Si existe cache local, fusionarlo con el centralizado (solo si use_cache=True)
        if use_cache and os.path.exists(cache_path):
            try:
                local_cache = json.load(open(cache_path, "r", encoding="utf-8"))
                # Merge local cache into centralized (solo para esta sesión)
                for en, es in local_cache.items():
                    if en not in cache:
                        cache[en] = es
                self.logger.info(f"Cache local fusionado temporalmente: {len(local_cache)} entradas")
            except Exception as e:
                self.logger.warning(f"Error leyendo cache local: {e}")

        # Aplicar caché existente (solo si use_cache=True)
        self.logger.info(f"🔍 APLICANDO CACHE: use_cache={use_cache}, cache_size={len(cache)}, unique_texts={len(unique_en_to_idlist)}")
        if use_cache:
            self.logger.info("✅ Entrando en bloque de aplicación de cache")
            for clean_en, idlist in list(unique_en_to_idlist.items()):
                if clean_en in cache:
                    es = cache[clean_en]
                    cache_hits_count += 1
                    self.logger.info(f"✅ CACHE HIT #{cache_hits_count}: '{clean_en}' -> '{es}' | Cache size: {len(cache)}")
                    for _id in idlist: id_to_seg[_id].es = es
                    unique_en_to_idlist.pop(clean_en, None)
        else:
            self.logger.info("🚫 ENTRANDO EN BLOQUE: Cache deshabilitado - no se aplicarán traducciones del cache")
            # IMPORTANTE: Verificar que el cache esté realmente vacío
            if len(cache) > 0:
                self.logger.error(f"❌ BUG DETECTADO: Cache deshabilitado pero contiene {len(cache)} entradas!")
                self.logger.error(f"   Primeras 5 entradas del cache: {list(cache.items())[:5]}")
            else:
                self.logger.info("✅ Confirmado: Cache vacío como se esperaba")

        # Preparar elementos para traducir
        to_query: List[Tuple[str, str]] = []
        for clean_en, idlist in unique_en_to_idlist.items():
            to_query.append((idlist[0], clean_en))

        # Términos protegidos
        protected_terms_set = set(
            (cfg.get("PROTECT_WORDS") or [])
            + (cfg.get("NO_TRANSLATE_TERMS") or [])
            + (cfg.get("TECHNICAL_TERMS_NO_TRASLATE") or [])
        )

        # 5. Mandar frases al modelo por lotes (PRIMER PASE)
        total_batches = len(range(0, len(to_query), batch_size))
        self.logger.info(f"Enviando {len(to_query)} frases únicas al modelo en {total_batches} lotes de {batch_size}")
        
        for i in range(0, len(to_query), batch_size):
            # Verificar cancelación antes de cada batch
            if self._check_cancellation():
                self.logger.warning("🛑 Cancelación detectada - Deteniendo envío de frases al modelo")
                raise Exception("Operación cancelada por el usuario - Envío de frases interrumpido")
            
            batch_number = (i // batch_size) + 1
            batch = to_query[i:i+batch_size]
            
            # Reportar progreso antes del lote
            if progress_callback:
                progress_data = {
                    'total_batches': total_batches,
                    'processed_batches': batch_number - 1,
                    'current_batch': batch_number,
                    'batch_progress': int(((batch_number - 1) / total_batches) * 100),
                    'cache_hits': cache_hits_count,
                    'model_calls': api_calls_count,
                    'phase': f'Procesando lote {batch_number}/{total_batches}'
                }
                progress_callback(progress_data)
            
            resp = self.call_lmstudio_batch(batch, cfg, timeout, lm_url, lm_model, compat=compat)
            api_calls_count += 1  # Contar llamada al API

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
                    if use_cache:  # Solo actualizar cache si está habilitado
                        cache[b_en] = translated_es
                    else:
                        self.logger.debug(f"Cache deshabilitado - no se guarda traducción: '{b_en}' -> '{translated_es}'")

                for _id in unique_en_to_idlist.get(b_en, []):
                    id_to_seg[_id].es = translated_es
            
            # Reportar progreso después del lote procesado
            if progress_callback:
                progress_data = {
                    'total_batches': total_batches,
                    'processed_batches': batch_number,
                    'current_batch': batch_number,
                    'batch_progress': int((batch_number / total_batches) * 100),
                    'cache_hits': cache_hits_count,
                    'model_calls': api_calls_count,
                    'phase': f'Completado lote {batch_number}/{total_batches}'
                }
                progress_callback(progress_data)

        # REINTENTO EN PARES para elementos no traducidos
        retry_items = [(seg.id, seg.clean_for_model) for seg in segments if seg.es is None and seg.clean_for_model.strip()]
        if retry_items:
            self.logger.info(f"Reintentando {len(retry_items)} entradas con lotes pequeños...")
            for j in range(0, len(retry_items), 2):
                # Verificar cancelación antes de cada reintento
                if self._check_cancellation():
                    self.logger.warning("🛑 Cancelación detectada - Deteniendo reintentos de traducción")
                    raise Exception("Operación cancelada por el usuario - Reintentos interrumpidos")
                
                batch = retry_items[j:j+2]
                resp = self.call_lmstudio_batch(batch, cfg, timeout, lm_url, lm_model, compat=compat)
                api_calls_count += 1  # Contar llamada al API de reintento
                for b_id, b_en in batch:
                    es2 = resp.get(b_id)
                    if isinstance(es2, str) and es2.strip():
                        translated_es = protect_terms(es2, protected_terms_set)
                        seg = id_to_seg[b_id]
                        if seg.br_tokens:
                            translated_es = unprotect_tokens(translated_es, seg.br_tokens)
                        translated_es = re.sub(r'\s+', ' ', translated_es).strip()
                        id_to_seg[b_id].es = translated_es
                        if use_cache:  # Solo actualizar cache si está habilitado
                            cache[b_en] = translated_es
                        else:
                            self.logger.debug(f"Cache deshabilitado en reintento - no se guarda: '{b_en}' -> '{translated_es}'")

        # FALLBACK: usar texto original limpio para elementos no traducidos
        for seg in segments:
            if seg.es is None and seg.clean_for_model.strip() != "":
                es_fallback = unprotect_tokens(seg.core, seg.br_tokens)
                es_fallback = re.sub(r'\s+', ' ', es_fallback).strip()
                seg.es = es_fallback
                self.logger.warning(f"Translation failed for {seg.id}, using fallback: {seg.es}")

        # Guardar caché actualizado
        # 1. Guardar cache local (solo si use_cache=True)
        if use_cache:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"Cache local guardado: {cache_path}")
            except Exception as e:
                self.logger.error(f"Error guardando cache local: {e}")
        else:
            self.logger.info("Cache deshabilitado - no se guardará cache local")
        
        # 2. Actualizar cache centralizado
        # Lógica de actualización:
        # - use_cache=True: siempre actualizar (comportamiento normal)
        # - use_cache=False + overwrite_cache=True: actualizar cache con nuevas traducciones 
        # - use_cache=False + overwrite_cache=False: no actualizar cache
        should_update_cache = use_cache or (not use_cache and overwrite_cache)
        
        if should_update_cache:
            # Extraer solo las nuevas traducciones (las que no venían del cache al inicio)
            new_translations = {}
            initial_cache = self.centralized_cache.load_cache(use_cache=True)  # Siempre cargar para comparar
            for en, es in cache.items():
                if en not in initial_cache or initial_cache[en] != es:
                    new_translations[en] = es
            
            if new_translations:
                success = self.centralized_cache.update_cache(new_translations, use_cache=True)  # Siempre actualizar si decidimos hacerlo
                action = "actualizado" if use_cache else "sobrescrito"
                self.logger.info(f"🔍 Cache centralizado {action}: {len(new_translations)} nuevas traducciones, success={success}")
            else:
                self.logger.info("🔍 No hay nuevas traducciones para el cache centralizado")
        else:
            self.logger.info("🚫 Cache centralizado no actualizado (use_cache=False, overwrite_cache=False)")

        # Export JSONL de segmentos
        jsonl_path = os.path.join(output_dir, os.path.basename(lua_path).rsplit(".", 1)[0] + ".translations.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as jf:
            for seg in segments:
                if seg.clean_for_model.strip() == "": continue
                obj = {"id": seg.id, "key": seg.key, "en": seg.clean_for_model, "es": seg.es}
                jf.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.logger.info(f"JSONL generado: {jsonl_path}")

        # 6. Sustituir placeholders y crear fichero .traducido.lua
        id_to_es_lua = {seg.id: f"{seg.leading_ws}{escape_for_lua(seg.es or '')}" for seg in segments}

        def reinsert_cb(m: re.Match) -> str:
            """Reinserta traducciones en lugar de placeholders"""
            pre, key, value, post = m.group("pre"), m.group("key"), m.group("value"), m.group("post")
            new_value = value
            for pid, es in id_to_es_lua.items():
                new_value = new_value.replace(pid, es)
            return pre + new_value + post

        final_text = self.entry_regex.sub(reinsert_cb, lua_with_placeholders)

        total_entries_out = len(list(self.entry_regex.finditer(final_text)))
        self.logger.info(f"Entradas detectadas en salida: {total_entries_out} (origen {total_entries_in})")

        # Post-proceso
        final_text = apply_post_rules(final_text, cfg)

        # Guardar archivo final traducido
        out_lua_path = os.path.join(output_dir, os.path.basename(lua_path).rsplit(".", 1)[0] + ".translated.lua")
        with open(out_lua_path, "w", encoding="utf-8", newline="") as f:
            f.write(final_text)
        
        self.logger.info(f"¡Archivo traducido completado!: {out_lua_path}")
        
        # Calcular tiempo de procesamiento
        processing_time = time.perf_counter() - processing_start_time
        
        # Estadísticas
        translated_count = len([seg for seg in segments if seg.es and seg.es.strip()])
        total_segments = len([seg for seg in segments if seg.clean_for_model.strip()])
        
        # Log de estadísticas para debugging
        self.logger.info(f"📊 Estadísticas de traducción:")
        self.logger.info(f"   Use Cache: {use_cache}")
        self.logger.info(f"   Cache hits: {cache_hits_count}")
        self.logger.info(f"   API calls: {api_calls_count}")
        self.logger.info(f"   Processing time: {processing_time:.2f}s")
        self.logger.info(f"   Segments translated: {translated_count}/{total_segments}")
        
        if not use_cache:
            self.logger.info("🚫 CONFIRMACIÓN: Cache estuvo DESHABILITADO durante toda la traducción")
        
        return {
            "success": True,
            "output_file": out_lua_path,
            "placeholder_file": tmp_lua_path,
            "translations_jsonl": jsonl_path,
            "cache_file": cache_path,
            "segments_total": total_segments,
            "segments_translated": translated_count,
            "translation_rate": (translated_count / total_segments * 100) if total_segments > 0 else 0,
            "entries_in": total_entries_in,
            "entries_out": total_entries_out,
            # Agregar estadísticas de caché
            "cache_hits": cache_hits_count,
            "api_calls": api_calls_count,
            "processing_time": processing_time
        }

    def translate_file(self, config: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
        """
        Traduce un archivo .lua usando la configuración proporcionada
        
        Args:
            config: Configuración de traducción con claves:
                - file_path: Ruta al archivo .lua
                - output_dir: Directorio de salida
                - lm_config: Configuración del modelo de lenguaje
                - prompt_config: Configuración de prompts
                - batch_size: Tamaño de lote
                - timeout: Timeout por request
                - keys_filter: Filtro de claves (opcional)
        
        Returns:
            Dict con resultados de la traducción
        """
        # Validar configuración
        is_valid, errors = validate_translation_config(config)
        if not is_valid:
            raise ValueError(f"Configuración inválida: {', '.join(errors)}")
        
        # Preparar directorios
        output_dir = config.get('output_dir', os.path.join(TRANSLATIONS_DIR, datetime.now().strftime('%Y-%m-%d')))
        ensure_directory(output_dir)
        
        # Configurar logging específico para esta traducción
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(LOGS_DIR, f"translation_{session_id}.log")
        
        # Cargar configuración de prompts
        prompt_config = self._load_prompt_config(config.get('prompt_file'))
        
        try:
            # Ejecutar traducción
            result = self._process_file(
                lua_path=config['file_path'],
                output_dir=output_dir,
                batch_size=config.get('batch_size', 4),
                timeout=config.get('timeout', 200),
                keys_filter=config.get('keys_filter'),
                prompt_config=prompt_config,
                lm_config=config.get('lm_config', {}),
                session_id=session_id,
                use_cache=use_cache
            )
            
            self.logger.info(f"Traducción completada: {result['output_file']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error durante la traducción: {e}")
            raise
    
    def translate_campaign(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traduce una campaña completa (múltiples archivos .miz)
        
        Args:
            config: Configuración con campañas a traducir
            
        Returns:
            Dict con resultados de la traducción de campaña
        """
        campaigns = config.get('campaigns', [])
        if not campaigns:
            raise ValueError("No hay campañas especificadas para traducir")
        
        results = {
            'session_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'campaigns': [],
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for campaign in campaigns:
            campaign_result = self._translate_campaign_files(campaign, config)
            results['campaigns'].append(campaign_result)
            results['total_files'] += campaign_result.get('total_files', 0)
            results['successful'] += campaign_result.get('successful', 0)
            results['failed'] += campaign_result.get('failed', 0)
            results['errors'].extend(campaign_result.get('errors', []))
        
        return results
    
    def _process_mission_miz(self, miz_file: str, mission_name: str, campaign_name: str, output_dir: str, config: Dict[str, Any], use_cache: bool = True, overwrite_cache: bool = False, skip_lm_validation: bool = False) -> Dict[str, Any]:
        """
        Procesa un archivo .miz individual (extrae y traduce el diccionario)
        
        Args:
            miz_file: Ruta al archivo .miz
            mission_name: Nombre de la misión
            campaign_name: Nombre de la campaña
            output_dir: Directorio de salida
            config: Configuración de traducción
            
        Returns:
            Dict con resultado del procesamiento
        """
        import zipfile
        import tempfile
        import shutil
        
        result = {
            'mission_name': mission_name,
            'miz_file': miz_file,
            'success': False,
            'extracted_files': [],
            'translation_results': [],
            'output_files': []
        }
        
        # Crear directorio temporal para extracción usando utilidades integradas
        temp_dir = tempfile.mkdtemp(prefix=f"dcs_mission_{self.slugify(mission_name)}_")
        
        try:
            # Extraer archivo .miz usando función integrada
            self.extract_miz(miz_file, temp_dir)
            
            # FILE_TARGET: Usar método centralizado
            from app.services.user_config import UserConfigService
            file_target = config.get('file_target') or UserConfigService.get_file_target()
            self.logger.info(f"🎯 FILE_TARGET obtenido: {file_target} (desde {'config' if config.get('file_target') else 'user_config'})")
            
            # Buscar archivo de diccionario
            lua_file = os.path.join(temp_dir, file_target)
            
            if not os.path.exists(lua_file):
                # Buscar en subdirectorios si no está en la ruta exacta
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file == 'dictionary' or file.endswith('dictionary.lua'):
                            lua_file = os.path.join(root, file)
                            break
                    if os.path.exists(lua_file):
                        break
            
            if not os.path.exists(lua_file):
                raise FileNotFoundError(f"Archivo de diccionario no encontrado en {miz_file}")
            
            result['extracted_files'].append(lua_file)
            
            # Crear estructura de directorios específica para esta misión
            mission_dirs = self.ensure_mission_local_dirs(campaign_name, mission_name)
            mission_output_dir = mission_dirs["out_lua"]
            
            # Cargar configuración de prompts y modelo
            prompt_config = self._load_prompt_config(config.get('prompt_file'))
            lm_config = config.get('lm_config', {})
            
            # Combinar configuraciones CON FUSIÓN DE API
            translation_cfg = prompt_config.copy()
            if lm_config:
                translation_cfg.update(lm_config)
            
            # FUSIONAR configuración API del preset con la del prompt
            merged_api_config = self._merge_api_config(prompt_config, lm_config)
            translation_cfg['LM_API'] = merged_api_config
            
            # Configurar parámetros
            batch_size = config.get('batch_size', 8)
            timeout = config.get('timeout', 120)
            keys_filter = config.get('keys_filter')
            
            # URLs y modelo LM Studio
            from app.services.user_config import UserConfigService
            lm_url = os.environ.get("LMSTUDIO_URL", UserConfigService.get_lm_studio_url())
            lm_model = os.environ.get("LMSTUDIO_MODEL", "gpt-neo")
            compat = config.get('lm_compat', 'auto')
            
            # Ejecutar traducción usando el nuevo motor integrado
            translation_result = self.translate_lua_file(
                lua_path=lua_file,
                campaign_name=campaign_name,
                output_dir=mission_output_dir,
                cfg=translation_cfg,
                batch_size=batch_size,
                timeout=timeout,
                keys_filter=keys_filter,
                lm_url=lm_url,
                lm_model=lm_model,
                compat=compat,
                use_cache=use_cache,
                overwrite_cache=overwrite_cache,
                skip_lm_validation=skip_lm_validation
            )
            
            result['translation_results'].append(translation_result)
            result['output_files'].extend(translation_result.get('output_files', []))
            result['success'] = True
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
        finally:
            # Limpiar directorio temporal
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _process_file_like_original(self, lua_path: str, output_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un archivo .lua usando la lógica del dcs_lua_translate.py original
        
        Args:
            lua_path: Ruta al archivo .lua
            output_dir: Directorio de salida  
            config: Configuración de traducción
            
        Returns:
            Dict con resultados de la traducción
        """
        # Cargar configuración de prompts y LM
        prompt_config = self._load_prompt_config(config.get('prompt_file'))
        lm_config = config.get('lm_config', {})
        
        # Configuración por defecto inspirada en dcs_lua_translate.py
        batch_size = config.get('batch_size', 8)
        timeout = config.get('timeout', 120)
        keys_filter = config.get('keys_filter')
        
        # Llamar al método interno que implementa la lógica de dcs_lua_translate.py
        return self._process_file(
            lua_path=lua_path,
            output_dir=output_dir,
            batch_size=batch_size,
            timeout=timeout,
            keys_filter=keys_filter,
            prompt_config=prompt_config,
            lm_config=lm_config,
            session_id=datetime.now().strftime('%Y%m%d_%H%M%S')
        )
    
    def _slugify(self, text: str) -> str:
        """Convierte texto en un nombre de archivo/directorio válido (método legacy)"""
        return self.slugify(text)
    
    def process_campaign_full_workflow(self, config: Dict[str, Any], use_cache: bool = True, overwrite_cache: bool = False, progress_callback=None) -> Dict[str, Any]:
        """
        Procesa campaña completa con workflow translate -> miz -> deploy
        Integra toda la lógica del orquestador original
        
        Args:
            config: Configuración completa con:
                - campaign_name: Nombre de campaña
                - campaign_path: Ruta de campaña
                - missions: Lista de misiones a procesar
                - mode: 'translate', 'miz', 'all', 'deploy'
                - output_dir: Directorio base de salida
                - deploy_dir: Directorio de deploy (opcional)
                - deploy_overwrite: Si sobreescribir en deploy
                - include_fc: Incluir misiones Flaming Cliffs
            progress_callback: Función opcional para reportar progreso: callback(mission_name, campaign_name, success)
                
        Returns:
            Dict con resultados completos del workflow
        """
        campaign_name = config.get('campaign_name', 'Unknown')
        campaign_path = config.get('campaign_path', '')
        mode = config.get('mode', 'translate')
        
        self.logger.info(f"Iniciando workflow completo para campaña: {campaign_name} (modo: {mode})")
        
        # Preparar directorios de campaña
        campaign_dirs = self.ensure_campaign_local_dirs(campaign_name)
        
        result = {
            'campaign_name': campaign_name,
            'mode': mode,
            'campaign_dirs': campaign_dirs,
            'translate_results': None,
            'miz_results': None,
            'deploy_results': None,
            'success': False,
            'errors': []
        }
        
        try:
            if mode in ('translate', 'all', 'traducir'):
                self.logger.info("Ejecutando fase de traducción...")
                translate_result = self._execute_translate_phase(config, campaign_dirs, use_cache=use_cache, overwrite_cache=overwrite_cache, progress_callback=progress_callback)
                result['translate_results'] = translate_result
                
                if not translate_result.get('success', False):
                    raise RuntimeError("Falló la fase de traducción")
            
            if mode in ('miz', 'all', 'reempaquetar'):
                self.logger.info("Ejecutando fase de empaquetado MIZ...")
                miz_result = self._execute_miz_phase(config, campaign_dirs, progress_callback)
                result['miz_results'] = miz_result
                
                if not miz_result.get('success', False):
                    raise RuntimeError("Falló la fase de empaquetado MIZ")
            
            if mode in ('deploy', 'desplegar'):
                self.logger.info("Ejecutando fase de deploy...")
                deploy_result = self._execute_deploy_phase(config, campaign_dirs, progress_callback)
                result['deploy_results'] = deploy_result
                
                if not deploy_result.get('success', False):
                    raise RuntimeError("Falló la fase de deploy")
            
            # Generar ZIP de logs
            log_zip = self.zip_campaign_logs(campaign_name)
            if log_zip:
                result['log_zip'] = log_zip
            
            result['success'] = True
            self.logger.info(f"Workflow completado exitosamente para campaña: {campaign_name}")
            
        except Exception as e:
            error_msg = f"Error en workflow de campaña {campaign_name}: {e}"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            result['success'] = False
            
        return result
    
    def _execute_translate_phase(self, config: Dict[str, Any], campaign_dirs: Dict[str, str], use_cache: bool = True, overwrite_cache: bool = False, progress_callback=None) -> Dict[str, Any]:
        """Ejecuta la fase de traducción de archivos Lua"""
        campaign_name = config.get('campaign_name')
        campaign_path = config.get('campaign_path')
        selected_missions = config.get('missions', [])
        
        # Obtener misiones a procesar
        normals, fcs = self.find_miz_files_grouped(campaign_path)
        include_fc = config.get('include_fc', False)
        
        # Filtrar misiones seleccionadas
        chosen = []
        chosen_names = set(selected_missions)
        
        for p in normals:
            if os.path.basename(p) in chosen_names:
                chosen.append(p)
        
        if include_fc:
            for p in fcs:
                if os.path.basename(p) in chosen_names:
                    chosen.append(p)
        
        if not chosen:
            raise RuntimeError("No se seleccionaron misiones válidas")
        
        result = {
            'total_missions': len(chosen),
            'successful_missions': 0,
            'failed_missions': 0,
            'mission_results': [],
            'success': False
        }
        
        # Variable para controlar la validación de LM Studio (solo una vez por campaña)
        lm_validation_done = False
        
        for idx, miz_path in enumerate(chosen, 1):
            miz_file = os.path.basename(miz_path)
            miz_stem_raw = os.path.splitext(miz_file)[0]
            miz_base = self.normalize_stem(miz_stem_raw)
            
            self.logger.info(f"Traduciendo misión {idx}/{len(chosen)}: {miz_file}")
            
            # Reportar progreso al iniciar misión
            if progress_callback:
                try:
                    progress_callback(miz_file, campaign_name, None)  # None = en progreso
                except Exception as e:
                    self.logger.warning(f"Error en callback de progreso: {e}")
            
            # Crear estructura específica para esta misión
            mission_dirs = self.ensure_mission_local_dirs(campaign_name, miz_file)
            # FIX: No duplicar el nombre de misión en extract_dir - ya está incluido en mission_dirs["extracted"]
            extract_dir = mission_dirs["extracted"]
            
            mission_success = False
            try:
                # Extraer MIZ
                self.extract_miz(miz_path, extract_dir)
                
                # FILE_TARGET: Usar método centralizado  
                from app.services.user_config import UserConfigService
                file_target = config.get('file_target') or UserConfigService.get_file_target()
                self.logger.info(f"🎯 FILE_TARGET obtenido: {file_target} (desde {'config' if config.get('file_target') else 'user_config'})")
                
                # Buscar diccionario
                lua_file = os.path.join(extract_dir, file_target)
                
                if not os.path.exists(lua_file):
                    raise FileNotFoundError(f"Diccionario no encontrado: {file_target}")
                
                # Traducir usando el nuevo motor integrado translate_lua_file
                # Cargar configuración de prompts y modelo
                prompt_config = self._load_prompt_config(config.get('prompt_file'))
                lm_config = config.get('lm_config', {})
                
                # Combinar configuraciones CON FUSIÓN DE API
                translation_cfg = prompt_config.copy()
                if lm_config:
                    translation_cfg.update(lm_config)
                
                # FUSIONAR configuración API del preset con la del prompt
                merged_api_config = self._merge_api_config(prompt_config, lm_config)
                translation_cfg['LM_API'] = merged_api_config
                
                # Cargar configuración del usuario
                user_config = self._load_user_config()
                
                # Configurar parámetros de traducción usando configuración del usuario
                batch_size = config.get('batch_size') or int(user_config.get('arg_batch', 8))
                timeout = config.get('timeout') or int(user_config.get('arg_timeout', 120))
                keys_filter = config.get('keys_filter')
                
                # URLs y modelo LM Studio - usar configuración del usuario (sin fallbacks)
                lm_url = lm_config.get('url') or user_config.get('lm_url')
                lm_model = lm_config.get('model') or user_config.get('lm_model')
                compat = lm_config.get('compat') or user_config.get('arg_compat')
                
                # Validar que la configuración requerida esté presente
                if not lm_url:
                    raise ValueError("lm_url no configurado en user_config.json")
                if not lm_model:
                    raise ValueError("lm_model no configurado en user_config.json")
                if not compat:
                    raise ValueError("arg_compat no configurado en user_config.json")
                
                # Crear estructura de directorios específica para esta misión
                mission_dirs = self.ensure_mission_local_dirs(campaign_name, miz_base + '.miz')
                mission_output_dir = mission_dirs["out_lua"]
                
                # Usar el motor original pero con configuración del usuario
                # FIX: No concatenar campaign_name con miz_base - usar campaign_name original
                translation_result = self.translate_lua_file(
                    lua_path=lua_file,
                    campaign_name=campaign_name,
                    output_dir=mission_output_dir,
                    cfg=translation_cfg,
                    batch_size=batch_size,
                    timeout=timeout,
                    keys_filter=keys_filter,
                    lm_url=lm_url,
                    lm_model=lm_model,
                    compat=compat,
                    use_cache=use_cache,
                    overwrite_cache=overwrite_cache,
                    skip_lm_validation=lm_validation_done  # Omitir validación después de la primera misión
                )
                
                # Marcar que la validación de LM Studio ya se hizo
                lm_validation_done = True
                
                # Mover logs de traducción
                self.harvest_translator_logs(mission_output_dir, campaign_name, miz_base)
                
                # Preparar resultado de misión
                mission_result = {
                    'mission': miz_file,
                    'success': True,
                    'translation_file': translation_result.get('output_file'),
                    'segments_translated': translation_result.get('segments_translated', 0),
                    'segments_total': translation_result.get('segments_total', 0),
                    'translation_rate': translation_result.get('translation_rate', 0),
                    'cache_hits': translation_result.get('cache_hits', 0),
                    'api_calls': translation_result.get('api_calls', 0),
                    'processing_time': translation_result.get('processing_time', 0),
                    'output_files': {
                        'translated_lua': translation_result.get('output_file'),
                        'placeholder_lua': translation_result.get('placeholder_file'),
                        'translations_jsonl': translation_result.get('translations_jsonl'),
                        'cache_file': translation_result.get('cache_file')
                    }
                }
                
                # Generar reporte individual para esta misión
                self._generate_mission_report(campaign_name, miz_file, mission_result, config)
                
                result['mission_results'].append(mission_result)
                result['successful_missions'] += 1
                mission_success = True
                
                # Reportar progreso al completar misión exitosamente
                if progress_callback:
                    try:
                        progress_callback(miz_file, campaign_name, True)
                    except Exception as e:
                        self.logger.warning(f"Error en callback de progreso (éxito): {e}")
                
            except Exception as e:
                error_msg = f"Error traduciendo {miz_file}: {e}"
                self.logger.error(error_msg)
                
                # Preparar resultado de misión fallida
                mission_result = {
                    'mission': miz_file,
                    'success': False,
                    'error': error_msg,
                    'translation_file': None,
                    'segments_translated': 0
                }
                
                # Generar reporte individual incluso para misiones fallidas
                self._generate_mission_report(campaign_name, miz_file, mission_result, config)
                
                result['mission_results'].append(mission_result)
                result['failed_missions'] += 1
                mission_success = False
                
                # Reportar progreso al fallar misión
                if progress_callback:
                    try:
                        progress_callback(miz_file, campaign_name, False)
                    except Exception as e:
                        self.logger.warning(f"Error en callback de progreso (fallo): {e}")
        
        result['success'] = result['successful_missions'] > 0
        
        # FIX: No copiar archivos fuera de out_lua - mantenerlos en su ubicación correcta
        # Los archivos ya están correctamente organizados en la estructura mission/out_lua/
        # Comentado para evitar duplicación de archivos fuera de out_lua
        # if result['success']:
        #     output_directory = config.get('output_dir')
        #     if output_directory:
        #         self._copy_final_translation_results(campaign_dirs, output_directory, result)
        
        return result
    
    def _copy_final_translation_results(self, campaign_dirs: Dict[str, str], output_directory: str, result: Dict[str, Any]) -> None:
        """Copia archivos finales de traducción al directorio de salida"""
        try:
            ensure_directory(output_directory)
            
            # Buscar archivos en subdirectorios de misiones (nueva estructura)
            # Patrón: F-5E_BFM/*/out_lua/
            mission_dirs = [d for d in os.listdir(campaign_dirs["base"]) 
                          if os.path.isdir(os.path.join(campaign_dirs["base"], d)) and 
                             os.path.exists(os.path.join(campaign_dirs["base"], d, "out_lua"))]
            
            for mission_dir in mission_dirs:
                mission_path = os.path.join(campaign_dirs["base"], mission_dir, "out_lua")
                mission_output_path = os.path.join(output_directory, mission_dir)
                ensure_directory(mission_output_path)
                
                # Copiar archivos .translated.lua
                translated_files = glob.glob(os.path.join(mission_path, "*.translated.lua"))
                for src_file in translated_files:
                    dst_file = os.path.join(mission_output_path, os.path.basename(src_file))
                    shutil.copy2(src_file, dst_file)
                    self.logger.info(f"Archivo copiado: {src_file} -> {dst_file}")
                
                # Copiar archivos de estadísticas y cache
                stats_files = glob.glob(os.path.join(mission_path, "*.stats.json"))
                for src_file in stats_files:
                    dst_file = os.path.join(mission_output_path, os.path.basename(src_file))
                    shutil.copy2(src_file, dst_file)
                
                jsonl_files = glob.glob(os.path.join(mission_path, "*.translations.jsonl"))
                for src_file in jsonl_files:
                    dst_file = os.path.join(mission_output_path, os.path.basename(src_file))
                    shutil.copy2(src_file, dst_file)
                
                cache_files = glob.glob(os.path.join(mission_path, "translation_cache.json"))
                for src_file in cache_files:
                    dst_file = os.path.join(mission_output_path, os.path.basename(src_file))
                    shutil.copy2(src_file, dst_file)
                
            self.logger.info(f"Archivos de traducción copiados a: {output_directory}")
            
        except Exception as e:
            self.logger.error(f"Error copiando archivos finales: {e}")
    
    def _execute_miz_phase(self, config: Dict[str, Any], campaign_dirs: Dict[str, str], progress_callback: Callable = None) -> Dict[str, Any]:
        """Ejecuta la fase de empaquetado MIZ con archivos traducidos"""
        campaign_path = config.get('campaign_path')
        selected_missions = config.get('missions', [])
        campaign_name = config.get('campaign_name', 'Unknown')
        
        result = {
            'total_packages': 0,
            'successful_packages': 0,
            'failed_packages': 0,
            'package_results': [],
            'success': False
        }
        
        if not selected_missions:
            raise RuntimeError("No se especificaron misiones para reempaquetar")
        
        self.logger.info(f"Reempaquetando {len(selected_missions)} misiones para campaña {campaign_name}")
        
        # Procesar cada misión seleccionada individualmente
        for mission_file in selected_missions:
            mission_name = mission_file.replace('.miz', '')  # Ej: "F-5E - Arrival"
            mission_slug = self.slugify(mission_name)        # Ej: "F-5E_-_Arrival"
            
            self.logger.info(f"Procesando misión: {mission_file}")
            
            # Callback de inicio de misión
            if progress_callback:
                progress_callback(mission_name, campaign_name)
            
            # Buscar MIZ original en campaign_path
            original_miz = os.path.join(campaign_path, mission_file)
            if not os.path.exists(original_miz):
                self.logger.warning(f"MIZ original no encontrado: {original_miz}")
                result['failed_packages'] += 1
                result['package_results'].append({
                    'mission': mission_file,
                    'success': False,
                    'error': f'MIZ original no encontrado: {original_miz}'
                })
                # Callback de finalización fallida
                if progress_callback:
                    progress_callback(mission_name, campaign_name, success=False)
                
                # Generar reporte individual para misión fallida
                failure_result = {
                    'mission': mission_file,
                    'mission_name': mission_name,
                    'success': False,
                    'mode': 'reempaquetado',
                    'error': f'MIZ original no encontrado: {original_miz}',
                    'output_files': {}
                }
                self._generate_mission_report(campaign_name, mission_file, failure_result, config)
                continue
            
            # Buscar archivos traducidos para esta misión específica
            mission_translation_dir = os.path.join(campaign_dirs["base"], mission_slug)
            translated_files = glob.glob(os.path.join(mission_translation_dir, "out_lua", "*.translated.lua"))
            
            if not translated_files:
                self.logger.warning(f"No se encontraron archivos traducidos para {mission_file}")
                result['failed_packages'] += 1
                result['package_results'].append({
                    'mission': mission_file,
                    'success': False,
                    'error': 'No se encontraron archivos traducidos'
                })
                # Callback de finalización fallida
                if progress_callback:
                    progress_callback(mission_name, campaign_name, success=False)
                
                # Generar reporte individual para misión fallida
                failure_result = {
                    'mission': mission_file,
                    'mission_name': mission_name,
                    'success': False,
                    'mode': 'reempaquetado',
                    'error': 'No se encontraron archivos traducidos',
                    'output_files': {}
                }
                self._generate_mission_report(campaign_name, mission_file, failure_result, config)
                continue
            
            # Procesar cada archivo traducido de esta misión
            for translated_file in translated_files:
                base_name = os.path.basename(translated_file).replace('.translated.lua', '')
                self.logger.info(f"Procesando archivo traducido: {base_name}.translated.lua")
                
                try:
                    # Obtener directorios específicos de esta misión
                    mission_dirs = self.ensure_mission_local_dirs(campaign_name, mission_file)
                    
                    self.logger.info(f"Empaquetando {mission_file} con archivo traducido {base_name}...")
                    
                    # Crear directorio temporal para el empaquetado
                    temp_extract_dir = os.path.join(mission_dirs["extracted"], f"repack_{self.slugify(mission_name)}")
                    
                    # Limpiar directorio temporal si existe
                    if os.path.exists(temp_extract_dir):
                        shutil.rmtree(temp_extract_dir)
                    
                    # Extraer MIZ original
                    self.extract_miz(original_miz, temp_extract_dir)
                    
                    # FILE_TARGET: Usar método centralizado
                    from app.services.user_config import UserConfigService
                    file_target = config.get('file_target') or UserConfigService.get_file_target()
                    self.logger.info(f"🎯 FILE_TARGET obtenido: {file_target} (desde {'config' if config.get('file_target') else 'user_config'})")
                    
                    # Reemplazar diccionario con versión traducida
                    dict_path = os.path.join(temp_extract_dir, file_target)
                    
                    if os.path.exists(dict_path):
                        self.logger.info(f"Reemplazando {dict_path} con {translated_file}")
                        shutil.copy2(translated_file, dict_path)
                    else:
                        # Crear directorios si no existen
                        self.logger.info(f"Creando directorio y copiando {translated_file} a {dict_path}")
                        ensure_directory(os.path.dirname(dict_path))
                        shutil.copy2(translated_file, dict_path)
                    
                    # Crear backup del original en la carpeta específica de la misión
                    self.backup_miz(original_miz, mission_dirs["backup"])
                    
                    # Comprimir nuevo MIZ en la carpeta específica de la misión
                    final_miz = os.path.join(mission_dirs["finalizado"], mission_file)
                    ensure_directory(mission_dirs["finalizado"])
                    self.compress_miz(temp_extract_dir, final_miz)
                    
                    # Limpiar temporal
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                    
                    self.logger.info(f"✅ Misión reempaquetada correctamente: {final_miz}")
                    
                    result['package_results'].append({
                        'mission': mission_file,
                        'translated_file': base_name,
                        'success': True,
                        'output_miz': final_miz
                    })
                    
                    result['successful_packages'] += 1
                    
                    # Callback de finalización exitosa
                    if progress_callback:
                        progress_callback(mission_name, campaign_name, success=True)
                    
                    # Generar reporte individual para esta misión reempaquetada
                    package_result = {
                        'mission': mission_file,
                        'mission_name': mission_name,
                        'success': True,
                        'mode': 'reempaquetado',
                        'translated_file': base_name,
                        'output_miz': final_miz,
                        'original_miz': original_miz,
                        'processing_time': time.time() - time.time(),  # TODO: medir tiempo real
                        'output_files': {
                            'output_miz': final_miz,
                            'backup_miz': os.path.join(mission_dirs["backup"], mission_file),
                            'translated_lua': translated_file
                        }
                    }
                    self._generate_mission_report(campaign_name, mission_file, package_result, config)
                    
                except Exception as e:
                    error_msg = f"Error empaquetando {mission_file} con {base_name}: {e}"
                    self.logger.error(error_msg)
                    result['package_results'].append({
                        'mission': mission_file,
                        'translated_file': base_name,
                        'success': False,
                        'error': error_msg
                    })
                    result['failed_packages'] += 1
                    
                    # Callback de finalización fallida
                    if progress_callback:
                        progress_callback(mission_name, campaign_name, success=False)
                    
                    # Generar reporte individual para misión fallida
                    failure_result = {
                        'mission': mission_file,
                        'mission_name': mission_name,
                        'success': False,
                        'mode': 'reempaquetado',
                        'error': error_msg,
                        'translated_file': base_name,
                        'output_files': {}
                    }
                    self._generate_mission_report(campaign_name, mission_file, failure_result, config)
        
        result['total_packages'] = len(selected_missions)
        
        result['success'] = result['successful_packages'] > 0
        return result
    
    def _execute_deploy_phase(self, config: Dict[str, Any], campaign_dirs: Dict[str, str], progress_callback: Callable = None) -> Dict[str, Any]:
        """Ejecuta la fase de deploy de archivos finalizados"""
        campaign_name = config.get('campaign_name')
        campaign_path = config.get('campaign_path')
        deploy_dir = config.get('deploy_dir', campaign_path)
        deploy_overwrite = config.get('deploy_overwrite', False)
        
        result = {
            'total_deploys': 0,
            'successful_deploys': 0,
            'failed_deploys': 0,
            'deploy_results': [],
            'success': False
        }
        
        # Obtener misiones seleccionadas específicamente
        selected_missions = config.get('missions', [])
        if not selected_missions:
            raise RuntimeError("No se especificaron misiones para deployar")
        
        # Buscar archivos finalizados solo para las misiones seleccionadas
        finalized_files = []
        base_dir = campaign_dirs["base"]
        
        self.logger.info(f"Buscando archivos finalizados en base: {base_dir}")
        
        for mission_file in selected_missions:
            found_file = False
            
            # Estrategia 1: Buscar en finalized_dir directamente
            finalized_dir = campaign_dirs.get("finalizado", os.path.join(base_dir, "finalizado"))
            mission_finalized_path = os.path.join(finalized_dir, mission_file)
            
            if os.path.exists(mission_finalized_path):
                finalized_files.append(mission_finalized_path)
                self.logger.info(f"✅ Encontrado en finalizado directo: {mission_file}")
                found_file = True
            else:
                # Estrategia 2: Buscar en subdirectorios de misión (estructura real)
                # Buscar en toda la estructura de subdirectorios
                search_pattern = os.path.join(base_dir, "**", "finalizado", mission_file)
                matching_files = glob.glob(search_pattern, recursive=True)
                
                if matching_files:
                    finalized_files.extend(matching_files)
                    self.logger.info(f"✅ Encontrado en subdirectorio: {mission_file} -> {matching_files[0]}")
                    found_file = True
                else:
                    # Estrategia 3: Búsqueda más amplia por nombre
                    search_pattern_wide = os.path.join(base_dir, "**", "finalizado", f"*{mission_file}*")
                    alternative_files = glob.glob(search_pattern_wide, recursive=True)
                    
                    if alternative_files:
                        finalized_files.extend(alternative_files)
                        self.logger.info(f"✅ Encontrado alternativo: {mission_file} -> {alternative_files[0]}")
                        found_file = True
            
            if not found_file:
                self.logger.error(f"❌ No se encontró archivo finalizado para: {mission_file}")
                self.logger.info(f"   Buscado en: {mission_finalized_path}")
                self.logger.info(f"   Patrón recursivo: {os.path.join(base_dir, '**', 'finalizado', mission_file)}")
        
        if not finalized_files:
            # Listar estructura para debug
            self.logger.error(f"📁 ESTRUCTURA ENCONTRADA EN {base_dir}:")
            try:
                for root, dirs, files in os.walk(base_dir):
                    level = root.replace(base_dir, '').count(os.sep)
                    indent = ' ' * 2 * level
                    self.logger.error(f"{indent}{os.path.basename(root)}/")
                    subindent = ' ' * 2 * (level + 1)
                    for file in files:
                        self.logger.error(f"{subindent}{file}")
            except Exception as e:
                self.logger.error(f"Error listando estructura: {e}")
                
            raise RuntimeError(f"No hay archivos .miz finalizados para las misiones seleccionadas: {selected_missions}")
        
        # Determinar directorio de destino
        if deploy_overwrite:
            # Sobrescribir: reemplazar misiones originales en el directorio de campaña original
            dest_dir = campaign_path
            backup_dir = os.path.join(campaign_path, "_backup_missions")
            self.logger.info(f"Modo SOBRESCRIBIR activado:")
            self.logger.info(f"  - Destino: {dest_dir}")
            self.logger.info(f"  - Backup: {backup_dir}")
        else:
            # No sobrescribir: crear nueva carpeta Translated_ES
            dest_dir = os.path.join(campaign_path, "Translated_ES")
            backup_dir = None
            self.logger.info(f"Modo NO SOBRESCRIBIR activado:")
            self.logger.info(f"  - Destino: {dest_dir}")
            self.logger.info(f"  - Sin backup necesario")
        
        ensure_directory(dest_dir)
        if backup_dir:
            ensure_directory(backup_dir)
        
        result['total_deploys'] = len(finalized_files)
        
        for finalized_file in finalized_files:
            file_name = os.path.basename(finalized_file)
            mission_name = file_name.replace('.miz', '')
            dest_file = os.path.join(dest_dir, file_name)
            
            # Callback de inicio de misión
            if progress_callback:
                progress_callback(mission_name, campaign_name)
            
            try:
                backup_created = False
                backup_path = None
                
                # Crear backup si es necesario (modo sobrescribir y archivo existe)
                if backup_dir and os.path.exists(dest_file):
                    backup_path = os.path.join(backup_dir, file_name)
                    shutil.copy2(dest_file, backup_path)
                    backup_created = True
                    self.logger.info(f"Backup creado: {file_name} -> {backup_path}")
                
                # Copiar archivo traducido al destino
                shutil.copy2(finalized_file, dest_file)
                
                if deploy_overwrite:
                    self.logger.info(f"Misión original reemplazada: {file_name} en {dest_file}")
                    if backup_created:
                        self.logger.info(f"Backup original guardado en: {backup_path}")
                else:
                    self.logger.info(f"Misión deployada: {file_name} -> {dest_file}")
                
                result['deploy_results'].append({
                    'mission': file_name,
                    'success': True,
                    'deployed_to': dest_file,
                    'source_file': finalized_file,
                    'backup_created': backup_created,
                    'backup_path': backup_path,
                    'overwrite_mode': deploy_overwrite
                })
                
                result['successful_deploys'] += 1
                
                # Callback de finalización exitosa
                if progress_callback:
                    progress_callback(mission_name, campaign_name, success=True)
                
                # Generar reporte individual para esta misión deployada
                deploy_result = {
                    'mission': file_name,
                    'mission_name': mission_name,
                    'success': True,
                    'mode': 'deploy',
                    'deployed_to': dest_file,
                    'source_file': finalized_file,
                    'backup_created': backup_created,
                    'backup_path': backup_path,
                    'overwrite_mode': deploy_overwrite,
                    'processing_time': 0,  # Deploy es instantáneo
                    'output_files': {
                        'deployed_miz': dest_file,
                        'source_miz': finalized_file,
                        'backup_miz': backup_path if backup_created else None
                    }
                }
                self._generate_mission_report(campaign_name, file_name, deploy_result, config)
                
            except Exception as e:
                error_msg = f"Error deployando {file_name}: {e}"
                self.logger.error(error_msg)
                result['deploy_results'].append({
                    'mission': file_name,
                    'success': False,
                    'error': error_msg,
                    'source_file': finalized_file
                })
                result['failed_deploys'] += 1
                
                # Callback de finalización fallida
                if progress_callback:
                    progress_callback(mission_name, campaign_name, success=False)
                
                # Generar reporte individual para misión fallida
                failure_result = {
                    'mission': file_name,
                    'mission_name': mission_name,
                    'success': False,
                    'mode': 'deploy',
                    'error': error_msg,
                    'source_file': finalized_file,
                    'output_files': {}
                }
                self._generate_mission_report(campaign_name, file_name, failure_result, config)
        
        result['success'] = result['successful_deploys'] > 0
        
        # Logging final del deploy
        self.logger.info(f"🎯 DEPLOY COMPLETADO:")
        self.logger.info(f"   Total archivos: {result['total_deploys']}")
        self.logger.info(f"   Exitosos: {result['successful_deploys']}")
        self.logger.info(f"   Fallidos: {result['failed_deploys']}")
        self.logger.info(f"   Directorio destino: {dest_dir}")
        if backup_dir and deploy_overwrite:
            self.logger.info(f"   Directorio backup: {backup_dir}")
        self.logger.info(f"   Modo sobrescribir: {deploy_overwrite}")
        
        return result
    
    def get_translation_status(self, session_id: str) -> Dict[str, Any]:
        """Obtiene el estado de una traducción en curso"""
        # TODO: Implementar seguimiento de estado en tiempo real
        return {
            'session_id': session_id,
            'status': 'unknown',
            'progress': 0,
            'current_file': None,
            'estimated_remaining': None
        }
    
    def cancel_translation(self, session_id: str) -> bool:
        """Cancela una traducción en curso"""
        # TODO: Implementar cancelación de traducción
        self.logger.info(f"Cancelación solicitada para sesión: {session_id}")
        return True
    
    def _load_user_config(self) -> Dict[str, Any]:
        """Carga la configuración del usuario desde app/data/my_config/user_config.json"""
        user_config_path = os.path.join(os.path.dirname(TRANSLATIONS_DIR), 'my_config', 'user_config.json')
        
        if not os.path.exists(user_config_path):
            self.logger.info("Archivo de configuración de usuario no encontrado, usando configuración por defecto")
            return {}
        
        try:
            with open(user_config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            
            self.logger.info(f"Configuración de usuario cargada: {user_config_path}")
            return user_config
            
        except Exception as e:
            self.logger.error(f"Error cargando configuración de usuario: {e}")
            return {}

    def _load_prompt_config(self, prompt_file: Optional[str]) -> Dict[str, Any]:
        """Carga la configuración de prompts desde archivo YAML o configuración de usuario"""
        
        self.logger.info(f"Cargando configuración de prompts: {prompt_file}")
        
        # Primero intentar cargar configuración del usuario
        user_config = self._load_user_config()
        
        # PRIORIDAD: usar configuración del usuario SIEMPRE (si existe)
        if user_config.get('arg_config'):
            prompt_file = user_config.get('arg_config')
            self.logger.info(f"Usando archivo de prompts desde configuración de usuario: {prompt_file}")
        elif not prompt_file:
            self.logger.warning("No se especificó archivo de prompts, usando configuración por defecto")
            return self._get_default_prompt_config()
        
        prompt_path = os.path.join(PROMPTS_DIR, prompt_file)
        if not os.path.exists(prompt_path):
            # Buscar también en el directorio legacy
            legacy_path = os.path.join(os.path.dirname(PROMPTS_DIR), 'PROMTS', prompt_file)
            if os.path.exists(legacy_path):
                prompt_path = legacy_path
            else:
                self.logger.warning(f"Archivo de prompts no encontrado: {prompt_file}")
                return self._get_default_prompt_config()
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                if prompt_path.lower().endswith(('.yml', '.yaml')):
                    config = yaml.safe_load(f) if YAML_AVAILABLE else {}
                else:
                    config = json.load(f)
            
            if not config:
                self.logger.warning(f"Archivo de configuración vacío: {prompt_path}")
                return self._get_default_prompt_config()
                
            # Verificar que tenga las claves necesarias
            if 'TARGET_PREFIXES' not in config:
                self.logger.warning(f"TARGET_PREFIXES no encontrado en {prompt_path}, usando valores por defecto")
                default_config = self._get_default_prompt_config()
                config['TARGET_PREFIXES'] = default_config['TARGET_PREFIXES']
                config['EXCLUDE_PREFIXES'] = config.get('EXCLUDE_PREFIXES', default_config['EXCLUDE_PREFIXES'])
            
            self.logger.info(f"Configuración de prompts cargada: {prompt_path}")
            self.logger.info(f"TARGET_PREFIXES: {config.get('TARGET_PREFIXES', [])}")
            self.logger.info(f"EXCLUDE_PREFIXES: {config.get('EXCLUDE_PREFIXES', [])}")
            return config
            
        except Exception as e:
            self.logger.error(f"Error cargando configuración de prompts desde {prompt_path}: {e}")
            self.logger.info("Usando configuración por defecto con TARGET_PREFIXES correctos")
            return self._get_default_prompt_config()
    
    def _get_default_prompt_config(self) -> Dict[str, Any]:
        """
        Configuración de prompts por defecto estandarizada
        Basada en el sistema de 3 presets (Ligero/Balanceado/Pesado)
        """
        return {
            # Configuración base - Compatible con preset "Ligero - Equipos Básicos"
            "name": "Default DCS Translation Config",
            "description": "Configuración por defecto basada en presets estandarizados",
            "type": "completions",
            "architecture": "universal",
            "weight_compatibility": ["ligero", "balanceado"],
            
            # Instrucciones principales optimizadas
            "LM_INSTRUCTIONS": "Eres un traductor profesional especializado en simuladores de vuelo militar, específicamente DCS World.\n\nTAREA: Traduce el siguiente texto JSON del inglés al español manteniendo:\n• Terminología técnica de aviación precisa\n• Nombres propios sin traducir (códigos, callsigns, lugares)\n• Formato JSON exacto\n• Coherencia con el contexto militar/aeronáutico\n\nRESPONDE SOLO con el JSON traducido:\n",
            
            # Sistema mejorado para modelos que lo soporten
            "SYSTEM": "Eres un especialista en traducción técnica militar con experiencia en DCS World y terminología OTAN.",
            
            # Configuración API estandarizada (basada en preset ligero)
            "LM_API": {
                "temperature": 0.1,              # Baja para consistencia técnica
                "top_p": 0.85,                   # Conservador para precisión
                "top_k": 30,                     # Limitado para evitar divagaciones
                "max_tokens": 1024,              # Suficiente para traducciones
                "stop": ["</s>", "<|eot_id|>", "\n\n---", "Human:", "Assistant:", "]}", "]}\n", "]},\n]"],
                "supports_system": True,
                "repetition_penalty": 1.1,       # Ligera para evitar repetición
                "presence_penalty": 0.05,        # Mínima para modelos pequeños
                "frequency_penalty": 0.05        # Mínima para modelos pequeños
            },
            
            # Configuración de procesamiento
            "PROTECT_BRACKETS": True,
            "PRESERVE_FORMATTING": True,
            "ENABLE_CONTEXT_AWARENESS": True,
            
            # Filtros TARGET expandidos y estandarizados
            "TARGET_PREFIXES": [
                "DictKey_ActionText_",          # Textos de acciones de misión
                "DictKey_ActionRadioText_",     # Comunicaciones de radio
                "DictKey_descriptionBlueTask_", # Descripciones de tareas azules
                "DictKey_descriptionRedTask_",  # Descripciones de tareas rojas (añadido)
                "DictKey_descriptionText_",     # Descripciones generales
                "DictKey_briefingText_",        # Textos de briefing (añadido)
                "DictKey_missionText_",         # Textos de misión (añadido)
                "DictKey_triggerText_"          # Textos de triggers (añadido)
            ],
            
            # Filtros EXCLUDE expandidos y estandarizados
            "EXCLUDE_PREFIXES": [
                "DictKey_UnitName_",            # Nombres de unidades
                "DictKey_GroupName_",           # Nombres de grupos
                "DictKey_sortie_",              # Códigos de sortie
                "DictKey_WptName_",             # Nombres de waypoints
                "DictKey_coalitionName_",       # Nombres de coalición (añadido)
                "DictKey_countryName_",         # Nombres de países (añadido)
                "DictKey_airbaseName_",         # Nombres de bases aéreas (añadido)
                "Country",                      # Países (códigos)
                "Callsign",                     # Indicativos
                "Skin",                         # Skins/libreas
                "Livery",                       # Libreas
                "Frequency"                     # Frecuencias (añadido)
            ],
            
            # Términos protegidos expandidos
            "PROTECT_WORDS": [
                # Aeronaves principales
                "DCS", "F-16C", "F/A-18C", "A-10C", "AV-8B", "F-14", "F-5E", "M-2000C",
                # Sistemas básicos
                "HOTAS", "HUD", "RWR", "IFF", "TACAN", "ILS", "VOR", "DME"
            ],
            
            # Términos técnicos que NO se traducen
            "NO_TRANSLATE_TERMS": [
                "HOTAS", "HUD", "RWR", "IFF", "TACAN", "ILS", "VOR", "DME", "GPS", "INS"
            ],
            
            # Configuración legacy mantenida para compatibilidad
            "TECHNICAL_TERMS_NO_TRASLATE": [],
            
            # Glosario técnico básico
            "TECHNICAL_GLOSSARY": {
                "ROE": "RdE",                   # Rules of Engagement
                "BDA": "EDA",                   # Battle Damage Assessment
                "CAS": "AAC",                   # Close Air Support
                "CAP": "PCA",                   # Combat Air Patrol
                "IP": "PI",                     # Initial Point
                "TGT": "OBJ"                    # Target
            },
            
            # Configuración legacy mantenida
            "GLOSSARY_OTAN": {},
            "PHRASEOLOGY_RULES": [],
            "POST_RULES": [],
            "FIXED_FULL_REPLACEMENTS": {},
            
            # Metadatos del preset por defecto
            "preset_info": {
                "recommended_preset": "Ligero - Equipos Básicos",
                "recommended_prompt": "1-llama-completions.yaml",
                "fallback_reason": "Configuración por defecto segura"
            }
        }
    
    def _process_file(self, lua_path: str, output_dir: str, batch_size: int, 
                     timeout: int, keys_filter: Optional[List[str]], 
                     prompt_config: Dict[str, Any], lm_config: Dict[str, Any],
                     session_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Redirige al nuevo flujo que respeta los filtros correctamente
        """
        return self._process_file_new_flow(lua_path, output_dir, batch_size, timeout, keys_filter, prompt_config, lm_config, session_id, use_cache)
    
    def _process_file_new_flow(self, lua_path: str, output_dir: str, batch_size: int, 
                     timeout: int, keys_filter: Optional[List[str]], 
                     prompt_config: Dict[str, Any], lm_config: Dict[str, Any],
                     session_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Procesa un archivo .lua individual
        Basado en la función process_file del motor original
        """
        self.logger.info(f"Iniciando procesamiento: {lua_path}")
        
        # Leer archivo
        try:
            with open(lua_path, "r", encoding="utf-8", newline="") as f:
                lua_text = f.read()
        except Exception as e:
            raise IOError(f"Error leyendo archivo {lua_path}: {e}")
        
        # Aplicar pre-procesamiento
        lua_text = self._apply_preprocessing(lua_text, prompt_config)
        
        # Detectar entradas
        total_entries = len(list(self.entry_regex.finditer(lua_text)))
        self.logger.info(f"Entradas detectadas: {total_entries}")
        
        # Procesar segmentos
        segments = self._extract_segments(lua_text, keys_filter, prompt_config)
        self.logger.info(f"Segmentos a traducir: {len(segments)}")
        
        # Traducir con LM Studio
        translation_results = self._translate_segments(
            segments, prompt_config, lm_config, batch_size, timeout, output_dir, use_cache
        )
        
        # Generar archivo final
        output_file = self._generate_output_file(
            lua_text, segments, output_dir, lua_path, prompt_config
        )
        
        # Generar archivos auxiliares
        self._generate_auxiliary_files(segments, output_dir, lua_path, session_id)
        
        return {
            'session_id': session_id,
            'input_file': lua_path,
            'output_file': output_file,
            'total_entries': total_entries,
            'segments_translated': len([s for s in segments if hasattr(s, 'es') and s.es]),
            'cache_hits': translation_results.get('cache_hits', 0),
            'api_calls': translation_results.get('api_calls', 0),
            'processing_time': translation_results.get('processing_time', 0)
        }
    
    def _translate_campaign_files(self, campaign: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Traduce los archivos de una campaña"""
        campaign_name = campaign.get('name', 'Unknown')
        campaign_path = campaign.get('path', '')
        
        self.logger.info(f"Iniciando traducción de campaña: {campaign_name}")
        
        # TODO: Implementar extracción de archivos .miz y traducción
        # Por ahora, mock de la funcionalidad
        
        return {
            'name': campaign_name,
            'path': campaign_path,
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'errors': [],
            'output_directory': os.path.join(TRANSLATIONS_DIR, campaign_name.replace(' ', '_'))
        }
    
    def _apply_preprocessing(self, text: str, config: Dict[str, Any]) -> str:
        """Aplica reglas de pre-procesamiento al texto"""
        # Normalizar comillas
        text = text.replace("'", "'")
        
        # Aplicar reemplazos fijos
        fixed_replacements = config.get("FIXED_FULL_REPLACEMENTS", {})
        for en_phrase, es_phrase in fixed_replacements.items():
            text = text.replace(en_phrase, es_phrase)
        
        # Aplicar otras reglas de pre-procesamiento
        text = self._apply_glossary_rules(text, config)
        text = self._apply_phraseology_rules(text, config)
        
        return text
    
    def _extract_segments(self, lua_text: str, keys_filter: Optional[List[str]], 
                         config: Dict[str, Any]) -> List['TranslationSegment']:
        """Extrae segmentos del texto lua para traducir"""
        segments = []
        protect_brackets = config.get("PROTECT_BRACKETS", True)
        
        def replace_entry(m: re.Match) -> str:
            pre, key, value, post = m.group("pre"), m.group("key"), m.group("value"), m.group("post")
            
            if not self._key_is_target(key, keys_filter, config):
                return m.group(0)
            
            # Extraer segmentos de línea
            start_idx = len(segments)
            for i, sm in enumerate(self.line_split_regex.finditer(value)):
                seg_txt = sm.group("seg")
                lb = sm.group("lb")
                
                if seg_txt == "" and lb == "":
                    continue
                
                segment = TranslationSegment(
                    key=key,
                    index=start_idx + i,
                    raw_seg=seg_txt,
                    lb=lb,
                    protect_brackets=protect_brackets
                )
                segments.append(segment)
            
            # Reemplazar con IDs temporales
            new_value = "".join(seg.id + seg.punct + seg.lb for seg in segments[start_idx:])
            return pre + new_value + post
        
        # Procesar el texto
        self.entry_regex.sub(replace_entry, lua_text)
        
        return segments
    
    def _translate_segments(self, segments: List['TranslationSegment'], 
                          config: Dict[str, Any], lm_config: Dict[str, Any],
                          batch_size: int, timeout: int, output_dir: str,
                          use_cache: bool = True) -> Dict[str, Any]:
        """Traduce los segmentos usando LM Studio"""
        
        self.logger.info(f"⚡⚡⚡ EJECUTANDO _TRANSLATE_SEGMENTS (FLUJO ALTERNATIVO) ⚡⚡⚡")
        self.logger.info(f"🔧 Parámetro use_cache en _translate_segments: {use_cache}")
        
        start_time = time.perf_counter()
        api_calls = 0
        cache_hits = 0
        
        # Cargar caché (solo si use_cache=True)
        cache_path = os.path.join(output_dir, "translation_cache.json")
        if use_cache:
            cache = self._load_cache(cache_path)
            self.logger.info(f"Cache local cargado: {len(cache)} entradas")
        else:
            cache = {}
            self.logger.info("Cache deshabilitado - iniciando con cache vacío")
        
        # Agrupar segmentos únicos
        unique_segments = {}
        for segment in segments:
            if segment.clean_for_model.strip():
                if segment.clean_for_model not in unique_segments:
                    unique_segments[segment.clean_for_model] = []
                unique_segments[segment.clean_for_model].append(segment.id)
        
        # Verificar caché (solo si use_cache=True)
        to_translate = []
        for text, segment_ids in unique_segments.items():
            if use_cache and text in cache:
                # Aplicar traducción desde caché
                for segment in segments:
                    if segment.id in segment_ids:
                        segment.es = cache[text]
                cache_hits += 1
            else:
                to_translate.append((segment_ids[0], text))
        
        self.logger.info(f"Caché hits: {cache_hits}, A traducir: {len(to_translate)}")
        
        # Calcular progreso real basado en segmentos totales
        total_segments = len(unique_segments)  # Total de segmentos únicos a procesar
        processed_segments = cache_hits  # Empezamos con los cache hits ya procesados
        total_batches = len(range(0, len(to_translate), batch_size)) if to_translate else 1
        
        # Reportar progreso inicial (cache hits completados)
        if hasattr(self, 'progress_callback') and self.progress_callback and total_segments > 0:
            initial_progress = int((processed_segments / total_segments) * 100)
            progress_data = {
                'total_segments': total_segments,
                'processed_segments': processed_segments,
                'cache_hits': cache_hits,
                'model_calls': api_calls,
                'total_batches': total_batches,
                'processed_batches': 0,
                'segment_progress': initial_progress,
                'phase': f'Cache: {cache_hits}/{total_segments} segmentos procesados'
            }
            self.progress_callback(progress_data)
        
        # Traducir en lotes
        for i in range(0, len(to_translate), batch_size):
            # Verificar cancelación antes de cada batch
            if self._check_cancellation():
                self.logger.warning("🛑 Cancelación detectada - Deteniendo traducción por lotes")
                raise Exception("Operación cancelada por el usuario - Traducción por lotes interrumpida")
            
            batch_number = (i // batch_size) + 1
            batch = to_translate[i:i+batch_size]
            
            try:
                results = self._call_lm_studio_batch(batch, config, lm_config, timeout)
                api_calls += 1
                
                for segment_id, original_text in batch:
                    translation = results.get(segment_id, original_text)
                    
                    # Aplicar post-procesamiento
                    translation = self._apply_postprocessing(translation, config)
                    
                    # Actualizar segmentos y caché (solo si use_cache=True)
                    if use_cache:
                        cache[original_text] = translation
                    for segment in segments:
                        if segment.clean_for_model == original_text:
                            segment.es = translation
                            
            except Exception as e:
                self.logger.error(f"Error en lote {i//batch_size + 1}: {e}")
                # Usar texto original como fallback
                for segment_id, original_text in batch:
                    for segment in segments:
                        if segment.id == segment_id:
                            segment.es = original_text
            
            # Actualizar contador de segmentos procesados
            processed_segments += len(batch)
            
            # Reportar progreso después del lote procesado
            if hasattr(self, 'progress_callback') and self.progress_callback and total_segments > 0:
                segment_progress = int((processed_segments / total_segments) * 100)
                progress_data = {
                    'total_segments': total_segments,
                    'processed_segments': processed_segments,
                    'cache_hits': cache_hits,
                    'model_calls': api_calls,
                    'total_batches': total_batches,
                    'processed_batches': batch_number,
                    'segment_progress': segment_progress,
                    'phase': f'Lote {batch_number}/{total_batches} - {processed_segments}/{total_segments} segmentos'
                }
                self.progress_callback(progress_data)
        
        # Guardar caché (solo si use_cache=True)
        if use_cache:
            self._save_cache(cache, cache_path)
        else:
            self.logger.info("Cache deshabilitado - no se guardará cache local")
        
        # Reportar progreso final (100%)
        if hasattr(self, 'progress_callback') and self.progress_callback:
            progress_data = {
                'total_segments': total_segments,
                'processed_segments': total_segments,
                'cache_hits': cache_hits,
                'model_calls': api_calls,
                'total_batches': total_batches,
                'processed_batches': total_batches,
                'segment_progress': 100,
                'phase': f'Completado: {total_segments} segmentos ({cache_hits} cache + {api_calls} modelo)'
            }
            self.progress_callback(progress_data)
        
        processing_time = time.perf_counter() - start_time
        
        return {
            'cache_hits': cache_hits,
            'api_calls': api_calls,
            'processing_time': processing_time
        }
    
    def _merge_api_config(self, prompt_config: Dict[str, Any], lm_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fusiona la configuración de API del prompt con la del preset.
        PRECEDENCIA: Preset (lm_api_config) > Prompt (LM_API) > Defaults
        
        Args:
            prompt_config: Configuración del prompt con campo LM_API
            lm_config: Configuración LM general que puede incluir lm_api_config desde preset
            
        Returns:
            Dict con configuración de API fusionada
        """
        # Base: configuración del prompt
        merged_config = prompt_config.get("LM_API", {}).copy()
        
        # Intentar obtener configuración del preset desde lm_config
        preset_api_config = lm_config.get("lm_api_config", {})
        
        # Si no está en lm_config, cargar preset actual desde user_config
        if not preset_api_config:
            try:
                user_config = self._load_user_config()
                active_preset = user_config.get('active_preset', '')
                
                if active_preset:
                    # Cargar preset YAML para obtener lm_api_config
                    preset_file = user_config.get('arg_config', '').replace('-instruct-', '-preset-')
                    if preset_file.endswith('.yaml'):
                        from config.settings import PRESETS_DIR
                        preset_path = os.path.join(PRESETS_DIR, preset_file)
                        
                        if os.path.exists(preset_path):
                            with open(preset_path, 'r', encoding='utf-8') as f:
                                if YAML_AVAILABLE:
                                    preset_data = yaml.safe_load(f) or {}
                                    preset_api_config = preset_data.get('lm_api_config', {})
                                    
                                    self.logger.info(f"🔧 Cargando configuración API desde preset: {preset_file}")
                                    self.logger.info(f"🔧 Preset API config: {preset_api_config}")
                                
            except Exception as e:
                self.logger.warning(f"Error cargando configuración de preset: {e}")
        
        # FUSIÓN: preset override prompt
        if preset_api_config:
            self.logger.info(f"🔧 FUSIONANDO configuración API:")
            self.logger.info(f"   📄 Prompt (LM_API): {merged_config}")  
            self.logger.info(f"   ⚙️  Preset (lm_api_config): {preset_api_config}")
            
            # Preset override prompt
            merged_config.update(preset_api_config)
            
            self.logger.info(f"   ✅ Resultado fusionado: {merged_config}")
        else:
            self.logger.info(f"🔧 Solo usando configuración del prompt (sin preset API config)")
        
        return merged_config

    def _call_lm_studio_batch(self, batch: List[Tuple[str, str]], 
                             prompt_config: Dict[str, Any], lm_config: Dict[str, Any],
                             timeout: int) -> Dict[str, str]:
        """Llama a LM Studio para traducir un lote de texto"""
        
        from app.services.user_config import UserConfigService
        lm_url = lm_config.get('url', UserConfigService.get_lm_studio_url())
        lm_model = lm_config.get('model', '') or 'gpt-3.5-turbo'  # Mejor fallback que gpt-neo
        compat = lm_config.get('compat', 'auto')
        
        logging.info(f"🔄 Intentando cargar modelo desde orquestador: {lm_model}")
        logging.info(f"LM Config completo recibido: {lm_config}")
        
        # Preparar payload
        items = [{"id": segment_id, "en": text} for segment_id, text in batch]
        json_content = json.dumps(items, ensure_ascii=False)
        
        # Headers
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("LMSTUDIO_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Configuración de API - Ya fusionada en translate_file()
        api_config = prompt_config.get("LM_API", {})
        lm_instructions = prompt_config.get("LM_INSTRUCTIONS", "")
        
        # NUEVO: Obtener campo SYSTEM separado si existe
        system_message = prompt_config.get("SYSTEM", "").strip()
        if system_message:
            print(f"🔧 [Orquestador] Usando campo SYSTEM separado para role='system'")
        else:
            print(f"🔧 [Orquestador] Sin campo SYSTEM, usando LM_INSTRUCTIONS para role='system'")
        
        try:
            if compat == "chat" or compat == "auto":
                response = self._call_chat_completions(
                    lm_url, lm_model, system_message, lm_instructions, json_content, 
                    api_config, headers, timeout
                )
            else:
                response = self._call_completions(
                    lm_url, lm_model, system_message, lm_instructions, json_content,
                    api_config, headers, timeout
                )
            
            return self._parse_lm_response(response, batch)
            
        except Exception as e:
            self.logger.error(f"Error en llamada a LM Studio: {e}")
            return {}
    
    def _call_chat_completions(self, url: str, model: str, system_msg: str, 
                              instructions: str, content: str, api_config: Dict, 
                              headers: Dict, timeout: int) -> str:
        """Llama al endpoint /chat/completions"""
        
        chat_url = f"{url.rstrip('/')}/chat/completions"
        supports_system = api_config.get("supports_system", True)
        
        # Determinar qué usar para el rol system
        if system_msg:
            # Si hay campo SYSTEM, usar ese para role="system"
            actual_system_content = system_msg
            # Las instrucciones van en el contenido del user
            actual_user_content = instructions + "\n\n" if instructions else ""
        else:
            # Fallback: usar instrucciones para role="system"
            actual_system_content = instructions
            actual_user_content = ""
        
        if supports_system:
            messages = [
                {"role": "system", "content": actual_system_content},
                {"role": "user", "content": actual_user_content + content}
            ]
        else:
            messages = [
                {"role": "user", "content": actual_system_content + "\n\n" + actual_user_content + content}
            ]
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": api_config.get("temperature", 0.2),
            "top_p": api_config.get("top_p", 0.9),
            "max_tokens": api_config.get("max_tokens", 2048),
            "stop": api_config.get("stop", ["</s>", "<|eot_id|>"])
        }
        
        # Parámetros opcionales
        if "top_k" in api_config:
            payload["top_k"] = api_config["top_k"]
        if "repetition_penalty" in api_config:
            payload["repetition_penalty"] = api_config["repetition_penalty"]
        
        response = self.http_session.post(chat_url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    def _call_completions(self, url: str, model: str, system_msg: str,
                         instructions: str, content: str, api_config: Dict, 
                         headers: Dict, timeout: int) -> str:
        """Llama al endpoint /completions"""
        
        comp_url = f"{url.rstrip('/')}/completions"
        
        # Determinar qué usar para el prompt del sistema
        if system_msg:
            # Si hay campo SYSTEM, usar ese como base del sistema
            system_content = system_msg
            user_content = instructions + "\n\n" if instructions else ""
        else:
            # Fallback: usar instrucciones como sistema
            system_content = instructions
            user_content = ""
        
        # Construir prompt según el modelo
        prompt = self._build_prompt_for_model(model, system_content, user_content + content)
        
        payload = {
            "model": model,
            "prompt": prompt,
            "temperature": api_config.get("temperature", 0.2),
            "top_p": api_config.get("top_p", 0.9),
            "max_tokens": api_config.get("max_tokens", 2048),
            "stop": api_config.get("stop", ["</s>", "<|eot_id|>"])
        }
        
        # Parámetros opcionales
        if "top_k" in api_config:
            payload["top_k"] = api_config["top_k"]
        if "repetition_penalty" in api_config:
            payload["repetition_penalty"] = api_config["repetition_penalty"]
        
        response = self.http_session.post(comp_url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        return response.json()["choices"][0].get("text", "")
    
    def _build_prompt_for_model(self, model: str, system_text: str, user_text: str) -> str:
        """Construye el prompt según el modelo"""
        model_lower = (model or "").lower()
        
        if "qwen" in model_lower:
            # ChatML para Qwen
            return (
                f"<|im_start|>system\n{system_text}\n<|im_end|>\n"
                f"<|im_start|>user\n{user_text}\n<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
        else:
            # Llama-3 por defecto
            BOS = "<|begin_of_text|>"
            EOT = "<|eot_id|>"
            S = "<|start_header_id|>"
            E = "<|end_header_id|>"
            
            sys = f"{S}system{E}\n{system_text}{EOT}"
            usr = f"{S}user{E}\n{user_text}{EOT}"
            asst = f"{S}assistant{E}\n"
            
            return f"{BOS}{sys}{usr}{asst}"
    
    def _parse_lm_response(self, response: str, batch: List[Tuple[str, str]]) -> Dict[str, str]:
        """Parsea la respuesta del modelo de lenguaje"""
        
        # Buscar JSON en la respuesta
        fence_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        clean_response = fence_match.group(1).strip() if fence_match else response.strip()
        
        try:
            parsed = json.loads(clean_response)
            
            results = {}
            
            if isinstance(parsed, dict) and "data" in parsed:
                items = parsed["data"]
            elif isinstance(parsed, list):
                items = parsed
            elif isinstance(parsed, dict) and "id" in parsed and "es" in parsed:
                items = [parsed]
            else:
                self.logger.warning("Formato de respuesta JSON inesperado")
                return {}
            
            for item in items:
                item_id = item.get("id")
                es_text = item.get("es") or item.get("text")
                
                if item_id and es_text:
                    results[item_id] = str(es_text)
            
            return results
            
        except json.JSONDecodeError:
            self.logger.error(f"Error parseando JSON: {clean_response[:500]}")
            return {}
    
    def _apply_postprocessing(self, text: str, config: Dict[str, Any]) -> str:
        """Aplica post-procesamiento al texto traducido"""
        
        # Aplicar reglas de post-procesamiento
        text = self._apply_post_rules(text, config)
        
        # Proteger términos técnicos
        protected_terms = set(
            config.get("PROTECT_WORDS", []) +
            config.get("NO_TRANSLATE_TERMS", []) +
            config.get("TECHNICAL_TERMS_NO_TRASLATE", [])
        )
        text = self._protect_terms(text, protected_terms)
        
        # Limpiar espacios
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _generate_output_file(self, original_text: str, segments: List['TranslationSegment'],
                             output_dir: str, input_path: str, config: Dict[str, Any]) -> str:
        """Genera el archivo .lua traducido final"""
        
        # Crear mapeo de IDs a traducciones
        id_to_translation = {}
        for segment in segments:
            if hasattr(segment, 'es') and segment.es:
                escaped_translation = self._escape_for_lua(segment.es)
                id_to_translation[segment.id] = f"{segment.leading_ws}{escaped_translation}"
        
        # Reemplazar IDs por traducciones
        def replace_ids(match):
            pre, key, value, post = match.groups()
            
            new_value = value
            for segment_id, translation in id_to_translation.items():
                new_value = new_value.replace(segment_id, translation)
            
            return pre + new_value + post
        
        translated_text = self.entry_regex.sub(replace_ids, original_text)
        
        # Aplicar post-procesamiento final
        translated_text = self._apply_post_rules(translated_text, config)
        
        # Generar archivo de salida
        base_name = os.path.basename(input_path).rsplit('.', 1)[0]
        output_file = os.path.join(output_dir, f"{base_name}.translated.lua")
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            f.write(translated_text)
        
        self.logger.info(f"Archivo traducido generado: {output_file}")
        return output_file
    
    def _generate_auxiliary_files(self, segments: List['TranslationSegment'], 
                                 output_dir: str, input_path: str, session_id: str):
        """Genera archivos auxiliares (JSONL, estadísticas, etc.)"""
        
        base_name = os.path.basename(input_path).rsplit('.', 1)[0]
        
        # Archivo JSONL con traducciones
        jsonl_file = os.path.join(output_dir, f"{base_name}.translations.jsonl")
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            for segment in segments:
                if segment.clean_for_model.strip():
                    obj = {
                        "id": segment.id,
                        "key": segment.key,
                        "en": segment.clean_for_model,
                        "es": getattr(segment, 'es', segment.clean_for_model)
                    }
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        
        # Archivo de estadísticas
        stats_file = os.path.join(output_dir, f"{base_name}.stats.json")
        stats = {
            "session_id": session_id,
            "input_file": input_path,
            "total_segments": len(segments),
            "translated_segments": len([s for s in segments if hasattr(s, 'es') and s.es]),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # Métodos auxiliares (versiones simplificadas de los originales)
    
    def _key_is_target(self, key: str, keys_filter: Optional[List[str]], config: Dict[str, Any]) -> bool:
        """Determina si una clave debe ser traducida"""
        if keys_filter:
            if "ALL" not in [k.strip().upper() for k in keys_filter]:
                if not any(kf in key for kf in keys_filter):
                    return False
        
        target_prefixes = config.get("TARGET_PREFIXES", [])
        exclude_prefixes = config.get("EXCLUDE_PREFIXES", [])
        
        if target_prefixes and not any(key.startswith(p) for p in target_prefixes):
            return False
        
        if exclude_prefixes and any(key.startswith(p) for p in exclude_prefixes):
            return False
        
        return True
    
    def _apply_glossary_rules(self, text: str, config: Dict[str, Any]) -> str:
        """Aplica reglas del glosario OTAN"""
        glossary = config.get("GLOSSARY_OTAN", {})
        for en_term, es_translation in glossary.items():
            pattern = r"\b" + re.escape(en_term) + r"\b"
            text = re.sub(pattern, es_translation, text, flags=re.IGNORECASE)
        return text
    
    def _apply_phraseology_rules(self, text: str, config: Dict[str, Any]) -> str:
        """Aplica reglas de fraseología"""
        for rule in config.get("PHRASEOLOGY_RULES", []):
            pattern = rule.get("pattern")
            replacement = rule.get("replacement", "")
            if pattern:
                flags = self._build_rule_flags(rule)
                text = re.sub(pattern, replacement, text, flags=flags)
        return text
    
    def _apply_post_rules(self, text: str, config: Dict[str, Any]) -> str:
        """Aplica reglas de post-procesamiento"""
        for rule in config.get("POST_RULES", []):
            pattern = rule.get("pattern")
            replacement = rule.get("replacement", "")
            if pattern:
                flags = self._build_rule_flags(rule)
                text = re.sub(pattern, replacement, text, flags=flags)
        return text
    
    def _build_rule_flags(self, rule: Dict[str, Any]) -> int:
        """Construye flags de regex desde configuración"""
        flags = 0
        for flag in rule.get("flags", []):
            flag = str(flag).upper().strip()
            if flag in ("I", "IGNORECASE"):
                flags |= re.IGNORECASE
            elif flag in ("M", "MULTILINE"):
                flags |= re.MULTILINE
            elif flag in ("S", "DOTALL"):
                flags |= re.DOTALL
        return flags
    
    def _protect_terms(self, text: str, terms: set) -> str:
        """Protege términos específicos de ser modificados"""
        if not terms:
            return text
        
        for term in sorted(terms, key=len, reverse=True):
            pattern = rf'(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])'
            text = re.sub(pattern, term, text, flags=re.IGNORECASE)
        
        return text
    
    def _escape_for_lua(self, text: str) -> str:
        """Escapa texto para formato Lua"""
        text = text.replace('\\', '\\\\')
        text = text.replace('"', r'\"')
        return text
    
    def _load_cache(self, cache_path: str) -> Dict[str, str]:
        """Carga caché de traducciones"""
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_cache(self, cache: Dict[str, str], cache_path: str):
        """Guarda caché de traducciones"""
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"Error guardando caché: {e}")
    
    def _filter_system_content(self, content: str) -> str:
        """Filtrar contenido del sistema que algunos modelos incluyen incorrectamente en la respuesta"""
        
        # Patrones comunes de contenido del sistema que aparecen en respuestas incorrectas
        system_patterns = [
            # Patrón EXACTO del problema reportado
            r'"system\s*\\n\s*Contexto especializado:\s*Eres el traductor oficial del programa DCS World en español para el Ejército del Aire y del Espacio de España\.\s*Tu trabajo requiere máxima precisión pues las traducciones se usan en entrenamiento militar real\.\s*Tienes acceso completo a glosarios oficiales OTAN en español, manuales técnicos de aeronaves en español, procedimientos operacionales estándar españoles y una base de datos terminológica militar actualizada\.\s*Aplica el máximo nivel de expertise y precisión técnica"[,\s]*',
            
            # Variaciones del patrón específico
            r'system\s*\\n\s*Contexto especializado:.*?máxima precisión técnica["\s]*,?\s*',
            r'"system.*?Contexto especializado:.*?máxima precisión técnica.*?"[,\s]*',
            r'system\s*\n\s*Contexto especializado:.*?máxima precisión técnica[,\s]*',
            
            # Patrones generales de contenido del sistema
            r'system\s*\\n.*?traductor oficial.*?DCS World.*?España[^"]*[",\s]*',
            r'"system":\s*"[^"]*traductor oficial[^"]*DCS World[^"]*"[,\s]*',
            r'system\s*\n.*?Eres el traductor oficial.*?["\s]*,?\s*',
            
            # Patrones de instrucciones del sistema
            r'system\s*\\n.*?entrenamiento militar real.*?["\s]*,?\s*',
            r'system\s*\\n.*?glosarios oficiales OTAN.*?["\s]*,?\s*',
            r'"system":\s*"[^"]*entrenamiento militar real[^"]*"[,\s]*',
            
            # Patrones más amplios para capturar variaciones
            r'system\s*\\n.*?Ejército del Aire y del Espacio.*?[",\s]*',
            r'system\s*\\n.*?base de datos terminológica militar.*?[",\s]*',
            r'system\s*\\n.*?expertise y precisión técnica.*?[",\s]*',
            
            # Limpiar inicio de respuesta con contenido del sistema
            r'^["\s]*system["\s]*\\n[^,]*?,?\s*',
            r'^system\s*\\n.*?\s*,\s*',
            
            # NUEVOS PATRONES PARA EXPLICACIONES Y TEXTO ADICIONAL
            # Explicaciones comunes que añaden los modelos
            r'(?:Aquí está|He aquí|La traducción es|El resultado es|A continuación).*?:\s*',
            r'(?:```json\s*|```\s*)',  # Marcadores de código
            r'(?:Explicación|Nota|Comentario|Observación).*?:\s*.*?(?:\n|$)',
            r'(?:Como se puede ver|En resumen|Finalmente|Por lo tanto).*?(?:\n|$)',
            r'(?:Esta traducción|La siguiente traducción|He traducido).*?(?:\n|$)',
            r'(?:Mantén|Mantengo|Mantiene).*?estructura.*?(?:\n|$)',
            r'(?:Términos técnicos|Traducción militar|Contexto militar).*?(?:\n|$)',
            
            # Patrones al final de la respuesta
            r'\s*(?:```|</s>|<\|eot_id\|>).*$',
            r'\s*(?:Espero|Esto debería|Cualquier duda).*$',
            
            # Texto antes del JSON
            r'^.*?(?=\s*\[)',  # Todo antes del primer [
        ]
        
        original_content = content
        for pattern in system_patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Si se removió contenido, registrar para debugging
        if len(content) != len(original_content):
            removed_chars = len(original_content) - len(content)
            self.logger.info(f"Filtrado contenido del sistema: removidos {removed_chars} caracteres")
            self.logger.debug(f"Contenido original: {original_content[:200]}...")
            self.logger.debug(f"Contenido filtrado: {content[:200]}...")
        
        # Limpiar espacios y comas sobrantes al inicio
        content = re.sub(r'^[,\s]+', '', content.strip())
        
        return content

    def _extract_pure_json(self, content: str) -> str:
        """Extrae únicamente el JSON válido de la respuesta, eliminando cualquier texto adicional"""
        
        # Limpiar texto explicativo común al inicio
        explanatory_patterns = [
            r'^.*?(?:aquí está|he aquí|la traducción es|el resultado es|a continuación).*?:\s*',
            r'^.*?(?:```json|```)\s*',
            r'^.*?(?:traducido|traducción).*?:\s*',
            r'^.*?(?:json|respuesta).*?:\s*',
        ]
        
        for pattern in explanatory_patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Buscar JSON array o object válido
        import json
        
        # Intentar encontrar un array JSON válido
        array_matches = re.finditer(r'\[[\s\S]*?\]', content)
        for match in array_matches:
            candidate = match.group(0)
            try:
                json.loads(candidate)
                self.logger.debug(f"JSON array válido encontrado: {candidate[:100]}...")
                return candidate
            except json.JSONDecodeError:
                continue
        
        # Si no se encuentra array, buscar objeto JSON válido
        object_matches = re.finditer(r'\{[\s\S]*?\}', content)
        for match in object_matches:
            candidate = match.group(0)
            try:
                json.loads(candidate)
                self.logger.debug(f"JSON object válido encontrado: {candidate[:100]}...")
                return candidate
            except json.JSONDecodeError:
                continue
        
        # Si no se encuentra JSON válido, intentar limpiar más agresivamente
        # Buscar contenido entre las primeras llaves o corchetes
        bracket_match = re.search(r'[\[\{].*[\]\}]', content, re.DOTALL)
        if bracket_match:
            candidate = bracket_match.group(0)
            try:
                json.loads(candidate)
                self.logger.debug(f"JSON encontrado con limpieza agresiva: {candidate[:100]}...")
                return candidate
            except json.JSONDecodeError:
                pass
        
        # Último recurso: devolver contenido original limpio
        clean_content = re.sub(r'^[^[\{]*', '', content)  # Quitar todo antes del primer [ o {
        clean_content = re.sub(r'[^}\]]*$', '', clean_content)  # Quitar todo después del último } o ]
        
        self.logger.warning(f"No se pudo extraer JSON válido, devolviendo contenido limpio: {clean_content[:100]}...")
        return clean_content.strip()


class TranslationSegment:
    """Representa un segmento de texto para traducir"""
    
    def __init__(self, key: str, index: int, raw_seg: str, lb: str, protect_brackets: bool = True):
        self.key = key
        self.index = index
        self.raw_seg = raw_seg
        self.lb = lb
        self.protect_brackets = protect_brackets
        
        # Procesar whitespace inicial
        ws_match = re.match(r'^(?P<ws>\s*)(?P<text>.*)$', raw_seg, re.DOTALL)
        self.leading_ws = ws_match.group("ws") if ws_match else ""
        text_without_ws = ws_match.group("text") if ws_match else raw_seg
        
        # Separar puntuación final
        punct_match = re.match(r'^(?P<core>.*?)(?P<punct>[\s\.\!\?\,;:\u2026]*)$', text_without_ws, re.DOTALL)
        self.core = punct_match.group("core")
        self.punct = punct_match.group("punct")
        
        # Protección de corchetes
        self.br_tokens = {}
        if self.protect_brackets:
            # Usar regex para corchetes comunes
            bracket_patterns = [
                r'\[[^\]]*\]',          # [texto]
                r'\{[^}]*\}',           # {texto}
                r'<[^>]*>',             # <texto>
                r'\([^)]*\)',           # (texto)
            ]
            combined_pattern = '|'.join(f'({pattern})' for pattern in bracket_patterns)
            bracket_regex = re.compile(combined_pattern)
            self.clean_for_model = self._protect_brackets(self.core, bracket_regex)
        else:
            self.clean_for_model = self.core
        
        # Generar ID único
        src_for_hash = f"{self.key}#{self.index}#{self.core.strip()}"
        hash_obj = hashlib.sha1(src_for_hash.encode("utf-8"))
        self.id = f"id_{hash_obj.hexdigest()[:16]}"
        
        # Traducción (se establece durante el proceso)
        self.es = None
    
    def _protect_brackets(self, text: str, bracket_regex) -> str:
        """Protege contenido entre corchetes reemplazándolos por placeholders"""
        def replace_bracket(match):
            token = f"BR_{len(self.br_tokens) + 1}"
            self.br_tokens[token] = match.group(0)
            return token
        return bracket_regex.sub(replace_bracket, text)