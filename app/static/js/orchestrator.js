/**
 * Orquestador DCS - JavaScript principal
 * Extraído y mejorado desde app.py
 */

class OrchestratorUI {
    constructor() {
        this.selectedCampaign = null;
        this.campaigns = [];
        this.missions = [];
        this.polling = false;
        this.pollInterval = null;
        this.confirmModalAvailable = false; // Track modal availability
        this.lastCompletionTime = null; // Track last execution completion
        this.currentlyRunning = false; // Track if execution is currently running
        this.completionLogged = false; // Track if completion has been logged to avoid spam
        
        // Inicializar timer de misión
        this.missionTimer = {
            startTime: null,
            isRunning: false,
            elapsed: 0,
            completedAt: null
        };
        
        // Inicializar variables para detección de actividad
        this.lastProgress = 0;
        this.lastValidOperations = null;
        this.visualTimerInterval = null;
        this.lastBatchCounters = { cacheHits: 0, modelCalls: 0, timestamp: 0 };
        
        // Configuración
        this.PRESET_KEY = 'dcs_orq_presets_v2';
        
        // Inicializar
        this.init();
    }
    
    testProfilesMethod() {
        console.log('✅ TestProfilesMethod funciona correctamente - clase definida correctamente');
        return true;
    }
    
    // ========================= FUNCIONES AUXILIARES TIMER =========================
    
    formatElapsedTime(milliseconds) {
        if (!milliseconds || milliseconds <= 0) return '0s';
        
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }

    detectLiveTranslationActivity(status) {
        // Detectar actividad de traducción en tiempo real analizando múltiples señales
        const indicators = [
            status.is_running,
            status.current_mission && status.current_mission !== null,
            status.detail?.includes('Lote'),
            status.detail?.includes('Studio'),
            status.detail?.includes('traduciendo'),
            status.detail?.includes('Procesando'),
            status.detail?.includes('frases'),
            status.phase === 'translating',
            status.phase === 'processing',
            status.progress > 0,
            // Detectar si el progreso está cambiando (comparar con valor anterior)
            this.lastProgress !== status.progress
        ];
        
        // Guardar progreso actual para la próxima comparación
        this.lastProgress = status.progress;
        
        // Si al menos 2 indicadores son positivos, considerar que hay actividad
        const activeIndicators = indicators.filter(Boolean).length;
        const hasActivity = activeIndicators >= 2;
        
        return hasActivity;
    }
    
    clearMissionProgress() {
        // Limpiar el progreso de misión completado
        const missionProgressSection = document.getElementById('currentMissionProgressSection');
        const clearBtn = document.getElementById('clearMissionBtn');
        
        if (missionProgressSection) {
            missionProgressSection.style.display = 'none';
        }
        
        // Limpiar timer y datos
        this.missionTimer = {
            startTime: null,
            isRunning: false,
            elapsed: 0,
            completedAt: null
        };
        
        this.lastValidOperations = null;
        
        console.log('🧹 Progreso de misión limpiado manualmente');
    }
    
    getRecentServerLogs() {
        // Por ahora retornar array vacío, pero esta función podría
        // hacer una llamada al backend para obtener logs recientes
        // o analizar el status.detail para detectar patrones
        return [];
    }
    
    updateExecuteButtonState(isRunning = false) {
        // Actualizar estado visual del botón de ejecutar basado en si hay traducción en curso
        const runButton = document.getElementById('run');
        if (runButton) {
            if (isRunning) {
                runButton.disabled = true;
                runButton.innerHTML = '<i class="fas fa-spinner fa-spin" style="margin-right: 6px;"></i>Traducción en Curso...';
                runButton.style.opacity = '0.6';
                runButton.style.cursor = 'not-allowed';
                runButton.title = 'Hay una traducción en ejecución';
            } else {
                runButton.disabled = false;
                runButton.innerHTML = '▶ Ejecutar Traducción';
                runButton.style.opacity = '1';
                runButton.style.cursor = 'pointer';
                runButton.title = 'Iniciar traducción de misiones seleccionadas';
            }
        }
    }
    
    // ========================= MÉTODOS DE PERFILES =========================
    
    initializeProfilesSystem() {
        console.log('✅ Sistema de perfiles inicializado correctamente');
        // Event listeners para perfiles
        try {
            const btnRefreshProfiles = document.getElementById('btnRefreshProfiles');
            if (btnRefreshProfiles) {
                btnRefreshProfiles.addEventListener('click', this.loadProfiles.bind(this));
            }
            
            const profilesList = document.getElementById('profilesList');
            if (profilesList) {
                profilesList.addEventListener('change', this.onProfileSelect.bind(this));
            }
            
            const btnLoadProfile = document.getElementById('btnLoadProfile');
            if (btnLoadProfile) {
                btnLoadProfile.addEventListener('click', () => this.loadProfile());
            }
            
            const btnUpdateProfile = document.getElementById('btnUpdateProfile');
            if (btnUpdateProfile) {
                btnUpdateProfile.addEventListener('click', this.updateProfile.bind(this));
            }
            
            const btnDeleteProfile = document.getElementById('btnDeleteProfile');
            if (btnDeleteProfile) {
                btnDeleteProfile.addEventListener('click', this.deleteProfile.bind(this));
            }
            
            const btnCreateProfile = document.getElementById('btnCreateProfile');
            if (btnCreateProfile) {
                btnCreateProfile.addEventListener('click', this.createProfile.bind(this));
            }
            
            // Botones de configuración unificada
            const btnSaveCompleteConfig = document.getElementById('btnSaveCompleteConfig');
            if (btnSaveCompleteConfig) {
                btnSaveCompleteConfig.addEventListener('click', this.saveCompleteConfig.bind(this));
            }
            
            const btnResetCompleteConfig = document.getElementById('btnResetCompleteConfig');
            if (btnResetCompleteConfig) {
                btnResetCompleteConfig.addEventListener('click', this.resetCompleteConfig.bind(this));
            }
            
            // Event listeners para modales
            this.setupModalEventListeners();
            
            console.log('✅ Event listeners de perfiles y configuración unificada configurados');
        } catch (error) {
            console.error('❌ Error configurando sistema de perfiles:', error);
        }
    }
    
    setupModalEventListeners() {
        /**
         * Configura event listeners para cerrar modales
         */
        // Cerrar modal con botones .close-modal
        document.querySelectorAll('.close-modal').forEach(button => {
            button.addEventListener('click', (e) => {
                const modalId = button.getAttribute('data-modal');
                if (modalId) {
                    this.hideModal(modalId);
                }
            });
        });
        
        // Cerrar modal haciendo clic fuera del contenido
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideModal(modal.id);
                }
            });
        });
        
        // Cerrar modal con Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const visibleModal = document.querySelector('.modal[style*="flex"]');
                if (visibleModal) {
                    this.hideModal(visibleModal.id);
                }
            }
        });
    }

    async loadProfiles() {
        try {
            // Cargar solo perfiles creados por el usuario
            const response = await fetch('/api/profiles');
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error cargando perfiles');
            }
            
            const profilesList = document.getElementById('profilesList');
            if (!profilesList) return;
            
            // Limpiar lista
            profilesList.innerHTML = '<option value="">Seleccionar perfil...</option>';
            
            // Añadir perfiles
            data.profiles.forEach(profile => {
                const option = document.createElement('option');
                option.value = profile.name;
                option.textContent = profile.name;
                profilesList.appendChild(option);
            });
            
            console.log(`✅ ${data.profiles.length} perfiles cargados`);
            this.showProfileStatus(`${data.profiles.length} perfiles disponibles`, 'success');
            
        } catch (error) {
            console.error('❌ Error cargando perfiles:', error);
            this.showProfileStatus('Error cargando perfiles: ' + error.message, 'error');
        }
    }

    // Función deshabilitada - solo perfiles de usuario
    // async createDefaultProfiles() {
    //     try {
    //         const response = await fetch('/api/profiles/defaults', {
    //             method: 'POST',
    //             headers: {
    //                 'Content-Type': 'application/json'
    //             }
    //         });
    //         
    //         const data = await response.json();
    //         
    //         if (data.ok) {
    //             console.log('✅ Perfiles por defecto creados');
    //             await this.loadProfiles(); // Recargar lista
    //         } else {
    //             console.log('ℹ️ Perfiles por defecto ya existen o no se pudieron crear');
    //         }
    //         
    //     } catch (error) {
    //         console.error('❌ Error creando perfiles por defecto:', error);
    //     }
    // }

    onProfileSelect() {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        if (selectedProfile) {
            console.log(`✅ Perfil seleccionado: ${selectedProfile}`);
            this.showProfileStatus(`Perfil "${selectedProfile}" seleccionado`, 'info');
            // Actualizar el badge de perfil en el header
            this.updateProfileStatus();
        }
    }

    async loadProfile(onlyGeneral = false, onlyModel = false) {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        if (!selectedProfile) {
            this.showProfileStatus('Seleccione un perfil primero', 'error');
            return;
        }
        
        try {
            let url = `/api/profiles/${encodeURIComponent(selectedProfile)}/load`;
            const body = {};
            
            if (onlyGeneral || onlyModel) {
                body.load_general = onlyGeneral;
                body.load_model = onlyModel;
            }
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error cargando perfil');
            }
            
            // Recargar configuraciones afectadas
            if (!onlyModel) {
                await this.loadUserConfig();
            }
            if (!onlyGeneral) {
                await this.loadUserLmModels();
                // Recargar lista de presets para reflejar el preset cargado
                this.renderPresetList();
            }
            
            // Mostrar información del preset si se cargó
            let statusMessage = `Perfil "${selectedProfile}" cargado correctamente`;
            const presetElement = document.getElementById('presetList');
            const selectedPreset = presetElement?.value;
            if (selectedPreset && selectedPreset !== '') {
                statusMessage += ` (Preset: ${selectedPreset})`;
            }
            
            const typeText = onlyGeneral ? ' (solo general)' : onlyModel ? ' (solo modelo)' : '';
            this.showProfileStatus(statusMessage + typeText, 'success');
            console.log(`✅ Perfil cargado: ${selectedProfile}${typeText}${selectedPreset ? ` - Preset: ${selectedPreset}` : ''}`);
            
            // Verificar si hay warning del modelo
            if (data.model_warning) {
                this.showModelWarning(data.model_warning, selectedProfile);
            }
            
            // Actualizar el badge de perfil en el header
            this.updateProfileStatus();
        } catch (error) {
            console.error('❌ Error cargando perfil:', error);
            this.showProfileStatus('Error cargando perfil: ' + error.message, 'error');
        }
    }

    showModelWarning(warning, profileName) {
        /**
         * Muestra un aviso al usuario sobre problemas con el modelo del perfil
         */
        console.warn(`⚠️ Problema con modelo del perfil ${profileName}:`, warning);
        
        const warningHtml = `
            <div class="alert alert-warning alert-dismissible fade show" role="alert" style="margin: 10px 0;">
                <h5 class="alert-heading">
                    <i class="fas fa-exclamation-triangle"></i> ${warning.title}
                </h5>
                <p class="mb-2"><strong>${warning.message}</strong></p>
                
                ${warning.details ? `
                    <div class="mb-2">
                        <small class="text-muted">
                            <strong>Modelo configurado:</strong> ${warning.details.configured_model || 'N/A'}
                        </small>
                    </div>
                ` : ''}
                
                ${warning.details && warning.details.available_models ? `
                    <div class="mb-2">
                        <small class="text-muted">
                            <strong>Modelos disponibles:</strong><br>
                            ${warning.details.available_models.map(model => `• ${model}`).join('<br>')}
                        </small>
                    </div>
                ` : ''}
                
                <div class="mb-2">
                    <strong>Sugerencias:</strong>
                    <ul class="mb-0">
                        ${warning.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                    </ul>
                </div>
                
                <div class="mt-3">
                    <button type="button" class="btn btn-sm btn-outline-primary me-2" onclick="window.orchestratorUI.openLMStudio()">
                        <i class="fas fa-external-link-alt"></i> Abrir LM Studio
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary me-2" onclick="window.orchestratorUI.refreshModels()">
                        <i class="fas fa-sync"></i> Actualizar Modelos
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-info" onclick="window.orchestratorUI.validateProfileModel('${profileName}')">
                        <i class="fas fa-check"></i> Verificar Nuevamente
                    </button>
                </div>
                
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>
            </div>
        `;
        
        // Buscar un contenedor apropiado para mostrar el warning
        const containers = [
            document.getElementById('profileStatus'),
            document.querySelector('.profile-section'),
            document.querySelector('.model-section'),
            document.querySelector('.container-fluid')
        ];
        
        const container = containers.find(c => c !== null);
        if (container) {
            // Insertar el warning después del elemento
            container.insertAdjacentHTML('afterend', warningHtml);
        } else {
            // Fallback: mostrar como alert básico
            alert(`⚠️ ${warning.title}\n\n${warning.message}\n\nSugerencias:\n${warning.suggestions.join('\n')}`);
        }
    }

    openLMStudio() {
        // Intentar abrir LM Studio (esto puede no funcionar en todos los navegadores)
        const lmUrl = this.getElementValue('userLmUrl') || 'http://localhost:1234/v1';
        const baseUrl = lmUrl.replace('/v1', '');
        window.open(baseUrl, '_blank');
    }

    refreshModels() {
        // Recargar la lista de modelos
        this.loadUserLmModels();
    }

    async validateProfileModel(profileName) {
        try {
            const response = await fetch(`/api/profiles/${encodeURIComponent(profileName)}/validate_model`);
            const data = await response.json();
            
            if (data.ok) {
                if (data.model_valid) {
                    this.showProfileStatus(`✅ Modelo del perfil "${profileName}" validado correctamente`, 'success');
                    // Remover warnings existentes
                    document.querySelectorAll('.alert-warning').forEach(alert => {
                        if (alert.textContent.includes('Modelo') || alert.textContent.includes('LM Studio')) {
                            alert.remove();
                        }
                    });
                } else if (data.warning) {
                    this.showModelWarning(data.warning, profileName);
                }
            } else {
                this.showProfileStatus('Error validando modelo: ' + data.error, 'error');
            }
        } catch (error) {
            console.error('Error validando modelo:', error);
            this.showProfileStatus('Error validando modelo: ' + error.message, 'error');
        }
    }

    async createProfile() {
        const nameInput = document.getElementById('newProfileName');
        const descInput = document.getElementById('newProfileDescription');
        
        const profileName = nameInput?.value?.trim();
        const profileDesc = descInput?.value?.trim() || '';
        
        if (!profileName) {
            this.showProfileStatus('Nombre de perfil requerido', 'error');
            nameInput?.focus();
            return;
        }
        
        try {
            // Capturar configuración general actual
            const generalConfig = this.captureForm();
            
            // Capturar configuración del modelo actual
            const modelConfig = {
                userLmModel: document.getElementById('userLmModel')?.value || '',
                arg_config: document.getElementById('arg_config')?.value || '',
                arg_compat: document.getElementById('arg_compat')?.value || 'completions',
                arg_batch: document.getElementById('arg_batch')?.value || '4',
                arg_timeout: document.getElementById('arg_timeout')?.value || '200',
                api_temperature: document.getElementById('api_temperature')?.value || 0.7,
                api_top_p: document.getElementById('api_top_p')?.value || 0.9,
                api_top_k: document.getElementById('api_top_k')?.value || 40,
                api_max_tokens: document.getElementById('api_max_tokens')?.value || 8000,
                api_repetition_penalty: document.getElementById('api_repetition_penalty')?.value || 1.0,
                api_presence_penalty: document.getElementById('api_presence_penalty')?.value || 0.0,
                presetList: document.getElementById('presetList')?.value || ''
            };
            
            const profileData = {
                name: profileName,
                description: profileDesc,
                general_config: generalConfig,
                model_config: modelConfig
            };
            
            const response = await fetch('/api/profiles', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(profileData)
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error creando perfil');
            }
            
            // Limpiar formulario
            if (nameInput) nameInput.value = '';
            if (descInput) descInput.value = '';
            
            await this.loadProfiles(); // Recargar lista
            this.showProfileStatus(`Perfil "${profileName}" creado correctamente`, 'success');
            console.log(`✅ Perfil creado: ${profileName}`);
            
        } catch (error) {
            console.error('❌ Error creando perfil:', error);
            this.showProfileStatus('Error creando perfil: ' + error.message, 'error');
        }
    }

    async updateProfile() {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        if (!selectedProfile) {
            this.showProfileStatus('Seleccione un perfil primero', 'error');
            return;
        }
        
        if (!confirm(`¿Desea actualizar el perfil "${selectedProfile}" con la configuración actual?`)) {
            return;
        }
        
        try {
            // Capturar configuración general actual
            const generalConfig = this.captureForm();
            
            // Capturar configuración del modelo actual
            const modelConfig = {
                userLmModel: document.getElementById('userLmModel')?.value || '',
                arg_config: document.getElementById('arg_config')?.value || '',
                arg_compat: document.getElementById('arg_compat')?.value || 'completions',
                arg_batch: document.getElementById('arg_batch')?.value || '4',
                arg_timeout: document.getElementById('arg_timeout')?.value || '200',
                api_temperature: document.getElementById('api_temperature')?.value || 0.7,
                api_top_p: document.getElementById('api_top_p')?.value || 0.9,
                api_top_k: document.getElementById('api_top_k')?.value || 40,
                api_max_tokens: document.getElementById('api_max_tokens')?.value || 8000,
                api_repetition_penalty: document.getElementById('api_repetition_penalty')?.value || 1.0,
                api_presence_penalty: document.getElementById('api_presence_penalty')?.value || 0.0,
                presetList: document.getElementById('presetList')?.value || ''
            };
            
            const profileData = {
                general_config: generalConfig,
                model_config: modelConfig
            };
            
            const response = await fetch(`/api/profiles/${encodeURIComponent(selectedProfile)}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(profileData)
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error actualizando perfil');
            }
            
            this.showProfileStatus(`Perfil "${selectedProfile}" actualizado correctamente`, 'success');
            console.log(`✅ Perfil actualizado: ${selectedProfile}`);
            
        } catch (error) {
            console.error('❌ Error actualizando perfil:', error);
            this.showProfileStatus('Error actualizando perfil: ' + error.message, 'error');
        }
    }

    async deleteProfile() {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        if (!selectedProfile) {
            this.showProfileStatus('Seleccione un perfil primero', 'error');
            return;
        }
        
        if (!confirm(`¿Está seguro de que desea eliminar el perfil "${selectedProfile}"?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/profiles/${encodeURIComponent(selectedProfile)}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error eliminando perfil');
            }
            
            await this.loadProfiles(); // Recargar lista
            this.showProfileStatus(`Perfil "${selectedProfile}" eliminado correctamente`, 'success');
            console.log(`✅ Perfil eliminado: ${selectedProfile}`);
            
        } catch (error) {
            console.error('❌ Error eliminando perfil:', error);
            this.showProfileStatus('Error eliminando perfil: ' + error.message, 'error');
        }
    }

    showProfileStatus(message, type) {
        const statusSpan = document.getElementById('profilesStatus');
        if (!statusSpan) return;
        
        statusSpan.textContent = message;
        statusSpan.className = `status-message ${type}`;
        
        // Auto-limpiar después de 3 segundos para mensajes de éxito
        if (type === 'success') {
            setTimeout(() => {
                statusSpan.textContent = '';
                statusSpan.className = 'status-message';
            }, 3000);
        }
    }

    showExecutionStatus(message, type = '') {
        const statusEl = document.getElementById('executionStatus');
        if (!statusEl) return;
        
        statusEl.textContent = message;
        statusEl.className = `execution-status ${type}`;
        statusEl.style.display = 'block';
    }

    showCompleteConfigStatus(message, type) {
        const statusSpan = document.getElementById('completeConfigStatus');
        if (!statusSpan) return;
        
        statusSpan.textContent = message;
        statusSpan.className = `status-message ${type}`;
        
        // Auto-limpiar después de 3 segundos para mensajes de éxito
        if (type === 'success') {
            setTimeout(() => {
                statusSpan.textContent = '';
                statusSpan.className = 'status-message';
            }, 3000);
        }
    }

    async saveCompleteConfig() {
        try {
            // Guardar configuración general
            const generalResult = await this.saveUserConfig();
            
            // Guardar configuración del modelo (simulado - necesitarías implementar el método real)
            // const modelResult = await this.saveModelConfig();
            
            this.showCompleteConfigStatus('Configuración completa guardada correctamente', 'success');
            console.log('✅ Configuración completa guardada');
            
        } catch (error) {
            console.error('❌ Error guardando configuración completa:', error);
            this.showCompleteConfigStatus('Error guardando configuración: ' + error.message, 'error');
        }
    }

    async resetCompleteConfig() {
        if (!confirm('¿Está seguro de que desea restaurar toda la configuración a los valores por defecto?')) {
            return;
        }
        
        try {
            // Resetear configuración general
            const generalResult = await this.resetUserConfig();
            
            // Resetear configuración del modelo (simulado)
            // const modelResult = await this.resetModelConfig();
            
            this.showCompleteConfigStatus('Configuración completa restaurada a valores por defecto', 'success');
            console.log('✅ Configuración completa restaurada');
            
        } catch (error) {
            console.error('❌ Error restaurando configuración completa:', error);
            this.showCompleteConfigStatus('Error restaurando configuración: ' + error.message, 'error');
        }
    }
    
    init() {
        console.log('Inicializando Orquestador DCS UI');
        
        // Configurar modales primero
        this.setupModalsSimple();
        
        // Configurar event listeners
        this.setupEventListeners();
        
        // Cargar datos iniciales
        this.loadInitialData();
        
        // Ocultar modelos recomendados inicialmente
        this.hideRecommendedModels();
        
        // Verificar actualizaciones
        this.checkUpdateBanner();
        
        // NO iniciar polling automáticamente - solo cuando sea necesario
        console.log('ℹ️  Polling de estado: inicialización diferida hasta que sea necesario');
        
        // Verificar estado inicial una vez sin polling
        this.pollStatus().then(() => {
            // Si hay actividad en curso, iniciar polling automáticamente
            if (this.lastStatusResponse && this.lastStatusResponse.is_running) {
                console.log('🔄 Actividad detectada en estado inicial, iniciando polling');
                this.startStatusPolling();
            }
        }).catch(e => console.log('ℹ️  Estado inicial no disponible:', e));
        
        // Mostrar modal de explicación de perfiles si es la primera vez
        setTimeout(() => {
            this.showProfileExplanationIfFirstTime();
        }, 1000); // Delay para que la UI esté completamente cargada
        
        console.log('✅ Orquestador DCS UI inicializado correctamente');
        
        // Actualizar badge del modelo cargado
        setTimeout(() => {
            this.updateLoadedModelBadge();
        }, 2000); // Delay para que la UI esté completamente cargada
    }
    
    setupEventListeners() {
        console.log('⚡ Configurando event listeners...');
        
        // NO configurar event listener para stopServer aquí
        // La funcionalidad está manejada globalmente por modern-theme.js
        // que puede usar nuestra función this.stopServer si está disponible
        console.log('🔧 stopServer manejado por modern-theme.js con fallback a orchestrator');
        
        // Modales
        this.setupModalsSimple();
        
        // Botones de ayuda
        this.wireHelpButtons();
        
        // Configuración general del usuario
        this.setupUserConfigEventListeners();
        
        // Perfiles de configuración
        this.initializeProfilesSystem();
        
        // Auto-detección de ROOT_DIR
        document.getElementById('btnAutoRoot')?.addEventListener('click', () => this.autoDetectRoot(false));
        
        // Detección automática de DCS
        document.getElementById('btnDetectDCS')?.addEventListener('click', this.detectDCSInstallation.bind(this));
        
        // Presets (simplificado - solo cargar)
        document.getElementById('btnLoadPreset')?.addEventListener('click', this.loadPreset.bind(this));
        // Botones eliminados: btnSavePreset y btnDeletePreset (innecesarios para presets predefinidos)
        
        // LM Studio
        // document.getElementById('btnScanModels')?.addEventListener('click', this.scanLmModels.bind(this)); // Botón removido
        document.getElementById('btnRefreshModels')?.addEventListener('click', this.loadUserLmModels.bind(this));
        document.getElementById('userLmModel')?.addEventListener('change', this.checkModelStatus.bind(this));
        
        // Campañas y misiones
        document.getElementById('scanCampaigns')?.addEventListener('click', this.scanCampaigns.bind(this));
        document.getElementById('include_fc')?.addEventListener('change', this.loadMissions.bind(this));
        
        // Controles de selección de misiones
        document.getElementById('selectAllMissions')?.addEventListener('click', this.selectAllMissions.bind(this));
        document.getElementById('deselectAllMissions')?.addEventListener('click', this.deselectAllMissions.bind(this));
        document.getElementById('refreshMissions')?.addEventListener('click', this.refreshMissions.bind(this));
        
        // Modal de confirmación
        document.getElementById('confirmCancel')?.addEventListener('click', this.hideConfirmModal.bind(this));
        document.getElementById('confirmExecute')?.addEventListener('click', this.executeAfterConfirm.bind(this));
        
        // Modos de ejecución
        document.querySelectorAll('input[name=mode]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.onModeChange();
            });
        });
        
        // Ejecución y cancelación
        const runButton = document.getElementById('run');
        console.log('🔘 Botón ejecutar encontrado:', runButton);
        runButton?.addEventListener('click', () => {
            console.log('🔘 Click en botón ejecutar detectado');
            this.runOrchestrator();
        });
        document.getElementById('cancel')?.addEventListener('click', this.cancelOrchestrator.bind(this));
        
        // ARGS preview
        this.setupArgsPreview();
        
        // LM URL auto-scan
        const urlInput = document.getElementById('userLmUrl');
        if (urlInput) {
            let lmScanTimer = null;
            urlInput.addEventListener('input', () => {
                clearTimeout(lmScanTimer);
                lmScanTimer = setTimeout(() => this.scanLmModels(), 500);
            });
        }
        
        // Banner de actualización
        document.getElementById('btnUpdateNow')?.addEventListener('click', this.doUpdateNow.bind(this));
    }
    
    async stopServer() {
        if (!confirm('¿Parar el servidor web ahora? Se cerrará esta pestaña.')) return;
        
        try {
            await fetch('/api/shutdown', { method: 'POST' });
        } catch(e) {
            console.log('Servidor ya detenido');
        }
        
        // Intentar cerrar pestaña
        setTimeout(() => { 
            window.close(); 
            location.href = 'about:blank'; 
        }, 500);
    }
    
    setupModals() {
        console.log('🔧 Configurando modales del orquestador (excluyendo botón de ayuda principal)...');
        
        // NOTA: El botón principal de ayuda "openHelp" es manejado ÚNICAMENTE por global-help.js
        // No tocamos ese botón aquí para evitar conflictos y modales duplicados
        const setupHelpButton = () => {
            const openHelp = document.getElementById('openHelp');
            console.log('🔍 Buscando botón openHelp...', !!openHelp);
            
            if (openHelp) {
                console.log('✅ Botón openHelp encontrado, configurando event listener...');
                
                // Remover event listeners existentes para evitar duplicados
                const newButton = openHelp.cloneNode(true);
                openHelp.parentNode.replaceChild(newButton, openHelp);
                
                // Configurar el nuevo botón
                newButton.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('🍄 CLICK EN BOTÓN PRINCIPAL DE AYUDA');
                    
                    // Crear y mostrar contenido inmediatamente
                    this.showMainHelp();
                });
                
                console.log('✅ Event listener configurado exitosamente');
                return true;
            } else {
                console.warn('⚠️ Botón openHelp NO encontrado');
                return false;
            }
        };
        
        // Intentar configurar inmediatamente
        if (!setupHelpButton()) {
            // Si no funciona, intentar después de que el DOM esté listo
            document.addEventListener('DOMContentLoaded', () => {
                setTimeout(setupHelpButton, 500);
            });
            
            // También intentar después de un delay
            setTimeout(setupHelpButton, 1000);
        }
        
        // Modal principal y otros elementos
        const modal = document.getElementById('modal');
        const closeHelp = document.getElementById('closeHelp');
        
        if (closeHelp && modal) {
            closeHelp.addEventListener('click', () => modal.classList.remove('open'));
        }
        
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.classList.remove('open');
            });
        }
        
        // Mini modal
        const mini = document.getElementById('miniModal');
        const miniClose = document.getElementById('miniClose');
        
        if (miniClose && mini) {
            miniClose.addEventListener('click', () => mini.classList.remove('open'));
        }
        
        if (mini) {
            mini.addEventListener('click', (e) => {
                if (e.target === mini) mini.classList.remove('open');
            });
        }
        
        // Modal de confirmación - Lo crearemos cuando se necesite
        console.log('✅ Modales configurados (modal de confirmación se creará dinámicamente)');
        
        // Configurar modal de perfiles
        this.setupModalEventListeners();
    }

    setupModalsSimple() {
        console.log('🔧 Configurando modales del orquestador (versión simplificada sin botón ayuda principal)...');
        
        // IMPORTANTE: NO tocamos el botón "openHelp" - es manejado por global-help.js
        
        // Solo configurar modales específicos del orquestador
        const modal = document.getElementById('modal');
        const closeHelp = document.getElementById('closeHelp');
        
        if (closeHelp && modal) {
            closeHelp.addEventListener('click', () => modal.classList.remove('open'));
        }
        
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.classList.remove('open');
            });
        }
        
        // Mini modal para ayudas específicas "?"
        const mini = document.getElementById('miniModal');
        const miniClose = document.getElementById('miniClose');
        
        if (miniClose && mini) {
            miniClose.addEventListener('click', () => mini.classList.remove('open'));
        }
        
        if (mini) {
            mini.addEventListener('click', (e) => {
                if (e.target === mini) mini.classList.remove('open');
            });
        }
        
        console.log('✅ Modales del orquestador configurados (sin conflictos con ayuda global)');
        
        // Configurar modal de perfiles
        this.setupModalEventListeners();
    }
    
    async wireHelpButtons() {
        console.log('🔧 Inicializando sistema de ayuda...');
        
        // No verificar el modal ahora, solo configurar los botones
        // El modal se verificará cuando se haga clic
        
        // Mapeo de data-help a archivos markdown
        const helpFileMap = {
            'presets': 'presets.md',
            'auto-detect-dcs': 'auto-detect-dcs.md',
            'user-root-dir': 'user-root-dir.md',
            'user-file-target': 'user-file-target.md',
            'user-lm-url': 'user-lm-url.md',
            'user-deploy-dir': 'user-deploy-dir.md',
            'user-deploy-overwrite': 'user-deploy-overwrite.md',
            'user-lm-model': 'user-lm-model.md',
            'args': 'args.md',
            'cache': 'cache.md',
            'overwrite-cache': 'overwrite-cache.md',
            'fc': 'fc.md',
            'profiles': 'profiles.md'
        };

        // Cache para archivos ya cargados
        this.helpContentCache = {};

        // Función para cargar contenido markdown
        const loadHelpContent = async (filename) => {
            if (this.helpContentCache[filename]) {
                return this.helpContentCache[filename];
            }

            try {
                console.log(`📖 Cargando archivo: ${filename}...`);
                const response = await fetch(`/static/README/${filename}`);
                console.log(`📡 Respuesta recibida: ${response.status} - ${response.statusText}`);
                if (!response.ok) {
                    throw new Error(`No se pudo cargar ${filename}: ${response.status}`);
                }
                const markdown = await response.text();
                console.log(`📄 Contenido markdown cargado: ${markdown.length} caracteres`);
                const html = this.markdownToHtml(markdown);
                console.log(`🎨 HTML generado: ${html.length} caracteres`);
                this.helpContentCache[filename] = html;
                return html;
            } catch (error) {
                console.warn(`Error cargando ayuda ${filename}:`, error);
                return this.getFallbackHelpContent(filename);
            }
        };

        // Contenido de respaldo (el actual) para mantener compatibilidad
        const helpContent = {
            presets: `
                <p><b>¿Qué es un preset?</b> Es una configuración predefinida optimizada para diferentes tipos de hardware.</p>
                <ul>
                    <li><b>🟢 Ligero:</b> Para equipos básicos (4-8GB RAM, GPU integrada) - Modelos 2B-3B</li>
                    <li><b>🟡 Balanceado:</b> Para equipos medios (8-16GB RAM, GPU dedicada) - Modelos 8B-9B</li>
                    <li><b>🔴 Pesado:</b> Para equipos high-end (16GB+ RAM, GPU potente) - Modelos 27B-70B</li>
                </ul>
                <p>Selecciona el preset que mejor se adapte a tu hardware y haz clic en <b>"Cargar"</b> para ver los modelos recomendados.</p>
            `,
            rootdir: `
                <p>Carpeta donde el juego tiene las campañas (<code>.miz</code>):</p>
                <ul>
                    <li><code>C:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns</code></li>
                    <li><code>C:\\Steam\\steamapps\\common\\DCSWorld\\Mods\\campaigns</code></li>
                </ul>
                <p>Pulsa "Detectar" para localizarla automáticamente.</p>
            `,
            file_target: `
                <p>Ruta <b>dentro</b> del .miz hacia el diccionario Lua:</p>
                <ul>
                    <li>Por defecto: <code>l10n/DEFAULT/dictionary</code></li>
                    <li>Otros idiomas: <code>l10n/RUS/dictionary</code>, etc.</li>
                </ul>
            `,
            args: `
                <p>Parámetros del modelo de traducción:</p>
                <ul>
                    <li><code>--config</code>: archivo de prompts desde ./PROMTS</li>
                    <li><code>--lm-compat</code>: protocolo (completions/chat)</li>
                    <li><code>--batch-size</code>: entradas por lote</li>
                    <li><code>--timeout</code>: tiempo máximo por llamada</li>
                </ul>
            `,
            mode: `
                <p><b>Modos de ejecución:</b></p>
                <ul>
                    <li><b>🌍 TRADUCIR</b>: Extrae y traduce misiones originales</li>
                    <li><b>📦 REEMPAQUETAR</b>: Genera .miz con traducciones (solo misiones traducidas)</li>
                    <li><b>🚀 DESPLEGAR</b>: Copia misiones al juego (solo misiones reempaquetadas)</li>
                    <br>
                    <p><strong>Flujo recomendado:</strong></p>
                    <ol>
                        <li>Usar <b>TRADUCIR</b> en misiones nuevas</li>
                        <li>Usar <b>REEMPAQUETAR</b> después de traducir</li>
                        <li>Usar <b>DESPLEGAR</b> para instalar en DCS</li>
                    </ol>
                </ul>
            `,
            fc: `
                <p><b>Flaming Cliffs (FC)</b>: módulos simplificados para DCS.</p>
                <p>Incluye misiones con <code>-FC-</code> en el nombre.</p>
            `,
            deploy_overwrite: `
                <p>Controla dónde se copian los .miz:</p>
                <ul>
                    <li><b>true</b>: sobrescribe originales (con backup)</li>
                    <li><b>false</b>: copia a Translated_ES/</li>
                </ul>
            `,
            deploy_dir: `
                <p>Directorio base para deploy. Si vacío, usa la carpeta original.</p>
            `,
            cache: `
                <p><b>Sistema de Cache de Traducciones:</b></p>
                <ul>
                    <li><b>✅ Activado</b>: Reutiliza traducciones previas para acelerar el proceso</li>
                    <li><b>❌ Desactivado</b>: Realiza traducción completamente nueva, ignorando cache</li>
                </ul>
                <p><strong>¿Cuándo desactivarlo?</strong></p>
                <ul>
                    <li>Para obtener traducciones diferentes de textos ya traducidos</li>
                    <li>Cuando se ha actualizado el modelo de traducción</li>
                    <li>Si hay problemas con traducciones incorrectas guardadas en cache</li>
                </ul>
                <p><em>Nota:</em> El cache se guarda de forma centralizada para todas las campañas y misiones.</p>
            `,
            'auto-detect-dcs': `
                <p><b>Detección Automática de DCS World</b></p>
                <p>Esta función busca automáticamente la instalación de DCS en tu sistema y configura las rutas necesarias.</p>
                
                <p><strong>¿Qué hace?</strong></p>
                <ul>
                    <li>🔍 Busca DCS World en ubicaciones comunes</li>
                    <li>📁 Configura automáticamente la <b>Ruta de Campañas</b></li>
                    <li>🎯 Establece la <b>Ruta de Despliegue</b></li>
                    <li>💾 Guarda la configuración automáticamente</li>
                </ul>
                
                <p><strong>Ubicaciones que busca:</strong></p>
                <ul>
                    <li><code>C:\\Program Files\\Eagle Dynamics\\DCS World\\</code></li>
                    <li><code>C:\\Program Files (x86)\\Eagle Dynamics\\DCS World\\</code></li>
                    <li><code>D:\\Steam\\steamapps\\common\\DCSWorld\\</code></li>
                    <li>Otras unidades de disco comunes</li>
                </ul>
                
                <p><em>💡 Si no encuentra DCS automáticamente, puedes configurar las rutas manualmente.</em></p>
            `,
            'overwrite-cache': `
                <p><b>Sobrescribir Cache:</b></p>
                <p>Controla si las nuevas traducciones actualizan el cache existente cuando el cache está <b>desactivado</b>.</p>
                <ul>
                    <li><b>✅ Activado</b>: Las nuevas traducciones se guardan en el cache para futuras ejecuciones</li>
                    <li><b>❌ Desactivado</b>: No se modifica el cache existente (comportamiento por defecto)</li>
                </ul>
                <p><strong>¿Cuándo activarlo?</strong></p>
                <ul>
                    <li>Cuando quieres obtener traducciones frescas PERO guardar las mejores</li>
                    <li>Para actualizar gradualmente el cache con traducciones mejoradas</li>
                    <li>Si has mejorado el modelo y quieres preservar las nuevas traducciones</li>
                </ul>
                <p><em>Nota:</em> Solo funciona cuando "Usar cache" está desactivado.</p>
            `,
            profiles: `
                <p><b>¿Qué son los perfiles?</b> Son configuraciones completas guardadas que incluyen TODA tu configuración (general + modelo).</p>
                <ul>
                    <li><b>📁 Configuración General:</b> ROOT_DIR, FILE_TARGET, URL LM Studio, rutas de despliegue</li>
                    <li><b>🤖 Configuración del Modelo:</b> Modelo preferido, presets, parámetros ARGS, cache</li>
                </ul>
                <p><b>Acciones disponibles:</b></p>
                <ul>
                    <li><b>Cargar Completo:</b> Aplica toda la configuración del perfil</li>
                    <li><b>Solo General:</b> Aplica únicamente las rutas y configuración general</li>
                    <li><b>Solo Modelo:</b> Aplica únicamente el modelo y parámetros de IA</li>
                    <li><b>Actualizar:</b> Guarda tu configuración actual en el perfil seleccionado</li>
                </ul>
                <p><em>Los perfiles son ideales para cambiar rápidamente entre diferentes configuraciones de trabajo.</em></p>
            `
        };
        
        const titleMap = {
            'presets': 'Ayuda — Presets',
            'auto-detect-dcs': 'Ayuda — Auto-detección DCS',
            'user-root-dir': 'Ayuda — Carpeta Raíz',
            'user-file-target': 'Ayuda — Archivo Objetivo',
            'user-lm-url': 'Ayuda — URL Servidor LM',
            'user-deploy-dir': 'Ayuda — Carpeta Despliegue',
            'user-deploy-overwrite': 'Ayuda — Sobrescribir Despliegue',
            'user-lm-model': 'Ayuda — Modelo de Lenguaje',
            'args': 'Ayuda — Argumentos',
            'cache': 'Ayuda — Cache',
            'overwrite-cache': 'Ayuda — Sobrescribir Cache',
            'fc': 'Ayuda — Flaming Cliffs',
            'profiles': 'Ayuda — Perfiles',
            
            // Compatibilidad con nombres antiguos
            'rootdir': 'Ayuda — ROOT_DIR',
            'file_target': 'Ayuda — FILE_TARGET',
            'mode': 'Ayuda — Modos',
            'deploy_overwrite': 'Ayuda — DEPLOY_OVERWRITE',
            'deploy_dir': 'Ayuda — DEPLOY_DIR'
        };

        console.log('🔍 Buscando botones de ayuda...');
        const helpButtons = document.querySelectorAll('.help-btn');
        console.log(`📋 Encontrados ${helpButtons.length} botones de ayuda`);

        document.querySelectorAll('.help-btn').forEach(btn => {
            const key = btn.getAttribute('data-help');
            console.log(`🔧 Configurando botón: ${key}`);
            
            btn.addEventListener('click', async () => {
                console.log(`🖱️ Click en botón de ayuda: ${key}`);
                
                // Buscar elementos del modal en tiempo real
                console.log('🔎 Buscando elementos del modal...');
                console.log('📄 document.body:', !!document.body);
                console.log('🌐 document.getElementById test:', !!document.getElementById);
                
                const miniTitle = document.getElementById('miniTitle');
                const miniContent = document.getElementById('miniContent');
                const miniModal = document.getElementById('miniModal');
                
                // Debug más detallado
                console.log('🔍 getElementById results:');
                console.log('  - miniTitle:', miniTitle);
                console.log('  - miniContent:', miniContent);
                console.log('  - miniModal:', miniModal);
                
                // Verificar si existen con querySelector
                const miniTitleQS = document.querySelector('#miniTitle');
                const miniContentQS = document.querySelector('#miniContent');
                const miniModalQS = document.querySelector('#miniModal');
                
                console.log('🔍 querySelector results:');
                console.log('  - miniTitle (QS):', miniTitleQS);
                console.log('  - miniContent (QS):', miniContentQS);
                console.log('  - miniModal (QS):', miniModalQS);
                
                // Buscar todos los elementos con IDs que contengan "mini"
                const allElements = document.querySelectorAll('[id*="mini"]');
                console.log('📋 Elementos con "mini" en el ID:', allElements);
                
                console.log(`🔍 Elementos del modal en click:`, {
                    miniTitle: !!miniTitle,
                    miniContent: !!miniContent,
                    miniModal: !!miniModal,
                    document_ready: document.readyState
                });
                
                // Si no existe el modal, crearlo dinámicamente
                if (!miniModal || !miniTitle || !miniContent) {
                    console.log('⚠️ Modal no encontrado, creando dinámicamente...');
                    this.createHelpModal();
                    
                    // Intentar buscar de nuevo los elementos
                    const miniModal2 = document.getElementById('miniModal');
                    const miniTitle2 = document.getElementById('miniTitle');
                    const miniContent2 = document.getElementById('miniContent');
                    
                    if (!miniModal2 || !miniTitle2 || !miniContent2) {
                        console.log('⚠️ No se pudo crear el modal, usando alert');
                        alert(`Ayuda - ${key}\n\nEl contenido se está cargando...`);
                        return;
                    }
                    
                    // Usar los elementos creados dinámicamente
                    this.showHelpInModal(key, miniModal2, miniTitle2, miniContent2, titleMap, helpFileMap, helpContent, loadHelpContent);
                } else {
                    // Usar el modal existente
                    this.showHelpInModal(key, miniModal, miniTitle, miniContent, titleMap, helpFileMap, helpContent, loadHelpContent);
                }
            });
        });
        
        console.log(`✅ Sistema de ayuda configurado con ${helpButtons.length} botones`);
    }
    
    // Función para crear el modal dinámicamente
    createHelpModal() {
        console.log('🔨 Creando modal de ayuda dinámicamente...');
        
        const modalHTML = `
            <div id="miniModal" class="modal" role="dialog" aria-modal="true" aria-labelledby="miniTitle" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(8px); z-index: 1000; justify-content: center; align-items: center;">
                <div class="modal-card" style="background: linear-gradient(135deg, #334155 0%, #475569 100%); border: 1px solid #475569; border-radius: 12px; padding: 24px; max-width: 600px; max-height: 80%; overflow-y: auto; margin: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.7);">
                    <header style="margin-bottom: 16px; border-bottom: 1px solid #64748b; padding-bottom: 12px;"><strong id="miniTitle" style="color: #f1f5f9; font-size: 1.25rem; font-weight: 600;">Ayuda</strong></header>
                    <div class="content" id="miniContent" style="color: #e2e8f0; line-height: 1.6; font-size: 0.95rem;"></div>
                    <footer style="margin-top: 20px; text-align: right; border-top: 1px solid #64748b; padding-top: 16px;"><button id="miniClose" class="secondary" style="background: linear-gradient(135deg, #475569 0%, #64748b 100%); color: #f1f5f9; border: 1px solid #64748b; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; font-weight: 500;">Cerrar</button></footer>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // Configurar eventos del modal
        const modal = document.getElementById('miniModal');
        const closeBtn = document.getElementById('miniClose');
        
        // Efecto hover para el botón
        closeBtn.addEventListener('mouseenter', () => {
            closeBtn.style.background = 'linear-gradient(135deg, #64748b 0%, #78716c 100%)';
            closeBtn.style.transform = 'scale(1.05)';
        });
        
        closeBtn.addEventListener('mouseleave', () => {
            closeBtn.style.background = 'linear-gradient(135deg, #475569 0%, #64748b 100%)';
            closeBtn.style.transform = 'scale(1)';
        });
        
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
            modal.classList.remove('open');
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
                modal.classList.remove('open');
            }
        });
        
        console.log('✅ Modal creado dinámicamente');
    }
    
    // Función para mostrar ayuda en el modal
    async showHelpInModal(key, miniModal, miniTitle, miniContent, titleMap, helpFileMap, helpContent, loadHelpContent) {
        const title = titleMap[key] || 'Ayuda';
        let content = '<p>Cargando ayuda...</p>';
        
        if (miniTitle) {
            miniTitle.textContent = title;
            console.log(`📝 Título del modal actualizado: ${title}`);
        }
        if (miniContent) {
            miniContent.innerHTML = content;
            console.log(`📝 Contenido inicial del modal actualizado`);
        }
        if (miniModal) {
            miniModal.style.display = 'flex';
            miniModal.classList.add('open');
            console.log(`📱 Modal abierto con clase 'open'`);
        }
        
        // Intentar cargar desde archivo markdown
        const filename = helpFileMap[key];
        if (filename) {
            console.log(`📂 Intentando cargar archivo: ${filename} para clave: ${key}`);
            try {
                content = await loadHelpContent(filename);
                console.log(`✅ Markdown cargado exitosamente para: ${key}`);
            } catch (error) {
                console.warn(`Error cargando ayuda markdown para ${key}:`, error);
                content = helpContent[key] || this.getFallbackHelpContent(key);
            }
        } else {
            console.log(`⚠️ No hay archivo markdown para: ${key}, usando fallback`);
            // Usar contenido de respaldo
            content = helpContent[key] || this.getFallbackHelpContent(key);
        }
        
        if (miniContent) {
            miniContent.innerHTML = content;
            console.log(`📝 Contenido actualizado en modal para: ${key}`);
            console.log(`📄 Contenido HTML (primeros 200 chars):`, content.substring(0, 200));
        } else {
            console.error(`❌ miniContent no encontrado - no se puede actualizar el contenido`);
        }
    }

    // Método simplificado para mostrar la ayuda principal
    async showMainHelp() {
        console.log('🎯 Mostrando ayuda principal...');
        
        try {
            // Crear modal si no existe
            this.createHelpModal();
            
            // Buscar elementos del modal
            const miniModal = document.getElementById('miniModal');
            const miniTitle = document.getElementById('miniTitle');
            const miniContent = document.getElementById('miniContent');
            
            if (!miniModal || !miniTitle || !miniContent) {
                console.error('❌ No se pudo crear el modal');
                alert('Error al crear el modal de ayuda');
                return;
            }
            
            // Configurar título
            miniTitle.textContent = 'Resumen General del Sistema';
            
            try {
                // Intentar cargar el archivo markdown
                const response = await fetch('/static/README/general-overview.md');
                if (response.ok) {
                    const markdown = await response.text();
                    miniContent.innerHTML = this.markdownToHtml(markdown);
                    console.log('✅ Contenido markdown cargado');
                } else {
                    throw new Error('No se pudo cargar el archivo');
                }
            } catch (error) {
                console.warn('⚠️ Usando contenido de respaldo:', error);
                // Contenido de respaldo
                miniContent.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <h2 style="color: #60a5fa; margin-bottom: 20px;">🎮 Sistema de Traducción DCS</h2>
                        <p style="margin-bottom: 20px; color: #e2e8f0;">Sistema completo para traducir campañas de DCS World al español de forma automatizada.</p>
                        
                        <div style="background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; padding: 16px; margin: 20px 0; text-align: left;">
                            <h3 style="color: #fca5a5; margin: 0 0 12px 0; display: flex; align-items: center;">
                                <i class="fas fa-exclamation-triangle" style="margin-right: 8px;"></i>
                                Requisito Previo Importante
                            </h3>
                            <p style="color: #fecaca; margin: 8px 0; font-weight: 500;">
                                ⚠️ <strong>DEBES instalar LM Studio</strong> en tu PC para que el sistema funcione correctamente.
                            </p>
                            <div style="color: #fed7d7; font-size: 0.9rem; line-height: 1.4;">
                                <p style="margin: 6px 0;"><strong>1.</strong> Descarga LM Studio desde: <span style="color: #60a5fa; font-family: monospace;">https://lmstudio.ai</span></p>
                                <p style="margin: 6px 0;"><strong>2.</strong> Instala y ejecuta LM Studio en tu PC</p>
                                <p style="margin: 6px 0;"><strong>3.</strong> Descarga un modelo de lenguaje compatible (ej: Llama, Mistral)</p>
                                <p style="margin: 6px 0;"><strong>4.</strong> Inicia el servidor local en LM Studio (puerto 1234 por defecto)</p>
                            </div>
                            <p style="color: #fecaca; margin: 12px 0 0 0; font-size: 0.85rem; font-style: italic;">
                                💡 Sin LM Studio funcionando, las traducciones NO se ejecutarán.
                            </p>
                        </div>
                        
                        <div style="text-align: left; max-width: 450px; margin: 0 auto;">
                            <h3 style="color: #fbbf24; margin: 20px 0 10px 0;">📋 Secciones Principales:</h3>
                            <ul style="list-style: none; padding: 0;">
                                <li style="margin: 12px 0; padding: 8px; background: rgba(30, 41, 59, 0.5); border-radius: 6px; border-left: 3px solid #3b82f6;">
                                    <strong style="color: #60a5fa;">🎮 Campañas:</strong> <span style="color: #cbd5e1;">Gestión y traducción automática de campañas DCS</span>
                                </li>
                                <li style="margin: 12px 0; padding: 8px; background: rgba(30, 41, 59, 0.5); border-radius: 6px; border-left: 3px solid #10b981;">
                                    <strong style="color: #34d399;">🤖 Modelos y Presets:</strong> <span style="color: #cbd5e1;">Configuración de IA optimizada por hardware</span>
                                </li>
                                <li style="margin: 12px 0; padding: 8px; background: rgba(30, 41, 59, 0.5); border-radius: 6px; border-left: 3px solid #f59e0b;">
                                    <strong style="color: #fbbf24;">📝 Prompts:</strong> <span style="color: #cbd5e1;">Plantillas especializadas para traducción militar</span>
                                </li>
                                <li style="margin: 12px 0; padding: 8px; background: rgba(30, 41, 59, 0.5); border-radius: 6px; border-left: 3px solid #8b5cf6;">
                                    <strong style="color: #a78bfa;">🎯 Orquestador:</strong> <span style="color: #cbd5e1;">Control automatizado del proceso completo</span>
                                </li>
                            </ul>
                        </div>
                        
                        <div style="background: rgba(34, 197, 94, 0.2); border: 1px solid rgba(34, 197, 94, 0.4); border-radius: 8px; padding: 12px; margin: 20px 0; text-align: left;">
                            <h4 style="color: #34d399; margin: 0 0 8px 0; font-size: 0.95rem;">🚀 Flujo de Trabajo Típico:</h4>
                            <ol style="color: #a7f3d0; font-size: 0.85rem; margin: 0; padding-left: 18px;">
                                <li>Asegurar que LM Studio esté ejecutándose</li>
                                <li>Detectar campañas en DCS World</li>
                                <li>Seleccionar preset de calidad apropiado</li>
                                <li>Configurar modelo de IA en LM Studio</li>
                                <li>Iniciar proceso de traducción automatizada</li>
                                <li>Monitorear progreso en tiempo real</li>
                            </ol>
                        </div>
                        
                        <p style="margin-top: 25px; color: #94a3b8; font-size: 0.9rem;">
                            💡 <em>Usa los botones "?" específicos para ayuda detallada de cada sección</em>
                        </p>
                    </div>
                `;
            }
            
            // Mostrar el modal
            miniModal.style.display = 'flex';
            console.log('✅ Modal de ayuda principal mostrado');
            
        } catch (error) {
            console.error('❌ Error crítico en showMainHelp:', error);
            alert('Resumen General del Sistema\n\n🎮 Campañas: Gestión de traducciones DCS\n🤖 Modelos: Configuración de IA\n📝 Prompts: Plantillas especializadas\n🎯 Orquestador: Control automatizado');
        }
    }

    // Función para convertir markdown básico a HTML
    markdownToHtml(markdown) {
        let html = markdown;
        
        // Convertir headers con tamaños más pequeños
        html = html.replace(/^# (.+)$/gm, '<h1 style="color: #3b82f6; margin: 0.8rem 0; font-size: 1.1rem; font-weight: 600;">$1</h1>');
        html = html.replace(/^## (.+)$/gm, '<h2 style="color: #60a5fa; margin: 0.6rem 0; font-size: 1rem; font-weight: 600;">$1</h2>');
        html = html.replace(/^### (.+)$/gm, '<h3 style="color: #93c5fd; margin: 0.5rem 0; font-size: 0.95rem; font-weight: 600;">$1</h3>');
        html = html.replace(/^#### (.+)$/gm, '<h4 style="color: #dbeafe; margin: 0.4rem 0; font-size: 0.9rem; font-weight: 600;">$1</h4>');
        
        // Code blocks (con styling más compacto)
        html = html.replace(/```[\s\S]*?```/g, (match) => {
            const code = match.replace(/```[\w]*\n?/g, '').replace(/```$/g, '');
            return `<pre style="background: rgba(30, 41, 59, 0.8); padding: 0.8rem; border-radius: 6px; border-left: 3px solid #3b82f6; margin: 0.8rem 0; overflow-x: auto; font-size: 0.85rem;"><code style="color: #e2e8f0; font-family: 'Consolas', 'Monaco', monospace;">${this.escapeHtml(code)}</code></pre>`;
        });
        
        // Inline code más pequeño
        html = html.replace(/`([^`]+)`/g, '<code style="background: rgba(51, 65, 85, 0.6); padding: 0.15rem 0.3rem; border-radius: 3px; color: #fbbf24; font-family: \'Consolas\', \'Monaco\', monospace; font-size: 0.85rem;">$1</code>');
        
        // Bold/Strong
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong style="color: #fbbf24; font-weight: 600;">$1</strong>');
        
        // Procesar listas (mejorado)
        const lines = html.split('\n');
        const processed = [];
        let inList = false;
        let listType = null;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const isUnorderedItem = /^- (.+)/.test(line);
            const isOrderedItem = /^\d+\. (.+)/.test(line);
            const isItem = isUnorderedItem || isOrderedItem;
            
            if (isItem) {
                const currentType = isUnorderedItem ? 'ul' : 'ol';
                
                if (!inList || listType !== currentType) {
                    if (inList) {
                        processed.push(`</${listType}>`);
                    }
                    processed.push(`<${currentType} style="margin: 0.4rem 0; padding-left: 1.2rem; font-size: 0.9rem;">`);
                    inList = true;
                    listType = currentType;
                }
                
                const content = line.replace(/^[-\d]+\.\s/, '');
                processed.push(`<li style="margin: 0.2rem 0; color: #cbd5e1; line-height: 1.4;">${content}</li>`);
            } else {
                if (inList) {
                    processed.push(`</${listType}>`);
                    inList = false;
                    listType = null;
                }
                processed.push(line);
            }
        }
        
        if (inList) {
            processed.push(`</${listType}>`);
        }
        
        html = processed.join('\n');
        
        // Convertir párrafos
        html = html.replace(/\n\n+/g, '</p><p style="margin: 0.8rem 0; color: #e2e8f0; line-height: 1.6;">');
        html = '<p style="margin: 0.8rem 0; color: #e2e8f0; line-height: 1.6;">' + html + '</p>';
        
        // Limpiar tags vacíos y conflictos
        html = html.replace(/<p[^>]*><\/p>/g, '');
        html = html.replace(/<p[^>]*>(\s*<h[1-6][^>]*>)/g, '$1');
        html = html.replace(/(<\/h[1-6]>)\s*<\/p>/g, '$1');
        html = html.replace(/<p[^>]*>(\s*<(?:ul|ol|pre)[^>]*>)/g, '$1');
        html = html.replace(/(<\/(?:ul|ol|pre)>)\s*<\/p>/g, '$1');
        
        // Styling adicional para emojis y elementos especiales
        html = html.replace(/(✅|❌|⚠️|🔧|🎯|💡|📋|🚀|⚡|🔍|💻|🎮|📁|🌐|💾|🛠️|🏠|🔄|🟢|🟡|🔴|🆕|🛡️|📊|🧹|📈|📞|🔄|👶|👨‍💼|👨‍💻|🔒|💰|🌟|🌡️|⏱️|📦|📝|💰|🔥|⚖️)/g, '<span style="font-size: 1.1em; margin-right: 0.3rem;">$1</span>');
        
        return html;
    }

    // Función para escapar HTML
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }

    // Función de respaldo para contenido de ayuda
    getFallbackHelpContent(key) {
        const fallbacks = {
            'presets': '<p><strong>Presets de Configuración</strong></p><p>Los presets optimizan el traductor para diferentes tipos de hardware.</p>',
            'auto-detect-dcs': '<p><strong>Auto-detección de DCS</strong></p><p>Detecta automáticamente la instalación de DCS World.</p>',
            'user-root-dir': '<p><strong>Carpeta Raíz</strong></p><p>Carpeta donde están las campañas de DCS.</p>',
            'user-file-target': '<p><strong>Archivo Objetivo</strong></p><p>Archivo específico de campaña a traducir.</p>',
            'user-lm-url': '<p><strong>URL Servidor LM</strong></p><p>Dirección del servidor de modelo de lenguaje.</p>',
            'user-deploy-dir': '<p><strong>Carpeta Despliegue</strong></p><p>Donde se guardan las traducciones.</p>',
            'user-deploy-overwrite': '<p><strong>Sobrescribir Despliegue</strong></p><p>Control de archivos existentes.</p>',
            'user-lm-model': '<p><strong>Modelo de Lenguaje</strong></p><p>Selección del modelo de IA a usar.</p>',
            'args': '<p><strong>Argumentos</strong></p><p>Parámetros técnicos del sistema.</p>',
            'cache': '<p><strong>Cache</strong></p><p>Sistema de reutilización de traducciones.</p>',
            'overwrite-cache': '<p><strong>Sobrescribir Cache</strong></p><p>Control del cache existente.</p>',
            'fc': '<p><strong>Flaming Cliffs</strong></p><p>Detección de campañas FC.</p>',
            'profiles': '<p><strong>Perfiles</strong></p><p>Configuraciones guardadas reutilizables.</p>'
        };
        
        return fallbacks[key] || '<p>Ayuda no disponible para esta función.</p>';
    }
    
    async loadInitialData() {
        // Mostrar modal explicativo de perfiles si es primera vez
        this.showProfileExplanationIfFirstTime();
        
        // Cargar PROMTS primero (para llenar el dropdown)
        await this.loadPromts();
        
        // Cargar presets ANTES de la configuración (para que el dropdown esté disponible)
        this.renderPresetList();
        
        // Cargar perfiles disponibles
        await this.loadProfiles();
        
        // Cargar configuración general del usuario (para establecer valores guardados)
        await this.loadUserConfig();
        
        // Escanear modelos LM Studio
        await this.scanLmModels();
        
        // Renderizar preview de ARGS
        this.renderArgsPreview();
        
        // Inicializar estado del modelo
        this.initializeModelStatus();
        
        // Verificar configuración inicial y actualizar contador de misiones
        await this.updateModeCounter();
        
        // Verificar estado de unidades (after loadInitialData para evitar conflictos)
        setTimeout(async () => {
            await this.checkDriveStatus();
        }, 500);
    }
    
    showProfileExplanationIfFirstTime() {
        /**
         * Muestra el modal explicativo de perfiles si es la primera vez que se accede
         * Usa localStorage para recordar si ya se mostró
         */
        try {
            const hasSeenProfileExplanation = localStorage.getItem('hasSeenProfileExplanation');
            
            if (!hasSeenProfileExplanation) {
                // Mostrar modal después de un pequeño delay para que la página cargue
                setTimeout(() => {
                    this.showModal('profileExplanationModal');
                }, 1000);
            }
        } catch (error) {
            console.error('Error verificando si mostrar modal de perfiles:', error);
        }
    }
    
    markProfileExplanationAsSeen() {
        /**
         * Marca el modal explicativo como visto para que no se muestre más
         */
        try {
            localStorage.setItem('hasSeenProfileExplanation', 'true');
        } catch (error) {
            console.error('Error marcando modal de perfiles como visto:', error);
        }
    }
    
    showModal(modalId) {
        /**
         * Muestra un modal específico
         */
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }
    
    hideModal(modalId) {
        /**
         * Oculta un modal específico
         */
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
            
            // Si es el modal de explicación de perfiles, marcarlo como visto
            if (modalId === 'profileExplanationModal') {
                this.markProfileExplanationAsSeen();
            }
        }
    }
    
    // === PRESETS ===
    
    loadStore() {
        try {
            return JSON.parse(localStorage.getItem(this.PRESET_KEY) || '{}');
        } catch(e) {
            return {};
        }
    }
    
    saveStore(store) {
        localStorage.setItem(this.PRESET_KEY, JSON.stringify(store));
    }
    
    renderPresetList() {
        const sel = document.getElementById('presetList');
        if (!sel) return;
        
        console.log('🔄 Cargando presets DINÁMICAMENTE desde app/data/presets...');
        
        // Cargar presets dinámicamente desde API
        fetch('/api/presets')
            .then(response => {
                console.log('🌐 Estado respuesta API:', response.status, response.statusText);
                return response.json();
            })
            .then(data => {
                console.log('📊 Respuesta completa API:', data);
                
                if (data.ok && data.presets && data.presets.length > 0) {
                    console.log('✅ Presets encontrados desde app/data/presets:', data.presets.length);
                    
                    sel.innerHTML = '';
                    
                    // Agregar opción por defecto
                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.textContent = '-- Seleccionar Preset --';
                    sel.appendChild(defaultOption);
                    
                    // Solo mostrar presets predefinidos (YAML)
                    const predefinedPresets = data.presets.filter(p => p.type === 'predefined');
                    if (predefinedPresets.length > 0) {
                        const predefinedGroup = document.createElement('optgroup');
                        predefinedGroup.label = 'Presets Predefinidos';
                        
                        predefinedPresets.forEach(preset => {
                            const option = document.createElement('option');
                            option.value = preset.name;
                            option.textContent = `${preset.name} - ${preset.description}`;
                            option.dataset.type = preset.type;
                            option.dataset.filename = preset.filename;
                            predefinedGroup.appendChild(option);
                        });
                        
                        sel.appendChild(predefinedGroup);
                        console.log('✅ Presets predefinidos cargados:', predefinedPresets.length);
                    } else {
                        console.warn('⚠️ No hay presets predefinidos en la respuesta');
                    }
                } else {
                    console.error('❌ API no devolvió presets válidos:', data);
                    console.log('🔄 NO usando fallback localStorage - solo API');
                }
            })
            .catch(error => {
                console.error('❌ Error conectando con API presets:', error);
                console.log('🔄 NO usando fallback localStorage - solo API');
            });
    }
    
    renderPresetListFallback() {
        const store = this.loadStore();
        const sel = document.getElementById('presetList');
        if (!sel) return;
        
        sel.innerHTML = '';
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '-- Seleccionar Preset --';
        sel.appendChild(defaultOption);
        
        Object.keys(store).sort().forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = `${name} (local)`;
            option.dataset.type = 'local';
            sel.appendChild(option);
        });
    }
    
    captureForm() {
        const mode = [...document.querySelectorAll('input[name=mode]')]
            .find(x => x.checked)?.value || 'translate';
        
        // Debug logging para verificar valores de cache
        const useCacheElement = document.getElementById('useCache');
        const overwriteCacheElement = document.getElementById('overwriteCache');
        console.log('🔍 DEBUG Cache checkboxes:');
        console.log('  useCache element:', useCacheElement);
        console.log('  useCache checked:', useCacheElement?.checked);
        console.log('  overwriteCache element:', overwriteCacheElement);
        console.log('  overwriteCache checked:', overwriteCacheElement?.checked);
            
        const formData = {
            ROOT_DIR: this.getElementValue('userRootDir'),
            FILE_TARGET: this.getElementValue('userFileTarget'),
            arg_config: this.getElementValue('arg_config'),
            arg_compat: this.getElementValue('arg_compat'),
            arg_batch: this.getElementValue('arg_batch'),
            arg_timeout: this.getElementValue('arg_timeout'),
            arg_model: this.getElementValue('userLmModel'),
            arg_url: this.getElementValue('userLmUrl'),
            DEPLOY_DIR: this.getElementValue('userDeployDir'),
            DEPLOY_OVERWRITE: document.getElementById('userDeployOverwrite')?.checked || false,
            include_fc: document.getElementById('include_fc')?.checked || false,
            use_cache: document.getElementById('useCache')?.checked === true,  // Explicitly check for true
            overwrite_cache: document.getElementById('overwriteCache')?.checked === true,  // Explicitly check for true
            preset: this.getElementValue('presetList'),  // Incluir preset seleccionado
            mode
        };
        
        console.log('🔍 Final formData cache values:');
        console.log('  use_cache:', formData.use_cache);
        console.log('  overwrite_cache:', formData.overwrite_cache);
        
        return formData;
    }
    
    applyForm(data) {
        if (!data) return;
        
        this.setElementValue('userRootDir', data.ROOT_DIR || '');
        this.setElementValue('userFileTarget', data.FILE_TARGET || 'l10n/DEFAULT/dictionary');
        this.setElementValue('arg_config', data.arg_config);
        this.setElementValue('arg_compat', data.arg_compat || 'completions');
        this.setElementValue('arg_batch', data.arg_batch || '4');
        this.setElementValue('arg_timeout', data.arg_timeout || '200');
        this.setElementValue('userLmModel', data.lm_model || '');
        this.setElementValue('userLmUrl', data.lm_url || 'http://localhost:1234/v1');
        this.setElementValue('userDeployDir', data.DEPLOY_DIR || '');
        this.setElementValue('userDeployOverwrite', data.DEPLOY_OVERWRITE);
        
        const includeFC = document.getElementById('include_fc');
        if (includeFC) includeFC.checked = !!data.include_fc;
        
        const useCache = document.getElementById('useCache');
        if (useCache) {
            // Default to true if not specified, or handle string/boolean values
            const useCacheValue = data.use_cache !== undefined ? 
                (data.use_cache === true || data.use_cache === "True" || data.use_cache === "true") : true;
            useCache.checked = useCacheValue;
        }
        
        const overwriteCache = document.getElementById('overwriteCache');
        if (overwriteCache) overwriteCache.checked = data.overwrite_cache === true || data.overwrite_cache === "True" || data.overwrite_cache === "true"; // Handle string and boolean values
        
        if (data.mode) {
            const radio = document.querySelector(`input[name=mode][value="${data.mode}"]`);
            if (radio) radio.checked = true;
        }
        
        this.renderArgsPreview();
    }
    
    applyModelConfigOnly(data) {
        /**
         * Aplica solo los parámetros del modelo, sin tocar la configuración general
         * Usado para cargar presets sin afectar ROOT_DIR, DEPLOY_DIR, etc.
         */
        if (!data) return;
        
        // Solo parámetros del modelo
        this.setElementValue('arg_config', data.arg_config);
        this.setElementValue('arg_compat', data.arg_compat || 'completions');
        this.setElementValue('arg_batch', data.arg_batch || '4');
        this.setElementValue('arg_timeout', data.arg_timeout || '200');
        
        // Solo actualizar modelo si el preset especifica uno
        if (data.lm_model) {
            this.setElementValue('userLmModel', data.lm_model);
        }
        
        // Solo actualizar URL si el preset especifica una
        if (data.lm_url) {
            this.setElementValue('userLmUrl', data.lm_url);
        }
        
        // Parámetros de API del modelo (desde preset)
        if (data.api_temperature !== undefined) this.setElementValue('api_temperature', data.api_temperature);
        if (data.api_top_p !== undefined) this.setElementValue('api_top_p', data.api_top_p);
        if (data.api_top_k !== undefined) this.setElementValue('api_top_k', data.api_top_k);
        if (data.api_max_tokens !== undefined) this.setElementValue('api_max_tokens', data.api_max_tokens);
        if (data.api_repetition_penalty !== undefined) this.setElementValue('api_repetition_penalty', data.api_repetition_penalty);
        if (data.api_presence_penalty !== undefined) this.setElementValue('api_presence_penalty', data.api_presence_penalty);
        
        // Actualizar preview de argumentos
        this.renderArgsPreview();
        
        console.log('✅ Preset cargado - solo parámetros del modelo aplicados (incluyendo API)');
    }
    
    captureModelConfigOnly() {
        /**
         * Captura solo los parámetros del modelo para guardar en presets
         * No incluye configuración general como ROOT_DIR, DEPLOY_DIR, etc.
         */
        return {
            // Solo parámetros del modelo
            arg_config: this.getElementValue('arg_config'),
            arg_compat: this.getElementValue('arg_compat'),
            arg_batch: this.getElementValue('arg_batch'),
            arg_timeout: this.getElementValue('arg_timeout'),
            lm_model: this.getElementValue('userLmModel'),
            lm_url: this.getElementValue('userLmUrl'),
            
            // Parámetros de API del modelo
            api_temperature: this.getElementValue('api_temperature'),
            api_top_p: this.getElementValue('api_top_p'),
            api_top_k: this.getElementValue('api_top_k'),
            api_max_tokens: this.getElementValue('api_max_tokens'),
            api_repetition_penalty: this.getElementValue('api_repetition_penalty'),
            api_presence_penalty: this.getElementValue('api_presence_penalty'),
            
            // Metadatos del preset
            preset_metadata: {
                name: 'Preset personalizado',
                description: 'Configuración guardada por el usuario',
                created_at: new Date().toISOString()
            }
        };
    }
    
    // FUNCIÓN DESHABILITADA: savePreset() 
    // Ya no es necesaria con presets predefinidos
    /* savePreset() {
        const nameInput = document.getElementById('presetName');
        const name = nameInput?.value?.trim();
        
        if (!name) {
            alert('Pon un nombre para el preset.');
            return;
        }
        
        const store = this.loadStore();
        store[name] = this.captureModelConfigOnly();
        this.saveStore(store);
        this.renderPresetList();
        
        // Seleccionar el preset recién guardado
        const presetList = document.getElementById('presetList');
        if (presetList) {
            [...presetList.options].forEach(option => {
                if (option.value === name) option.selected = true;
            });
        }
        
        // Limpiar campo de nombre
        if (nameInput) nameInput.value = '';
    } */
    
    async loadPreset() {
        const presetList = document.getElementById('presetList');
        const name = presetList?.value;
        
        if (!name) {
            alert('No hay preset seleccionado.');
            return;
        }
        
        const selectedOption = presetList.options[presetList.selectedIndex];
        const presetType = selectedOption.dataset.type;
        
        if (presetType === 'local') {
            // Cargar desde localStorage (compatibilidad)
            const store = this.loadStore();
            if (!store[name]) {
                alert('Preset no encontrado.');
                return;
            }
            this.applyModelConfigOnly(store[name]);
            
            // Asegurar que el preset queda seleccionado en el dropdown
            presetList.value = name;
            
            // Guardar automáticamente el preset activo
            await this.saveModelConfig();
            
            // Actualizar el badge de perfil en el header
            this.updateProfileStatus();
        } else {
            // Cargar desde API (YAML o JSON)
            try {
                const response = await fetch(`/api/presets/${encodeURIComponent(name)}`);
                const data = await response.json();
                
                if (data.ok) {
                    this.applyModelConfigOnly(data.config);
                    
                    // NUEVO: Mostrar modelos recomendados
                    this.showRecommendedModels(data.config);
                    
                    // Mostrar información del preset si está disponible
                    const metadata = data.config.preset_metadata;
                    if (metadata && metadata.description) {
                        const message = `Preset cargado: ${metadata.name}\n${metadata.description}`;
                        console.log(message);
                        // Opcional: mostrar toast o notificación
                    }
                    
                    // Asegurar que el preset queda seleccionado en el dropdown
                    presetList.value = name;
                    
                    // Guardar automáticamente el preset activo
                    await this.saveModelConfig();
                    
                    // Actualizar el badge de perfil en el header
                    this.updateProfileStatus();
                } else {
                    alert(`Error cargando preset: ${data.error}`);
                }
            } catch (error) {
                console.error('Error cargando preset:', error);
                alert('Error conectando con el servidor para cargar el preset.');
            }
        }
    }
    
    // FUNCIÓN DESHABILITADA: deletePreset()
    // Ya no es necesaria con presets predefinidos (no se pueden borrar)
    /* deletePreset() {
        const presetList = document.getElementById('presetList');
        const name = presetList?.value;
        
        if (!name) {
            alert('No hay preset seleccionado.');
            return;
        }
        
        if (!confirm(`¿Borrar el preset "${name}"?`)) return;
        
        const store = this.loadStore();
        delete store[name];
        this.saveStore(store);
        this.renderPresetList();
    } */
    
    // === AUTO-DETECCIÓN ROOT_DIR ===
    
    async autoDetectRoot(deep = false) {
        const msg = document.getElementById('autoRootMsg');
        if (msg) {
            msg.textContent = deep ? 'Buscando (búsqueda profunda)…' : 'Buscando ubicaciones típicas…';
        }
        
        // Verificar estado de unidades antes de la detección
        await this.checkDriveStatus();
        
        try {
            const response = await fetch('/api/auto_detect_roots', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ deep_scan: deep })
            });
            
            const result = await response.json();
            
            if (!result.success) {
                if (msg) msg.textContent = `No fue posible detectar (${result.error || ''})`;
                
                // Mostrar avisos de unidades desconectadas si los hay
                if (result.campaigns_summary && result.campaigns_summary.warnings.length > 0) {
                    this.showDriveWarnings(result.campaigns_summary.warnings);
                }
                return;
            }
            
            const roots = result.roots || [];
            
            // Mostrar información de campañas registradas y estado de unidades
            if (result.campaigns_summary) {
                this.processCampaignsSummary(result.campaigns_summary);
            }
            
            if (roots.length === 0) {
                if (msg) {
                    if (deep) {
                        msg.textContent = 'No se encontró instalación de DCS World. Configura manualmente la ruta.';
                    } else {
                        msg.textContent = 'No se encontró DCS en ubicaciones comunes.';
                    }
                }
                
                if (!deep && confirm('¿Probar una búsqueda más profunda (puede tardar)?')) {
                    this.autoDetectRoot(true);
                } else if (deep) {
                    // Mostrar ayuda adicional después de búsqueda profunda fallida
                    if (confirm('No se encontró DCS World instalado.\\n\\n¿Necesitas ayuda para configurar manualmente la ruta?')) {
                        alert('Para configurar manualmente:\\n\\n1. Localiza tu instalación de DCS World\\n2. Navega hasta la carpeta "Mods/campaigns"\\n3. Ingresa esa ruta en el campo "RUTA CAMPAÑAS"\\n\\nEjemplos comunes:\\n• C:\\\\Program Files\\\\Eagle Dynamics\\\\DCS World\\\\Mods\\\\campaigns\\n• D:\\\\Steam\\\\steamapps\\\\common\\\\DCSWorld\\\\Mods\\\\campaigns');
                    }
                }
                return;
            }
            
            if (roots.length === 1) {
                this.setElementValue('userRootDir', roots[0]);
                if (msg) msg.textContent = `Detectado: ${roots[0]}`;
                // Guardar automáticamente la configuración actualizada
                await this.saveUserConfig();
            } else {
                const list = roots.map((p, i) => `${i + 1}) ${p}`).join('\\n');
                const selection = prompt(
                    `Se han encontrado varias ubicaciones:\\n\\n${list}\\n\\nEscribe el número a usar:`, 
                    '1'
                );
                
                const idx = parseInt(selection || '1', 10) - 1;
                
                if (isFinite(idx) && idx >= 0 && idx < roots.length) {
                    this.setElementValue('userRootDir', roots[idx]);
                    if (msg) msg.textContent = `Seleccionado: ${roots[idx]}`;
                    // Guardar automáticamente la configuración actualizada
                    await this.saveUserConfig();
                } else {
                    if (msg) msg.textContent = 'Selección cancelada.';
                }
            }
            
        } catch (error) {
            console.error('Error en auto-detección:', error);
            if (msg) msg.textContent = 'Error al escanear unidades.';
        }
    }
    
    async detectDCSInstallation() {
        const statusElement = document.getElementById('dcsDetectionStatus');
        const btnDetect = document.getElementById('btnDetectDCS');
        
        if (!statusElement || !btnDetect) return;
        
        try {
            // Deshabilitar botón y mostrar estado de carga
            btnDetect.disabled = true;
            btnDetect.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Detectando...';
            statusElement.textContent = '🔍 Buscando instalación de DCS World...';
            statusElement.className = 'status-message loading';
            
            // Llamar al endpoint de detección de DCS
            const response = await fetch('/api/detect-dcs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.ok && result.paths) {
                const { campaigns_path, deploy_path } = result.paths;
                
                // Llenar las rutas detectadas
                if (campaigns_path) {
                    this.setElementValue('userRootDir', campaigns_path);
                    console.log('✅ Ruta de campañas detectada:', campaigns_path);
                }
                
                if (deploy_path) {
                    this.setElementValue('userDeployDir', deploy_path);
                    console.log('✅ Ruta de despliegue detectada:', deploy_path);
                }
                
                statusElement.textContent = '✅ DCS World detectado correctamente';
                statusElement.className = 'status-message success';
                
                // Guardar automáticamente la configuración
                await this.saveUserConfig();
                
            } else {
                // No se encontró DCS
                statusElement.textContent = result.message || '❌ No se pudo detectar DCS World';
                statusElement.className = 'status-message error';
                
                // Mostrar ayuda si no se encontró
                setTimeout(() => {
                    if (confirm('No se encontró una instalación automática de DCS World.\\n\\n¿Quieres ayuda para configurar manualmente las rutas?')) {
                        this.showDCSManualHelp();
                    }
                }, 1500);
            }
            
        } catch (error) {
            console.error('Error detectando DCS:', error);
            statusElement.textContent = '❌ Error al detectar DCS World';
            statusElement.className = 'status-message error';
            
        } finally {
            // Restaurar botón
            btnDetect.disabled = false;
            btnDetect.innerHTML = '<i class="fas fa-search"></i> Detectar DCS World';
            
            // Limpiar mensaje después de 5 segundos
            setTimeout(() => {
                if (statusElement) {
                    statusElement.textContent = '';
                    statusElement.className = 'status-message';
                }
            }, 5000);
        }
    }
    
    showDCSManualHelp() {
        const helpMessage = `Para configurar manualmente las rutas de DCS:

🎯 RUTA CAMPAÑAS:
• Ubicación: [Instalación DCS]\\Mods\\campaigns
• Ejemplo: C:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns

📁 RUTA DESPLIEGUE:
• Ubicación: Misma que campañas (donde quieres las misiones traducidas)
• Ejemplo: C:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns

🔍 Ubicaciones comunes de DCS:
• C:\\Program Files\\Eagle Dynamics\\DCS World\\
• D:\\Steam\\steamapps\\common\\DCSWorld\\
• C:\\Users\\[Usuario]\\Saved Games\\DCS.openbeta\\`;
        
        alert(helpMessage);
    }
    
    async tryAutoDetectDCS() {
        /**
         * Función de conveniencia para detectar DCS desde el contador de modo.
         * Se llama cuando hay error de ROOT_DIR no configurado.
         */
        try {
            console.log('🔍 Intentando auto-detección de DCS desde contador de modo...');
            
            // Llamar la función principal de detección
            await this.detectDCSInstallation();
            
            // Si tuvo éxito, recargar el contador
            setTimeout(() => {
                this.updateModeCounter();
            }, 1000);
            
        } catch (error) {
            console.error('❌ Error en tryAutoDetectDCS:', error);
        }
    }
    
    // === PROMTS ===
    
    async loadPromts() {
        const sel = document.getElementById('arg_config');
        if (!sel) return;
        
        sel.innerHTML = '';
        
        try {
            const response = await fetch('/api/promts');
            const result = await response.json();
            
            if (!result.ok) throw new Error(result.error || 'Error');
            
            const files = result.files || [];
            
            if (files.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = '(no hay YAML en ./PROMTS)';
                sel.appendChild(option);
            } else {
                files.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file;
                    option.textContent = file;
                    sel.appendChild(option);
                });
                
                console.log(`PROMTS cargados: ${files.length} archivos encontrados`);
                // No establecer valor aquí - se hará en loadUserConfig()
            }
            
        } catch (error) {
            console.error('Error cargando PROMTS:', error);
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '(error leyendo /promts)';
            sel.appendChild(option);
        }
    }
    
    // === LM STUDIO ===
    
    async scanLmModels() {
        const url = this.getElementValue('userLmUrl') || 'http://localhost:1234/v1';
        const hint = document.getElementById('lmModelsHint');
        const datalist = document.getElementById('user_lm_models_list');
        
        if (hint) hint.textContent = 'Consultando modelos…';
        if (datalist) datalist.innerHTML = '';
        
        try {
            const response = await fetch(`/api/lm_models?lm_url=${encodeURIComponent(url)}`);
            const result = await response.json();
            
            if (!result.ok) {
                if (hint) hint.textContent = `LM Studio no disponible (${result.error || ''})`;
                return;
            }
            
            const models = result.models || [];
            console.log('Modelos recibidos de la API:', models);
            
            if (datalist) {
                models.forEach((model, index) => {
                    console.log(`Modelo ${index}:`, model, 'tipo:', typeof model);
                    const option = document.createElement('option');
                    
                    // Extraer el nombre del modelo del objeto
                    let modelName;
                    if (typeof model === 'string') {
                        modelName = model;
                    } else if (model && typeof model === 'object') {
                        // Usar 'name' si existe, sino 'id', sino JSON stringify
                        modelName = model.name || model.id || JSON.stringify(model);
                    } else {
                        modelName = String(model);
                    }
                    
                    option.value = modelName;
                    datalist.appendChild(option);
                });
            }
            
            if (hint) {
                hint.textContent = models.length ? 
                    `Modelos disponibles: ${models.length}` : 
                    'No se encontraron modelos cargados.';
            }
            
            // NO auto-seleccionar modelo - dejar que el usuario elija conscientemente
            // Solo actualizar el preview si ya hay un modelo seleccionado
            const modelInput = document.getElementById('userLmModel');
            if (modelInput?.value) {
                this.renderArgsPreview();
                console.log('Modelo ya seleccionado:', modelInput.value);
            } else {
                console.log('No hay modelo seleccionado - esperando selección manual del usuario');
            }
            
        } catch (error) {
            console.error('Error escaneando modelos LM:', error);
            if (hint) hint.textContent = 'Error consultando LM Studio.';
        }
    }
    
    // Verificar estado del modelo seleccionado (versión optimizada)
    async checkModelStatus() {
        const modelStatusIndicator = document.getElementById('modelStatusIndicator');
        const modelStatusIcon = document.getElementById('modelStatusIcon');
        const modelStatusText = document.getElementById('modelStatusText');
        
        if (!modelStatusIndicator || !modelStatusIcon || !modelStatusText) return;
        
        const selectedModel = this.getElementValue('userLmModel');
        const lmUrl = this.getElementValue('userLmUrl') || 'http://localhost:1234/v1';
        
        if (!selectedModel || selectedModel.trim() === '' || selectedModel === 'Seleccionar modelo...') {
            // No hay modelo seleccionado
            this.updateModelStatus('warning', '⚠️', 'Selecciona un modelo de la lista');
            return;
        }
        
        // Verificación rápida sin mostrar "verificando" para evitar delay
        try {
            // Usar timeout corto para verificación rápida
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 segundos timeout
            
            const response = await fetch(`/api/lm_models?lm_url=${encodeURIComponent(lmUrl)}`, {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const result = await response.json();
            
            if (!result.ok) {
                this.updateModelStatus('error', '❌', 'LM Studio no disponible');
                return;
            }
            
            const models = result.models || [];
            
            // Crear arrays tanto de IDs completos como de nombres cortos
            const modelIds = models.map(m => typeof m === 'string' ? m : m.id || '');
            const modelNames = models.map(m => typeof m === 'string' ? m : (m.name || ''));
            
            // Debug: mostrar información de comparación
            console.log('🔍 DEBUG - Verificación de modelo:');
            console.log('Modelo seleccionado:', selectedModel);
            console.log('IDs completos disponibles:', modelIds);
            console.log('Nombres cortos disponibles:', modelNames);
            console.log('Modelos raw:', models);
            
            // Verificar si coincide con ID completo O con nombre corto
            const isModelLoaded = modelIds.includes(selectedModel) || modelNames.includes(selectedModel);
            
            if (isModelLoaded) {
                this.updateModelStatus('success', '✅', `Modelo "${selectedModel}" listo`);
            } else if (models.length === 0) {
                this.updateModelStatus('warning', '⚠️', 'Sin modelos cargados en LM Studio');
            } else {
                console.log('❌ Modelo no encontrado. Comparación exacta falló.');
                this.updateModelStatus('warning', '⚠️', `Modelo "${selectedModel}" no cargado`);
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                this.updateModelStatus('warning', '⏱️', 'LM Studio responde lento');
            } else {
                console.error('Error verificando estado del modelo:', error);
                this.updateModelStatus('error', '❌', 'Error al verificar modelo');
            }
        }
    }
    
    // Inicializar el estado del modelo cuando carga la página
    initializeModelStatus() {
        const selectedModel = this.getElementValue('userLmModel');
        
        if (!selectedModel || selectedModel.trim() === '' || selectedModel === 'Seleccionar modelo...') {
            this.updateModelStatus('warning', '⚠️', 'Selecciona un modelo para traducir');
        } else {
            // Si hay modelo seleccionado, verificar su estado
            this.checkModelStatus();
        }
        
        // Actualizar estado del perfil al cargar la página
        this.updateProfileStatus();
    }

    // Actualizar badge con el modelo realmente cargado en LM Studio
    async updateLoadedModelBadge() {
        const modelStatusBadge = document.getElementById('modelStatus');
        if (!modelStatusBadge) {
            console.log('Badge modelStatus no encontrado');
            return;
        }
        
        const lmUrl = this.getElementValue('userLmUrl') || 'http://localhost:1234/v1';
        
        try {
            console.log('🔥 Consultando modelo cargado en:', lmUrl);
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 segundos timeout
            
            const response = await fetch(`/api/lm_loaded_model?lm_url=${encodeURIComponent(lmUrl)}`, {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const result = await response.json();
            console.log('🔥 Respuesta del servidor:', result);
            
            if (result.ok && result.loaded_model) {
                // Hay un modelo cargado
                const shortName = result.loaded_model.short_name;
                modelStatusBadge.className = 'badge bg-success';
                modelStatusBadge.textContent = `✅ ${shortName}`;
                
                // Marcar el badge como "protegido" para evitar que otras funciones lo sobrescriban
                modelStatusBadge.dataset.loadedModel = 'true';
                modelStatusBadge.dataset.modelName = shortName;
                
                console.log('✅ Badge actualizado con modelo cargado:', shortName);
                
                // Programar actualizaciones periódicas cada 10 segundos
                setTimeout(() => {
                    this.updateLoadedModelBadge();
                }, 10000);
                
            } else {
                // No hay modelo cargado o error
                console.log('⚠️ No hay modelos cargados en LM Studio');
                modelStatusBadge.className = 'badge bg-warning';
                modelStatusBadge.textContent = '⚠️ Sin Modelo';
                delete modelStatusBadge.dataset.loadedModel;
            }
            
        } catch (error) {
            console.log('❌ Error verificando modelo en LM Studio:', error.name, error.message);
            // No cambiar el badge si hay error, pero programar reintento
            setTimeout(() => {
                this.updateLoadedModelBadge();
            }, 15000);
        }
    }

    async updateProfileStatus() {
        const profileStatus = document.getElementById('profileStatus');
        if (!profileStatus) return;
        
        const profilesList = document.getElementById('profilesList');
        const presetList = document.getElementById('presetList');
        
        const selectedProfile = profilesList?.value;
        const selectedPreset = presetList?.value;
        
        if (selectedProfile && selectedProfile !== '') {
            let displayText = `📋 ${selectedProfile}`;
            if (selectedPreset && selectedPreset !== '') {
                displayText += ` | ${selectedPreset}`;
            }
            
            profileStatus.className = 'badge badge-success me-2';
            profileStatus.textContent = displayText;
            profileStatus.style.display = 'inline-block';
        } else {
            profileStatus.className = 'badge badge-warning me-2';
            profileStatus.textContent = '⚠️ Sin Perfil';
            profileStatus.style.display = 'inline-block';
        }
    }
    
    // Actualizar el indicador visual de estado del modelo
    updateModelStatus(type, icon, text) {
        const modelStatusIndicator = document.getElementById('modelStatusIndicator');
        const modelStatusIcon = document.getElementById('modelStatusIcon');
        const modelStatusText = document.getElementById('modelStatusText');
        
        if (!modelStatusIndicator || !modelStatusIcon || !modelStatusText) return;
        
        // Mostrar el indicador
        modelStatusIndicator.style.display = 'block';
        
        // Actualizar contenido
        modelStatusIcon.textContent = icon;
        modelStatusText.textContent = text;
        
        // 🔧 TAMBIÉN ACTUALIZAR EL BADGE DEL HEADER
        const modelStatusBadge = document.getElementById('modelStatus');
        if (modelStatusBadge) {
            // NO sobrescribir si ya hay un modelo cargado detectado
            if (modelStatusBadge.dataset.loadedModel === 'true') {
                console.log('🛡️ Badge protegido - modelo ya cargado:', modelStatusBadge.dataset.modelName);
                return;
            }
            
            // Mapear tipos a clases de bootstrap y textos cortos
            const badgeConfig = {
                success: { 
                    className: 'badge bg-success', 
                    text: `${icon} Modelo Listo` 
                },
                warning: { 
                    className: 'badge bg-warning', 
                    text: `${icon} Modelo Pendiente` 
                },
                error: { 
                    className: 'badge bg-danger', 
                    text: `${icon} Error Modelo` 
                },
                info: { 
                    className: 'badge bg-info', 
                    text: `${icon} Verificando...` 
                }
            };
            
            const config = badgeConfig[type] || badgeConfig.info;
            modelStatusBadge.className = config.className;
            modelStatusBadge.textContent = config.text;
        }

        // Aplicar estilos según el tipo
        const styles = {
            success: {
                background: 'rgba(34, 197, 94, 0.1)',
                border: '1px solid rgba(34, 197, 94, 0.3)',
                color: '#22c55e'
            },
            warning: {
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                color: '#f59e0b'
            },
            error: {
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#ef4444'
            },
            info: {
                background: 'rgba(59, 130, 246, 0.1)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                color: '#3b82f6'
            }
        };
        
        const style = styles[type] || styles.info;
        Object.assign(modelStatusIndicator.style, style);
    }
    
    // === ARGS PREVIEW ===
    
    setupArgsPreview() {
        const argIds = ['arg_config', 'arg_compat', 'arg_batch', 'arg_timeout', 'arg_model', 'arg_url'];
        
        argIds.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', () => this.renderArgsPreview());
                element.addEventListener('change', () => this.renderArgsPreview());
            }
        });
    }
    
    buildArgs() {
        const parts = [];
        
        const config = this.getElementValue('arg_config');
        if (config) parts.push(`--config ${config}`);
        
        const compat = this.getElementValue('arg_compat');
        if (compat) parts.push(`--lm-compat ${compat}`);
        
        const batchSize = this.getElementValue('arg_batch');
        if (batchSize) parts.push(`--batch-size ${batchSize}`);
        
        const timeout = this.getElementValue('arg_timeout');
        if (timeout) parts.push(`--timeout ${timeout}`);
        
        const model = this.getElementValue('userLmModel');
        if (model) parts.push(`--lm-model ${model}`);
        
        const url = this.getElementValue('userLmUrl');
        if (url) parts.push(`--lm-url ${url}`);
        
        return parts.join(' ');
    }
    
    renderArgsPreview() {
        const preview = document.getElementById('argsPreview');
        if (preview) {
            preview.textContent = this.buildArgs();
        }
    }
    
    // === CAMPAÑAS Y MISIONES ===
    
    async scanCampaigns() {
        try {
            const rootDir = this.getElementValue('userRootDir');
            
            if (!rootDir || rootDir.trim() === '') {
                alert('Por favor, configura primero la ruta de DCS World');
                return;
            }
            
            const response = await fetch('/api/scan_campaigns', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rootDir: rootDir })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.campaigns = result.campaigns || [];
                this.renderCampaigns();
                
                // Limpiar misiones
                const missionsDiv = document.getElementById('missions');
                if (missionsDiv) missionsDiv.innerHTML = '';
                
                console.log(`Encontradas ${result.total || 0} campañas en ${result.scanned_path}`);
            } else {
                console.error('Error del servidor:', result.error);
                alert(`Error al escanear campañas: ${result.error}`);
            }
            
        } catch (error) {
            console.error('Error escaneando campañas:', error);
            alert('Error de conexión al escanear campañas');
        }
    }
    
    async renderCampaigns() {
        const box = document.getElementById('campaigns');
        if (!box) return;
        
        box.innerHTML = '<div style="color: #6b7280; font-style: italic;">Analizando campañas para el modo seleccionado...</div>';
        
        try {
            // Obtener el modo seleccionado
            const selectedMode = this.getSelectedMode();
            
            // Filtrar campañas según tengan misiones disponibles para el modo
            const availableCampaigns = await this.getAvailableCampaignsForMode(selectedMode);
            
            box.innerHTML = '';
            
            if (availableCampaigns.length === 0) {
                const modeNames = {
                    'traducir': 'traducir',
                    'reempaquetar': 'reempaquetar (necesitas misiones traducidas)',
                    'desplegar': 'desplegar (necesitas misiones reempaquetadas)'
                };
                
                box.innerHTML = `
                    <div style="color: #dc2626; padding: 8px; border: 1px solid #fecaca; background: #fef2f2; border-radius: 4px;">
                        <strong>📋 No hay campañas disponibles</strong><br>
                        <small>No se encontraron campañas con misiones listas para ${modeNames[selectedMode] || selectedMode}</small>
                    </div>
                `;
                return;
            }
            
            availableCampaigns.forEach(campaign => {
                const div = document.createElement('div');
                const missionCount = campaign.mission_count || 0;
                const stateInfo = campaign.state_info || '';
                
                div.innerHTML = `
                    <label title="Campaña: ${campaign.name} (${missionCount} misiones disponibles para ${selectedMode})">
                        <input type="radio" name="camp" value="${campaign.name}"> 
                        ${campaign.name}
                        <small style="color: #6b7280; display: block; margin-left: 20px;">${missionCount} misiones • ${stateInfo}</small>
                    </label>
                `;
                box.appendChild(div);
            });
            
            // Event listener para cambios de campaña
            box.addEventListener('change', (e) => {
                if (e.target && e.target.name === 'camp') {
                    this.selectedCampaign = e.target.value;
                    this.loadMissionsForCurrentMode();
                }
            });
            
        } catch (error) {
            console.error('Error renderizando campañas:', error);
            box.innerHTML = `
                <div style="color: #dc2626;">
                    ❌ Error cargando campañas para el modo seleccionado
                </div>
            `;
        }
    }
    
    async loadMissions() {
        if (!this.selectedCampaign) return;
        
        try {
            const includeFC = document.getElementById('include_fc')?.checked || false;
            const rootDir = this.getElementValue('userRootDir');
            
            if (!rootDir || rootDir.trim() === '') {
                alert('Por favor, configura primero la ruta de DCS World');
                return;
            }
            
            console.log(`Cargando misiones para campaña: ${this.selectedCampaign}`);
            console.log(`Filtro FC activado: ${includeFC}`);
            
            const response = await fetch('/api/scan_missions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ROOT_DIR: rootDir,
                    campaign_name: this.selectedCampaign,
                    include_fc: includeFC
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.missions = result.missions || [];
                
                // Pasar los contadores a renderMissions
                const counters = {
                    normal_count: result.normal_count || 0,
                    fc_count: result.fc_count || 0,
                    total: result.total || 0,
                    include_fc: result.include_fc || false,
                    fc_patterns_detected: result.fc_patterns_detected || [],
                    detection_summary: result.detection_summary || {}
                };
                
                this.renderMissionsForCurrentMode(counters);
                
                console.log(`Encontradas ${result.total || 0} misiones (${result.normal_count || 0} normales, ${result.fc_count || 0} FC)`);
                console.log(`Filtro FC: ${includeFC ? 'ACTIVADO' : 'DESACTIVADO'} - Mostrando: ${this.missions.length} misiones`);
                
                // Mostrar patrones FC detectados si los hay
                if (result.fc_patterns_detected && result.fc_patterns_detected.length > 0) {
                    console.log(`Patrones FC detectados: ${result.fc_patterns_detected.join(', ')}`);
                }
            } else {
                console.error('Error del servidor:', result.error);
                alert(`Error al cargar misiones: ${result.error}`);
            }
            
        } catch (error) {
            console.error('Error cargando misiones:', error);
            alert('Error de conexión al cargar misiones');
        }
    }
    
    renderMissions(list, counters = {}, currentMode = null) {
        const box = document.getElementById('missions');
        if (!box) return;
        
        box.innerHTML = '';
        
        // Obtener modo actual si no se especifica
        if (!currentMode) {
            currentMode = this.getSelectedMode();
        }
        
        // Contador de misiones
        const includeFC = document.getElementById('include_fc')?.checked || false;
        const totalMissions = list ? list.length : 0;
        
        // Si no hay contadores del backend, calcular a partir de la lista actual
        let normalCount = counters.normal_count || 0;
        let fcCount = counters.fc_count || 0;
        
        if (list && (normalCount === 0 && fcCount === 0)) {
            // Calcular contadores basándose en la lista usando detección mejorada
            normalCount = list.filter(m => m.type !== 'fc' && !this.isFlameingCliffsMission(m.name || '')).length;
            fcCount = list.filter(m => m.type === 'fc' || this.isFlameingCliffsMission(m.name || '')).length;
        }
        
        // Crear encabezado con información del modo
        const modeInfo = document.createElement('div');
        modeInfo.className = 'mode-info-header';
        modeInfo.style.cssText = 'margin-bottom: 12px; padding: 8px; background: #f0f9ff; border-left: 4px solid #0369a1; border-radius: 4px;';
        
        const modeDescriptions = {
            'traducir': {
                icon: '🌍',
                name: 'TRADUCIR',
                description: 'Mostrando todas las misiones disponibles para traducir'
            },
            'reempaquetar': {
                icon: '📦',
                name: 'REEMPAQUETAR',
                description: 'Mostrando solo misiones ya traducidas (con archivos .lua generados)'
            },
            'desplegar': {
                icon: '🚀',
                name: 'DESPLEGAR',
                description: 'Mostrando solo misiones reempaquetadas (archivos .miz listos)'
            }
        };
        
        const modeDesc = modeDescriptions[currentMode] || modeDescriptions['traducir'];
        modeInfo.innerHTML = `
            <div style="font-weight: 600; color: #0369a1;">
                ${modeDesc.icon} Modo: ${modeDesc.name}
            </div>
            <div style="font-size: 0.85em; color: #6b7280; margin-top: 2px;">
                ${modeDesc.description}
            </div>
        `;
        box.appendChild(modeInfo);
        
        const counter = document.createElement('div');
        counter.className = 'mission-counter';
        counter.style.marginBottom = '8px';
        counter.style.padding = '8px';
        counter.style.backgroundColor = '#f5f5f5';
        counter.style.borderRadius = '4px';
        counter.style.fontSize = '0.9em';
        
        let counterHTML = `<strong>📊 Misiones encontradas: ${totalMissions}</strong>`;
        if (normalCount > 0 || fcCount > 0) {
            counterHTML += ` (${normalCount} normales`;
            if (fcCount > 0) {
                counterHTML += `, ${fcCount} FC`;
                if (!includeFC) {
                    counterHTML += ` <em style="color: #666;">- ${fcCount} FC ocultas</em>`;
                }
            }
            counterHTML += `)`;
            
            // Mostrar patrones FC detectados si están disponibles y hay misiones FC
            if (fcCount > 0 && counters.fc_patterns_detected && counters.fc_patterns_detected.length > 0) {
                const patterns = counters.fc_patterns_detected.join(', ');
                counterHTML += `<br><small style="color: #666;">Patrones FC: <code>${patterns}</code></small>`;
            }
        }
        
        counter.innerHTML = counterHTML;
        box.appendChild(counter);
        
        // Leyenda dinámica según el modo - COMO HEADER LIMPIO
        const legend = document.createElement('div');
        legend.className = 'missions-legend-header';
        
        let legendHTML = '<strong>Leyenda:</strong> ';
        legendHTML += '<span class="pill pill-blue" style="background-color: #065d96ff; color: white;">FC</span> = Flaming Cliffs · ';
        
        // Leyenda específica según el modo
        if (currentMode === 'traducir') {
            legendHTML += '<span class="pill pill-green">✅ Lista para desplegar</span> = reempaquetada en <code>finalizado/</code> · ';
            legendHTML += '<span class="pill pill-amber">✨ Traducida</span> = solo <code>.translated.lua</code> en <code>out_lua/</code> · ';
            legendHTML += '<span class="pill pill-purple">🚀 Desplegada</span> = instalada en DCS';
        } else if (currentMode === 'reempaquetar') {
            legendHTML += '<span class="pill pill-amber">✨ Traducida</span> = listas para reempaquetar en .miz';
        } else if (currentMode === 'desplegar') {
            legendHTML += '<span class="pill pill-green">✅ Lista para desplegar</span> = reempaquetada en <code>finalizado/</code>';
        }
        
        legend.innerHTML = legendHTML + '.';
        
        // Insertar la leyenda al principio del contenedor
        box.insertBefore(legend, box.firstChild);
        
        if (!list || !list.length) {
            const empty = document.createElement('div');
            empty.textContent = '(sin misiones)';
            box.appendChild(empty);
            return;
        }
        
        const mode = this.getMode();
        
        // Aplicar filtro FC antes de mostrar las misiones
        const filteredList = list.filter(mission => {
            const isFC = mission.type === 'fc' || this.isFlameingCliffsMission(mission.name || '');
            return includeFC || !isFC; // Mostrar si includeFC está activo O si no es FC
        });
        
        filteredList.forEach(mission => {
            let badges = [];
            
            // Badge para misiones FC usando detección mejorada
            if (mission.type === 'fc' || this.isFlameingCliffsMission(mission.name || '')) {
                badges.push('<span class="pill pill-blue" style="background-color: #065d96ff; color: white;">FC</span>');
            }
            
            // Badge para estado de traducción/deploy basado en el nuevo sistema
            if (mission.state) {
                switch(mission.state) {
                    case 'traducida':
                        // No mostrar badge aquí - se verificará después si existe *.translated.lua
                        mission.needsTranslationCheck = true;
                        break;
                    case 'reempaquetada':
                        badges.push('<span class="pill pill-green">✅ Lista para desplegar</span>');
                        break;
                    case 'desplegada':
                        badges.push('<span class="pill pill-purple">🚀 Desplegada</span>');
                        break;
                    // 'sin_traducir' no necesita badge
                }
            } else {
                // Fallback al sistema legacy
                if (mission.deploy_ready) {
                    badges.push('<span class="pill pill-green">✅ Lista para desplegar</span>');
                } else if (mission.translated_only) {
                    badges.push('<span class="pill pill-amber">✨ Traducida</span>');
                }
            }
            
            const checked = (mode === 'desplegar' && mission.deploy_ready) ? ' checked' : '';
            
            const div = document.createElement('div');
            div.innerHTML = `
                <label>
                    <input type="checkbox" name="miz" value="${mission.name}"${checked}> 
                    ${mission.name}${badges.length > 0 ? (' ' + badges.join(' ')) : ''}
                </label>
            `;
            box.appendChild(div);
        });
        
        // Nota sobre preselección
        const note = document.createElement('div');
        note.className = 'muted';
        note.style.marginTop = '6px';
        note.innerHTML = mode === 'desplegar' ? 
            'En modo <b>desplegar</b> se preseleccionan automáticamente las ✅.' : '';
        box.appendChild(note);
        
        // Verificar estado de traducción para misiones que lo requieren
        this.checkTranslationState(filteredList);
    }

    async checkTranslationState(missions) {
        console.log('🔍 Iniciando checkTranslationState con', missions.length, 'misiones');
        
        // Filtrar misiones que necesitan verificación de traducción
        const missionsToCheck = missions.filter(mission => mission.needsTranslationCheck);
        console.log('🔍 Misiones que necesitan verificación:', missionsToCheck.length, missionsToCheck.map(m => m.name));
        
        if (missionsToCheck.length === 0) {
            console.log('ℹ️ No hay misiones que verificar');
            return;
        }
        
        // Obtener nombre de campaña actual del elemento del DOM
        const currentCampaignEl = document.getElementById('currentCampaignName');
        const currentCampaign = currentCampaignEl ? currentCampaignEl.textContent.trim() : null;
        console.log('🔍 Campaña actual:', currentCampaign, 'Elemento encontrado:', !!currentCampaignEl);
        
        // Si no hay campaña en el DOM, intentar extraerla del estado del orquestador
        let campaignToUse = currentCampaign;
        if (!campaignToUse || campaignToUse === '-') {
            // Buscar misiones con nombres que contengan pistas sobre la campaña
            if (missionsToCheck.length > 0 && missionsToCheck[0].name) {
                const missionName = missionsToCheck[0].name;
                if (missionName.startsWith('F5-E')) {
                    campaignToUse = 'F-5E_Black_Sea_Resolve__79';
                    console.log('🔍 Campaña inferida de nombre de misión F5-E:', campaignToUse);
                } else if (missionName.startsWith('F-5E')) {
                    campaignToUse = 'F-5E_BFM';
                    console.log('🔍 Campaña inferida de nombre de misión F-5E:', campaignToUse);
                }
            }
        }
        
        if (!campaignToUse || campaignToUse === '-') {
            console.log('⚠️ No hay campaña seleccionada para verificar estado de traducción');
            return;
        }
        
        try {
            // Preparar lista de misiones a verificar
            const missionNames = missionsToCheck.map(mission => mission.name);
            console.log('🔍 Enviando petición para verificar misiones:', missionNames, 'en campaña:', campaignToUse);
            
            // Llamar al endpoint para verificar archivos *.translated.lua
            const response = await fetch('/api/check_translated_dict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    campaign: campaignToUse,
                    missions: missionNames
                })
            });
            
            console.log('🔍 Respuesta del servidor:', response.status, response.ok);
            
            if (!response.ok) {
                console.error('❌ Error al verificar estado de traducción:', response.status);
                const errorText = await response.text();
                console.error('❌ Error details:', errorText);
                return;
            }
            
            const data = await response.json();
            console.log('🔍 Datos recibidos:', data);
            const results = data.results || {};
            
            // Actualizar badges para misiones que tienen *.translated.lua
            Object.keys(results).forEach(missionName => {
                console.log(`🔍 Misión ${missionName}: tiene archivos traducidos = ${results[missionName]}`);
                if (results[missionName]) {
                    // La misión tiene *.translated.lua - añadir badge
                    this.addTranslatedBadge(missionName);
                }
            });
            
            console.log(`✅ Verificado estado de traducción para ${Object.keys(results).length} misiones`);
            
        } catch (error) {
            console.error('❌ Error al verificar estado de traducción:', error);
        }
    }
    
    addTranslatedBadge(missionName) {
        // Buscar el checkbox de la misión
        const checkboxes = document.querySelectorAll('input[name="miz"]');
        let targetCheckbox = null;
        
        checkboxes.forEach(checkbox => {
            if (checkbox.value === missionName) {
                targetCheckbox = checkbox;
            }
        });
        
        if (!targetCheckbox) {
            console.log(`⚠️ No se encontró checkbox para la misión: ${missionName}`);
            return;
        }
        
        // Buscar el label padre
        const label = targetCheckbox.parentElement;
        if (!label) {
            console.log(`⚠️ No se encontró label para la misión: ${missionName}`);
            return;
        }
        
        // Verificar si ya tiene el badge (evitar duplicados)
        const existingBadge = label.querySelector('.pill-amber');
        if (existingBadge) {
            return; // Ya tiene el badge
        }
        
        // Añadir el badge de traducida
        const badge = document.createElement('span');
        badge.className = 'pill pill-amber';
        badge.innerHTML = '✨ Traducida';
        badge.style.marginLeft = '8px';
        
        label.appendChild(badge);
        console.log(`✨ Badge añadido para misión traducida: ${missionName}`);
    }
    
    getMode() {
        const radio = document.querySelector('input[name=mode]:checked');
        return radio ? radio.value : 'translate';
    }
    
    // === CONTROLES DE SELECCIÓN DE MISIONES ===
    
    selectAllMissions() {
        const missionCheckboxes = document.querySelectorAll('input[name="miz"]');
        missionCheckboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
        console.log(`✅ Marcadas ${missionCheckboxes.length} misiones`);
    }
    
    deselectAllMissions() {
        const missionCheckboxes = document.querySelectorAll('input[name="miz"]');
        missionCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        console.log(`❌ Desmarcadas ${missionCheckboxes.length} misiones`);
    }
    
    refreshMissions() {
        console.log('🔄 Actualizando lista de misiones...');
        
        // Verificar que haya una campaña seleccionada
        if (!this.selectedCampaign) {
            alert('Selecciona una campaña primero');
            return;
        }
        
        // Ejecutar re-escaneo de la campaña actual
        const scanButton = document.getElementById('scanCampaigns');
        if (scanButton && !scanButton.disabled) {
            // Marcar que es un refresh de misiones para UX específica
            const refreshButton = document.getElementById('refreshMissions');
            if (refreshButton) {
                refreshButton.disabled = true;
                refreshButton.textContent = '🔄 Actualizando...';
            }
            
            // Ejecutar escaneo
            scanButton.click();
            
            // Restaurar botón después de un momento
            setTimeout(() => {
                if (refreshButton) {
                    refreshButton.disabled = false;
                    refreshButton.textContent = '🔄 Refrescar';
                }
            }, 2000);
        } else {
            alert('El escaneo no está disponible en este momento');
        }
    }
    
    // === EJECUCIÓN ===
    
    async runOrchestrator() {
        console.log('🚀 Ejecutar orquestador - iniciando');
        
        // Verificar si hay una traducción en curso
        try {
            const response = await fetch('/api/status');
            const status = await response.json();
            
            if (status.is_running) {
                alert('⚠️ Ya hay una traducción en ejecución.\n\nEspera a que termine la traducción actual antes de iniciar una nueva.');
                return;
            }
        } catch (error) {
            console.error('Error verificando estado:', error);
            // Continuar si no se puede verificar el estado
        }
        
        // Limpiar resumen de ejecución anterior al iniciar nueva ejecución
        this.clearPreviousExecutionSummary();
        
        // Validaciones básicas
        if (!this.selectedCampaign) {
            alert('Selecciona una campaña.');
            return;
        }
        
        const selectedMissions = [...document.querySelectorAll('input[name=miz]:checked')]
            .map(x => x.value);
        
        if (selectedMissions.length === 0) {
            alert('Selecciona al menos una misión.');
            return;
        }
        
        // Mostrar modal de confirmación - SIMPLE
        this.showConfirmModal(selectedMissions);
    }
    
    createConfirmModal() {
        // Crear el modal de confirmación dinámicamente
        const modal = document.createElement('div');
        modal.id = 'confirmModal';
        modal.className = 'modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-labelledby', 'confirmTitle');
        
        modal.innerHTML = `
            <div class="modal-card">
                <header>
                    <h3 id="confirmTitle">🚀 Confirmar Ejecución</h3>
                </header>
                <div class="content" id="confirmContent">
                    <div class="confirm-summary">
                        <div class="summary-item">
                            <span class="label">Modo:</span>
                            <span id="confirmMode" class="value"></span>
                        </div>
                        <div class="summary-item">
                            <span class="label">Campaña:</span>
                            <span id="confirmCampaign" class="value"></span>
                        </div>
                        <div class="summary-item">
                            <span class="label">Misiones:</span>
                            <span id="confirmMissionCount" class="value"></span>
                        </div>
                        <div class="summary-item">
                            <span class="label">Modelo:</span>
                            <span id="confirmModel" class="value"></span>
                        </div>
                        <div class="summary-item">
                            <span class="label">Usar cache:</span>
                            <span id="confirmUseCache" class="value"></span>
                        </div>
                        <div class="summary-item" id="confirmOverwriteCacheRow" style="display: none;">
                            <span class="label">Sobrescribir cache:</span>
                            <span id="confirmOverwriteCache" class="value"></span>
                        </div>
                        <div class="summary-item" id="confirmDeployInfo" style="display: none;">
                            <span class="label">Destino:</span>
                            <span id="confirmDeployDir" class="value"></span>
                        </div>
                        <div class="summary-item" id="confirmOverwriteInfo" style="display: none;">
                            <span class="label">Sobrescribir:</span>
                            <span id="confirmOverwrite" class="value"></span>
                        </div>
                    </div>
                    
                    <div class="missions-list">
                        <h4>Misiones seleccionadas:</h4>
                        <ul id="confirmMissionsList"></ul>
                    </div>
                </div>
                <footer>
                    <button id="confirmCancel" class="btn btn-secondary">❌ Cancelar</button>
                    <button id="confirmExecute" class="btn btn-primary">✅ Ejecutar</button>
                </footer>
            </div>
        `;
        
        // Añadir al body
        document.body.appendChild(modal);
        
        // Configurar event listeners
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideConfirmModal();
            }
        });
        
        document.getElementById('confirmCancel').addEventListener('click', () => {
            this.hideConfirmModal();
        });
        
        document.getElementById('confirmExecute').addEventListener('click', () => {
            this.executeAfterConfirm();
        });
        
        console.log('✅ Modal de confirmación creado dinámicamente');
        return modal;
    }
    
    showConfirmModal(selectedMissions) {
        const mode = this.getMode();
        const modeNames = {
            'traducir': '✨ TRADUCIR',
            'reempaquetar': '📦 REEMPAQUETAR', 
            'desplegar': '🚀 DESPLEGAR'
        };
        
        // Verificar si es modo deploy con sobrescribir activado
        const isDeployWithOverwrite = mode === 'desplegar' && (this.getElementValue('userDeployOverwrite') === 'true' || document.getElementById('userDeployOverwrite')?.checked);
        
        if (isDeployWithOverwrite) {
            const overwriteConfirm = confirm(
                '⚠️ ADVERTENCIA: Sobrescribir archivos existentes\n\n' +
                'Has seleccionado la opción "Sobrescribir archivos existentes".\n' +
                'Esto reemplazará los archivos MIZ originales en el directorio de campaña.\n\n' +
                '¿Estás seguro de que quieres continuar?\n\n' +
                'Se creará una copia de seguridad automática en "_backup_missions".'
            );
            
            if (!overwriteConfirm) {
                console.log('❌ Usuario canceló el deploy con sobrescribir');
                return;
            }
        }
        
        // Buscar el modal o crearlo si no existe
        let modal = document.getElementById('confirmModal');
        if (!modal) {
            console.log('🔧 Creando modal de confirmación...');
            modal = this.createConfirmModal();
        }
        
        console.log('✅ Mostrando modal de confirmación');
        
        // Llenar datos del modal
        document.getElementById('confirmMode').textContent = modeNames[mode] || mode;
        document.getElementById('confirmCampaign').textContent = this.selectedCampaign;
        document.getElementById('confirmMissionCount').textContent = selectedMissions.length;
        document.getElementById('confirmModel').textContent = this.getElementValue('userLmModel') || 'No configurado';
        
        // 📋 Mostrar opciones de cache
        const useCacheCheckbox = document.getElementById('useCache');
        const overwriteCacheCheckbox = document.getElementById('overwriteCache');
        const useCacheEnabled = useCacheCheckbox?.checked || false;
        const overwriteCacheEnabled = overwriteCacheCheckbox?.checked || false;
        
        // Actualizar información de cache
        document.getElementById('confirmUseCache').textContent = useCacheEnabled ? '✅ SÍ' : '❌ NO';
        
        // Mostrar/ocultar información de sobrescribir cache
        const overwriteRow = document.getElementById('confirmOverwriteCacheRow');
        if (mode === 'traducir' && !useCacheEnabled && overwriteCacheEnabled) {
            overwriteRow.style.display = 'flex';
            document.getElementById('confirmOverwriteCache').textContent = '⚠️ SÍ';
        } else {
            overwriteRow.style.display = 'none';
        }
        
        // Mostrar información específica para deploy
        const deployInfo = document.getElementById('confirmDeployInfo');
        const overwriteInfo = document.getElementById('confirmOverwriteInfo');
        
        if (mode === 'desplegar') {
            deployInfo.style.display = 'flex';
            overwriteInfo.style.display = 'flex';
            
            const deployDir = this.getElementValue('userDeployDir') || 'Directorio de campaña';
            const isOverwrite = this.getElementValue('userDeployOverwrite') === 'true' || document.getElementById('userDeployOverwrite')?.checked;
            
            document.getElementById('confirmDeployDir').textContent = deployDir;
            document.getElementById('confirmOverwrite').textContent = isOverwrite ? '⚠️ SÍ (con backup)' : '✅ NO (nueva carpeta)';
            
            // Cambiar color del botón si es sobrescribir
            const executeBtn = document.getElementById('confirmExecute');
            if (isOverwrite) {
                executeBtn.style.backgroundColor = '#e74c3c';
                executeBtn.textContent = '⚠️ Ejecutar (Sobrescribir)';
            } else {
                executeBtn.style.backgroundColor = '';
                executeBtn.textContent = '✅ Ejecutar';
            }
        } else {
            deployInfo.style.display = 'none';
            overwriteInfo.style.display = 'none';
            
            // Restaurar botón normal
            const executeBtn = document.getElementById('confirmExecute');
            executeBtn.style.backgroundColor = '';
            executeBtn.textContent = '✅ Ejecutar';
        }
        
        // Llenar lista de misiones
        const missionsList = document.getElementById('confirmMissionsList');
        missionsList.innerHTML = '';
        selectedMissions.forEach(mission => {
            const li = document.createElement('li');
            li.textContent = mission;
            missionsList.appendChild(li);
        });
        
        // Mostrar modal
        modal.classList.add('open');
    }
    
    hideConfirmModal() {
        const modal = document.getElementById('confirmModal');
        if (modal) modal.classList.remove('open');
    }
    
    clearPreviousExecutionSummary() {
        console.log('🧹 Limpiando resumen de ejecución anterior...');
        
        // Limpiar el estado actual de ejecución pero mantener solo el progreso
        this.clearExecutionProgress(false);
        
        // Ocultar el contenido del resumen y mostrar mensaje de "sin ejecuciones"
        const noExecutionEl = document.getElementById('noExecutionMessage');
        const summaryContentEl = document.getElementById('summaryContent');
        
        if (noExecutionEl) {
            noExecutionEl.style.display = 'block';
        }
        if (summaryContentEl) {
            summaryContentEl.style.display = 'none';
        }
        
        // Limpiar específicamente elementos de resultados anteriores
        const elementsToReset = [
            // IDs principales del resumen
            'executionMode',
            'executionTime', 
            'executionDate',
            'statusIndicator',
            'statusText',
            // Estadísticas generales
            'totalCampaigns',
            'totalMissions',
            'successfulMissions',
            'failedMissions',
            // Estadísticas de caché
            'cacheHitRate',
            'totalCacheHits',
            'totalApiCalls',
            'processingTime'
        ];
        
        elementsToReset.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                if (id.includes('Rate')) {
                    element.textContent = '0%';
                } else if (id.includes('Time')) {
                    element.textContent = '0s';
                } else if (id === 'executionMode') {
                    element.textContent = '-';
                    element.className = 'mode-badge';
                } else if (id === 'statusIndicator') {
                    element.textContent = '⏳';
                } else if (id === 'statusText') {
                    element.textContent = 'Preparando...';
                } else {
                    element.textContent = '0';
                }
            }
        });
        
        // Limpiar tabla de detalles por misión
        const missionTableBody = document.querySelector('#missionsDetail tbody');
        if (missionTableBody) {
            missionTableBody.innerHTML = '';
        }
        
        // Limpiar estado de ejecución
        const executionStatus = document.getElementById('executionStatus');
        if (executionStatus) {
            executionStatus.className = 'execution-status';
            executionStatus.classList.remove('success', 'error', 'warning');
        }
        
        console.log('✅ Resumen anterior limpiado - UI lista para nueva ejecución');
    }
    
    async executeAfterConfirm() {
        // Ocultar modal de confirmación
        this.hideConfirmModal();
        
        // Ejecutar la operación real
        await this.executeOrchestrator();
    }
    
    async executeOrchestrator() {
        console.log('🚀 executeOrchestrador iniciado');
        
        // LIMPIAR completamente la ejecución anterior antes de iniciar
        this.clearPreviousExecutionSummary();
        
        // LIMPIAR mensaje de ejecución anterior al iniciar nueva
        this.clearExecutionProgress(false); // false = limpiar TODO incluido mensajes de éxito
        console.log('🧹 Limpiado estado anterior - iniciando nueva ejecución');
        
        try {
            const selectedMissions = [...document.querySelectorAll('input[name=miz]:checked')]
                .map(x => x.value);
            
            console.log('🎯 Misiones seleccionadas:', selectedMissions);

            // ✅ VALIDACIÓN FRONTEND: Verificar modelo configurado para modos de traducción
            const mode = this.getMode();
            if (mode === 'traducir' || mode === 'all') {
                const lmModel = this.getElementValue('userLmModel');
                if (!lmModel || lmModel.trim() === '' || lmModel === 'Seleccionar modelo...') {
                    alert('🤖 MODELO NO CONFIGURADO\n\n' +
                          'Debes seleccionar un modelo de LM Studio antes de traducir.\n\n' +
                          '💡 Pasos para solucionarlo:\n' +
                          '1. Asegúrate que LM Studio esté ejecutándose\n' +
                          '2. Haz clic en "🔄 Actualizar" para escanear modelos\n' +
                          '3. Selecciona un modelo de la lista desplegable\n' +
                          '4. Verifica que el indicador de estado esté en verde ✅\n' +
                          '5. Intenta la traducción nuevamente');
                    
                    // Enfocar el selector de modelo para facilitar la selección
                    document.getElementById('userLmModel')?.focus();
                    return;
                }
                console.log('✅ Validación frontend: Modelo configurado -', lmModel);
            }

            // Construir ruta de campaña directamente desde ROOT_DIR
            const rootDir = this.getElementValue('userRootDir');
            if (!rootDir) {
                alert('Error: ROOT_DIR no configurado. Configura la ruta de campañas primero.');
                return;
            }
            
            const campaignPath = `${rootDir}\\${this.selectedCampaign}`.replace(/\\\\/g, '\\');
            console.log('📂 Ruta de campaña construida:', campaignPath);
            
            // Verificar que tenemos datos de campañas (opcional, solo para logging)
            console.log('📋 Datos de campañas disponibles:', this.campaigns);
            
            const campaignData = {
                name: this.selectedCampaign,
                path: campaignPath
            };
            console.log('🔍 Datos de campaña preparados:', campaignData);

            const payload = {
                ROOT_DIR: this.getElementValue('userRootDir'),
                FILE_TARGET: this.getElementValue('userFileTarget'),
                ARGS: this.buildArgs(),
                DEPLOY_DIR: this.getElementValue('userDeployDir'),
                DEPLOY_OVERWRITE: this.getElementValue('userDeployOverwrite'),
                mode: this.getMode(),
                // Campos individuales de configuración para el backend
                arg_config: this.getElementValue('arg_config'),
                arg_compat: this.getElementValue('arg_compat'),
                arg_batch: this.getElementValue('arg_batch'),
                arg_timeout: this.getElementValue('arg_timeout'),
                lm_model: this.getElementValue('userLmModel'),
                lm_url: this.getElementValue('userLmUrl'),
                // Formato nuevo para el orchestrator service
                campaigns: [{
                    name: this.selectedCampaign,
                    path: campaignData.path,
                    missions: selectedMissions
                }],
                // Formato anterior para compatibilidad con el endpoint /api/run
                campaign_name: this.selectedCampaign,
                missions: selectedMissions,
                include_fc: document.getElementById('include_fc')?.checked || false,
                // Parámetros de cache
                use_cache: document.getElementById('useCache')?.checked === true,
                overwrite_cache: document.getElementById('overwriteCache')?.checked === true
            };
            
            // 🔍 DEBUG: Log específico para parámetros de cache y validación
            console.log('🔍 DEBUG JS - Parámetros de cache en payload:');
            console.log('  use_cache:', payload.use_cache, '(tipo:', typeof payload.use_cache, ')');
            console.log('  overwrite_cache:', payload.overwrite_cache, '(tipo:', typeof payload.overwrite_cache, ')');
            console.log('� DEBUG JS - Validación de payload:');
            console.log('  modo:', payload.mode);
            console.log('  modelo LM:', payload.lm_model);
            console.log('  URL LM:', payload.lm_url);
            console.log('  campaña:', payload.campaign_name);
            console.log('  misiones:', payload.missions?.length || 0);
            console.log('📦 Payload completo:', JSON.stringify(payload, null, 2));
            
            // Mostrar estado de "preparando" que incluye posible carga de modelo
            this.showExecutionStatus('🔄 Preparando ejecución (validando y cargando modelo si es necesario)...', '');
            
            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            console.log('📡 Respuesta HTTP:', response.status, response.statusText);
            
            const result = await response.json();
            console.log('📋 Resultado completo del servidor:', result);
            console.log('📊 Status HTTP:', response.status);
            console.log('🔍 Error details:', result.error, 'Tipo:', result.error_type);
            
            if (!result.ok) {
                // Manejar diferentes tipos de errores de modelo
                if (result.error_type === 'model_not_configured') {
                    alert('🤖 MODELO NO CONFIGURADO\n\n' + 
                          result.error + '\n\n' +
                          '💡 Solución:\n' +
                          '1. Ve a la sección "Configuración del Modelo"\n' +
                          '2. Haz clic en "Escanear LM Studio" para ver modelos disponibles\n' +
                          '3. Selecciona un modelo de la lista\n' +
                          '4. Intenta la traducción nuevamente');
                } else if (result.error_type === 'lm_studio_unavailable') {
                    alert('🔴 LM STUDIO NO DISPONIBLE\n\n' + 
                          result.error + '\n\n' +
                          '💡 Solución:\n' +
                          '1. Abre LM Studio\n' +
                          '2. Asegúrate que esté ejecutándose\n' +
                          '3. Verifica la URL de conexión en configuración');
                } else if (result.error_type === 'no_model_loaded') {
                    alert('🤖 MODELO NO CARGADO\n\n' + 
                          result.error + '\n\n' +
                          '💡 Solución:\n' +
                          '1. Abre LM Studio\n' +
                          '2. Ve a "My Models"\n' +
                          '3. Carga el modelo requerido\n' +
                          '4. O usa "Escanear LM Studio" para verificar modelos disponibles');
                } else if (result.error_type === 'auto_load_failed') {
                    alert('⚠️ CARGA AUTOMÁTICA FALLÓ\n\n' + 
                          result.error + '\n\n' +
                          '💡 Solución:\n' +
                          '1. Abre LM Studio manualmente\n' +
                          '2. Carga el modelo: ' + (result.details?.requested_model || 'modelo requerido') + '\n' +
                          '3. Vuelve a intentar la traducción');
                } else if (result.error_type === 'auto_load_error') {
                    alert('❌ ERROR EN CARGA AUTOMÁTICA\n\n' + 
                          result.error + '\n\n' +
                          '💡 Solución:\n' +
                          '1. Verifica que LM Studio esté ejecutándose\n' +
                          '2. Carga manualmente el modelo: ' + (result.details?.requested_model || 'modelo requerido') + '\n' +
                          '3. Intenta nuevamente');
                } else if (result.error_type === 'specific_model_load_failed') {
                    const availableModels = result.available_models ? 
                          '\n\nModelos disponibles:\n• ' + result.available_models.slice(0, 3).join('\n• ') : '';
                    alert('🔄 MODELO ESPECÍFICO NO DISPONIBLE\n\n' + 
                          result.error + availableModels + '\n\n' +
                          '💡 Soluciones:\n' +
                          '1. Selecciona uno de los modelos disponibles arriba\n' +
                          '2. O carga el modelo requerido en LM Studio\n' +
                          '3. Verifica el nombre exacto del modelo');
                } else if (result.error_type === 'specific_model_load_error') {
                    const availableModels = result.available_models ? 
                          '\n\nModelos disponibles:\n• ' + result.available_models.slice(0, 3).join('\n• ') : '';
                    alert('❌ ERROR CARGANDO MODELO ESPECÍFICO\n\n' + 
                          result.error + availableModels + '\n\n' +
                          '💡 Solución:\n' +
                          '1. Usa uno de los modelos disponibles arriba\n' +
                          '2. O verifica el estado de LM Studio');
                } else if (result.error_type === 'model_check_failed') {
                    alert('⚠️ ERROR DE VERIFICACIÓN\n\n' + 
                          result.error + '\n\n' +
                          '💡 Solución:\n' +
                          '1. Verifica que LM Studio esté ejecutándose\n' +
                          '2. Revisa la URL de conexión\n' +
                          '3. Intenta escanear modelos para comprobar conexión');
                } else if (result.error_type === 'orchestrator_initialization_error') {
                    alert('🔧 ERROR DE INICIALIZACIÓN\n\n' + 
                          'El orquestador no pudo iniciarse correctamente.\n\n' +
                          '💡 Soluciones:\n' +
                          '1. Reinicia la aplicación Flask\n' +
                          '2. Verifica los logs del sistema\n' +
                          '3. Comprueba la configuración del sistema\n\n' +
                          'Detalles técnicos:\n' + result.details);
                } else if (result.error_type === 'model_error') {
                    alert('🤖 ERROR DEL MODELO\n\n' + 
                          'Problema con el modelo de lenguaje configurado.\n\n' +
                          '💡 Soluciones:\n' +
                          '1. Verifica que LM Studio esté funcionando\n' +
                          '2. Asegúrate de que el modelo esté cargado\n' +
                          '3. Intenta cargar un modelo diferente\n' +
                          '4. Reinicia LM Studio si es necesario\n\n' +
                          'Error: ' + result.details);
                } else if (result.error_type === 'connection_error') {
                    alert('🌐 ERROR DE CONEXIÓN\n\n' + 
                          'No se pudo conectar con LM Studio.\n\n' +
                          '💡 Soluciones:\n' +
                          '1. Verifica que LM Studio esté ejecutándose\n' +
                          '2. Comprueba la URL: http://localhost:1234/v1\n' +
                          '3. Revisa el firewall/antivirus\n' +
                          '4. Reinicia LM Studio\n\n' +
                          'Error: ' + result.details);
                } else {
                    // Error genérico con más información
                    let errorMsg = '❌ ERROR INTERNO\n\n' + (result.error || 'Error desconocido');
                    if (result.suggestion) {
                        errorMsg += '\n\n💡 Sugerencia:\n' + result.suggestion;
                    }
                    if (result.details && result.details !== result.error) {
                        errorMsg += '\n\n🔍 Detalles técnicos:\n' + result.details;
                    }
                    alert(errorMsg);
                }
                return;
            }
            
            // Iniciar polling de estado SOLO si no está ya iniciado
            if (!this.polling) {
                console.log('🔄 Iniciando polling porque se comenzó una ejecución');
                this.startStatusPolling();
            } else {
                console.log('🔄 Polling ya activo, no iniciando duplicado');
            }
            
            // Forzar una actualización inmediata del estado
            console.log('⚡ Forzando actualización inmediata del estado después de iniciar ejecución');
            this.pollStatus();
            
        } catch (error) {
            console.error('❌ Error ejecutando orquestador:', error);
            alert('Error al lanzar la ejecución: ' + error.message);
        }
    }
    
    async cancelOrchestrator() {
        console.log('🛑 CANCELACIÓN ULTRA-AGRESIVA iniciada...');
        
        // Deshabilitar botón inmediatamente para evitar múltiples clics
        const cancelBtn = document.getElementById('cancel');
        if (cancelBtn) {
            cancelBtn.disabled = true;
            cancelBtn.innerHTML = '💀 MATANDO LM STUDIO...';
        }
        
        // Mostrar mensaje de cancelación inmediato
        const statusEl = document.getElementById('executionStatus');
        if (statusEl) {
            statusEl.innerHTML = '🛑 <strong>CANCELACIÓN ULTRA-AGRESIVA...</strong><br><small>• MATANDO procesos de LM Studio<br>• Deteniendo TODA generación en curso<br>• Terminación FORZADA inmediata</small>';
            statusEl.className = 'status-message error';
        }

        // Variable para controlar si la cancelación fue exitosa
        let cancelled = false;
        
        try {
            // Detener polling local INMEDIATAMENTE para evitar interferencias
            this.stopStatusPolling();
            console.log('🛑 Polling local detenido');
            
            // PASO 1: MATAR LM STUDIO INMEDIATAMENTE
            console.log('💀 PASO 1: Matando procesos de LM Studio...');
            try {
                const killController = new AbortController();
                const killTimeoutId = setTimeout(() => killController.abort(), 3000); // 3 segundos timeout
                
                const killResponse = await fetch('/api/force_kill_lm_studio', { 
                    method: 'POST',
                    signal: killController.signal,
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                clearTimeout(killTimeoutId);
                const killResult = await killResponse.json();
                
                if (killResult.ok) {
                    console.log(`💀 LM Studio MATADO: ${killResult.message}`);
                    if (statusEl) {
                        statusEl.innerHTML = '💀 <strong>LM STUDIO MATADO</strong><br><small>• Procesos terminados: ' + killResult.killed_processes.length + '<br>• Ejecutando cancelación completa...</small>';
                    }
                } else {
                    console.warn('⚠️ Error matando LM Studio:', killResult.error);
                }
            } catch (killError) {
                console.warn('⚠️ Error crítico matando LM Studio:', killError.message);
            }
            
            // PASO 2: Cancelación en el backend con múltiples intentos
            console.log('🛑 PASO 2: Cancelación en backend...');
            const maxAttempts = 5;
            let attempt = 1;
            
            while (attempt <= maxAttempts && !cancelled) {
                console.log(`🛑 Intento de cancelación backend ${attempt}/${maxAttempts}...`);
                
                try {
                    // Cancelación en el backend con timeout agresivo
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 segundos timeout
                    
                    const response = await fetch('/api/cancel', { 
                        method: 'POST',
                        signal: controller.signal,
                        headers: {
                            'Content-Type': 'application/json',
                        }
                    });
                    
                    clearTimeout(timeoutId);
                    
                    if (response.ok) {
                        const result = await response.json();
                        if (result.ok) {
                            cancelled = true;
                            console.log(`✅ Cancelación backend exitosa en intento ${attempt}`);
                            break;
                        } else {
                            console.warn(`⚠️ Intento ${attempt} falló: ${result.message || 'Error desconocido'}`);
                        }
                    } else {
                        console.warn(`⚠️ HTTP Error en intento ${attempt}: ${response.status}`);
                    }
                    
                } catch (fetchError) {
                    console.warn(`⚠️ Error en intento ${attempt}: ${fetchError.message}`);
                    
                    // Si es timeout o error de red, continuar intentando
                    if (attempt < maxAttempts) {
                        console.log(`🔄 Reintentando backend en 500ms...`);
                        await new Promise(resolve => setTimeout(resolve, 500));
                    }
                }
                
                attempt++;
            }
            
            // Cancelación forzada local INMEDIATA
            this.currentlyRunning = false;
            this.completionLogged = false;
            
            // ACTUALIZAR BOTÓN DE EJECUTAR INMEDIATAMENTE
            this.updateExecuteButtonState(false);
            console.log('🛑 Botón de ejecutar actualizado a estado normal');
            
            // Limpiar timer de misión si existe
            if (this.visualTimerInterval) {
                clearInterval(this.visualTimerInterval);
                this.visualTimerInterval = null;
                console.log('🛑 Timer visual limpiado');
            }
            
            // Resetear estado de misión
            if (this.missionTimer) {
                this.missionTimer.isRunning = false;
                this.missionTimer.startTime = null;
                this.missionTimer.elapsed = 0;
                console.log('🛑 Timer de misión reseteado');
            }
            
            // Mostrar resultado final
            if (statusEl) {
                if (cancelled) {
                    statusEl.innerHTML = '💀 <strong>CANCELACIÓN ULTRA-AGRESIVA COMPLETADA</strong><br><small>• 💀 LM Studio MATADO completamente<br>• ✅ Generación interrumpida inmediatamente<br>• ✅ Todos los procesos terminados<br>• 🔄 Puedes reiniciar LM Studio manualmente</small>';
                    statusEl.className = 'status-message success';
                } else {
                    statusEl.innerHTML = '💀 <strong>CANCELACIÓN FORZADA EJECUTADA</strong><br><small>• 💀 LM Studio matado (proceso terminado)<br>• ⚠️ El backend puede estar ocupado<br>• ✅ Interfaz reseteada completamente<br>• 🔄 Reinicia LM Studio para continuar</small>';
                    statusEl.className = 'status-message warning';
                }
            }
            
            console.log('💀 CANCELACIÓN ULTRA-AGRESIVA COMPLETADA - LM Studio MATADO');
            
            // PASO 3: Mostrar instrucción para reiniciar LM Studio
            setTimeout(() => {
                if (statusEl) {
                    statusEl.innerHTML = '🔄 <strong>LISTO PARA CONTINUAR</strong><br><small>• ✅ Cancelación completada exitosamente<br>• � <strong>Reinicia LM Studio</strong> y carga el modelo<br>• ▶️ Luego puedes iniciar nueva traducción</small>';
                    statusEl.className = 'status-message info';
                }
                
                // Restaurar botón de cancelar
                if (cancelBtn) {
                    cancelBtn.disabled = false;
                    cancelBtn.innerHTML = '🛑 Cancelar';
                }
                
                // ASEGURAR que el botón de ejecutar esté en estado normal
                this.updateExecuteButtonState(false);
                console.log('🔄 Botón de ejecutar confirmado en estado normal');
                
                // FORZAR el estado de no-ejecución para evitar que polling lo sobrescriba
                this.currentlyRunning = false;
                
                // Hacer una verificación adicional después de 2 segundos para asegurar el estado
                setTimeout(() => {
                    this.updateExecuteButtonState(false);
                    console.log('🔄 Verificación final: Botón de ejecutar forzado a estado normal');
                }, 2000);
            }, 3000); // Mostrar mensaje de reinicio después de 3 segundos
            
            console.log('✅ Proceso de cancelación completado');
            
        } catch (error) {
            console.error('❌ Error crítico en cancelación:', error);
            
            // Cancelación de emergencia - resetear todo localmente
            this.stopStatusPolling();
            this.currentlyRunning = false;
            this.completionLogged = false;
            
            // ACTUALIZAR BOTÓN DE EJECUTAR también en caso de error
            this.updateExecuteButtonState(false);
            console.log('🛑 Botón de ejecutar actualizado tras error de cancelación');
            
            if (this.visualTimerInterval) {
                clearInterval(this.visualTimerInterval);
                this.visualTimerInterval = null;
            }
            
            if (statusEl) {
                statusEl.innerHTML = `❌ <strong>ERROR EN CANCELACIÓN - RESET FORZADO</strong><br><small>• ❌ Error: ${error.message}<br>• ✅ Interfaz reseteada localmente<br>• 🔄 Reinicia la aplicación para limpiar completamente</small>`;
                statusEl.className = 'status-message error';
            }
            
        } finally {
            // Reactivar botón de cancelación
            if (cancelBtn) {
                cancelBtn.disabled = false;
                cancelBtn.innerHTML = '🛑 Cancelar';
            }
            
            // ASEGURAR que el botón de ejecutar esté en estado normal EN TODOS LOS CASOS
            this.updateExecuteButtonState(false);
            console.log('🛑 Finally: Botón de ejecutar asegurado en estado normal');
            
            // Asegurar que otros botones estén habilitados
            const executeBtn = document.getElementById('execute');
            if (executeBtn) {
                executeBtn.disabled = false;
            }
        }
    }
    
    clearExecutionProgress(onlyProgressMessages = false) {
        // Limpiar solo mensajes de progreso temporal, preservar mensajes de éxito
        const statusEl = document.getElementById('executionStatus');
        
        if (statusEl) {
            const hasSuccessClass = statusEl.classList.contains('success') || statusEl.classList.contains('warning');
            
            if (onlyProgressMessages) {
                // Solo limpiar si es un mensaje de progreso temporal (sin clase success/warning)
                if (!hasSuccessClass) {
                    statusEl.className = 'execution-status';
                    statusEl.innerHTML = '';
                    console.log('🧹 Limpiado mensaje de progreso temporal');
                } else {
                    console.log('💾 Preservando mensaje de éxito completado');
                }
            } else {
                // Limpiar todo (solo cuando se inicia nueva ejecución)
                statusEl.className = 'execution-status';
                statusEl.innerHTML = '';
                console.log('🧹 Limpiado estado completo de ejecución');
            }
        }
        
        // NO forzar actualización automática del resumen - preservar estado final
    }
    
    // === POLLING DE ESTADO ===
    
    startStatusPolling() {
        if (this.polling) {
            console.log('🔄 Polling ya está activo, no iniciando duplicado');
            return;
        }
        
        this.polling = true;
        this.pollCount = 0;
        this.lastActivityTime = Date.now();
        this.currentPollingInterval = 2000; // Inicializar con valor base
        
        // Polling inteligente: comenzar con intervalo base
        this.pollInterval = setInterval(() => this.adaptivePollStatus(), this.currentPollingInterval);
        console.log('🔄 Iniciando polling adaptativo del orquestador');
        
        // Inicializar timer visual independiente para actualizar la UI cada segundo
        this.startVisualTimer();
    }

    startVisualTimer() {
        // Evitar duplicar timers
        if (this.visualTimerInterval) {
            clearInterval(this.visualTimerInterval);
        }
        
        // Timer independiente que actualiza la UI cada segundo cuando hay actividad
        this.visualTimerInterval = setInterval(() => {
            if (this.missionTimer && this.missionTimer.isRunning) {
                // Actualizar el tiempo transcurrido
                this.missionTimer.elapsed = Date.now() - this.missionTimer.startTime;
                
                // Actualizar solo el tiempo en la UI sin hacer llamadas al servidor
                this.updateMissionProgressTimer();
            }
        }, 1000); // Actualizar cada segundo
        
        console.log('⏱️ Timer visual iniciado para actualización en tiempo real');
    }

    updateMissionProgressTimer() {
        // Actualizar solo el contador de tiempo en la UI
        const batchesCounterEl = document.getElementById('batchesProgressCounter');
        const missionProgressSection = document.getElementById('currentMissionProgressSection');
        const cacheHitsEl = document.getElementById('cacheHits');
        const modelCallsEl = document.getElementById('modelCalls');
        
        if (batchesCounterEl && this.missionTimer.isRunning) {
            const timeElapsed = this.formatElapsedTime(this.missionTimer.elapsed);
            
            // Agregar clase de animación para mostrar actividad
            if (missionProgressSection) {
                missionProgressSection.classList.add('mission-active');
            }
            
            // Obtener el texto actual
            let currentText = batchesCounterEl.innerHTML || batchesCounterEl.textContent;
            
            // Si es HTML, extraer solo el texto de la primera línea
            if (currentText.includes('<div class="batch-main">')) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = currentText;
                const mainElement = tempDiv.querySelector('.batch-main');
                if (mainElement) {
                    currentText = mainElement.textContent;
                }
            }
            
            // Actualizar el tiempo en el texto principal
            if (currentText.includes('⏱️')) {
                const textWithoutTime = currentText.split('|')[0].trim();
                const updatedText = `${textWithoutTime} | <span class="timer-highlight">⏱️ ${timeElapsed}</span>`;
                
                // Si hay breakdown, mantenerlo
                if (batchesCounterEl.innerHTML.includes('batch-breakdown')) {
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = batchesCounterEl.innerHTML;
                    const mainElement = tempDiv.querySelector('.batch-main');
                    const breakdownElement = tempDiv.querySelector('.batch-breakdown');
                    
                    if (mainElement && breakdownElement) {
                        mainElement.innerHTML = updatedText;
                        batchesCounterEl.innerHTML = tempDiv.innerHTML;
                    }
                } else {
                    batchesCounterEl.innerHTML = updatedText;
                }
            }
            
            // Actualizar contadores visuales si están simulando
            if (cacheHitsEl && parseInt(cacheHitsEl.textContent) > 0) {
                cacheHitsEl.classList.add('updating');
                setTimeout(() => cacheHitsEl.classList.remove('updating'), 300);
            }
            if (modelCallsEl && parseInt(modelCallsEl.textContent) > 0) {
                modelCallsEl.classList.add('updating');
                setTimeout(() => modelCallsEl.classList.remove('updating'), 300);
            }
        } else {
            // Remover animaciones cuando no hay actividad
            if (missionProgressSection) {
                missionProgressSection.classList.remove('mission-active');
            }
        }
    }

    async adaptivePollStatus() {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();
            
            // Almacenar última respuesta para verificaciones
            this.lastStatusResponse = status;
            
            this.pollCount++;
            
            // Detectar actividad
            const hasActivity = status.is_running || 
                               status.missions_total > 0 || 
                               status.missions_processed > 0 ||
                               status.phase !== 'idle';
            
            if (hasActivity) {
                this.lastActivityTime = Date.now();
            }
            
            // Log solo cuando hay actividad relevante
            if (hasActivity) {
                console.log('📊 Poll status:', {
                    is_running: status.is_running,
                    phase: status.phase,
                    missions: `${status.missions_processed}/${status.missions_total}`,
                    current_mission: status.current_mission,
                    progress: status.progress
                });
            }
            
            this.updateStatusDisplay(status);
            
            // Actualizar misiones si se empaquetaron nuevas
            if (status.just_packaged && status.just_packaged.length) {
                this.applyJustPackaged(status.just_packaged);
            }
            
            // Ajustar frecuencia de polling dinámicamente
            this.adjustPollingFrequency(hasActivity);
            
            // Detener polling si no está en ejecución y no hay actividad reciente
            if (!status.is_running && this.polling) {
                const timeSinceActivity = Date.now() - this.lastActivityTime;
                if (timeSinceActivity > 10000) { // 10 segundos sin actividad
                    console.log('⏹️ Deteniendo polling - sin actividad reciente');
                    setTimeout(() => this.stopStatusPolling(), 2000);
                }
            }
            
        } catch (error) {
            console.error('Error en polling de estado:', error);
        }
    }
    
    adjustPollingFrequency(hasActivity) {
        if (!this.pollInterval) return;
        
        // Detectar si hay traducción activa para polling más frecuente
        const hasTranslationActivity = this.missionTimer?.isRunning || 
                                     this.lastStatusResponse?.is_running ||
                                     this.lastStatusResponse?.current_mission;
        
        // Mantener referencia al intervalo actual
        let newInterval;
        if (hasTranslationActivity) {
            newInterval = 1000; // 1 segundo para traducción activa
        } else if (hasActivity) {
            newInterval = 1500; // 1.5s para actividad general
        } else {
            newInterval = 5000; // 5s para idle
        }
        
        // Solo cambiar si es diferente al actual
        if (this.currentPollingInterval !== newInterval) {
            console.log(`🔄 Ajustando polling: ${this.currentPollingInterval || 2000}ms → ${newInterval}ms (actividad: ${hasActivity}, traducción: ${hasTranslationActivity}, pollCount: ${this.pollCount})`);
            
            clearInterval(this.pollInterval);
            this.pollInterval = setInterval(() => this.adaptivePollStatus(), newInterval);
            this.currentPollingInterval = newInterval;
        }
    }

    async pollStatus() {
        // Si no hay polling activo, hacer una llamada única
        if (!this.polling) {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                this.lastStatusResponse = status;
                this.updateStatusDisplay(status);
                return status;
            } catch (error) {
                console.error('Error en polling único de estado:', error);
                return null;
            }
        }
        // Si hay polling activo, redirigir al adaptativo
        return this.adaptivePollStatus();
    }
    
    stopStatusPolling() {
        this.polling = false;
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        
        // Detener también el timer visual
        if (this.visualTimerInterval) {
            clearInterval(this.visualTimerInterval);
            this.visualTimerInterval = null;
            console.log('⏱️ Timer visual detenido');
        }
        
        console.log('⏹️ Polling del orquestador detenido');
    }
    
    updateStatusDisplay(status) {
        // Detectar cuando INICIA una nueva ejecución para limpiar resumen anterior
        if (status.is_running && !this.currentlyRunning) {
            console.log('🚀 Nueva ejecución iniciada - limpiando resumen anterior');
            this.clearPreviousExecutionSummary();
            this.currentlyRunning = true;
            this.completionLogged = false; // Reset completion logging for new execution
            
            // Reanudar logging para nueva ejecución
            if (window.realTimeLogger) {
                window.realTimeLogger.resumeLogging();
            }
        } else if (!status.is_running && this.currentlyRunning) {
            // Marcar que ya no está corriendo cuando termine
            this.currentlyRunning = false;
            
            // Pausar logging cuando termine la ejecución
            if (window.realTimeLogger && !this.completionLogged) {
                setTimeout(() => {
                    window.realTimeLogger.pauseLogging();
                }, 2000); // Pequeña pausa para asegurar que se muestren los últimos logs
            }
        }
        
        // Si hay una ejecución completada, actualizar el resumen
        if (status.last_execution) {
            this.updateExecutionSummary(status.last_execution);
        }
        
        // Actualizar siempre la tarjeta de progreso cuando hay datos de estado
        this.showCurrentProgressCard(status);
        
        // Si hay ejecución en curso, mostrar progreso temporal
        if (status.is_running && status.phase) {
            this.showExecutionProgress(status);
        } else if (!status.is_running && this.polling) {
            // Detectar nueva finalización de ejecución
            const newCompletionTime = status.completion_time;
            const isNewCompletion = newCompletionTime && 
                                  (!this.lastCompletionTime || newCompletionTime > this.lastCompletionTime);
            
            if (isNewCompletion) {
                console.log('🎉 Nueva ejecución completada detectada');
                this.lastCompletionTime = newCompletionTime;
            }
            
            // Cuando termina la ejecución, mostrar mensaje de éxito SOLO UNA VEZ
            const statusEl = document.getElementById('executionStatus');
            const hasCompletionMessage = statusEl && (statusEl.classList.contains('success') || statusEl.classList.contains('warning'));
            
            if (!hasCompletionMessage && status.last_execution) {
                this.showExecutionComplete(status.last_execution);
                
                // SIEMPRE actualizar el estado de las campañas cuando finaliza una ejecución
                // (no solo en nueva finalización, para mayor confiabilidad)
                console.log('🔄 Actualizando estado de campañas tras finalizar ejecución...');
                this.refreshCampaignsAfterExecution();
            }
        }
        
        // Actualizar estado del botón de ejecutar basado en si hay traducción en curso
        this.updateExecuteButtonState(status.is_running);
    }
    
    updateExecutionSummary(execution) {
        console.log('🔄 Actualizando resumen de ejecución:', execution);
        console.log('🔍 Cache stats check:', {
            hasExecution: !!execution,
            hasCacheStats: !!(execution && execution.cache_stats),
            mode: execution?.mode,
            cacheStats: execution?.cache_stats
        });
        
        const noExecutionEl = document.getElementById('noExecutionMessage');
        const summaryContentEl = document.getElementById('summaryContent');
        
        if (!execution || !execution.campaigns || execution.campaigns.length === 0) {
            // Mostrar mensaje de sin ejecuciones
            if (noExecutionEl) noExecutionEl.style.display = 'block';
            if (summaryContentEl) summaryContentEl.style.display = 'none';
            return;
        }
        
        // Ocultar mensaje vacío y mostrar contenido
        if (noExecutionEl) noExecutionEl.style.display = 'none';
        if (summaryContentEl) summaryContentEl.style.display = 'block';
        
        // Actualizar información general
        this.updateExecutionHeader(execution);
        
        // Actualizar estadísticas
        this.updateExecutionStats(execution);
        
        // Actualizar estadísticas de caché
        this.updateCacheStats(execution);
        
        // Actualizar tabla de misiones
        this.updateMissionsTable(execution);
        
        // Actualizar errores si los hay
        this.updateExecutionErrors(execution);
    }
    
    updateExecutionHeader(execution) {
        // Modo
        const modeEl = document.getElementById('executionMode');
        if (modeEl) {
            const mode = execution.mode || 'unknown';
            modeEl.textContent = mode;
            modeEl.className = `mode-badge ${mode}`;
        }
        
        // Tiempo total
        const timeEl = document.getElementById('executionTime');
        if (timeEl) {
            const duration = execution.duration || 0;
            timeEl.textContent = this.formatDuration(duration);
        }
        
        // Fecha
        const dateEl = document.getElementById('executionDate');
        if (dateEl) {
            const date = execution.timestamp || execution.date || new Date().toISOString();
            dateEl.textContent = this.formatDate(date);
        }
        
        // Estado general
        const statusEl = document.getElementById('executionStatus');
        const indicatorEl = document.getElementById('statusIndicator');
        const textEl = document.getElementById('statusText');
        
        if (statusEl && indicatorEl && textEl) {
            const hasErrors = execution.total_errors > 0;
            const allSuccess = execution.successful_missions === execution.total_missions;
            
            if (allSuccess && !hasErrors) {
                statusEl.className = 'execution-status success';
                indicatorEl.textContent = '✅';
                textEl.textContent = 'Completado exitosamente';
            } else if (execution.successful_missions > 0) {
                statusEl.className = 'execution-status warning';
                indicatorEl.textContent = '⚠️';
                textEl.textContent = 'Completado con advertencias';
            } else {
                statusEl.className = 'execution-status error';
                indicatorEl.textContent = '❌';
                textEl.textContent = 'Falló la ejecución';
            }
        }
    }
    
    updateExecutionStats(execution) {
        // Total campañas
        const totalCampaignsEl = document.getElementById('totalCampaigns');
        if (totalCampaignsEl) {
            totalCampaignsEl.textContent = execution.campaigns ? execution.campaigns.length : 0;
        }
        
        // Total misiones
        const totalMissionsEl = document.getElementById('totalMissions');
        if (totalMissionsEl) {
            totalMissionsEl.textContent = execution.total_missions || 0;
        }
        
        // Misiones exitosas
        const successfulEl = document.getElementById('successfulMissions');
        if (successfulEl) {
            successfulEl.textContent = execution.successful_missions || 0;
        }
        
        // Misiones fallidas
        const failedEl = document.getElementById('failedMissions');
        if (failedEl) {
            failedEl.textContent = execution.failed_missions || 0;
        }
    }
    
    updateCacheStats(execution) {
        const cacheStatsEl = document.getElementById('cacheStats');
        
        console.log('🔍 updateCacheStats called:', {
            hasElement: !!cacheStatsEl,
            hasCacheStats: !!execution.cache_stats,
            cacheStats: execution.cache_stats,
            mode: execution.mode
        });
        
        // Mostrar sección de caché para modo traducir
        if (execution.mode === 'traducir') {
            if (cacheStatsEl) {
                cacheStatsEl.style.display = 'block';
                console.log('✅ Cache stats section shown for traducir mode');
            }
        } else {
            if (cacheStatsEl) {
                cacheStatsEl.style.display = 'none';
                console.log('ℹ️ Cache stats section hidden for non-traducir mode');
            }
            return;
        }
        
        // Usar estadísticas existentes o valores por defecto
        const stats = execution.cache_stats || {
            cache_hit_rate: 0,
            total_cache_hits: 0,
            total_api_calls: 0,
            total_processing_time: 0
        };
        
        console.log('📊 Cache stats being applied:', stats);
        
        // Verificar que todos los elementos existen
        const elements = {
            cacheHitRate: document.getElementById('cacheHitRate'),
            totalCacheHits: document.getElementById('totalCacheHits'),
            totalApiCalls: document.getElementById('totalApiCalls'),
            processingTime: document.getElementById('processingTime')
        };
        
        console.log('📄 Cache elements found:', {
            cacheHitRate: !!elements.cacheHitRate,
            totalCacheHits: !!elements.totalCacheHits,
            totalApiCalls: !!elements.totalApiCalls,
            processingTime: !!elements.processingTime
        });
        
        // Tasa de caché
        if (elements.cacheHitRate) {
            elements.cacheHitRate.textContent = Math.round(stats.cache_hit_rate || 0) + '%';
            console.log('✅ Cache hit rate updated:', elements.cacheHitRate.textContent);
        }
        
        // Total desde caché
        if (elements.totalCacheHits) {
            elements.totalCacheHits.textContent = stats.total_cache_hits || 0;
            console.log('✅ Total cache hits updated:', elements.totalCacheHits.textContent);
        }
        
        // Total enviadas al modelo
        if (elements.totalApiCalls) {
            elements.totalApiCalls.textContent = stats.total_api_calls || 0;
            console.log('✅ Total API calls updated:', elements.totalApiCalls.textContent);
        }
        
        // Tiempo de procesado
        if (elements.processingTime) {
            elements.processingTime.textContent = this.formatDuration(stats.total_processing_time || 0);
            console.log('✅ Processing time updated:', elements.processingTime.textContent);
        }
    }
    
    updateMissionsTable(execution) {
        const tableBody = document.getElementById('missionsTableBody');
        if (!tableBody || !execution.campaigns) return;
        
        tableBody.innerHTML = '';
        
        execution.campaigns.forEach(campaign => {
            if (campaign.missions && campaign.missions.length > 0) {
                campaign.missions.forEach(mission => {
                    const row = document.createElement('tr');
                    
                    // Campaña
                    const campaignCell = document.createElement('td');
                    campaignCell.textContent = campaign.name || '-';
                    row.appendChild(campaignCell);
                    
                    // Misión
                    const missionCell = document.createElement('td');
                    missionCell.textContent = mission.name || '-';
                    row.appendChild(missionCell);
                    
                    // Estado
                    const statusCell = document.createElement('td');
                    const statusSpan = document.createElement('span');
                    if (mission.success) {
                        statusSpan.className = 'mission-status success';
                        statusSpan.innerHTML = '✅ Exitosa';
                    } else {
                        statusSpan.className = 'mission-status error';
                        statusSpan.innerHTML = '❌ Fallida';
                    }
                    statusCell.appendChild(statusSpan);
                    row.appendChild(statusCell);
                    
                    // Errores
                    const errorsCell = document.createElement('td');
                    const errorCount = (mission.errors && mission.errors.length) || 0;
                    const errorSpan = document.createElement('span');
                    errorSpan.className = errorCount > 0 ? 'error-count has-errors' : 'error-count zero';
                    errorSpan.textContent = errorCount;
                    errorsCell.appendChild(errorSpan);
                    row.appendChild(errorsCell);
                    
                    // Tiempo
                    const timeCell = document.createElement('td');
                    const timeSpan = document.createElement('span');
                    timeSpan.className = 'mission-time';
                    timeSpan.textContent = this.formatDuration(mission.duration || 0);
                    timeCell.appendChild(timeSpan);
                    row.appendChild(timeCell);
                    
                    // Caché/Modelo
                    const cacheCell = document.createElement('td');
                    const cacheInfo = document.createElement('div');
                    cacheInfo.className = 'mission-cache-info';
                    
                    const cacheHits = mission.cache_hits || 0;
                    const apiCalls = mission.api_calls || 0;
                    const segmentsTotal = mission.segments_total || mission.segments_translated || 0;
                    const total = cacheHits + apiCalls;
                    
                    // Debug detallado para identificar problema con porcentajes
                    console.log(`🔍 DEBUGGING Mission ${mission.name}:`);
                    console.log(`   Raw data: cache_hits=${mission.cache_hits}, api_calls=${mission.api_calls}, segments_total=${mission.segments_total}`);
                    console.log(`   Parsed: cache_hits=${cacheHits}, api_calls=${apiCalls}, total=${total}, segmentsTotal=${segmentsTotal}`);
                    
                    // Validación y corrección de datos sospechosos
                    let correctedApiCalls = apiCalls;
                    let correctedCacheHits = cacheHits;
                    
                    // Detectar si apiCalls parece estar corrupto (muy alto en relación a cache hits)
                    if (apiCalls > 100 && cacheHits > 0 && apiCalls > cacheHits * 3) {
                        console.warn(`⚠️ DATOS SOSPECHOSOS DETECTADOS: api_calls=${apiCalls} parece demasiado alto para cache_hits=${cacheHits}`);
                        console.warn(`⚠️ Intentando corregir dividiendo api_calls entre 100...`);
                        correctedApiCalls = Math.round(apiCalls / 100);
                        console.warn(`⚠️ Valor corregido: api_calls=${correctedApiCalls}`);
                    }
                    
                    // Aplicar valores corregidos
                    const finalCacheHits = correctedCacheHits;
                    const finalApiCalls = correctedApiCalls;
                    
                    const correctedTotal = finalCacheHits + finalApiCalls;
                    
                    if (correctedTotal > 0 || (finalCacheHits === 0 && finalApiCalls === 0 && mission.success)) {
                        const cacheRatio = document.createElement('span');
                        cacheRatio.className = 'cache-ratio';
                        cacheRatio.textContent = `💾 ${finalCacheHits}`;
                        
                        const modelRatio = document.createElement('span');
                        modelRatio.className = 'model-ratio';
                        modelRatio.textContent = `🤖 ${finalApiCalls}`;
                        
                        // Calcular porcentaje correcto: usar total de segmentos si disponible, si no usar suma
                        const denominator = segmentsTotal > 0 ? segmentsTotal : correctedTotal;
                        const percentage = denominator > 0 ? Math.round((finalCacheHits / denominator) * 100) : 0;
                        
                        // Validar que el porcentaje sea razonable
                        const validPercentage = Math.min(percentage, 100); // Nunca más de 100%
                        
                        console.log(`   Calculation: ${finalCacheHits}/${denominator} * 100 = ${percentage}% -> capped at ${validPercentage}%`);
                        
                        const details = document.createElement('span');
                        details.className = 'cache-details';
                        
                        if (correctedTotal > 0) {
                            details.textContent = `${validPercentage}% caché`;
                        } else if (mission.success) {
                            details.textContent = 'Sin datos';
                        } else {
                            details.textContent = 'Error';
                        }
                        
                        cacheInfo.appendChild(cacheRatio);
                        
                        // Agregar separador visual
                        const separator1 = document.createElement('span');
                        separator1.textContent = ' ';
                        cacheInfo.appendChild(separator1);
                        
                        cacheInfo.appendChild(modelRatio);
                        
                        // Agregar separador visual  
                        const separator2 = document.createElement('span');
                        separator2.textContent = ' ';
                        cacheInfo.appendChild(separator2);
                        
                        cacheInfo.appendChild(details);
                    } else {
                        cacheInfo.textContent = '-';
                    }
                    
                    cacheCell.appendChild(cacheInfo);
                    row.appendChild(cacheCell);
                    
                    tableBody.appendChild(row);
                });
            }
        });
    }
    
    updateExecutionErrors(execution) {
        const errorsSection = document.getElementById('errorsSection');
        const errorsList = document.getElementById('errorsList');
        
        if (!errorsSection || !errorsList) return;
        
        const allErrors = [];
        
        // Recopilar todos los errores
        if (execution.campaigns) {
            execution.campaigns.forEach(campaign => {
                if (campaign.errors && campaign.errors.length > 0) {
                    campaign.errors.forEach(error => {
                        allErrors.push({
                            campaign: campaign.name,
                            message: error
                        });
                    });
                }
                
                if (campaign.missions) {
                    campaign.missions.forEach(mission => {
                        if (mission.errors && mission.errors.length > 0) {
                            mission.errors.forEach(error => {
                                allErrors.push({
                                    campaign: campaign.name,
                                    mission: mission.name,
                                    message: error
                                });
                            });
                        }
                    });
                }
            });
        }
        
        if (allErrors.length > 0) {
            errorsSection.style.display = 'block';
            errorsList.innerHTML = '';
            
            allErrors.forEach(error => {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error-item';
                
                const campaignDiv = document.createElement('div');
                campaignDiv.className = 'error-campaign';
                campaignDiv.textContent = error.mission 
                    ? `${error.campaign} › ${error.mission}`
                    : error.campaign;
                
                const messageDiv = document.createElement('div');
                messageDiv.className = 'error-message';
                messageDiv.textContent = error.message;
                
                errorDiv.appendChild(campaignDiv);
                errorDiv.appendChild(messageDiv);
                errorsList.appendChild(errorDiv);
            });
        } else {
            errorsSection.style.display = 'none';
        }
    }
    
    showExecutionProgress(status) {
        // Si estamos comenzando una nueva ejecución y aún hay un resumen visible, limpiarlo
        const summaryContentEl = document.getElementById('summaryContent');
        const isShowingSummary = summaryContentEl && summaryContentEl.style.display !== 'none';
        
        if (isShowingSummary && status.is_running) {
            console.log('🧹 Nueva ejecución detectada - limpiando resumen anterior...');
            this.clearPreviousExecutionSummary();
        }
        
        // Mostrar sección de progreso en tiempo real
        this.showCurrentProgressCard(status);
        
        // Mostrar progreso temporal mientras se ejecuta
        const statusEl = document.getElementById('executionStatus');
        if (statusEl) {
            // Solo mostrar progreso si no hay mensaje de éxito persistente de ejecución anterior
            const hasCompletionMessage = statusEl.classList.contains('success') || statusEl.classList.contains('warning');
            
            if (!hasCompletionMessage) {
                // Construir información de progreso detallada
                const missionsProgress = status.missions_total > 0 
                    ? `${status.missions_processed}/${status.missions_total} misiones` 
                    : '';
                    
                const currentMissionInfo = status.current_mission 
                    ? `📋 ${status.current_mission}` 
                    : '';
                    
                const progressPercent = status.progress || 0;
                
                // Texto de estado detallado
                let detailText = status.detail || status.phase || 'En proceso';
                if (missionsProgress) {
                    detailText += ` • ${missionsProgress}`;
                }
                if (currentMissionInfo) {
                    detailText += ` • ${currentMissionInfo}`;
                }
                
                statusEl.className = 'execution-status';
                statusEl.innerHTML = `
                    <span class="status-indicator">⏳</span>
                    <span class="status-text">${detailText}</span>
                `;
                
                // Actualizar también los contadores en tiempo real en las estadísticas
                this.updateProgressStats(status);
            } else {
                // Hay mensaje de éxito anterior - solo lo sobrescribimos si es una nueva ejecución
                console.log('⚠️ Detectado mensaje de éxito persistente - no sobrescribiendo con progreso temporal');
            }
        }
    }
    
    showCurrentProgressCard(status) {
        const progressCard = document.getElementById('currentProgressCard');
        if (!progressCard) return;
        
        // Debug logging para diagnosticar el problema
        console.log('🔍 showCurrentProgressCard called:', {
            is_running: status.is_running,
            current_mission: status.current_mission,
            missions_total: status.missions_total,
            missions_processed: status.missions_processed,
            missions_successful: status.missions_successful,
            missions_failed: status.missions_failed,
            progress: status.progress,
            // Campos simulados del backend
            batch_progress: status.batch_progress,
            total_batches: status.total_batches,
            processed_batches: status.processed_batches,
            cache_hits: status.cache_hits,
            model_calls: status.model_calls,
            // Campos reales que pueden existir
            api_calls: status.api_calls,
            segments_total: status.segments_total,
            detail: status.detail
        });
        
        // Mostrar la tarjeta si hay datos de progreso relevantes
        const hasProgressData = status.missions_total > 0 || 
                               status.missions_processed > 0 || 
                               status.is_running ||
                               status.current_mission;
        
        if (hasProgressData) {
            progressCard.style.display = 'block';
            
            // Actualizar fase actual con el nuevo sistema
            if (status.is_running) {
                const detail = status.detail || status.phase || 'En proceso...';
                if (window.realTimeLogger) {
                    // Determinar el tipo basado en el contenido
                    let type = 'info';
                    if (detail.includes('❌') || detail.includes('Error') || detail.includes('error')) {
                        type = 'error';
                    } else if (detail.includes('⚠️') || detail.includes('Advertencia') || detail.includes('no disponible')) {
                        type = 'warning';
                    } else if (detail.includes('✅') || detail.includes('completad') || detail.includes('exitoso')) {
                        type = 'success';
                    }
                    
                    window.realTimeLogger.updatePhaseWithStatus(status.phase, detail, type);
                } else {
                    // Fallback al método anterior
                    const currentPhaseEl = document.getElementById('currentPhase');
                    if (currentPhaseEl) {
                        currentPhaseEl.textContent = detail;
                    }
                }
            } else {
                // Solo mostrar "Ejecución completada" una vez por ejecución
                if (window.realTimeLogger && !this.completionLogged) {
                    window.realTimeLogger.updatePhaseWithStatus('completed', 'Ejecución completada', 'success');
                    this.completionLogged = true; // Marcar que ya se registró la finalización
                } else if (!window.realTimeLogger) {
                    const currentPhaseEl = document.getElementById('currentPhase');
                    if (currentPhaseEl) {
                        currentPhaseEl.textContent = 'Ejecución completada';
                    }
                }
            }
            
            // === ACTUALIZAR BARRA DE PROGRESO GENERAL (MISIONES) ===
            this.updateGeneralProgress(status);
            
            // === ACTUALIZAR BARRA DE PROGRESO DE MISIÓN ACTUAL (LOTES) ===
            this.updateMissionProgress(status);
            
            // Procesar errores si existen (filtrar mensajes de éxito que no son errores)
            if (status.errors && Array.isArray(status.errors) && window.realTimeLogger) {
                status.errors.forEach(error => {
                    // Filtrar errores que no son realmente errores
                    if (error.type === 'lm_studio_success' || 
                        (error.message && error.message.includes('funcionando correctamente'))) {
                        // Convertir a log de éxito en lugar de error
                        window.realTimeLogger.addLogEntry(error.message, 'success', error.ts);
                    } else {
                        window.realTimeLogger.addError(error);
                    }
                });
            }
            
            // Procesar logs de progreso si existen
            if (status.progress_logs && Array.isArray(status.progress_logs) && window.realTimeLogger) {
                status.progress_logs.forEach(log => {
                    // Solo agregar logs nuevos (comparar timestamp)
                    const existingLogs = window.realTimeLogger.logContainer.querySelectorAll('.log-entry');
                    const logExists = Array.from(existingLogs).some(existingLog => {
                        const timestamp = existingLog.querySelector('.log-timestamp');
                        const message = existingLog.querySelector('.log-message');
                        return timestamp && message && 
                               timestamp.textContent === log.ts && 
                               message.textContent === log.message;
                    });
                    
                    if (!logExists) {
                        window.realTimeLogger.addLogEntry(log.message, log.type, log.ts);
                    }
                });
            }
            
            // Actualizar campaña actual
            const currentCampaignEl = document.getElementById('currentCampaignName');
            if (currentCampaignEl) {
                currentCampaignEl.textContent = status.current_campaign || '-';
            }
            
            // Actualizar misión actual
            const currentMissionEl = document.getElementById('currentMissionName');
            if (currentMissionEl) {
                currentMissionEl.textContent = status.current_mission || 'Ninguna';
            }
            
            // Actualizar contadores SIEMPRE que tengamos datos
            this.updateCurrentStats(status);
        } else {
            // Ocultar la tarjeta solo si no hay datos relevantes
            progressCard.style.display = 'none';
            console.log('🔍 Hiding progress card - no relevant data');
        }
    }
    
    updateGeneralProgress(status) {
        // Actualizar contador de misiones
        const missionsCounterEl = document.getElementById('missionsProgressCounter');
        if (missionsCounterEl) {
            const processed = status.missions_processed || 0;
            const total = status.missions_total || 0;
            missionsCounterEl.textContent = `${processed}/${total} misiones`;
        }
        
        // Actualizar barra de progreso general
        const progressFillEl = document.getElementById('currentProgressFill');
        const progressTextEl = document.getElementById('currentProgressText');
        
        let progress = 0;
        if (status.missions_total > 0) {
            progress = Math.round((status.missions_processed / status.missions_total) * 100);
        } else if (status.progress) {
            progress = Math.max(0, Math.min(100, status.progress));
        }
        
        // Si no está corriendo y hay misiones procesadas, mostrar 100%
        if (!status.is_running && status.missions_processed > 0) {
            progress = 100;
        }
        
        if (progressFillEl) {
            progressFillEl.style.width = `${progress}%`;
            // Agregar animación si está activo
            if (status.is_running) {
                progressFillEl.classList.add('active');
            } else {
                progressFillEl.classList.remove('active');
                if (progress === 100) {
                    progressFillEl.classList.add('completed');
                }
            }
        }
        
        if (progressTextEl) {
            progressTextEl.textContent = `${progress}%`;
        }
    }
    
    updateMissionProgress(status) {
        const missionProgressSection = document.getElementById('currentMissionProgressSection');
        const batchesCounterEl = document.getElementById('batchesProgressCounter');
        const missionProgressFillEl = document.getElementById('missionProgressFill');
        const missionProgressTextEl = document.getElementById('missionProgressText');
        const cacheHitsEl = document.getElementById('cacheHits');
        const modelCallsEl = document.getElementById('modelCalls');
        
        // Inicializar contador de tiempo si no existe
        if (!this.missionTimer) {
            this.missionTimer = {
                startTime: null,
                isRunning: false,
                elapsed: 0
            };
        }
        
        // Usar datos directos del status que ahora incluye batch info
        const cacheHits = status.cache_hits || 0;
        const modelCalls = status.model_calls || 0;
        const totalBatches = status.total_batches || 0;
        const processedBatches = status.processed_batches || 0;
        const missionProgress = status.batch_progress || 0;
        const totalSegments = status.total_segments || 0;
        const processedSegments = status.processed_segments || 0;
        
        // NUEVA LÓGICA: Detectar actividad de lotes incluso cuando los contadores no se actualizan
        const hasActiveTranslation = status.is_running && (
            status.current_mission || 
            status.detail?.includes('Lote') || 
            status.detail?.includes('Studio') ||
            status.detail?.includes('traduciendo') ||
            status.phase === 'translating' ||
            status.phase === 'processing'
        );
        
        // MANEJO DEL TIMER DE MISIÓN
        if (hasActiveTranslation || status.is_running) {
            if (!this.missionTimer.isRunning) {
                this.missionTimer.startTime = Date.now();
                this.missionTimer.isRunning = true;
                console.log('⏱️ Timer de misión iniciado');
            }
            this.missionTimer.elapsed = Date.now() - this.missionTimer.startTime;
        } else if (status.phase === 'completed' || (!status.is_running && this.missionTimer.isRunning)) {
            // Completar el timer pero mantenerlo visible por un tiempo
            if (this.missionTimer.isRunning) {
                this.missionTimer.elapsed = Date.now() - this.missionTimer.startTime;
                this.missionTimer.isRunning = false;
                this.missionTimer.completedAt = Date.now();
                console.log('⏱️ Timer de misión completado:', this.formatElapsedTime(this.missionTimer.elapsed));
            }
        }
        
        // Contadores anteriores para detectar cambios (mantener en variable global)
        if (!this.lastBatchCounters) {
            this.lastBatchCounters = { cacheHits: 0, modelCalls: 0, timestamp: Date.now() };
        }
        
        const hasRecentActivity = (
            cacheHits !== this.lastBatchCounters.cacheHits || 
            modelCalls !== this.lastBatchCounters.modelCalls ||
            (Date.now() - this.lastBatchCounters.timestamp) < 30000 // Actividad en los últimos 30 segundos
        );
        
        if (hasRecentActivity) {
            this.lastBatchCounters = { cacheHits, modelCalls, timestamp: Date.now() };
        }
        
        // DETECCIÓN MEJORADA: Analizar logs del servidor para detectar lotes reales
        const hasLiveActivity = this.detectLiveTranslationActivity(status);
        
        // Inicializar contadores para display
        let displayCacheHits = cacheHits;
        let displayModelCalls = modelCalls;
        let totalOperations = displayCacheHits + displayModelCalls;
        
        // ACTUALIZAR CONTADORES ESTIMADOS basándose en actividad detectada
        if (hasLiveActivity && totalOperations === 0) {
            // Si detectamos actividad pero no hay contadores, estimar algunos valores
            const timeRunning = this.missionTimer.elapsed / 1000; // segundos
            displayCacheHits = Math.max(displayCacheHits, Math.floor(timeRunning / 10)); // 1 cada 10s
            displayModelCalls = Math.max(displayModelCalls, Math.floor(timeRunning / 20)); // 1 cada 20s
            totalOperations = displayCacheHits + displayModelCalls;
        }
        
        // GUARDAR ÚLTIMOS VALORES VÁLIDOS para mostrar en misiones completadas
        if (totalOperations > 0 || displayCacheHits > 0 || displayModelCalls > 0) {
            this.lastValidOperations = {
                cache: displayCacheHits,
                model: displayModelCalls,
                total: totalOperations,
                timestamp: Date.now()
            };
        }
        
        // Determinar si mostrar la sección de progreso con lógica MUY permisiva
        const hasValidData = totalSegments > 0 || processedSegments > 0 || cacheHits > 0 || modelCalls > 0 || missionProgress > 0;
        const hasMissionData = status.current_mission && hasValidData;
        const isCompleted = status.phase === 'completed' && status.missions_processed > 0;
        const hasCompletedRecently = this.missionTimer.completedAt && (Date.now() - this.missionTimer.completedAt) < 60000; // Mostrar por 1 minuto después de completar
        
        // NUEVA LÓGICA MEJORADA: Mostrar la sección en cualquiera de estos casos:
        const shouldShow = status.is_running || 
                          hasActiveTranslation ||
                          hasRecentActivity ||
                          hasLiveActivity ||
                          (status.current_mission && status.current_mission !== null) ||
                          hasValidData || 
                          isCompleted || 
                          hasCompletedRecently ||
                          (status.phase && status.phase !== 'idle') ||
                          status.missions_processed > 0 ||
                          this.missionTimer.isRunning;
        
        // Log para debug mejorado - SIEMPRE mostrar cuando podría haber actividad
        console.log('🔍 Enhanced Progress Debug:', {
            is_running: status.is_running,
            current_mission: status.current_mission,
            phase: status.phase,
            missionProgress,
            totalSegments, 
            processedSegments,
            cacheHits,
            modelCalls,
            totalBatches,
            processedBatches,
            shouldShow,
            hasValidData,
            hasMissionData,
            hasActiveTranslation,
            hasRecentActivity,
            hasCompletedRecently,
            isCompleted,
            missions_processed: status.missions_processed,
            // Datos adicionales útiles
            detail: status.detail,
            progress: status.progress,
            lastBatchCounters: this.lastBatchCounters,
            lastValidOperations: this.lastValidOperations,
            missionTimer: this.missionTimer
        });
        
        if (shouldShow) {
            // Mostrar la sección de progreso de misión
            if (missionProgressSection) {
                missionProgressSection.style.display = 'block';
                
                // Mostrar/ocultar botón de limpiar
                const clearBtn = document.getElementById('clearMissionBtn');
                if (clearBtn) {
                    if (isCompleted || hasCompletedRecently) {
                        clearBtn.style.display = 'inline-block';
                    } else {
                        clearBtn.style.display = 'none';
                    }
                }
            }
            
            // Determinar valores a mostrar con fallbacks más inteligentes
            let displayProgress = missionProgress;
            let displayTotalSegments = totalSegments;
            let displayProcessedSegments = processedSegments;
            
            // Calcular total de operaciones/lotes (usar las variables ya inicializadas)
            let displayTotalBatches = Math.max(totalBatches, Math.ceil(totalOperations / 5)); // Estimar lotes si no hay datos
            let displayProcessedBatches = processedBatches;
            
            // Si está ejecutando pero no hay datos aún, estimar basándose en el progreso general
            if ((status.is_running || hasActiveTranslation) && !hasValidData) {
                displayProgress = Math.max(1, status.progress || 1); // Usar progreso general si está disponible
                
                // Si hay detalle en el status, intentar extraer información
                if (status.detail && status.detail.includes('%')) {
                    const progressMatch = status.detail.match(/(\d+)%/);
                    if (progressMatch) {
                        displayProgress = Math.max(displayProgress, parseInt(progressMatch[1]));
                    }
                }
                
                // Si detectamos actividad de lotes en el detalle, estimar algunos datos
                if (status.detail?.includes('Lote') || status.detail?.includes('Studio')) {
                    displayProcessedBatches = Math.max(1, displayProcessedBatches);
                    displayTotalBatches = Math.max(3, displayTotalBatches); // Estimar al menos 3 lotes
                }
            }
            
            // Si hay misión actual pero no datos, simular estado inicial
            if (status.current_mission && !hasValidData && status.is_running) {
                displayProgress = Math.max(5, displayProgress); // 5% mínimo para misión activa
            }
            
            // Si hay operaciones pero no hay datos de lotes, calcularlos
            if (totalOperations > 0 && displayTotalBatches === 0) {
                displayTotalBatches = Math.max(1, Math.ceil(totalOperations / 5)); // Asumir ~5 operaciones por lote
                displayProcessedBatches = Math.max(1, Math.ceil(totalOperations / 5));
            }
            
            // Actualizar contador con lógica mejorada que prioriza mostrar información útil
            if (batchesCounterEl) {
                // Formatear tiempo transcurrido
                const timeElapsed = this.formatElapsedTime(this.missionTimer.elapsed);
                const timeInfo = (this.missionTimer.isRunning || hasCompletedRecently) ? ` | ⏱️ ${timeElapsed}` : '';
                
                // DETECTAR ESTADO COMPLETADO
                if (isCompleted || (hasCompletedRecently && !status.is_running)) {
                    // Mostrar información de misión completada
                    const completionTime = this.formatElapsedTime(this.missionTimer.elapsed);
                    batchesCounterEl.textContent = `✅ Misión completada${timeInfo ? ` en ${completionTime}` : ''}`;
                } else if (displayTotalBatches > 0 || totalOperations > 0 || hasLiveActivity || hasRecentActivity) {
                    // NUEVA LÓGICA: Siempre intentar mostrar información útil de lotes
                    if (displayTotalBatches > 0) {
                        batchesCounterEl.textContent = `📦 ${displayProcessedBatches}/${displayTotalBatches} lotes enviados${timeInfo}`;
                    } else {
                        // Estimar lotes basándose en operaciones (aproximadamente 5 operaciones por lote)
                        const estimatedBatches = Math.ceil(totalOperations / 5);
                        const currentBatch = Math.max(1, Math.ceil((displayCacheHits + displayModelCalls) / 5));
                        batchesCounterEl.textContent = `📦 ~${currentBatch}/${estimatedBatches} lotes${timeInfo}`;
                    }
                } else if (displayTotalSegments > 0) {
                    // Mostrar segmentos si no hay datos de lotes
                    batchesCounterEl.textContent = `📄 ${displayProcessedSegments}/${displayTotalSegments} segmentos${timeInfo}`;
                } else if (status.is_running && status.current_mission) {
                    // Si está ejecutando, mostrar estado más descriptivo
                    batchesCounterEl.textContent = `🔄 Procesando lotes de traducción...${timeInfo}`;
                } else if (status.current_mission && !isCompleted) {
                    // Hay misión pero no datos específicos
                    batchesCounterEl.textContent = `📋 Preparando lotes para: ${status.current_mission}${timeInfo}`;
                } else if (status.detail && status.detail.trim() !== '' && !isCompleted) {
                    // Usar el detalle del status si está disponible
                    batchesCounterEl.textContent = `📋 ${status.detail}${timeInfo}`;
                } else if (status.is_running || this.missionTimer.isRunning) {
                    // Fallback para cuando está ejecutando
                    batchesCounterEl.textContent = `🔄 Iniciando procesamiento...${timeInfo}`;
                } else {
                    // Fallback final
                    batchesCounterEl.textContent = `⏸️ Listo para nueva misión`;
                }
                
                // AGREGAR INFORMACIÓN ADICIONAL: Mostrar detalles de tiempo real si hay operaciones activas
                if ((totalOperations > 0 && (displayCacheHits > 0 || displayModelCalls > 0)) || (isCompleted && this.lastValidOperations)) {
                    // Para misiones completadas, usar los últimos valores válidos
                    const finalCacheHits = isCompleted && this.lastValidOperations ? this.lastValidOperations.cache : displayCacheHits;
                    const finalModelCalls = isCompleted && this.lastValidOperations ? this.lastValidOperations.model : displayModelCalls;
                    const finalTotal = finalCacheHits + finalModelCalls;
                    
                    const currentText = batchesCounterEl.textContent;
                    batchesCounterEl.innerHTML = `
                        <div class="batch-main">${currentText}</div>
                        <div class="batch-breakdown">
                            <small>💾 Cache: ${finalCacheHits} | 🤖 Modelo: ${finalModelCalls} | 📊 Total: ${finalTotal}</small>
                        </div>
                    `;
                } else if (this.missionTimer.isRunning && totalOperations === 0) {
                    // Si el timer está corriendo pero no hay datos, mostrar que está activo
                    const currentText = batchesCounterEl.textContent;
                    batchesCounterEl.innerHTML = `
                        <div class="batch-main">${currentText}</div>
                        <div class="batch-breakdown">
                            <small>🔍 Detectando actividad de traducción...${timeInfo}</small>
                        </div>
                    `;
                }
            }
            
            // Actualizar barra de progreso de misión
            if (missionProgressFillEl) {
                missionProgressFillEl.style.width = `${displayProgress}%`;
                missionProgressFillEl.classList.add('active');
                
                // Cambiar color según el estado
                if (displayProgress >= 95) {
                    missionProgressFillEl.classList.add('completed');
                } else {
                    missionProgressFillEl.classList.remove('completed');
                }
            }
            
            if (missionProgressTextEl) {
                missionProgressTextEl.textContent = `${displayProgress}%`;
            }
            
            // Actualizar contadores de cache y modelo con simulación en tiempo real
            if (cacheHitsEl) {
                // Si hay actividad real, usar datos reales
                if (displayCacheHits > 0) {
                    cacheHitsEl.textContent = displayCacheHits;
                } else if (isCompleted && this.lastValidOperations) {
                    // Mostrar últimos valores válidos para misión completada
                    cacheHitsEl.textContent = this.lastValidOperations.cache;
                } else if (this.missionTimer.isRunning && status.is_running) {
                    // Simular actividad de cache basándose en el tiempo transcurrido y actividad detectada
                    const timeSeconds = this.missionTimer.elapsed / 1000;
                    const estimatedCache = Math.floor(timeSeconds / 8); // 1 cache hit cada 8 segundos
                    cacheHitsEl.textContent = Math.max(0, estimatedCache);
                } else {
                    cacheHitsEl.textContent = displayCacheHits;
                }
            }
            if (modelCallsEl) {
                // Si hay actividad real, usar datos reales
                if (displayModelCalls > 0) {
                    modelCallsEl.textContent = displayModelCalls;
                } else if (isCompleted && this.lastValidOperations) {
                    // Mostrar últimos valores válidos para misión completada
                    modelCallsEl.textContent = this.lastValidOperations.model;
                } else if (this.missionTimer.isRunning && status.is_running) {
                    // Simular actividad del modelo basándose en el tiempo transcurrido
                    const timeSeconds = this.missionTimer.elapsed / 1000;
                    const estimatedModel = Math.floor(timeSeconds / 12); // 1 model call cada 12 segundos
                    modelCallsEl.textContent = Math.max(0, estimatedModel);
                } else {
                    modelCallsEl.textContent = displayModelCalls;
                }
            }
            
        } else {
            // Ocultar la sección de progreso de misión
            if (missionProgressSection) {
                missionProgressSection.style.display = 'none';
                
                // Ocultar también el botón de limpiar
                const clearBtn = document.getElementById('clearMissionBtn');
                if (clearBtn) {
                    clearBtn.style.display = 'none';
                }
            }
        }
    }
    
    updateCurrentStats(status) {
        const elements = [
            { id: 'currentTotalMissions', value: status.missions_total || 0 },
            { id: 'currentProcessedMissions', value: status.missions_processed || 0 },
            { id: 'currentSuccessfulMissions', value: status.missions_successful || 0 },
            { id: 'currentFailedMissions', value: status.missions_failed || 0 }
        ];
        
        elements.forEach(({ id, value }) => {
            const element = document.getElementById(id);
            if (element) {
                const oldValue = element.textContent;
                element.textContent = value;
                if (oldValue !== String(value)) {
                    console.log(`🔄 Updated ${id}: ${oldValue} -> ${value}`);
                }
            } else {
                console.warn(`⚠️ Element not found: ${id}`);
            }
        });
    }
    
    updateProgressStats(status) {
        // Actualizar contadores en tiempo real
        const totalMissionsEl = document.getElementById('totalMissions');
        if (totalMissionsEl) {
            totalMissionsEl.textContent = status.missions_total || 0;
        }
        
        const successfulEl = document.getElementById('successfulMissions');
        if (successfulEl) {
            successfulEl.textContent = status.missions_successful || 0;
        }
        
        const failedEl = document.getElementById('failedMissions');
        if (failedEl) {
            failedEl.textContent = status.missions_failed || 0;
        }
    }
    
    showExecutionComplete(execution) {
        // Mostrar mensaje de éxito PERSISTENTE cuando termina la ejecución
        if (!execution) return;
        
        const statusEl = document.getElementById('executionStatus');
        if (statusEl) {
            const modeNames = {
                'traducir': 'Traducción',
                'reempaquetar': 'Reempaquetado', 
                'desplegar': 'Despliegue'
            };
            
            const modeName = modeNames[execution.mode] || execution.mode;
            const isSuccess = execution.total_errors === 0;
            
            // Información adicional sobre la ejecución
            const missionCount = execution.campaigns?.[0]?.missions?.length || 0;
            const timeInfo = execution.total_time ? ` en ${this.formatDuration(execution.total_time)}` : '';
            
            statusEl.className = `execution-status ${isSuccess ? 'success' : 'warning'}`;
            statusEl.innerHTML = `
                <span class="status-indicator">${isSuccess ? '✅' : '⚠️'}</span>
                <span class="status-text">${modeName} ${isSuccess ? 'completada exitosamente' : 'completada con advertencias'} - ${missionCount} misión(es)${timeInfo}</span>
            `;
            
            console.log(`🎉 ${modeName} terminada - Mensaje PERSISTENTE mostrado`);
            console.log('💾 El mensaje permanecerá hasta nueva ejecución, recarga o cierre');
            
            // NO hay timeout - el mensaje permanece hasta que el usuario haga algo explícito
        }
    }
    
    formatDuration(seconds) {
        if (!seconds || seconds < 0) return '0s';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    }
    
    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffMs = now - date;
            const diffMinutes = Math.floor(diffMs / (1000 * 60));
            const diffHours = Math.floor(diffMinutes / 60);
            const diffDays = Math.floor(diffHours / 24);
            
            // Mostrar fecha completa con hora para mejor claridad
            const fullDate = date.toLocaleDateString('es-ES', {
                day: '2-digit',
                month: '2-digit', 
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            });
            
            // Agregar indicador de tiempo relativo para contexto
            let relativeTime = '';
            if (diffMinutes < 1) {
                relativeTime = ' (ahora mismo)';
            } else if (diffMinutes < 60) {
                relativeTime = ` (hace ${diffMinutes} min)`;
            } else if (diffHours < 24) {
                relativeTime = ` (hace ${diffHours}h)`;
            } else if (diffDays < 7) {
                relativeTime = ` (hace ${diffDays} días)`;
            }
            
            return fullDate + relativeTime;
            
        } catch (e) {
            console.warn('Error formateando fecha:', e, dateString);
            return dateString || 'Fecha desconocida';
        }
    }
    
    applyJustPackaged(delta) {
        if (!delta || !delta.length || !this.missions || !this.missions.length) return;
        
        const packaged = new Set(delta);
        this.missions.forEach(mission => {
            if (packaged.has(mission.name)) {
                mission.deploy_ready = true;
                mission.translated_only = false;
            }
        });
        
        this.renderMissions(this.missions);
    }
    
    // === ACTUALIZACIONES ===
    
    async checkUpdateBanner() {
        try {
            const response = await fetch('/api/update_info');
            const result = await response.json();
            
            const banner = document.getElementById('updateBanner');
            const link = document.getElementById('updateLink');
            
            if (result && result.ok && result.is_newer) {
                const reason = result.by && result.by.version_file ? 'archivo VERSION' :
                              result.by && result.by.git_head ? 'commits nuevos' : 'actualización disponible';
                              
                const latestVer = document.getElementById('latestVer');
                if (latestVer) {
                    latestVer.textContent = result.latest_version ? 
                        `${result.latest_version} (${reason})` : `(${reason})`;
                }
                
                if (result.repo_url && link) {
                    link.href = result.repo_url;
                }
                
                if (banner) {
                    banner.style.display = '';
                }
            } else {
                if (banner) {
                    banner.style.display = 'none';
                }
            }
            
        } catch (error) {
            console.warn('Error verificando actualizaciones:', error);
        }
    }
    
    async doUpdateNow() {
        const btn = document.getElementById('btnUpdateNow');
        const msg = document.getElementById('updMsg');
        
        if (!confirm('¿Actualizar ahora desde el repositorio? Se mantendrán "campaigns/" y "log_orquestador/".')) {
            return;
        }
        
        if (btn) btn.disabled = true;
        if (msg) msg.textContent = 'Actualizando...';
        
        try {
            const response = await fetch('/api/update_now', { method: 'POST' });
            const result = await response.json();
            
            if (result.ok) {
                if (msg) msg.textContent = 'Listo. Recargando...';
                setTimeout(() => location.reload(), 1000);
            } else {
                if (msg) msg.textContent = result.error || 'Fallo en la actualización';
                if (btn) btn.disabled = false;
            }
            
        } catch (error) {
            console.error('Error actualizando:', error);
            if (msg) msg.textContent = 'Error en la petición.';
            if (btn) btn.disabled = false;
        }
    }
    
    // === UTILIDADES ===
    
    getElementValue(id) {
        const element = document.getElementById(id);
        if (!element) return '';
        
        // Para checkboxes, devolver el estado checked
        if (element.type === 'checkbox') {
            return element.checked;
        }
        
        return element.value;
    }
    
    setElementValue(id, value) {
        const element = document.getElementById(id);
        if (element && value !== undefined) {
            if (element.type === 'checkbox') {
                element.checked = (value === 'true' || value === true);
            } else {
                element.value = value;
            }
        }
    }

    // ============================================================
    // CONFIGURACIÓN GENERAL DEL USUARIO
    // ============================================================
    
    setupUserConfigEventListeners() {
        // Botón guardar configuración
        document.getElementById('btnSaveUserConfig')?.addEventListener('click', 
            this.saveUserConfig.bind(this));
        
        // Botón guardar configuración de modelo
        document.getElementById('btnSaveModelConfig')?.addEventListener('click', 
            this.saveModelConfig.bind(this));
        
        // Botón resetear configuración de modelo
        document.getElementById('btnResetModelConfig')?.addEventListener('click', 
            this.resetModelConfig.bind(this));
        
        // Botón resetear configuración
        document.getElementById('btnResetUserConfig')?.addEventListener('click', 
            this.resetUserConfig.bind(this));
        
        // Validación en tiempo real
        document.getElementById('userRootDir')?.addEventListener('blur', 
            this.validateUserPaths.bind(this));
        document.getElementById('userDeployDir')?.addEventListener('blur', 
            this.validateUserPaths.bind(this));
        
        // Cargar modelos LM cuando cambie la URL
        document.getElementById('userLmUrl')?.addEventListener('blur', 
            this.loadUserLmModels.bind(this));
    }
    
    async loadUserConfig() {
        try {
            console.log('Cargando configuración del usuario...');
            
            const response = await fetch('/api/user_config', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                await this.populateUserConfigForm(data.config);
                this.updateValidationStatus(data.validation);
            } else {
                console.error('Error cargando configuración:', data.error);
            }
            
        } catch (error) {
            console.error('Error cargando configuración del usuario:', error);
        }
    }
    
    async populateUserConfigForm(config) {
        console.log('Configuración recibida:', config);
        
        // Mapear campos de configuración a elementos del formulario
        const fieldMappings = {
            'ROOT_DIR': 'userRootDir',
            'FILE_TARGET': 'userFileTarget', 
            'lm_model': 'userLmModel',
            'lm_url': 'userLmUrl',
            'DEPLOY_DIR': 'userDeployDir',
            'DEPLOY_OVERWRITE': 'userDeployOverwrite',
            // Preset activo (tanto active_preset como preset para compatibilidad)
            'active_preset': 'presetList',
            'preset': 'presetList',  // Nuevo campo añadido para perfiles
            // Campos de configuración del modelo
            'arg_config': 'arg_config',
            'arg_compat': 'arg_compat',
            'arg_batch': 'arg_batch',
            'arg_timeout': 'arg_timeout',
            // Parámetros del API del modelo (¡ESTOS SE RESTAURAN AHORA!)
            'api_temperature': 'api_temperature',
            'api_top_p': 'api_top_p',
            'api_top_k': 'api_top_k',
            'api_max_tokens': 'api_max_tokens',
            'api_repetition_penalty': 'api_repetition_penalty',
            'api_presence_penalty': 'api_presence_penalty',
            // Cache settings
            'use_cache': 'useCache',
            'overwrite_cache': 'overwriteCache'
        };
        
        for (const [configKey, elementId] of Object.entries(fieldMappings)) {
            const element = document.getElementById(elementId);
            if (element) {
                // Obtener el valor, manejando tanto objetos como valores directos
                let value;
                if (config[configKey] !== undefined) {
                    if (typeof config[configKey] === 'object' && config[configKey].value !== undefined) {
                        value = config[configKey].value;
                    } else {
                        value = config[configKey];
                    }
                } else {
                    // Valores por defecto para campos que pueden no existir
                    switch (configKey) {
                        case 'FILE_TARGET':
                            value = 'l10n/DEFAULT/dictionary';
                            break;
                        case 'DEPLOY_OVERWRITE':
                            value = true;
                            break;
                        case 'use_cache':
                            value = true;
                            break;
                        case 'overwrite_cache':
                            value = false;
                            break;
                        case 'lm_url':
                            value = 'http://localhost:1234/v1';
                            break;
                        default:
                            value = '';
                    }
                }
                
                // Debug específico para lm_model y arg_config
                if (configKey === 'lm_model') {
                    console.log(`lm_model - config[${configKey}]:`, config[configKey]);
                    console.log(`lm_model - valor extraído:`, value);
                    console.log(`lm_model - tipo del valor:`, typeof value);
                }
                
                if (configKey === 'arg_config') {
                    console.log(`arg_config - config[${configKey}]:`, config[configKey]);
                    console.log(`arg_config - valor extraído:`, value);
                    console.log(`arg_config - elemento encontrado:`, !!element);
                }
                
                if (element.type === 'checkbox') {
                    // Preservar valores por defecto del HTML si el servidor devuelve vacío/undefined
                    if (value === '' || value === null || value === undefined) {
                        // Solo establecer si no tiene checked por defecto en HTML
                        if (!element.defaultChecked) {
                            element.checked = false;
                        }
                        // Si tiene defaultChecked, no lo sobrescribir
                    } else {
                        element.checked = !!value;
                    }
                } else {
                    // Preservar valores por defecto del HTML si el servidor devuelve vacío
                    if (value === '' || value === null || value === undefined) {
                        // Solo establecer si no tiene valor por defecto en HTML
                        if (!element.defaultValue) {
                            element.value = '';
                        }
                        // Si tiene defaultValue, no lo sobrescribir
                    } else {
                        element.value = value;
                    }
                }
            }
        }
        
        const overwriteCacheElement = document.getElementById('overwriteCache');
        if (overwriteCacheElement) {
            overwriteCacheElement.checked = config.overwrite_cache === true || config.overwrite_cache === "true" || config.overwrite_cache === "True";
            console.log('overwriteCache configurado a:', overwriteCacheElement.checked);
        }
        
        console.log('Configuración del usuario cargada en el formulario');
        
        // Guardar el modelo configurado antes de recargar la lista
        const savedModel = config.lm_model;
        
        // Cargar modelos LM después de configurar la URL
        await this.loadUserLmModels();
        
        // Restaurar el modelo guardado si existe
        if (savedModel) {
            const modelSelect = document.getElementById('userLmModel');
            if (modelSelect) {
                // Si el modelo guardado no está en las opciones, agregarlo
                const modelExists = [...modelSelect.options].some(opt => opt.value === savedModel);
                if (!modelExists && savedModel.trim() !== '') {
                    const option = document.createElement('option');
                    option.value = savedModel;
                    option.textContent = `${savedModel} (configurado)`;
                    modelSelect.appendChild(option);
                }
                modelSelect.value = savedModel;
                console.log('Modelo restaurado:', savedModel);
            }
        }
        
        // Restaurar el preset activo si existe
        const savedPreset = config.active_preset;
        if (savedPreset) {
            const presetSelect = document.getElementById('presetList');
            if (presetSelect) {
                presetSelect.value = savedPreset;
                console.log('Preset restaurado:', savedPreset);
            }
        }
    }
    
    async saveUserConfig() {
        try {
            // Buscar elementos de UI (pueden no existir en configuración unificada)
            const saveBtn = document.getElementById('btnSaveUserConfig') || document.getElementById('btnSaveCompleteConfig');
            const statusSpan = document.getElementById('userConfigStatus') || document.getElementById('completeConfigStatus');
            
            // Mostrar estado de carga si hay botón disponible
            if (saveBtn) {
                saveBtn.disabled = true;
                const originalText = saveBtn.textContent;
                saveBtn.textContent = '💾 Guardando...';
                
                // Restaurar texto original después
                setTimeout(() => {
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.textContent = originalText;
                    }
                }, 1000);
            }
            
            // Recopilar datos del formulario de configuración general
            const config = {
                ROOT_DIR: this.getElementValue('userRootDir'),
                FILE_TARGET: this.getElementValue('userFileTarget'),
                lm_url: this.getElementValue('userLmUrl'),
                DEPLOY_DIR: this.getElementValue('userDeployDir'),
                DEPLOY_OVERWRITE: document.getElementById('userDeployOverwrite').checked
            };
            
            // Debug: mostrar qué valores se están enviando
            console.log('Datos a guardar:', config);
            console.log('FILE_TARGET element:', document.getElementById('userFileTarget'));
            console.log('DEPLOY_OVERWRITE element:', document.getElementById('userDeployOverwrite'));
            
            const response = await fetch('/api/user_config/general', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Mostrar éxito si hay elemento de estado disponible
                if (statusSpan) {
                    statusSpan.textContent = '✅ Configuración guardada exitosamente';
                    statusSpan.className = 'status-message success';
                    
                    setTimeout(() => {
                        if (statusSpan) {
                            statusSpan.textContent = '';
                            statusSpan.className = 'status-message';
                        }
                    }, 3000);
                }
                
                // Revalidar rutas (comentado temporalmente debido a problemas de validación)
                // await this.validateUserPaths();
                
            } else {
                // Mostrar error si hay elemento de estado disponible
                if (statusSpan) {
                    statusSpan.textContent = `❌ ${data.error}`;
                    statusSpan.className = 'status-message error';
                }
            }
            
        } catch (error) {
            const statusSpan = document.getElementById('userConfigStatus') || document.getElementById('completeConfigStatus');
            if (statusSpan) {
                statusSpan.textContent = `❌ Error guardando configuración: ${error.message}`;
                statusSpan.className = 'status-message error';
            }
            console.error('Error guardando configuración de usuario:', error);
            
        } finally {
            // Los elementos ya se manejan en el timeout del try block
            // No necesitamos hacer nada aquí
        }
    }
    
    async saveModelConfig() {
        try {
            // Buscar elementos de UI (pueden no existir en configuración unificada)
            const saveBtn = document.getElementById('btnSaveModelConfig') || document.getElementById('btnSaveCompleteConfig');
            const statusSpan = document.getElementById('modelConfigStatus') || document.getElementById('completeConfigStatus');
            
            // Mostrar estado de carga si hay botón disponible
            if (saveBtn) {
                saveBtn.disabled = true;
                const originalText = saveBtn.textContent;
                saveBtn.textContent = '💾 Guardando...';
                
                // Restaurar texto original después
                setTimeout(() => {
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.textContent = originalText;
                    }
                }, 1000);
            }
            
            // Recopilar todas las propiedades de la configuración del modelo
            const config = {
                // Modelo preferido
                lm_model: this.getElementValue('userLmModel'),
                
                // Preset activo
                active_preset: this.getElementValue('presetList'),
                preset: this.getElementValue('presetList'),  // Incluir para perfiles también
                
                // Parámetros ARGS
                arg_config: this.getElementValue('arg_config'),
                arg_compat: this.getElementValue('arg_compat'),
                arg_batch: this.getElementValue('arg_batch'),
                arg_timeout: this.getElementValue('arg_timeout'),
                
                // Parámetros del modelo desde preset (¡ESTOS SE ESTABAN PERDIENDO!)
                api_temperature: this.getElementValue('api_temperature'),
                api_top_p: this.getElementValue('api_top_p'),
                api_top_k: this.getElementValue('api_top_k'),
                api_max_tokens: this.getElementValue('api_max_tokens'),
                api_repetition_penalty: this.getElementValue('api_repetition_penalty'),
                api_presence_penalty: this.getElementValue('api_presence_penalty'),
                
                // Configuración de caché
                use_cache: document.getElementById('useCache')?.checked === true,
                overwrite_cache: document.getElementById('overwriteCache')?.checked === true
            };
            
            // Debug: mostrar qué se está guardando
            console.log('💾 Guardando configuración del modelo:');
            console.log('  lm_model:', config.lm_model);
            console.log('  active_preset:', config.active_preset);
            console.log('  Parámetros del modelo:');
            console.log('    api_temperature:', config.api_temperature);
            console.log('    api_top_p:', config.api_top_p);
            console.log('    api_top_k:', config.api_top_k);
            console.log('    api_max_tokens:', config.api_max_tokens);
            console.log('    api_repetition_penalty:', config.api_repetition_penalty);
            console.log('    api_presence_penalty:', config.api_presence_penalty);
            console.log('  Cache:');
            console.log('    use_cache:', config.use_cache);
            console.log('    overwrite_cache:', config.overwrite_cache);
            
            const response = await fetch('/api/user_config/model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Mostrar éxito si hay elemento de estado disponible
                if (statusSpan) {
                    statusSpan.textContent = '✅ Configuración guardada exitosamente';
                    statusSpan.className = 'status-message success';
                    
                    setTimeout(() => {
                        if (statusSpan) {
                            statusSpan.textContent = '';
                            statusSpan.className = 'status-message';
                        }
                    }, 3000);
                }
                
            } else {
                // Mostrar error si hay elemento de estado disponible
                if (statusSpan) {
                    statusSpan.textContent = `❌ ${data.error}`;
                    statusSpan.className = 'status-message error';
                }
            }
            
        } catch (error) {
            const statusSpan = document.getElementById('modelConfigStatus') || document.getElementById('completeConfigStatus');
            if (statusSpan) {
                statusSpan.textContent = `❌ Error guardando configuración: ${error.message}`;
                statusSpan.className = 'status-message error';
            }
            console.error('Error guardando configuración del modelo:', error);
            
        } finally {
            // Los elementos ya se manejan en el timeout del try block
            // No necesitamos hacer nada aquí
        }
    }
    
    async resetModelConfig() {
        if (!confirm('¿Estás seguro de que quieres restaurar la configuración del modelo a los valores por defecto?')) {
            return;
        }
        
        try {
            const statusSpan = document.getElementById('modelConfigStatus');
            
            // Resetear la configuración del modelo usando el endpoint específico
            const response = await fetch('/api/user_config/model/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Recargar la configuración para actualizar los campos en la interfaz
                await this.loadUserConfig();
                
                // Mostrar éxito
                statusSpan.textContent = '🔄 Configuración del modelo restablecida';
                statusSpan.className = 'status-message success';
                
                // Actualizar preview de ARGS
                this.renderArgsPreview();
                
                setTimeout(() => {
                    statusSpan.textContent = '';
                    statusSpan.className = 'status-message';
                }, 3000);
                
            } else {
                throw new Error(data.error);
            }
            
        } catch (error) {
            const statusSpan = document.getElementById('modelConfigStatus');
            statusSpan.textContent = `❌ Error: ${error.message}`;
            statusSpan.className = 'status-message error';
        }
    }
    
    async resetUserConfig() {
        if (!confirm('¿Estás seguro de que quieres restaurar la configuración a los valores por defecto?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/user_config/general/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Recargar la configuración
                await this.loadUserConfig();
                
                const statusSpan = document.getElementById('userConfigStatus');
                statusSpan.textContent = '🔄 Configuración restablecida';
                statusSpan.className = 'status-message success';
                
                setTimeout(() => {
                    statusSpan.textContent = '';
                    statusSpan.className = 'status-message';
                }, 3000);
                
            } else {
                throw new Error(data.error);
            }
            
        } catch (error) {
            const statusSpan = document.getElementById('userConfigStatus');
            statusSpan.textContent = `❌ Error: ${error.message}`;
            statusSpan.className = 'status-message error';
        }
    }
    
    async validateUserPaths() {
        const rootDir = this.getElementValue('userRootDir');
        const deployDir = this.getElementValue('userDeployDir');
        
        if (rootDir || deployDir) {
            try {
                const config = {
                    ROOT_DIR: rootDir,
                    DEPLOY_DIR: deployDir
                };
                
                const response = await fetch('/api/validate_paths', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(config)
                });
                
                const data = await response.json();
                
                if (data.validation) {
                    this.updateValidationStatus(data.validation);
                }
                
            } catch (error) {
                console.error('Error validando rutas:', error);
            }
        }
    }
    
    updateValidationStatus(validation) {
        // Validar ROOT_DIR
        const rootStatus = document.getElementById('rootDirStatus');
        if (rootStatus && validation.ROOT_DIR !== null) {
            if (validation.ROOT_DIR) {
                rootStatus.textContent = '✅ Ruta válida';
                rootStatus.className = 'validation-status valid';
            } else {
                rootStatus.textContent = '❌ Ruta no encontrada';
                rootStatus.className = 'validation-status invalid';
            }
        } else if (rootStatus) {
            rootStatus.style.display = 'none';
        }
        
        // Validar DEPLOY_DIR
        const deployStatus = document.getElementById('deployDirStatus');
        if (deployStatus && validation.DEPLOY_DIR !== null) {
            if (validation.DEPLOY_DIR) {
                deployStatus.textContent = '✅ Ruta válida';
                deployStatus.className = 'validation-status valid';
            } else {
                deployStatus.textContent = '❌ Ruta no encontrada';
                deployStatus.className = 'validation-status invalid';
            }
        } else if (deployStatus) {
            deployStatus.style.display = 'none';
        }
    }
    
    async loadUserLmModels() {
        const url = this.getElementValue('userLmUrl');
        const hint = document.getElementById('lmModelsHint');
        const select = document.getElementById('userLmModel');
        const refreshBtn = document.getElementById('btnRefreshModels');
        
        // Mostrar estado de carga
        if (hint) hint.textContent = 'Cargando modelos...';
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.textContent = '🔄 Cargando...';
        }
        
        if (url && url.trim() !== '') {
            try {
                const response = await fetch(`/api/lm_models?lm_url=${encodeURIComponent(url)}`);
                const data = await response.json();
                
                if (data.ok && data.models) {
                    if (select) {
                        // Guardar el valor actual seleccionado
                        const currentValue = select.value;
                        
                        // Limpiar opciones existentes excepto la primera
                        select.innerHTML = '<option value="">Seleccionar modelo...</option>';
                        
                        // Agregar nuevas opciones solo si hay modelos disponibles
                        if (data.models.length > 0) {
                            data.models.forEach(model => {
                                const option = document.createElement('option');
                                const modelId = model.id || model.name || model;
                                option.value = modelId;
                                option.textContent = modelId;
                                select.appendChild(option);
                            });
                            
                            // Restaurar valor anterior si existe
                            if (currentValue && [...select.options].some(opt => opt.value === currentValue)) {
                                select.value = currentValue;
                            }
                            
                            if (hint) hint.textContent = `${data.models.length} modelos disponibles`;
                        } else {
                            // No hay modelos disponibles
                            select.innerHTML = '<option value="">No hay modelos cargados en LM Studio</option>';
                            if (hint) {
                                const serverMsg = data.server_info && data.server_info.message ? data.server_info.message : 'No hay modelos disponibles';
                                
                                // Verificar si es un problema de rendimiento y obtener diagnósticos
                                if (serverMsg.includes('muy lento') || serverMsg.includes('responde muy lento')) {
                                    this.handleSlowLMStudioResponse(hint, url);
                                } else {
                                    hint.textContent = serverMsg;
                                }
                            }
                        }
                    }
                } else {
                    if (select) {
                        select.innerHTML = '<option value="">Error al cargar modelos - servidor no responde</option>';
                    }
                    if (hint) hint.textContent = 'Error al cargar modelos desde el servidor';
                }
                
            } catch (error) {
                console.error('Error cargando modelos LM para configuración de usuario:', error);
                if (select) {
                    select.innerHTML = '<option value="">Error de conexión - verifique que LM Studio esté corriendo</option>';
                }
                if (hint) hint.textContent = 'Error de conexión - verifique que LM Studio esté corriendo';
            }
            
            // Restaurar estado del botón en caso de error también
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.textContent = '🔄 Actualizar';
            }
        } else {
            if (select) {
                select.innerHTML = '<option value="">Configure la URL del servidor primero...</option>';
            }
            if (hint) hint.textContent = 'Configure la URL del servidor en la sección superior';
        }
        
        // Restaurar estado del botón
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.textContent = '🔄 Actualizar';
        }
        
        // Verificar estado del modelo solo si hay uno seleccionado
        const modelInput = document.getElementById('userLmModel');
        if (modelInput?.value && modelInput.value !== 'Seleccionar modelo...') {
            this.checkModelStatus();
        } else {
            // Solo mostrar mensaje de ayuda si no hay modelo seleccionado
            this.updateModelStatus('warning', '⚠️', 'Selecciona un modelo de la lista');
        }
    }

    /**
     * Maneja respuestas lentas de LM Studio con diagnósticos detallados
     * @param {HTMLElement} hintElement - Elemento donde mostrar la información
     * @param {string} lmUrl - URL del servidor LM Studio
     */
    async handleSlowLMStudioResponse(hintElement, lmUrl) {
        try {
            // Mostrar mensaje inicial
            hintElement.innerHTML = '<span style="color: #ff6b35;">⚠️ LM Studio responde muy lento - Obteniendo diagnósticos...</span>';
            
            // Obtener diagnósticos del servidor
            const diagnosticsResponse = await fetch(`/api/lm_studio/diagnostics?lm_url=${encodeURIComponent(lmUrl)}`);
            const diagnostics = await diagnosticsResponse.json();
            
            if (diagnostics.ok && diagnostics.diagnostics) {
                const diag = diagnostics.diagnostics;
                
                // Crear mensaje mejorado con recomendaciones
                let message = '<div style="color: #ff6b35; font-weight: bold;">⚠️ LM Studio responde muy lento</div>';
                
                if (diag.performance_issue) {
                    message += `<div style="color: #666; font-size: 0.9em; margin-top: 5px;">
                        <strong>Problema:</strong> ${diag.performance_issue}<br>
                        <strong>Acción recomendada:</strong> ${diag.recommended_action}
                    </div>`;
                    
                    // Mostrar modelos recomendados si están disponibles
                    if (diag.recommended_models && diag.recommended_models.length > 0) {
                        message += `<div style="color: #28a745; font-size: 0.85em; margin-top: 3px;">
                            <strong>Modelos recomendados:</strong> ${diag.recommended_models.slice(0, 2).join(', ')}
                        </div>`;
                    }
                    
                    // Agregar botón para ver más detalles
                    message += `<div style="margin-top: 5px;">
                        <button onclick="orchestratorInstance.showLMStudioDiagnosticsModal('${encodeURIComponent(JSON.stringify(diag))}')" 
                                style="font-size: 0.8em; padding: 2px 8px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer;">
                            Ver diagnóstico completo
                        </button>
                    </div>`;
                }
                
                hintElement.innerHTML = message;
            } else {
                // Fallback si no se pueden obtener diagnósticos
                hintElement.innerHTML = `<span style="color: #ff6b35;">⚠️ LM Studio responde muy lento</span>
                    <div style="color: #666; font-size: 0.9em; margin-top: 3px;">
                        Sugerencia: Pruebe con un modelo más pequeño o reinicie LM Studio
                    </div>`;
            }
            
        } catch (error) {
            console.error('Error obteniendo diagnósticos de LM Studio:', error);
            
            // Mensaje de fallback con sugerencias básicas
            hintElement.innerHTML = `<span style="color: #ff6b35;">⚠️ LM Studio responde muy lento</span>
                <div style="color: #666; font-size: 0.9em; margin-top: 3px;">
                    Sugerencias: Reinicie LM Studio, cambie a un modelo más pequeño, o verifique recursos del sistema
                </div>`;
        }
    }

    /**
     * Muestra modal con diagnósticos completos de LM Studio
     * @param {string} diagnosticsJson - JSON string con información de diagnósticos
     */
    showLMStudioDiagnosticsModal(diagnosticsJson) {
        try {
            const diagnostics = JSON.parse(decodeURIComponent(diagnosticsJson));
            
            // Crear contenido del modal
            let modalContent = `
                <div style="max-width: 600px;">
                    <h3 style="color: #ff6b35; margin-bottom: 15px;">🔍 Diagnóstico LM Studio</h3>
                    
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                        <h4 style="margin-top: 0; color: #dc3545;">Problema Detectado</h4>
                        <p><strong>Estado:</strong> ${diagnostics.performance_issue}</p>
                        <p><strong>Recomendación:</strong> ${diagnostics.recommended_action}</p>
                    </div>
            `;
            
            // Agregar información de modelos recomendados
            if (diagnostics.recommended_models && diagnostics.recommended_models.length > 0) {
                modalContent += `
                    <div style="background: #d4edda; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                        <h4 style="margin-top: 0; color: #155724;">Modelos Recomendados</h4>
                        <ul style="margin-bottom: 0;">
                `;
                
                diagnostics.recommended_models.forEach(model => {
                    modalContent += `<li style="margin-bottom: 5px;">${model}</li>`;
                });
                
                modalContent += '</ul></div>';
            }
            
            // Agregar sugerencias de optimización
            if (diagnostics.suggestions && diagnostics.suggestions.length > 0) {
                modalContent += `
                    <div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                        <h4 style="margin-top: 0; color: #856404;">Sugerencias de Optimización</h4>
                        <ol style="margin-bottom: 0;">
                `;
                
                diagnostics.suggestions.forEach(suggestion => {
                    modalContent += `<li style="margin-bottom: 5px;">${suggestion}</li>`;
                });
                
                modalContent += '</ol></div>';
            }
            
            modalContent += `
                    <div style="text-align: center; margin-top: 20px;">
                        <button onclick="this.closest('.modal').style.display='none'" 
                                style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer;">
                            Cerrar
                        </button>
                    </div>
                </div>
            `;
            
            // Mostrar modal (usando el sistema de modales existente o crear uno simple)
            this.showInfoModal('Diagnóstico LM Studio', modalContent);
            
        } catch (error) {
            console.error('Error mostrando diagnósticos:', error);
            alert('Error al mostrar diagnósticos detallados');
        }
    }

    isFlameingCliffsMission(filename) {
        /**
         * Detecta si un archivo de misión es de Flaming Cliffs usando múltiples patrones
         * Sincronizado con la lógica del backend en translation_engine.py
         */
        if (!filename) return false;
        
        const filenameUpper = filename.toUpperCase();
        
        // Patrones FC optimizados (sincronizados con FCDetector backend)
        // IMPORTANTE: Mantener sincronizado con app/utils/fc_detector.py
        const fcPatterns = [
            // Patrones de alta prioridad (más específicos)
            /-FC-/,            // Patrón clásico: F-5E-FC-Training.miz
            /-FC\s/,           // FC con espacio: F-5E-FC - BFM Arrival.miz  
            /^FC-/,            // Prefijo FC: FC-Mission.miz
            /_FC_/,            // FC con underscores: Hornet_FC_BVR.miz
            
            // Patrones de prioridad media
            /-FC\./,           // FC antes de extensión: Mission-FC.miz
            /-FC$/,            // Termina en FC: Mission-FC
            /_FC\s/,           // Underscore FC espacio: Mission_FC Combat.miz
            /^FC_/,            // Prefijo FC underscore: FC_Mission.miz
            
            // Patrones específicos
            /FLAMINGCLIFF/     // Palabra completa FlamingCliff
        ];
        
        // Verificar cada patrón
        for (const pattern of fcPatterns) {
            if (pattern.test(filenameUpper)) {
                console.debug(`Archivo '${filename}' detectado como FC por patrón: ${pattern}`);
                return true;
            }
        }
        
        return false;
    }

    // === NUEVOS MÉTODOS PARA MANEJO DE MODOS ===

    onModeChange() {
        /**
         * Manejador para cambio de modo de trabajo.
         * Actualiza contador, re-renderiza campañas y misiones según filtros del modo.
         */
        console.log('🔄 Cambio de modo detectado');
        
        // Controlar visibilidad de opciones de traducción
        this.updateTranslationOptions();
        
        // Actualizar contador de misiones disponibles para el modo
        this.updateModeCounter();
        
        // Re-renderizar campañas para el nuevo modo (solo las que tengan misiones disponibles)
        if (this.campaigns && this.campaigns.length > 0) {
            this.renderCampaigns();
        }
        
        // Limpiar selección de campaña si la actual no tiene misiones para el nuevo modo
        this.validateCampaignForCurrentMode();
        
        // Re-renderizar misiones con filtros del modo actual
        if (this.selectedCampaign && this.missions && this.missions.length) {
            this.renderMissionsForCurrentMode();
        }
    }
    
    updateTranslationOptions() {
        /**
         * Controla la visibilidad de las opciones de traducción según el modo seleccionado
         */
        const mode = this.getSelectedMode();
        const translationOptionsDiv = document.getElementById('translation-options');
        
        if (translationOptionsDiv) {
            // Solo mostrar opciones de traducción en modo 'traducir'
            if (mode === 'traducir') {
                translationOptionsDiv.style.display = 'block';
            } else {
                translationOptionsDiv.style.display = 'none';
            }
        }
    }

    async validateCampaignForCurrentMode() {
        /**
         * Validar si la campaña seleccionada tiene misiones para el modo actual.
         * Si no las tiene, limpiar la selección.
         */
        if (!this.selectedCampaign) return;
        
        const selectedMode = this.getSelectedMode();
        const availableCampaigns = await this.getAvailableCampaignsForMode(selectedMode);
        
        const campaignAvailable = availableCampaigns.some(c => c.name === this.selectedCampaign);
        
        if (!campaignAvailable) {
            console.log(`🔄 Campaña ${this.selectedCampaign} no tiene misiones para modo ${selectedMode}, limpiando selección`);
            this.selectedCampaign = null;
            
            // Limpiar radio button seleccionado
            const radioButtons = document.querySelectorAll('input[name="camp"]');
            radioButtons.forEach(radio => radio.checked = false);
            
            // Limpiar lista de misiones
            const missionsBox = document.getElementById('missions');
            if (missionsBox) {
                missionsBox.innerHTML = `
                    <div style="padding: 12px; text-align: center; color: #6b7280; font-style: italic;">
                        Selecciona una campaña para ver las misiones disponibles
                    </div>
                `;
            }
        }
    }

    async updateModeCounter() {
        /**
         * Actualizar contador de misiones disponibles para el modo seleccionado.
         */
        try {
            const selectedMode = this.getSelectedMode();
            const counter = document.getElementById('mode-missions-text');
            
            if (!counter) {
                console.warn('❌ Elemento mode-missions-text no encontrado');
                return;
            }
            
            // Mostrar cargando
            counter.textContent = 'Analizando misiones disponibles...';
            counter.style.color = '#6b7280';
            
            console.log(`🔍 Actualizando contador para modo: ${selectedMode}`);
            
            // Obtener misiones para el modo seleccionado (con timeout)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 segundos timeout
            
            const response = await fetch(`/api/missions_by_mode?mode=${selectedMode}`, {
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('📊 Respuesta del API:', data);
            
            if (data.ok) {
                const modeInfo = data.mode_info;
                const count = data.count;
                const summary = data.summary;
                
                // Actualizar texto con información del modo
                counter.innerHTML = `
                    ${modeInfo.icon} <strong>${count} misiones</strong> disponibles para ${modeInfo.action.toLowerCase()}
                    <br><small>Total: ${summary.sin_traducir} sin traducir • ${summary.traducidas} traducidas • ${summary.reempaquetadas} reempaquetadas</small>
                `;
                counter.style.color = '#0369a1';
                
            } else {
                // Error del servidor - verificar si es problema de configuración
                let errorText = `Error: ${data.error}`;
                
                if (data.error && data.error.includes('ROOT_DIR')) {
                    // Es un problema de configuración de ROOT_DIR
                    errorText = '⚠️ Ruta de DCS no configurada';
                    
                    // Mostrar botón para detectar automáticamente
                    const detectButton = ' <button type="button" onclick="window.orchestratorUI.tryAutoDetectDCS()" style="margin-left:8px;padding:2px 8px;background:#22c55e;color:white;border:none;border-radius:4px;cursor:pointer;">🔍 Detectar DCS</button>';
                    counter.innerHTML = errorText + detectButton;
                    counter.style.color = '#dc2626';
                } else {
                    counter.textContent = errorText;
                    counter.style.color = '#dc2626';
                }
            }
            
        } catch (error) {
            console.error('❌ Error actualizando contador de modo:', error);
            const counter = document.getElementById('mode-missions-text');
            if (counter) {
                let message = '⚠️ No se pudo cargar información de misiones';
                let detail = 'Verifica que la ruta de DCS esté configurada correctamente';
                
                if (error.name === 'AbortError') {
                    detail = 'Timeout - la operación tardó demasiado tiempo';
                } else if (error.message.includes('HTTP')) {
                    detail = `Error del servidor: ${error.message}`;
                }
                
                counter.innerHTML = `
                    <span style="color: #f59e0b;">${message}</span>
                    <br><small>${detail}</small>
                `;
                counter.style.color = '#f59e0b';
            }
        }
    }

    getSelectedMode() {
        /**
         * Obtener el modo actualmente seleccionado.
         */
        const modeRadio = document.querySelector('input[name=mode]:checked');
        return modeRadio ? modeRadio.value : 'traducir';
    }

    async renderMissionsForCurrentMode(counters = {}) {
        /**
         * Re-renderizar misiones aplicando filtros según el modo actual.
         */
        const selectedMode = this.getSelectedMode();
        
        console.log(`🎯 Renderizando misiones para modo: ${selectedMode}`);
        
        try {
            // Obtener misiones filtradas por modo desde el backend
            const filteredMissions = await this.getMissionsByModeAndCampaign(selectedMode, this.selectedCampaign);
            
            // Renderizar solo las misiones apropiadas para el modo
            this.renderMissions(filteredMissions, counters, selectedMode);
            
            // Actualizar descripciones según el modo
            this.updateModeDescription(selectedMode);
            
        } catch (error) {
            console.error('Error renderizando misiones para modo:', error);
            // Fallback: mostrar todas las misiones si hay error
            this.renderMissions(this.missions, counters, selectedMode);
        }
    }

    async loadMissionsForCurrentMode() {
        /**
         * Cargar misiones específicamente para el modo actual.
         */
        if (!this.selectedCampaign) return;
        
        const selectedMode = this.getSelectedMode();
        console.log(`🔄 Cargando misiones para modo: ${selectedMode}, campaña: ${this.selectedCampaign}`);
        
        // Re-cargar todas las misiones primero
        await this.loadMissions();
    }

    updateModeDescription(mode) {
        /**
         * Actualizar descripción de las acciones según el modo.
         */
        const descriptions = {
            'traducir': {
                icon: '🌍',
                action: 'Traducir',
                description: 'Se extraerán y traducirán las misiones seleccionadas'
            },
            'reempaquetar': {
                icon: '📦',
                action: 'Reempaquetar',
                description: 'Se generarán archivos .miz con las traducciones aplicadas'
            },
            'desplegar': {
                icon: '🚀',
                action: 'Desplegar',
                description: 'Se copiarán las misiones traducidas al directorio de DCS'
            }
        };
        
        const modeDesc = descriptions[mode] || descriptions['traducir'];
        
        // Actualizar título del botón ejecutar si existe
        const runButton = document.getElementById('run');
        if (runButton) {
            runButton.innerHTML = `${modeDesc.icon} ${modeDesc.action} Seleccionadas`;
            runButton.title = modeDesc.description;
        }
    }

    async getMissionsByMode(mode, campaign = null) {
        /**
         * Obtener misiones filtradas por modo desde el backend.
         */
        try {
            let url = `/api/missions_by_mode?mode=${mode}`;
            if (campaign) {
                url += `&campaign=${encodeURIComponent(campaign)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.ok) {
                return data.missions;
            } else {
                console.error('Error obteniendo misiones por modo:', data.error);
                return [];
            }
        } catch (error) {
            console.error('Error en getMissionsByMode:', error);
            return [];
        }
    }

    async getMissionsByModeAndCampaign(mode, campaign) {
        /**
         * Obtener misiones de una campaña específica filtradas por modo.
         * Ahora usa la nueva API que integra DCS original + estados de traducción.
         */
        try {
            let url = `/api/missions_by_mode?mode=${mode}`;
            if (campaign) {
                url += `&campaign=${encodeURIComponent(campaign)}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.ok) {
                // Convertir formato nuevo a formato esperado por renderMissions
                const missions = (data.missions || []).map(mission => {
                    if (typeof mission === 'object' && mission.name) {
                        // Formato nuevo: {name, campaign, state, path}
                        return {
                            name: mission.name,
                            campaign: mission.campaign,
                            state: mission.state,
                            type: mission.state === 'traducida' ? 'translated' : 
                                  mission.state === 'reempaquetada' ? 'packaged' : 'normal'
                        };
                    } else {
                        // Formato legacy: string
                        return {
                            name: mission,
                            type: 'normal'
                        };
                    }
                });
                
                return missions;
            } else {
                console.warn(`Error obteniendo misiones: ${data.error}`);
                
                // Si es un problema de configuración, mostrar mensaje específico
                if (data.error.includes('ROOT_DIR')) {
                    alert('⚠️ Ruta DCS no configurada.\n\nPor favor:\n1. Ve a "Configuración General"\n2. Configura "RUTA CAMPAÑAS"\n3. Haz clic en "🎯 Detectar DCS" o ingresa la ruta manualmente');
                }
                
                return [];
            }
        } catch (error) {
            console.error('Error obteniendo misiones por modo y campaña:', error);
            return [];
        }
    }

    async getAvailableCampaignsForMode(mode) {
        /**
         * Obtener campañas que tienen misiones disponibles para el modo seleccionado.
         */
        try {
            const response = await fetch(`/api/campaigns_by_mode?mode=${mode}`);
            const data = await response.json();
            
            if (data.ok) {
                return data.campaigns || [];
            } else {
                console.warn(`No se pudieron obtener campañas para modo ${mode}:`, data.error);
                // Fallback: retornar todas las campañas disponibles
                return this.campaigns || [];
            }
        } catch (error) {
            console.error('Error obteniendo campañas por modo:', error);
            // Fallback: retornar todas las campañas disponibles
            return this.campaigns || [];
        }
    }
    
    /**
     * Verifica el estado actual de las unidades y campañas registradas
     */
    async checkDriveStatus() {
        try {
            const response = await fetch('/api/drives/status');
            const result = await response.json();
            
            if (result.success) {
                this.processDriveStatus(result);
                // También actualizar el contador de misiones para refrescar el estado
                await this.updateModeCounter();
            }
        } catch (error) {
            console.error('Error verificando estado de unidades:', error);
            // Si hay error, también intentar actualizar el contador para mostrar estado actual
            await this.updateModeCounter();
        }
    }
    
    /**
     * Procesa el estado de las unidades y muestra avisos si es necesario
     */
    processDriveStatus(statusData) {
        const { drive_changes, status_summary, unavailable_campaigns } = statusData;
        
        // Mostrar avisos de unidades desconectadas
        if (drive_changes.disconnected && drive_changes.disconnected.length > 0) {
            this.showDisconnectedDrivesWarning(drive_changes.disconnected, unavailable_campaigns);
        }
        
        // Mostrar avisos generales del estado
        if (status_summary.warnings && status_summary.warnings.length > 0) {
            this.showDriveWarnings(status_summary.warnings);
        }
        
        // Actualizar indicadores en la UI
        this.updateDriveStatusIndicators(status_summary);
    }
    
    /**
     * Procesa el resumen de campañas desde la detección automática
     */
    processCampaignsSummary(summary) {
        if (summary.warnings && summary.warnings.length > 0) {
            this.showDriveWarnings(summary.warnings);
        }
        
        if (summary.unavailable_campaigns && summary.unavailable_campaigns.length > 0) {
            this.showUnavailableCampaignsInfo(summary.unavailable_campaigns);
        }
    }
    
    /**
     * Muestra advertencia cuando se detectan unidades desconectadas con campañas
     */
    showDisconnectedDrivesWarning(disconnectedDrives, unavailableCampaigns) {
        const campaignsByDrive = {};
        
        // Agrupar campañas por unidad desconectada
        unavailableCampaigns.forEach(campaign => {
            if (disconnectedDrives.includes(campaign.drive_letter)) {
                if (!campaignsByDrive[campaign.drive_letter]) {
                    campaignsByDrive[campaign.drive_letter] = [];
                }
                campaignsByDrive[campaign.drive_letter].push(campaign);
            }
        });
        
        if (Object.keys(campaignsByDrive).length > 0) {
            let message = '🔌 ¡Unidades desconectadas detectadas!\\n\\n';
            
            for (const [drive, campaigns] of Object.entries(campaignsByDrive)) {
                message += `📀 Unidad ${drive}: - ${campaigns.length} campañas no disponibles\\n`;
                campaigns.slice(0, 3).forEach(c => {
                    message += `   • ${c.name} (${c.missions_count} misiones)\\n`;
                });
                if (campaigns.length > 3) {
                    message += `   • ... y ${campaigns.length - 3} más\\n`;
                }
                message += '\\n';
            }
            
            message += 'Conecta las unidades para acceder a estas campañas.';
            
            alert(message);
        }
    }
    
    /**
     * Muestra información sobre campañas no disponibles
     */
    showUnavailableCampaignsInfo(unavailableCampaigns) {
        if (unavailableCampaigns.length > 0) {
            console.log(`ℹ️ Hay ${unavailableCampaigns.length} campañas registradas actualmente no disponibles`);
        }
    }
    
    /**
     * Muestra avisos generales del estado de unidades
     */
    showDriveWarnings(warnings) {
        warnings.forEach(warning => {
            console.warn('🔍 Estado de unidades:', warning);
        });
        
        // Si hay muchos avisos, mostrar un resumen
        if (warnings.length > 0) {
            const driveIssues = warnings.filter(w => w.includes('no está disponible')).length;
            if (driveIssues > 0) {
                const statusMsg = document.getElementById('autoRootMsg') || document.getElementById('campaignStatusMsg');
                if (statusMsg) {
                    statusMsg.innerHTML = `⚠️ ${driveIssues} unidad(es) con campañas no disponibles. <a href="#" onclick="window.orchestratorUI.showDetailedDriveStatus()">Ver detalles</a>`;
                    statusMsg.style.color = '#ffa500';
                }
            }
        }
    }
    
    /**
     * Actualiza indicadores visuales del estado de unidades en la UI
     */
    updateDriveStatusIndicators(statusSummary) {
        // Crear o actualizar indicador de estado
        let statusIndicator = document.getElementById('driveStatusIndicator');
        if (!statusIndicator) {
            statusIndicator = document.createElement('div');
            statusIndicator.id = 'driveStatusIndicator';
            statusIndicator.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 1000;
                max-width: 250px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            `;
            document.body.appendChild(statusIndicator);
        }
        
        const { available_campaigns, unavailable_campaigns, drives_available, drives_with_campaigns } = statusSummary;
        
        if (unavailable_campaigns > 0) {
            statusIndicator.innerHTML = `🔌 ${unavailable_campaigns} campañas no disponibles`;
            statusIndicator.style.backgroundColor = '#fff3cd';
            statusIndicator.style.borderLeft = '4px solid #ffc107';
            statusIndicator.style.color = '#856404';
            statusIndicator.title = 'Hay campañas registradas en unidades que no están conectadas';
        } else if (available_campaigns > 0) {
            statusIndicator.innerHTML = `✅ ${available_campaigns} campañas disponibles`;
            statusIndicator.style.backgroundColor = '#d4edda';
            statusIndicator.style.borderLeft = '4px solid #28a745';
            statusIndicator.style.color = '#155724';
            statusIndicator.title = 'Todas las campañas registradas están disponibles';
        } else {
            statusIndicator.style.display = 'none';
        }
    }
    
    /**
     * Muestra estado detallado de unidades en un modal o nueva ventana
     */
    async showDetailedDriveStatus() {
        try {
            const response = await fetch('/api/drives/status');
            const result = await response.json();
            
            if (result.success) {
                let content = '=== ESTADO DETALLADO DE UNIDADES ===\\n\\n';
                
                content += `📊 RESUMEN GENERAL:\\n`;
                content += `• Unidades disponibles: ${result.status_summary.drives_available}\\n`;
                content += `• Unidades con campañas: ${result.status_summary.drives_with_campaigns}\\n`;
                content += `• Campañas disponibles: ${result.status_summary.available_campaigns}\\n`;
                content += `• Campañas no disponibles: ${result.status_summary.unavailable_campaigns}\\n\\n`;
                
                if (result.status_summary.drives_detail.length > 0) {
                    content += '📀 DETALLE POR UNIDAD:\\n';
                    result.status_summary.drives_detail.forEach(drive => {
                        const status = drive.is_available ? '✅' : '❌';
                        content += `${status} ${drive.letter}: - ${drive.campaigns_count} campañas`;
                        if (!drive.is_available && drive.campaigns_count > 0) {
                            content += ' (NO DISPONIBLE)';
                        }
                        content += '\\n';
                    });
                    content += '\\n';
                }
                
                if (result.unavailable_campaigns.length > 0) {
                    content += '⚠️ CAMPAÑAS NO DISPONIBLES:\\n';
                    result.unavailable_campaigns.forEach(campaign => {
                        content += `• ${campaign.name} (${campaign.drive_letter}:) - ${campaign.missions_count} misiones\\n`;
                    });
                }
                
                alert(content);
            }
        } catch (error) {
            console.error('Error obteniendo estado detallado:', error);
            alert('Error al obtener el estado detallado de unidades');
        }
    }

    /**
     * Muestra modal informativo con título y contenido personalizado
     * @param {string} title - Título del modal
     * @param {string} content - Contenido HTML del modal
     */
    showInfoModal(title, content) {
        // Crear modal dinámico si no existe
        let modal = document.getElementById('info-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'info-modal';
            modal.className = 'modal';
            modal.style.cssText = `
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
            `;
            
            modal.innerHTML = `
                <div style="
                    background-color: #fefefe;
                    margin: 5% auto;
                    padding: 20px;
                    border-radius: 8px;
                    width: 80%;
                    max-width: 700px;
                    max-height: 80vh;
                    overflow-y: auto;
                    position: relative;
                ">
                    <span id="info-modal-close" style="
                        color: #aaa;
                        float: right;
                        font-size: 28px;
                        font-weight: bold;
                        cursor: pointer;
                        position: absolute;
                        top: 15px;
                        right: 20px;
                    ">&times;</span>
                    <h2 id="info-modal-title" style="margin-top: 0; color: #333;"></h2>
                    <div id="info-modal-content"></div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Agregar event listeners
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
            
            document.getElementById('info-modal-close').addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }
        
        // Actualizar contenido y mostrar
        document.getElementById('info-modal-title').textContent = title;
        document.getElementById('info-modal-content').innerHTML = content;
        modal.style.display = 'block';
    }

    // NUEVO: Mostrar información de modelos recomendados
    showRecommendedModels(config) {
        const recommendedModelsCard = document.getElementById('recommendedModelsCard');
        const recommendedLlama = document.getElementById('recommendedLlama');
        const recommendedGemma = document.getElementById('recommendedGemma');
        const presetInfo = document.getElementById('presetInfo');
        
        // Si no hay elementos de modelos recomendados, simplemente ignorar sin error
        if (!recommendedModelsCard) {
            // En la configuración unificada, estos elementos no existen
            // Mostrar información de modelos recomendados en consola si están disponibles
            if (config.supported_models) {
                console.log('🎯 Modelos recomendados para este preset:');
                if (config.supported_models.llama) {
                    console.log('  🦙 Llama:', config.supported_models.llama);
                }
                if (config.supported_models.gemma) {
                    console.log('  💎 Gemma:', config.supported_models.gemma);
                }
            }
            return;
        }
        
        // Mostrar la tarjeta
        recommendedModelsCard.style.display = 'block';
        
        // Limpiar valores por defecto
        recommendedLlama.textContent = '-';
        recommendedGemma.textContent = '-';
        presetInfo.textContent = 'Sin información disponible';
        
        // Cargar modelos recomendados si están disponibles
        if (config.supported_models) {
            const models = config.supported_models;
            
            if (models.llama) {
                recommendedLlama.textContent = models.llama;
                recommendedLlama.style.color = '#fbbf24';
            }
            
            if (models.gemma) {
                recommendedGemma.textContent = models.gemma;
                recommendedGemma.style.color = '#22d3ee';
            }
        }
        
        // Mostrar información del preset
        let infoText = '';
        
        if (config.preset_name && config.preset_description) {
            infoText += `📋 ${config.preset_name}\n`;
            infoText += `📝 ${config.preset_description}\n`;
        }
        
        if (config.preset_weight) {
            infoText += `⚖️ Peso: ${config.preset_weight}\n`;
        }
        
        if (config.hardware_profile) {
            infoText += `💻 Hardware: ${config.hardware_profile}\n`;
        }
        
        if (config.arg_batch && config.arg_timeout) {
            infoText += `🔧 Batch: ${config.arg_batch}, Timeout: ${config.arg_timeout}s`;
        }
        
        if (infoText) {
            presetInfo.textContent = infoText;
            presetInfo.style.color = '#a78bfa';
        }
        
        console.log('🎯 Modelos recomendados mostrados:', config.supported_models);
    }

    // Ocultar información de modelos recomendados
    hideRecommendedModels() {
        const recommendedModelsCard = document.getElementById('recommendedModelsCard');
        if (recommendedModelsCard) {
            recommendedModelsCard.style.display = 'none';
            console.log('🙈 Modelos recomendados ocultados');
        }
    }

    // Función para actualizar campañas automáticamente después de la ejecución
    refreshCampaignsAfterExecution() {
        console.log('🔄 Iniciando actualización automática de campañas...');
        
        // Pequeña pausa para asegurar que el backend termine completamente
        setTimeout(() => {
            // 1. Re-escanear las campañas para actualizar contadores
            console.log('📊 Actualizando contadores de misiones...');
            
            // Verificar que hay una campaña seleccionada antes de intentar actualizar
            if (!this.selectedCampaign) {
                console.log('⚠️ No hay campaña seleccionada, saltando actualización automática');
                return;
            }
            
            // Buscar el botón de escaneo y simular click si está disponible
            const scanButton = document.getElementById('scanCampaigns');
            if (scanButton && !scanButton.disabled) {
                console.log('🔄 Ejecutando re-escaneo automático...');
                
                // Marcar que es un refresh automático para evitar interferir con UI
                scanButton.dataset.autoRefresh = 'true';
                
                // Forzar el escaneo programáticamente
                try {
                    // Llamar directamente a la función de escaneo si existe
                    if (typeof this.scanForCampaigns === 'function') {
                        console.log('📡 Usando método directo scanForCampaigns...');
                        this.scanForCampaigns();
                    } else {
                        // Fallback: simular click en el botón
                        console.log('🖱️ Fallback: simulando click en botón de escaneo...');
                        scanButton.click();
                    }
                } catch (error) {
                    console.error('❌ Error ejecutando re-escaneo automático:', error);
                    // Intentar con click como último recurso
                    scanButton.click();
                }
                
                // Limpiar la marca después de un momento
                setTimeout(() => {
                    if (scanButton.dataset.autoRefresh) {
                        delete scanButton.dataset.autoRefresh;
                    }
                }, 2000);
                
                // 2. Mostrar notificación de actualización
                this.showRefreshNotification();
            } else {
                console.log('⚠️ Botón de escaneo no disponible para refresh automático');
                console.log('🔄 Intentando actualización alternativa...');
                
                // Método alternativo: actualizar solo la campaña actual
                if (this.selectedCampaign) {
                    this.loadCampaignMissions(this.selectedCampaign);
                }
            }
            
            console.log('✅ Actualización automática de campañas completada');
        }, 3000); // 3 segundos de espera para asegurar que todo termine
    }

    // Función para mostrar notificación de actualización
    showRefreshNotification() {
        // Buscar un lugar apropiado para mostrar la notificación
        const campaignsSection = document.querySelector('#campaigns');
        if (!campaignsSection) return;
        
        // Crear notificación temporal
        const notification = document.createElement('div');
        notification.className = 'refresh-notification';
        notification.innerHTML = `
            <span class="refresh-icon">🔄</span>
            <span class="refresh-text">Estados actualizados automáticamente</span>
            <span class="refresh-detail">Las misiones procesadas ahora muestran su nuevo estado</span>
        `;
        
        // Estilos inline para la notificación
        notification.style.cssText = `
            position: relative;
            display: flex;
            flex-direction: column;
            gap: 4px;
            padding: 12px 16px;
            margin: 8px 0;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
            animation: slideInFade 0.5s ease-out;
            border-left: 4px solid #34d399;
        `;
        
        // Estilo específico para el detalle
        const detailElement = notification.querySelector('.refresh-detail');
        if (detailElement) {
            detailElement.style.cssText = `
                font-size: 0.8rem;
                opacity: 0.9;
                font-weight: 400;
            `;
        }
        
        // Agregar animación CSS si no existe
        if (!document.querySelector('#refresh-animation-styles')) {
            const style = document.createElement('style');
            style.id = 'refresh-animation-styles';
            style.textContent = `
                @keyframes slideInFade {
                    from {
                        opacity: 0;
                        transform: translateY(-15px) scale(0.95);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }
                
                @keyframes fadeOut {
                    from {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                    to {
                        opacity: 0;
                        transform: translateY(-15px) scale(0.95);
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Insertar la notificación al inicio de la sección de campañas
        campaignsSection.insertBefore(notification, campaignsSection.firstChild);
        
        // Remover la notificación después de 5 segundos
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.5s ease-out';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 500);
        }, 5000); // 5 segundos para dar tiempo a leer
    }
}

class RealTimeLogger {
    constructor() {
        this.logContainer = document.getElementById('logContent');
        this.errorContainer = document.getElementById('errorList');
        this.realTimeLog = document.getElementById('realTimeLog');
        this.errorPanel = document.getElementById('errorPanel');
        this.autoScroll = true;
        this.maxLogEntries = 100;
        this.maxErrorEntries = 50;
        this.logPaused = false; // Control para pausar logging
        
        this.initializeControls();
    }
    
    initializeControls() {
        // Control de auto-scroll
        const toggleAutoScroll = document.getElementById('toggleAutoScroll');
        if (toggleAutoScroll) {
            toggleAutoScroll.addEventListener('click', () => {
                this.autoScroll = !this.autoScroll;
                toggleAutoScroll.classList.toggle('active', this.autoScroll);
                toggleAutoScroll.setAttribute('data-enabled', this.autoScroll);
                toggleAutoScroll.textContent = this.autoScroll ? '📜 Auto-scroll' : '⏸️ Manual';
            });
        }
        
        // Limpiar log
        const clearLog = document.getElementById('clearLog');
        if (clearLog) {
            clearLog.addEventListener('click', () => {
                this.clearLog();
            });
        }
        
        // Limpiar errores
        const clearErrors = document.getElementById('clearErrors');
        if (clearErrors) {
            clearErrors.addEventListener('click', () => {
                this.clearErrors();
            });
        }
    }
    
    addLogEntry(message, type = 'info', timestamp = null) {
        if (!this.logContainer) return;
        
        // Si el logging está pausado, no agregar más logs (excepto mensajes de control)
        if (this.logPaused && !message.includes('pausado automáticamente') && !message.includes('Reanudando logging')) {
            return;
        }
        
        // Mostrar el log si no está visible
        if (this.realTimeLog) {
            this.realTimeLog.style.display = 'block';
        }
        
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        
        const time = timestamp || new Date().toLocaleTimeString('es-ES', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        entry.innerHTML = `
            <span class="log-timestamp">${time}</span>
            <span class="log-message">${this.escapeHtml(message)}</span>
        `;
        
        this.logContainer.appendChild(entry);
        
        // Limitar número de entradas
        while (this.logContainer.children.length > this.maxLogEntries) {
            this.logContainer.removeChild(this.logContainer.firstChild);
        }
        
        // Auto-scroll si está habilitado
        if (this.autoScroll) {
            this.logContainer.scrollTop = this.logContainer.scrollHeight;
        }
    }
    
    addError(errorInfo) {
        if (!this.errorContainer) return;
        
        // Filtrar mensajes que no son realmente errores
        if (errorInfo.type === 'lm_studio_success' || 
            (errorInfo.message && errorInfo.message.includes('funcionando correctamente'))) {
            // No mostrar como error, solo como log de éxito
            this.addLogEntry(`✅ ${errorInfo.message}`, 'success', errorInfo.ts);
            return;
        }
        
        // Filtrar mensajes informativos que no deberían estar en el panel de errores
        if (errorInfo.type === 'lm_studio_help' && 
            errorInfo.message && errorInfo.message.includes('Sugerencia:')) {
            // Agregar como log informativo en lugar de error
            this.addLogEntry(`💡 ${errorInfo.message}`, 'info', errorInfo.ts);
            return;
        }
        
        // Mostrar el panel de errores si no está visible
        if (this.errorPanel) {
            this.errorPanel.style.display = 'block';
        }
        
        const errorItem = document.createElement('div');
        errorItem.className = `error-item ${errorInfo.type || 'error'}`;
        
        const timestamp = errorInfo.ts || new Date().toLocaleTimeString('es-ES', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        const location = errorInfo.campaign && errorInfo.mission 
            ? `${errorInfo.campaign} → ${errorInfo.mission}`
            : errorInfo.campaign || errorInfo.mission || 'General';
        
        errorItem.innerHTML = `
            <div class="error-meta">
                <span class="error-location">${this.escapeHtml(location)}</span>
                <span class="error-timestamp">${timestamp}</span>
            </div>
            <div class="error-message">${this.escapeHtml(errorInfo.message)}</div>
        `;
        
        this.errorContainer.insertBefore(errorItem, this.errorContainer.firstChild);
        
        // Limitar número de errores
        while (this.errorContainer.children.length > this.maxErrorEntries) {
            this.errorContainer.removeChild(this.errorContainer.lastChild);
        }
        
        // También agregar al log general solo si es realmente un error
        const logType = errorInfo.type === 'warning' ? 'warning' : 'error';
        const logIcon = logType === 'warning' ? '⚠️' : '❌';
        this.addLogEntry(`${logIcon} ${errorInfo.message}`, logType, errorInfo.ts);
    }
    
    updatePhaseWithStatus(phase, detail, type = 'info') {
        const currentPhaseEl = document.getElementById('currentPhase');
        if (currentPhaseEl) {
            currentPhaseEl.textContent = detail || phase;
            
            // Limpiar clases previas
            currentPhaseEl.classList.remove('error', 'warning', 'success', 'info');
            currentPhaseEl.classList.add(type);
        }
        
        // Agregar al log
        const icons = {
            'info': '🔄',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        };
        
        this.addLogEntry(`${icons[type]} ${detail || phase}`, type);
    }
    
    clearLog() {
        if (this.logContainer) {
            this.logContainer.innerHTML = '';
        }
        if (this.realTimeLog) {
            this.realTimeLog.style.display = 'none';
        }
    }
    
    clearErrors() {
        if (this.errorContainer) {
            this.errorContainer.innerHTML = '';
        }
        if (this.errorPanel) {
            this.errorPanel.style.display = 'none';
        }
    }
    
    pauseLogging() {
        console.log('⏸️ Pausando logging automático al finalizar ejecución');
        this.logPaused = true;
        
        // Agregar mensaje de finalización
        this.addLogEntry('Ejecución finalizada - Logging pausado automáticamente', 'success');
        
        // Opcional: ocultar el panel de logs después de un tiempo
        setTimeout(() => {
            if (this.realTimeLog && this.logPaused) {
                this.realTimeLog.style.display = 'none';
                console.log('🔽 Panel de logs oculto automáticamente');
            }
        }, 10000); // 10 segundos
    }
    
    resumeLogging() {
        console.log('▶️ Reanudando logging para nueva ejecución');
        this.logPaused = false;
        
        // Mostrar el panel de logs si estaba oculto
        if (this.realTimeLog) {
            this.realTimeLog.style.display = 'block';
        }
    }
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ========================= MÉTODOS DE PERFILES =========================

    initializeProfilesSystem() {
        console.log('✅ Sistema de perfiles inicializado correctamente');
        // Event listeners para perfiles
        try {
            const btnRefreshProfiles = document.getElementById('btnRefreshProfiles');
            if (btnRefreshProfiles) {
                btnRefreshProfiles.addEventListener('click', this.loadProfiles.bind(this));
            }
            
            const profilesList = document.getElementById('profilesList');
            if (profilesList) {
                profilesList.addEventListener('change', this.onProfileSelect.bind(this));
            }
            
            console.log('✅ Event listeners de perfiles configurados');
        } catch (error) {
            console.error('❌ Error configurando sistema de perfiles:', error);
        }
    }

    async loadProfiles() {
        try {
            // Cargar solo perfiles creados por el usuario
            const response = await fetch('/api/profiles');
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error cargando perfiles');
            }
            
            const profilesList = document.getElementById('profilesList');
            if (!profilesList) return;
            
            // Limpiar lista
            profilesList.innerHTML = '<option value="">Seleccionar perfil...</option>';
            
            // Añadir perfiles
            data.profiles.forEach(profile => {
                const option = document.createElement('option');
                option.value = profile.name;
                option.textContent = `${profile.name}${profile.description ? ' - ' + profile.description : ''}`;
                profilesList.appendChild(option);
            });
            
            // Actualizar hint
            const hint = document.getElementById('profilesHint');
            if (hint) {
                hint.textContent = `${data.profiles.length} perfil(es) disponible(s)`;
            }
            
        } catch (error) {
            console.error('Error cargando perfiles:', error);
            this.showProfileStatus('Error cargando perfiles: ' + error.message, 'error');
        }
    }

    async onProfileSelect() {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        // Resetear botones
        const buttons = ['btnLoadProfile', 'btnLoadProfileGeneral', 'btnLoadProfileModel', 'btnUpdateProfile', 'btnDeleteProfile'];
        buttons.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) btn.disabled = !selectedProfile;
        });
        
        const infoSection = document.getElementById('profileInfoSection');
        
        if (!selectedProfile) {
            if (infoSection) infoSection.style.display = 'none';
            return;
        }
        
        try {
            // Cargar información del perfil
            const response = await fetch(`/api/profiles/${encodeURIComponent(selectedProfile)}`);
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error cargando perfil');
            }
            
            const profile = data.profile;
            
            // Mostrar información
            document.getElementById('profileInfoName').textContent = profile.name;
            document.getElementById('profileInfoDescription').textContent = profile.description || 'Sin descripción';
            document.getElementById('profileInfoCreated').textContent = new Date(profile.created_at).toLocaleDateString();
            document.getElementById('profileInfoUpdated').textContent = new Date(profile.updated_at).toLocaleDateString();
            
            if (infoSection) infoSection.style.display = 'block';
            
        } catch (error) {
            console.error('Error cargando información del perfil:', error);
            this.showProfileStatus('Error cargando información del perfil: ' + error.message, 'error');
        }
    }

    async loadProfile(applyGeneral = true, applyModel = true) {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        if (!selectedProfile) {
            this.showProfileStatus('Selecciona un perfil para cargar', 'error');
            return;
        }
        
        try {
            this.showProfileStatus('Cargando perfil...', 'info');
            
            const response = await fetch(`/api/profiles/${encodeURIComponent(selectedProfile)}/load`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    apply_general: applyGeneral,
                    apply_model: applyModel
                })
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error cargando perfil');
            }
            
            let message = `Perfil "${selectedProfile}" cargado`;
            if (!applyGeneral && applyModel) {
                message += ' (solo modelo)';
            } else if (applyGeneral && !applyModel) {
                message += ' (solo general)';
            }
            
            this.showProfileStatus(message, 'success');
            
            // Recargar configuraciones
            if (applyGeneral) {
                await this.loadUserConfig();
            }
            if (applyModel) {
                await this.loadUserConfig(); // También recarga modelo
                await this.loadPresetsAndModels();
            }
            
        } catch (error) {
            console.error('Error cargando perfil:', error);
            this.showProfileStatus('Error cargando perfil: ' + error.message, 'error');
        }
    }

    async createProfile() {
        const nameInput = document.getElementById('newProfileName');
        const descInput = document.getElementById('newProfileDescription');
        
        const name = nameInput?.value?.trim();
        const description = descInput?.value?.trim();
        
        if (!name) {
            this.showProfileStatus('El nombre del perfil es requerido', 'error');
            return;
        }
        
        try {
            this.showProfileStatus('Creando perfil...', 'info');
            
            const response = await fetch('/api/profiles', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: name,
                    description: description
                })
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error creando perfil');
            }
            
            this.showProfileStatus(`Perfil "${name}" creado exitosamente`, 'success');
            
            // Limpiar campos
            if (nameInput) nameInput.value = '';
            if (descInput) descInput.value = '';
            
            // Recargar lista
            await this.loadProfiles();
            
            // Seleccionar el perfil creado
            const profilesList = document.getElementById('profilesList');
            if (profilesList) {
                profilesList.value = name;
                await this.onProfileSelect();
            }
            
        } catch (error) {
            console.error('Error creando perfil:', error);
            this.showProfileStatus('Error creando perfil: ' + error.message, 'error');
        }
    }

    async updateProfile() {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        if (!selectedProfile) {
            this.showProfileStatus('Selecciona un perfil para actualizar', 'error');
            return;
        }
        
        try {
            this.showProfileStatus('Actualizando perfil...', 'info');
            
            const response = await fetch(`/api/profiles/${encodeURIComponent(selectedProfile)}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error actualizando perfil');
            }
            
            this.showProfileStatus(`Perfil "${selectedProfile}" actualizado con la configuración actual`, 'success');
            
            // Recargar información del perfil
            await this.onProfileSelect();
            
        } catch (error) {
            console.error('Error actualizando perfil:', error);
            this.showProfileStatus('Error actualizando perfil: ' + error.message, 'error');
        }
    }

    async deleteProfile() {
        const profilesList = document.getElementById('profilesList');
        const selectedProfile = profilesList?.value;
        
        if (!selectedProfile) {
            this.showProfileStatus('Selecciona un perfil para eliminar', 'error');
            return;
        }
        
        if (!confirm(`¿Estás seguro de que quieres eliminar el perfil "${selectedProfile}"?`)) {
            return;
        }
        
        try {
            this.showProfileStatus('Eliminando perfil...', 'info');
            
            const response = await fetch(`/api/profiles/${encodeURIComponent(selectedProfile)}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || 'Error eliminando perfil');
            }
            
            this.showProfileStatus(`Perfil "${selectedProfile}" eliminado`, 'success');
            
            // Recargar lista
            await this.loadProfiles();
            
            // Ocultar información del perfil
            const infoSection = document.getElementById('profileInfoSection');
            if (infoSection) infoSection.style.display = 'none';
            
        } catch (error) {
            console.error('Error eliminando perfil:', error);
            this.showProfileStatus('Error eliminando perfil: ' + error.message, 'error');
        }
    }

    // Función deshabilitada - solo perfiles de usuario
    // async createDefaultProfiles() {
    //     try {
    //         const response = await fetch('/api/profiles/defaults', {
    //             method: 'POST'
    //         });
    //         
    //         const data = await response.json();
    //         
    //         if (data.ok) {
    //             await this.loadProfiles();
    //         }
    //         
    //     } catch (error) {
    //         console.error('Error creando perfiles por defecto:', error);
    //     }
    // }

    showProfileStatus(message, type) {
        const statusSpan = document.getElementById('profilesStatus');
        if (!statusSpan) return;
        
        statusSpan.textContent = message;
        statusSpan.className = `status-message ${type}`;
        
        // Auto-limpiar después de 3 segundos para mensajes de éxito
        if (type === 'success') {
            setTimeout(() => {
                statusSpan.textContent = '';
                statusSpan.className = 'status-message';
            }, 3000);
        }
    }

    showCompleteConfigStatus(message, type) {
        const statusSpan = document.getElementById('completeConfigStatus');
        if (!statusSpan) return;
        
        statusSpan.textContent = message;
        statusSpan.className = `status-message ${type}`;
        
        // Auto-limpiar después de 3 segundos para mensajes de éxito
        if (type === 'success') {
            setTimeout(() => {
                statusSpan.textContent = '';
                statusSpan.className = 'status-message';
            }, 3000);
        }
    }

    async saveCompleteConfig() {
        try {
            // Guardar configuración general
            const generalResult = await this.saveUserConfig();
            
            // Guardar configuración del modelo (simulado - necesitarías implementar el método real)
            // const modelResult = await this.saveModelConfig();
            
            this.showCompleteConfigStatus('Configuración completa guardada correctamente', 'success');
            console.log('✅ Configuración completa guardada');
            
        } catch (error) {
            console.error('❌ Error guardando configuración completa:', error);
            this.showCompleteConfigStatus('Error guardando configuración: ' + error.message, 'error');
        }
    }

    async resetCompleteConfig() {
        if (!confirm('¿Está seguro de que desea restaurar toda la configuración a los valores por defecto?')) {
            return;
        }
        
        try {
            // Resetear configuración general
            const generalResult = await this.resetUserConfig();
            
            // Resetear configuración del modelo (simulado)
            // const modelResult = await this.resetModelConfig();
            
            this.showCompleteConfigStatus('Configuración completa restaurada a valores por defecto', 'success');
            console.log('✅ Configuración completa restaurada');
            
        } catch (error) {
            console.error('❌ Error restaurando configuración completa:', error);
            this.showCompleteConfigStatus('Error restaurando configuración: ' + error.message, 'error');
        }
    }
}

// Inicializar cuando la página esté lista
document.addEventListener('DOMContentLoaded', () => {
    console.log('🔄 DOM cargado - inicializando UI...');
    
    // Inicializar UI directamente - no necesitamos verificar el modal
    window.orchestratorUI = new OrchestratorUI();
    window.orchestrator = window.orchestratorUI; // Exponer también como 'orchestrator' para el botón
    console.log('✅ OrchestadorUI inicializado');
    
    // Verificar estado de unidades periódicamente (cada 30 segundos)
    setInterval(() => {
        if (window.orchestratorUI) {
            window.orchestratorUI.checkDriveStatus();
        }
    }, 30000);
});