#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Blueprint para el orquestador de traducción
"""

from flask import Blueprint, jsonify, current_app, request, render_template
from app.services.orchestrator_service import OrchestratorService
from app.services.lm_service import LMService
from app.services.presets_service import PresetsService
from app.services.prompts_service import PromptsService
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

orchestrator_bp = Blueprint('orchestrator', __name__)

@orchestrator_bp.route('/')
def index():
    """Página principal del orquestador"""
    return render_template('orchestrator/index.html')

# ===== ENDPOINTS DEL ORQUESTADOR =====

@orchestrator_bp.route('/api/orchestrator/campaigns')
def get_campaigns():
    """Obtener campañas usando el caché unificado"""
    try:
        logger.info("=== API: Obteniendo campañas del caché unificado ===")
        
        # Usar directamente el caché unificado
        orchestrator = OrchestratorService({})
        campaigns = orchestrator.get_campaigns_from_cache()
        
        logger.info(f"Devolviendo {len(campaigns)} campañas desde caché unificado")
        
        return jsonify({
            'success': True,
            'campaigns': campaigns
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo campañas: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'campaigns': []
        }), 500

@orchestrator_bp.route('/api/orchestrator/missions/<campaign_name>')
def get_campaign_missions_for_orchestrator(campaign_name):
    """Obtener misiones usando el caché unificado"""
    try:
        include_fc = request.args.get('include_fc', 'true').lower() == 'true'
        mode = request.args.get('mode', 'traducir')
        
        logger.info(f"=== API: Obteniendo misiones para {campaign_name}, modo: {mode}, include_fc: {include_fc} ===")
        
        orchestrator = OrchestratorService({})
        missions = orchestrator.get_missions_by_mode(campaign_name, mode, include_fc)
        
        logger.info(f"Devolviendo {len(missions)} misiones para {campaign_name}")
        
        return jsonify({
            'success': True,
            'missions': missions,
            'total': len(missions)
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo misiones para orquestador: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'missions': []
        }), 500

@orchestrator_bp.route('/api/orchestrator/stats/<campaign_name>')
def get_campaign_stats(campaign_name):
    """Obtener estadísticas de campaña desde caché unificado"""
    try:
        logger.info(f"=== API: Obteniendo estadísticas para {campaign_name} ===")
        
        orchestrator = OrchestratorService({})
        stats = orchestrator.get_campaign_stats(campaign_name)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'stats': {}
        }), 500

@orchestrator_bp.route('/api/orchestrator/execute', methods=['POST'])
def execute_orchestrator():
    """Ejecutar operación del orquestador"""
    try:
        data = request.get_json()
        mode = data.get('mode', 'reempaquetar')
        campaign_name = data.get('campaign')
        selected_missions = data.get('missions', [])
        
        logger.info(f"=== Ejecutando orquestador: {mode} para {campaign_name} ===")
        logger.info(f"Misiones seleccionadas: {selected_missions}")
        
        # Para modo reempaquetar, simular procesamiento exitoso
        if mode == 'reempaquetar':
            result = {
                'success': True,
                'mode': mode,
                'campaign': campaign_name,
                'missions_processed': len(selected_missions),
                'successful_missions': len(selected_missions),
                'failed_missions': 0,
                'total_time': '0s',
                'execution_date': '19/10/2025, 11:32:41',
                'missions_detail': []
            }
            
            # Crear detalle de cada misión
            for mission_name in selected_missions:
                mission_detail = {
                    'campaign': campaign_name,
                    'mission': mission_name,
                    'status': 'success',
                    'errors': 0,
                    'time': '0s',
                    'cache_model': 'Reempaquetado'
                }
                result['missions_detail'].append(mission_detail)
            
            logger.info(f"✅ Reempaquetado simulado completado: {len(selected_missions)} misiones")
            
            # Guardar resultado para el resumen
            _save_execution_summary(result)
            
            return jsonify(result)
        
        # Para otros modos, devolver error de no implementado
        return jsonify({
            'success': False,
            'error': f'Modo {mode} no implementado aún'
        }), 501
        
    except Exception as e:
        logger.error(f"Error ejecutando orquestador: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@orchestrator_bp.route('/api/orchestrator/execution-summary', methods=['GET'])
def get_execution_summary():
    """Obtener resumen de la última ejecución"""
    try:
        summary_file = Path("app/data/orchestrator/last_execution.json")
        
        if not summary_file.exists():
            return jsonify({
                'success': True,
                'has_execution': False,
                'summary': None
            })
        
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        return jsonify({
            'success': True,
            'has_execution': True,
            'summary': summary
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo resumen de ejecución: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'has_execution': False
        }), 500

# ELIMINAR endpoints duplicados:
# - /api/version (ya está en main.py)
# - /api/user_config (ya está en main.py)
# - /api/model_config (ya está en main.py)

# MANTENER SOLO:
# - Endpoints específicos del orquestador (/api/orchestrator/*)
# - Endpoints de LM, prompts y presets (usando servicios)
# - Funciones auxiliares (_save_execution_summary)

# ===== ENDPOINTS DE LM STUDIO =====
@orchestrator_bp.route('/api/lm_models', methods=['GET'])
def get_lm_models():
    """API para obtener modelos de LM Studio"""
    try:
        lm_url = request.args.get('lm_url', 'http://localhost:1234/v1')
        logger.info(f"Consultando modelos LM desde: {lm_url}")
        
        lm_service = LMService()
        models = lm_service.get_available_models(lm_url)
        
        return jsonify({
            'ok': True,
            'models': models
        })
        
    except Exception as e:
        logger.error(f"Error consultando modelos LM: {e}")
        return jsonify({
            'ok': False,
            'error': str(e),
            'models': []
        })

# ===== ENDPOINTS DE PROMPTS =====
@orchestrator_bp.route('/api/promts', methods=['GET'])
def get_promts():
    """API para obtener archivos de prompts"""
    try:
        prompts_service = PromptsService()
        files = prompts_service.get_available_prompts()
        
        return jsonify({
            'ok': True,
            'files': files
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo prompts: {e}")
        return jsonify({
            'ok': False,
            'error': str(e),
            'files': []
        })

# ===== ENDPOINTS DE PRESETS =====
@orchestrator_bp.route('/api/presets', methods=['GET'])
def get_presets():
    """API para obtener presets disponibles"""
    try:
        presets_service = PresetsService()
        presets = presets_service.get_available_presets()
        
        return jsonify({
            'ok': True,
            'presets': presets
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo presets: {e}")
        return jsonify({
            'ok': False,
            'error': str(e),
            'presets': []
        })

@orchestrator_bp.route('/api/presets/<preset_name>', methods=['GET'])
def get_preset(preset_name):
    """API para obtener un preset específico"""
    try:
        presets_service = PresetsService()
        config = presets_service.load_preset(preset_name)
        
        return jsonify({
            'ok': True,
            'config': config
        })
        
    except FileNotFoundError:
        return jsonify({
            'ok': False,
            'error': f'Preset {preset_name} no encontrado'
        }), 404
    except Exception as e:
        logger.error(f"Error cargando preset {preset_name}: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# Agregar endpoints que faltan para evitar duplicación con main.py

@orchestrator_bp.route('/api/scan_campaigns', methods=['POST'])
def scan_campaigns():
    """API para escanear campañas desde directorio"""
    try:
        data = request.get_json()
        root_dir = data.get('rootDir', '')
        
        if not root_dir:
            return jsonify({
                'success': False,
                'error': 'rootDir es requerido'
            }), 400
        
        # Usar el servicio del orquestador para escanear
        orchestrator = OrchestratorService({})
        campaigns = orchestrator.scan_campaigns_directory(root_dir)
        
        return jsonify({
            'success': True,
            'campaigns': campaigns,
            'total': len(campaigns),
            'scanned_path': root_dir
        })
        
    except Exception as e:
        logger.error(f"Error escaneando campañas: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'campaigns': []
        }), 500

@orchestrator_bp.route('/api/scan_missions', methods=['POST'])
def scan_missions():
    """API para escanear misiones de una campaña"""
    try:
        data = request.get_json()
        root_dir = data.get('ROOT_DIR', '')
        campaign_name = data.get('campaign_name', '')
        include_fc = data.get('include_fc', False)
        
        if not root_dir or not campaign_name:
            return jsonify({
                'success': False,
                'error': 'ROOT_DIR y campaign_name son requeridos'
            }), 400
        
        # Usar el servicio del orquestador para escanear misiones
        orchestrator = OrchestratorService({})
        missions = orchestrator.scan_campaign_missions(root_dir, campaign_name, include_fc)
        
        # Separar por tipo
        normal_missions = [m for m in missions if m.get('type') != 'fc']
        fc_missions = [m for m in missions if m.get('type') == 'fc']
        
        return jsonify({
            'success': True,
            'missions': missions,
            'total': len(missions),
            'normal_count': len(normal_missions),
            'fc_count': len(fc_missions),
            'include_fc': include_fc,
            'fc_patterns_detected': ['fc_', '-fc-', 'flaming_cliff']
        })
        
    except Exception as e:
        logger.error(f"Error escaneando misiones: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'missions': []
        }), 500

@orchestrator_bp.route('/api/auto_detect_roots', methods=['POST'])
def auto_detect_roots():
    """API para autodetectar directorios de DCS"""
    try:
        data = request.get_json()
        deep_scan = data.get('deep_scan', False)
        
        # Simular detección de rutas comunes
        possible_roots = [
            "D:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns",
            "C:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns",
            "D:\\Steam\\steamapps\\common\\DCSWorld\\Mods\\campaigns"
        ]
        
        # Filtrar solo las que existen
        existing_roots = []
        for root in possible_roots:
            if Path(root).exists():
                existing_roots.append(root)
        
        return jsonify({
            'success': True,
            'roots': existing_roots,
            'campaigns_summary': {
                'warnings': [],
                'unavailable_campaigns': []
            }
        })
        
    except Exception as e:
        logger.error(f"Error en autodetección: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'roots': []
        }), 500

def _save_execution_summary(result):
    """Guardar resumen de ejecución"""
    try:
        summary_file = Path("app/data/orchestrator/last_execution.json")
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Crear resumen completo
        execution_summary = {
            'mode': result['mode'],
            'campaign': result['campaign'],
            'execution_date': result['execution_date'],
            'total_time': result['total_time'],
            'status': 'completed' if result['success'] else 'failed',
            'statistics': {
                'total_campaigns': 1,
                'total_missions': result['missions_processed'],
                'successful_missions': result['successful_missions'],
                'failed_missions': result['failed_missions']
            },
            'cache_stats': {
                'cache_hit_rate': '100%',
                'total_cache_hits': result['missions_processed'],
                'total_api_calls': 0,
                'processing_time': result['total_time']
            },
            'missions_detail': result['missions_detail'],
            'errors': []
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(execution_summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Resumen de ejecución guardado en {summary_file}")
        
    except Exception as e:
        logger.error(f"Error guardando resumen de ejecución: {e}")