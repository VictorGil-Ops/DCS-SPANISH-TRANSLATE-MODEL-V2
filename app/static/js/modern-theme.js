/**
 * JavaScript para el tema moderno del DCS Traductor Español
 */

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎨 Tema moderno inicializado');
    
    // Animaciones de entrada
    initFadeInAnimations();
    
    // Estado de LM Studio
    checkLMStudioStatus();
    
    // Banner de actualización
    checkUpdateBanner();
    
    // Configurar botones de ayuda y servidor
    setupGlobalButtons();
    
    // Configurar botón de actualización
    setupUpdateButton();
});

/**
 * Inicializar animaciones de entrada
 */
function initFadeInAnimations() {
    const elements = document.querySelectorAll('.fade-in');
    
    elements.forEach((element, index) => {
        element.style.animationDelay = `${index * 0.1}s`;
    });
}

/**
 * Verificar estado de LM Studio
 */
async function checkLMStudioStatus() {
    // Buscar el elemento que contiene "LM Studio" de forma más compatible
    const statusElements = document.querySelectorAll('.status-indicator');
    let statusElement = null;
    
    for (let element of statusElements) {
        if (element.textContent && element.textContent.includes('LM Studio')) {
            statusElement = element;
            break;
        }
    }
    
    if (!statusElement) return;
    
    try {
        const response = await fetch('/api/lm_models?lm_url=http://localhost:1234/v1');
        const result = await response.json();
        
        if (result.ok && result.models && result.models.length > 0) {
            statusElement.className = 'status-indicator status-success mb-2';
            statusElement.innerHTML = '<span>🟢</span><span>LM Studio: Conectado (' + result.models.length + ' modelos)</span>';
        } else {
            statusElement.className = 'status-indicator status-warning mb-2';
            statusElement.innerHTML = '<span>🟡</span><span>LM Studio: Sin modelos</span>';
        }
    } catch (error) {
        statusElement.className = 'status-indicator status-error mb-2';
        statusElement.innerHTML = '<span>🔴</span><span>LM Studio: Desconectado</span>';
    }
}

/**
 * Verificar banner de actualización
 */
async function checkUpdateBanner() {
    try {
        // Verificar si está en modo de prueba
        const urlParams = new URLSearchParams(window.location.search);
        const testMode = urlParams.get('test') === 'true';
        
        const apiUrl = testMode ? '/api/update_info?test=true' : '/api/update_info';
        const response = await fetch(apiUrl);
        const result = await response.json();
        
        console.log('Update info response:', result); // Debug
        
        if (result.ok && result.is_newer) {
            const banner = document.getElementById('updateBanner');
            const latestVer = document.getElementById('latestVer');
            const updateLink = document.getElementById('updateLink');
            
            if (banner && latestVer && updateLink) {
                const reason = result.by && result.by.version_file ? 'archivo VERSION' :
                              result.by && result.by.git_head ? 'commits nuevos' : 'actualización disponible';
                              
                latestVer.textContent = result.latest_version ? 
                    `${result.latest_version} (${reason})` : `(${reason})`;
                updateLink.href = result.repo_url;
                banner.classList.remove('hidden');
                
                console.log('Banner de actualización mostrado'); // Debug
            }
        } else {
            // Ocultar banner si no hay actualizaciones
            const banner = document.getElementById('updateBanner');
            if (banner) {
                banner.classList.add('hidden');
            }
            console.log('No hay actualizaciones disponibles'); // Debug
        }
    } catch (error) {
        console.log('No se pudo verificar actualizaciones:', error);
    }
}

/**
 * Configurar botones globales
 */
function setupGlobalButtons() {
    // Botón de ayuda - DESHABILITADO para usar sistema global
    const helpButton = document.getElementById('openHelp');
    if (helpButton) {
        // NO configurar event listener aquí - lo maneja global-help-ultra.js
        console.log('🔧 Botón de ayuda encontrado - delegando a sistema global');
    }
    
    // Botón de parar servidor - IMPLEMENTACIÓN GLOBAL
    const stopButton = document.getElementById('stopServer');
    if (stopButton) {
        stopButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Intentar usar la función específica del orquestador si existe
            if (typeof window.orchestrator !== 'undefined' && 
                typeof window.orchestrator.stopServer === 'function') {
                console.log('🔧 Usando función stopServer del orquestador');
                window.orchestrator.stopServer();
                return;
            }
            
            // Implementación global para parar el servidor
            console.log('🔧 Usando implementación global de stopServer');
            stopServerGlobal();
        });
    }
    
    // Botón actualizar ahora (deshabilitado - endpoint no disponible)
    const updateNowButton = document.getElementById('btnUpdateNow');
    if (updateNowButton) {
        updateNowButton.addEventListener('click', function() {
            alert('Funcionalidad de actualización automática no disponible en esta versión.');
        });
    }
}

/**
 * Utilidades para efectos visuales
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `status-indicator status-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 2rem;
        right: 2rem;
        z-index: 1000;
        animation: fadeIn 0.3s ease-out;
    `;
    notification.innerHTML = `<span>${getTypeIcon(type)}</span><span>${message}</span>`;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease-out forwards';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function getTypeIcon(type) {
    const icons = {
        success: '✅',
        warning: '⚠️',
        error: '❌',
        info: 'ℹ️'
    };
    return icons[type] || icons.info;
}

/**
 * Configurar botón de actualización
 */
function setupUpdateButton() {
    const btnUpdateNow = document.getElementById('btnUpdateNow');
    if (btnUpdateNow) {
        btnUpdateNow.addEventListener('click', doUpdateNow);
    }
}

/**
 * Ejecutar actualización del sistema
 */
async function doUpdateNow() {
    const btn = document.getElementById('btnUpdateNow');
    const msg = document.getElementById('updMsg');
    
    if (!confirm('¿Actualizar ahora desde el repositorio? Se mantendrán los directorios de configuración y datos.')) {
        return;
    }
    
    if (btn) btn.disabled = true;
    if (msg) msg.textContent = 'Actualizando...';
    
    try {
        const response = await fetch('/api/update_now', { method: 'POST' });
        const result = await response.json();
        
        if (result.ok) {
            if (msg) msg.textContent = `Actualización completada a ${result.new_version}. Recargando...`;
            setTimeout(() => location.reload(), 2000);
        } else {
            if (msg) msg.textContent = result.error || 'Fallo en la actualización';
            if (btn) btn.disabled = false;
        }
        
    } catch (error) {
        console.error('Error actualizando:', error);
        if (msg) msg.textContent = 'Error en la petición de actualización.';
        if (btn) btn.disabled = false;
    }
}

/**
 * Función global para parar el servidor
 * Funciona desde cualquier página de la aplicación
 */
function stopServerGlobal() {
    const stopButton = document.getElementById('stopServer');
    
    if (confirm('¿Estás seguro de que quieres parar el servidor Flask?')) {
        console.log('🛑 Deteniendo servidor desde interfaz global...');
        
        // Cambiar texto del botón para indicar que se está procesando
        if (stopButton) {
            const originalText = stopButton.innerHTML;
            stopButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deteniendo...';
            stopButton.disabled = true;
            
            // Función para restaurar botón en caso de error
            const restoreButton = () => {
                stopButton.innerHTML = originalText;
                stopButton.disabled = false;
            };
            
            // Realizar petición para detener el servidor
            fetch('/api/shutdown', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            }).then(response => {
                if (response.ok) {
                    console.log('✅ Servidor detenido exitosamente');
                    stopButton.innerHTML = '<i class="fas fa-check"></i> Servidor Detenido';
                    
                    // Mostrar mensaje de confirmación
                    showNotification('Servidor detenido correctamente', 'success');
                    
                    // Mostrar mensaje simple sin pregunta sobre cerrar pestaña
                    setTimeout(() => {
                        alert('El servidor se ha detenido correctamente.');
                    }, 1000);
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }).catch(error => {
                console.error('❌ Error al detener el servidor:', error);
                restoreButton();
                
                // Mostrar error al usuario
                showNotification(`Error al detener servidor: ${error.message}`, 'error');
                alert(`Error al detener el servidor:\n${error.message}\n\nVerifica la consola para más detalles.`);
            });
        } else {
            // Fallback si no hay botón (caso edge)
            fetch('/api/shutdown', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            }).then(() => {
                showNotification('Servidor detenido correctamente', 'success');
                console.log('✅ Servidor detenido (sin botón UI)');
            }).catch(error => {
                console.error('❌ Error al detener servidor:', error);
                showNotification(`Error: ${error.message}`, 'error');
            });
        }
    }
}