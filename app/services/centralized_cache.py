import json
import os
from typing import Dict, Optional
import logging

class CentralizedCache:
    """Sistema de cache centralizado para traducciones DCS"""
    
    def __init__(self, cache_dir: str = None):
        """
        Inicializar el cache centralizado
        
        Args:
            cache_dir: Directorio donde guardar el cache. Si es None, usa app/data/cache/
        """
        if cache_dir is None:
            # Usar directorio por defecto en app/data/cache/
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_dir = os.path.join(base_dir, "data", "cache")
        
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "global_translation_cache.json")
        self.logger = logging.getLogger(__name__)
        
        # Crear directorio si no existe
        os.makedirs(cache_dir, exist_ok=True)
        
        # Inicializar cache vacío si no existe
        if not os.path.exists(self.cache_file):
            self._save_cache({})
    
    def load_cache(self, use_cache: bool = True) -> Dict[str, str]:
        """
        Cargar el cache centralizado
        
        Args:
            use_cache: Si False, retorna un diccionario vacío (simula cache deshabilitado)
            
        Returns:
            Diccionario con las traducciones en cache
        """
        if not use_cache:
            self.logger.info("Cache deshabilitado - retornando cache vacío")
            return {}
            
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    self.logger.info(f"Cache centralizado cargado: {len(cache)} entradas")
                    return cache
            else:
                self.logger.info("Archivo de cache centralizado no existe - creando nuevo")
                return {}
        except Exception as e:
            self.logger.error(f"Error cargando cache centralizado: {e}")
            return {}
    
    def _save_cache(self, cache: Dict[str, str]) -> bool:
        """
        Guardar el cache centralizado
        
        Args:
            cache: Diccionario con traducciones
            
        Returns:
            True si se guardó correctamente, False en caso de error
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Cache centralizado guardado: {len(cache)} entradas")
            return True
        except Exception as e:
            self.logger.error(f"Error guardando cache centralizado: {e}")
            return False
    
    def update_cache(self, new_translations: Dict[str, str], use_cache: bool = True) -> bool:
        """
        Actualizar el cache centralizado con nuevas traducciones
        
        Args:
            new_translations: Nuevas traducciones para añadir
            use_cache: Si False, no actualiza el cache (simula cache deshabilitado)
            
        Returns:
            True si se actualizó correctamente
        """
        if not use_cache:
            self.logger.info("Cache deshabilitado - no se actualizará el cache centralizado")
            return True
            
        try:
            # Cargar cache actual (usar el parámetro use_cache)
            current_cache = self.load_cache(use_cache=use_cache)
            
            # Filtrar traducciones válidas
            valid_translations = {
                en: es for en, es in new_translations.items()
                if isinstance(en, str) and isinstance(es, str) and 
                   en.strip() and es.strip() and 
                   en.strip().lower() != es.strip().lower()
            }
            
            # Merge sin duplicados
            merged_count = 0
            for en, es in valid_translations.items():
                if en not in current_cache:
                    current_cache[en] = es
                    merged_count += 1
                elif current_cache[en] != es:
                    # Actualizar si la traducción es diferente
                    current_cache[en] = es
                    merged_count += 1
            
            # Guardar cache actualizado
            if self._save_cache(current_cache):
                self.logger.info(f"Cache actualizado con {merged_count} nuevas/modificadas traducciones")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error actualizando cache centralizado: {e}")
            return False
    
    def merge_local_cache(self, local_cache_path: str, use_cache: bool = True) -> bool:
        """
        Fusionar un cache local (translation_cache.json) con el centralizado
        
        Args:
            local_cache_path: Ruta al archivo de cache local
            use_cache: Si False, no fusiona el cache
            
        Returns:
            True si se fusionó correctamente
        """
        if not use_cache:
            self.logger.info("Cache deshabilitado - no se fusionará el cache local")
            return True
            
        try:
            if os.path.exists(local_cache_path):
                with open(local_cache_path, 'r', encoding='utf-8') as f:
                    local_cache = json.load(f)
                
                result = self.update_cache(local_cache, use_cache=True)
                self.logger.info(f"Cache local fusionado desde: {local_cache_path}")
                return result
            else:
                self.logger.warning(f"Cache local no encontrado: {local_cache_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error fusionando cache local {local_cache_path}: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, any]:
        """
        Obtener estadísticas del cache centralizado
        
        Returns:
            Diccionario con estadísticas del cache
        """
        try:
            cache = self.load_cache(use_cache=True)
            file_size = os.path.getsize(self.cache_file) if os.path.exists(self.cache_file) else 0
            
            return {
                'total_entries': len(cache),
                'cache_file': self.cache_file,
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2)
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas del cache: {e}")
            return {
                'total_entries': 0,
                'cache_file': self.cache_file,
                'file_size_bytes': 0,
                'file_size_mb': 0,
                'error': str(e)
            }
    
    def clear_cache(self) -> bool:
        """
        Limpiar completamente el cache centralizado
        
        Returns:
            True si se limpió correctamente
        """
        try:
            self._save_cache({})
            self.logger.info("Cache centralizado limpiado")
            return True
        except Exception as e:
            self.logger.error(f"Error limpiando cache centralizado: {e}")
            return False