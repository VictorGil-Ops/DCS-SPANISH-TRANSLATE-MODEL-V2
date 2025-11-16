"""
Detector robusto y eficiente para misiones Flaming Cliffs en DCS.

Este módulo proporciona una implementación optimizada para detectar misiones
Flaming Cliffs con:
- Patrones regex compilados para mejor rendimiento
- Sistema de caché LRU para evitar re-procesamiento
- Validaciones robustas y manejo de errores
- Métricas de rendimiento y logging detallado
- API simple y consistente

Autor: GitHub Copilot
Versión: 2.0
"""

import re
import os
import time
import logging
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class FCPattern:
    """Representa un patrón de detección FC con metadatos."""
    regex: re.Pattern
    name: str
    description: str
    priority: int  # 1=alta, 2=media, 3=baja
    examples: List[str]


@dataclass
class DetectionResult:
    """Resultado de detección FC con información detallada."""
    is_fc: bool
    pattern_used: Optional[str] = None
    pattern_name: Optional[str] = None
    confidence: float = 0.0  # 0.0-1.0
    processing_time_ms: float = 0.0


class FCDetector:
    """
    Detector robusto y eficiente para misiones Flaming Cliffs.
    
    Características:
    - Patrones optimizados basados en casos reales
    - Caché LRU para mejor rendimiento
    - Validaciones y manejo de errores
    - Métricas detalladas
    """
    
    def __init__(self, cache_size: int = 1000):
        """
        Inicializar detector FC.
        
        Args:
            cache_size: Tamaño del caché LRU (default: 1000)
        """
        self.logger = logging.getLogger(__name__)
        self.cache_size = cache_size
        
        # Métricas de rendimiento
        self.stats = {
            'total_checks': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'fc_detected': 0,
            'normal_detected': 0,
            'errors': 0,
            'total_time_ms': 0.0
        }
        
        # Inicializar patrones
        self._compile_patterns()
        
        # Cache para resultados (filename -> DetectionResult)
        self._cache: Dict[str, DetectionResult] = {}
        
        self.logger.info(f"FCDetector inicializado con {len(self.patterns)} patrones y caché de {cache_size}")
    
    def _compile_patterns(self) -> None:
        """Compilar patrones regex para mejor rendimiento."""
        
        # Definición de patrones con prioridades y metadatos
        pattern_definitions = [
            # Patrones de alta prioridad (más específicos)
            {
                'regex': r'-FC-',
                'name': 'dash-FC-dash',
                'description': 'Patrón clásico con guiones: Mission-FC-01.miz',
                'priority': 1,
                'examples': ['F-5E-FC-Training.miz', 'A-10C-FC-CAS.miz']
            },
            {
                'regex': r'-FC\s',
                'name': 'dash-FC-space',
                'description': 'FC seguido de espacio: F-5E-FC BFM.miz',
                'priority': 1,
                'examples': ['F-5E-FC - BFM Arrival.miz', 'Harrier-FC Combat.miz']
            },
            {
                'regex': r'^FC-',
                'name': 'FC-prefix',
                'description': 'Archivos que empiezan con FC-: FC-Mission.miz',
                'priority': 1,
                'examples': ['FC-Training.miz', 'FC-Combat Mission.miz']
            },
            {
                'regex': r'_FC_',
                'name': 'underscore-FC-underscore',
                'description': 'FC con underscores: Mission_FC_01.miz',
                'priority': 1,
                'examples': ['Hornet_FC_BVR.miz', 'Training_FC_Basic.miz']
            },
            
            # Patrones de prioridad media
            {
                'regex': r'-FC\.',
                'name': 'dash-FC-dot',
                'description': 'FC antes de extensión: Mission-FC.miz',
                'priority': 2,
                'examples': ['Combat-FC.miz', 'Training-FC.miz']
            },
            {
                'regex': r'-FC$',
                'name': 'dash-FC-end',
                'description': 'Termina en -FC (sin extensión)',
                'priority': 2,
                'examples': ['Mission-FC', 'Training-FC']
            },
            {
                'regex': r'_FC\s',
                'name': 'underscore-FC-space',
                'description': 'Underscore FC con espacio: Mission_FC Combat.miz',
                'priority': 2,
                'examples': ['Mission_FC Combat.miz', 'Training_FC Advanced.miz']
            },
            {
                'regex': r'^FC_',
                'name': 'FC-underscore-prefix',
                'description': 'Empieza con FC_: FC_Mission.miz',
                'priority': 2,
                'examples': ['FC_Training.miz', 'FC_Combat.miz']
            },
            
            # Patrones específicos para nombres completos
            {
                'regex': r'FLAMINGCLIFF',
                'name': 'flamingcliff-word',
                'description': 'Palabra completa FlamingCliff',
                'priority': 3,
                'examples': ['FlamingCliff-Training.miz', 'Mission-FlamingCliff.miz']
            }
        ]
        
        # Compilar patrones para mejor rendimiento
        self.patterns: List[FCPattern] = []
        
        for pattern_def in pattern_definitions:
            try:
                compiled_regex = re.compile(pattern_def['regex'], re.IGNORECASE)
                pattern = FCPattern(
                    regex=compiled_regex,
                    name=pattern_def['name'],
                    description=pattern_def['description'],
                    priority=pattern_def['priority'],
                    examples=pattern_def['examples']
                )
                self.patterns.append(pattern)
                
            except re.error as e:
                self.logger.error(f"Error compilando patrón '{pattern_def['regex']}': {e}")
                self.stats['errors'] += 1
        
        # Ordenar por prioridad (alta prioridad primero)
        self.patterns.sort(key=lambda p: p.priority)
        
        self.logger.info(f"Compilados {len(self.patterns)} patrones FC exitosamente")
    
    def detect(self, filename: str, use_cache: bool = True) -> DetectionResult:
        """
        Detectar si un archivo es una misión Flaming Cliffs.
        
        Args:
            filename: Nombre del archivo a verificar
            use_cache: Usar caché para resultados previos
            
        Returns:
            DetectionResult con información detallada
        """
        start_time = time.perf_counter()
        self.stats['total_checks'] += 1
        
        try:
            # Validar entrada
            if not filename or not isinstance(filename, str):
                self.logger.warning(f"Nombre de archivo inválido: {filename}")
                self.stats['errors'] += 1
                return DetectionResult(is_fc=False, confidence=0.0)
            
            # Normalizar nombre
            filename_clean = filename.strip()
            if not filename_clean:
                return DetectionResult(is_fc=False, confidence=0.0)
            
            # Verificar caché
            if use_cache and filename_clean in self._cache:
                self.stats['cache_hits'] += 1
                result = self._cache[filename_clean]
                self.logger.debug(f"Cache hit para '{filename_clean}': {result.is_fc}")
                return result
            
            self.stats['cache_misses'] += 1
            
            # Realizar detección
            result = self._perform_detection(filename_clean)
            
            # Calcular tiempo de procesamiento
            end_time = time.perf_counter()
            result.processing_time_ms = (end_time - start_time) * 1000
            self.stats['total_time_ms'] += result.processing_time_ms
            
            # Actualizar estadísticas
            if result.is_fc:
                self.stats['fc_detected'] += 1
            else:
                self.stats['normal_detected'] += 1
            
            # Guardar en caché (con límite de tamaño)
            if use_cache:
                self._update_cache(filename_clean, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error detectando FC en '{filename}': {e}")
            self.stats['errors'] += 1
            return DetectionResult(is_fc=False, confidence=0.0)
    
    def _perform_detection(self, filename: str) -> DetectionResult:
        """Realizar la detección real usando patrones compilados."""
        filename_upper = filename.upper()
        
        # Probar cada patrón en orden de prioridad
        for pattern in self.patterns:
            if pattern.regex.search(filename_upper):
                # Calcular confianza basada en prioridad
                confidence = 1.0 - (pattern.priority - 1) * 0.2  # Alta=1.0, Media=0.8, Baja=0.6
                
                result = DetectionResult(
                    is_fc=True,
                    pattern_used=pattern.regex.pattern,
                    pattern_name=pattern.name,
                    confidence=confidence
                )
                
                self.logger.debug(f"FC detectado: '{filename}' con patrón '{pattern.name}' (confianza: {confidence:.2f})")
                return result
        
        # No se encontró ningún patrón
        self.logger.debug(f"Archivo normal: '{filename}' (ningún patrón FC coincidió)")
        return DetectionResult(is_fc=False, confidence=1.0)
    
    def _update_cache(self, filename: str, result: DetectionResult) -> None:
        """Actualizar caché con gestión de tamaño."""
        if len(self._cache) >= self.cache_size:
            # Eliminar el elemento más antiguo (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[filename] = result
    
    def batch_detect(self, filenames: List[str], use_cache: bool = True) -> Dict[str, DetectionResult]:
        """
        Detectar FC en múltiples archivos de forma eficiente.
        
        Args:
            filenames: Lista de nombres de archivos
            use_cache: Usar caché para resultados
            
        Returns:
            Dict con filename -> DetectionResult
        """
        results = {}
        
        self.logger.info(f"Iniciando detección en lote de {len(filenames)} archivos")
        start_time = time.perf_counter()
        
        for filename in filenames:
            results[filename] = self.detect(filename, use_cache)
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000
        
        self.logger.info(f"Detección en lote completada en {total_time:.2f}ms")
        
        return results
    
    def get_fc_files(self, filenames: List[str]) -> List[str]:
        """
        Filtrar solo archivos FC de una lista.
        
        Args:
            filenames: Lista de nombres de archivos
            
        Returns:
            Lista de archivos FC únicamente
        """
        results = self.batch_detect(filenames)
        return [f for f, result in results.items() if result.is_fc]
    
    def get_normal_files(self, filenames: List[str]) -> List[str]:
        """
        Filtrar solo archivos normales de una lista.
        
        Args:
            filenames: Lista de nombres de archivos
            
        Returns:
            Lista de archivos normales únicamente
        """
        results = self.batch_detect(filenames)
        return [f for f, result in results.items() if not result.is_fc]
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas de rendimiento."""
        stats = self.stats.copy()
        
        # Calcular métricas derivadas
        total_checks = stats['total_checks']
        if total_checks > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / total_checks
            stats['avg_processing_time_ms'] = stats['total_time_ms'] / total_checks
            stats['fc_detection_rate'] = stats['fc_detected'] / total_checks
        else:
            stats['cache_hit_rate'] = 0.0
            stats['avg_processing_time_ms'] = 0.0
            stats['fc_detection_rate'] = 0.0
        
        return stats
    
    def clear_cache(self) -> None:
        """Limpiar caché de resultados."""
        cache_size = len(self._cache)
        self._cache.clear()
        self.logger.info(f"Caché limpiado: {cache_size} entradas eliminadas")
    
    def get_pattern_info(self) -> List[Dict]:
        """Obtener información sobre los patrones disponibles."""
        return [
            {
                'name': p.name,
                'pattern': p.regex.pattern,
                'description': p.description,
                'priority': p.priority,
                'examples': p.examples
            }
            for p in self.patterns
        ]
    
    def validate_filename(self, filename: str) -> Tuple[bool, str]:
        """
        Validar que un nombre de archivo sea válido para procesamiento.
        
        Args:
            filename: Nombre de archivo a validar
            
        Returns:
            Tuple (es_válido, mensaje_error)
        """
        if not filename:
            return False, "Nombre de archivo vacío"
        
        if not isinstance(filename, str):
            return False, f"Tipo inválido: esperado str, recibido {type(filename)}"
        
        filename_clean = filename.strip()
        if not filename_clean:
            return False, "Nombre de archivo solo contiene espacios"
        
        # Verificar caracteres inválidos para nombres de archivo
        invalid_chars = set('<>:"/\\|?*')
        if any(char in invalid_chars for char in filename_clean):
            return False, f"Contiene caracteres inválidos: {invalid_chars & set(filename_clean)}"
        
        return True, "Válido"


# Instancia global singleton para uso en toda la aplicación
_fc_detector_instance: Optional[FCDetector] = None


def get_fc_detector(cache_size: int = 1000) -> FCDetector:
    """
    Obtener instancia singleton del detector FC.
    
    Args:
        cache_size: Tamaño del caché (solo para primera inicialización)
        
    Returns:
        Instancia de FCDetector
    """
    global _fc_detector_instance
    
    if _fc_detector_instance is None:
        _fc_detector_instance = FCDetector(cache_size)
    
    return _fc_detector_instance


# Funciones de conveniencia para compatibilidad hacia atrás
def is_fc_mission(filename: str) -> bool:
    """Función simple para verificar si un archivo es FC."""
    detector = get_fc_detector()
    result = detector.detect(filename)
    return result.is_fc


def get_fc_pattern_used(filename: str) -> str:
    """Obtener el patrón FC usado para un archivo."""
    detector = get_fc_detector()
    result = detector.detect(filename)
    return result.pattern_name or "unknown"


def filter_fc_files(filenames: List[str]) -> List[str]:
    """Filtrar solo archivos FC de una lista."""
    detector = get_fc_detector()
    return detector.get_fc_files(filenames)


def filter_normal_files(filenames: List[str]) -> List[str]:
    """Filtrar solo archivos normales de una lista."""
    detector = get_fc_detector()
    return detector.get_normal_files(filenames)