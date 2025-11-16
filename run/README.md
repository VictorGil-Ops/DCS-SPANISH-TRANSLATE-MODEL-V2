# Carpeta Run - Scripts de Ejecución

Esta carpeta contiene todos los scripts de arranque y ejecución del DCS Orquestador Traductor.

## Archivos incluidos:

### 🚀 Scripts de Ejecución Principal
- **`run_orquestador.cmd`** - Script de arranque principal (Windows CMD)
- **`run_orquestador.ps1`** - Script de PowerShell para el orquestador legacy
- **`run_flask_app.py`** - Servidor Flask moderno con interfaz web

### � Archivos de Configuración del Sistema
- **`VERSION`** - 🔒 **ARCHIVO CRÍTICO** - Define la versión del sistema mostrada en la interfaz
- **`.gitkeep`** - Protege la carpeta y sus archivos en el repositorio Git
- **`README.md`** - Esta documentación
- **`requirements.txt`** - Dependencias específicas para ejecución

### �📁 Accesos Directos
- **Creación automática:** Ejecuta `run\create_shortcut.ps1` para generar automáticamente
- **Manual:** Crea un acceso directo a `run\run_orquestador.cmd` con icono `app\static\DCS_SPANISH.ico`
- **Nota:** Los archivos `.lnk` están en `.gitignore` (no se suben a GitHub)

## ⚠️ ARCHIVOS CRÍTICOS - NO ELIMINAR:

### 🔒 `VERSION`
- **Propósito:** Define la versión mostrada en la interfaz web
- **Contenido:** Número de versión actual (ej: "2.0")
- **Ubicación en código:** Leído por `config/settings.py`
- **⚠️ IMPORTANTE:** NO eliminar este archivo, la aplicación lo necesita para funcionar

### 🔒 `.gitkeep`
- **Propósito:** Mantiene la carpeta `run/` en el repositorio Git
- **Función:** Protege la carpeta y sus archivos críticos
- **⚠️ IMPORTANTE:** Asegura que los archivos del sistema no se pierdan

## Uso:

### Para ejecutar el servidor Flask moderno:
```bash
# Desde el directorio raíz del proyecto
python run/run_flask_app.py
# O usando el acceso directo
```

### Para ejecutar el orquestador legacy:
```bash
# Desde el directorio raíz del proyecto
run/run_orquestador.cmd
# O usando el acceso directo
```

## Características:

✅ **Detección automática de entorno virtual**  
✅ **Verificación de dependencias**  
✅ **Interfaz web moderna (Flask)**  
✅ **Compatibilidad con versión legacy**  
✅ **Configuración automática de rutas**  

## 🔗 Crear Acceso Directo:

### Automático (Recomendado):
```powershell
.\run\create_shortcut.ps1
```

### Manual:
1. Clic derecho en el escritorio → "Nuevo" → "Acceso directo"
2. Ubicación: `[ruta_del_proyecto]\run\run_orquestador.cmd`
3. Nombre: "Traductor - DCS"
4. Clic derecho en el acceso directo → "Propiedades" → "Cambiar icono"
5. Seleccionar: `[ruta_del_proyecto]\app\static\DCS_SPANISH.ico`

## Notas importantes:

- Todos los scripts están configurados para ejecutarse desde el directorio raíz del proyecto
- El servidor Flask moderno incluye una interfaz web completa en `http://localhost:5000`
- Los archivos `.lnk` no se suben a GitHub (están en `.gitignore`)
- Los accesos directos permiten ejecución rápida desde el explorador de archivos