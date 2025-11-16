# Carpeta de Despliegue

## ¿Qué es la carpeta de despliegue?

Es la **carpeta destino** donde se guardarán las campañas traducidas. Aquí se almacenan las versiones en español de tus campañas de DCS, listas para usar.

## ¿Por qué es importante?

✅ **Organización**: Mantiene separadas las versiones originales y traducidas  
✅ **Seguridad**: Preserva los archivos originales intactos  
✅ **Gestión**: Facilita instalar/desinstalar traducciones  
✅ **Respaldo**: Permite tener múltiples versiones  

## Ubicaciones recomendadas

### 🎯 **Opción 1: Carpeta dedicada (RECOMENDADO)**
```
C:\Users\[TuNombre]\Documents\DCS-Traducciones\
```
**Ventajas:**
- ✅ Fácil de encontrar y gestionar
- ✅ No interfiere con DCS
- ✅ Fácil respaldo y sincronización

### 🔄 **Opción 2: Junto a DCS (solo usuarios avanzados)**
```
C:\Program Files\Eagle Dynamics\DCS World\Campaigns-ES\
```
**Ventajas:**
- ✅ Integración directa con DCS
- ✅ Instalación automática

**Desventajas:**
- ⚠️ Riesgo de sobrescribir archivos originales
- ⚠️ Se puede perder con actualizaciones de DCS

### 🏠 **Opción 3: Carpeta personalizada**
```
D:\Mis-Traducciones-DCS\
E:\Gaming\DCS-Spanish\
```
**Ideal para:**
- Usuarios con múltiples discos
- Configuraciones de red
- Servidores dedicados

## Estructura de carpetas generada

Cuando traduces, se crea automáticamente:

```
📁 Carpeta-Despliegue/
├── 📁 [Nombre-Campaña]/
│   ├── 📄 [archivo-original].miz
│   ├── 📄 [archivo-traducido].lua
│   └── 📁 l10n/
│       └── 📄 dictionary.lua
└── 📁 logs/
    ├── 📄 translation-log.txt
    └── 📄 errors.log
```

## ¿Cómo configurarla?

### 🚀 **Configuración automática**
1. **Deja el campo vacío** al inicio
2. El traductor te **sugerirá una ubicación**
3. **Acepta la sugerencia** o modifícala

### ⚙️ **Configuración manual**
1. **Haz clic en "Examinar"**
2. **Navega** hasta donde quieres guardar las traducciones
3. **Crea una carpeta nueva** si es necesario
4. **Selecciona la carpeta** y confirma

### 📝 **Escribir la ruta manualmente**
```
C:\Users\TuNombre\Documents\DCS-Traducciones
```
**Nota**: Usa barras normales `/` o dobles `\\`, no barras simples `\`

## Verificación de la carpeta

### ✅ **Antes de traducir, verifica que**
- La carpeta existe y es accesible
- Tienes permisos de escritura
- Hay suficiente espacio libre (mín. 1GB)
- La ruta no tiene caracteres especiales

### 🔍 **El traductor verificará automáticamente**
- ✅ Permisos de escritura
- ✅ Espacio disponible
- ✅ Validez de la ruta
- ✅ Conflictos con archivos existentes

## Gestión de traducciones

### 📦 **Instalación en DCS**
Una vez traducido:
1. **Ve a la carpeta de despliegue**
2. **Busca la carpeta de tu campaña**
3. **Copia los archivos traducidos**
4. **Pégalos en** `DCS World/Campaigns/`

### 🔄 **Actualización de traducciones**
- Las nuevas traducciones **sobrescriben** las anteriores
- Los logs mantienen **historial** de cambios
- Puedes **revertir** usando los archivos originales

### 🗑️ **Limpieza de espacio**
- Borra carpetas de traducciones antiguas
- Mantén solo las versiones que uses
- Los logs se pueden comprimir o eliminar

## Resolución de problemas

### ❌ **"No se puede escribir en la carpeta"**
- **Ejecuta como administrador** si la carpeta está en Program Files
- **Verifica permisos** de la carpeta
- **Cambia a una carpeta** en tu perfil de usuario

### ❌ **"La ruta no existe"**
- **Verifica que escribiste** la ruta correctamente
- **Crea la carpeta manualmente** si es necesario
- **Usa el botón "Examinar"** para navegar

### ❌ **"Espacio insuficiente"**
- **Libera espacio** en el disco
- **Cambia a un disco** con más espacio libre
- **Elimina traducciones** antiguas que no uses

### ❌ **"Archivos en uso"**
- **Cierra DCS World** antes de traducir
- **Cierra editores** que tengan archivos abiertos
- **Reinicia** si el problema persiste

## Consejos profesionales

### 🎯 **Para principiantes**
- Usa la ubicación sugerida automáticamente
- No cambies la carpeta durante un proceso de traducción
- Haz respaldo de traducciones importantes

### ⚙️ **Para usuarios avanzados**
- Configura diferentes carpetas para diferentes tipos de campañas
- Usa enlaces simbólicos para integración automática con DCS
- Automatiza la instalación con scripts de PowerShell