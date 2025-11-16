"""
Detector de Estados de Misiones para el nuevo sistema de modos.

Este módulo detecta automáticamente el estado de cada misión basándose 
en la estructura de archivos en app/data/traducciones:

Estados posibles:
1. SIN_TRADUCIR - No hay carpeta de traducción o está vacía
2. TRADUCIDA - Existe out_lua/ con archivos de traducción 
3. REEMPAQUETADA - Existe finalizado/ con .miz reempaquetado
4. DESPLEGADA - Existe en directorio de despliegue

Autor: GitHub Copilot
Versión: 1.0
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from pathlib import Path


class MissionState(Enum):
    """Estados posibles de una misión en el flujo de traducción."""
    SIN_TRADUCIR = "sin_traducir"
    TRADUCIDA = "traducida" 
    REEMPAQUETADA = "reempaquetada"
    DESPLEGADA = "desplegada"


@dataclass
class MissionStatus:
    """Estado detallado de una misión."""
    filename: str
    state: MissionState
    translation_path: Optional[str] = None
    has_lua_files: bool = False
    has_repackaged_miz: bool = False
    has_deployment: bool = False
    translation_progress: float = 0.0  # 0.0 - 1.0
    last_modified: Optional[str] = None
    error_message: Optional[str] = None


class MissionStateDetector:
    """
    Detector robusto de estados de misiones basado en estructura de archivos.
    
    Analiza la estructura en app/data/traducciones para determinar automáticamente
    el estado de cada misión y qué acciones están disponibles.
    """
    
    def __init__(self, translations_base_path: str = None):
        """
        Inicializar detector de estados.
        
        Args:
            translations_base_path: Ruta base a app/data/traducciones 
        """
        self.logger = logging.getLogger(__name__)
        
        # Configurar ruta base
        if translations_base_path is None:
            # Buscar automáticamente la ruta
            current_dir = Path(__file__).parent
            self.translations_path = current_dir.parent / "data" / "traducciones"
        else:
            self.translations_path = Path(translations_base_path)
        
        self.logger.info(f"MissionStateDetector inicializado con ruta: {self.translations_path}")
    
    def detect_mission_state(self, mission_filename: str, campaign_name: str = None) -> MissionStatus:
        """
        Detectar el estado actual de una misión específica.
        
        Args:
            mission_filename: Nombre del archivo .miz (ej: "F-5E - Arrival.miz")
            campaign_name: Nombre de la campaña (opcional, se auto-detecta)
            
        Returns:
            MissionStatus con información detallada del estado
        """
        try:
            # Normalizar nombre de archivo
            clean_filename = mission_filename.replace('.miz', '').strip()
            
            # Buscar carpeta de traducción
            mission_path = self._find_mission_translation_path(clean_filename, campaign_name)
            
            if mission_path is None:
                return MissionStatus(
                    filename=mission_filename,
                    state=MissionState.SIN_TRADUCIR,
                    error_message="No se encontró carpeta de traducción"
                )
            
            # Analizar estructura de archivos
            return self._analyze_mission_structure(mission_filename, mission_path)
            
        except Exception as e:
            self.logger.error(f"Error detectando estado de '{mission_filename}': {e}")
            return MissionStatus(
                filename=mission_filename,
                state=MissionState.SIN_TRADUCIR,
                error_message=str(e)
            )
    
    def _find_mission_translation_path(self, mission_name: str, campaign_name: str = None) -> Optional[Path]:
        """Buscar la carpeta de traducción para una misión."""
        
        # Si se especifica campaña, buscar directamente
        if campaign_name:
            campaign_path = self.translations_path / campaign_name
            if campaign_path.exists():
                return self._search_mission_in_campaign(mission_name, campaign_path)
        
        # Buscar en todas las campañas
        for campaign_dir in self.translations_path.iterdir():
            if campaign_dir.is_dir() and campaign_dir.name != "README.md":
                mission_path = self._search_mission_in_campaign(mission_name, campaign_dir)
                if mission_path:
                    return mission_path
        
        return None
    
    def _search_mission_in_campaign(self, mission_name: str, campaign_path: Path) -> Optional[Path]:
        """Buscar una misión específica dentro de una campaña."""
        
        # Generar posibles nombres de carpeta (el sistema convierte caracteres especiales)
        possible_names = [
            mission_name,
            mission_name.replace(' - ', '_-_'),
            mission_name.replace(' ', '_'),
            mission_name.replace('-', '_'),
        ]
        
        for folder in campaign_path.iterdir():
            if folder.is_dir():
                # Comparar con posibles nombres (exactos primero)
                for possible_name in possible_names:
                    if folder.name.lower() == possible_name.lower():
                        return folder
                
                # Búsqueda más específica para evitar coincidencias erróneas
                # Por ejemplo, F5-E-C1 no debe coincidir con F5-E-C10
                for possible_name in possible_names:
                    # Solo coincidir si el nombre de la carpeta es exactamente el nombre buscado
                    # O si después del nombre hay un carácter no alfanumérico (como -, _, espacio)
                    folder_name_lower = folder.name.lower()
                    possible_name_lower = possible_name.lower()
                    
                    if folder_name_lower.startswith(possible_name_lower):
                        # Verificar que no hay más caracteres alfanuméricos después
                        if len(folder_name_lower) == len(possible_name_lower):
                            return folder
                        elif len(folder_name_lower) > len(possible_name_lower):
                            next_char = folder_name_lower[len(possible_name_lower)]
                            if not next_char.isalnum():  # Solo si el siguiente carácter no es alfanumérico
                                return folder
        
        return None
    
    def _analyze_mission_structure(self, mission_filename: str, mission_path: Path) -> MissionStatus:
        """Analizar la estructura de archivos de una misión traducida."""
        
        status = MissionStatus(
            filename=mission_filename,
            state=MissionState.SIN_TRADUCIR,
            translation_path=str(mission_path)
        )
        
        # Verificar carpeta out_lua/ (archivos de traducción)
        out_lua_path = mission_path / "out_lua"
        if out_lua_path.exists() and out_lua_path.is_dir():
            lua_files = list(out_lua_path.glob("*.lua"))
            jsonl_files = list(out_lua_path.glob("*.jsonl"))
            
            if lua_files or jsonl_files:
                status.has_lua_files = True
                status.state = MissionState.TRADUCIDA
                
                # Calcular progreso de traducción
                status.translation_progress = self._calculate_translation_progress(out_lua_path)
        
        # Verificar carpeta finalizado/ (reempaquetado)
        finalizado_path = mission_path / "finalizado"
        if finalizado_path.exists() and finalizado_path.is_dir():
            miz_files = list(finalizado_path.glob("*.miz"))
            
            if miz_files:
                status.has_repackaged_miz = True
                status.state = MissionState.REEMPAQUETADA
        
        # Verificar despliegue (esto se implementará según configuración específica)
        # Por ahora, asumimos que no hay despliegue automático
        
        # Obtener fecha de última modificación
        try:
            status.last_modified = str(mission_path.stat().st_mtime)
        except:
            pass
        
        return status
    
    def _calculate_translation_progress(self, out_lua_path: Path) -> float:
        """Calcular el progreso de traducción basándose en archivos."""
        
        try:
            # Buscar archivo de caché de traducción con estadísticas
            cache_file = out_lua_path / "translation_cache.json"
            if cache_file.exists():
                with cache_file.open('r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                    # Si hay estadísticas de traducción
                    if 'stats' in cache_data:
                        stats = cache_data['stats']
                        total = stats.get('total_strings', 0)
                        translated = stats.get('translated_strings', 0)
                        
                        if total > 0:
                            return translated / total
            
            # Fallback: calcular basándose en archivos presentes
            required_files = ['dictionary.translated.lua', 'dictionary.translations.jsonl']
            present_files = sum(1 for f in required_files if (out_lua_path / f).exists())
            
            return present_files / len(required_files)
            
        except Exception as e:
            self.logger.warning(f"Error calculando progreso: {e}")
            return 0.5  # Progreso asumido si hay errores
    
    def get_missions_by_state(self, state: MissionState, campaign_name: str = None) -> List[MissionStatus]:
        """
        Obtener todas las misiones en un estado específico.
        
        Args:
            state: Estado a filtrar
            campaign_name: Campaña específica (opcional)
            
        Returns:
            Lista de misiones en el estado solicitado
        """
        missions = []
        
        # Determinar qué campañas analizar
        campaigns_to_analyze = []
        if campaign_name:
            campaign_path = self.translations_path / campaign_name
            if campaign_path.exists():
                campaigns_to_analyze.append(campaign_path)
        else:
            campaigns_to_analyze = [
                d for d in self.translations_path.iterdir() 
                if d.is_dir() and d.name != "README.md"
            ]
        
        # Analizar cada campaña
        for campaign_path in campaigns_to_analyze:
            for mission_dir in campaign_path.iterdir():
                if mission_dir.is_dir():
                    # Inferir nombre de misión desde nombre de carpeta
                    mission_name = self._infer_mission_name_from_folder(mission_dir.name)
                    
                    # Detectar estado
                    status = self._analyze_mission_structure(mission_name, mission_dir)
                    
                    # Filtrar por estado solicitado
                    if status.state == state:
                        missions.append(status)
        
        return missions
    
    def _infer_mission_name_from_folder(self, folder_name: str) -> str:
        """Inferir el nombre original de la misión desde el nombre de carpeta."""
        
        # Revertir transformaciones comunes
        mission_name = folder_name.replace('_-_', ' - ').replace('_', ' ')
        
        # Añadir extensión .miz si no está presente
        if not mission_name.endswith('.miz'):
            mission_name += '.miz'
        
        return mission_name
    
    def get_available_missions_for_mode(self, mode: str, campaign_name: str = None) -> List[str]:
        """
        Obtener misiones disponibles para un modo específico.
        
        Args:
            mode: Modo solicitado ('traducir', 'reempaquetar', 'desplegar')
            campaign_name: Campaña específica (opcional)
            
        Returns:
            Lista de nombres de archivos .miz disponibles para ese modo
        """
        
        if mode == "traducir":
            # Para traducir: todas las misiones (independientemente del estado)
            return self._get_all_mission_names(campaign_name)
        
        elif mode == "reempaquetar":
            # Para reempaquetar: solo misiones traducidas
            translated_missions = self.get_missions_by_state(MissionState.TRADUCIDA, campaign_name)
            return [m.filename for m in translated_missions]
        
        elif mode == "desplegar":
            # Para desplegar: solo misiones reempaquetadas
            repackaged_missions = self.get_missions_by_state(MissionState.REEMPAQUETADA, campaign_name)
            return [m.filename for m in repackaged_missions]
        
        else:
            self.logger.warning(f"Modo desconocido: {mode}")
            return []
    
    def _get_all_mission_names(self, campaign_name: str = None) -> List[str]:
        """Obtener nombres de todas las misiones conocidas."""
        all_missions = set()
        
        # Obtener de todos los estados
        for state in MissionState:
            missions = self.get_missions_by_state(state, campaign_name)
            all_missions.update(m.filename for m in missions)
        
        # Función para ordenación natural (numérica)
        import re
        def natural_sort_key(name):
            """
            Crear una clave de ordenación natural para nombres de misión.
            Convierte números en nombres a enteros para ordenación correcta.
            Ej: F5-E-C2.miz viene antes que F5-E-C10.miz
            """
            # Separar letras y números
            parts = re.split(r'(\d+)', name.lower())
            # Convertir partes numéricas a enteros
            for i in range(len(parts)):
                if parts[i].isdigit():
                    parts[i] = int(parts[i])
            return parts
        
        return sorted(list(all_missions), key=natural_sort_key)
    
    def get_campaign_summary(self, campaign_name: str = None) -> Dict:
        """
        Obtener resumen de estados de todas las misiones en una campaña.
        
        Returns:
            Dict con contadores por estado y detalles
        """
        summary = {
            'total_missions': 0,
            'by_state': {
                MissionState.SIN_TRADUCIR.value: 0,
                MissionState.TRADUCIDA.value: 0,
                MissionState.REEMPAQUETADA.value: 0,
                MissionState.DESPLEGADA.value: 0
            },
            'missions': []
        }
        
        # Obtener todas las misiones
        for state in MissionState:
            missions = self.get_missions_by_state(state, campaign_name)
            summary['by_state'][state.value] = len(missions)
            summary['missions'].extend(missions)
            summary['total_missions'] += len(missions)
        
        return summary


# Instancia global singleton
_mission_state_detector_instance: Optional[MissionStateDetector] = None


def get_mission_state_detector(translations_path: str = None) -> MissionStateDetector:
    """
    Obtener instancia singleton del detector de estados.
    
    Args:
        translations_path: Ruta a traducciones (solo primera inicialización)
        
    Returns:
        Instancia de MissionStateDetector
    """
    global _mission_state_detector_instance
    
    if _mission_state_detector_instance is None:
        _mission_state_detector_instance = MissionStateDetector(translations_path)
    
    return _mission_state_detector_instance


# Funciones de conveniencia
def get_missions_for_mode(mode: str, campaign_name: str = None) -> List[str]:
    """Obtener misiones disponibles para un modo específico."""
    detector = get_mission_state_detector()
    return detector.get_available_missions_for_mode(mode, campaign_name)


def get_mission_state(mission_filename: str, campaign_name: str = None) -> MissionStatus:
    """Obtener estado de una misión específica."""
    detector = get_mission_state_detector()
    return detector.detect_mission_state(mission_filename, campaign_name)