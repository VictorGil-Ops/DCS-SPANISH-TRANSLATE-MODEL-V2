/**
 * Sistema de Ayuda Global - Versión Ultra Robusta
 * Se ejecuta en todas las páginas para manejar el botón principal de ayuda
 */

let globalHelpModalVisible = false;
let globalHelpModalElement = null;

// Función para detectar la página actual
function getCurrentSection() {
    const path = window.location.pathname;
    
    if (path.includes('/campaigns') || path.includes('/campañas')) {
        return 'campaigns';
    } else if (path.includes('/models-presets') || path.includes('/modelos-presets')) {
        return 'models-presets';
    } else if (path.includes('/prompts')) {
        return 'prompts';
    } else if (path.includes('/orchestrator') || path.includes('/orquestador')) {
        return 'orchestrator';
    } else if (path === '/' || path.includes('/index')) {
        return 'home';
    }
    
    return 'general';
}

// Función directa sin clase para evitar conflictos
function setupGlobalHelp() {
    console.log('🌐 SETUP: Configurando sistema de ayuda global...');
    
    const openHelp = document.getElementById('openHelp');
    if (!openHelp) {
        console.warn('⚠️ SETUP: Botón de ayuda global NO encontrado');
        return false;
    }
    
    console.log('✅ SETUP: Botón de ayuda global encontrado:', openHelp);
    
    // MÉTODO MÁS SIMPLE: Solo remover listeners existentes y configurar nuevo
    openHelp.removeEventListener('click', handleHelpClick);
    openHelp.addEventListener('click', handleHelpClick);
    
    // También configurar onclick como backup
    openHelp.onclick = handleHelpClick;
    
    console.log('✅ SETUP: Event listeners configurados correctamente');
    return true;
}

// Función separada para manejar el click
function handleHelpClick(event) {
    console.log('🖱️ CLICK: Detectado click en botón de ayuda');
    
    if (event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
    }
    
    const section = getCurrentSection();
    console.log('🎯 CLICK: Sección detectada:', section);
    
    forceShowGlobalHelp(section);
    
    return false;
}

// Función global accesible desde consola para testing
window.testHelp = function() {
    console.log('🧪 TEST: Ejecutando función de ayuda manualmente...');
    const section = getCurrentSection();
    forceShowGlobalHelp(section);
};

// Función para forzar reconfiguración
window.fixHelpButton = function() {
    console.log('🔧 FIX: Reconfigurando botón de ayuda...');
    setupGlobalHelp();
};

// Función para generar contenido específico por sección
function getSectionContent(section) {
    const contents = {
        'campaigns': {
            title: '🎮 Sección: Campañas',
            subtitle: 'Gestión y traducción de campañas DCS',
            content: `
                <div style="text-align: left;">
                    <h3 style="color: #fbbf24; margin: 20px 0 15px 0;">📋 ¿Qué es la sección de Campañas?</h3>
                    <p style="color: #cbd5e1; line-height: 1.6;">
                        Esta sección te permite gestionar las campañas de DCS World instaladas en tu sistema y controlar su proceso de traducción al español.
                    </p>
                    
                    <h4 style="color: #60a5fa; margin: 25px 0 15px 0;">🔍 Funcionalidades principales:</h4>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Detección automática:</strong> Encuentra todas las campañas instaladas en DCS</li>
                        <li><strong>Estado de traducción:</strong> Muestra qué campañas están traducidas, en proceso o pendientes</li>
                        <li><strong>Información detallada:</strong> Número de misiones, archivos y estado de cada campaña</li>
                        <li><strong>Control por misión:</strong> Permite traducir misiones individuales o campañas completas</li>
                        <li><strong>Historial de cambios:</strong> Tracking de modificaciones y versiones</li>
                    </ul>
                    
                    <h4 style="color: #34d399; margin: 25px 0 15px 0;">🎯 Estados de las campañas:</h4>
                    <div style="padding-left: 15px;">
                        <div style="margin: 10px 0; padding: 10px; background: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e; border-radius: 4px;">
                            <strong style="color: #22c55e;">✅ Traducida:</strong> <span style="color: #cbd5e1;">Campaña completamente traducida y lista para usar</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(245, 158, 11, 0.1); border-left: 3px solid #f59e0b; border-radius: 4px;">
                            <strong style="color: #fbbf24;">⏳ En Proceso:</strong> <span style="color: #cbd5e1;">Traducción en curso o parcialmente completada</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(148, 163, 184, 0.1); border-left: 3px solid #94a3b8; border-radius: 4px;">
                            <strong style="color: #94a3b8;">⭕ Pendiente:</strong> <span style="color: #cbd5e1;">Sin traducir, disponible para procesar</span>
                        </div>
                    </div>
                    
                    <div style="margin-top: 25px; padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 4px solid #3b82f6;">
                        <h5 style="color: #60a5fa; margin: 0 0 10px 0;">💡 Consejo:</h5>
                        <p style="color: #cbd5e1; margin: 0; font-size: 0.95rem;">
                            Usa esta sección para monitorear el progreso de tus traducciones y gestionar qué campañas quieres procesar. 
                            Desde aquí puedes ver estadísticas detalladas y acceder directamente al editor de traducciones.
                        </p>
                    </div>
                </div>
            `
        },
        'models-presets': {
            title: '🤖 Sección: Modelos y Presets',
            subtitle: 'Configuración de IA y optimización por hardware',
            content: `
                <div style="text-align: left;">
                    <h3 style="color: #fbbf24; margin: 20px 0 15px 0;">🛠️ ¿Qué es la sección de Modelos y Presets?</h3>
                    <p style="color: #cbd5e1; line-height: 1.6;">
                        Aquí configuras el "cerebro" del sistema de traducción: qué modelo de IA usar y cómo optimizarlo según tu hardware.
                    </p>
                    
                    <h4 style="color: #60a5fa; margin: 25px 0 15px 0;">🧠 Modelos de IA:</h4>
                    <p style="color: #e2e8f0; line-height: 1.6; margin-bottom: 15px;">
                        Los modelos son redes neuronales entrenadas para traducir. Cada uno tiene diferentes características:
                    </p>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Tamaño:</strong> Más grande = mejor calidad, pero requiere más RAM</li>
                        <li><strong>Velocidad:</strong> Modelos pequeños son más rápidos</li>
                        <li><strong>Especialización:</strong> Algunos están optimizados para texto técnico/militar</li>
                        <li><strong>Quantización:</strong> Optimización para reducir uso de memoria</li>
                    </ul>
                    
                    <h4 style="color: #34d399; margin: 25px 0 15px 0;">⚙️ Presets de configuración:</h4>
                    <div style="padding-left: 15px;">
                        <div style="margin: 10px 0; padding: 10px; background: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e; border-radius: 4px;">
                            <strong style="color: #22c55e;">🪶 Ligero:</strong> <span style="color: #cbd5e1;">Para equipos básicos (8-16GB RAM). Rápido pero calidad estándar.</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3b82f6; border-radius: 4px;">
                            <strong style="color: #60a5fa;">⚖️ Balanceado:</strong> <span style="color: #cbd5e1;">Para equipos medios (16-32GB RAM). Equilibrio entre calidad y velocidad.</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(139, 92, 246, 0.1); border-left: 3px solid #8b5cf6; border-radius: 4px;">
                            <strong style="color: #a78bfa;">💪 Pesado:</strong> <span style="color: #cbd5e1;">Para equipos potentes (32GB+ RAM). Máxima calidad de traducción.</span>
                        </div>
                    </div>
                    
                    <h4 style="color: #f59e0b; margin: 25px 0 15px 0;">🎛️ Parámetros técnicos:</h4>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Temperature:</strong> Creatividad vs consistencia (0.1 = conservador, 0.8 = creativo)</li>
                        <li><strong>Top P/K:</strong> Control de vocabulario usado por el modelo</li>
                        <li><strong>Max Tokens:</strong> Longitud máxima de respuesta del modelo</li>
                        <li><strong>Batch Size:</strong> Cuántas traducciones procesar simultáneamente</li>
                    </ul>
                    
                    <div style="margin-top: 25px; padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 4px solid #3b82f6;">
                        <h5 style="color: #60a5fa; margin: 0 0 10px 0;">💡 Consejo:</h5>
                        <p style="color: #cbd5e1; margin: 0; font-size: 0.95rem;">
                            Haz clic en cualquier tarjeta de modelo para ver instrucciones detalladas de instalación en LM Studio. 
                            Empieza con el preset "Balanceado" y ajusta según el rendimiento de tu equipo.
                        </p>
                    </div>
                </div>
            `
        },
        'prompts': {
            title: '📝 Sección: Prompts',
            subtitle: 'Plantillas especializadas para traducción militar',
            content: `
                <div style="text-align: left;">
                    <h3 style="color: #fbbf24; margin: 20px 0 15px 0;">📋 ¿Qué son los Prompts?</h3>
                    <p style="color: #cbd5e1; line-height: 1.6;">
                        Los prompts son las "instrucciones" que le das al modelo de IA. Definen cómo debe comportarse, 
                        qué tono usar y qué reglas seguir para traducir contenido militar y de aviación.
                    </p>
                    
                    <h4 style="color: #60a5fa; margin: 25px 0 15px 0;">🎯 Especialización militar:</h4>
                    <p style="color: #e2e8f0; line-height: 1.6; margin-bottom: 15px;">
                        Los prompts de DCS están especialmente diseñados para:
                    </p>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Terminología militar:</strong> Traduce correctamente rangos, unidades y equipos</li>
                        <li><strong>Aviación naval/aérea:</strong> Mantiene precisión en procedimientos y maniobras</li>
                        <li><strong>Códigos y señales:</strong> Preserva identificadores técnicos importantes</li>
                        <li><strong>Contexto táctico:</strong> Entiende situaciones de combate y operaciones</li>
                    </ul>
                    
                    <h4 style="color: #34d399; margin: 25px 0 15px 0;">📁 Tipos de prompts disponibles:</h4>
                    <div style="padding-left: 15px;">
                        <div style="margin: 10px 0; padding: 10px; background: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e; border-radius: 4px;">
                            <strong style="color: #22c55e;">🎖️ Militar General:</strong> <span style="color: #cbd5e1;">Para contenido militar básico y procedimientos estándar</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3b82f6; border-radius: 4px;">
                            <strong style="color: #60a5fa;">✈️ Aviación Naval:</strong> <span style="color: #cbd5e1;">Especializado en operaciones de portaaviones y F/A-18</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(245, 158, 11, 0.1); border-left: 3px solid #f59e0b; border-radius: 4px;">
                            <strong style="color: #fbbf24;">🎯 Aire-Aire:</strong> <span style="color: #cbd5e1;">Para combate aéreo, BVR y dogfighting</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(139, 92, 246, 0.1); border-left: 3px solid #8b5cf6; border-radius: 4px;">
                            <strong style="color: #a78bfa;">🏔️ Aire-Superficie:</strong> <span style="color: #cbd5e1;">Para misiones CAS, SEAD y bombardeo</span>
                        </div>
                    </div>
                    
                    <h4 style="color: #f59e0b; margin: 25px 0 15px 0;">⚙️ Personalización de prompts:</h4>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Edición directa:</strong> Modifica las instrucciones según tus necesidades</li>
                        <li><strong>Reglas específicas:</strong> Añade reglas para tu dialecto o preferencias</li>
                        <li><strong>Vocabulario técnico:</strong> Define traducciones específicas para equipos</li>
                        <li><strong>Tono y estilo:</strong> Ajusta si quieres traducción formal o coloquial</li>
                    </ul>
                    
                    <div style="margin-top: 25px; padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 4px solid #3b82f6;">
                        <h5 style="color: #60a5fa; margin: 0 0 10px 0;">💡 Consejo:</h5>
                        <p style="color: #cbd5e1; margin: 0; font-size: 0.95rem;">
                            Empieza con un prompt predefinido y personalízalo gradualmente. Prueba con misiones pequeñas 
                            antes de aplicar cambios a campañas completas. Los mejores prompts equilibran precisión técnica con fluidez natural.
                        </p>
                    </div>
                </div>
            `
        },
        'orchestrator': {
            title: '🎯 Sección: Orquestador',
            subtitle: 'Control automatizado del proceso completo',
            content: `
                <div style="text-align: left;">
                    <h3 style="color: #fbbf24; margin: 20px 0 15px 0;">🎼 ¿Qué es el Orquestador?</h3>
                    <p style="color: #cbd5e1; line-height: 1.6;">
                        El Orquestador es el "cerebro" del sistema que coordina todo el proceso de traducción automática. 
                        Combina tu configuración, modelos y prompts para ejecutar traducciones completas sin intervención manual.
                    </p>
                    
                    <h4 style="color: #60a5fa; margin: 25px 0 15px 0;">🔄 Proceso automatizado:</h4>
                    <div style="padding-left: 15px;">
                        <div style="margin: 10px 0; padding: 10px; background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3b82f6; border-radius: 4px;">
                            <strong style="color: #60a5fa;">1. Detección:</strong> <span style="color: #cbd5e1;">Encuentra campañas DCS automáticamente</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e; border-radius: 4px;">
                            <strong style="color: #22c55e;">2. Extracción:</strong> <span style="color: #cbd5e1;">Descomprime misiones y localiza textos</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(245, 158, 11, 0.1); border-left: 3px solid #f59e0b; border-radius: 4px;">
                            <strong style="color: #fbbf24;">3. Traducción:</strong> <span style="color: #cbd5e1;">Procesa textos con IA en lotes optimizados</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(139, 92, 246, 0.1); border-left: 3px solid #8b5cf6; border-radius: 4px;">
                            <strong style="color: #a78bfa;">4. Empaquetado:</strong> <span style="color: #cbd5e1;">Reconstruye archivos y despliega en DCS</span>
                        </div>
                    </div>
                    
                    <h4 style="color: #34d399; margin: 25px 0 15px 0;">📊 Monitoreo en tiempo real:</h4>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Progreso por misión:</strong> Ve qué misión se está procesando actualmente</li>
                        <li><strong>Estadísticas de caché:</strong> Cuántas traducciones vienen del caché vs IA</li>
                        <li><strong>Errores y advertencias:</strong> Problemas detectados durante el proceso</li>
                        <li><strong>Tiempo estimado:</strong> Cuánto falta para completar la operación</li>
                        <li><strong>Logs detallados:</strong> Información técnica para debugging</li>
                    </ul>
                    
                    <h4 style="color: #f59e0b; margin: 25px 0 15px 0;">🎛️ Configuración avanzada:</h4>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Perfiles guardados:</strong> Guarda configuraciones completas para reutilizar</li>
                        <li><strong>Modos de trabajo:</strong> Traducir, reempaquetar o solo desplegar</li>
                        <li><strong>Gestión de caché:</strong> Reutiliza traducciones anteriores para acelerar</li>
                        <li><strong>Filtros de misión:</strong> Selecciona qué misiones procesar</li>
                    </ul>
                    
                    <h4 style="color: #ec4899; margin: 25px 0 15px 0;">💾 Gestión de perfiles:</h4>
                    <p style="color: #e2e8f0; line-height: 1.6; margin-bottom: 15px;">
                        Los perfiles guardan toda tu configuración (rutas, modelo, parámetros, presets) para reutilización:
                    </p>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Por modelo:</strong> "Llama-Rápido", "Gemma-Calidad", etc.</li>
                        <li><strong>Por campaña:</strong> "F/A-18", "A-10C", "F-16C", etc.</li>
                        <li><strong>Por hardware:</strong> "Equipo-Casa", "Equipo-Oficina", etc.</li>
                    </ul>
                    
                    <div style="margin-top: 25px; padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 4px solid #3b82f6;">
                        <h5 style="color: #60a5fa; margin: 0 0 10px 0;">💡 Consejo:</h5>
                        <p style="color: #cbd5e1; margin: 0; font-size: 0.95rem;">
                            Usa el Orquestador una vez que tengas todo configurado. Guarda perfiles para diferentes situaciones 
                            y aprovecha el progreso en tiempo real para monitorear grandes traducciones. El caché acelera mucho las re-traducciones.
                        </p>
                    </div>
                </div>
            `
        },
        'home': {
            title: '🏠 Página Principal',
            subtitle: 'Centro de control del sistema DCS',
            content: `
                <div style="text-align: left;">
                    <h3 style="color: #fbbf24; margin: 20px 0 15px 0;">🏠 ¿Qué es la página principal?</h3>
                    <p style="color: #cbd5e1; line-height: 1.6;">
                        La página principal es tu centro de control para el sistema de traducción DCS. 
                        Desde aquí puedes navegar a todas las secciones y ver el estado general del sistema.
                    </p>
                    
                    <h4 style="color: #60a5fa; margin: 25px 0 15px 0;">🧭 Navegación principal:</h4>
                    <div style="padding-left: 15px;">
                        <div style="margin: 10px 0; padding: 10px; background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3b82f6; border-radius: 4px;">
                            <strong style="color: #60a5fa;">🎮 Campañas:</strong> <span style="color: #cbd5e1;">Ver y gestionar campañas DCS detectadas</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e; border-radius: 4px;">
                            <strong style="color: #22c55e;">🤖 Modelos y Presets:</strong> <span style="color: #cbd5e1;">Configurar IA y optimización</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(245, 158, 11, 0.1); border-left: 3px solid #f59e0b; border-radius: 4px;">
                            <strong style="color: #fbbf24;">📝 Prompts:</strong> <span style="color: #cbd5e1;">Editar plantillas de traducción</span>
                        </div>
                        <div style="margin: 10px 0; padding: 10px; background: rgba(139, 92, 246, 0.1); border-left: 3px solid #8b5cf6; border-radius: 4px;">
                            <strong style="color: #a78bfa;">🎯 Orquestador:</strong> <span style="color: #cbd5e1;">Ejecutar traducciones automáticas</span>
                        </div>
                    </div>
                    
                    <h4 style="color: #34d399; margin: 25px 0 15px 0;">📊 Estado del sistema:</h4>
                    <ul style="color: #e2e8f0; line-height: 1.7; padding-left: 20px;">
                        <li><strong>Conectividad:</strong> Estado de LM Studio y modelos cargados</li>
                        <li><strong>Campañas detectadas:</strong> Número de campañas encontradas</li>
                        <li><strong>Progreso de traducción:</strong> Misiones completadas vs pendientes</li>
                        <li><strong>Configuración activa:</strong> Preset y modelo actualmente seleccionados</li>
                    </ul>
                    
                    <div style="margin-top: 25px; padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 4px solid #3b82f6;">
                        <h5 style="color: #60a5fa; margin: 0 0 10px 0;">💡 Consejo:</h5>
                        <p style="color: #cbd5e1; margin: 0; font-size: 0.95rem;">
                            Esta página te da una vista general rápida. Usa la navegación superior para acceder a cada sección específica. 
                            Cada sección tiene su propia ayuda detallada accesible con el botón "❓".
                        </p>
                    </div>
                </div>
            `
        },
        'general': {
            title: '🎮 Sistema de Traducción DCS',
            subtitle: 'Sistema completo para traducir campañas de DCS World',
            content: `
                <div style="text-align: center;">
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
                </div>
            `
        }
    };

    return contents[section] || contents['general'];
}

function forceShowGlobalHelp(section = 'general') {
    console.log('🎯 FORCE: Mostrando ayuda para sección:', section);
    
    // Obtener el contenido específico para esta sección
    const sectionContent = getSectionContent(section);
    console.log('📄 FORCE: Contenido obtenido:', sectionContent.title);
    
    // Intentar crear modal directamente
    try {
        createHelpModal(sectionContent);
    } catch (error) {
        console.error('❌ FORCE: Error creando modal:', error);
        // Solo usar alert como último recurso
        alert(`${sectionContent.title}\n\n${sectionContent.subtitle}`);
    }
}

function createHelpModal(sectionContent) {
    console.log('🔨 MODAL: Creando modal...');
    
    // Eliminar cualquier modal existente
    const existingModal = document.getElementById('globalHelpModal');
    if (existingModal) {
        existingModal.remove();
        console.log('🗑️ MODAL: Modal existente eliminado');
    }
    
    // Crear modal completamente nuevo cada vez con contenido específico
    const modalHTML = `
        <div id="globalHelpModal" style="display: flex !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important; background: rgba(0,0,0,0.95) !important; z-index: 99999 !important; justify-content: center !important; align-items: center !important;">
            <div id="globalHelpContent" style="background: #0f172a !important; border: 1px solid #334155 !important; border-radius: 8px !important; padding: 25px !important; max-width: 650px !important; max-height: 85% !important; overflow-y: auto !important; margin: 20px !important; box-shadow: 0 8px 32px rgba(0,0,0,0.6) !important;">
                <header style="margin-bottom: 15px !important; border-bottom: 1px solid #334155 !important; padding-bottom: 10px !important;">
                    <h2 style="color: #60a5fa !important; font-size: 1.3rem !important; font-weight: 600 !important; margin: 0 !important;">${sectionContent.title}</h2>
                    <p style="color: #cbd5e1; margin: 8px 0 0 0; font-size: 1rem; opacity: 0.9;">${sectionContent.subtitle}</p>
                </header>
                <div style="color: #e2e8f0 !important; line-height: 1.6 !important; font-size: 0.95rem !important;">
                    ${sectionContent.content}
                </div>
                <footer style="margin-top: 20px !important; text-align: right !important; border-top: 1px solid #334155 !important; padding-top: 15px !important;">
                    <button id="globalHelpClose" style="background: #374151 !important; color: #e5e7eb !important; border: 1px solid #4b5563 !important; padding: 10px 20px !important; border-radius: 6px !important; cursor: pointer !important; font-size: 0.95rem !important; transition: background-color 0.2s !important;">Entendido</button>
                </footer>
            </div>
        </div>
    `;
    
    console.log('🔨 MODAL: Insertando HTML...');
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    globalHelpModalElement = document.getElementById('globalHelpModal');
    globalHelpModalVisible = true;
    
    if (!globalHelpModalElement) {
        console.error('❌ MODAL: No se pudo crear el modal');
        return;
    }
    
    console.log('✅ MODAL: Modal creado exitosamente');
    
    // Configurar botón cerrar de forma simple
    const closeBtn = document.getElementById('globalHelpClose');
    if (closeBtn) {
        closeBtn.onclick = function() {
            console.log('🔴 MODAL: Cerrando modal');
            globalHelpModalElement.remove();
            globalHelpModalElement = null;
            globalHelpModalVisible = false;
        };
    }
    
    // Click en el fondo para cerrar
    globalHelpModalElement.onclick = function(e) {
        if (e.target === globalHelpModalElement) {
            console.log('🔴 MODAL: Cerrando por click en fondo');
            globalHelpModalElement.remove();
            globalHelpModalElement = null;
            globalHelpModalVisible = false;
        }
    };
    
    // Prevenir cierre por clicks internos
    const content = document.getElementById('globalHelpContent');
    if (content) {
        content.onclick = function(e) {
            e.stopPropagation();
        };
    }
    
    console.log('✅ MODAL: Eventos configurados correctamente');
}

function closeGlobalHelp() {
    if (globalHelpModalElement) {
        globalHelpModalElement.remove();
        globalHelpModalElement = null;
        globalHelpModalVisible = false;
        console.log('✅ Modal cerrado y limpiado');
    }
}

// Configurar cuando el DOM esté listo Y después de otros scripts
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        console.log('🚀 DOM READY - Configurando ayuda global después de delay...');
        setTimeout(setupGlobalHelp, 100);
    });
} else {
    console.log('🚀 DOM YA LISTO - Configurando ayuda global después de delay...');
    setTimeout(setupGlobalHelp, 100);
}

// También intentar después de un delay mayor
setTimeout(function() {
    console.log('🔄 RETRY - Intentando configurar ayuda global después de 1 segundo...');
    setupGlobalHelp();
}, 1000);

// Debug: Verificar estado del botón cada 3 segundos
setInterval(function() {
    const helpBtn = document.getElementById('openHelp');
    if (helpBtn) {
        console.log('✅ DEBUG: Botón de ayuda encontrado, onclick =', helpBtn.onclick ? 'CONFIGURADO' : 'NO CONFIGURADO');
    } else {
        console.warn('⚠️ DEBUG: Botón de ayuda NO encontrado en DOM');
    }
}, 3000);

// FUNCIÓN DE EMERGENCIA: Si nada funciona, usar esta
window.emergencyHelp = function() {
    alert('🆘 EMERGENCIA: Sistema de ayuda activado manualmente\n\nEste mensaje confirma que JavaScript funciona.\n\nSi el botón de ayuda no responde, hay un problema con los event listeners.');
};

console.log('🎯 ARCHIVO COMPLETAMENTE CARGADO - Sistema de ayuda inicializado');
console.log('💡 Para probar manualmente, ejecuta en consola: testHelp() o emergencyHelp()');