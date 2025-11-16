"""
Servicio para interactuar con LM Studio
"""
import logging
from typing import List, Dict, Any
from .lm_studio import LMStudio
from config.settings import LM_CONFIG

logger = logging.getLogger(__name__)

class LMService:
    """Servicio que encapsula la funcionalidad de LM Studio"""
    
    def __init__(self):
        self.lm_studio = None
    
    def get_available_models(self, lm_url: str = None) -> List[Dict[str, Any]]:
        """
        Obtiene los modelos disponibles desde LM Studio
        
        Args:
            lm_url: URL base de LM Studio (opcional, usa configuración por defecto si no se proporciona)
            
        Returns:
            Lista de modelos disponibles
        """
        try:
            # Usar URL proporcionada o la configuración por defecto
            url = lm_url or LM_CONFIG['DEFAULT_URL']
            # Crear instancia de LMStudio con la URL proporcionada
            self.lm_studio = LMStudio(base_url=url)
            
            # Obtener modelos disponibles
            models = self.lm_studio.get_available_models()
            
            logger.info(f"Encontrados {len(models)} modelos disponibles en LM Studio")
            
            return models
            
        except Exception as e:
            logger.error(f"Error obteniendo modelos de LM Studio: {e}")
            return []
    
    def check_model_status(self, model_name: str, lm_url: str = None) -> bool:
        """
        Verifica si un modelo específico está cargado en LM Studio
        
        Args:
            model_name: Nombre del modelo a verificar
            lm_url: URL base de LM Studio (opcional, usa configuración por defecto si no se proporciona)
            
        Returns:
            True si el modelo está cargado, False en caso contrario
        """
        try:
            # Usar URL proporcionada o la configuración por defecto
            url = lm_url or LM_CONFIG['DEFAULT_URL']
            self.lm_studio = LMStudio(base_url=url)
            return self.lm_studio.check_model_loaded(model_name)
            
        except Exception as e:
            logger.error(f"Error verificando estado del modelo {model_name}: {e}")
            return False