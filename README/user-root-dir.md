# Carpeta Raíz de Usuario

## ¿Qué es la carpeta raíz de usuario?

Es la **carpeta principal** donde están almacenadas todas tus campañas de DCS World. Esta configuración le dice al traductor dónde debe buscar las campañas que quieres traducir.

## Ubicaciones típicas

### 🎮 **Instalación Steam**
```
C:\Program Files (x86)\Steam\steamapps\common\DCSWorld\
```

### 💿 **Instalación Standalone** 
```
C:\Program Files\Eagle Dynamics\DCS World\
C:\Program Files\Eagle Dynamics\DCS World OpenBeta\
```

### 💾 **Saved Games**
```
C:\Users\[TuNombre]\Saved Games\DCS\
C:\Users\[TuNombre]\Saved Games\DCS.openbeta\
```

### 🛠️ **Instalaciones Personalizadas**
Cualquier carpeta donde hayas instalado DCS World

## ¿Cómo encontrar mi carpeta?

### Método 1: Desde DCS World
1. Abre DCS World
2. Ve a **Settings** → **Special** → **DCS Installation**
3. Copia la ruta que aparece

### Método 2: Navegación Manual
1. Abre el Explorador de Windows
2. Busca la carpeta donde tienes DCS instalado
3. Navega hasta encontrar la carpeta **Campaigns** o **Mods**

### Método 3: Steam (si usas Steam)
1. Abre Steam
2. Biblioteca → DCS World → Clic derecho
3. **Administrar** → **Examinar archivos locales**

## Estructura esperada

Tu carpeta raíz debe contener algo como:

```
📁 DCS World/
├── 📁 Bin/
├── 📁 Mods/
│   └── 📁 campaigns/
├── 📁 Campaigns/
├── 📁 Scripts/
└── 📁 Textures/
```

## ¿Por qué es importante?

✅ **Encuentra campañas**: El traductor sabrá dónde buscar  
✅ **Estructura correcta**: Respeta la organización de DCS  
✅ **Traducciones precisas**: Traduce en el contexto correcto  
✅ **Evita errores**: No se pierden archivos o referencias  

## Configuración recomendada

### 🚀 **Para principiantes**
Usa la **auto-detección** de DCS y deja que el sistema encuentre automáticamente tu instalación.

### ⚙️ **Para usuarios avanzados**
Configura manualmente la ruta si:
- Tienes múltiples instalaciones de DCS
- Usas una estructura de carpetas personalizada
- Solo quieres traducir campañas específicas

## Resolución de problemas

### ❌ **"No se encuentran campañas"**
- Verifica que la ruta apunte a la carpeta correcta de DCS
- Asegúrate de que existe la subcarpeta **Campaigns** o **Mods/campaigns**

### ❌ **"Acceso denegado"**
- Ejecuta el traductor como administrador
- Verifica que tengas permisos de lectura en la carpeta

### ❌ **"Campañas duplicadas"**
- Es normal, DCS puede tener campañas en múltiples ubicaciones
- Selecciona la versión que prefieras traducir

## Consejo profesional

Si tienes **múltiples versiones** de DCS (Alpha, Beta, Release), cada una tiene su propia carpeta raíz. Configura un perfil diferente para cada versión para mantener las traducciones organizadas.