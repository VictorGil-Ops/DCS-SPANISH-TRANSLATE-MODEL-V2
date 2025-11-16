#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de rutas para la aplicación Flask
"""

from .main import main_bp
from .api import api_bp

# Importar blueprints simples
from .campaigns import campaigns_bp

# Importar blueprints modulares adicionales
from .modules.campaigns_extended import campaigns_extended_bp
from .modules.models_extended import models_extended_bp

# Registrar blueprints - MANTIENE toda la funcionalidad existente
blueprints = [
    (main_bp, None),  # Sin prefijo URL - FUNCIONALIDAD ORIGINAL
    (api_bp, '/api'),  # Con prefijo /api - FUNCIONALIDAD ORIGINAL
    # Blueprints simples
    (campaigns_bp, '/campaigns'),
    # Blueprints extendidos (FUNCIONALIDAD ADICIONAL)
    (campaigns_extended_bp, '/campaigns-extended'),
    (models_extended_bp, '/models-extended')
]

def register_blueprints(app):
    """Registra todos los blueprints en la aplicación Flask"""
    for blueprint, url_prefix in blueprints:
        app.register_blueprint(blueprint, url_prefix=url_prefix)