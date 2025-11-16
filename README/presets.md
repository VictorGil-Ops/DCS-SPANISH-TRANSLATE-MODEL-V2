# Presets de Configuración

## ¿Qué son los presets?

Los **presets** son configuraciones predefinidas que optimizan el traductor para diferentes tipos de hardware, velocidad y calidad de traducción. Son como "recetas" que ajustan automáticamente todos los parámetros técnicos.

## Tipos de presets disponibles

### ⚡ **Preset Ligero**
```
Archivo: 1-preset-ligero.yaml
Objetivo: Máxima velocidad en hardware básico
```

**Características:**
- 🚀 **Traducción rápida**: Prioriza velocidad sobre calidad
- 💻 **Hardware básico**: Funciona en PCs modestos
- 🔄 **Batch grande**: Procesa muchos textos a la vez
- ⏱️ **Timeout bajo**: No espera mucho por respuestas lentas

**Ideal para:**
- Computadoras con poca RAM
- Modelos de IA pequeños (2B-7B)
- Traducciones de prueba
- Hardware antiguo

### ⚖️ **Preset Balanceado**
```
Archivo: 2-preset-balanceado.yaml
Objetivo: Equilibrio entre velocidad y calidad
```

**Características:**
- 🎯 **Balance óptimo**: Velocidad y calidad equilibradas
- 💪 **Hardware medio**: Para PCs de gama media
- 📊 **Batch medio**: Procesa cantidades moderadas
- ⏳ **Timeout medio**: Espera razonable por mejores resultados

**Ideal para:**
- La mayoría de usuarios
- Modelos de IA medianos (7B-13B)
- Uso regular del traductor
- Hardware moderno estándar

### 🎯 **Preset Pesado**
```
Archivo: 3-preset-pesado.yaml
Objetivo: Máxima calidad de traducción
```

**Características:**
- 🌟 **Máxima calidad**: Traducciones muy precisas y naturales
- 🖥️ **Hardware potente**: Requiere PCs de alta gama
- 📝 **Batch pequeño**: Procesa pocos textos pero con detalle
- ⏰ **Timeout alto**: Espera el tiempo necesario para calidad

**Ideal para:**
- PCs con mucha RAM y GPU potente
- Modelos de IA grandes (13B+)
- Traducciones finales importantes
- Usuarios que priorizan calidad

## ¿Cómo elegir el preset correcto?

### 💻 **Basado en tu hardware**

#### **PC Básico** (8GB RAM, sin GPU dedicada)
```
Recomendado: Preset Ligero
Modelo sugerido: Gemma 2B, Llama 3.2 3B
```

#### **PC Medio** (16GB RAM, GPU dedicada)
```
Recomendado: Preset Balanceado
Modelo sugerido: Llama 3 8B, Qwen 2.5 7B
```

#### **PC Potente** (32GB+ RAM, GPU alta gama)
```
Recomendado: Preset Pesado
Modelo sugerido: Llama 3 70B, Qwen 2.5 27B
```

### 🎯 **Basado en tu objetivo**

#### **Primera traducción de prueba**
- Usa **Preset Ligero** para ver si todo funciona
- Cambia a uno mejor si el resultado te gusta

#### **Traducción para jugar**
- Usa **Preset Balanceado** para buen resultado en tiempo razonable
- La mayoría de traducciones serán muy usables

#### **Traducción para compartir**
- Usa **Preset Pesado** para máxima calidad
- Vale la pena esperar más tiempo por mejor resultado

## Parámetros que ajustan los presets

### 📦 **Batch Size (Tamaño de lote)**
- **Ligero**: Lotes grandes (más rápido, usa más memoria)
- **Balanceado**: Lotes medianos (equilibrio)
- **Pesado**: Lotes pequeños (más control de calidad)

### ⏱️ **Timeout (Tiempo de espera)**
- **Ligero**: 30 segundos (si no responde rápido, continúa)
- **Balanceado**: 60 segundos (espera razonable)
- **Pesado**: 120 segundos (espera para calidad máxima)

### 🧠 **Parámetros del modelo**
- **Temperatura**: Creatividad vs consistencia
- **Top-p**: Control de variabilidad
- **Max tokens**: Longitud máxima de respuesta

### 🔄 **Configuración de cache**
- **Ligero**: Cache agresivo (reutiliza mucho)
- **Balanceado**: Cache selectivo (equilibrio)
- **Pesado**: Cache conservador (nueva traducción cuando sea necesario)

## ¿Cómo aplicar un preset?

### 📋 **Desde la interfaz**
1. **Ve a la sección "Presets"**
2. **Selecciona** el preset que quieres
3. **Haz clic en "Aplicar"**
4. **Todos los parámetros** se ajustan automáticamente

### ⚙️ **Personalización después del preset**
1. **Aplica un preset** como base
2. **Modifica parámetros específicos** según tus necesidades
3. **Guarda como nuevo perfil** para reutilizar

### 🔄 **Cambiar entre presets**
- Puedes cambiar de preset **en cualquier momento**
- Los cambios se aplican **inmediatamente**
- **No afecta traducciones en curso**

## Resolución de problemas por preset

### ❌ **Preset Ligero muy lento**
- Tu modelo de IA es demasiado grande para tu hardware
- Cambia a un modelo más pequeño
- Verifica que no tienes otros programas consumiendo recursos

### ❌ **Preset Balanceado con errores**
- Puede ser un problema de memoria
- Prueba el Preset Ligero temporalmente
- Cierra otros programas para liberar RAM

### ❌ **Preset Pesado no termina nunca**
- El timeout puede ser demasiado alto para tu modelo
- Reduce el timeout manualmente
- O cambia al Preset Balanceado

## Consejos profesionales

### 🎯 **Estrategia de uso**
1. **Empieza con Ligero** para verificar que todo funciona
2. **Sube a Balanceado** si tu PC lo soporta bien
3. **Usa Pesado solo** para traducciones importantes

### 🔄 **Optimización progresiva**
- **Traduce una misión pequeña** con cada preset
- **Compara los resultados** y tiempos
- **Elige el mejor balance** para tu uso

### 💾 **Gestión de configuraciones**
- **Guarda configuraciones personalizadas** como perfiles
- **Documenta qué funciona** mejor para cada tipo de campaña
- **Mantén respaldos** de configuraciones exitosas