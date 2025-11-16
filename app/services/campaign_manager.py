#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio para gestión completa de campañas traducidas, empaquetadas y desplegadas
Basado en el directorio app/data/traducciones y integración con DCS
"""
import os
import json
import hashlib
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict

from app.services.centralized_cache import CentralizedCache
from config.settings import BASE_DIR


@dataclass
class MissionStatus:
    """Estado completo de una misión"""
    name: str
    campaign: str
    path: str
    
    # Estados de proceso
    has_out_lua: bool
    has_finalizado: bool
    has_backup: bool
    is_deployed: bool
    
    # Metadatos
    finalizado_hash: Optional[str]
    deployed_hash: Optional[str]
    last_modified: str
    size_mb: float
    
    # Estado de traducción
    translation_complete: bool
    lua_files_count: int
    
    # Estado de deployment
    deploy_path: Optional[str]
    backup_path: Optional[str]


@dataclass
class CampaignSummary:
    """Resumen de estado de una campaña"""
    name: str
    path: str
    total_missions: int
    translated_missions: int
    finalized_missions: int
    deployed_missions: int
    backed_up_missions: int
    
    # Metadatos
    total_size_mb: float
    last_activity: str
    creation_date: str


class CampaignManager:
    """
    Gestor completo de campañas traducidas
    Maneja estados, deployment, cache y operaciones CRUD
    """
    
    def __init__(self, translations_dir: str = None, dcs_root: str = None):
        """
        Inicializar el gestor de campañas
        
        Args:
            translations_dir: Directorio de traducciones (default: app/data/traducciones)
            dcs_root: Directorio raíz de DCS (se obtiene de config si no se especifica)
        """
        if translations_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            translations_dir = os.path.join(base_dir, "data", "traducciones")
        
        self.translations_dir = Path(translations_dir)
        self.dcs_root = Path(dcs_root) if dcs_root else None
        self.cache = CentralizedCache()
        self.logger = logging.getLogger(__name__)
        
        # Crear directorio si no existe
        self.translations_dir.mkdir(parents=True, exist_ok=True)
    
    def get_campaigns_summary(self) -> List[CampaignSummary]:
        """
        Obtener resumen de todas las campañas
        
        Returns:
            Lista de resúmenes de campañas
        """
        campaigns = []
        
        if not self.translations_dir.exists():
            return campaigns
        
        for campaign_dir in self.translations_dir.iterdir():
            if campaign_dir.is_dir():
                try:
                    summary = self._analyze_campaign(campaign_dir)
                    campaigns.append(summary)
                except Exception as e:
                    self.logger.error(f"Error analizando campaña {campaign_dir.name}: {e}")
        
        # Ordenar por última actividad (más reciente primero)
        campaigns.sort(key=lambda x: x.last_activity, reverse=True)
        return campaigns
    
    def get_campaign_missions(self, campaign_name: str) -> List[MissionStatus]:
        """
        Obtener estado detallado de todas las misiones de una campaña
        
        Args:
            campaign_name: Nombre de la campaña
            
        Returns:
            Lista de estados de misiones
        """
        campaign_path = self.translations_dir / campaign_name
        if not campaign_path.exists():
            return []
        
        missions = []
        for mission_dir in campaign_path.iterdir():
            if mission_dir.is_dir():
                try:
                    status = self._analyze_mission(mission_dir, campaign_name)
                    missions.append(status)
                except Exception as e:
                    self.logger.error(f"Error analizando misión {mission_dir.name}: {e}")
        
        # Función para ordenación natural (numérica)
        import re
        def natural_sort_key(mission):
            """
            Crear una clave de ordenación natural para nombres de misión.
            Convierte números en nombres a enteros para ordenación correcta.
            Ej: F5-E-C2 viene antes que F5-E-C10
            """
            name = mission.name
            # Separar letras y números
            parts = re.split(r'(\d+)', name.lower())
            # Convertir partes numéricas a enteros
            for i in range(len(parts)):
                if parts[i].isdigit():
                    parts[i] = int(parts[i])
            return parts
        
        # Ordenar por nombre de misión con ordenación natural
        missions.sort(key=natural_sort_key)
        return missions
    
    def delete_mission(self, campaign_name: str, mission_name: str) -> bool:
        """
        Eliminar archivos de traducción de una misión pero preservar el backup original
        
        Args:
            campaign_name: Nombre de la campaña
            mission_name: Nombre de la misión
            
        Returns:
            True si se eliminó correctamente
        """
        mission_path = self.translations_dir / campaign_name / mission_name
        
        if not mission_path.exists():
            self.logger.warning(f"Misión no encontrada: {mission_path}")
            return False
        
        try:
            files_removed = 0
            folders_removed = 0
            backup_preserved = False
            
            # Listar todos los elementos en la carpeta de la misión
            for item in mission_path.iterdir():
                if item.name == 'backup':
                    # PRESERVAR la carpeta backup - NO ELIMINAR
                    backup_preserved = True
                    self.logger.info(f"Backup preservado: {item}")
                    continue
                
                # Eliminar todo lo demás (extracted, out_lua, finalizado, etc.)
                if item.is_file():
                    item.unlink()
                    files_removed += 1
                    self.logger.debug(f"Archivo eliminado: {item}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    folders_removed += 1
                    self.logger.debug(f"Carpeta eliminada: {item}")
            
            # Si no hay backup, advertir al usuario
            if not backup_preserved:
                self.logger.warning(f"ADVERTENCIA: No se encontró backup para {mission_name}. La misión se ha eliminado completamente.")
            
            self.logger.info(f"Traducción eliminada para {mission_name}: {files_removed} archivos, {folders_removed} carpetas removidas. Backup preservado: {backup_preserved}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error eliminando traducción de misión {mission_path}: {e}")
            return False

    def delete_mission_completely(self, campaign_name: str, mission_name: str) -> bool:
        """
        Eliminar completamente una misión incluyendo el backup (USAR CON PRECAUCIÓN)
        
        Args:
            campaign_name: Nombre de la campaña
            mission_name: Nombre de la misión
            
        Returns:
            True si se eliminó correctamente
        """
        mission_path = self.translations_dir / campaign_name / mission_name
        
        if not mission_path.exists():
            self.logger.warning(f"Misión no encontrada: {mission_path}")
            return False
        
        try:
            shutil.rmtree(mission_path)
            self.logger.info(f"Misión eliminada completamente (incluyendo backup): {mission_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error eliminando misión completamente {mission_path}: {e}")
            return False
    
    def redeploy_from_backup(self, campaign_name: str, mission_name: str, target_dcs_path: str) -> bool:
        """
        Redesplegar una misión desde backup a su ubicación original en DCS
        
        Args:
            campaign_name: Nombre de la campaña
            mission_name: Nombre de la misión
            target_dcs_path: Ruta objetivo en DCS
            
        Returns:
            True si se redesplegó correctamente
        """
        mission_path = self.translations_dir / campaign_name / mission_name
        backup_dir = mission_path / "backup"
        
        if not backup_dir.exists():
            self.logger.error(f"No hay backup disponible para {mission_name}")
            return False
        
        # Buscar archivo .miz en backup
        backup_files = list(backup_dir.glob("*.miz"))
        if not backup_files:
            self.logger.error(f"No se encontró archivo .miz en backup de {mission_name}")
            return False
        
        backup_file = backup_files[0]  # Tomar el primero
        target_path = Path(target_dcs_path) / backup_file.name
        
        try:
            # Crear directorio objetivo si no existe
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copiar desde backup
            shutil.copy2(backup_file, target_path)
            self.logger.info(f"Misión redesplegada desde backup: {backup_file} -> {target_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error redesplegando desde backup: {e}")
            return False
    
    def get_cache_info(self, campaign_name: str = None) -> Dict:
        """
        Obtener información del cache (global y local)
        
        Args:
            campaign_name: Si se especifica, filtrar por campaña
            
        Returns:
            Información del cache
        """
        global_cache = self.cache.load_cache()
        
        if campaign_name:
            # Filtrar entradas por campaña
            filtered_cache = {k: v for k, v in global_cache.items() 
                            if campaign_name.lower() in k.lower()}
        else:
            filtered_cache = global_cache
        
        # Limpiar claves duplicadas (case-insensitive) para evitar problemas de JSON
        cleaned_cache = {}
        seen_keys_lower = set()
        
        for key, value in filtered_cache.items():
            key_lower = key.lower()
            if key_lower not in seen_keys_lower:
                cleaned_cache[key] = value
                seen_keys_lower.add(key_lower)
            else:
                self.logger.warning(f"Clave duplicada ignorada en cache: {key}")
        
        return {
            'total_entries': len(cleaned_cache),
            'global_entries': len(global_cache),
            'cache_file': str(self.cache.cache_file),
            'entries': cleaned_cache,
            'duplicates_removed': len(filtered_cache) - len(cleaned_cache)
        }
    
    def compact_cache(self) -> Dict:
        """
        Compactar el cache eliminando entradas duplicadas y optimizando
        
        Returns:
            Estadísticas de la compactación
        """
        try:
            original_cache = self.cache.load_cache()
            original_count = len(original_cache)
            
            # Eliminar entradas duplicadas por valor
            seen_values = set()
            compacted_cache = {}
            
            for key, value in original_cache.items():
                if value not in seen_values:
                    compacted_cache[key] = value
                    seen_values.add(value)
            
            # Guardar cache compactado
            self.cache._save_cache(compacted_cache)
            
            new_count = len(compacted_cache)
            removed_count = original_count - new_count
            
            self.logger.info(f"Cache compactado: {removed_count} entradas eliminadas")
            
            return {
                'original_entries': original_count,
                'compacted_entries': new_count,
                'removed_entries': removed_count,
                'space_saved_percent': round((removed_count / original_count) * 100, 2) if original_count > 0 else 0
            }
        except Exception as e:
            self.logger.error(f"Error compactando cache: {e}")
            return {'error': str(e)}
    
    def verify_deployment_hashes(self, campaign_name: str, dcs_campaign_path: str) -> Dict:
        """
        Verificar hashes de misiones desplegadas vs finalizadas
        
        Args:
            campaign_name: Nombre de la campaña
            dcs_campaign_path: Ruta de la campaña en DCS
            
        Returns:
            Reporte de verificación de hashes
        """
        missions = self.get_campaign_missions(campaign_name)
        dcs_path = Path(dcs_campaign_path)
        
        report = {
            'campaign': campaign_name,
            'total_missions': len(missions),
            'verified_missions': 0,
            'mismatched_missions': 0,
            'missing_missions': 0,
            'details': []
        }
        
        for mission in missions:
            if not mission.has_finalizado:
                continue
            
            # Buscar archivo en DCS
            dcs_mission_file = dcs_path / f"{mission.name}.miz"
            
            detail = {
                'mission': mission.name,
                'finalizado_hash': mission.finalizado_hash,
                'deployed_hash': None,
                'status': 'missing'
            }
            
            if dcs_mission_file.exists():
                try:
                    deployed_hash = self._calculate_file_hash(dcs_mission_file)
                    detail['deployed_hash'] = deployed_hash
                    
                    if deployed_hash == mission.finalizado_hash:
                        detail['status'] = 'verified'
                        report['verified_missions'] += 1
                    else:
                        detail['status'] = 'mismatched'
                        report['mismatched_missions'] += 1
                except Exception as e:
                    detail['status'] = 'error'
                    detail['error'] = str(e)
            else:
                report['missing_missions'] += 1
            
            report['details'].append(detail)
        
        return report
    
    def _analyze_campaign(self, campaign_path: Path) -> CampaignSummary:
        """Analizar una campaña y generar resumen"""
        missions = list(campaign_path.iterdir())
        mission_dirs = [m for m in missions if m.is_dir()]
        
        total_missions = len(mission_dirs)
        translated = finalized = deployed = backed_up = 0
        total_size = 0
        last_activity = creation_date = datetime.now().isoformat()
        
        for mission_dir in mission_dirs:
            if (mission_dir / "out_lua").exists():
                translated += 1
            if (mission_dir / "finalizado").exists():
                finalized += 1
            if (mission_dir / "backup").exists():
                backed_up += 1
            
            # Verificar si está desplegada usando comparación de hashes
            is_deployed, _, _ = self._detect_deployment_status(mission_dir, campaign_path.name)
            if is_deployed:
                deployed += 1
            
            # Calcular tamaño total
            try:
                for file_path in mission_dir.rglob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
            except Exception:
                pass
        
        # Obtener fechas de última modificación
        try:
            stats = campaign_path.stat()
            creation_date = datetime.fromtimestamp(stats.st_ctime).isoformat()
            last_activity = datetime.fromtimestamp(stats.st_mtime).isoformat()
        except Exception:
            pass
        
        return CampaignSummary(
            name=campaign_path.name,
            path=str(campaign_path),
            total_missions=total_missions,
            translated_missions=translated,
            finalized_missions=finalized,
            deployed_missions=deployed,
            backed_up_missions=backed_up,
            total_size_mb=round(total_size / (1024 * 1024), 2),
            last_activity=last_activity,
            creation_date=creation_date
        )
    
    def _analyze_mission(self, mission_path: Path, campaign_name: str) -> MissionStatus:
        """Analizar una misión específica"""
        name = mission_path.name
        
        # Verificar existencia de directorios clave
        has_out_lua = (mission_path / "out_lua").exists()
        has_finalizado = (mission_path / "finalizado").exists()
        has_backup = (mission_path / "backup").exists()
        
        # Detectar estado de despliegue comparando hashes
        is_deployed, deployed_hash, deploy_path = self._detect_deployment_status(mission_path, campaign_name)
        
        # Calcular hashes
        finalizado_hash = None
        if has_finalizado:
            finalizado_files = list((mission_path / "finalizado").glob("*.miz"))
            if finalizado_files:
                finalizado_hash = self._calculate_file_hash(finalizado_files[0])
        
        # Contar archivos .lua traducidos
        lua_files_count = 0
        if has_out_lua:
            lua_files = list((mission_path / "out_lua").glob("*.translated.lua"))
            lua_files_count = len(lua_files)
        
        # Calcular tamaño
        size = 0
        try:
            for file_path in mission_path.rglob("*"):
                if file_path.is_file():
                    size += file_path.stat().st_size
        except Exception:
            pass
        
        # Obtener fecha de modificación
        try:
            last_modified = datetime.fromtimestamp(mission_path.stat().st_mtime).isoformat()
        except Exception:
            last_modified = datetime.now().isoformat()
        
        return MissionStatus(
            name=name,
            campaign=campaign_name,
            path=str(mission_path),
            has_out_lua=has_out_lua,
            has_finalizado=has_finalizado,
            has_backup=has_backup,
            is_deployed=is_deployed,
            finalizado_hash=finalizado_hash,
            deployed_hash=deployed_hash,
            last_modified=last_modified,
            size_mb=round(size / (1024 * 1024), 2),
            translation_complete=has_out_lua and lua_files_count > 0,
            lua_files_count=lua_files_count,
            deploy_path=deploy_path,
            backup_path=str(mission_path / "backup") if has_backup else None
        )
    
    def _normalize_mission_filename(self, filename: str) -> str:
        """
        Normaliza nombres de archivos de misión para que coincidan entre sistema y DCS
        """
        # Convertir guiones bajos a espacios o guiones normales
        normalized = filename.replace('_-_', ' - ')  # F-5E_-_BFM04 -> F-5E - BFM04
        normalized = normalized.replace('_', ' ')    # Cualquier otro guión bajo a espacio
        
        return normalized

    def _normalize_campaign_name(self, name: str) -> str:
        """
        Normaliza nombres de campaña para que coincidan entre sistema y DCS
        usando transformación automática en lugar de mapeos hardcodeados
        
        Esta función hace el proceso INVERSO al mapeo del orquestador:
        - El orquestador convierte: "F-5E Black Sea Resolve '79" → "F-5E_Black_Sea_Resolve__79"
        - Esta función convierte: "F-5E_Black_Sea_Resolve__79" → "F-5E Black Sea Resolve '79"
        """
        import re
        
        # Proceso inverso al mapeo del orquestador
        normalized = name
        
        # 1. Casos específicos que necesitan manejo especial ANTES de la transformación general
        special_replacements = [
            # F/A-18C (barra especial)
            ('F_A-18C', 'F/A-18C'),
            # Dos puntos para títulos especiales
            ('__Special_Edition', ': Special Edition'),
            ('__Special', ': Special'),
        ]
        
        for old_pattern, new_pattern in special_replacements:
            normalized = normalized.replace(old_pattern, new_pattern)
        
        # 2. Convertir doble guión bajo a comillas simples con espacio antes
        # Usar regex para capturar el contexto y añadir espacio si es necesario
        normalized = re.sub(r'([a-zA-Z\d])__(\d)', r"\1 '\2", normalized)  # Resolve__79 → Resolve '79
        normalized = re.sub(r'([a-zA-Z\d])__([a-zA-Z])', r"\1 '\2", normalized)  # word__text → word 'text
        
        # 3. Convertir guiones bajos restantes a espacios
        normalized = normalized.replace('_', ' ')
        
        # 4. Limpiar espacios múltiples
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 5. Limpiar espacios al inicio y final
        normalized = normalized.strip()
        
        self.logger.debug(f"Mapeo campaña: '{name}' -> '{normalized}'")
        
        return normalized

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcular hash SHA256 de un archivo"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculando hash de {file_path}: {e}")
            return ""
    
    def _detect_deployment_status(self, mission_path: Path, campaign_name: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Detectar si una misión está desplegada comparando hashes
        
        Args:
            mission_path: Ruta de la misión en traducciones
            campaign_name: Nombre de la campaña
            
        Returns:
            Tuple[is_deployed, deployed_hash, deploy_path]
        """
        mission_name = mission_path.name
        
        # Buscar archivo .miz en backup (versión original)
        backup_path = mission_path / "backup"
        if not backup_path.exists():
            self.logger.debug(f"No hay backup para {campaign_name}/{mission_name}")
            return False, None, None
        
        backup_miz_files = list(backup_path.glob("*.miz"))
        if not backup_miz_files:
            self.logger.debug(f"No se encontró archivo .miz en backup de {campaign_name}/{mission_name}")
            return False, None, None
        
        backup_hash = self._calculate_file_hash(backup_miz_files[0])
        if not backup_hash:
            self.logger.warning(f"No se pudo calcular hash del backup de {campaign_name}/{mission_name}")
            return False, None, None
        
        self.logger.debug(f"Hash backup {campaign_name}/{mission_name}: {backup_hash[:8]}...")
        
        # Buscar en posibles ubicaciones de DCS
        possible_dcs_paths = self._get_possible_dcs_paths()
        self.logger.debug(f"Buscando en {len(possible_dcs_paths)} rutas DCS posibles")
        
        # Normalizar nombre de campaña para búsqueda en DCS
        normalized_campaign_name = self._normalize_campaign_name(campaign_name)
        self.logger.debug(f"Campaña original: {campaign_name} -> Normalizada: {normalized_campaign_name}")

        for dcs_base_path in possible_dcs_paths:
            self.logger.debug(f"Verificando ruta DCS: {dcs_base_path}")
            
            campaign_path_in_dcs = dcs_base_path / normalized_campaign_name
            if not campaign_path_in_dcs.exists():
                self.logger.debug(f"Campaña no encontrada en: {campaign_path_in_dcs}")
                continue
            
            self.logger.info(f"✅ Campaña encontrada en DCS: {campaign_path_in_dcs}")
            
            # Buscar archivo .miz en la campaña desplegada
            mission_miz_files = list(campaign_path_in_dcs.glob(f"{mission_name}*.miz"))
            if not mission_miz_files:
                # Buscar con nombre normalizado
                normalized_mission_name = self._normalize_mission_filename(mission_name)
                mission_miz_files = list(campaign_path_in_dcs.glob(f"{normalized_mission_name}*.miz"))
                
                if not mission_miz_files:
                    # También buscar con patrones más flexibles
                    mission_miz_files = list(campaign_path_in_dcs.glob(f"*{normalized_mission_name}*.miz"))
                    if not mission_miz_files:
                        self.logger.debug(f"Misión .miz no encontrada en DCS: {campaign_path_in_dcs}/{normalized_mission_name}")
                        continue
            
            self.logger.info(f"✅ Misión .miz encontrada en DCS: {mission_miz_files[0]}")            # Calcular hash del archivo desplegado
            deployed_hash = self._calculate_file_hash(mission_miz_files[0])
            if not deployed_hash:
                self.logger.warning(f"No se pudo calcular hash del archivo desplegado: {mission_miz_files[0]}")
                continue
            
            self.logger.debug(f"Hash desplegado {campaign_name}/{mission_name}: {deployed_hash[:8]}...")
            
            # Comparar hashes
            if backup_hash != deployed_hash:
                # El hash es diferente = misión traducida está desplegada
                self.logger.info(f"🚀 Misión desplegada detectada: {campaign_name}/{mission_name}")
                self.logger.info(f"   Backup hash: {backup_hash[:8]}...")
                self.logger.info(f"   Deploy hash: {deployed_hash[:8]}...")
                return True, deployed_hash, str(mission_miz_files[0])
            else:
                self.logger.info(f"❌ Misión NO desplegada (hashes iguales): {campaign_name}/{mission_name}")
        
        return False, None, None
    
    def _get_possible_dcs_paths(self) -> List[Path]:
        """
        Obtener posibles rutas donde puede estar instalado DCS
        Escanea automáticamente todas las unidades disponibles
        
        Returns:
            Lista de rutas posibles para campañas DCS
        """
        possible_paths = []
        
        # Detectar automáticamente todas las unidades disponibles
        import string
        available_drives = []
        for drive_letter in string.ascii_uppercase:
            drive_path = f"{drive_letter}:\\"
            if os.path.exists(drive_path):
                available_drives.append(drive_letter)
        
        self.logger.info(f"Unidades detectadas para escaneo DCS: {available_drives}")
        
        # Ubicaciones comunes relativas donde se instala DCS
        common_locations = [
            "Program Files\\Eagle Dynamics\\DCS World",
            "Program Files (x86)\\Eagle Dynamics\\DCS World",
            "Program Files\\Steam\\steamapps\\common\\DCSWorld",
            "Program Files (x86)\\Steam\\steamapps\\common\\DCSWorld",
            "Steam\\steamapps\\common\\DCSWorld",
            "Games\\DCS World",
            "DCS World",
            "Epic Games\\DCSWorld"
        ]
        
        # Subdirectorios donde pueden estar las campañas
        campaign_subdirs = [
            "Mods\\campaigns",
            "Missions\\Campaigns", 
            "Campaigns",
            "UserData\\Missions\\Campaigns"
        ]
        
        # Escanear todas las unidades disponibles
        for drive_letter in available_drives:
            for location in common_locations:
                base_path = Path(f"{drive_letter}:\\{location}")
                
                for subdir in campaign_subdirs:
                    full_path = base_path / subdir
                    if full_path.exists():
                        possible_paths.append(full_path)
                        self.logger.info(f"✅ Ruta DCS encontrada: {full_path}")
                    else:
                        self.logger.debug(f"❌ Ruta DCS no existe: {full_path}")
        
        if not possible_paths:
            self.logger.warning("⚠️ No se encontraron rutas DCS válidas")
        else:
            self.logger.info(f"📁 Total rutas DCS encontradas: {len(possible_paths)}")
        
        # TODO: Leer desde configuración del usuario
        # user_config_path = self.data_dir / "my_config" / "user_config.json"
        # if user_config_path.exists():
        #     with open(user_config_path, 'r') as f:
        #         config = json.load(f)
        #         if 'dcs_campaigns_path' in config:
        #             possible_paths.append(Path(config['dcs_campaigns_path']))
        
        return possible_paths