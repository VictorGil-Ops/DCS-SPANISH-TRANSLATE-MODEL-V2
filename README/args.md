# Argumentos Avanzados

## ¿Qué son los argumentos?

Los **argumentos** son parámetros técnicos que controlan el comportamiento del motor de traducción. Estos ajustes finos permiten optimizar el rendimiento y la calidad según tus necesidades específicas.

## Argumentos principales

### 🔧 **--config [archivo]**

**¿Qué hace?**  
Especifica el archivo de configuración de prompts que guiará las traducciones.

**Ubicación:** `PROMTS/[archivo].yaml`

**Ejemplos:**
- `--config 1-completions-PROMT.yaml` - Prompts básicos
- `--config 2-completions-PROMT.yaml` - Prompts mejorados  
- `--config 3-completions-LLAMA-models.yaml` - Específico para Llama

### 🔄 **--lm-compat [protocolo]**

**¿Qué hace?**  
Define el protocolo de comunicación con el modelo de IA.

**Opciones disponibles:**
- `completions` - Para modelos que usan completions API
- `chat` - Para modelos que usan chat API (recomendado)
- `auto` - Detección automática

**Recomendación:** Usa `chat` para la mayoría de modelos modernos.

### 📦 **--batch-size [número]**

**¿Qué hace?**  
Controla cuántos textos se envían al modelo en cada petición.

**Valores típicos:**
- `5-10` - Para modelos grandes y hardware limitado
- `15-25` - Para modelos medianos (recomendado)
- `30-50` - Para modelos pequeños y hardware potente

**Impacto:**
- **Valor alto**: Más rápido, pero consume más memoria
- **Valor bajo**: Más lento, pero más estable

### ⏱️ **--timeout [segundos]**

**¿Qué hace?**  
Tiempo máximo que el sistema espera una respuesta del modelo antes de dar error.

**Valores recomendados:**
- `30-60` - Para modelos pequeños y rápidos
- `60-120` - Para modelos medianos (estándar)
- `120-300` - Para modelos grandes o hardware lento

### 🔍 **--max-tokens [número]**

**¿Qué hace?**  
Límite máximo de tokens (palabras) que puede generar el modelo por respuesta.

**Valores típicos:**
- `256` - Para textos cortos (mensajes, nombres)
- `512` - Para textos medianos (briefings)
- `1024` - Para textos largos (narrativa completa)

### 🌡️ **--temperature [0.0-2.0]**

**¿Qué hace?**  
Controla la creatividad vs consistencia del modelo.

**Valores recomendados:**
- `0.1-0.3` - Muy consistente, traducciones técnicas
- `0.4-0.7` - Equilibrio (recomendado para DCS)
- `0.8-1.2` - Más creativo, traducciones literarias

### 🎯 **--top-p [0.1-1.0]**

**¿Qué hace?**  
Controla la variabilidad en la selección de palabras.

**Valores típicos:**
- `0.1-0.3` - Muy predecible
- `0.4-0.6` - Equilibrado (recomendado)
- `0.7-0.9` - Más variado

## Configuraciones por preset

### ⚡ **Preset Ligero**
```
--config 1-completions-PROMT.yaml
--lm-compat chat
--batch-size 30
--timeout 60
--max-tokens 512
--temperature 0.3
--top-p 0.5
```

### ⚖️ **Preset Balanceado**
```
--config 2-completions-PROMT.yaml
--lm-compat chat
--batch-size 20
--timeout 90
--max-tokens 512
--temperature 0.5
--top-p 0.6
```

### 🔥 **Preset Pesado**
```
--config 3-completions-LLAMA-models.yaml
--lm-compat chat
--batch-size 10
--timeout 180
--max-tokens 1024
--temperature 0.7
--top-p 0.7
```

## Argumentos especiales

### 🚀 **--parallel [número]**

**¿Qué hace?**  
Controla cuántas peticiones simultáneas puede hacer al modelo.

**Cuidado:** Valores altos pueden saturar el modelo o causar errores.

### 🔄 **--retry-attempts [número]**

**¿Qué hace?**  
Cuántas veces reintenta una traducción si falla.

**Recomendado:** 2-3 intentos para estabilidad.

### 📝 **--log-level [nivel]**

**¿Qué hace?**  
Controla la cantidad de información en los logs.

**Opciones:**
- `ERROR` - Solo errores críticos
- `INFO` - Información general (recomendado)
- `DEBUG` - Información detallada para diagnosticar

## Optimización por tipo de contenido

### 📋 **Textos técnicos** (procedimientos, checklists)
```
--temperature 0.2
--top-p 0.3
--max-tokens 256
```

**Prioriza:** Consistencia y precisión

### 📖 **Narrativa** (briefings, historias)
```
--temperature 0.6
--top-p 0.7
--max-tokens 1024
```

**Prioriza:** Naturalidad y fluidez

### ⚡ **Textos cortos** (mensajes, nombres)
```
--batch-size 50
--timeout 30
--max-tokens 128
```

**Prioriza:** Velocidad de procesamiento

## Resolución de problemas con argumentos

### ❌ **"Timeout errors frecuentes"**
- **Aumentar** `--timeout`
- **Reducir** `--batch-size`
- **Verificar** que el modelo no esté sobrecargado

### ❌ **"Traducciones inconsistentes"**
- **Reducir** `--temperature` (0.1-0.3)
- **Reducir** `--top-p` (0.2-0.4)
- **Usar prompts más específicos**

### ❌ **"Traducciones cortadas"**
- **Aumentar** `--max-tokens`
- **Reducir** `--batch-size`
- **Verificar límites del modelo**

### ❌ **"Muy lento"**
- **Aumentar** `--batch-size`
- **Reducir** `--timeout`
- **Usar modelo más pequeño**

### ❌ **"Errores de memoria"**
- **Reducir** `--batch-size`
- **Reducir** `--max-tokens`
- **Cerrar otros programas**

## Configuración personalizada

### 🛠️ **Para crear tu configuración:**

1. **Comienza** con un preset base
2. **Modifica** 1-2 argumentos a la vez
3. **Prueba** con una campaña pequeña
4. **Ajusta** según los resultados
5. **Guarda** como perfil personalizado

### 📊 **Métricas para evaluar:**

- **Velocidad**: Tiempo total de traducción
- **Calidad**: Naturalidad y precisión
- **Estabilidad**: Frecuencia de errores
- **Consumo**: Uso de memoria y CPU

## Argumentos experimentales

### ⚠️ **Usar con precaución:**

- `--experimental-mode` - Funciones beta
- `--force-gpu` - Forzar uso de GPU
- `--memory-limit` - Límite de memoria

**Nota:** Estos argumentos pueden cambiar o ser removidos en futuras versiones.

## Recomendaciones por experiencia

### 👶 **Principiantes:**
- **Usa presets** por defecto sin modificar
- **No toques** temperatura ni top-p inicialmente
- **Solo ajusta** batch-size y timeout si hay problemas

### 👨‍💼 **Usuarios regulares:**
- **Personaliza** batch-size según tu hardware
- **Ajusta timeout** según velocidad del modelo
- **Experimenta** con temperature para diferentes tipos de texto

### 👨‍💻 **Usuarios avanzados:**
- **Crea configuraciones específicas** para cada tipo de campaña
- **Optimiza** todos los parámetros según tus necesidades
- **Contribuye** con configuraciones exitosas para la comunidad