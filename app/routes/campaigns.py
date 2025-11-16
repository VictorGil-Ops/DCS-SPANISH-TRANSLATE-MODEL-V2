from flask import Blueprint, render_template, jsonify, request
import logging
from app.services.campaign_manager import CampaignManager
from app.services.mission_cache_manager import mission_cache_manager

campaigns_bp = Blueprint("campaigns", __name__)
logger = logging.getLogger(__name__)

campaign_manager = CampaignManager()

@campaigns_bp.route("/")
def index():
    try:
        campaigns = campaign_manager.get_campaigns_summary()
        return render_template("campaigns.html", campaigns=campaigns)
    except Exception as e:
        logger.error(f"Error obteniendo campañas: {e}")
        return render_template("campaigns.html", campaigns=[], error=str(e))

@campaigns_bp.route("/api/campaigns")
def api_campaigns():
    """API: Obtener resumen de todas las campañas"""
    try:
        campaigns = campaign_manager.get_campaigns_summary()
        return jsonify({
            "ok": True,
            "campaigns": [campaign.__dict__ for campaign in campaigns]
        })
    except Exception as e:
        logger.error(f"Error obteniendo campañas via API: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/campaigns/<campaign_name>/missions")
def api_campaign_missions(campaign_name):
    """API: Obtener misiones de una campaña específica"""
    try:
        missions = campaign_manager.get_campaign_missions(campaign_name)
        return jsonify({
            "ok": True,
            "campaign": campaign_name,
            "missions": [mission.__dict__ for mission in missions]
        })
    except Exception as e:
        logger.error(f"Error obteniendo misiones de {campaign_name}: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/campaigns/<campaign_name>/missions/<mission_name>/delete", methods=["POST"])
def api_delete_mission(campaign_name, mission_name):
    """API: Eliminar una misión"""
    try:
        success = campaign_manager.delete_mission(campaign_name, mission_name)
        if success:
            return jsonify({
                "ok": True,
                "message": f"Misión {mission_name} eliminada correctamente"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "No se pudo eliminar la misión"
            }), 400
    except Exception as e:
        logger.error(f"Error eliminando misión {mission_name}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@campaigns_bp.route("/api/campaigns/<campaign_name>/missions/<mission_name>/redeploy", methods=["POST"])
def api_redeploy_mission(campaign_name, mission_name):
    """API: Redesplegar misión desde backup"""
    try:
        data = request.get_json()
        target_path = data.get('target_path')
        
        if not target_path:
            return jsonify({
                "ok": False,
                "error": "target_path es requerido"
            }), 400
        
        success = campaign_manager.redeploy_from_backup(campaign_name, mission_name, target_path)
        if success:
            return jsonify({
                "ok": True,
                "message": f"Misión {mission_name} redesplegada desde backup"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "No se pudo redesplegar la misión"
            }), 400
    except Exception as e:
        logger.error(f"Error redesplegando misión {mission_name}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@campaigns_bp.route("/api/cache")
def api_cache_info():
    """API: Información del cache"""
    try:
        campaign_filter = request.args.get('campaign')
        cache_info = campaign_manager.get_cache_info(campaign_filter)
        return jsonify({
            "ok": True,
            "cache": cache_info
        })
    except Exception as e:
        logger.error(f"Error obteniendo info del cache: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/cache/compact", methods=["POST"])
def api_compact_cache():
    """API: Compactar cache"""
    try:
        stats = campaign_manager.compact_cache()
        return jsonify({
            "ok": True,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error compactando cache: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/mission-caches")
def api_mission_caches():
    """API: Listar todos los caches de misión"""
    try:
        logger.info("🎯 Iniciando obtención de caches de misión...")
        mission_caches = mission_cache_manager.get_all_mission_caches()
        logger.info(f"🎯 Obtenidos {len(mission_caches)} caches de misión")
        
        if mission_caches:
            logger.info(f"🎯 Primer cache: {mission_caches[0]}")
        
        return jsonify({
            "ok": True,
            "mission_caches": mission_caches,
            "total": len(mission_caches)
        })
    except Exception as e:
        logger.error(f"❌ Error obteniendo caches de misión: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/mission-cache/<campaign>/<mission>")
def api_get_mission_cache(campaign, mission):
    """API: Obtener cache de una misión específica"""
    try:
        cache_data = mission_cache_manager.load_mission_cache(campaign, mission)
        return jsonify({
            "ok": True,
            "campaign": campaign,
            "mission": mission,
            "cache": cache_data,
            "entries_count": len(cache_data.get('entries', {}))
        })
    except Exception as e:
        logger.error(f"Error obteniendo cache de {campaign}/{mission}: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/mission-cache/<campaign>/<mission>", methods=["POST"])
def api_update_mission_cache(campaign, mission):
    """API: Actualizar cache de una misión"""
    try:
        data = request.get_json()
        
        if 'translation' in data:
            # Añadir nueva traducción
            success = mission_cache_manager.add_translation_to_mission(
                campaign, mission,
                data['translation']['original'],
                data['translation']['translated'],
                data['translation'].get('context')
            )
        elif 'cache_data' in data:
            # Actualizar cache completo
            success = mission_cache_manager.save_mission_cache(
                campaign, mission, data['cache_data']
            )
        else:
            return jsonify({"ok": False, "error": "Datos inválidos"}), 400
        
        return jsonify({
            "ok": success,
            "message": "Cache actualizado correctamente" if success else "Error actualizando cache"
        })
    except Exception as e:
        logger.error(f"Error actualizando cache de {campaign}/{mission}: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/sync/mission/<campaign>/<mission>", methods=["POST"])
def api_sync_mission_cache(campaign, mission):
    """API: Sincronizar cache de misión con el global"""
    try:
        success, synced_count = mission_cache_manager.sync_mission_to_global(campaign, mission)
        return jsonify({
            "ok": success,
            "synced_entries": synced_count,
            "message": f"Sincronizadas {synced_count} entradas" if success else "Error en sincronización"
        })
    except Exception as e:
        logger.error(f"Error sincronizando {campaign}/{mission}: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/sync/all", methods=["POST"])
def api_sync_all_caches():
    """API: Sincronizar todos los caches de misión"""
    try:
        success, total_synced = mission_cache_manager.sync_all_to_global()
        return jsonify({
            "ok": success,
            "total_synced": total_synced,
            "message": f"Sincronizadas {total_synced} entradas en total" if success else "Error en sincronización"
        })
    except Exception as e:
        logger.error(f"Error sincronizando todos los caches: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/compact/mission/<campaign>/<mission>", methods=["POST"])
def api_compact_mission_cache(campaign, mission):
    """API: Compactar cache de una misión"""
    try:
        success, duplicates_removed = mission_cache_manager.compact_mission_cache(campaign, mission)
        return jsonify({
            "ok": success,
            "duplicates_removed": duplicates_removed,
            "message": f"Eliminados {duplicates_removed} duplicados" if success else "Error compactando"
        })
    except Exception as e:
        logger.error(f"Error compactando cache de {campaign}/{mission}: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/update-translation/<campaign>/<mission>", methods=["POST"])
def api_update_translation(campaign, mission):
    """API: Actualizar una traducción específica"""
    try:
        data = request.json
        key = data.get('key')
        translation = data.get('translation')
        context = data.get('context', '')
        
        if not key or not translation:
            return jsonify({"ok": False, "error": "Clave y traducción son requeridas"})
        
        success = mission_cache_manager.update_translation(campaign, mission, key, translation, context)
        
        return jsonify({
            "ok": success,
            "message": "Traducción actualizada" if success else "Error actualizando traducción"
        })
    except Exception as e:
        logger.error(f"Error actualizando traducción {campaign}/{mission}: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/api/update-multiple-translations/<campaign>/<mission>", methods=["POST"])
def api_update_multiple_translations(campaign, mission):
    """API: Actualizar múltiples traducciones"""
    try:
        data = request.json
        updates = data.get('updates', {})
        
        if not updates:
            return jsonify({"ok": False, "error": "No hay actualizaciones para procesar"})
        
        success, count = mission_cache_manager.update_multiple_translations(campaign, mission, updates)
        
        return jsonify({
            "ok": success,
            "updated_count": count,
            "message": f"{count} traducciones actualizadas" if success else "Error actualizando traducciones"
        })
    except Exception as e:
        logger.error(f"Error actualizando múltiples traducciones {campaign}/{mission}: {e}")
        return jsonify({"ok": False, "error": str(e)})

@campaigns_bp.route("/test")
def test():
    return jsonify({"ok": True, "message": "Campaigns working"})
