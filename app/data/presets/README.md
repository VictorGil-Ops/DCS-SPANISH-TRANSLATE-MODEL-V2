# Carpeta de Presets

Esta carpeta almacena las configuraciones predefinidas de la aplicación.

## Estructura

- `*.json` - Archivos de configuración de presets
- `default.json` - Preset por defecto del sistema

## Uso

Los presets permiten guardar y cargar configuraciones completas de traducción, incluyendo:
- Rutas de DCS
- Configuración del modelo de lenguaje
- Parámetros de traducción
- Campañas seleccionadas

## Ejemplo de preset

```json
{
  "name": "Configuración Básica",
  "dcs_path": "D:\\Program Files\\Eagle Dynamics\\DCS World\\Mods\\campaigns",
  "lm_url": "http://localhost:1234/v1",
  "lm_model": "llama-2-7b-chat",
  "batch_size": 4,
  "timeout": 200,
  "created": "2025-10-09T12:00:00Z"
}
```