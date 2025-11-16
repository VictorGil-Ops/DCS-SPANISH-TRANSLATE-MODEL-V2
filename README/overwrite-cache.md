# Sobrescribir Cache

## ¿Qué hace esta opción?

Controla si el sistema **actualiza el cache** con nuevas traducciones cuando el cache está **desactivado**. Es una función avanzada para gestionar inteligentemente el contenido del cache.

## ¿Cómo funciona?

### 🔄 **Flujo normal (cache activado)**
1. **Busca** en cache traducciones existentes
2. **Usa** traducciones del cache si están disponibles
3. **Traduce** solo textos nuevos
4. **Guarda** nuevas traducciones en cache automáticamente

### 🆕 **Con cache desactivado + sobrescribir activado**
1. **Ignora** completamente el cache existente
2. **Traduce** todo desde cero (traducciones frescas)
3. **Guarda** las nuevas traducciones en cache
4. **Reemplaza** o añade entradas al cache

### ❌ **Con cache desactivado + sobrescribir desactivado**
1. **Ignora** el cache existente
2. **Traduce** todo desde cero
3. **NO modifica** el cache
4. **Mantiene** el cache intacto

## ¿Cuándo usar cada configuración?

### ✅ **Activar Sobrescribir Cache cuando:**

#### 🔄 **Actualización gradual del cache**
- Quieres **nuevas traducciones** pero preservar las buenas del cache
- Has **mejorado el modelo** y quieres actualizar progresivamente
- Necesitas **corregir traducciones específicas** sin perder todo el cache

#### 🧪 **Experimentación con preservación**
- Pruebas **diferentes configuraciones** pero quieres guardar las mejores
- **Comparas modelos** y quieres conservar resultados buenos
- **Ajustas parámetros** y quieres acumular mejoras

#### 📚 **Construcción de cache de calidad**
- Estás **construyendo un cache** con traducciones curadas
- Quieres **mantener solo las mejores traducciones**
- **Refinas gradualmente** la calidad del cache

### ❌ **Desactivar Sobrescribir Cache cuando:**

#### 🧪 **Experimentación pura**
- Solo quieres **ver** cómo traduce sin cache
- **Comparas** con traducciones del cache sin modificarlo
- **Pruebas temporales** que no quieres conservar

#### 🛡️ **Protección del cache**
- Tienes un **cache valioso** que no quieres modificar
- **Experimentas** con configuraciones arriesgadas
- **Cache de backup** que debe mantenerse intacto

#### 🔍 **Análisis de diferencias**
- Quieres **comparar** traducciones nuevas vs cache
- **Evaluas** la mejora de un modelo nuevo
- **Investigas** qué tan diferente traduce sin cache

## Ejemplos prácticos

### 📋 **Escenario 1: Mejora de modelo**

```
Situación: Actualizaste de Llama 7B a Llama 13B
Objetivo: Mejorar gradualmente tu cache

Configuración:
- Cache: ❌ Desactivado
- Sobrescribir Cache: ✅ Activado

Resultado: 
- Traduce todo con el modelo nuevo
- Guarda las mejores traducciones en cache
- Mantiene traducciones del cache que siguen siendo buenas
```

### 🔍 **Escenario 2: Evaluación de calidad**

```
Situación: Quieres ver qué tan bueno es tu cache actual
Objetivo: Comparar sin modificar el cache

Configuración:
- Cache: ❌ Desactivado  
- Sobrescribir Cache: ❌ Desactivado

Resultado:
- Traduce todo ignorando cache
- No modifica el cache existente
- Puedes comparar resultados manualmente
```

### 🎯 **Escenario 3: Traducción híbrida**

```
Situación: Cache bueno pero quieres mejoras puntuales
Objetivo: Usar cache + mejorar específicamente

Configuración Primera Pasada:
- Cache: ✅ Activado
- (Usar cache normal)

Configuración Segunda Pasada:
- Cache: ❌ Desactivado
- Sobrescribir Cache: ✅ Activado
- Solo en textos que quieres mejorar
```

## Interacción con otras configuraciones

### 🔗 **Con Presets**

#### **Preset Ligero + Sobrescribir Cache:**
- **Ventaja**: Rápido para actualizar cache masivamente
- **Cuidado**: Calidad puede ser menor

#### **Preset Pesado + Sobrescribir Cache:**
- **Ventaja**: Cache de máxima calidad
- **Cuidado**: Muy lento, solo para textos importantes

### 🔗 **Con diferentes modelos**

#### **Modelo pequeño → grande:**
```
Cache desactivado + Sobrescribir = SÍ
(Mejorar calidad gradualmente)
```

#### **Modelo grande → pequeño:**
```
Cache desactivado + Sobrescribir = NO
(Evitar degradar cache existente)
```

## Gestión avanzada del cache

### 📊 **Estrategia por fases**

#### **Fase 1: Construcción inicial**
```
Cache: ❌ | Sobrescribir: ✅ | Modelo: Mediano-Grande
Objetivo: Crear base sólida
```

#### **Fase 2: Uso productivo**
```
Cache: ✅ | Sobrescribir: Auto
Objetivo: Velocidad en uso diario
```

#### **Fase 3: Mantenimiento**
```
Cache: ❌ | Sobrescribir: ✅ | Modelo: Mejor disponible
Objetivo: Mejora periódica del cache
```

### 🧹 **Limpieza del cache**

Cuando usar **cache desactivado + sobrescribir activado**:
- **Limpiar traducciones incorrectas** específicas
- **Actualizar terminología** de versiones nuevas de DCS
- **Homogeneizar estilo** de traducción

## Resolución de problemas

### ❌ **"Cache no se actualiza"**
- **Verifica** que Sobrescribir Cache esté **activado**
- **Confirma** que Cache esté **desactivado**
- **Revisa permisos** de escritura en archivo cache

### ❌ **"Traducciones duplicadas en cache"**
- **Usa limpieza** de cache automática
- **Revisa** si hay conflictos de codificación de texto

### ❌ **"Cache crece muy rápido"**
- **Configura límites** de tamaño de cache
- **Usa filtros** de calidad para cache

### ❌ **"Traducciones nuevas peores que cache"**
- **Desactiva** Sobrescribir Cache temporalmente
- **Mejora configuración** del modelo antes de actualizar cache

## Monitoreo del cache

### 📈 **Métricas importantes**

#### **Durante traducción con sobrescribir:**
- **Entradas añadidas**: Nuevas traducciones guardadas
- **Entradas actualizadas**: Traducciones mejoradas
- **Tamaño del cache**: Crecimiento del archivo

#### **Calidad del cache:**
- **Tasa de reutilización**: % de textos encontrados en cache
- **Consistencia**: Uniformidad en traducciones similares
- **Actualidad**: Fechas de las traducciones en cache

## Recomendaciones por nivel

### 👶 **Principiantes:**
- **Mantén simple**: Cache activado, no toques sobrescribir
- **Si experimentas**: Cache desactivado + sobrescribir desactivado

### 👨‍💼 **Usuarios regulares:**
- **Mejora gradual**: Cache desactivado + sobrescribir activado mensualmente
- **Uso diario**: Cache activado

### 👨‍💻 **Usuarios avanzados:**
- **Estrategia híbrida**: Combina configuraciones según objetivos
- **Cache especializado**: Diferentes caches para diferentes tipos de contenido
- **Automatización**: Scripts para gestión inteligente del cache