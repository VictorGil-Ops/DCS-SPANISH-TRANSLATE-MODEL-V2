# Traducciones Generadas

Esta carpeta contiene todas las traducciones de campañas DCS generadas por el sistema automático.

## Estructura Típica

```
app/data/traducciones/
├── [Nombre_Campaña]/
│   ├── [Nombre_Misión]/
│   │   ├── extracted/           # Archivos extraídos del .miz
│   │   │   ├── l10n/DEFAULT/    # Diccionarios y recursos
│   │   │   ├── mission          # Archivo de misión
│   │   │   ├── options          # Opciones de la misión
│   │   │   └── warehouses       # Depósitos
│   │   ├── backup/              # Respaldo del .miz original
│   │   ├── finalizado/          # .miz reempaquetado y listo
│   │   ├── out_lua/             # Archivos .lua traducidos
│   │   │   ├── dictionary.translated.lua
│   │   │   ├── dictionary.placeholders.lua
│   │   │   └── translation_cache.json
│   │   └── mission_report_*.json # Reporte de traducción
│   └── ...
└── README.md
```

## Archivos Generados

### Por Misión:
- **extracted/**: Contenido del archivo .miz original
- **backup/**: Copia de seguridad del .miz original  
- **out_lua/**: Archivos Lua con las traducciones
- **finalizado/**: Archivo .miz final con traducciones integradas
- **mission_report_*.json**: Estadísticas y resultado de la traducción

### Archivos de Traducción:
- `dictionary.translated.lua` - Diccionario con traducciones aplicadas
- `dictionary.placeholders.lua` - Diccionario con placeholders para elementos no traducibles
- `translation_cache.json` - Cache local de traducciones para esa misión

## ⚠️ Importante

**Estos archivos NO se incluyen en el control de versiones** porque:

1. **Son generados automáticamente** por el sistema de traducción
2. **Contienen datos específicos del usuario** (rutas, configuraciones)
3. **Pueden ser muy grandes** (archivos .miz, audios .ogg, imágenes)
4. **Se regeneran** en cada ejecución del traductor
5. **Son temporales** y específicos de cada instalación

## Flujo de Trabajo

1. **TRADUCIR**: Extrae archivos → Traduce textos → Genera .lua
2. **REEMPAQUETAR**: Integra traducciones → Genera .miz final
3. **DESPLEGAR**: Copia .miz a la instalación de DCS World

## Limpieza

Para limpiar traducciones antiguas:
```bash
# Eliminar todas las traducciones
rm -rf app/data/traducciones/*

# Mantener solo la estructura
git checkout app/data/traducciones/.gitkeep
git checkout app/data/traducciones/README.md
```