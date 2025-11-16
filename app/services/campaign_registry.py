#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio para gestión de unidades y persistencia de campañas detectadas
Maneja la detección de unidades disponibles/desconectadas y guarda un registro
de campañas encontradas para uso posterior.
"""
import os
import json
import time
import string
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path
from dataclasses import dataclass, asdict

from config.settings import BASE_DIR


@dataclass
class DetectedCampaign:
    """Información de una campaña detectada"""
    name: str
    path: str
    drive_letter: str
    missions_count: int
    last_seen: str
    total_size_mb: float
    is_available: bool
    detection_method: str  # 'system', 'quick_scan', 'deep_scan'


@dataclass
class DriveStatus:
    """Estado de una unidad"""
    letter: str
    is_available: bool
    has_campaigns: bool
    campaigns_found: int
    last_check: str


class CampaignRegistryService:
    """
    Servicio para gestionar el registro persistente de campañas detectadas
    y el estado de las unidades donde se encuentran.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Rutas de archivos de persistencia
        self.config_dir = Path(BASE_DIR) / "app" / "data" / "my_config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.campaigns_file = self.config_dir / "detected_campaigns.jsonl"
        self.drives_file = self.config_dir / "drives_status.json"
        
        # Cache en memoria
        self._campaigns_cache = {}
        self._drives_cache = {}
        
        # Cargar datos existentes
        self._load_campaigns()
        self._load_drives_status()
        
        self.logger.info(f"CampaignRegistryService inicializado. Campañas en cache: {len(self._campaigns_cache)}")
    
    def get_available_drives(self) -> Set[str]:
        """Obtiene las unidades actualmente disponibles en el sistema"""
        available = set()
        
        for drive_letter in string.ascii_uppercase:
            drive_path = f"{drive_letter}:\\"
            if os.path.exists(drive_path):
                available.add(drive_letter)
        
        return available
    
    def detect_drive_changes(self) -> Dict[str, List[str]]:
        """
        Detecta cambios en las unidades disponibles desde la última verificación.
        
        Returns:
            Dict con 'connected' y 'disconnected' conteniendo listas de letras de unidades
        """
        current_drives = self.get_available_drives()
        previous_drives = set(self._drives_cache.keys())
        
        connected = list(current_drives - previous_drives)
        disconnected = list(previous_drives - current_drives)
        
        # Actualizar estado de unidades
        timestamp = datetime.now().isoformat()
        
        # Marcar unidades conectadas como disponibles
        for drive in connected:
            self._drives_cache[drive] = DriveStatus(
                letter=drive,
                is_available=True,
                has_campaigns=False,
                campaigns_found=0,
                last_check=timestamp
            )
            self.logger.info(f"Unidad {drive}: conectada")
        
        # Marcar unidades desconectadas como no disponibles
        for drive in disconnected:
            if drive in self._drives_cache:
                self._drives_cache[drive].is_available = False
                self._drives_cache[drive].last_check = timestamp
                self.logger.warning(f"Unidad {drive}: desconectada")
        
        # Actualizar unidades que siguen disponibles
        for drive in current_drives:
            if drive in self._drives_cache:
                self._drives_cache[drive].is_available = True
                self._drives_cache[drive].last_check = timestamp
        
        # Guardar cambios
        if connected or disconnected:
            self._save_drives_status()
        
        return {
            'connected': connected,
            'disconnected': disconnected,
            'current_drives': list(current_drives)
        }
    
    def register_campaigns(self, campaigns: List[Dict], detection_method: str = 'unknown') -> int:
        """
        Registra campañas detectadas en el sistema persistente.
        
        Args:
            campaigns: Lista de campañas encontradas
            detection_method: Método usado para detectarlas
            
        Returns:
            Número de campañas nuevas registradas
        """
        new_campaigns = 0
        timestamp = datetime.now().isoformat()
        
        for campaign_data in campaigns:
            campaign_path = campaign_data.get('path', '')
            if not campaign_path:
                continue
            
            # Extraer letra de unidad
            drive_letter = campaign_path[0].upper() if campaign_path and len(campaign_path) > 1 else 'Unknown'
            
            # Calcular tamaño total
            total_size = sum(
                mission.get('size', 0) 
                for mission in campaign_data.get('missions', [])
            ) / (1024 * 1024)  # Convertir a MB
            
            campaign = DetectedCampaign(
                name=campaign_data.get('name', 'Unknown'),
                path=campaign_path,
                drive_letter=drive_letter,
                missions_count=campaign_data.get('missions_count', 0),
                last_seen=timestamp,
                total_size_mb=round(total_size, 2),
                is_available=os.path.exists(campaign_path),
                detection_method=detection_method
            )
            
            # Verificar si es nueva o actualizar existente
            campaign_key = f"{drive_letter}:{campaign.name}"
            
            if campaign_key not in self._campaigns_cache:
                new_campaigns += 1
                self.logger.info(f"Nueva campaña registrada: {campaign.name} en {drive_letter}:")
            else:
                self.logger.debug(f"Campaña actualizada: {campaign.name}")
            
            self._campaigns_cache[campaign_key] = campaign
            
            # Actualizar estado de la unidad
            if drive_letter != 'Unknown':
                if drive_letter not in self._drives_cache:
                    self._drives_cache[drive_letter] = DriveStatus(
                        letter=drive_letter,
                        is_available=True,
                        has_campaigns=True,
                        campaigns_found=1,
                        last_check=timestamp
                    )
                else:
                    self._drives_cache[drive_letter].has_campaigns = True
                    self._drives_cache[drive_letter].campaigns_found += 1
        
        # Guardar en disco
        self._save_campaigns()
        self._save_drives_status()
        
        return new_campaigns
    
    def get_campaigns_by_drive(self, drive_letter: str) -> List[DetectedCampaign]:
        """Obtiene todas las campañas de una unidad específica"""
        return [
            campaign for campaign in self._campaigns_cache.values()
            if campaign.drive_letter == drive_letter
        ]
    
    def get_unavailable_campaigns(self) -> List[DetectedCampaign]:
        """Obtiene campañas cuyas unidades no están disponibles"""
        unavailable = []
        
        for campaign in self._campaigns_cache.values():
            if not os.path.exists(campaign.path):
                campaign.is_available = False
                unavailable.append(campaign)
        
        return unavailable
    
    def get_all_campaigns(self, only_available: bool = False) -> List[DetectedCampaign]:
        """
        Obtiene todas las campañas registradas.
        
        Args:
            only_available: Si True, solo devuelve campañas en unidades disponibles
        """
        campaigns = list(self._campaigns_cache.values())
        
        if only_available:
            # Actualizar disponibilidad en tiempo real
            for campaign in campaigns:
                campaign.is_available = os.path.exists(campaign.path)
            
            campaigns = [c for c in campaigns if c.is_available]
        
        return campaigns
    
    def get_drive_status_summary(self) -> Dict[str, any]:
        """Obtiene un resumen del estado de todas las unidades"""
        current_drives = self.get_available_drives()
        
        summary = {
            'total_drives_known': len(self._drives_cache),
            'drives_available': len(current_drives),
            'drives_with_campaigns': 0,
            'total_campaigns': len(self._campaigns_cache),
            'available_campaigns': 0,
            'unavailable_campaigns': 0,
            'drives_detail': [],
            'warnings': []
        }
        
        # Procesar cada unidad conocida
        for drive_letter, drive_status in self._drives_cache.items():
            campaigns_in_drive = self.get_campaigns_by_drive(drive_letter)
            available_campaigns_in_drive = len([c for c in campaigns_in_drive if c.is_available])
            
            drive_info = {
                'letter': drive_letter,
                'is_available': drive_letter in current_drives,
                'has_campaigns': len(campaigns_in_drive) > 0,
                'campaigns_count': len(campaigns_in_drive),
                'available_campaigns': available_campaigns_in_drive,
                'last_check': drive_status.last_check
            }
            
            summary['drives_detail'].append(drive_info)
            
            if drive_info['has_campaigns']:
                summary['drives_with_campaigns'] += 1
                
            if not drive_info['is_available'] and drive_info['has_campaigns']:
                summary['warnings'].append(
                    f"Unidad {drive_letter}: no está disponible pero tiene {len(campaigns_in_drive)} campañas registradas"
                )
        
        # Contar campañas disponibles/no disponibles
        for campaign in self._campaigns_cache.values():
            if os.path.exists(campaign.path):
                summary['available_campaigns'] += 1
            else:
                summary['unavailable_campaigns'] += 1
        
        return summary
    
    def cleanup_old_entries(self, days_old: int = 30) -> int:
        """
        Limpia entradas antiguas que no han sido vistas en los días especificados.
        
        Args:
            days_old: Días desde la última vez que se vio la campaña
            
        Returns:
            Número de entradas eliminadas
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        
        campaigns_to_remove = []
        for key, campaign in self._campaigns_cache.items():
            try:
                last_seen = datetime.fromisoformat(campaign.last_seen.replace('Z', '+00:00'))
                if last_seen < cutoff_date and not campaign.is_available:
                    campaigns_to_remove.append(key)
            except (ValueError, AttributeError):
                # Si no se puede parsear la fecha, mantener la campaña
                continue
        
        for key in campaigns_to_remove:
            del self._campaigns_cache[key]
            removed_count += 1
            self.logger.info(f"Campaña antigua eliminada: {key}")
        
        if removed_count > 0:
            self._save_campaigns()
        
        return removed_count
    
    def _load_campaigns(self):
        """Carga campañas desde el archivo JSONL"""
        self._campaigns_cache = {}
        
        if not self.campaigns_file.exists():
            return
        
        try:
            with open(self.campaigns_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        # Manejar compatibilidad: eliminar campaign_name si existe y usar name
                        if 'campaign_name' in data:
                            if 'name' not in data:
                                data['name'] = data['campaign_name']
                            del data['campaign_name']
                        
                        # Filtrar campos que no pertenecen al dataclass
                        valid_fields = {'name', 'path', 'drive_letter', 'missions_count', 'last_seen', 'total_size_mb', 'is_available', 'detection_method'}
                        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                        
                        # Asegurar campos requeridos con valores por defecto
                        filtered_data.setdefault('drive_letter', 'D')
                        filtered_data.setdefault('last_seen', datetime.now().isoformat())
                        filtered_data.setdefault('total_size_mb', 0.0)
                        filtered_data.setdefault('is_available', True)
                        filtered_data.setdefault('detection_method', 'legacy')
                        
                        campaign = DetectedCampaign(**filtered_data)
                        key = f"{campaign.drive_letter}:{campaign.name}"
                        self._campaigns_cache[key] = campaign
                    except (json.JSONDecodeError, TypeError) as e:
                        self.logger.error(f"Error en línea {line_num} del archivo de campañas: {e}")
                        self.logger.debug(f"Línea problemática: {line}")
            
            self.logger.info(f"Cargadas {len(self._campaigns_cache)} campañas desde archivo")
            
        except Exception as e:
            self.logger.error(f"Error cargando campañas: {e}")
    
    def _save_campaigns(self):
        """Guarda campañas en el archivo JSONL"""
        try:
            with open(self.campaigns_file, 'w', encoding='utf-8') as f:
                for campaign in self._campaigns_cache.values():
                    f.write(json.dumps(asdict(campaign), ensure_ascii=False) + '\n')
            
            self.logger.debug(f"Guardadas {len(self._campaigns_cache)} campañas en archivo")
            
        except Exception as e:
            self.logger.error(f"Error guardando campañas: {e}")
    
    def _load_drives_status(self):
        """Carga estado de unidades desde archivo JSON"""
        self._drives_cache = {}
        
        if not self.drives_file.exists():
            return
        
        try:
            with open(self.drives_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for drive_data in data:
                drive_status = DriveStatus(**drive_data)
                self._drives_cache[drive_status.letter] = drive_status
            
            self.logger.info(f"Cargado estado de {len(self._drives_cache)} unidades desde archivo")
            
        except Exception as e:
            self.logger.error(f"Error cargando estado de unidades: {e}")
    
    def _save_drives_status(self):
        """Guarda estado de unidades en archivo JSON"""
        try:
            data = [asdict(drive_status) for drive_status in self._drives_cache.values()]
            
            with open(self.drives_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Guardado estado de {len(self._drives_cache)} unidades en archivo")
            
        except Exception as e:
            self.logger.error(f"Error guardando estado de unidades: {e}")


# Instancia global del servicio
_campaign_registry = None


def get_campaign_registry() -> CampaignRegistryService:
    """Obtiene la instancia global del servicio de registro de campañas"""
    global _campaign_registry
    if _campaign_registry is None:
        _campaign_registry = CampaignRegistryService()
    return _campaign_registry