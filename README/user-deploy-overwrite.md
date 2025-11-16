# Sobrescribir en Despliegue

## ¿Qué hace esta opción?

Controla el **comportamiento del sistema** cuando encuentra archivos que ya existen en la carpeta de despliegue durante el proceso de traducción.

## Opciones disponibles

### ✅ **Activado (true) - Sobrescribir**

**¿Qué hace?**
- **Reemplaza** los archivos existentes con las nuevas traducciones
- **Crea respaldo** automático de los archivos originales
- **Mantiene** la estructura de carpetas original

**Ventajas:**
- ✅ Siempre tienes la versión más reciente
- ✅ No hay duplicados confusos
- ✅ Respaldo automático de seguridad
- ✅ Estructura limpia y organizada

**Desventajas:**
- ⚠️ Los archivos antiguos se pierden (pero hay respaldo)
- ⚠️ No puedes comparar versiones fácilmente

### ❌ **Desactivado (false) - Conservar**

**¿Qué hace?**
- **Mantiene** los archivos existentes intactos
- **Crea nueva carpeta** con sufijo para las nuevas traducciones
- **Preserva** todas las versiones anteriores

**Ventajas:**
- ✅ Conserva todas las versiones de traducciones
- ✅ Permite comparar diferentes traducciones
- ✅ No hay riesgo de perder trabajo anterior
- ✅ Ideal para experimentación

**Desventajas:**
- ⚠️ Puede acumular muchas carpetas
- ⚠️ Consume más espacio en disco
- ⚠️ Puede ser confuso encontrar la versión correcta

## Ejemplos prácticos

### Con Sobrescribir ACTIVADO

```
Antes:
📁 Mi-Campaña/
├── 📄 mission_01.miz
└── 📄 briefing.lua

Después de re-traducir:
📁 Mi-Campaña/
├── 📄 mission_01.miz          (nueva versión)
├── 📄 briefing.lua            (nueva versión)
└── 📁 backup_[timestamp]/
    ├── 📄 mission_01.miz      (versión anterior)
    └── 📄 briefing.lua        (versión anterior)
```

### Con Sobrescribir DESACTIVADO

```
Estructura después de múltiples traducciones:
📁 Traducciones/
├── 📁 Mi-Campaña/
│   ├── 📄 mission_01.miz
│   └── 📄 briefing.lua
├── 📁 Mi-Campaña_v2/
│   ├── 📄 mission_01.miz      (segunda traducción)
│   └── 📄 briefing.lua
└── 📁 Mi-Campaña_v3/
    ├── 📄 mission_01.miz      (tercera traducción)
    └── 📄 briefing.lua
```

## ¿Cuándo usar cada opción?

### 🟢 **Activar Sobrescribir cuando:**

- **Primera vez** traduciendo una campaña
- **Corriges errores** en traducción anterior
- **Actualizas** con un modelo mejor
- **Quieres mantener orden** y no acumular archivos
- **Usas el traductor regularmente** y confías en el sistema
- **Espacio en disco limitado**

### 🔴 **Desactivar Sobrescribir cuando:**

- **Experimentas** con diferentes modelos o configuraciones
- **Quieres comparar** diferentes versiones de traducción
- **No estás seguro** de la calidad de la nueva traducción
- **Es una campaña importante** y quieres máxima seguridad
- **Compartes traducciones** y necesitas múltiples versiones
- **Desarrollas** o pruebas el sistema de traducción

## Seguridad de los datos

### 🛡️ **Con Sobrescribir activado:**
- **Respaldo automático**: Se crea antes de sobrescribir
- **Timestamp único**: Cada respaldo tiene fecha y hora
- **Recuperación fácil**: Puedes restaurar desde backup

### 🔒 **Con Sobrescribir desactivado:**
- **Preservación total**: Nunca se pierde información
- **Control manual**: Tú decides qué conservar
- **Comparación sencilla**: Fácil ver diferencias entre versiones

## Gestión del espacio en disco

### 📊 **Estimación de espacio:**

**Campaña típica:** ~50-200 MB  
**Con sobrescribir:** +10% (solo backup)  
**Sin sobrescribir:** +100% por cada traducción  

### 🧹 **Limpieza recomendada:**

#### **Con Sobrescribir activado:**
- Revisa carpetas backup cada mes
- Elimina respaldos muy antiguos (>90 días)
- Conserva solo 2-3 respaldos más recientes

#### **Con Sobrescribir desactivado:**
- Elimina versiones intermedias que no necesites
- Conserva la primera y la última versión
- Mueve versiones antiguas a almacenamiento externo

## Resolución de problemas

### ❌ **"Error al crear respaldo"**
- **Causa**: Espacio insuficiente o permisos
- **Solución**: Libera espacio o ejecuta como administrador

### ❌ **"No se puede sobrescribir archivo en uso"**
- **Causa**: DCS tiene el archivo abierto
- **Solución**: Cierra DCS antes de traducir

### ❌ **"Demasiadas versiones de archivos"**
- **Causa**: Sobrescribir desactivado por mucho tiempo
- **Solución**: Limpia versiones antiguas manualmente

### ❌ **"No encuentro mi traducción anterior"**
- **Causa**: Sobrescribir activado sin darte cuenta
- **Solución**: Busca en la carpeta backup_[timestamp]

## Recomendación según experiencia

### 👶 **Usuarios nuevos:**
**Desactivar sobrescribir** inicialmente para experimentar sin riesgo

### 👨‍💼 **Usuarios regulares:**
**Activar sobrescribir** para flujo de trabajo eficiente

### 👨‍💻 **Usuarios avanzados:**
**Alternar según el proyecto**: activado para uso regular, desactivado para experimentación