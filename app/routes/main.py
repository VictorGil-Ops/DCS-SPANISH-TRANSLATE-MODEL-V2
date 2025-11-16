#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rutas principales de la aplicación web
"""
from flask import Blueprint, render_template, request, jsonify, current_app, send_from_directory, abort
import logging
import os
from config.settings import APP_VERSION, TRANSLATIONS_DIR, PRESETS_DIR, PROMPTS_DIR

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Página principal de la aplicación"""
    try:
        # Información de la aplicación
        app_info = {
            'version': APP_VERSION,
            'title': 'DCS Spanish Translate Model V2',
            'description': 'Sistema de traducción automática para campañas de DCS World'
        }
        
        # Información de directorios
        directories_info = {
            'translations_dir': TRANSLATIONS_DIR,
            'presets_dir': PRESETS_DIR, 
            'prompts_dir': PROMPTS_DIR
        }
        
        # Verificar existencia de directorios
        directories_status = {}
        for name, path in directories_info.items():
            directories_status[name] = {
                'path': path,
                'exists': os.path.exists(path),
                'writable': os.access(path, os.W_OK) if os.path.exists(path) else False
            }
        
        return render_template('index.html', 
                             app_info=app_info,
                             directories=directories_status,
                             version=APP_VERSION)
        
    except Exception as e:
        logging.error(f"Error rendering index page: {e}")
        return render_template('error.html', error=str(e)), 500

@main_bp.route('/orchestrator')
def orchestrator():
    """Página del orquestador de traducciones"""
    try:
        return render_template('orchestrator/index.html', version=APP_VERSION)
    except Exception as e:
        logging.error(f"Error rendering orchestrator page: {e}")
        return render_template('error.html', error=str(e), version=APP_VERSION), 500

@main_bp.route('/config')
def config_page():
    """Página de configuración"""
    try:
        return render_template('config.html')
    except Exception as e:
        logging.error(f"Error rendering config page: {e}")
        return render_template('error.html', error=str(e)), 500

@main_bp.route('/help')
def help_page():
    """Página de ayuda"""
    try:
        return render_template('help.html')
    except Exception as e:
        logging.error(f"Error rendering help page: {e}")
        return render_template('error.html', error=str(e)), 500

@main_bp.route('/logs')
def logs_page():
    """Página de visualización de logs"""
    try:
        return render_template('logs.html')
    except Exception as e:
        logging.error(f"Error rendering logs page: {e}")
        return render_template('error.html', error=str(e)), 500

# Manejar URLs mal formadas de API que no tienen el prefijo correcto
@main_bp.route('/orchestratorapi/status')
def handle_malformed_api_status():
    """Maneja URLs mal formadas como /orchestratorapi/status"""
    logging.warning("URL mal formada detectada: /orchestratorapi/status")
    return jsonify({
        'ok': True,
        'status': 'running',
        'message': 'Orquestador funcionando correctamente (URL corregida)',
        'processes': {
            'translation': False,
            'lm_studio': False
        },
        'note': 'Esta URL fue corregida automáticamente'
    })

@main_bp.route('/orchestratorapi/<path:endpoint>')
def handle_malformed_api_routes(endpoint):
    """Maneja cualquier URL mal formada que empiece con /orchestratorapi/"""
    logging.warning(f"URL mal formada detectada: /orchestratorapi/{endpoint}")
    return jsonify({
        'error': 'URL mal formada',
        'received': f'/orchestratorapi/{endpoint}',
        'suggestion': f'Usa /api/{endpoint} en su lugar'
    }), 404

# Manejadores de errores
@main_bp.errorhandler(404)
def not_found_error(error):
    """Maneja errores 404"""
    return render_template('error.html', 
                         error="Página no encontrada",
                         error_code=404), 404

@main_bp.errorhandler(500)  
def internal_error(error):
    """Maneja errores internos del servidor"""
    logging.error(f"Internal server error: {error}")
    return render_template('error.html',
                         error="Error interno del servidor", 
                         error_code=500), 500

# Filtros de templates
@main_bp.app_template_filter('file_exists')
def file_exists_filter(filepath):
    """Filtro para verificar si un archivo existe"""
    return os.path.exists(filepath) if filepath else False

@main_bp.app_template_filter('dir_exists')
def dir_exists_filter(dirpath):
    """Filtro para verificar si un directorio existe"""
    return os.path.isdir(dirpath) if dirpath else False

# Nuevas rutas para las páginas modernas
@main_bp.route('/campaigns')
def campaigns():
    """Página de gestión de campañas"""
    return render_template('campaigns.html', version=APP_VERSION)

@main_bp.route('/models-presets')
def models_presets():
    """Página de modelos y presets"""
    return render_template('models-presets.html', version=APP_VERSION)

@main_bp.route('/prompts')
def prompts():
    """Página de gestión de prompts"""
    return render_template('prompts.html', version=APP_VERSION)

@main_bp.route('/static/README/<filename>')
def serve_readme(filename):
    """Servir archivos de ayuda markdown desde la carpeta README"""
    try:
        # Ruta base del proyecto
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        readme_dir = os.path.join(project_root, 'README')
        
        # Verificar que el archivo existe y es seguro
        if not filename.endswith('.md'):
            abort(404)
            
        file_path = os.path.join(readme_dir, filename)
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            abort(404)
            
        # Verificar que no intenta salir del directorio README
        real_path = os.path.realpath(file_path)
        real_readme_dir = os.path.realpath(readme_dir)
        if not real_path.startswith(real_readme_dir):
            abort(403)
            
        return send_from_directory(readme_dir, filename, mimetype='text/plain; charset=utf-8')
        
    except Exception as e:
        logging.error(f"Error serving README file {filename}: {e}")
        abort(500)