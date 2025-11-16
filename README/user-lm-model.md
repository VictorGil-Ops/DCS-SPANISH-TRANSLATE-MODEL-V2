# Modelo de Lenguaje

## ¿Qué es el modelo de lenguaje?

Es la **inteligencia artificial** específica que realizará las traducciones. Cada modelo tiene diferentes capacidades, velocidad, calidad y requisitos de hardware.

## Tipos de modelos disponibles

### 🎯 **Modelos Pequeños (2B-3B parámetros)**

#### **Gemma 2B**
- **Tamaño**: ~1.4 GB
- **RAM requerida**: 4-6 GB
- **Velocidad**: Muy rápida
- **Calidad**: Básica, ideal para pruebas
- **Ideal para**: PCs básicos, traducciones de prueba

#### **Llama 3.2 3B**
- **Tamaño**: ~1.9 GB
- **RAM requerida**: 6-8 GB
- **Velocidad**: Rápida
- **Calidad**: Buena para textos simples
- **Ideal para**: Equipos modestos, traducciones frecuentes

### ⚖️ **Modelos Medianos (7B-13B parámetros)**

#### **Llama 3.1 8B**
- **Tamaño**: ~4.7 GB
- **RAM requerida**: 8-12 GB
- **Velocidad**: Moderada
- **Calidad**: Muy buena, equilibrada
- **Ideal para**: La mayoría de usuarios

#### **Qwen 2.5 7B**
- **Tamaño**: ~4.4 GB
- **RAM requerida**: 8-10 GB
- **Velocidad**: Buena
- **Calidad**: Excelente para textos técnicos
- **Ideal para**: Traducciones técnicas de aviación

#### **Mistral 7B**
- **Tamaño**: ~4.1 GB
- **RAM requerida**: 8-10 GB
- **Velocidad**: Rápida
- **Calidad**: Buena, muy consistente
- **Ideal para**: Uso productivo regular

### 🔥 **Modelos Grandes (27B+ parámetros)**

#### **Qwen 2.5 27B**
- **Tamaño**: ~15.8 GB
- **RAM requerida**: 20-32 GB
- **Velocidad**: Lenta
- **Calidad**: Excelente, muy natural
- **Ideal para**: PCs high-end, traducciones finales

#### **Llama 3.1 70B**
- **Tamaño**: ~40 GB
- **RAM requerida**: 48-64 GB
- **Velocidad**: Muy lenta
- **Calidad**: Excepcional, nivel profesional
- **Ideal para**: Servidores dedicados, máxima calidad

## ¿Cómo elegir el modelo correcto?

### 💻 **Según tu hardware**

#### **PC Básico** (8GB RAM, sin GPU dedicada)
```
Recomendado: Gemma 2B, Llama 3.2 3B
Preset: Ligero
Tiempo esperado: 5-15 min por campaña mediana
```

#### **PC Medio** (16GB RAM, GPU dedicada)
```
Recomendado: Llama 3.1 8B, Qwen 2.5 7B
Preset: Balanceado
Tiempo esperado: 10-30 min por campaña mediana
```

#### **PC Potente** (32GB+ RAM, GPU high-end)
```
Recomendado: Qwen 2.5 27B, Llama 3.1 70B
Preset: Pesado
Tiempo esperado: 30-120 min por campaña mediana
```

### 🎯 **Según el tipo de contenido**

#### **Textos simples** (mensajes básicos, nombres)
- **Cualquier modelo** es suficiente
- **Prioriza velocidad**: Gemma 2B, Llama 3.2 3B

#### **Textos técnicos** (procedimientos, briefings)
- **Modelos especializados**: Qwen 2.5 7B/27B
- **Buena comprensión**: Llama 3.1 8B

#### **Narrativa compleja** (historias, diálogos)
- **Modelos grandes**: Qwen 2.5 27B, Llama 3.1 70B
- **Naturalidad importante**: Prioriza calidad sobre velocidad

### 💰 **Según costes (APIs de pago)**

#### **OpenAI API** (GPT-4, GPT-3.5)
- **GPT-4**: Excelente calidad, costoso
- **GPT-3.5**: Buena calidad, más económico
- **Ideal para**: Uso esporádico, traducción de alta calidad

#### **Anthropic Claude**
- **Claude 3**: Muy buena comprensión contextual
- **Ideal para**: Textos largos y complejos

## Configuración según el modelo

### 🛠️ **LM Studio (local)**

#### **Configuración típica:**
```
URL: http://localhost:1234/v1
Modelo: [seleccionar desde interfaz LM Studio]
Timeout: 60-120 segundos según modelo
```

#### **Ventajas:**
- ✅ Sin coste por uso
- ✅ Privacidad total
- ✅ Sin límites de uso

#### **Desventajas:**
- ⚠️ Requiere hardware potente
- ⚠️ Consume recursos locales

### ☁️ **Servicios en la nube**

#### **OpenAI API:**
```
URL: https://api.openai.com/v1
Modelo: gpt-4 o gpt-3.5-turbo
API Key: [tu clave]
```

#### **Ventajas:**
- ✅ Sin requisitos de hardware
- ✅ Siempre disponible
- ✅ Calidad consistente

#### **Desventajas:**
- 💰 Coste por uso
- 🌐 Requiere conexión a internet
- 🔒 Datos enviados externamente

## Optimización por modelo

### ⚡ **Para modelos pequeños (2B-7B):**
- **Batch size grande**: 20-50 textos por lote
- **Timeout corto**: 30-60 segundos
- **Cache activado**: Reutiliza traducciones

### ⚖️ **Para modelos medianos (8B-13B):**
- **Batch size medio**: 10-20 textos por lote
- **Timeout medio**: 60-90 segundos
- **Balance cache**: Según preferencia

### 🔥 **Para modelos grandes (27B+):**
- **Batch size pequeño**: 5-10 textos por lote
- **Timeout alto**: 90-180 segundos
- **Cache selectivo**: Solo para textos importantes

## Resolución de problemas comunes

### ❌ **"Modelo no disponible"**
- **Verifica** que el modelo esté cargado en LM Studio
- **Confirma** que el servidor LM esté funcionando
- **Prueba** con un modelo diferente

### ❌ **"Respuestas muy lentas"**
- **Cambia a un modelo más pequeño**
- **Aumenta el timeout**
- **Reduce el batch size**

### ❌ **"Calidad de traducción pobre"**
- **Prueba con un modelo más grande**
- **Ajusta los prompts de traducción**
- **Verifica la configuración del modelo**

### ❌ **"Se queda sin memoria"**
- **Usa un modelo más pequeño**
- **Cierra otros programas**
- **Reduce el batch size**

## Recomendaciones por experiencia

### 👶 **Principiantes:**
1. **Comienza** con Llama 3.1 8B (buen equilibrio)
2. **Usa Preset Balanceado** por defecto
3. **Prueba una campaña pequeña** primero

### 👨‍💼 **Usuarios regulares:**
1. **Qwen 2.5 7B** para textos técnicos
2. **Llama 3.1 8B** para uso general
3. **Personaliza presets** según necesidades

### 👨‍💻 **Usuarios avanzados:**
1. **Múltiples modelos** para diferentes tipos de contenido
2. **Configuraciones específicas** por campaña
3. **Combinación local + nube** según el proyecto