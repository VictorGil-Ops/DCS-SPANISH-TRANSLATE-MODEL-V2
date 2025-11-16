#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inicialización del paquete app
"""
from flask import Flask
import logging
from config.settings import FLASK_CONFIG, LOGGING_CONFIG

def create_app():
    """Factory function para crear la aplicación Flask"""
    app = Flask(__name__)
    
    # Configurar la aplicación
    app.config.update(FLASK_CONFIG)
    
    # Configurar logging
    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG['level']),
        format=LOGGING_CONFIG['format'],
        handlers=[
            logging.FileHandler(LOGGING_CONFIG['file_path'], encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    
    # Registrar blueprints usando la función centralizada
    from app.routes import register_blueprints
    register_blueprints(app)
    
    return app