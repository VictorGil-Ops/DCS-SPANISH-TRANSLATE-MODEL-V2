# Detección FC (Flaming Cliffs)

## ¿Qué es Flaming Cliffs?

**Flaming Cliffs (FC)** es una serie de módulos de aeronaves **simplificados** para DCS World. A diferencia de las aeronaves "full-fidelity" (simulación completa), las aeronaves FC ofrecen una experiencia más arcade pero accesible.

## Diferencias entre FC y Full-Fidelity

### ✈️ **Aeronaves Flaming Cliffs**

**Características:**
- **Simulación simplificada** de sistemas
- **Arranque instantáneo** (sin procedimientos complejos)
- **Controles arcade** más accesibles
- **Menos switches y procedimientos** reales
- **Ideal para principiantes** en simulación de vuelo

**Aeronaves incluidas:**
- **A-10A** (versión simplificada del A-10C)
- **F-15C Eagle** 
- **F-16C Fighting Falcon** (versión FC)
- **Su-27 Flanker**
- **Su-33 Flanker-D**
- **MiG-29 Fulcrum**
- **Su-25T Frogfoot**
- **Su-25A Frogfoot**

### 🎯 **Aeronaves Full-Fidelity**

**Características:**
- **Simulación completa** de todos los sistemas
- **Procedimientos reales** de arranque y operación
- **Cockpit completamente funcional**
- **Curva de aprendizaje alta**
- **Experiencia ultra-realista**

**Ejemplos:**
- **A-10C II Tank Killer**
- **F/A-18C Hornet**
- **F-16C Viper** (versión completa)
- **AV-8B Harrier**
- **F-14 Tomcat**

## ¿Por qué detectar FC automáticamente?

### 🔍 **Diferencias en traducción**

Las campañas FC y Full-Fidelity tienen **diferentes tipos de contenido**:

#### **Campañas FC:**
- **Briefings más simples** enfocados en acción
- **Menos procedimientos técnicos** específicos
- **Terminología más general** de combate aéreo
- **Instrucciones arcade** simplificadas

#### **Campañas Full-Fidelity:**
- **Procedimientos detallados** de sistemas reales
- **Terminología técnica específica** de cada aeronave
- **Checklists complejos** de procedimientos
- **Referencias a sistemas avanzados** reales

### ⚙️ **Optimización del traductor**

La detección FC permite:

- **Prompts especializados** para cada tipo
- **Terminología apropiada** según complejidad
- **Parámetros optimizados** para el contenido
- **Mejor calidad** de traducción contextual

## ¿Cómo funciona la detección?

### 🔍 **Métodos de detección**

#### **Por nombre de archivo:**
```
Detecta patrones como:
- "FC" en el nombre de archivo
- "Flaming" en el título
- "Simplified" en descripción
```

#### **Por contenido de la campaña:**
```
Analiza si contiene:
- Referencias a aeronaves FC específicas
- Ausencia de procedimientos complejos
- Terminología simplificada
```

#### **Por metadatos:**
```
Revisa información de:
- Desarrollador/módulo origen
- Tags de clasificación
- Categorías de campaña
```

### 🎯 **Indicadores típicos de FC**

#### **✅ Fuertemente FC:**
- Archivo contiene "-FC-" en nombre
- Mención explícita de "Flaming Cliffs"
- Solo aeronaves de la lista FC
- Procedimientos simplificados

#### **🟡 Posiblemente FC:**
- Mix de aeronaves FC y full-fidelity
- Procedimientos de complejidad media
- Terminología mixta

#### **❌ Claramente Full-Fidelity:**
- Procedimientos detallados específicos
- Referencias a sistemas complejos
- Aeronaves full-fidelity exclusivamente
- Terminología técnica avanzada

## Beneficios de la detección automática

### 🎯 **Traducciones más precisas**

#### **Para campañas FC:**
- **Lenguaje más accesible** y directo
- **Términos generales** en lugar de técnicos específicos
- **Explicaciones simplificadas** de procedimientos
- **Enfoque en diversión** más que realismo

#### **Para campañas Full-Fidelity:**
- **Terminología técnica precisa** y específica
- **Procedimientos detallados** respetando realismo
- **Referencias correctas** a sistemas reales
- **Traducción conservadora** de términos técnicos

### ⚡ **Mejores parámetros de traducción**

#### **Configuración FC:**
```
- Temperatura más alta (creatividad)
- Enfoque en claridad sobre precisión técnica
- Prompts orientados a jugabilidad
- Batch size optimizado para texto simple
```

#### **Configuración Full-Fidelity:**
```
- Temperatura más baja (precisión)
- Enfoque en exactitud técnica
- Prompts orientados a realismo
- Procesamiento cuidadoso de terminología
```

## Configuración manual de detección FC

### ⚙️ **Si la detección automática falla**

#### **Forzar modo FC:**
1. **Identifica manualmente** que es una campaña FC
2. **Activa detección FC** en configuración
3. **Verifica** que se apliquen prompts FC
4. **Prueba** con una misión pequeña

#### **Forzar modo Full-Fidelity:**
1. **Desactiva detección FC** si se activó incorrectamente
2. **Selecciona prompts** específicos de full-fidelity
3. **Ajusta parámetros** para precisión técnica
4. **Valida** terminología en traducción de prueba

### 🔧 **Ajustes finos por tipo**

#### **Optimización para FC:**
```
Preset: Ligero o Balanceado
Batch Size: Alto (procesamiento rápido)
Temperature: 0.6-0.8 (más natural)
Cache: Activado (reutilización frecuente)
```

#### **Optimización para Full-Fidelity:**
```
Preset: Balanceado o Pesado
Batch Size: Medio (procesamiento cuidadoso)
Temperature: 0.2-0.4 (más preciso)
Cache: Selectivo (terminología específica)
```

## Ejemplos de campaña por tipo

### 🟢 **Campañas FC típicas:**
- **F-15C Red Flag Campaign**
- **A-10A Basic Flight Training**
- **MiG-29 Fulcrum Instant Action**
- **Su-27 Air Combat Training**

### 🔴 **Campañas Full-Fidelity típicas:**
- **A-10C Enemy Within**
- **F/A-18C Rise of the Persian Lion**
- **F-16C Red Flag Campaign**
- **AV-8B The Enemy Within**

### 🟡 **Campañas mixtas:**
- Campañas que incluyen tanto aeronaves FC como full-fidelity
- Requieren detección manual o configuración híbrida

## Resolución de problemas

### ❌ **"Detección incorrecta de FC"**
- **Desactiva** la detección automática FC
- **Configura manualmente** el tipo de campaña
- **Revisa** el contenido para confirmar tipo

### ❌ **"Terminología incorrecta en FC"**
- **Activa** la detección FC si no está activa
- **Cambia a prompts FC** específicos
- **Ajusta temperatura** para mayor naturalidad

### ❌ **"Procedimientos demasiado simples"**
- **Desactiva** detección FC
- **Usa configuración full-fidelity**
- **Aumenta precisión** en parámetros

### ❌ **"Mix de aeronaves confunde detección"**
- **Configura manualmente** según aeronave principal
- **Usa prompts genéricos** que funcionen para ambos
- **Divide** en secciones si es posible

## Recomendaciones por experiencia

### 👶 **Nuevos en DCS:**
- **Comienza con campañas FC** (más accesibles)
- **Usa detección automática** sin modificar
- **Aprende diferencias** entre tipos gradualmente

### 👨‍💼 **Pilotos regulares:**
- **Configura detección** según tus módulos preferidos
- **Personaliza prompts** para tus aeronaves principales
- **Mantén configuraciones** separadas para FC vs full-fidelity

### 👨‍💻 **Usuarios avanzados:**
- **Crea prompts específicos** para cada aeronave
- **Automatiza detección** con reglas personalizadas
- **Contribuye** mejorando la detección automática