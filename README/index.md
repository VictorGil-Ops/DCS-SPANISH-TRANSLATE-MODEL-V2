# 📖 Índice de Ayudas del Orquestador

Este directorio contiene toda la documentación de ayuda para el **Sistema de Traducción de DCS Spanish**.

## � Configuración Básica

### **Gestión de Configuraciones**
- **[📋 Perfiles de Configuración](profiles.md)** - Cómo guardar y reutilizar configuraciones completas
- **[🎯 Auto-detección de DCS](auto-detect-dcs.md)** - Detección automática de instalación y campañas

### **Rutas y Archivos**
- **[📁 Carpeta Raíz de Usuario](user-root-dir.md)** - Dónde buscar las campañas de DCS
- **[📄 Archivo de Campaña Objetivo](user-file-target.md)** - Cómo seleccionar qué traducir
- **[💾 Carpeta de Despliegue](user-deploy-dir.md)** - Dónde guardar traducciones
- **[🔄 Sobrescribir en Despliegue](user-deploy-overwrite.md)** - Control de archivos existentes

## 🤖 Configuración del Modelo de IA

### **Conexión y Modelos**
- **[🌐 URL del Servidor LM](user-lm-url.md)** - Configuración de conexión al modelo de lenguaje
- **[🧠 Modelo de Lenguaje](user-lm-model.md)** - Selección y configuración del modelo de IA

## ⚡ Optimización y Rendimiento

### **Configuraciones Predefinidas**
- **[⚙️ Presets de Configuración](presets.md)** - Configuraciones optimizadas para diferentes hardware

### **Parámetros Avanzados**
- **[🔧 Argumentos Avanzados](args.md)** - Parámetros técnicos del motor de traducción

### **Sistema de Cache**
- **[💨 Cache de Traducciones](cache.md)** - Sistema de reutilización de traducciones
- **[🔄 Sobrescribir Cache](overwrite-cache.md)** - Control inteligente del cache existente

## �️ Funcionalidades Especiales

- **[✈️ Detección FC](fc.md)** - Detección automática de campañas Flaming Cliffs vs Full-Fidelity

---

## 🚀 Guía Rápida para Principiantes

### **1️⃣ Primera Configuración**
1. **Lee** [Auto-detección de DCS](auto-detect-dcs.md) para configuración automática
2. **Configura** tu [URL del Servidor LM](user-lm-url.md) 
3. **Aplica** un [Preset](presets.md) según tu hardware

### **2️⃣ Primera Traducción**
1. **Activa** auto-detección o configura [Carpeta Raíz](user-root-dir.md)
2. **Selecciona** tu [Archivo Objetivo](user-file-target.md)
3. **Configura** [Carpeta de Despliegue](user-deploy-dir.md)
4. **🚀 ¡Inicia la traducción!**

### **3️⃣ Optimización**
1. **Revisa** el [Cache](cache.md) para acelerar futuras traducciones
2. **Guarda** tu configuración como [Perfil](profiles.md)
3. **Ajusta** [Argumentos](args.md) si es necesario

---

## 🆘 Resolución de Problemas

Cada guía incluye una sección de **"Resolución de problemas"** con las situaciones más comunes y sus soluciones.

### **📞 Ayuda Adicional**

Si necesitas ayuda que no está cubierta en estas guías:

1. **🔍 Verifica los logs** del sistema en `app/data/logs/`
2. **📝 Consulta el archivo DEBUG.md** en la raíz del proyecto  
3. **⚙️ Prueba** diferentes configuraciones usando los presets

---

## 🔄 Información del Sistema

- **📖 Versión de documentación**: 1.0  
- **📅 Fecha**: Enero 2025  
- **🔧 Compatible con**: DCS Spanish Translator v2.x
- **🎯 Sistema**: Orquestador Web Moderno

**💡 Consejo**: Usa los botones de ayuda **"?"** en cada sección del orquestador para acceder rápidamente a la información relevante.