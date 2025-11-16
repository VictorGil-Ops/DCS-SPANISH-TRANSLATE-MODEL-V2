# Auto-detección de DCS

## ¿Qué hace la auto-detección?

Esta función **detecta automáticamente** dónde tienes instalado DCS World y encuentra todas tus campañas disponibles sin que tengas que navegar manualmente por las carpetas.

## ¿Cómo funciona?

### 🔍 Búsqueda automática de DCS:
- Examina las rutas típicas de instalación de DCS:
  - Versión Steam
  - Versión standalone (DCS World OpenBeta)
  - Instalaciones personalizadas registradas
- Detecta automáticamente versión Alpha, Beta y Stable

### 📁 Escaneo de campañas:
Una vez encontrado DCS, busca campañas en:
- **Campañas integradas**: Las que vienen con DCS
- **Campañas instaladas**: Módulos y DLC comprados
- **Campañas personalizadas**: Las que has descargado o creado
- **Subcarpetas**: Explora toda la estructura de directorios

### 🏷️ Clasificación automática:
- **FC (Flaming Cliffs)**: Campañas para aeronaves FC3
- **Full DCS**: Campañas para aeronaves full-fidelity
- **Mixtas**: Campañas que funcionan con ambos tipos

## Ventajas de usar auto-detección:

✅ **Sin configuración manual**: No necesitas buscar carpetas  
✅ **Encuentra todo**: Detecta campañas que podrías haber olvidado  
✅ **Siempre actualizado**: Re-escanea automáticamente  
✅ **Evita errores**: No hay riesgo de rutas incorrectas  
✅ **Ahorra tiempo**: Configuración instantánea

## ¿Cuándo usarla?

### ✅ **Recomendado si**:
- Es tu primera vez usando el traductor
- Tienes DCS instalado en rutas estándar
- Quieres traducir varias campañas diferentes
- No estás seguro de dónde están tus campañas

### ⚠️ **Usar manual si**:
- DCS está en una ubicación muy personalizada
- Solo quieres traducir una campaña específica
- Tienes problemas de rendimiento con el escaneo automático

## Proceso paso a paso:

1. **🎯 Activar**: Marca la casilla "Auto-detectar DCS"
2. **🔍 Escanear**: El sistema busca automáticamente DCS
3. **📋 Seleccionar**: Aparece una lista de campañas encontradas
4. **⚙️ Configurar**: Solo ajusta el modelo y parámetros de traducción
5. **🚀 Ejecutar**: ¡Listo para traducir!

## Resolución de problemas:

- **❌ No encuentra DCS**: Verifica que DCS esté instalado y actualizado
- **❌ No encuentra campañas**: Asegúrate de que las campañas estén en las carpetas correctas
- **❌ Lentitud**: Desactiva y usa configuración manual para campañas específicas

## Nota técnica:

La auto-detección explora:
```
DCS World/Mods/campaigns/
DCS World/Campaigns/
[Usuario]/Saved Games/DCS/
[Usuario]/Saved Games/DCS.openbeta/
```