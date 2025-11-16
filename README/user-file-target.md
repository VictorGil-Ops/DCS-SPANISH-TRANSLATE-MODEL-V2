# Archivo de Campaña Objetivo

## ¿Qué es el archivo de campaña objetivo?

Es el **archivo específico de campaña** que quieres traducir. En DCS, cada campaña tiene un archivo principal (normalmente con extensión `.miz` o `.lua`) que contiene todas las misiones, briefings y textos.

## Ubicación típica

Las campañas de DCS se encuentran en:

```
DCS World/Campaigns/[Nombre de la Campaña]/[Archivo de Campaña]
```

## Tipos de archivos de campaña

### 📦 **Archivos .miz**
- **¿Qué son?**: Misiones individuales empaquetadas
- **Contenido**: Una misión completa con briefings, objetivos, scripts
- **Traducción**: Se traduce todo el contenido de la misión

### 📝 **Archivos .lua**
- **¿Qué son?**: Scripts que definen campañas dinámicas
- **Contenido**: Lógica de campaña, eventos, narrativa
- **Traducción**: Se traduce solo el texto visible al usuario

### 🗂️ **Carpetas de campaña**
- **¿Qué son?**: Conjuntos de misiones relacionadas
- **Contenido**: Múltiples archivos .miz y .lua organizados
- **Traducción**: Se procesan todos los archivos de texto

## ¿Cómo seleccionar el archivo correcto?

### 🎯 **Para una misión individual**
1. Navega a la carpeta de la campaña
2. Selecciona el archivo `.miz` específico
3. Solo se traducirá esa misión

### 📚 **Para una campaña completa**
1. Busca el archivo principal de la campaña (normalmente `.lua`)
2. O selecciona la carpeta completa de la campaña
3. Se traducirán todas las misiones relacionadas

### 🔍 **Para encontrar el archivo principal**
- Busca archivos con nombres como:
  - `campaign.lua`
  - `main.lua`
  - `[Nombre de la Campaña].lua`
  - El archivo más grande de la carpeta

## Información que se traduce

### ✅ **Textos traducibles**
- **Briefings**: Información de misión antes del vuelo
- **Objetivos**: Metas y tareas de la misión
- **Mensajes**: Comunicaciones durante el vuelo
- **Narrativa**: Texto de la historia y contexto
- **UI**: Elementos de interfaz de usuario

### ❌ **Lo que NO se traduce**
- **Nombres técnicos**: Códigos de aeronaves, waypoints
- **Coordenadas**: Posiciones GPS y navegación
- **Comandos**: Instrucciones técnicas de DCS
- **Scripts**: Código Lua funcional

## Ejemplos prácticos

### 🚁 **Campaña del UH-1H**
```
Archivo: "UH-1H Spring Tension.lua"
Resultado: Se traducen briefings y comunicaciones de radio
```

### ✈️ **Misión individual F/A-18C**
```
Archivo: "Strike Mission.miz"
Resultado: Se traduce solo esa misión específica
```

### 🎯 **Campaña completa A-10C**
```
Carpeta: "A-10C Advanced Aircraft Training/"
Resultado: Se traducen todas las misiones de entrenamiento
```

## Consejos para la selección

### 🟢 **Buenas prácticas**
- **Haz respaldo**: Siempre copia el archivo original antes de traducir
- **Prueba primero**: Traduce una misión pequeña para verificar resultado
- **Lee la descripción**: Asegúrate de seleccionar el archivo correcto

### 🔴 **Evita estos errores**
- **No selecciones archivos del sistema**: Solo archivos de campañas de usuario
- **No traduzcas campañas en uso**: Cierra DCS antes de traducir
- **No modifiques archivos originales**: Usa las copias traducidas

## Resolución de problemas

### ❌ **"Archivo no válido"**
- Verifica que sea un archivo de campaña real (.miz o .lua)
- Asegúrate de que no esté corrupto o en uso

### ❌ **"No se encuentra contenido para traducir"**
- Es posible que el archivo no tenga texto traducible
- Prueba con un archivo de campaña diferente

### ❌ **"Traducción incompleta"**
- Algunos archivos tienen texto mezclado con código
- Es normal que no todo el contenido sea traducible