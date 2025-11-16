# Cache de Traducciones

## ¿Qué es el cache?

El **cache** es un sistema que guarda las traducciones ya realizadas para **reutilizarlas** cuando encuentre el mismo texto nuevamente. Es como una "memoria" del traductor que evita traducir lo mismo dos veces.

## ¿Cómo funciona?

### 🔄 **Proceso básico**
1. **Encuentra texto** para traducir
2. **Busca en cache** si ya se tradujo antes
3. **Si existe**: Usa la traducción guardada (instantáneo)
4. **Si no existe**: Traduce con IA y guarda en cache

### 💾 **Almacenamiento**
- Se guarda en: `app/data/cache/global_translation_cache.json`
- **Formato**: Texto original → Texto traducido
- **Persistente**: Se mantiene entre sesiones
- **Acumulativo**: Crece con cada traducción

## Ventajas del cache

### ⚡ **Velocidad**
- **Traducciones instantáneas** para texto repetido
- **Reduce tiempo total** significativamente
- **Menos espera** en textos ya conocidos

### 💰 **Ahorro de recursos**
- **Menos uso de CPU/GPU** (no procesa texto repetido)
- **Menos consultas a API** (ahorra dinero si usas servicios de pago)
- **Menor consumo eléctrico**

### 🎯 **Consistencia**
- **Traducciones idénticas** para el mismo texto
- **Terminología consistente** entre campañas
- **Calidad uniforme** en todo el proyecto

### 🔄 **Reutilización**
- **Entre campañas**: Reutiliza traducciones de campañas anteriores
- **Entre sesiones**: Mantiene traducciones de días/semanas anteriores
- **Entre versiones**: Aprovecha traducciones de versiones similares

## ¿Cuándo usar el cache?

### ✅ **Activar cache cuando**
- Traduces **varias campañas** del mismo tipo
- Hay **mucho texto repetitivo** (nombres, lugares, términos técnicos)
- Quieres **mantener consistencia** en traducciones
- **Velocidad** es más importante que variedad
- Usas **APIs de pago** y quieres ahorrar

### ❌ **Desactivar cache cuando**
- Quieres **traducciones completamente nuevas**
- El cache tiene **traducciones de mala calidad** que quieres corregir
- Cambiaste de **modelo de IA** y quieres comparar resultados
- **Experimentas** con diferentes estilos de traducción
- El cache está **corrupto** o causa problemas

## Gestión del cache

### 📊 **Información del cache**
El traductor muestra:
- **Número de entradas** en cache
- **Tamaño del archivo** cache
- **Tasa de aciertos** (% de texto encontrado en cache)
- **Fecha de última actualización**

### 🧹 **Limpieza del cache**

#### **Limpieza básica**
- Elimina entradas duplicadas
- Remueve traducciones vacías o erróneas
- Optimiza el formato del archivo

#### **Limpieza avanzada**
- Filtra por calidad de traducción
- Remueve traducciones muy antiguas
- Elimina entradas de campañas específicas

#### **Limpieza completa**
- Borra todo el cache (empezar desde cero)
- Útil cuando cambias completamente de modelo o estilo

### 📁 **Respaldo del cache**
```
Archivo original: global_translation_cache.json
Respaldo automático: global_translation_cache.json.backup
Respaldos manuales: cache_backup_[fecha].json
```

## Tipos de cache

### 🌍 **Cache Global**
- **Ubicación**: Compartido entre todas las campañas
- **Contenido**: Traducciones de términos comunes
- **Ventaja**: Máxima reutilización
- **Uso**: Activado por defecto

### 📁 **Cache por Campaña** (futuro)
- **Ubicación**: Específico de cada campaña
- **Contenido**: Traducciones específicas del contexto
- **Ventaja**: Traducciones contextualizadas
- **Uso**: Para campañas muy específicas

## Optimización del cache

### 🎯 **Mejores prácticas**
- **Traduce campañas similares** secuencialmente
- **Revisa traducciones** antes de guardarlas en cache
- **Mantén cache limpio** con limpiezas regulares
- **Haz respaldos** antes de cambios importantes

### ⚙️ **Configuración avanzada**
- **Tamaño máximo**: Límite de entradas en cache
- **Validez temporal**: Expiración de traducciones antiguas
- **Filtros de calidad**: Solo cache traducciones de alta calidad

## Resolución de problemas

### ❌ **"Cache corrupto"**
- **Síntoma**: Errores al cargar traducciones
- **Solución**: Restaurar desde respaldo o limpiar cache

### ❌ **"Traducciones incorrectas repetidas"**
- **Síntoma**: Mismo error aparece en todas las traducciones
- **Solución**: Limpiar cache y re-traducir

### ❌ **"Cache muy lento"**
- **Síntoma**: Búsquedas en cache tardan mucho
- **Solución**: Optimizar o reducir tamaño del cache

### ❌ **"No encuentra traducciones en cache"**
- **Síntoma**: Traduce texto que debería estar en cache
- **Solución**: Verificar formato del texto y configuración

## Estadísticas útiles

### 📊 **Métricas de rendimiento**
- **Tasa de acierto**: % de textos encontrados en cache
- **Tiempo ahorrado**: Estimación de tiempo evitado
- **Textos únicos**: Cantidad de traducciones diferentes
- **Crecimiento**: Nuevas entradas por sesión

### 💹 **Beneficios cuantificables**
- **Reducción de tiempo**: Hasta 80% menos tiempo en retraducciones
- **Ahorro de recursos**: Menor uso de CPU/GPU
- **Consistencia**: 100% de consistencia en textos repetidos