# Configuración de Usuario

Esta carpeta contiene la configuración personal del usuario que no se debe incluir en el control de versiones.

## Configuración Inicial

1. **Copia el archivo de ejemplo:**

   ```bash
   cp user_config.json.example user_config.json
   ```

2. **Edita los valores según tu instalación:**
   - `ROOT_DIR`: Ruta a la carpeta de campañas de DCS World
   - `DEPLOY_DIR`: Ruta donde desplegar las traducciones (normalmente la misma que ROOT_DIR)
   - `lm_url`: URL de tu servidor LM Studio
   - `lm_model`: Nombre del modelo que estés usando
   - Otros parámetros según tus preferencias

## Archivos en esta carpeta

- `user_config.json.example` - Archivo de ejemplo con valores placeholder
- `user_config.json` - Tu configuración personal (ignorado por Git)
- `.gitkeep` - Mantiene la carpeta en Git

## ⚠️ Importante

El archivo `user_config.json` contiene rutas específicas de tu sistema y configuraciones personales, por lo que **NO debe subirse al repositorio**.

## Rutas Típicas de DCS World

### Steam

```text
D:\Steam\steamapps\common\DCSWorld\Mods\campaigns
```

### Standalone

```text
D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns
```