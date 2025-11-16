# URL del Servidor de Modelo de Lenguaje

## ¿Qué es la URL del servidor LM?

Es la **dirección web** donde está ejecutándose tu modelo de lenguaje (como LM Studio, Ollama, o cualquier servidor compatible con OpenAI API). El traductor se conecta a esta dirección para enviar textos y recibir traducciones.

## Formato de URL

### 🌐 **Estructura típica**
```
http://[dirección]:[puerto]/v1
```

### 📋 **Ejemplos comunes**

#### **LM Studio (local)**
```
http://localhost:1234/v1
http://127.0.0.1:1234/v1
```

#### **Ollama (local)**
```
http://localhost:11434/v1
```

#### **Servidor remoto**
```
http://192.168.1.100:1234/v1
http://mi-servidor.local:8080/v1
```

#### **OpenAI API (oficial)**
```
https://api.openai.com/v1
```

## Configuración paso a paso

### 🚀 **Para LM Studio**

1. **Inicia LM Studio**
2. **Carga un modelo** (ej: Llama-3-8B, Gemma-2B)
3. **Ve a la pestaña "Local Server"**
4. **Inicia el servidor** (Start Server)
5. **Copia la URL** que aparece (normalmente `http://localhost:1234`)
6. **Pégala en el traductor** con `/v1` al final

### 🐳 **Para Ollama**

1. **Instala Ollama** desde ollama.ai
2. **Descarga un modelo**: `ollama pull llama3`
3. **Inicia el servidor**: `ollama serve`
4. **Usa la URL**: `http://localhost:11434/v1`

### 🔗 **Para servidor remoto**

1. **Obtén la IP** del servidor donde corre el modelo
2. **Averigua el puerto** (pregunta al administrador)
3. **Construye la URL**: `http://[IP]:[Puerto]/v1`

## ¿Cómo verificar que funciona?

### ✅ **Prueba de conexión**

El traductor incluye un **botón de test** que verifica:
- ✅ Si la URL es accesible
- ✅ Si el servidor responde
- ✅ Si hay modelos disponibles
- ✅ Si la API es compatible

### 🔍 **Prueba manual (avanzado)**

Abre un navegador y visita:
```
http://tu-servidor:puerto/v1/models
```

Deberías ver una lista de modelos disponibles.

## Configuraciones especiales

### 🔐 **Con autenticación (API Keys)**
Si tu servidor requiere autenticación:
1. Configura la URL normalmente
2. En el campo "API Key", ingresa tu clave
3. El traductor la enviará automáticamente

### 🌍 **Usando servicios en la nube**
- **OpenAI**: Necesitas una cuenta y API Key
- **Hugging Face**: Puedes usar endpoints de modelos hospedados
- **Replicate**: Para modelos especializados

### 🏠 **Red local (LAN)**
Para usar un servidor en otra computadora:
1. Encuentra la IP de la computadora servidor
2. Asegúrate de que el firewall permita la conexión
3. Usa `http://[IP-de-la-computadora]:puerto/v1`

## Resolución de problemas comunes

### ❌ **"No se puede conectar"**
- **Verifica que el servidor esté funcionando**
- **Revisa la URL** (puerto correcto, http vs https)
- **Desactiva firewall** temporalmente para probar

### ❌ **"Timeout de conexión"**
- **El modelo es muy lento** para tu hardware
- **Aumenta el timeout** en configuraciones avanzadas
- **Usa un modelo más pequeño**

### ❌ **"API Key inválida"**
- **Verifica la clave** si usas servicios de pago
- **Para servidores locales**, deja el campo vacío

### ❌ **"No hay modelos disponibles"**
- **Asegúrate de haber cargado un modelo** en LM Studio/Ollama
- **Verifica que el modelo esté activo**

## Recomendaciones de rendimiento

### ⚡ **Para traducción rápida**
- Usa **modelos pequeños** (2B-7B parámetros)
- **Servidor local** en la misma computadora
- **SSD rápido** para cargar modelos

### 🎯 **Para máxima calidad**
- Usa **modelos grandes** (13B+ parámetros)
- **GPU potente** si está disponible
- **Servidor dedicado** para no competir por recursos

### 💰 **Para uso esporádico**
- **OpenAI API** puede ser más económico que hardware dedicado
- **Servicios en la nube** para traducciones ocasionales