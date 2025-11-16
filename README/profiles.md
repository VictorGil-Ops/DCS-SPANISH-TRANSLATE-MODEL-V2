# Perfiles de Configuración

## ¿Qué son los perfiles?

Los **perfiles de configuración** son una forma de guardar todas tus configuraciones (rutas, modelo, parámetros, etc.) para poder reutilizarlas fácilmente.

## ¿Para qué sirven?

- **🎯 Especialización**: Crea configuraciones específicas para diferentes tipos de traducciones
- **⚡ Rapidez**: Cambia entre configuraciones al instante
- **🔄 Consistencia**: Mantén configuraciones probadas y confiables
- **📁 Organización**: Organiza tus configuraciones por proyecto, modelo o tipo de trabajo

## Casos de uso típicos:

### Por Modelo de IA:
- **"Gemma-2B-Ligero"**: Configuración para modelo pequeño en PC básico
- **"Llama-8B-Balanceado"**: Configuración para modelo mediano
- **"Qwen-27B-Calidad"**: Configuración para modelo grande con máxima calidad

### Por Tipo de Campaña:
- **"Campañas-FC"**: Configuración específica para misiones Flaming Cliffs
- **"Campañas-Full-DCS"**: Configuración para simulaciones completas
- **"Test-Rapido"**: Configuración para pruebas rápidas

### Por Velocidad:
- **"Traducción-Rápida"**: Batch grande, timeout bajo, cache activado
- **"Traducción-Calidad"**: Batch pequeño, timeout alto, cache desactivado

### Por Proyecto:
- **"Proyecto-A10C"**: Configuraciones específicas para campañas del A-10C
- **"Proyecto-F18"**: Configuraciones específicas para campañas del F/A-18C

## Flujo de trabajo recomendado:

1. **📂 Cargar perfil** → Selecciona una configuración base (opcional)
2. **⚙️ Ajustar configuraciones** → Modifica según tus necesidades
3. **💾 Guardar como nuevo perfil** → Crea un perfil con un nombre descriptivo

## Ventajas:

- ✅ **Ahorro de tiempo**: No reconfigures manualmente cada vez
- ✅ **Menos errores**: Usa configuraciones ya probadas
- ✅ **Experimentación**: Prueba diferentes configuraciones fácilmente
- ✅ **Compartir**: Exporta configuraciones para otros usuarios
- ✅ **Respaldo**: Mantén copias de seguridad de tus configuraciones

## Nota importante:

Los perfiles incluyen **TODA** tu configuración:
- Rutas de carpetas (campañas, despliegue)
- Configuración del modelo (URL, modelo seleccionado)
- Parámetros de traducción (batch, timeout, compatibilidad)
- Configuración de cache
- Presets aplicados