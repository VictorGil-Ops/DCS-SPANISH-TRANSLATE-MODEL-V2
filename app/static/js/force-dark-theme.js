/**
 * Forzar Tema Oscuro - JavaScript Override
 * Aplica estilos dinámicamente para asegurar tema oscuro
 */

// Aplicar tema oscuro inmediatamente al cargar
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎨 Aplicando tema oscuro forzado...');
    
    // Forzar tema oscuro en body
    forceDarkTheme();
    
    // Observar cambios en el DOM para aplicar tema a nuevos elementos
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        applyDarkThemeToElement(node);
                    }
                });
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    console.log('✅ Tema oscuro aplicado correctamente');
});

function forceDarkTheme() {
    // Aplicar al body
    document.body.style.background = 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)';
    document.body.style.color = '#e2e8f0';
    document.body.style.minHeight = '100vh';
    
    // Aplicar al html
    document.documentElement.style.background = 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)';
    document.documentElement.style.color = '#e2e8f0';
    
    // Aplicar a todos los elementos existentes
    const allElements = document.querySelectorAll('*');
    allElements.forEach(applyDarkThemeToElement);
}

function applyDarkThemeToElement(element) {
    if (!element || !element.style) return;
    
    // Contenedores principales
    if (element.matches('.container, .container-fluid, .row, [class*="col-"]')) {
        element.style.background = 'transparent';
        element.style.color = '#e2e8f0';
    }
    
    // Cards
    if (element.matches('.card, .card-body, .card-header, .card-footer')) {
        element.style.background = 'linear-gradient(135deg, #334155 0%, #475569 100%)';
        element.style.color = '#e2e8f0';
        element.style.borderColor = 'rgba(148, 163, 184, 0.2)';
    }
    
    // Tablas
    if (element.matches('.table thead th')) {
        element.style.background = 'linear-gradient(135deg, #1e293b 0%, #334155 100%)';
        element.style.color = '#e2e8f0';
        element.style.borderColor = 'rgba(148, 163, 184, 0.2)';
    }
    
    if (element.matches('.table tbody td')) {
        element.style.background = 'rgba(30, 41, 59, 0.2)';
        element.style.color = '#cbd5e1';
        element.style.borderColor = 'rgba(148, 163, 184, 0.1)';
    }
    
    // Botones
    if (element.matches('.btn:not([class*="btn-"])')) {
        element.style.background = 'linear-gradient(135deg, #374151, #4b5563)';
        element.style.borderColor = 'rgba(148, 163, 184, 0.3)';
        element.style.color = '#e2e8f0';
    }
    
    // Badges
    if (element.matches('.badge:not([class*="bg-"]):not([class*="text-bg-"])')) {
        element.style.background = 'linear-gradient(135deg, #3b82f6, #1d4ed8)';
        element.style.color = 'white';
    }
    
    // Inputs
    if (element.matches('input, textarea, select, .form-control, .form-select')) {
        element.style.background = 'rgba(30, 41, 59, 0.8)';
        element.style.color = '#e2e8f0';
        element.style.borderColor = 'rgba(148, 163, 184, 0.3)';
    }
    
    // Modales
    if (element.matches('.modal-content')) {
        element.style.background = 'linear-gradient(135deg, #334155 0%, #475569 100%)';
        element.style.color = '#e2e8f0';
        element.style.borderColor = 'rgba(148, 163, 184, 0.3)';
    }
    
    if (element.matches('.modal-header')) {
        element.style.background = 'linear-gradient(135deg, #1e293b 0%, #334155 100%)';
        element.style.borderColor = 'rgba(148, 163, 184, 0.2)';
    }
    
    // Elementos con fondo blanco forzado
    if (element.matches('.bg-white, .bg-light')) {
        element.style.background = 'rgba(30, 41, 59, 0.6)';
        element.style.color = '#e2e8f0';
    }
    
    // Texto general
    if (element.matches('h1, h2, h3, h4, h5, h6, p, span, div, td, th, li, a:not(.btn)')) {
        if (!element.style.color || element.style.color === 'rgb(0, 0, 0)' || element.style.color === 'black') {
            element.style.color = '#e2e8f0';
        }
    }
    
    // Alertas con estados específicos
    if (element.matches('.loading-state, .empty-state')) {
        element.style.background = 'rgba(30, 41, 59, 0.4)';
        element.style.color = '#e2e8f0';
        element.style.borderColor = 'rgba(148, 163, 184, 0.2)';
    }
}

// Función para forzar recarga de estilos
function forceStyleRefresh() {
    console.log('🔄 Forzando recarga de estilos...');
    
    // Recargar todas las hojas de estilo
    const stylesheets = document.querySelectorAll('link[rel="stylesheet"]');
    stylesheets.forEach(function(link) {
        const href = link.href;
        link.href = href + (href.includes('?') ? '&' : '?') + 'v=' + Date.now();
    });
    
    // Aplicar tema después de un breve delay
    setTimeout(forceDarkTheme, 100);
}

// Exportar funciones para uso global
window.forceDarkTheme = forceDarkTheme;
window.forceStyleRefresh = forceStyleRefresh;
window.applyDarkThemeToElement = applyDarkThemeToElement;

console.log('🎨 Sistema de tema oscuro forzado cargado');