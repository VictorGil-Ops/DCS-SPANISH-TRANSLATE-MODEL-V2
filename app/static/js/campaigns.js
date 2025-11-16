/* ===================================
   JAVASCRIPT PARA GESTIÓN DE CAMPAÑAS
   =================================== */

// Variables globales
let campaignsData = [];
let cacheData = {};
let deleteTarget = { campaign: '', mission: '' };
let userConfig = null; // Cache de configuración de usuario

// ====================================
// INICIALIZACIÓN
// ====================================

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🏛️ Gestión de Campañas - Inicializando...');
    
    try {
        // Limpiar modales previos al inicializar
        cleanupModals();
        
        // Cargar configuración de usuario
        await loadUserConfig();
        
        // Cargar datos dinámicamente desde API
        await loadCampaignsData();
        
        // Renderizar campañas en el DOM
        renderCampaigns();
        
        // Actualizar estadísticas
        updateGlobalStats();
        
        // Configurar modales
        setupModals();
        
        // Configurar event listeners
        setupEventListeners();
        
        console.log('✅ Gestión de Campañas - Inicializado correctamente');
        
    } catch (error) {
        console.error('❌ Error inicializando:', error);
        showError('Error cargando campañas: ' + error.message);
    }
});

// Limpiar modales cuando se salga de la página
window.addEventListener('beforeunload', function() {
    cleanupModals();
});

// Limpiar modales si hay errores JavaScript
window.addEventListener('error', function() {
    cleanupModals();
});

/**
 * Configurar event listeners
 */
function setupEventListeners() {
    console.log('🔧 Configurando event listeners...');
    
    // Botón Gestionar Cache
    const cacheBtn = document.querySelector('[onclick="openCacheManager()"]');
    if (cacheBtn) {
        cacheBtn.removeAttribute('onclick');
        cacheBtn.addEventListener('click', openCacheManager);
        console.log('✅ Event listener para cache configurado');
    } else {
        console.error('❌ Botón de cache no encontrado');
    }
    
    // Botón Actualizar
    const refreshBtn = document.querySelector('[onclick="refreshCampaigns()"]');
    if (refreshBtn) {
        refreshBtn.removeAttribute('onclick');
        refreshBtn.addEventListener('click', refreshCampaigns);
        console.log('✅ Event listener para refresh configurado');
    } else {
        console.error('❌ Botón de refresh no encontrado');
    }
}

// ====================================
// FUNCIONES PRINCIPALES
// ====================================

/**
 * Cargar configuración de usuario
 */
async function loadUserConfig() {
    try {
        console.log('⚙️ Cargando configuración de usuario...');
        const response = await fetch('/api/user_config');
        const data = await response.json();
        
        if (data.ok && data.config) {
            userConfig = data.config;
            console.log('✅ Configuración de usuario cargada:', Object.keys(userConfig));
        } else {
            console.log('⚠️ No se pudo cargar configuración de usuario');
        }
    } catch (error) {
        console.error('❌ Error cargando configuración de usuario:', error);
    }
}

/**
 * Obtener ruta de DCS desde configuración
 */
function getDcsPath() {
    if (userConfig && (userConfig.DEPLOY_DIR || userConfig.ROOT_DIR)) {
        return userConfig.DEPLOY_DIR || userConfig.ROOT_DIR;
    }
    // Ruta por defecto si no hay configuración
    return 'D:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns\\';
}

/**
 * Cargar datos de campañas desde la API
 */
async function loadCampaignsData() {
    try {
        console.log('📡 Cargando datos de campañas...');
        const response = await fetch('/campaigns/api/campaigns');
        const data = await response.json();
        
        console.log('📋 Respuesta API:', data);
        
        if (data.ok) {
            campaignsData = data.campaigns;
            console.log(`📊 Cargadas ${campaignsData.length} campañas:`, campaignsData);
        } else {
            console.error('❌ Error en API:', data.error);
            showError('Error cargando campañas: ' + data.error);
        }
    } catch (error) {
        console.error('❌ Error cargando campañas:', error);
        showError('Error de conexión al cargar campañas');
    }
}

/**
 * Renderizar campañas dinámicamente en el DOM
 */
function renderCampaigns() {
    console.log('🎨 Renderizando campañas...');
    
    const container = document.getElementById('campaignsContainer');
    
    if (!campaignsData.length) {
        container.innerHTML = `
            <div class="empty-state text-center p-5">
                <i class="fas fa-folder-open fa-3x text-muted mb-3"></i>
                <h4>No hay campañas disponibles</h4>
                <p class="text-muted">Las campañas aparecerán aquí cuando traduzcas misiones con el Orquestador</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    campaignsData.forEach(campaign => {
        html += `
            <div class="campaign-card" data-campaign="${campaign.name}">
                <!-- Header de la campaña -->
                <div class="campaign-header" onclick="toggleCampaign('${campaign.name}')">
                    <div class="campaign-info">
                        <h5 class="campaign-name">📁 ${campaign.name}</h5>
                        <div class="campaign-stats">
                            <span class="badge bg-secondary">${campaign.total_missions} misiones</span>
                            <span class="badge bg-success">${campaign.translated_missions} traducidas</span>
                            <span class="badge bg-primary">${campaign.finalized_missions} finalizadas</span>
                            <span class="badge bg-warning">${campaign.deployed_missions} desplegadas</span>
                            <span class="text-muted">| ${campaign.total_size_mb} MB</span>
                        </div>
                    </div>
                    <div class="campaign-actions">
                        <small class="text-muted">${campaign.last_activity.substring(0, 10)}</small>
                        <i class="fas fa-chevron-down expand-icon"></i>
                    </div>
                </div>
                
                <!-- Contenido de misiones (inicialmente oculto) -->
                <div class="campaign-content" id="campaign-${campaign.name}" style="display: none;">
                    <div class="loading-spinner text-center p-3">
                        <i class="fas fa-spinner fa-spin"></i> Cargando misiones...
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    console.log(`✅ ${campaignsData.length} campañas renderizadas`);
}

/**
 * Actualizar estadísticas globales desde campañas existentes en el DOM
 */
function updateGlobalStatsFromDOM() {
    console.log('📈 Calculando estadísticas desde DOM...');
    
    const campaignCards = document.querySelectorAll('.campaign-card');
    const campaignsCount = campaignCards.length;
    
    let totalMissions = 0;
    let totalSize = 0;
    
    campaignCards.forEach(card => {
        // Extraer número de misiones del badge
        const missionsBadge = card.querySelector('.badge.bg-secondary');
        if (missionsBadge) {
            const missionsText = missionsBadge.textContent;
            const missionsMatch = missionsText.match(/(\d+)/);
            if (missionsMatch) {
                totalMissions += parseInt(missionsMatch[1]);
            }
        }
        
        // Extraer tamaño del texto
        const sizeText = card.querySelector('.text-muted');
        if (sizeText) {
            const sizeMatch = sizeText.textContent.match(/([\d.]+)\s*MB/);
            if (sizeMatch) {
                totalSize += parseFloat(sizeMatch[1]);
            }
        }
    });
    
    console.log(`📊 Estadísticas DOM: ${campaignsCount} campañas, ${totalMissions} misiones, ${totalSize.toFixed(1)} MB`);
    
    document.getElementById('totalCampaigns').textContent = `${campaignsCount} campañas`;
    document.getElementById('totalMissions').textContent = `${totalMissions} misiones`;
    document.getElementById('totalSizeMB').textContent = `${totalSize.toFixed(1)} MB`;
}

/**
 * Actualizar estadísticas globales
 */
function updateGlobalStats() {
    console.log('📈 Actualizando estadísticas globales. Campañas:', campaignsData.length);
    
    if (!campaignsData.length) {
        console.log('⚠️ No hay campañas para mostrar');
        document.getElementById('totalCampaigns').textContent = '0 campañas';
        document.getElementById('totalMissions').textContent = '0 misiones';
        document.getElementById('totalSizeMB').textContent = '0 MB';
        return;
    }
    
    const totalMissions = campaignsData.reduce((sum, c) => sum + c.total_missions, 0);
    const totalSize = campaignsData.reduce((sum, c) => sum + c.total_size_mb, 0);
    
    console.log(`📊 Estadísticas: ${campaignsData.length} campañas, ${totalMissions} misiones, ${totalSize.toFixed(1)} MB`);
    
    document.getElementById('totalCampaigns').textContent = `${campaignsData.length} campañas`;
    document.getElementById('totalMissions').textContent = `${totalMissions} misiones`;
    document.getElementById('totalSizeMB').textContent = `${totalSize.toFixed(1)} MB`;
}

/**
 * Refrescar lista de campañas
 */
async function refreshCampaigns() {
    const btn = event.target.closest('button');
    const originalHtml = btn.innerHTML;
    
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';
    btn.disabled = true;
    
    try {
        // Mostrar indicador de carga
        const container = document.getElementById('campaignsContainer');
        container.innerHTML = `
            <div class="loading-state text-center p-5">
                <i class="fas fa-spinner fa-spin fa-2x text-primary mb-3"></i>
                <h4>Actualizando campañas...</h4>
                <p class="text-muted">Reescaneando directorio de traducciones</p>
            </div>
        `;
        
        // Cargar datos frescos
        await loadCampaignsData();
        
        // Re-renderizar
        renderCampaigns();
        
        // Actualizar estadísticas
        updateGlobalStats();
        
        showSuccess('Campañas actualizadas correctamente');
    } catch (error) {
        showError('Error actualizando campañas: ' + error.message);
        console.error('Error actualizando campañas:', error);
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}

// Asegurar que las funciones estén disponibles globalmente
window.refreshCampaigns = refreshCampaigns;

/**
 * Alternar contenido de una campaña
 */
async function toggleCampaign(campaignName) {
    const campaignCard = document.querySelector(`[data-campaign="${campaignName}"]`);
    const content = document.getElementById(`campaign-${campaignName}`);
    const icon = campaignCard.querySelector('.expand-icon');
    
    if (content.style.display === 'none') {
        // Expandir - cargar misiones
        content.style.display = 'block';
        campaignCard.classList.add('expanded');
        await loadCampaignMissions(campaignName);
    } else {
        // Contraer
        content.style.display = 'none';
        campaignCard.classList.remove('expanded');
    }
}

// Asegurar que toggleCampaign esté disponible globalmente
window.toggleCampaign = toggleCampaign;

/**
 * Cargar misiones de una campaña específica
 */
async function loadCampaignMissions(campaignName) {
    const content = document.getElementById(`campaign-${campaignName}`);
    
    try {
        const response = await fetch(`/campaigns/api/campaigns/${campaignName}/missions`);
        const data = await response.json();
        
        if (data.ok) {
            renderMissionsTable(content, data.missions);
        } else {
            content.innerHTML = `<div class="alert alert-danger m-3">Error: ${data.error}</div>`;
        }
    } catch (error) {
        console.error('Error cargando misiones:', error);
        content.innerHTML = `<div class="alert alert-danger m-3">Error de conexión</div>`;
    }
}

/**
 * Renderizar tabla de misiones
 */
function renderMissionsTable(container, missions) {
    if (!missions.length) {
        container.innerHTML = `
            <div class="empty-state text-center p-4">
                <i class="fas fa-folder-open fa-2x text-muted mb-2"></i>
                <p class="text-muted">No hay misiones en esta campaña</p>
            </div>
        `;
        return;
    }
    
    const tableHtml = `
        <table class="missions-table table table-sm mb-0">
            <thead>
                <tr>
                    <th>📋 Misión</th>
                    <th>🔄 Estado</th>
                    <th>📦 Archivos</th>
                    <th>💾 Tamaño</th>
                    <th>🔧 Acciones</th>
                </tr>
            </thead>
            <tbody>
                ${missions.map(mission => renderMissionRow(mission)).join('')}
            </tbody>
        </table>
    `;
    
    container.innerHTML = tableHtml;
}

/**
 * Renderizar fila de misión
 */
function renderMissionRow(mission) {
    const statusInfo = getMissionStatusInfo(mission);
    const filesInfo = getMissionFilesInfo(mission);
    
    return `
        <tr>
            <td>
                <strong>${mission.name}</strong>
                <br><small class="text-muted">${mission.last_modified.split('T')[0]}</small>
            </td>
            <td>
                <div class="mission-status ${statusInfo.class}">
                    <i class="fas ${statusInfo.icon}"></i>
                    ${statusInfo.text}
                </div>
            </td>
            <td>
                <div class="d-flex gap-1">
                    ${filesInfo.map(info => `
                        <span class="badge ${info.class}" title="${info.title}">
                            ${info.icon} ${info.text}
                        </span>
                    `).join('')}
                </div>
            </td>
            <td>
                <span class="text-muted">${mission.size_mb} MB</span>
            </td>
            <td>
                <div class="mission-actions">
                    ${mission.has_out_lua ? `
                        <button class="btn btn-outline-primary btn-sm btn-view-lua" 
                                onclick="viewLuaFiles('${mission.campaign}', '${mission.name}')"
                                title="Ver archivos LUA (original vs traducido)">
                            <i class="fas fa-eye"></i> 📝
                        </button>
                    ` : ''}
                    ${mission.has_backup ? `
                        <button class="btn btn-outline-info btn-sm btn-redeploy" 
                                onclick="redeployMission('${mission.campaign}', '${mission.name}')"
                                title="Restaurar misión original en inglés desde backup">
                            <i class="fas fa-undo"></i> 🇬🇧
                        </button>
                    ` : ''}
                    <button class="btn btn-outline-danger btn-sm btn-delete" 
                            onclick="deleteMission('${mission.campaign}', '${mission.name}')"
                            title="Eliminar misión">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

/**
 * Obtener información de estado de misión
 */
function getMissionStatusInfo(mission) {
    // Para ser "Completa" debe tener: finalizado, backup Y archivos LUA traducidos
    if (mission.has_finalizado && mission.has_backup && mission.has_out_lua && mission.lua_files_count > 0) {
        return {
            class: 'status-ready',
            icon: 'fa-check-circle',
            text: 'Completa'
        };
    } else if (mission.has_out_lua && mission.translation_complete) {
        return {
            class: 'status-partial',
            icon: 'fa-clock',
            text: 'Traducida'
        };
    } else if (mission.has_out_lua) {
        return {
            class: 'status-partial',
            icon: 'fa-exclamation-triangle',
            text: 'Parcial'
        };
    } else if (mission.has_finalizado && !mission.has_out_lua) {
        // Solo tiene MIZ empaquetado pero no archivos LUA traducidos
        return {
            class: 'status-packaged',
            icon: 'fa-cube',
            text: 'Solo MIZ'
        };
    } else if (mission.has_backup && !mission.has_out_lua) {
        // Solo tiene backup pero no procesado
        return {
            class: 'status-backup-only',
            icon: 'fa-archive',
            text: 'Solo Backup'
        };
    } else {
        return {
            class: 'status-missing',
            icon: 'fa-times-circle',
            text: 'Sin procesar'
        };
    }
}

/**
 * Obtener información de archivos de misión
 */
function getMissionFilesInfo(mission) {
    const files = [];
    
    if (mission.has_out_lua) {
        files.push({
            class: 'bg-info',
            icon: '📝',
            text: `${mission.lua_files_count} LUA`,
            title: 'Archivos LUA traducidos'
        });
    }
    
    if (mission.has_finalizado) {
        files.push({
            class: 'bg-success',
            icon: '📦',
            text: 'MIZ',
            title: 'Archivo MIZ finalizado'
        });
    }
    
    if (mission.has_backup) {
        files.push({
            class: 'bg-success',
            icon: '🇬🇧',
            text: 'ORIG',
            title: 'Backup original en inglés disponible - Puede restaurarse'
        });
    }
    
    if (mission.is_deployed) {
        files.push({
            class: 'bg-warning',
            icon: '🚀',
            text: 'DESP',
            title: 'Misión traducida desplegada en DCS - Hash diferente al backup'
        });
    }
    
    return files;
}

// ====================================
// FUNCIONES DE GESTIÓN
// ====================================

/**
 * Eliminar misión
 */
function deleteMission(campaignName, missionName) {
    deleteTarget = { campaign: campaignName, mission: missionName };
    document.getElementById('deleteTarget').textContent = `${campaignName} > ${missionName}`;
    
    const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
    modal.show();
}

/**
 * Confirmar eliminación
 */
async function confirmDelete() {
    const { campaign, mission } = deleteTarget;
    
    try {
        const response = await fetch(`/campaigns/api/campaigns/${campaign}/missions/${mission}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.ok) {
            showSuccess(`Misión ${mission} eliminada correctamente`);
            
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteModal'));
            modal.hide();
            
            // Recargar misiones de la campaña
            await loadCampaignMissions(campaign);
        } else {
            showError('Error eliminando misión: ' + data.error);
        }
    } catch (error) {
        console.error('Error eliminando misión:', error);
        showError('Error de conexión al eliminar misión');
    }
}

/**
 * Restaurar misión original en inglés desde backup
 */
async function redeployMission(campaignName, missionName) {
    // Confirmar acción
    const confirm = window.confirm(
        `🇬🇧 RESTAURAR MISIÓN ORIGINAL EN INGLÉS\n\n` +
        `Misión: ${missionName}\n` +
        `Campaña: ${campaignName}\n\n` +
        `Esta acción:\n` +
        `• Restaurará la versión original en inglés desde el backup\n` +
        `• Sobrescribirá la versión traducida actual\n` +
        `• Los archivos en español se perderán\n\n` +
        `¿Estás seguro de que quieres continuar?`
    );
    
    if (!confirm) return;
    
    // Obtener ruta de DCS desde configuración
    const defaultPath = getDcsPath();
    
    const targetPath = prompt(
        '📁 RUTA DE DESTINO DCS\n\n' +
        'Introduce la ruta donde restaurar la misión original:\n' +
        '(Se usa la ruta configurada en el sistema)', 
        defaultPath
    );
    
    if (!targetPath) return;
    
    try {
        const response = await fetch(`/campaigns/api/campaigns/${campaignName}/missions/${missionName}/redeploy`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                target_path: targetPath,
                restore_original: true
            })
        });
        
        const data = await response.json();
        
        if (data.ok) {
            showSuccess(`✅ Misión original en inglés restaurada: ${missionName}`);
            // Recargar la lista de misiones para reflejar cambios
            setTimeout(() => {
                loadCampaignMissions(campaignName);
            }, 1000);
        } else {
            showError('❌ Error restaurando misión original: ' + data.error);
        }
    } catch (error) {
        console.error('Error redesplegando misión:', error);
        showError('Error de conexión al redesplegar misión');
    }
}

// ====================================
// GESTIÓN DE CACHE
// ====================================

/**
 * Abrir gestor de cache
 */
function openCacheManager() {
    console.log('🗄️ === ABRIENDO GESTOR DE CACHE ===');
    
    try {
        const modalElement = document.getElementById('cacheModal');
        if (!modalElement) {
            console.error('❌ Modal cacheModal no encontrado');
            alert('Error: Modal de cache no encontrado');
            return;
        }
        
        console.log('🗄️ Verificando Bootstrap...');
        if (typeof bootstrap === 'undefined') {
            console.error('❌ Bootstrap no está disponible');
            // Fallback: mostrar modal manualmente
            modalElement.style.display = 'block';
            modalElement.classList.add('show');
            document.body.classList.add('modal-open');
        } else {
            console.log('🗄️ Bootstrap disponible, creando modal...');
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        }
        
        console.log('🗄️ Modal mostrado, iniciando carga...');
        
        // Mostrar indicador de carga inmediatamente
        showCacheLoading();
        
        console.log('🗄️ Loading mostrado, iniciando loadCacheInfo...');
        
        // Cargar datos del cache
        loadCacheInfo();
        
        console.log('🗄️ === FIN APERTURA CACHE MANAGER ===');
        
    } catch (error) {
        console.error('❌ Error en openCacheManager:', error);
        alert('Error abriendo cache: ' + error.message);
    }
}

// Asegurar que la función esté disponible globalmente
window.openCacheManager = openCacheManager;

/**
 * Función de test simple para cache
 */
async function testCacheAPI() {
    console.log('🧪 === TEST CACHE API ===');
    
    try {
        console.log('🧪 Haciendo fetch simple...');
        const response = await fetch('/campaigns/api/cache');
        console.log('🧪 Response status:', response.status);
        console.log('🧪 Response ok:', response.ok);
        
        const text = await response.text();
        console.log('🧪 Response text length:', text.length);
        console.log('🧪 First 200 chars:', text.substring(0, 200));
        
        const data = JSON.parse(text);
        console.log('🧪 JSON parsed successfully');
        console.log('🧪 Data keys:', Object.keys(data));
        
        if (data.cache) {
            console.log('🧪 Cache keys:', Object.keys(data.cache));
            console.log('🧪 Total entries:', data.cache.total_entries);
        }
        
        return data;
    } catch (error) {
        console.error('🧪 Error:', error);
        return null;
    }
}

// Hacer función disponible globalmente para testing
window.testCacheAPI = testCacheAPI;

/**
 * Test simple del cache sin modal
 */
async function simpleTestCache() {
    console.log('🧪 === SIMPLE CACHE TEST ===');
    
    try {
        const data = await testCacheAPI();
        if (data && data.ok) {
            console.log('🧪 ✅ API funciona correctamente');
            console.log('🧪 Probando updateCacheDisplay directamente...');
            
            cacheData = data.cache;
            updateCacheDisplay();
            
            console.log('🧪 ✅ Test completado');
        } else {
            console.log('🧪 ❌ API no funcionó');
        }
    } catch (error) {
        console.error('🧪 ❌ Error en test:', error);
    }
}

window.simpleTestCache = simpleTestCache;

/**
 * Cancelar carga de cache
 */
function cancelCacheLoad() {
    console.log('❌ Usuario canceló carga de cache');
    
    // Mostrar información básica sin cargar entradas
    const container = document.getElementById('cacheEntries');
    container.innerHTML = `
        <div class="text-center p-5">
            <i class="fas fa-info-circle fa-2x text-info mb-3"></i>
            <h5>Carga cancelada</h5>
            <p class="text-muted">El archivo de cache es muy grande para cargar todas las entradas.</p>
            <div class="mt-3">
                <button class="btn btn-primary btn-sm" onclick="loadBasicCacheInfo()">
                    <i class="fas fa-chart-bar"></i> Ver solo estadísticas
                </button>
                <button class="btn btn-outline-primary btn-sm" onclick="loadCacheInfo()">
                    <i class="fas fa-retry"></i> Reintentar carga completa
                </button>
            </div>
        </div>
    `;
}

/**
 * Cargar solo información básica del cache
 */
async function loadBasicCacheInfo() {
    console.log('📊 Cargando solo estadísticas básicas del cache...');
    
    const container = document.getElementById('cacheEntries');
    container.innerHTML = `
        <div class="text-center p-3">
            <i class="fas fa-spinner fa-spin"></i> Cargando estadísticas...
        </div>
    `;
    
    try {
        // Solo obtener stats básicas
        const response = await fetch('/campaigns/api/cache');
        const data = await response.json();
        
        if (data.ok) {
            // Actualizar solo estadísticas, no mostrar entradas
            const totalEntries = data.cache.total_entries || 0;
            const duplicatesRemoved = data.cache.duplicates_removed || 0;
            
            document.getElementById('cacheTotal').textContent = totalEntries.toLocaleString();
            document.getElementById('cacheSize').textContent = `~${((totalEntries * 100) / (1024 * 1024)).toFixed(1)} MB`;
            document.getElementById('cacheLastUpdate').textContent = new Date().toLocaleDateString();
            
            container.innerHTML = `
                <div class="text-center p-4">
                    <i class="fas fa-chart-pie fa-3x text-success mb-3"></i>
                    <h5>Estadísticas del Cache</h5>
                    <div class="row text-center mt-4">
                        <div class="col-4">
                            <div class="border rounded p-3">
                                <h3 class="text-primary">${totalEntries.toLocaleString()}</h3>
                                <small class="text-muted">Total Entradas</small>
                            </div>
                        </div>
                        <div class="col-4">
                            <div class="border rounded p-3">
                                <h3 class="text-warning">${duplicatesRemoved}</h3>
                                <small class="text-muted">Duplicados Eliminados</small>
                            </div>
                        </div>
                        <div class="col-4">
                            <div class="border rounded p-3">
                                <h3 class="text-info">~${((totalEntries * 100) / (1024 * 1024)).toFixed(1)}</h3>
                                <small class="text-muted">MB Estimados</small>
                            </div>
                        </div>
                    </div>
                    <div class="mt-4">
                        <p class="text-muted">
                            <i class="fas fa-info-circle"></i>
                            Entradas individuales no mostradas para mejorar rendimiento
                        </p>
                    </div>
                </div>
            `;
        } else {
            showCacheError('Error cargando estadísticas: ' + data.error);
        }
    } catch (error) {
        console.error('Error cargando estadísticas básicas:', error);
        showCacheError('Error cargando estadísticas: ' + error.message);
    }
}

window.cancelCacheLoad = cancelCacheLoad;
window.loadBasicCacheInfo = loadBasicCacheInfo;

/**
 * Mostrar indicador de carga para el cache
 */
function showCacheLoading() {
    console.log('🗄️ Mostrando indicador de carga del cache...');
    
    const container = document.getElementById('cacheEntries');
    
    if (!container) {
        console.error('❌ Elemento cacheEntries no encontrado');
        return;
    }
    
    // Mostrar indicador de carga moderno
    container.innerHTML = `
        <div class="cache-loading slide-up">
            <div class="spinner-border" role="status"></div>
            <p class="mt-2">Inicializando sistema de cache...</p>
        </div>
    `;
    
    console.log('✅ Loading mostrado correctamente');
}

/**
 * Cargar información del cache
 */
async function loadCacheInfo() {
    console.log('🎯 === INICIO Sistema de Cache por Misión ===');
    
    const container = document.getElementById('cacheEntries');
    
    // Mostrar información del sistema de cache por misión
    container.innerHTML = `
        <div class="cache-loading slide-up">
            <i class="fas fa-project-diagram fa-3x text-info mb-3"></i>
            <h5>Sistema de Cache por Misión</h5>
            <p class="text-muted">Gestión inteligente y eficiente de traducciones</p>
            <div class="cache-actions mt-4">
                <button class="btn btn-primary" onclick="loadMissionCaches()">
                    <i class="fas fa-database"></i> Ver Caches por Misión
                </button>
                <button class="btn btn-outline-secondary" onclick="loadGlobalCacheStats()">
                    <i class="fas fa-chart-pie"></i> Estadísticas Globales
                </button>
            </div>
            <div class="alert alert-info mt-4" style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px;">
                <i class="fas fa-lightbulb"></i>
                <strong>Nuevo Sistema:</strong> Los caches están organizados por misión para mejor rendimiento
            </div>
        </div>
    `;
    
    console.log('✅ Sistema de cache por misión inicializado');
}

/**
 * Cargar estadísticas del cache global (solo números)
 */
async function loadGlobalCacheStats() {
    console.log('📊 Cargando estadísticas del cache global...');
    
    const container = document.getElementById('cacheEntries');
    
    container.innerHTML = `
        <div class="cache-loading">
            <div class="spinner-border" role="status"></div>
            <p class="mt-2">Cargando estadísticas globales...</p>
        </div>
    `;
    
    try {
        const response = await fetch('/campaigns/api/cache');
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.ok && data.cache) {
            renderGlobalCacheStats(data.cache);
        } else {
            throw new Error(data.error || 'Error obteniendo estadísticas');
        }
        
    } catch (error) {
        console.error('❌ Error cargando estadísticas:', error);
        container.innerHTML = `
            <div class="text-center p-4 text-danger">
                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                <h5>Error cargando estadísticas</h5>
                <p class="small">${error.message}</p>
                <div class="cache-actions mt-3">
                    <button class="btn btn-outline-primary" onclick="loadCacheInfo()">
                        <i class="fas fa-arrow-left"></i> Volver
                    </button>
                </div>
            </div>
        `;
    }
}

/**
 * Renderizar estadísticas del cache global
 */
function renderGlobalCacheStats(stats) {
    const container = document.getElementById('cacheEntries');
    
    container.innerHTML = `
        <div class="slide-up">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0">
                    <i class="fas fa-chart-pie me-2"></i>
                    Estadísticas del Cache Global
                </h6>
                <div class="cache-actions">
                    <button class="btn btn-outline-primary btn-sm" onclick="loadMissionCaches()">
                        <i class="fas fa-project-diagram"></i> Ver por Misión
                    </button>
                </div>
            </div>
            
            <div class="cache-stats">
                <div class="cache-stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-database"></i>
                    </div>
                    <div class="stat-value">${(stats.total_entries || 0).toLocaleString()}</div>
                    <div class="stat-label">Entradas Totales</div>
                </div>
                
                <div class="cache-stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-globe"></i>
                    </div>
                    <div class="stat-value">${(stats.global_entries || 0).toLocaleString()}</div>
                    <div class="stat-label">Entradas Globales</div>
                </div>
                
                <div class="cache-stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-clone"></i>
                    </div>
                    <div class="stat-value">${(stats.duplicates_removed || 0).toLocaleString()}</div>
                    <div class="stat-label">Duplicados Eliminados</div>
                </div>
            </div>
            
            <div class="alert alert-warning mt-3" style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px;">
                <i class="fas fa-info-circle"></i>
                <strong>Cache Grande:</strong> Use el sistema por misión para explorar entradas individuales
            </div>
            
            <div class="cache-actions">
                <button class="btn btn-primary" onclick="loadMissionCaches()">
                    <i class="fas fa-project-diagram"></i> Explorar por Misión
                </button>
                <button class="btn btn-outline-secondary" onclick="loadCacheInfo()">
                    <i class="fas fa-arrow-left"></i> Volver al Inicio
                </button>
            </div>
        </div>
    `;
}

/**
 * Mostrar error en el cache
 */
function showCacheError(message) {
    const container = document.getElementById('cacheEntries');
    container.innerHTML = `
        <div class="text-center p-5">
            <i class="fas fa-exclamation-triangle fa-2x text-warning mb-3"></i>
            <h5>Error cargando cache</h5>
            <p class="text-muted">${message}</p>
            <button class="btn btn-primary btn-sm" onclick="loadCacheInfo()">
                <i class="fas fa-retry"></i> Reintentar
            </button>
        </div>
    `;
}

/**
 * Actualizar display del cache
 */
function updateCacheDisplay() {
    console.log('🎨 === INICIO updateCacheDisplay ===');
    console.log('🎨 cacheData existe:', !!cacheData);
    
    if (!cacheData) {
        console.error('❌ cacheData es null/undefined');
        showCacheError('No se han cargado datos del cache');
        return;
    }
    
    // Actualizar estadísticas
    const totalEntries = cacheData.total_entries || 0;
    const globalEntries = cacheData.global_entries || 0;
    const entriesSize = Object.keys(cacheData.entries || {}).length;
    
    console.log(`🎨 Stats: ${totalEntries} entradas, ${entriesSize} keys`);
    
    // Calcular tamaño aproximado (cada entrada ~100 bytes en promedio)
    const estimatedSizeMB = (entriesSize * 100) / (1024 * 1024);
    
    document.getElementById('cacheTotal').textContent = totalEntries.toLocaleString();
    document.getElementById('cacheSize').textContent = `~${estimatedSizeMB.toFixed(1)} MB`;
    document.getElementById('cacheLastUpdate').textContent = new Date().toLocaleDateString();
    
    console.log('🎨 DOM actualizado, llamando renderCacheEntries...');
    
    // Renderizar entradas
    renderCacheEntries();
}

/**
 * Renderizar entradas del cache
 */
function renderCacheEntries() {
    console.log('🎨 Renderizando entradas del cache...');
    
    const container = document.getElementById('cacheEntries');
    
    if (!cacheData || !cacheData.entries) {
        container.innerHTML = `
            <div class="text-center p-4 text-muted">
                <i class="fas fa-database fa-2x mb-2"></i>
                <p>No hay entradas en el cache</p>
                <small>Las traducciones aparecerán aquí cuando uses el Orquestador</small>
            </div>
        `;
        return;
    }
    
    const entries = Object.entries(cacheData.entries);
    
    if (!entries.length) {
        container.innerHTML = `
            <div class="text-center p-4 text-muted">
                <i class="fas fa-database fa-2x mb-2"></i>
                <p>Cache vacío</p>
                <small>Las traducciones aparecerán aquí cuando uses el Orquestador</small>
            </div>
        `;
        return;
    }
    
    console.log(`🎨 Total entries a procesar: ${entries.length}`);
    
    // Si hay demasiadas entradas, mostrar solo estadísticas por rendimiento
    if (entries.length > 500) {
        console.log('⚠️ Demasiadas entradas, mostrando solo estadísticas');
        container.innerHTML = `
            <div class="text-center p-4">
                <i class="fas fa-chart-bar fa-3x text-warning mb-3"></i>
                <h5>Cache Grande Detectado</h5>
                <p class="text-muted">El cache tiene ${entries.length.toLocaleString()} entradas</p>
                
                <div class="alert alert-info mt-3">
                    <i class="fas fa-info-circle"></i>
                    Debido al gran tamaño, solo se muestran estadísticas para mejorar el rendimiento.
                </div>
                
                <div class="mt-3">
                    <button class="btn btn-primary btn-sm" onclick="renderSampleEntries()">
                        <i class="fas fa-eye"></i> Ver muestra (10 entradas)
                    </button>
                    <button class="btn btn-outline-primary btn-sm" onclick="compactCache()">
                        <i class="fas fa-compress"></i> Compactar Cache
                    </button>
                </div>
            </div>
        `;
        return;
    }
    
    // Renderizar hasta 50 entradas para archivos medianos
    const maxEntries = entries.length > 100 ? 50 : 100;
    const entriesToShow = entries.slice(0, maxEntries);
    
    console.log(`🎨 Renderizando ${entriesToShow.length} entradas...`);
    
    const entriesHtml = entriesToShow.map(([key, value]) => {
        // Truncar valores largos y escapar HTML
        const displayKey = key.length > 80 ? key.substring(0, 80) + '...' : key;
        const displayValue = typeof value === 'string' 
            ? (value.length > 100 ? value.substring(0, 100) + '...' : value)
            : JSON.stringify(value).substring(0, 100) + '...';
            
        return `
            <div class="cache-entry border-bottom py-2">
                <div class="cache-entry-key text-primary fw-bold mb-1 small">
                    <i class="fas fa-key fa-sm me-1"></i>
                    ${displayKey}
                </div>
                <div class="cache-entry-value text-muted small">
                    ${displayValue}
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = entriesHtml;
    
    // Mostrar indicador si hay más entradas
    if (entries.length > maxEntries) {
        container.innerHTML += `
            <div class="text-center p-3 bg-light text-muted">
                <i class="fas fa-ellipsis-h me-1"></i>
                ... y ${entries.length - maxEntries} entradas más
                <div class="mt-2">
                    <button class="btn btn-outline-secondary btn-sm" onclick="renderSampleEntries()">
                        Ver más ejemplos
                    </button>
                </div>
            </div>
        `;
    }
    
    console.log(`✅ ${entriesToShow.length} entradas renderizadas de ${entries.length} totales`);
}

/**
 * Refrescar información del cache
 */
async function refreshCacheInfo() {
    console.log('🔄 Refrescando información del cache...');
    
    // Mostrar indicador de carga
    showCacheLoading();
    
    // Recargar datos
    await loadCacheInfo();
    
    showSuccess('Cache actualizado correctamente');
}

/**
 * Compactar cache
 */
async function compactCache() {
    console.log('🗜️ Compactando cache...');
    
    const btn = event.target;
    const originalHtml = btn.innerHTML;
    
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Compactando...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/campaigns/api/cache/compact', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.ok) {
            showSuccess(`Cache compactado: ${data.stats.removed_entries || 0} entradas eliminadas`);
            
            // Recargar información del cache
            await loadCacheInfo();
        } else {
            showError('Error compactando cache: ' + data.error);
        }
    } catch (error) {
        console.error('Error compactando cache:', error);
        showError('Error de conexión al compactar cache');
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}
async function compactCache() {
    const btn = event.target;
    const originalHtml = btn.innerHTML;
    
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Compactando...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/campaigns/api/cache/compact', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.ok) {
            const stats = data.stats;
            showSuccess(`Cache compactado: ${stats.removed_entries} entradas eliminadas (${stats.space_saved_percent}% de espacio ahorrado)`);
            loadCacheInfo(); // Recargar
        } else {
            showError('Error compactando cache: ' + data.error);
        }
    } catch (error) {
        console.error('Error compactando cache:', error);
        showError('Error de conexión al compactar cache');
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}

/**
 * Filtrar entradas del cache
 */
function filterCacheEntries() {
    const filter = document.getElementById('cacheFilter').value.toLowerCase();
    const entries = document.querySelectorAll('.cache-entry');
    
    entries.forEach(entry => {
        const key = entry.querySelector('.cache-entry-key').textContent.toLowerCase();
        const value = entry.querySelector('.cache-entry-value').textContent.toLowerCase();
        
        if (key.includes(filter) || value.includes(filter)) {
            entry.style.display = 'block';
        } else {
            entry.style.display = 'none';
        }
    });
}

/**
 * Filtrar campañas
 */
function filterCampaigns() {
    const filter = document.getElementById('campaignFilter').value.toLowerCase();
    const campaigns = document.querySelectorAll('.campaign-card');
    
    campaigns.forEach(campaign => {
        const name = campaign.querySelector('.campaign-name').textContent.toLowerCase();
        
        if (name.includes(filter)) {
            campaign.style.display = 'block';
        } else {
            campaign.style.display = 'none';
        }
    });
}

// ====================================
// FUNCIONES DE UTILIDAD
// ====================================

/**
 * Filtrar campañas
 */
function filterCampaigns() {
    const filter = document.getElementById('campaignFilter').value.toLowerCase();
    const cards = document.querySelectorAll('.campaign-card');
    
    cards.forEach(card => {
        const campaignName = card.dataset.campaign.toLowerCase();
        const shouldShow = campaignName.includes(filter);
        card.style.display = shouldShow ? 'block' : 'none';
    });
}

/**
 * Filtrar entradas del cache
 */
function filterCacheEntries() {
    const filter = document.getElementById('cacheFilter').value.toLowerCase();
    const entries = document.querySelectorAll('.cache-entry');
    
    entries.forEach(entry => {
        const key = entry.querySelector('.cache-entry-key').textContent.toLowerCase();
        const value = entry.querySelector('.cache-entry-value').textContent.toLowerCase();
        const shouldShow = key.includes(filter) || value.includes(filter);
        entry.style.display = shouldShow ? 'block' : 'none';
    });
}

// ====================================
// FUNCIONES DE UTILIDAD
// ====================================

/**
 * Configurar modales
 */
function setupModals() {
    // Configuraciones adicionales de modales si es necesario
}

/**
 * Mostrar mensaje de éxito
 */
function showSuccess(message) {
    // TODO: Implementar sistema de notificaciones
    console.log('✅ Éxito:', message);
    alert(message); // Temporal
}

/**
 * Mostrar mensaje de error
 */
function showError(message) {
    // TODO: Implementar sistema de notificaciones
    console.error('❌ Error:', message);
    alert(message); // Temporal
}

/**
 * Formatear fecha
 */
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('es-ES');
}

/**
 * Formatear tamaño de archivo
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// ================================
// SISTEMA DE CACHE POR MISIÓN
// ================================

/**
 * Cargar caches de misión (más eficiente)
 */
async function loadMissionCaches() {
    console.log('🎯 Cargando caches de misión...');
    
    const container = document.getElementById('cacheEntries');
    
    container.innerHTML = `
        <div class="text-center p-3">
            <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
            <span class="ms-2">Cargando caches de misión...</span>
        </div>
    `;
    
    try {
        const response = await fetch('/campaigns/api/mission-caches');
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('🎯 Caches de misión recibidos:', data);
        
        if (data.ok) {
            renderMissionCaches(data.mission_caches);
        } else {
            throw new Error(data.error || 'Error desconocido');
        }
        
    } catch (error) {
        console.error('❌ Error cargando caches de misión:', error);
        container.innerHTML = `
            <div class="text-center p-4 text-danger">
                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                <h5>Error cargando caches de misión</h5>
                <p class="small">${error.message}</p>
                <button class="btn btn-outline-primary btn-sm mt-2" onclick="loadMissionCaches()">
                    <i class="fas fa-sync"></i> Reintentar
                </button>
            </div>
        `;
    }
}

/**
 * Renderizar lista de caches de misión
 */
function renderMissionCaches(missionCaches) {
    console.log('🎨 Renderizando caches de misión...');
    
    const container = document.getElementById('cacheEntries');
    
    if (!missionCaches || missionCaches.length === 0) {
        container.innerHTML = `
            <div class="text-center p-4 text-muted">
                <i class="fas fa-database fa-2x mb-2"></i>
                <p>No se encontraron caches de misión</p>
                <small>Los caches se crean automáticamente durante las traducciones</small>
                <div class="mt-3">
                    <button class="btn btn-outline-primary btn-sm" onclick="loadCacheInfo()">
                        <i class="fas fa-globe"></i> Ver Cache Global
                    </button>
                </div>
            </div>
        `;
        return;
    }
    
    // Agrupar por campaña
    const campaignGroups = {};
    missionCaches.forEach(cache => {
        if (!campaignGroups[cache.campaign]) {
            campaignGroups[cache.campaign] = [];
        }
        campaignGroups[cache.campaign].push(cache);
    });
    
    let html = `
        <div class="slide-up">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0">
                    <i class="fas fa-project-diagram me-2"></i>
                    Caches por Misión (${missionCaches.length})
                </h6>
                <div class="cache-actions">
                    <button class="btn btn-success btn-sm" onclick="syncAllMissionCaches()">
                        <i class="fas fa-sync"></i> Sincronizar Todo
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="loadCacheInfo()">
                        <i class="fas fa-home"></i> Inicio
                    </button>
                </div>
            </div>
    `;
    
    // Renderizar cada campaña
    Object.entries(campaignGroups).forEach(([campaignName, caches]) => {
        const totalEntries = caches.reduce((sum, cache) => sum + cache.entries_count, 0);
        
        html += `
            <div class="mission-cache-card fade-in">
                <div class="card-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">
                            <i class="fas fa-folder me-2"></i>
                            ${campaignName}
                        </h6>
                        <span class="badge">${caches.length} misiones • ${totalEntries.toLocaleString()} entradas</span>
                    </div>
                </div>
                <div class="card-body p-0">
        `;
        
        // Renderizar misiones de la campaña
        caches.forEach(cache => {
            const lastUpdated = cache.last_updated ? formatDate(cache.last_updated) : 'Nunca';
            const fileSize = formatFileSize(cache.file_size || 0);
            
            html += `
                <div class="mission-cache-item border-bottom py-2 px-2">
                    <div class="row align-items-center">
                        <div class="col-md-5">
                            <div class="fw-bold text-primary">${cache.mission}</div>
                            <small class="text-muted">${lastUpdated}</small>
                        </div>
                        <div class="col-md-3 text-center">
                            <span class="badge bg-info">${cache.entries_count} entradas</span>
                            <br><small class="text-muted">${fileSize}</small>
                        </div>
                        <div class="col-md-4 text-end">
                            <div class="btn-group btn-group-sm" role="group">
                                <button class="btn btn-outline-primary" 
                                        onclick="viewMissionCache('${cache.campaign}', '${cache.mission}')"
                                        title="Ver cache">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button class="btn btn-outline-success" 
                                        onclick="syncMissionCache('${cache.campaign}', '${cache.mission}')"
                                        title="Sincronizar">
                                    <i class="fas fa-sync"></i>
                                </button>
                                <button class="btn btn-outline-warning" 
                                        onclick="compactMissionCache('${cache.campaign}', '${cache.mission}')"
                                        title="Compactar">
                                    <i class="fas fa-compress"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    html += `
        </div>
    `;
    
    container.innerHTML = html;
    console.log(`✅ ${missionCaches.length} caches de misión renderizados`);
}

/**
 * Ver cache de una misión específica
 */
async function viewMissionCache(campaign, mission) {
    console.log(`👀 Viendo cache de ${campaign}/${mission}`);
    
    const container = document.getElementById('cacheEntries');
    
    container.innerHTML = `
        <div class="text-center p-3">
            <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
            <span class="ms-2">Cargando cache de ${mission}...</span>
        </div>
    `;
    
    try {
        const response = await fetch(`/campaigns/api/mission-cache/${encodeURIComponent(campaign)}/${encodeURIComponent(mission)}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.ok) {
            renderSingleMissionCache(data);
        } else {
            throw new Error(data.error || 'Error desconocido');
        }
        
    } catch (error) {
        console.error('❌ Error cargando cache de misión:', error);
        container.innerHTML = `
            <div class="text-center p-4 text-danger">
                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                <h5>Error cargando cache</h5>
                <p class="small">${error.message}</p>
                <button class="btn btn-outline-primary btn-sm mt-2" onclick="loadMissionCaches()">
                    <i class="fas fa-arrow-left"></i> Volver
                </button>
            </div>
        `;
    }
}

/**
 * Renderizar cache de una misión específica con capacidades de edición
 */
function renderSingleMissionCache(data) {
    console.log('🎨 Renderizando cache individual editable:', data.mission);
    
    const container = document.getElementById('cacheEntries');
    const entries = Object.entries(data.cache.entries || {});
    
    // Almacenar datos globalmente para edición
    window.currentMissionCache = {
        campaign: data.campaign,
        mission: data.mission,
        entries: data.cache.entries || {},
        originalData: JSON.parse(JSON.stringify(data.cache.entries || {}))
    };
    
    let html = `
        <div class="d-flex justify-content-between align-items-center mb-3">
            <div>
                <h6 class="mb-1">
                    <i class="fas fa-edit me-2"></i>
                    ${data.mission} - Editor de Traducciones
                </h6>
                <small class="text-muted">${data.campaign} • ${entries.length} entradas editables</small>
            </div>
            <div class="btn-group" role="group">
                <button class="btn btn-outline-primary btn-sm" onclick="loadMissionCaches()">
                    <i class="fas fa-arrow-left"></i> Volver
                </button>
                <button class="btn btn-outline-warning btn-sm" onclick="toggleEditMode()">
                    <i class="fas fa-edit"></i> <span id="editModeText">Activar Edición</span>
                </button>
                <button class="btn btn-outline-success btn-sm" onclick="saveMissionCache()">
                    <i class="fas fa-save"></i> Guardar Cambios
                </button>
                <button class="btn btn-outline-info btn-sm" onclick="syncMissionCache('${data.campaign}', '${data.mission}')">
                    <i class="fas fa-sync"></i> Sincronizar
                </button>
            </div>
        </div>
        
        <!-- Búsqueda y filtros -->
        <div class="row mb-3">
            <div class="col-md-6">
                <div class="input-group">
                    <span class="input-group-text"><i class="fas fa-search"></i></span>
                    <input type="text" class="form-control" id="searchEntries" 
                           placeholder="Buscar en original o traducción..." 
                           onkeyup="filterCacheEntries()">
                </div>
            </div>
            <div class="col-md-6">
                <select class="form-select" id="filterStatus" onchange="filterCacheEntries()">
                    <option value="all">Todas las entradas</option>
                    <option value="translated">Solo traducidas</option>
                    <option value="untranslated">Sin traducir</option>
                    <option value="modified">Modificadas</option>
                </select>
            </div>
        </div>
    `;
    
    if (entries.length === 0) {
        html += `
            <div class="text-center p-4 text-muted">
                <i class="fas fa-database fa-2x mb-2"></i>
                <p>Cache vacío</p>
                <small>Las traducciones aparecerán aquí cuando uses el Orquestador</small>
            </div>
        `;
    } else {
        html += `
            <div id="cacheEntriesList" class="cache-entries-list">
        `;
        
        // Renderizar todas las entradas editables
        entries.forEach(([key, value], index) => {
            const safeKey = encodeURIComponent(key);
            const original = value.original || '';
            const translated = value.translated || '';
            const context = value.context || '';
            
            html += `
                <div class="cache-entry-editable border rounded mb-2 p-3" data-key="${safeKey}" data-index="${index}">
                    <!-- Header de entrada -->
                    <div class="entry-header d-flex justify-content-between align-items-start mb-2">
                        <div class="entry-key-info flex-fill">
                            <div class="fw-bold text-primary small mb-1">
                                <i class="fas fa-key fa-sm me-1"></i>
                                Entrada ${index + 1}
                            </div>
                            <code class="small text-muted">${key}</code>
                        </div>
                        <div class="entry-actions">
                            <div class="btn-group btn-group-sm" role="group">
                                <button class="btn btn-outline-success btn-sm edit-btn" 
                                        onclick="enableEntryEdit('${safeKey}')" 
                                        title="Editar entrada">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button class="btn btn-outline-warning btn-sm save-btn d-none" 
                                        onclick="saveEntry('${safeKey}')" 
                                        title="Guardar cambios">
                                    <i class="fas fa-save"></i>
                                </button>
                                <button class="btn btn-outline-secondary btn-sm cancel-btn d-none" 
                                        onclick="cancelEntryEdit('${safeKey}')" 
                                        title="Cancelar edición">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Contenido de la entrada -->
                    <div class="row">
                        <div class="col-md-6">
                            <label class="form-label small fw-bold">📝 Texto Original:</label>
                            <div class="original-text border rounded p-2 bg-light small">
                                ${original}
                            </div>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small fw-bold">🌍 Traducción:</label>
                            <!-- Vista de solo lectura -->
                            <div class="translation-display border rounded p-2 ${translated ? 'bg-success bg-opacity-10' : 'bg-warning bg-opacity-10'} small">
                                ${translated || '<em class="text-muted">Sin traducir</em>'}
                            </div>
                            <!-- Campo de edición (oculto inicialmente) -->
                            <textarea class="form-control translation-edit d-none" 
                                      rows="3" 
                                      placeholder="Escribe la traducción aquí..."
                                      data-key="${safeKey}">${translated}</textarea>
                        </div>
                    </div>
                    
                    <!-- Contexto (si existe) -->
                    ${context ? `
                        <div class="mt-2">
                            <label class="form-label small fw-bold">ℹ️ Contexto:</label>
                            <div class="context-text small text-muted p-2 bg-info bg-opacity-10 rounded">
                                ${context}
                            </div>
                        </div>
                    ` : ''}
                    
                    <!-- Estado de modificación -->
                    <div class="entry-status mt-2 d-none">
                        <small class="badge bg-warning">
                            <i class="fas fa-exclamation-circle"></i> Modificado - Sin guardar
                        </small>
                    </div>
                </div>
            `;
        });
        
        html += `
            </div>
        `;
        
        // Información de paginación si hay muchas entradas
        if (entries.length > 100) {
            html += `
                <div class="text-center p-3 bg-info bg-opacity-10 text-info rounded">
                    <i class="fas fa-info-circle me-1"></i>
                    Mostrando todas las ${entries.length} entradas. Usa la búsqueda para filtrar resultados.
                </div>
            `;
        }
    }
    
    container.innerHTML = html;
    console.log(`✅ Cache individual renderizado con edición: ${entries.length} entradas`);
}

/**
 * Sincronizar cache de una misión con el global
 */
async function syncMissionCache(campaign, mission) {
    console.log(`🔄 Sincronizando cache de ${campaign}/${mission}`);
    
    try {
        const response = await fetch(`/campaigns/api/sync/mission/${encodeURIComponent(campaign)}/${encodeURIComponent(mission)}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const data = await response.json();
        
        if (data.ok) {
            showNotification(`✅ ${data.message}`, 'success');
            console.log(`✅ Sincronización exitosa: ${data.synced_entries} entradas`);
        } else {
            throw new Error(data.error || 'Error en sincronización');
        }
        
    } catch (error) {
        console.error('❌ Error sincronizando:', error);
        showNotification(`❌ Error: ${error.message}`, 'error');
    }
}

/**
 * Sincronizar todos los caches de misión
 */
async function syncAllMissionCaches() {
    console.log('🔄 Sincronizando todos los caches...');
    
    const container = document.getElementById('cacheEntries');
    const originalContent = container.innerHTML;
    
    container.innerHTML = `
        <div class="text-center p-4">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-2">Sincronizando todos los caches...</p>
            <small class="text-muted">Esto puede tomar unos segundos</small>
        </div>
    `;
    
    try {
        const response = await fetch('/campaigns/api/sync/all', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const data = await response.json();
        
        if (data.ok) {
            showNotification(`✅ ${data.message}`, 'success');
            console.log(`✅ Sincronización global exitosa: ${data.total_synced} entradas`);
            // Recargar lista
            loadMissionCaches();
        } else {
            throw new Error(data.error || 'Error en sincronización');
        }
        
    } catch (error) {
        console.error('❌ Error sincronizando todos:', error);
        showNotification(`❌ Error: ${error.message}`, 'error');
        container.innerHTML = originalContent;
    }
}

/**
 * Compactar cache de una misión
 */
async function compactMissionCache(campaign, mission) {
    console.log(`🗜️ Compactando cache de ${campaign}/${mission}`);
    
    try {
        const response = await fetch(`/campaigns/api/compact/mission/${encodeURIComponent(campaign)}/${encodeURIComponent(mission)}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const data = await response.json();
        
        if (data.ok) {
            showNotification(`✅ ${data.message}`, 'success');
            console.log(`✅ Compactación exitosa: ${data.duplicates_removed} duplicados eliminados`);
            // Recargar lista
            loadMissionCaches();
        } else {
            throw new Error(data.error || 'Error compactando');
        }
        
    } catch (error) {
        console.error('❌ Error compactando:', error);
        showNotification(`❌ Error: ${error.message}`, 'error');
    }
}

/**
 * Habilitar edición de una entrada específica
 */
function enableEntryEdit(encodedKey) {
    const key = decodeURIComponent(encodedKey);
    const entryDiv = document.querySelector(`[data-key="${encodedKey}"]`);
    
    if (!entryDiv) {
        console.error('Entrada no encontrada:', key);
        return;
    }
    
    // Mostrar campo de edición y ocultar display
    const displayDiv = entryDiv.querySelector('.translation-display');
    const editTextarea = entryDiv.querySelector('.translation-edit');
    const editBtn = entryDiv.querySelector('.edit-btn');
    const saveBtn = entryDiv.querySelector('.save-btn');
    const cancelBtn = entryDiv.querySelector('.cancel-btn');
    
    if (displayDiv && editTextarea && editBtn && saveBtn && cancelBtn) {
        displayDiv.classList.add('d-none');
        editTextarea.classList.remove('d-none');
        editBtn.classList.add('d-none');
        saveBtn.classList.remove('d-none');
        cancelBtn.classList.remove('d-none');
        
        // Enfocar el textarea
        editTextarea.focus();
        
        console.log(`📝 Modo edición habilitado para: ${key.substring(0, 50)}...`);
    }
}

/**
 * Cancelar edición de entrada
 */
function cancelEntryEdit(encodedKey) {
    const key = decodeURIComponent(encodedKey);
    const entryDiv = document.querySelector(`[data-key="${encodedKey}"]`);
    
    if (!entryDiv) {
        console.error('Entrada no encontrada:', key);
        return;
    }
    
    // Restaurar vista original
    const displayDiv = entryDiv.querySelector('.translation-display');
    const editTextarea = entryDiv.querySelector('.translation-edit');
    const editBtn = entryDiv.querySelector('.edit-btn');
    const saveBtn = entryDiv.querySelector('.save-btn');
    const cancelBtn = entryDiv.querySelector('.cancel-btn');
    const statusDiv = entryDiv.querySelector('.entry-status');
    
    if (displayDiv && editTextarea && editBtn && saveBtn && cancelBtn) {
        // Restaurar valor original
        const originalValue = window.currentMissionCache.originalData[key]?.translated || '';
        editTextarea.value = originalValue;
        
        displayDiv.classList.remove('d-none');
        editTextarea.classList.add('d-none');
        editBtn.classList.remove('d-none');
        saveBtn.classList.add('d-none');
        cancelBtn.classList.add('d-none');
        
        // Ocultar estado de modificación
        if (statusDiv) {
            statusDiv.classList.add('d-none');
        }
        
        console.log(`❌ Edición cancelada para: ${key.substring(0, 50)}...`);
    }
}

/**
 * Guardar entrada individual
 */
async function saveEntry(encodedKey) {
    const key = decodeURIComponent(encodedKey);
    const entryDiv = document.querySelector(`[data-key="${encodedKey}"]`);
    
    if (!entryDiv) {
        console.error('Entrada no encontrada:', key);
        return;
    }
    
    const editTextarea = entryDiv.querySelector('.translation-edit');
    const newTranslation = editTextarea.value.trim();
    
    if (!newTranslation) {
        showNotification('❌ La traducción no puede estar vacía', 'error');
        return;
    }
    
    console.log(`💾 Guardando traducción para: ${key.substring(0, 50)}...`);
    
    try {
        const response = await fetch(`/campaigns/api/update-translation/${encodeURIComponent(window.currentMissionCache.campaign)}/${encodeURIComponent(window.currentMissionCache.mission)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                key: key,
                translation: newTranslation,
                context: ''
            })
        });
        
        const data = await response.json();
        
        if (data.ok) {
            // Actualizar cache local
            if (window.currentMissionCache.entries[key]) {
                window.currentMissionCache.entries[key].translated = newTranslation;
                window.currentMissionCache.entries[key].user_modified = true;
            }
            
            // Actualizar display
            const displayDiv = entryDiv.querySelector('.translation-display');
            displayDiv.innerHTML = newTranslation;
            displayDiv.classList.add('bg-success', 'bg-opacity-10');
            
            // Volver a modo vista
            const editBtn = entryDiv.querySelector('.edit-btn');
            const saveBtn = entryDiv.querySelector('.save-btn');
            const cancelBtn = entryDiv.querySelector('.cancel-btn');
            const statusDiv = entryDiv.querySelector('.entry-status');
            
            displayDiv.classList.remove('d-none');
            editTextarea.classList.add('d-none');
            editBtn.classList.remove('d-none');
            saveBtn.classList.add('d-none');
            cancelBtn.classList.add('d-none');
            
            // Mostrar estado modificado
            if (statusDiv) {
                statusDiv.classList.remove('d-none');
            }
            
            showNotification('✅ Traducción guardada exitosamente', 'success');
            console.log(`✅ Traducción guardada: ${key.substring(0, 50)}...`);
            
        } else {
            throw new Error(data.error || 'Error desconocido');
        }
        
    } catch (error) {
        console.error('❌ Error guardando traducción:', error);
        showNotification(`❌ Error guardando: ${error.message}`, 'error');
    }
}

/**
 * Guardar todos los cambios del cache de misión
 */
async function saveMissionCache() {
    if (!window.currentMissionCache) {
        showNotification('❌ No hay cache cargado para guardar', 'error');
        return;
    }
    
    console.log('💾 Guardando todos los cambios del cache...');
    
    // Recopilar todas las traducciones modificadas
    const updates = {};
    const textareas = document.querySelectorAll('.translation-edit');
    
    textareas.forEach(textarea => {
        const key = decodeURIComponent(textarea.dataset.key);
        const newValue = textarea.value.trim();
        const originalValue = window.currentMissionCache.originalData[key]?.translated || '';
        
        if (newValue && newValue !== originalValue) {
            updates[key] = newValue;
        }
    });
    
    if (Object.keys(updates).length === 0) {
        showNotification('ℹ️ No hay cambios para guardar', 'info');
        return;
    }
    
    try {
        const response = await fetch(`/campaigns/api/update-multiple-translations/${encodeURIComponent(window.currentMissionCache.campaign)}/${encodeURIComponent(window.currentMissionCache.mission)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                updates: updates
            })
        });
        
        const data = await response.json();
        
        if (data.ok) {
            // Actualizar cache local
            Object.keys(updates).forEach(key => {
                if (window.currentMissionCache.entries[key]) {
                    window.currentMissionCache.entries[key].translated = updates[key];
                    window.currentMissionCache.entries[key].user_modified = true;
                }
            });
            
            // Actualizar datos originales para futuras comparaciones
            window.currentMissionCache.originalData = JSON.parse(JSON.stringify(window.currentMissionCache.entries));
            
            showNotification(`✅ ${data.updated_count} traducciones guardadas exitosamente`, 'success');
            console.log(`✅ Cache guardado: ${data.updated_count} cambios`);
            
            // Sincronización automática después de guardar
            showNotification('🔄 Sincronizando con cache global...', 'info');
            setTimeout(async () => {
                try {
                    await syncMissionCache(window.currentMissionCache.campaign, window.currentMissionCache.mission);
                    showNotification('✅ Sincronización completada', 'success');
                } catch (error) {
                    console.error('❌ Error en sincronización automática:', error);
                }
                
                // Recargar vista para mostrar cambios
                setTimeout(() => {
                    viewMissionCache(window.currentMissionCache.campaign, window.currentMissionCache.mission);
                }, 500);
            }, 1000);
            
        } else {
            throw new Error(data.error || 'Error desconocido');
        }
        
    } catch (error) {
        console.error('❌ Error guardando cache:', error);
        showNotification(`❌ Error guardando: ${error.message}`, 'error');
    }
}

/**
 * Filtrar entradas del cache
 */
function filterCacheEntries() {
    const searchText = document.getElementById('searchEntries')?.value.toLowerCase() || '';
    const filterStatus = document.getElementById('filterStatus')?.value || 'all';
    
    const entries = document.querySelectorAll('.cache-entry-editable');
    
    entries.forEach(entry => {
        const keyText = entry.querySelector('code').textContent.toLowerCase();
        const originalText = entry.querySelector('.original-text').textContent.toLowerCase();
        const translatedText = entry.querySelector('.translation-display').textContent.toLowerCase();
        
        // Filtro de búsqueda
        const matchesSearch = !searchText || 
                            keyText.includes(searchText) || 
                            originalText.includes(searchText) || 
                            translatedText.includes(searchText);
        
        // Filtro de estado
        let matchesStatus = true;
        if (filterStatus === 'translated') {
            matchesStatus = !translatedText.includes('sin traducir');
        } else if (filterStatus === 'untranslated') {
            matchesStatus = translatedText.includes('sin traducir');
        } else if (filterStatus === 'modified') {
            matchesStatus = entry.querySelector('.entry-status:not(.d-none)') !== null;
        }
        
        // Mostrar/ocultar entrada
        if (matchesSearch && matchesStatus) {
            entry.style.display = '';
        } else {
            entry.style.display = 'none';
        }
    });
    
    console.log(`🔍 Filtros aplicados: "${searchText}" | ${filterStatus}`);
}

/**
 * Alternar modo de edición global
 */
function toggleEditMode() {
    const editModeText = document.getElementById('editModeText');
    const isEditMode = editModeText.textContent.includes('Desactivar');
    
    if (isEditMode) {
        // Desactivar modo edición
        document.querySelectorAll('.translation-edit:not(.d-none)').forEach(textarea => {
            const encodedKey = encodeURIComponent(textarea.dataset.key);
            cancelEntryEdit(encodedKey);
        });
        editModeText.textContent = 'Activar Edición';
    } else {
        // Activar modo edición para todas las entradas visibles
        document.querySelectorAll('.cache-entry-editable:not([style*="display: none"]) .edit-btn:not(.d-none)').forEach(btn => {
            btn.click();
        });
        editModeText.textContent = 'Desactivar Edición';
    }
}

/**
 * Mostrar notificación temporal
 */
function showNotification(message, type = 'info') {
    const alertClass = type === 'success' ? 'alert-success' : 
                     type === 'error' ? 'alert-danger' : 'alert-info';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// ====================================
// FUNCIONES PARA VISUALIZACIÓN DE ARCHIVOS LUA
// ====================================

/**
 * Ver archivos LUA (original vs traducido)
 */
async function viewLuaFiles(campaignName, missionName) {
    try {
        showLoadingModal();
        
        // Obtener datos de archivos LUA
        const response = await fetch(`/api/campaigns/${encodeURIComponent(campaignName)}/missions/${encodeURIComponent(missionName)}/lua/view`);
        const data = await response.json();
        
        hideLoadingModal();
        
        if (!data.ok) {
            showError(`Error cargando archivos: ${data.error}`);
            return;
        }
        
        // Crear y mostrar modal de visualización
        createLuaViewModal(data);
        
    } catch (error) {
        hideLoadingModal();
        console.error('Error viewing LUA files:', error);
        showError(`Error cargando archivos LUA: ${error.message}`);
    }
}

/**
 * Crear modal de visualización de archivos LUA
 */
function createLuaViewModal(data) {
    const { campaign_name, mission_name, files, warnings } = data;
    
    // Crear modal si no existe
    let modal = document.getElementById('luaViewModal');
    if (modal) {
        modal.remove();
    }
    
    modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'luaViewModal';
    modal.tabIndex = -1;
    
    const hasOriginal = files.original && files.original.content;
    const hasTranslated = files.translated && files.translated.content;
    
    modal.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-file-code"></i> Archivos LUA - ${mission_name}
                        <small class="text-muted d-block">${campaign_name}</small>
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    ${createWarningAlerts(warnings)}
                    ${createLuaViewTabs(files)}
                </div>
                <div class="modal-footer">
                    <div class="me-auto">
                        ${hasOriginal && hasTranslated ? `
                            <button type="button" class="btn btn-outline-info btn-sm" onclick="compareLuaFiles('${campaign_name}', '${mission_name}')">
                                <i class="fas fa-chart-bar"></i> Ver Estadísticas
                            </button>
                        ` : ''}
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-outline-success btn-sm dropdown-toggle" type="button" data-bs-toggle="dropdown">
                            <i class="fas fa-download"></i> Descargar
                        </button>
                        <ul class="dropdown-menu">
                            ${hasOriginal ? '<li><a class="dropdown-item" onclick="downloadLuaFile(\'' + campaign_name + '\', \'' + mission_name + '\', \'original\')">📄 Original (Inglés)</a></li>' : ''}
                            ${hasTranslated ? '<li><a class="dropdown-item" onclick="downloadLuaFile(\'' + campaign_name + '\', \'' + mission_name + '\', \'translated\')">📝 Traducido (Español)</a></li>' : ''}
                        </ul>
                    </div>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="fas fa-times"></i> Cerrar
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Mostrar modal
    const bsModal = new bootstrap.Modal(modal);
    
    // Añadir evento para limpiar cuando se cierre
    modal.addEventListener('hidden.bs.modal', function () {
        // Asegurar que el modal de carga esté cerrado
        hideLoadingModal();
        
        // Limpiar el modal del DOM
        if (modal && modal.parentNode) {
            modal.remove();
        }
    });
    
    bsModal.show();
    
    // Configurar syntax highlighting
    setupSyntaxHighlighting();
}

/**
 * Crear alertas de advertencia
 */
function createWarningAlerts(warnings) {
    if (!warnings || warnings.length === 0) {
        return '';
    }
    
    let alertsHtml = '';
    
    warnings.forEach(warning => {
        const alertClass = warning.severity === 'error' ? 'alert-danger' : 'alert-warning';
        const iconClass = warning.severity === 'error' ? 'fa-exclamation-triangle' : 'fa-exclamation-circle';
        
        alertsHtml += `
            <div class="alert ${alertClass} alert-dismissible fade show mb-3" role="alert">
                <i class="fas ${iconClass} me-2"></i>
                <strong>${warning.type === 'already_translated' ? 'Archivo Ya Traducido' : 'Retradución Detectada'}:</strong>
                <br>${warning.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
    });
    
    return alertsHtml;
}

/**
 * Crear pestañas de visualización
 */
function createLuaViewTabs(files) {
    const tabs = [];
    const tabContent = [];
    
    if (files.original && files.original.content) {
        const detectedLang = files.original.detected_language || 'unknown';
        const langIcon = detectedLang === 'spanish' ? '🇪🇸' : detectedLang === 'english' ? '🇬🇧' : '❓';
        const langText = detectedLang === 'spanish' ? 'Español' : detectedLang === 'english' ? 'Inglés' : 'Desconocido';
        const isAlreadyTranslated = files.original.is_already_translated;
        
        tabs.push(`
            <li class="nav-item" role="presentation">
                <button class="nav-link active ${isAlreadyTranslated ? 'border-warning' : ''}" id="original-tab" data-bs-toggle="tab" data-bs-target="#original-content" type="button">
                    <i class="fas fa-globe"></i> Original (${langIcon} ${langText})
                    <span class="badge bg-secondary ms-2">${files.original.lines} líneas</span>
                    ${isAlreadyTranslated ? '<i class="fas fa-exclamation-triangle text-warning ms-1" title="Archivo ya traducido"></i>' : ''}
                </button>
            </li>
        `);
        
        tabContent.push(`
            <div class="tab-pane fade show active" id="original-content">
                <div class="file-info mb-2">
                    <small class="text-muted">
                        <i class="fas fa-file"></i> ${files.original.path} 
                        <span class="ms-2"><i class="fas fa-weight"></i> ${(files.original.size / 1024).toFixed(1)} KB</span>
                    </small>
                </div>
                <pre class="lua-code-viewer"><code class="language-lua">${escapeHtml(files.original.content)}</code></pre>
            </div>
        `);
    }
    
    if (files.translated && files.translated.content) {
        const isActive = !files.original;
        const translatedLang = files.translated.detected_language || 'unknown';
        const translatedIcon = translatedLang === 'spanish' ? '🇪🇸' : translatedLang === 'english' ? '🇬🇧' : '❓';
        const translatedText = translatedLang === 'spanish' ? 'Español' : translatedLang === 'english' ? 'Inglés' : 'Desconocido';
        
        tabs.push(`
            <li class="nav-item" role="presentation">
                <button class="nav-link ${isActive ? 'active' : ''}" id="translated-tab" data-bs-toggle="tab" data-bs-target="#translated-content" type="button">
                    <i class="fas fa-language"></i> Traducido (${translatedIcon} ${translatedText})
                    <span class="badge bg-success ms-2">${files.translated.lines} líneas</span>
                </button>
            </li>
        `);
        
        tabContent.push(`
            <div class="tab-pane fade ${isActive ? 'show active' : ''}" id="translated-content">
                <div class="file-info mb-2">
                    <small class="text-muted">
                        <i class="fas fa-file"></i> ${files.translated.path}
                        <span class="ms-2"><i class="fas fa-weight"></i> ${(files.translated.size / 1024).toFixed(1)} KB</span>
                    </small>
                </div>
                <pre class="lua-code-viewer"><code class="language-lua">${escapeHtml(files.translated.content)}</code></pre>
            </div>
        `);
    }
    
    // Nota: Esta pestaña se reserva para archivos placeholders si es necesario en el futuro
    // La funcionalidad de archivo original ahora se muestra en la pestaña 'original'
    
    if (tabs.length === 0) {
        return `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i> 
                No se encontraron archivos LUA para mostrar.
            </div>
        `;
    }
    
    return `
        <ul class="nav nav-tabs" id="luaFileTabs" role="tablist">
            ${tabs.join('')}
        </ul>
        <div class="tab-content" id="luaFileTabContent">
            ${tabContent.join('')}
        </div>
    `;
}

/**
 * Comparar archivos LUA y mostrar estadísticas
 */
async function compareLuaFiles(campaignName, missionName) {
    try {
        const response = await fetch(`/api/campaigns/${encodeURIComponent(campaignName)}/missions/${encodeURIComponent(missionName)}/lua/compare`);
        const data = await response.json();
        
        if (!data.ok) {
            showError(`Error generando comparación: ${data.error}`);
            return;
        }
        
        // Mostrar estadísticas en modal secundario
        showLuaComparisonModal(data);
        
    } catch (error) {
        console.error('Error comparing LUA files:', error);
        showError(`Error comparando archivos: ${error.message}`);
    }
}

/**
 * Mostrar modal de comparación de archivos LUA
 */
function showLuaComparisonModal(data) {
    const { statistics, samples } = data;
    
    // Crear modal de estadísticas
    let modal = document.getElementById('luaComparisonModal');
    if (modal) {
        modal.remove();
    }
    
    modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'luaComparisonModal';
    modal.tabIndex = -1;
    
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-chart-bar"></i> Estadísticas de Traducción
                        <small class="text-muted d-block">${data.mission_name} - ${data.campaign_name}</small>
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h6 class="mb-0">📊 Resumen General</h6>
                                </div>
                                <div class="card-body">
                                    <div class="stat-item">
                                        <label>Total Original:</label>
                                        <span class="badge bg-secondary">${statistics.original_entries}</span>
                                    </div>
                                    <div class="stat-item">
                                        <label>Total Traducido:</label>
                                        <span class="badge bg-primary">${statistics.translated_entries}</span>
                                    </div>
                                    <div class="stat-item">
                                        <label>Realmente Traducido:</label>
                                        <span class="badge bg-success">${statistics.actually_translated}</span>
                                    </div>
                                    <div class="stat-item">
                                        <label>Sin Cambios:</label>
                                        <span class="badge bg-warning">${statistics.unchanged_entries}</span>
                                    </div>
                                    <div class="stat-item">
                                        <label>Tasa de Traducción:</label>
                                        <span class="badge bg-info">${statistics.translation_rate}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h6 class="mb-0">🔄 Diferencias</h6>
                                </div>
                                <div class="card-body">
                                    <div class="stat-item">
                                        <label>Entradas Comunes:</label>
                                        <span class="badge bg-primary">${statistics.common_entries}</span>
                                    </div>
                                    <div class="stat-item">
                                        <label>Solo en Original:</label>
                                        <span class="badge bg-warning">${statistics.only_in_original}</span>
                                    </div>
                                    <div class="stat-item">
                                        <label>Solo en Traducido:</label>
                                        <span class="badge bg-info">${statistics.only_in_translated}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    ${createComparisonSamples(samples)}
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="fas fa-times"></i> Cerrar
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Mostrar modal
    const bsModal = new bootstrap.Modal(modal);
    
    // Añadir evento para limpiar cuando se cierre
    modal.addEventListener('hidden.bs.modal', function () {
        // Asegurar que el modal de carga esté cerrado
        hideLoadingModal();
        
        // Limpiar el modal del DOM
        if (modal && modal.parentNode) {
            modal.remove();
        }
    });
    
    bsModal.show();
}

/**
 * Crear muestras de comparación
 */
function createComparisonSamples(samples) {
    let html = '<div class="mt-3">';
    
    if (samples.translated_samples && samples.translated_samples.length > 0) {
        html += `
            <div class="card mb-3">
                <div class="card-header">
                    <h6 class="mb-0">✅ Ejemplos Traducidos</h6>
                </div>
                <div class="card-body">
        `;
        
        samples.translated_samples.forEach(sample => {
            html += `
                <div class="comparison-sample mb-2">
                    <small class="text-muted">${escapeHtml(sample.key)}</small>
                    <div class="original-text"><strong>EN:</strong> ${escapeHtml(sample.original)}</div>
                    <div class="translated-text"><strong>ES:</strong> ${escapeHtml(sample.translated)}</div>
                </div>
            `;
        });
        
        html += '</div></div>';
    }
    
    if (samples.unchanged_samples && samples.unchanged_samples.length > 0) {
        html += `
            <div class="card mb-3">
                <div class="card-header">
                    <h6 class="mb-0">⚠️ Sin Traducir</h6>
                </div>
                <div class="card-body">
        `;
        
        samples.unchanged_samples.forEach(sample => {
            html += `
                <div class="unchanged-sample mb-2">
                    <small class="text-muted">${escapeHtml(sample.key)}</small>
                    <div>${escapeHtml(sample.value)}</div>
                </div>
            `;
        });
        
        html += '</div></div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * Descargar archivo LUA
 */
async function downloadLuaFile(campaignName, missionName, type) {
    try {
        const response = await fetch(`/api/campaigns/${encodeURIComponent(campaignName)}/missions/${encodeURIComponent(missionName)}/lua/download?type=${type}`);
        
        if (!response.ok) {
            const errorData = await response.json();
            showError(`Error descargando archivo: ${errorData.error}`);
            return;
        }
        
        // Crear enlace de descarga
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `${campaignName}_${missionName}_${type}.lua`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification('Archivo descargado exitosamente', 'success');
        
    } catch (error) {
        console.error('Error downloading LUA file:', error);
        showError(`Error descargando archivo: ${error.message}`);
    }
}

/**
 * Configurar syntax highlighting
 */
function setupSyntaxHighlighting() {
    // Si Prism.js está disponible, úsalo
    if (typeof Prism !== 'undefined') {
        setTimeout(() => {
            Prism.highlightAll();
        }, 100);
    }
}

/**
 * Escapar HTML para mostrar texto seguro
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Función de limpieza general de modales
 */
function cleanupModals() {
    console.log('🧹 Limpiando modales...');
    
    // Cerrar modal de carga si existe
    hideLoadingModal();
    
    // Limpiar todos los backdrops
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => {
        console.log('🧹 Removiendo backdrop');
        backdrop.remove();
    });
    
    // Restaurar clases del body
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
    
    // Limpiar modales temporales
    const temporaryModals = document.querySelectorAll('#luaViewModal, #luaComparisonModal, #loadingModal');
    temporaryModals.forEach(modal => {
        if (modal && modal.parentNode) {
            console.log(`🧹 Removiendo modal: ${modal.id}`);
            modal.remove();
        }
    });
    
    console.log('✅ Limpieza de modales completada');
}

// Hacer función disponible globalmente
window.cleanupModals = cleanupModals;

/**
 * Mostrar modal de carga
 */
function showLoadingModal() {
    // Primero, asegurar que no hay modales de carga previos
    const existingModal = document.getElementById('loadingModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Limpiar cualquier backdrop que pueda quedar
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => backdrop.remove());
    
    // Crear nuevo modal de carga
    const loadingModal = document.createElement('div');
    loadingModal.className = 'modal fade';
    loadingModal.id = 'loadingModal';
    loadingModal.innerHTML = `
        <div class="modal-dialog modal-sm">
            <div class="modal-content">
                <div class="modal-body text-center">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2 mb-0">Cargando archivos...</p>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(loadingModal);
    
    // Mostrar modal
    const bsModal = new bootstrap.Modal(loadingModal, {
        backdrop: 'static',
        keyboard: false
    });
    bsModal.show();
}

/**
 * Ocultar modal de carga
 */
function hideLoadingModal() {
    const loadingModal = document.getElementById('loadingModal');
    if (loadingModal) {
        try {
            // Intentar obtener instancia existente
            let bsModal = bootstrap.Modal.getInstance(loadingModal);
            
            // Si no existe, crear una nueva instancia
            if (!bsModal) {
                bsModal = new bootstrap.Modal(loadingModal);
            }
            
            // Ocultar modal
            bsModal.hide();
            
            // Como medida adicional, remover el modal del DOM después de un delay
            setTimeout(() => {
                const backdrop = document.querySelector('.modal-backdrop');
                if (backdrop) {
                    backdrop.remove();
                }
                
                if (loadingModal && loadingModal.parentNode) {
                    loadingModal.remove();
                }
                
                // Limpiar clases del body que puedan quedar
                document.body.classList.remove('modal-open');
                document.body.style.removeProperty('overflow');
                document.body.style.removeProperty('padding-right');
            }, 300);
            
        } catch (error) {
            console.error('Error cerrando modal de carga:', error);
            
            // Forzar limpieza manual si hay error
            if (loadingModal) {
                loadingModal.remove();
            }
            
            // Limpiar backdrop manualmente
            const backdrops = document.querySelectorAll('.modal-backdrop');
            backdrops.forEach(backdrop => backdrop.remove());
            
            // Restaurar body
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('overflow');
            document.body.style.removeProperty('padding-right');
        }
    }
}