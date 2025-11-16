from flask import Blueprint, render_template, jsonify

# Blueprint adicional para campañas (no reemplaza funcionalidad existente)
campaigns_extended_bp = Blueprint('campaigns_extended', __name__)

@campaigns_extended_bp.route('/dashboard')
def dashboard():
    """Dashboard avanzado de campañas (funcionalidad adicional)"""
    return render_template('campaigns.html')

@campaigns_extended_bp.route('/api/health')
def health_check():
    """Health check para el módulo de campañas"""
    return jsonify({
        'ok': True,
        'module': 'campaigns_extended',
        'status': 'healthy',
        'message': 'Módulo de campañas extendido funcionando correctamente'
    })