"""
Sistema de Cache Local por Misión
Gestiona caches individuales para cada misión que se sincronizan con el cache global.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class MissionCacheManager:
    """Gestor de cache local por misión con sincronización global"""
    
    def __init__(self, base_path: str = None):
        if base_path:
            self.base_path = Path(base_path)
        else:
            # Usar path absoluto desde la raíz del proyecto
            import os
            project_root = Path(__file__).parent.parent.parent
            self.base_path = project_root / "app" / "data" / "traducciones"
            
        self.global_cache_path = self.base_path.parent / "cache" / "global_translation_cache.json"
        self.cache_filename = "translation_cache.json"  # Usar archivos existentes
        self.cache_subpath = "out_lua"  # Subdirectorio donde están los caches
        
    def get_mission_cache_path(self, campaign_name: str, mission_name: str) -> Path:
        """Obtener ruta del cache de una misión específica"""
        return self.base_path / campaign_name / mission_name / self.cache_subpath / self.cache_filename
    
    def load_mission_cache(self, campaign_name: str, mission_name: str) -> Dict:
        """Cargar cache local de una misión"""
        cache_path = self.get_mission_cache_path(campaign_name, mission_name)
        
        if not cache_path.exists():
            logger.info(f"Cache no existe para {campaign_name}/{mission_name}, creando nuevo")
            return self._create_empty_cache()
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                raw_cache = json.load(f)
                
            # Si es un diccionario simple (formato existente), adaptarlo
            if isinstance(raw_cache, dict) and 'metadata' not in raw_cache and 'entries' not in raw_cache:
                logger.info(f"Adaptando cache existente: {campaign_name}/{mission_name}")
                
                # Convertir formato legacy: {"clave": "traduccion"} -> {"clave": {"original": "clave", "translated": "traduccion"}}
                adapted_entries = {}
                for key, value in raw_cache.items():
                    if isinstance(value, str):  # Formato simple clave->traducción
                        adapted_entries[key] = {
                            'original': key,
                            'translated': value,
                            'context': '',
                            'added_at': datetime.now().isoformat(),
                            'campaign': campaign_name,
                            'mission': mission_name,
                            'format': 'legacy_adapted'
                        }
                    elif isinstance(value, dict):  # Ya tiene estructura de objeto
                        adapted_entries[key] = value
                    else:
                        logger.warning(f"Entrada con formato no reconocido: {key} = {type(value)}")
                
                cache_data = {
                    'entries': adapted_entries,
                    'metadata': {
                        'campaign': campaign_name,
                        'mission': mission_name,
                        'entries_count': len(adapted_entries),
                        'format': 'legacy_adapted',
                        'last_updated': datetime.now().isoformat(),
                        'original_format': 'simple_dict'
                    }
                }
                
                logger.info(f"✅ Cache legacy adaptado: {len(adapted_entries)} entradas convertidas")
            else:
                # Ya tiene el formato esperado
                cache_data = raw_cache
                
            logger.info(f"✅ Cache cargado: {campaign_name}/{mission_name} ({len(cache_data.get('entries', {}))} entradas)")
            return cache_data
        except Exception as e:
            logger.error(f"❌ Error cargando cache {cache_path}: {e}")
            return self._create_empty_cache()
    
    def save_mission_cache(self, campaign_name: str, mission_name: str, cache_data: Dict) -> bool:
        """Guardar cache local de una misión"""
        try:
            cache_path = self.get_mission_cache_path(campaign_name, mission_name)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Añadir metadatos
            cache_data['metadata'] = {
                'last_updated': datetime.now().isoformat(),
                'campaign': campaign_name,
                'mission': mission_name,
                'entries_count': len(cache_data.get('entries', {}))
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Cache guardado: {campaign_name}/{mission_name} ({cache_data['metadata']['entries_count']} entradas)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error guardando cache {campaign_name}/{mission_name}: {e}")
            return False
    
    def add_translation_to_mission(self, campaign_name: str, mission_name: str, 
                                 original_text: str, translated_text: str,
                                 context: str = None) -> bool:
        """Añadir traducción al cache de una misión específica"""
        try:
            cache_data = self.load_mission_cache(campaign_name, mission_name)
            
            # Crear clave única
            cache_key = f"{campaign_name}#{mission_name}#{original_text[:50]}"
            
            cache_data['entries'][cache_key] = {
                'original': original_text,
                'translated': translated_text,
                'context': context,
                'added_at': datetime.now().isoformat(),
                'campaign': campaign_name,
                'mission': mission_name
            }
            
            success = self.save_mission_cache(campaign_name, mission_name, cache_data)
            
            if success:
                logger.info(f"✅ Traducción añadida al cache: {cache_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error añadiendo traducción: {e}")
            return False
    
    def update_translation(self, campaign_name: str, mission_name: str, key: str, new_translation: str, context: str = None) -> bool:
        """Actualizar una traducción específica en el cache de misión"""
        try:
            # Cargar cache actual
            cache_data = self.load_mission_cache(campaign_name, mission_name)
            
            if key not in cache_data['entries']:
                logger.warning(f"Clave no encontrada en cache: {key}")
                return False
            
            # Actualizar la traducción
            cache_data['entries'][key]['translated'] = new_translation
            cache_data['entries'][key]['last_updated'] = datetime.now().isoformat()
            
            if context:
                cache_data['entries'][key]['context'] = context
            
            # Marcar como modificado por usuario
            cache_data['entries'][key]['user_modified'] = True
            cache_data['entries'][key]['modified_at'] = datetime.now().isoformat()
            
            # Guardar cambios
            success = self.save_mission_cache(campaign_name, mission_name, cache_data)
            
            if success:
                logger.info(f"✅ Traducción actualizada: {key[:50]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error actualizando traducción: {e}")
            return False
    
    def update_multiple_translations(self, campaign_name: str, mission_name: str, updates: Dict[str, str]) -> Tuple[bool, int]:
        """Actualizar múltiples traducciones de una vez"""
        try:
            cache_data = self.load_mission_cache(campaign_name, mission_name)
            updated_count = 0
            
            for key, new_translation in updates.items():
                if key in cache_data['entries']:
                    cache_data['entries'][key]['translated'] = new_translation
                    cache_data['entries'][key]['last_updated'] = datetime.now().isoformat()
                    cache_data['entries'][key]['user_modified'] = True
                    cache_data['entries'][key]['modified_at'] = datetime.now().isoformat()
                    updated_count += 1
                else:
                    logger.warning(f"Clave no encontrada: {key[:50]}...")
            
            if updated_count > 0:
                success = self.save_mission_cache(campaign_name, mission_name, cache_data)
                if success:
                    logger.info(f"✅ {updated_count} traducciones actualizadas")
                return success, updated_count
            else:
                return False, 0
                
        except Exception as e:
            logger.error(f"❌ Error actualizando múltiples traducciones: {e}")
            return False, 0
    
    def get_all_mission_caches(self) -> List[Dict]:
        """Obtener información de todos los caches de misión"""
        mission_caches = []
        
        try:
            for campaign_dir in self.base_path.iterdir():
                if not campaign_dir.is_dir():
                    continue
                    
                for mission_dir in campaign_dir.iterdir():
                    if not mission_dir.is_dir():
                        continue
                    
                    cache_path = mission_dir / self.cache_subpath / self.cache_filename
                    
                    if cache_path.exists():
                        cache_info = self._get_cache_info(cache_path, campaign_dir.name, mission_dir.name)
                        if cache_info:
                            mission_caches.append(cache_info)
            
            logger.info(f"✅ Encontrados {len(mission_caches)} caches de misión")
            return mission_caches
            
        except Exception as e:
            logger.error(f"❌ Error listando caches de misión: {e}")
            return []
    
    def sync_mission_to_global(self, campaign_name: str, mission_name: str) -> Tuple[bool, int]:
        """Sincronizar cache de misión con el cache global"""
        try:
            # Cargar cache de misión
            mission_cache = self.load_mission_cache(campaign_name, mission_name)
            
            if not mission_cache.get('entries'):
                logger.info(f"No hay entradas para sincronizar en {campaign_name}/{mission_name}")
                return True, 0
            
            # Cargar cache global
            global_cache_raw = self._load_global_cache()
            
            # Adaptar cache global al formato estructurado si es necesario
            if 'entries' not in global_cache_raw:
                # Es formato legacy, convertir
                logger.info("Adaptando cache global a formato estructurado")
                global_cache = {'entries': global_cache_raw}
            else:
                global_cache = global_cache_raw
            
            # Asegurar que entries existe
            if 'entries' not in global_cache:
                global_cache['entries'] = {}
            
            # Sincronizar entradas
            synced_count = 0
            for key, mission_entry in mission_cache['entries'].items():
                # Extraer solo la traducción para el cache global (formato legacy)
                if isinstance(mission_entry, dict) and 'translated' in mission_entry:
                    translation = mission_entry['translated']
                elif isinstance(mission_entry, str):
                    translation = mission_entry
                else:
                    logger.warning(f"Formato de entrada no reconocido: {key}")
                    continue
                
                # Solo añadir si no existe o si la traducción ha cambiado
                if key not in global_cache['entries'] or global_cache['entries'][key] != translation:
                    global_cache['entries'][key] = translation
                    synced_count += 1
            
            # Guardar cache global actualizado (mantener formato legacy para compatibilidad)
            if synced_count > 0:
                # Guardar solo las entradas (formato legacy)
                success = self._save_global_cache(global_cache['entries'])
                if success:
                    logger.info(f"✅ Sincronizadas {synced_count} entradas de {campaign_name}/{mission_name} al cache global")
                return success, synced_count
            else:
                logger.info(f"Cache de {campaign_name}/{mission_name} ya está sincronizado")
                return True, 0
                
        except Exception as e:
            logger.error(f"❌ Error sincronizando {campaign_name}/{mission_name}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, 0
    
    def sync_all_to_global(self) -> Tuple[bool, int]:
        """Sincronizar todos los caches de misión con el global"""
        try:
            mission_caches = self.get_all_mission_caches()
            total_synced = 0
            
            for cache_info in mission_caches:
                success, count = self.sync_mission_to_global(
                    cache_info['campaign'], 
                    cache_info['mission']
                )
                if success:
                    total_synced += count
            
            logger.info(f"✅ Sincronización completa: {total_synced} entradas añadidas al cache global")
            return True, total_synced
            
        except Exception as e:
            logger.error(f"❌ Error en sincronización global: {e}")
            return False, 0
    
    def compact_mission_cache(self, campaign_name: str, mission_name: str) -> Tuple[bool, int]:
        """Compactar cache de una misión eliminando duplicados"""
        try:
            cache_data = self.load_mission_cache(campaign_name, mission_name)
            
            original_count = len(cache_data.get('entries', {}))
            
            # Eliminar duplicados basados en texto original
            seen_originals = {}
            unique_entries = {}
            
            for key, value in cache_data.get('entries', {}).items():
                original_text = value.get('original', '').strip().lower()
                
                if original_text not in seen_originals:
                    seen_originals[original_text] = key
                    unique_entries[key] = value
                else:
                    logger.debug(f"Eliminando duplicado: {key}")
            
            cache_data['entries'] = unique_entries
            duplicates_removed = original_count - len(unique_entries)
            
            if duplicates_removed > 0:
                success = self.save_mission_cache(campaign_name, mission_name, cache_data)
                if success:
                    logger.info(f"✅ Cache compactado {campaign_name}/{mission_name}: {duplicates_removed} duplicados eliminados")
                return success, duplicates_removed
            else:
                logger.info(f"Cache {campaign_name}/{mission_name} ya está compacto")
                return True, 0
                
        except Exception as e:
            logger.error(f"❌ Error compactando cache {campaign_name}/{mission_name}: {e}")
            return False, 0
    
    def _create_empty_cache(self) -> Dict:
        """Crear estructura de cache vacía"""
        return {
            'entries': {},
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'entries_count': 0
            }
        }
    
    def _get_cache_info(self, cache_path: Path, campaign: str, mission: str) -> Optional[Dict]:
        """Obtener información de un cache específico"""
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                raw_cache = json.load(f)
            
            # Detectar formato del cache
            if isinstance(raw_cache, dict) and 'metadata' not in raw_cache and 'entries' not in raw_cache:
                # Formato existente (diccionario simple)
                entries_count = len(raw_cache)
                last_updated = None
            else:
                # Formato con metadatos
                entries_count = len(raw_cache.get('entries', {}))
                last_updated = raw_cache.get('metadata', {}).get('last_updated')
                
            return {
                'campaign': campaign,
                'mission': mission,
                'path': str(cache_path),
                'entries_count': entries_count,
                'last_updated': last_updated,
                'file_size': cache_path.stat().st_size
            }
        except Exception as e:
            logger.error(f"Error leyendo cache {cache_path}: {e}")
            return None
    
    def _load_global_cache(self) -> Dict:
        """Cargar cache global"""
        try:
            if self.global_cache_path.exists():
                with open(self.global_cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Cache global cargado: {len(data) if isinstance(data, dict) else 0} entradas")
                return data
            else:
                logger.info("Cache global no existe, creando uno nuevo")
                return {}
        except Exception as e:
            logger.error(f"Error cargando cache global: {e}")
            return {}
    
    def _save_global_cache(self, cache_data: Dict) -> bool:
        """Guardar cache global"""
        try:
            self.global_cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.global_cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            entries_count = len(cache_data) if isinstance(cache_data, dict) else 0
            logger.info(f"✅ Cache global guardado: {entries_count} entradas")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error guardando cache global: {e}")
            return False

# Instancia global
mission_cache_manager = MissionCacheManager()