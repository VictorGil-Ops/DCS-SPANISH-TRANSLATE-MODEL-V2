/**
 * Sistema de Ayuda Global - Versión Simplificada
 * Se ejecuta en todas las páginas para manejar el botón principal de ayuda
 */

// Función directa sin clase para evitar conflictos
function setupGlobalHelp() {
    console.log('🌐 Configurando sistema de ayuda global simplificado...');
    
    const openHelp = document.getElementById('openHelp');
    if (!openHelp) {
        console.warn('⚠️ Botón de ayuda global no encontrado');
        return;
    }
    
    console.log('✅ Botón de ayuda global encontrado');
    
    // Agregar el event listener de forma directa y robusta
    openHelp.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('🖱️ CLICK EN BOTÓN DE AYUDA GLOBAL');
        showGlobalHelp();
    });
    
    // También agregar usando un método más directo por si el anterior falla
    openHelp.onclick = function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('🖱️ CLICK ALTERNATIVO EN BOTÓN DE AYUDA GLOBAL');
        showGlobalHelp();
        return false;
    };
    
    console.log('✅ Botón de ayuda global configurado');
}

function showGlobalHelp() {
    console.log('🎯 Mostrando ayuda global...');
    
    // Verificar si ya existe un modal global
    let modal = document.getElementById('globalHelpModal');
    
    if (!modal) {
        console.log('🔨 Creando modal de ayuda global...');
        
        const modalHTML = `
            <div id="globalHelpModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 9999; justify-content: center; align-items: center;">
                <div style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 25px; max-width: 650px; max-height: 85%; overflow-y: auto; margin: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.6);">
                    <header style="margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 10px;">
                        <h2 id="globalHelpTitle" style="color: #60a5fa; font-size: 1.3rem; font-weight: 600; margin: 0;">Resumen General del Sistema</h2>
                    </header>
                    <div id="globalHelpContent" style="color: #e2e8f0; line-height: 1.6; font-size: 0.95rem;">
                        <div style="padding: 20px; text-align: center;">
                            <h2 style="color: #60a5fa; margin-bottom: 25px;">🎮 Sistema de Traducción DCS</h2>
                            <p style="margin-bottom: 25px; color: #e2e8f0; font-size: 1.05rem;">Sistema completo para traducir campañas de DCS World al español de forma automatizada.</p>
                            
                            <div style="text-align: left; max-width: 550px; margin: 0 auto;">
                                <h3 style="color: #fbbf24; margin: 25px 0 15px 0;">📋 Secciones Principales:</h3>
                                <ul style="list-style: none; padding: 0;">
                                    <li style="margin: 15px 0; padding: 15px; background: rgba(30, 41, 59, 0.5); border-radius: 8px; border-left: 4px solid #3b82f6;">
                                        <strong style="color: #60a5fa; font-size: 1.05rem;">🎮 Campañas:</strong> 
                                        <span style="color: #cbd5e1; display: block; margin-top: 5px;">Gestión y traducción automática de campañas DCS. Detección automática, escaneo de misiones y seguimiento del progreso.</span>
                                    </li>
                                    <li style="margin: 15px 0; padding: 15px; background: rgba(30, 41, 59, 0.5); border-radius: 8px; border-left: 4px solid #10b981;">
                                        <strong style="color: #34d399; font-size: 1.05rem;">🤖 Modelos y Presets:</strong> 
                                        <span style="color: #cbd5e1; display: block; margin-top: 5px;">Configuración de IA optimizada por hardware. Presets ligero, balanceado y pesado según tu equipo.</span>
                                    </li>
                                    <li style="margin: 15px 0; padding: 15px; background: rgba(30, 41, 59, 0.5); border-radius: 8px; border-left: 4px solid #f59e0b;">
                                        <strong style="color: #fbbf24; font-size: 1.05rem;">📝 Prompts:</strong> 
                                        <span style="color: #cbd5e1; display: block; margin-top: 5px;">Plantillas especializadas para traducción militar. Contexto específico de aviación y combate.</span>
                                    </li>
                                    <li style="margin: 15px 0; padding: 15px; background: rgba(30, 41, 59, 0.5); border-radius: 8px; border-left: 4px solid #8b5cf6;">
                                        <strong style="color: #a78bfa; font-size: 1.05rem;">🎯 Orquestador:</strong> 
                                        <span style="color: #cbd5e1; display: block; margin-top: 5px;">Control automatizado del proceso completo. Monitoreo en tiempo real y gestión de recursos.</span>
                                    </li>
                                </ul>
                            </div>
                            
                            <div style="margin-top: 30px; padding: 20px; background: rgba(59, 130, 246, 0.1); border-radius: 10px; border-left: 4px solid #3b82f6;">
                                <h4 style="color: #60a5fa; margin: 0 0 15px 0; font-size: 1.1rem;">🚀 Flujo de Trabajo Típico:</h4>
                                <ol style="text-align: left; color: #cbd5e1; padding-left: 25px; margin: 0; line-height: 1.8;">
                                    <li style="margin: 8px 0;"><strong>Configurar:</strong> Selecciona modelo y preset según tu hardware</li>
                                    <li style="margin: 8px 0;"><strong>Detectar:</strong> El sistema encuentra automáticamente las campañas DCS</li>
                                    <li style="margin: 8px 0;"><strong>Procesar:</strong> El Orquestador gestiona la traducción completa</li>
                                    <li style="margin: 8px 0;"><strong>Aplicar:</strong> Usa los archivos traducidos en DCS</li>
                                </ol>
                            </div>
                            
                            <div style="margin-top: 25px; padding: 15px; background: rgba(16, 185, 129, 0.1); border-radius: 8px; border-left: 4px solid #10b981;">
                                <p style="margin: 0; color: #94a3b8; font-size: 0.95rem;">
                                    💡 <em>Navega a cada sección para acceder a las ayudas específicas usando los botones "?" individuales</em>
                                </p>
                            </div>
                        </div>
                    </div>
                    <footer style="margin-top: 20px; text-align: right; border-top: 1px solid #334155; padding-top: 15px;">
                        <button id="globalHelpClose" style="background: #374151; color: #e5e7eb; border: 1px solid #4b5563; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 0.95rem; transition: background-color 0.2s;">Cerrar</button>
                    </footer>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        modal = document.getElementById('globalHelpModal');
        
        // Configurar eventos del modal
        const closeBtn = document.getElementById('globalHelpClose');
        if (closeBtn) {
            closeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('🔴 Cerrando modal por botón cerrar');
                modal.style.display = 'none';
            });
            
            closeBtn.addEventListener('mouseenter', () => {
                closeBtn.style.backgroundColor = '#4b5563';
            });
            
            closeBtn.addEventListener('mouseleave', () => {
                closeBtn.style.backgroundColor = '#374151';
            });
        }
        
        // IMPORTANTE: Solo cerrar con click en el fondo si es específicamente el modal
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                console.log('🔴 Cerrando modal por click en fondo');
                modal.style.display = 'none';
            }
        });
        
        // Prevenir que clicks dentro del contenido cierren el modal
        const modalContent = modal.querySelector('div');
        if (modalContent) {
            modalContent.addEventListener('click', function(e) {
                e.stopPropagation();
            });
        }
        
        // Cerrar con ESC - pero solo si el modal está visible
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal && modal.style.display === 'flex') {
                console.log('🔴 Cerrando modal por tecla ESC');
                modal.style.display = 'none';
            }
        });
    }
    
    // Mostrar el modal y mantenerlo visible
    modal.style.display = 'flex';
    console.log('✅ Modal de ayuda global mostrado y fijado');
    
    // Debug: Verificar que el modal está visible después de un tiempo
    setTimeout(function() {
        if (modal && modal.style.display === 'flex') {
            console.log('✅ Modal sigue visible después de 2 segundos');
        } else {
            console.warn('⚠️ Modal se cerró inesperadamente');
        }
    }, 2000);
}

// Configurar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupGlobalHelp);
} else {
    // El DOM ya está listo
    setupGlobalHelp();
}

// También intentar después de un delay para asegurar que todo esté cargado
setTimeout(setupGlobalHelp, 500);