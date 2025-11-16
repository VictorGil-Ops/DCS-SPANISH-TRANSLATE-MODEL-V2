from flask import Blueprint, render_template, jsonify

# Blueprint adicional para modelos (funcionalidad extendida)
models_extended_bp = Blueprint('models_extended', __name__)

@models_extended_bp.route('/dashboard')
def dashboard():
    """Dashboard avanzado de modelos"""
    return render_template('models-presets.html')

@models_extended_bp.route('/api/health')
def health_check():
    """Health check para el módulo de modelos"""
    return jsonify({
        'ok': True,
        'module': 'models_extended', 
        'status': 'healthy',
        'message': 'Módulo de modelos extendido funcionando correctamente'
    })