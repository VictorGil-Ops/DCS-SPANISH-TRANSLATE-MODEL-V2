# ARQUITECTURA DEFINITIVA - RAMA MAIN
## DCS Spanish Translator v2

**Fecha de documentación**: 19 de Octubre 2025  
**Rama**: `main`  
**Estado**: Arquitectura estable - Versión base sin funcionalidades experimentales

---

## 🎯 OBJETIVO DE LA APLICACIÓN

Traductor de misiones DCS World del inglés al español usando modelos de IA locales (LM Studio), con una interfaz web Flask para gestionar el proceso completo de traducción, extracción y reempaquetado.

---

## 📁 ESTRUCTURA DE DIRECTORIOS

### **Directorios Principales**
```
PROJECT_ROOT/
├── app/                          # Aplicación Flask principal
│   ├── __init__.py              # Factory app con blueprints básicos
│   ├── data/                    # Datos de la aplicación
│   ├── routes/                  # Blueprints de rutas
│   ├── services/                # Servicios y lógica de negocio
│   ├── static/                  # Recursos estáticos (CSS, JS)
│   ├── templates/               # Templates Jinja2
│   └── ui/                      # Componentes UI adicionales
├── config/                      # Configuración de la aplicación
├── run/                         # Scripts de ejecución
└── log_orquestador/            # Logs (legacy)
```

### **Directorio de Datos (app/data/)**
```
app/data/
├── promts/                      # Templates de prompts (YAML)
│   ├── 1-completions-PROMT.yaml
│   ├── 2-completions-PROMT.yaml
│   └── 3-completions-LLAMA-models.yaml
├── presets/                     # Configuraciones predefinidas (YAML)
│   ├── 1-preset-ligero.yaml
│   ├── 2-preset-balanceado.yaml
│   └── 3-preset-pesado.yaml
├── traducciones/               # Área de trabajo de traducciones
│   └── [CAMPAÑA]/             # Por cada campaña
│       └── [MISIÓN]/          # Por cada misión
│           ├── backup/        # Archivos originales
│           ├── extracted/     # Contenido extraído del .miz
│           ├── out_lua/       # Archivos traducidos
│           └── finalizado/    # .miz reempaquetados
├── logs/                       # Logs de aplicación
├── cache/                      # Cachés globales
└── my_config/                  # Configuración de usuario
    ├── user_config.json
    └── drives_status.json
```

---

## 🏗️ ARQUITECTURA DE LA APLICACIÓN

### **1. Aplicación Flask (app/__init__.py)**
- **Patrón**: Application Factory
- **Blueprints registrados**:
  - `main_bp` - Rutas principales (index, templates)
  - `api_bp` - API endpoints (prefijo `/api`)
- **Configuración**: Cargada desde `config/settings.py`
- **Logging**: Configurado con handlers para archivo y consola

### **2. Rutas y Blueprints (app/routes/)**

#### **main.py - Blueprint Principal**
- **Responsabilidad**: Servir templates HTML y páginas principales
- **Rutas principales**:
  - `/` - Página de inicio
  - `/models-presets` - Configuración de modelos
  - `/prompts` - Gestión de prompts
- **Templates**: Renderiza con Jinja2

#### **api.py - Blueprint API**
- **Responsabilidad**: Endpoints REST para operaciones
- **Endpoints principales**:
  - `/api/status` - Estado general del sistema
  - `/api/campaigns` - Gestión de campañas
  - `/api/models` - Información de modelos
  - `/api/presets` - Gestión de presets
  - `/api/prompts` - Gestión de prompts
- **Formato**: Respuestas JSON

### **3. Servicios Core (app/services/)**

#### **translation_engine.py - Motor Principal**
- **Responsabilidad**: Lógica central de traducción
- **Funcionalidades**:
  - Extracción de archivos .miz
  - Traducción usando LM Studio
  - Reempaquetado de misiones
  - Gestión de caché de traducciones
- **Integración**: LM Studio API
- **Patrones**: Singleton, Factory

#### **orchestrator.py - Orquestador**
- **Responsabilidad**: Coordinación de procesos de traducción
- **Funcionalidades**:
  - Gestión de flujos de trabajo
  - Monitoreo de progreso
  - Manejo de errores y reintentos
- **Estado**: Mantiene estado de operaciones activas

#### **Servicios de Datos**:
- `campaign_registry.py` - Registro y detección de campañas
- `dcs_campaigns.py` - Interfaz con campañas DCS
- `lm_studio.py` - Cliente para LM Studio
- `presets.py` - Gestión de configuraciones predefinidas
- `user_config.py` - Configuración de usuario
- `centralized_cache.py` - Sistema de caché centralizado

---

## 🔧 CONFIGURACIÓN (config/settings.py)

### **Directorios Principales**
```python
BASE_DIR = "Directorio raíz del proyecto"
APP_DIR = "app/"
DATA_DIR = "app/data/"

# Directorios de datos
PROMPTS_DIR = "app/data/promts/"      # Templates de prompts
PRESETS_DIR = "app/data/presets/"    # Configuraciones predefinidas
TRANSLATIONS_DIR = "app/data/traducciones/"  # Área de trabajo
LOGS_DIR = "app/data/logs/"          # Logs de aplicación
MY_CONFIG_DIR = "app/data/my_config/" # Configuración usuario
```

### **Configuración Flask**
```python
FLASK_CONFIG = {
    'SECRET_KEY': 'clave-secreta-generada',
    'DEBUG': False,
    'TESTING': False
}
```

### **Configuración de Logging**
```python
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_path': 'app/data/logs/application.log'
}
```

---

## 🎨 FRONTEND (app/static/ y app/templates/)

### **Templates Jinja2**
- `base.html` - Template base con layout común
- `modern-base.html` - Template moderno con estilos actualizados
- `index.html` - Página principal
- `models-presets.html` - Configuración de modelos y presets
- `prompts.html` - Gestión de prompts
- `orchestrator/index.html` - Interfaz del orquestador

### **Recursos Estáticos**
```
app/static/
├── css/
│   ├── main.css               # Estilos principales
│   ├── modern-theme.css       # Tema moderno
│   └── modal.css              # Estilos para modales
├── js/
│   ├── main.js               # JavaScript principal
│   └── modern-theme.js       # Funcionalidad del tema moderno
└── favicon_placeholder.txt
```

---

## 🗄️ SISTEMA DE DATOS

### **Configuraciones (YAML)**
- **Presets**: Configuraciones predefinidas para diferentes niveles de traducción
- **Prompts**: Templates de prompts para diferentes modelos de IA
- **Formato**: YAML con estructura específica para cada tipo

### **Área de Trabajo de Traducciones**
```
app/data/traducciones/
└── [CAMPAÑA]/                 # Ej: F-5E_BFM
    └── [MISIÓN]/              # Ej: F-5E_-_Arrival
        ├── backup/            # Archivo .miz original
        ├── extracted/         # Contenido descomprimido
        ├── out_lua/          # Archivos Lua traducidos
        │   ├── dictionary.translated.lua
        │   ├── dictionary.translations.jsonl
        │   └── translation_cache.json
        └── finalizado/        # .miz final reempaquetado
```

### **Configuración de Usuario**
- `app/data/my_config/user_config.json` - Preferencias del usuario
- `app/data/my_config/drives_status.json` - Estado de unidades detectadas

---

## 🔗 INTEGRACIÓN CON LM STUDIO

### **Endpoints Utilizados**
- `GET /v1/models` - Lista de modelos disponibles
- `POST /v1/chat/completions` - Chat completions
- `POST /v1/completions` - Text completions

### **Configuración**
- **URL por defecto**: `http://localhost:1234`
- **Timeout**: Configurable por preset
- **Headers**: Content-Type: application/json
- **Autenticación**: Bearer token (opcional)

---

## 📊 FLUJO DE TRABAJO

### **1. Detección de Campañas**
1. Escaneo de directorio DCS World
2. Detección de archivos .miz
3. Registro en `campaign_registry.py`
4. Caché en `app/data/my_config/`

### **2. Proceso de Traducción**
1. **Extracción**: .miz → `extracted/`
2. **Backup**: Copia original → `backup/`
3. **Traducción**: Lua files → LM Studio → `out_lua/`
4. **Reempaquetado**: Archivos traducidos → `finalizado/`

### **3. Gestión de Estado**
- Estado global en memoria
- Caché persistente en archivos JSON
- Logs detallados de operaciones
- Recovery automático de errores

---

## 🔒 REGLAS DE ARQUITECTURA

### **❌ NUNCA HACER:**
1. Modificar archivos en directorio DCS original
2. Mezclar rutas de DCS con rutas de trabajo
3. Hardcodear nombres de archivos específicos en servicios
4. Ignorar manejo de errores en operaciones de archivo
5. Crear dependencias circulares entre servicios

### **✅ SIEMPRE HACER:**
1. Usar paths absolutos para operaciones de archivo
2. Validar existencia de directorios antes de uso
3. Manejar excepciones en operaciones I/O
4. Mantener separación clara entre datos y lógica
5. Documentar cambios en servicios core

### **🔧 PATRONES ESTABLECIDOS:**
1. **Factory Pattern**: Para creación de app Flask
2. **Blueprint Pattern**: Para organización de rutas
3. **Service Layer**: Para lógica de negocio
4. **Repository Pattern**: Para acceso a datos
5. **Singleton**: Para servicios globales (cuando aplique)

---

## 🚀 EJECUCIÓN Y DESPLIEGUE

### **Scripts de Ejecución (run/)**
- `run_flask_app.py` - Script principal de la aplicación
- `run_orquestador.cmd` - Ejecutor para Windows (CMD)
- `run_orquestador.ps1` - Ejecutor para Windows (PowerShell)

### **Requisitos del Sistema**
- Python 3.8+
- Flask y dependencias (requirements.txt)
- LM Studio ejecutándose en puerto 1234
- Acceso a directorio de DCS World

### **Variables de Entorno**
```bash
LMSTUDIO_API_KEY=optional_api_key
FLASK_ENV=production
FLASK_DEBUG=False
```

---

## 📝 NOTAS DE MANTENIMIENTO

### **Archivos Críticos (NO MODIFICAR SIN CUIDADO)**
- `app/__init__.py` - Factory principal
- `config/settings.py` - Configuración base
- `app/services/translation_engine.py` - Motor core
- `app/services/orchestrator.py` - Coordinador principal

### **Extensibilidad**
- **Nuevos modelos**: Agregar detección en `translation_engine.py`
- **Nuevos endpoints**: Crear en `app/routes/api.py`
- **Nuevas páginas**: Agregar rutas en `app/routes/main.py`
- **Nuevos servicios**: Crear en `app/services/`

### **Debugging**
- Logs en `app/data/logs/application.log`
- Debug info en consola cuando `DEBUG=True`
- Estado de servicios via `/api/status`

---

## ⚠️ ARQUITECTURA ESTABLE

Esta es la **versión base estable** de la aplicación. Todas las funcionalidades experimentales o en desarrollo se deben realizar en ramas separadas para mantener la integridad de `main`.

---

## 🔄 MEJORAS DE PROGRESO Y MODOS DE EJECUCIÓN

### **Actualización**: 20 de Octubre 2025 - Merge de rama `3_repack`

### **Sistema de Progreso en Tiempo Real**

#### **Problemas Solucionados**
- **Progreso UI**: Las actualizaciones de progreso no se mostraban en tiempo real
- **Contadores**: Los modos reempaquetado y deploy mostraban "0 misión(es)" incorrectamente
- **Reportes**: Falta de reportes detallados por misión en modos reempaquetado/deploy
- **Selección**: Deploy procesaba todas las misiones en lugar de solo las seleccionadas

#### **Implementaciones Realizadas**

##### **1. Callbacks de Progreso (`orchestrator.py` y `translation_engine.py`)**
```python
def progress_callback(mission_name: str, campaign_name: str, success: bool = None):
    """
    Callback para reportar progreso en tiempo real:
    - success=None: Misión iniciando
    - success=True: Misión completada exitosamente  
    - success=False: Misión falló
    """
    if success is None:
        self.status['current_mission'] = mission_name
        self.status['detail'] = f'Procesando: {mission_name}'
    else:
        self._update_mission_progress(mission_name, campaign_name, success)
```

##### **2. Corrección de Contadores por Modo**

**Problema Original**: Solo se procesaban resultados de `translate_results`, ignorando `miz_results` y `deploy_results` en modos únicos.

**Solución Implementada** (`orchestrator.py` líneas 904-950):
```python
# Si es modo solo empaquetado, crear misiones desde miz_results
if mode in ('miz', 'reempaquetar') and not workflow_result.get('translate_results'):
    for package in miz_res.get('package_results', []):
        all_missions.append({
            'mission': mission_name,
            'packaged': package.get('success', False),
            'success': package.get('success', False),
            # ... datos completos de la misión
        })
        if package.get('success', False):
            successful_missions += 1
        else:
            failed_missions += 1
        total_missions += 1

# Similar implementación para modo deploy
if mode in ('deploy', 'desplegar') and not workflow_result.get('translate_results'):
    # Procesamiento específico para deploy_results
```

##### **3. Polling Frontend Mejorado (`orchestrator.js`)**

**Cambios Implementados**:
- **Frecuencia aumentada**: 2s → 1s para mejor experiencia
- **Lógica de visualización corregida**: Mostrar progreso durante Y después de ejecución
- **Actualización inmediata**: Forzar poll inmediato al iniciar ejecución
- **Debug logging**: Trazabilidad completa de actualizaciones

```javascript
showCurrentProgressCard(status) {
    // ANTES: Solo mostrar si is_running = true
    // DESPUÉS: Mostrar si hay datos relevantes
    const hasProgressData = status.missions_total > 0 || 
                           status.missions_processed > 0 || 
                           status.is_running ||
                           status.current_mission;
    
    if (hasProgressData) {
        // Actualizar SIEMPRE que tengamos datos
        this.updateCurrentStats(status);
    }
}
```

##### **4. Generación de Reportes por Misión**

**Reempaquetado** (`_execute_miz_phase`):
```python
# Para cada misión procesada
package_result = {
    'mission': mission_file,
    'success': True,
    'mode': 'reempaquetado',
    'translated_file': base_name,
    'output_miz': final_miz,
    'output_files': {
        'output_miz': final_miz,
        'backup_miz': backup_path,
        'translated_lua': translated_file
    }
}
self._generate_mission_report(campaign_name, mission_file, package_result, config)
```

**Deploy** (`_execute_deploy_phase`):
```python
# Para cada archivo deployado
deploy_result = {
    'mission': file_name,
    'success': True,
    'mode': 'deploy',
    'deployed_to': dest_file,
    'backup_created': backup_created,
    'overwrite_mode': deploy_overwrite,
    'output_files': {
        'deployed_miz': dest_file,
        'backup_miz': backup_path if backup_created else None
    }
}
self._generate_mission_report(campaign_name, file_name, deploy_result, config)
```

### **Sistema de Deploy Mejorado**

#### **Funcionalidad de Sobrescribir**

**Configuración por Modo**:
```python
if deploy_overwrite:
    # Sobrescribir: reemplazar misiones originales
    dest_dir = campaign_path
    backup_dir = os.path.join(campaign_path, "_backup_missions")
else:
    # No sobrescribir: crear nueva carpeta
    dest_dir = os.path.join(campaign_path, "Translated_ES")
    backup_dir = None
```

**Proceso de Backup Automático**:
1. **Detección**: Si existe archivo original en destino
2. **Backup**: Copia a `_backup_missions/` antes de reemplazar
3. **Reemplazo**: Archivo traducido reemplaza el original
4. **Logging**: Registro detallado de operaciones

#### **Selección Específica de Misiones**

**Problema**: Deploy procesaba todos los archivos finalizados.
**Solución**: Filtrado por misiones seleccionadas.

```python
# Buscar archivos finalizados solo para las misiones seleccionadas
selected_missions = config.get('missions', [])
for mission_file in selected_missions:
    mission_slug = self.slugify(mission_name)
    mission_finalized_pattern = os.path.join(
        campaign_dirs["base"], mission_slug, "finalizado", mission_file
    )
    matching_files = glob.glob(mission_finalized_pattern)
    if matching_files:
        finalized_files.extend(matching_files)
```

#### **Confirmaciones de Seguridad (Frontend)**

**Modal de Confirmación Mejorado**:
```javascript
// Información específica para deploy
if (mode === 'desplegar') {
    const isOverwrite = this.getElementValue('userDeployOverwrite') === 'true';
    
    // Advertencia previa para sobrescribir
    if (isOverwrite) {
        const overwriteConfirm = confirm(
            '⚠️ ADVERTENCIA: Sobrescribir archivos existentes\n\n' +
            'Se creará una copia de seguridad automática en "_backup_missions".'
        );
        if (!overwriteConfirm) return;
    }
    
    // Modal con información detallada
    document.getElementById('confirmOverwrite').textContent = 
        isOverwrite ? '⚠️ SÍ (con backup)' : '✅ NO (nueva carpeta)';
    
    // Botón visual diferenciado
    if (isOverwrite) {
        executeBtn.style.backgroundColor = '#e74c3c';
        executeBtn.textContent = '⚠️ Ejecutar (Sobrescribir)';
    }
}
```

### **Estructura de Archivos por Modo**

#### **Modo Traducir**
```
traducciones/CAMPAÑA/MISIÓN/
├── backup/           # MIZ original
├── extracted/        # Contenido descomprimido  
├── out_lua/         # Archivos traducidos
└── finalizado/      # MIZ reempaquetado
```

#### **Modo Reempaquetar** 
- **Input**: `out_lua/*.translated.lua`
- **Output**: `finalizado/*.miz` (reempaquetado)
- **Reports**: Detalle por misión en UI

#### **Modo Deploy**
```
# Con sobrescribir:
CAMPAÑA/
├── mission.miz              # ← Archivo reemplazado
└── _backup_missions/
    └── mission.miz          # ← Backup automático

# Sin sobrescribir:
CAMPAÑA/
├── mission.miz              # Original intacto
└── Translated_ES/
    └── mission.miz          # ← Nueva versión
```

### **Compatibilidad y Mantenimiento**

#### **Archivos Modificados**
- ✅ `app/services/orchestrator.py` - Sistema de progreso y contadores
- ✅ `app/services/translation_engine.py` - Callbacks y reportes
- ✅ `app/static/js/orchestrator.js` - UI en tiempo real
- ✅ `app/templates/orchestrator/index.html` - Modal mejorado

### **6. Sistema de Deploy Corregido (Octubre 2025)**

El sistema de deploy ha sido completamente corregido para manejar correctamente la sobrescritura de misiones y la creación de backups.

#### **Funcionalidad Corregida**

**Antes (Problemático):**
- Creaba carpeta `Translated_ES` incluso con sobrescribir activado
- No creaba directorio `_backup_missions`
- Lógica de deploy confusa

**Después (Corregido):**
- ✅ **DEPLOY_OVERWRITE = true**: Sobrescribe misiones originales + backup en `_backup_missions`
- ✅ **DEPLOY_OVERWRITE = false**: Crea carpeta `Translated_ES` sin tocar originales

#### **Arquitectura Deploy**

```python
def _execute_deploy_phase(config, campaign_dirs):
    deploy_overwrite = config.get('deploy_overwrite', False)
    
    if deploy_overwrite:
        # Modo sobrescribir: reemplazar originales
        dest_dir = campaign_path
        backup_dir = os.path.join(campaign_path, "_backup_missions")
        
        # Crear backup antes de sobrescribir
        if os.path.exists(dest_file):
            backup_path = os.path.join(backup_dir, file_name)
            shutil.copy2(dest_file, backup_path)
    else:
        # Modo seguro: nueva carpeta
        dest_dir = os.path.join(campaign_path, "Translated_ES")
        backup_dir = None
```

#### **Refactorización LMStudioService**

Movidas todas las funciones de gestión de LM Studio al servicio dedicado:

```python
# ANTES: Funciones dispersas en TranslationEngine
class TranslationEngine:
    def get_loaded_models(self): ...
    def unload_current_model(self): ...
    def try_load_lm_studio_model(self): ...

# DESPUÉS: Centralizadas en LMStudioService
class LMStudioService:
    def get_loaded_models(self): ...
    def unload_current_model(self): ...
    def load_model_via_cli(self):  # Mejorada con gestión inteligente
        # Verificación automática de modelos cargados
        # Descarga automática antes de cargar nuevo
        # Evita recargas innecesarias
```

#### **Archivos Modificados**
- ✅ `app/services/lm_studio.py` - Gestión inteligente de modelos
- ✅ `app/services/orchestrator.py` - Deploy directo mejorado
- ✅ `app/services/translation_engine.py` - Limpieza y uso de LMStudioService

#### **Retrocompatibilidad**
- ✅ Mantiene funcionalidad existente de traducción
- ✅ No afecta estructura de datos legacy
- ✅ Compatible con configuraciones existentes

#### **Testing**
- ✅ Modo Traducir: Funcionalidad original preservada
- ✅ Modo Reempaquetar: Contadores y reportes correctos  
- ✅ Modo Deploy: Selección específica y backup funcionando
- ✅ Deploy con sobrescribir: Backup en `_backup_missions` funcionando
- ✅ Deploy sin sobrescribir: Carpeta `Translated_ES` funcionando

---

**Última actualización**: 20 de Octubre 2025  
**Versión documentada**: Rama `main` - Estado estable con mejoras de progreso y deploy integradas