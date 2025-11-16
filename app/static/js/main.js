/**
 * DCS Spanish Translator - JavaScript Principal
 */

class DCSTranslator {
    constructor() {
        this.isRunning = false;
        this.currentRequestId = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadInitialData();
        this.startStatusPolling();
    }

    bindEvents() {
        // Botones principales
        document.getElementById('btnScanCampaigns')?.addEventListener('click', () => this.scanCampaigns());
        document.getElementById('btnRun')?.addEventListener('click', () => this.runTranslation());
        document.getElementById('btnCancel')?.addEventListener('click', () => this.cancelTranslation());
        
        // Auto scan
        document.getElementById('btnAutoScan')?.addEventListener('click', () => this.autoRootScan());
        
        // Actualización
        document.getElementById('btnCheckUpdate')?.addEventListener('click', () => this.checkUpdates());
        document.getElementById('btnUpdate')?.addEventListener('click', () => this.updateApp());
        
        // Presets
        document.getElementById('btnPreset1')?.addEventListener('click', () => this.loadPreset(1));
        document.getElementById('btnPreset2')?.addEventListener('click', () => this.loadPreset(2));
        
        // Modales
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-backdrop')) {
                this.closeModal(e.target.closest('.modal'));
            }
        });
    }

    async loadInitialData() {
        try {
            await Promise.all([
                this.loadLMModels(),
                this.loadPrompts(),
                this.updateStatus()
            ]);
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    async loadLMModels() {
        try {
            const response = await fetch('/api/lm_models');
            const data = await response.json();
            this.populateSelect('lmModel', data.models || []);
        } catch (error) {
            console.error('Error loading LM models:', error);
        }
    }

    async loadPrompts() {
        try {
            const response = await fetch('/api/promts');
            const data = await response.json();
            this.populateSelect('promptFile', data.promts || []);
        } catch (error) {
            console.error('Error loading prompts:', error);
        }
    }

    populateSelect(selectId, options) {
        const select = document.getElementById(selectId);
        if (!select) return;

        select.innerHTML = '<option value="">Seleccione...</option>';
        options.forEach(option => {
            const optElement = document.createElement('option');
            optElement.value = option.value || option;
            optElement.textContent = option.label || option;
            select.appendChild(optElement);
        });
    }

    async scanCampaigns() {
        const dcsPath = document.getElementById('dcsPath')?.value;
        if (!dcsPath) {
            this.showError('Por favor, especifica la ruta de DCS');
            return;
        }

        try {
            const response = await fetch('/api/scan_campaigns', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dcs_path: dcsPath })
            });

            const data = await response.json();
            this.updateCampaignsList(data.campaigns || []);
        } catch (error) {
            console.error('Error scanning campaigns:', error);
            this.showError('Error al escanear campañas: ' + error.message);
        }
    }

    updateCampaignsList(campaigns) {
        const container = document.getElementById('campaignsList');
        if (!container) return;

        container.innerHTML = '';
        campaigns.forEach(campaign => {
            const item = document.createElement('div');
            item.className = 'campaign-item';
            item.innerHTML = `
                <label>
                    <input type="checkbox" value="${campaign.path}" data-name="${campaign.name}">
                    ${campaign.name} <span class="muted">(${campaign.missions_count} misiones)</span>
                </label>
            `;
            container.appendChild(item);
        });
    }

    async runTranslation() {
        if (this.isRunning) return;

        const config = this.getTranslationConfig();
        if (!this.validateConfig(config)) return;

        try {
            this.isRunning = true;
            this.updateRunButton(true);

            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await response.json();
            this.currentRequestId = data.request_id;
        } catch (error) {
            console.error('Error running translation:', error);
            this.showError('Error al iniciar traducción: ' + error.message);
            this.isRunning = false;
            this.updateRunButton(false);
        }
    }

    getTranslationConfig() {
        const selectedCampaigns = Array.from(
            document.querySelectorAll('#campaignsList input:checked')
        ).map(cb => ({
            path: cb.value,
            name: cb.dataset.name
        }));

        return {
            dcs_path: document.getElementById('dcsPath')?.value,
            lm_url: document.getElementById('lmUrl')?.value,
            lm_model: document.getElementById('lmModel')?.value,
            prompt_file: document.getElementById('promptFile')?.value,
            campaigns: selectedCampaigns,
            max_concurrent: parseInt(document.getElementById('maxConcurrent')?.value) || 2,
            retry_limit: parseInt(document.getElementById('retryLimit')?.value) || 3
        };
    }

    validateConfig(config) {
        if (!config.dcs_path) {
            this.showError('Ruta de DCS es requerida');
            return false;
        }
        if (!config.lm_url) {
            this.showError('URL de LM Studio es requerida');
            return false;
        }
        if (config.campaigns.length === 0) {
            this.showError('Selecciona al menos una campaña');
            return false;
        }
        return true;
    }

    async cancelTranslation() {
        if (!this.isRunning) return;

        try {
            const response = await fetch('/api/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request_id: this.currentRequestId })
            });

            if (response.ok) {
                this.isRunning = false;
                this.currentRequestId = null;
                this.updateRunButton(false);
            }
        } catch (error) {
            console.error('Error cancelling translation:', error);
        }
    }

    async autoRootScan() {
        try {
            const response = await fetch('/api/auto_root_scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();
            if (data.suggested_path) {
                document.getElementById('dcsPath').value = data.suggested_path;
                await this.scanCampaigns();
            }
        } catch (error) {
            console.error('Error in auto scan:', error);
        }
    }

    startStatusPolling() {
        // Solo iniciar polling si no estamos en la página del orquestador
        // (que tiene su propio sistema de polling más avanzado)
        const currentPath = window.location.pathname;
        console.log(`🔍 DEBUG: Verificando URL para polling: '${currentPath}'`);
        
        if (currentPath.includes('/orchestrator') || currentPath.includes('/orquestador')) {
            console.log('🔄 Polling de main.js DESHABILITADO: detectada página del orquestador');
            return;
        }
        
        // También verificar si ya existe un orquestador UI
        if (window.orchestratorUI || window.OrchestratorUI) {
            console.log('🔄 Polling de main.js DESHABILITADO: OrquestratorUI ya existe');
            return;
        }
        
        console.log('🔄 Iniciando polling de main.js cada 5 segundos');
        this.statusPollingInterval = setInterval(() => this.updateStatus(), 5000);
    }

    async updateStatus() {
        try {
            console.log('🔔 DEBUG: main.js - Actualizando estado via /api/status (MAIN.JS)');
            const response = await fetch('/api/status');
            const data = await response.json();
            this.displayStatus(data);
        } catch (error) {
            console.error('Error updating status:', error);
        }
    }

    displayStatus(status) {
        const statusElement = document.getElementById('status');
        if (!statusElement) return;

        if (status.is_running) {
            this.isRunning = true;
            this.updateRunButton(true);
            this.updateProgress(status.progress || 0);
        } else if (this.isRunning) {
            this.isRunning = false;
            this.updateRunButton(false);
        }
    }

    updateProgress(progress) {
        const progressBar = document.querySelector('.progress > div');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
    }

    updateRunButton(running) {
        const btnRun = document.getElementById('btnRun');
        const btnCancel = document.getElementById('btnCancel');
        
        if (btnRun) {
            btnRun.textContent = running ? 'Traduciendo...' : 'Iniciar Traducción';
            btnRun.disabled = running;
        }
        
        if (btnCancel) {
            btnCancel.style.display = running ? 'inline-block' : 'none';
        }
    }

    async loadPreset(presetNumber) {
        try {
            // Obtener URL de LM Studio desde la configuración del usuario
            const lmUrlResponse = await fetch('/api/lm_studio_url');
            const lmUrlData = await lmUrlResponse.json();
            const userLmUrl = lmUrlData.success ? lmUrlData.lm_url : 'http://localhost:1234/v1';
            
            const presets = {
                1: {
                    lmUrl: userLmUrl,
                    maxConcurrent: 2,
                    retryLimit: 3
                },
                2: {
                    lmUrl: userLmUrl,
                    maxConcurrent: 1,
                    retryLimit: 5
                }
            };

            const preset = presets[presetNumber];
            if (!preset) return;

            Object.entries(preset).forEach(([key, value]) => {
                const element = document.getElementById(key);
                if (element) element.value = value;
            });
        } catch (error) {
            console.error('Error loading preset:', error);
            // Fallback a valores por defecto
            const presets = {
                1: { lmUrl: 'http://localhost:1234/v1', maxConcurrent: 2, retryLimit: 3 },
                2: { lmUrl: 'http://localhost:1234/v1', maxConcurrent: 1, retryLimit: 5 }
            };
            const preset = presets[presetNumber];
            if (preset) {
                Object.entries(preset).forEach(([key, value]) => {
                    const element = document.getElementById(key);
                    if (element) element.value = value;
                });
            }
        }
    }

    async checkUpdates() {
        try {
            const response = await fetch('/api/update_info');
            const data = await response.json();
            this.displayUpdateInfo(data);
        } catch (error) {
            console.error('Error checking updates:', error);
        }
    }

    displayUpdateInfo(updateInfo) {
        // TODO: Implementar display de información de actualización
        console.log('Update info:', updateInfo);
    }

    async updateApp() {
        if (!confirm('¿Estás seguro de que deseas actualizar la aplicación?')) {
            return;
        }

        try {
            const response = await fetch('/api/update_now', {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                alert('Actualización iniciada. La aplicación se reiniciará.');
            }
        } catch (error) {
            console.error('Error updating app:', error);
            this.showError('Error durante la actualización: ' + error.message);
        }
    }

    showError(message) {
        // TODO: Implementar mejor sistema de notificaciones
        alert(message);
    }

    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('open');
        }
    }

    closeModal(modal) {
        if (modal) {
            modal.classList.remove('open');
        }
    }
}

// Inicializar la aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.dcsTranslator = new DCSTranslator();
});