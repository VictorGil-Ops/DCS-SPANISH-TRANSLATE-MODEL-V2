# Carpeta de Prompts DCS World

Esta carpeta contiene los archivos de configuración de prompts optimizados para diferentes tamaños de modelos de IA.

## Archivos de Prompts:

### `1-instruct-ligero.yaml`
- **Modelos objetivo**: Llama-3.2-3B-Instruct, Gemma-2-2B-IT
- **Peso**: Ligero (2B-3B parámetros)
- **Características**: Instrucciones simples y directas, configuración optimizada para modelos pequeños
- **Temperature**: 0.1 (alta consistencia)

### `2-instruct-balanceado.yaml`
- **Modelos objetivo**: Llama-3.1-8B-Instruct, Gemma-2-9B-IT
- **Peso**: Balanceado (8B-9B parámetros)
- **Características**: Contexto detallado con terminología militar especializada
- **Temperature**: 0.1 (alta consistencia)

### `3-instruct-pesado.yaml`
- **Modelos objetivo**: Llama-3.1-70B-Instruct, Gemma-2-27B-IT
- **Peso**: Pesado (27B-70B parámetros)
- **Características**: Contexto profesional militar avanzado con máxima precisión
- **Temperature**: 0.05 (máxima consistencia)

## Características Comunes (Optimización v2.0):

### Formato de Respuesta Estricto:
- ✅ **Respuesta EXCLUSIVA**: Solo JSON válido, sin explicaciones
- ❌ **Prohibido**: Comentarios, marcadores de código, texto explicativo
- 🎯 **Objetivo**: Respuesta parseable directamente como JSON

### Secuencias de Parada Mejoradas:
- Incluyen patrones comunes de explicaciones: `"Explicación"`, `"Nota:"`, `"La traducción"`
- Stop sequences específicas para modelos Llama: `"</s>"`, `"<|eot_id|>"`
- Prevención de texto adicional: `"Aquí está"`, `"El resultado"`

### Configuración API Optimizada:
- **Temperature reducida**: Para máxima consistencia en respuestas
- **Top_p ajustado**: Para mayor enfoque en tokens relevantes
- **Stop sequences extensas**: Para prevenir generación de texto adicional

## Uso con el Sistema:

Los prompts se seleccionan automáticamente según:
1. **Modelo configurado** en LM Studio
2. **Preset seleccionado** en la interfaz
3. **Compatibilidad de peso** del modelo

## Validación de Respuestas:

El motor de traducción incluye:
- **Filtrado de contenido del sistema** que algunos modelos incluyen incorrectamente
- **Extracción de JSON puro** eliminando texto explicativo
- **Múltiples intentos de parseo** con diferentes estrategias de limpieza