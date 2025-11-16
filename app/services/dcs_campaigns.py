#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio para manejar campañas y misiones de DCS
"""
import os
import glob
import re
import zipfile
import logging

# Importar el nuevo detector FC optimizado
from app.utils.fc_detector import get_fc_detector
from typing import List, Dict, Tuple, Optional
from pathlib import Path


class DCSCampaignService:
    """Servicio para escanear y manejar campañas de DCS"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def scan_campaigns(self, dcs_path: str) -> List[Dict[str, any]]:
        """Escanea las campañas disponibles en el directorio de DCS"""
        campaigns = []
        
        if not os.path.exists(dcs_path):
            self.logger.error(f"DCS path does not exist: {dcs_path}")
            return campaigns
        
        try:
            # Buscar archivos .miz en el directorio
            miz_files = glob.glob(os.path.join(dcs_path, "**", "*.miz"), recursive=True)
            
            # Agrupar por directorio de campaña
            campaign_dirs = {}
            
            for miz_file in miz_files:
                campaign_dir = os.path.dirname(miz_file)
                campaign_name = os.path.basename(campaign_dir)
                
                if campaign_name not in campaign_dirs:
                    campaign_dirs[campaign_name] = {
                        'name': campaign_name,
                        'path': campaign_dir,
                        'missions': [],
                        'missions_count': 0
                    }
                
                mission_name = os.path.basename(miz_file)
                campaign_dirs[campaign_name]['missions'].append({
                    'name': mission_name,
                    'path': miz_file,
                    'size': os.path.getsize(miz_file)
                })
                campaign_dirs[campaign_name]['missions_count'] += 1
            
            campaigns = list(campaign_dirs.values())
            
            # Ordenar campañas por nombre
            campaigns.sort(key=lambda x: x['name'].lower())
            
            self.logger.info(f"Found {len(campaigns)} campaigns with {sum(c['missions_count'] for c in campaigns)} missions")
            
        except Exception as e:
            self.logger.error(f"Error scanning campaigns: {e}")
        
        return campaigns
    
    def get_mission_details(self, mission_path: str) -> Dict[str, any]:
        """Obtiene detalles de una misión específica"""
        try:
            mission_info = {
                'path': mission_path,
                'name': os.path.basename(mission_path),
                'size': os.path.getsize(mission_path),
                'has_dictionary': False,
                'dictionary_path': None,
                'status': 'unknown'
            }
            
            # Verificar si tiene diccionario dentro del .miz
            if zipfile.is_zipfile(mission_path):
                with zipfile.ZipFile(mission_path, 'r') as zip_file:
                    # Buscar el archivo de diccionario
                    dictionary_patterns = [
                        'l10n/DEFAULT/dictionary',
                        'l10n/RUS/dictionary',
                        'l10n/EN/dictionary'
                    ]
                    
                    for pattern in dictionary_patterns:
                        if pattern in zip_file.namelist():
                            mission_info['has_dictionary'] = True
                            mission_info['dictionary_path'] = pattern
                            break
            
            # Verificar si ya está traducida
            translated_file = mission_path.replace('.miz', '.translated.lua')
            if os.path.exists(translated_file):
                mission_info['status'] = 'translated'
            
            # Verificar si está finalizada (empaquetada)
            finalized_dir = os.path.join(os.path.dirname(mission_path), 'finalizado')
            finalized_file = os.path.join(finalized_dir, os.path.basename(mission_path))
            if os.path.exists(finalized_file):
                mission_info['status'] = 'finalized'
            
            return mission_info
            
        except Exception as e:
            self.logger.error(f"Error getting mission details for {mission_path}: {e}")
            return {
                'path': mission_path,
                'name': os.path.basename(mission_path),
                'error': str(e)
            }
    
    def filter_fc_missions(self, missions: List[Dict], include_fc: bool = False) -> List[Dict]:
        """Filtra misiones de Flaming Cliffs si es necesario usando detección mejorada"""
        if include_fc:
            return missions
        
        return [
            mission for mission in missions
            if not self._is_flaming_cliffs_mission(mission.get('name', ''))
        ]
    
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
            return result.is_fc
        except Exception as e:
            logging.error(f"Error en detección FC para '{filename}': {e}")
            return False
    

    
    def validate_dcs_path(self, path: str) -> Tuple[bool, str]:
        """Valida que una ruta sea un directorio válido de campañas DCS"""
        if not os.path.exists(path):
            return False, "El directorio no existe"
        
        if not os.path.isdir(path):
            return False, "La ruta no es un directorio"
        
        # Buscar al menos un archivo .miz
        miz_files = glob.glob(os.path.join(path, "**", "*.miz"), recursive=True)
        if not miz_files:
            return False, "No se encontraron archivos .miz en el directorio"
        
        return True, f"Directorio válido con {len(miz_files)} misiones encontradas"
    
    def get_campaign_statistics(self, dcs_path: str) -> Dict[str, any]:
        """Obtiene estadísticas de las campañas"""
        campaigns = self.scan_campaigns(dcs_path)
        
        total_missions = sum(c['missions_count'] for c in campaigns)
        total_size = 0
        
        for campaign in campaigns:
            for mission in campaign['missions']:
                total_size += mission.get('size', 0)
        
        return {
            'total_campaigns': len(campaigns),
            'total_missions': total_missions,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'campaigns': campaigns
        }