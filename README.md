# DCS-SPANISH-TRANSLATE-MODEL-V2

Traductor de misiones DCS al español utilizando un modelo (IA) local y LM Studio.

Versiones:

2.0 (latest)

</br>

## DCS Orquestador Traductor (Web)

### 🚀 ¿Cómo se ejecuta?

#### **🎯 Opción 1: Lanzador Directo (MÁS FÁCIL)**
- Doble clic en `Traductor - DCS.bat` (directorio raíz)
- **Ideal para:** Usuario final sin conocimientos técnicos
- **Ventajas:** 
  - ✅ Incluido en el repositorio, funciona inmediatamente
  - ✅ **Genera siempre** el acceso directo `Traductor - DCS.lnk` con icono actualizado
  - ✅ Obtienes ambas opciones: `.bat` (portable) + `.lnk` (con icono)

#### **🎯 Opción 2: Script CMD Alternativo (FÁCIL)** 
- Doble clic en `run\run_orquestador.cmd`
- **Ideal para:** Usuario que prefiere usar la carpeta `run\`

#### **🎯 Opción 3: Python Directo (AVANZADO)**

```bash
# Ejecutar directamente el servidor Flask
python run\run_flask_app.py
```

- **Ideal para:** Desarrolladores o usuarios avanzados

#### **🎯 Opción 4: Script PowerShell (INTERMEDIO)**
- Clic derecho en `run\run_orquestador.ps1` → "Ejecutar con PowerShell"
- **Ideal para:** Usuario con PowerShell habilitado

### 🔗 Generación Automática de Acceso Directo

El acceso directo con icono **se genera automáticamente** cada vez que ejecutes `Traductor - DCS.bat`.

Si necesitas crearlo manualmente sin ejecutar la aplicación:

```powershell
.\run\create_shortcut.ps1
```

> **💡 Tip:** El `.lnk` no se incluye en el repositorio pero se genera dinámicamente con las rutas correctas de tu sistema.

---

## 📥 Para Usuarios Nuevos (Descarga desde GitHub)

Si acabas de descargar/clonar este repositorio:

### **🚀 ¡PRIMERA VEZ? ¡NO HAY PROBLEMA!**

**¿No tienes Python instalado?**
1. ✅ **¡YA ESTÁ LISTO!** Doble clic en `Traductor - DCS.bat`
2. 🔧 **INSTALACIÓN AUTOMÁTICA**: Te preguntará si quieres instalar Python automáticamente
3. ⏱️ **2-3 minutos**: El sistema descargará e instalará Python por ti
4. 🎉 **LISTO**: Se generará `Traductor - DCS.lnk` con icono y se abrirá la aplicación

**¿Ya tienes Python?**
1. **¡YA ESTÁ LISTO!** Doble clic en `Traductor - DCS.bat`
2. **¡AUTOMÁTICO!** Se genera `Traductor - DCS.lnk` con icono personalizado
3. **Siempre disponibles:** Ambos archivos para tu comodidad

### **🔧 Instalación Inteligente de Python**

El sistema detectará automáticamente si necesitas Python y:

- 🤖 **Opción A (Recomendada)**: Instalación automática silenciosa
  - Descarga Python 3.11+ oficial desde python.org
  - Configura PATH automáticamente  
  - Instala pip y dependencias
  - No requiere conocimientos técnicos

- 🌐 **Opción B (Manual)**: Te lleva a python.org para instalación manual
  - Para usuarios que prefieren control total
  - Instrucciones claras paso a paso

> **🎉 Ventajas:** 
> - `Traductor - DCS.bat` funciona **incluso sin Python instalado**
> - Instalación completamente automatizada de todas las dependencias
> - Genera automáticamente el acceso directo con icono DCS actualizado  
> - Sin archivos .lnk en el repositorio (se crean dinámicamente)
> - **Primera experiencia perfecta**: de descarga a funcionando en 3 minutos

---

## 🔄 Flujo de Ejecución Automático

### **Cada vez que ejecutas `Traductor - DCS.bat`:**
1. 🔗 **Genera/actualiza** automáticamente `Traductor - DCS.lnk`
2. ✅ **Asegura** que el acceso directo tiene el icono DCS actualizado
3. 🚀 **Lanza** la aplicación web
4. 💡 **Te informa** que también puedes usar el `.lnk` directamente

### **Opciones de lanzamiento disponibles:**
- 🖱️ **Opción A:** Doble clic en `Traductor - DCS.bat` (genera .lnk + lanza app)
- 🖱️ **Opción B:** Doble clic en `Traductor - DCS.lnk` (lanza app directamente)

---

### ⚙️ ¿Qué hace el script automáticamente?

- 🔍 **Detecta Python 3** (lo instala automáticamente si no está disponible)
- 🐍 **Instala Python desde python.org** (descarga oficial, instalación silenciosa)
- 📦 **Configura pip** automáticamente (gestor de paquetes de Python)
- 🏠 **Crea entorno virtual** `.venv` automáticamente
- 📚 **Instala dependencias** desde `run\requirements.txt`
- 🚀 **Lanza el servidor Flask** en `http://127.0.0.1:5000/orchestrator`
- 🌐 **Abre el navegador** automáticamente (~90 segundos la primera vez)

**🎯 Experiencia de usuario:**

- **Usuario sin Python**: Instalación automática + configuración completa (~3 minutos)
- **Usuario con Python**: Configuración directa + apertura inmediata (~90 segundos)
- **Sin conocimientos técnicos requeridos** para ninguno de los casos

Necesitas LM Studio para traducir con modelos locales (ver sugerencias). Si no hay modelo cargado/servidor activo, la UI te avisará y podrás pulsar "🔄 Escanear LM Studio" para refrescar la lista.

</br>
</br>

## Ayudas disponibles dentro de la aplicación

Cuando se abre la web del orquestador (en <http://localhost:5000>), verás:

Un botón “❓ Ayuda” arriba a la derecha con una guía rápida sobre:

Descarga, instalación y configuración de LM Studio.

Activación del servidor local (API).

Botones “?” contextuales en:

Presets (qué son y cómo guardarlos/cargarlos/borrarlos).

ROOT_DIR (qué carpeta seleccionar y detección automática).

FILE_TARGET (qué archivo se traduce dentro del .miz).

ARGS (cada parámetro: --config, --lm-compat, --batch-size, --timeout, --lm-model, --lm-url).

Modo (qué hace translate, miz, all, deploy).

Incluir misiones -FC- (Flaming Cliffs) (qué significa).

DEPLOY_DIR y DEPLOY_OVERWRITE (dónde se copian los .miz y cómo evitar sobrescribir los originales).

Estas ayudas se abren en un mini-modal con explicaciones claras y ejemplos.
Además, en la lista de misiones aparece una leyenda arriba con los estados:

✅ Deploy = empaquetada en finalizado/

✨ Traducida = hay .translated.lua en out_lua/ (pero aún no se empaquetó el .miz)

Sugerencias útiles

LM Studio: activa la API local (Developer → Enable Local Server) y carga un modelo “Instruct”.
Después, en la UI del orquestador pulsa “🔄 Escanear LM Studio”.

Firewall: si Windows pregunta, permite a Python escuchar en 127.0.0.1:5000.

Atajos: crea un acceso directo al .ps1 y usa “Run with PowerShell”.

Problemas de ejecución: si PowerShell bloquea scripts, ejecuta una vez:

Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

Actualizar dependencias: si añades librerías nuevas, crea un requirements.txt y el .ps1 las instalará.

</br>
</br>

## Rutas y manejo de errores

### Estructura de carpetas (lado orquestador)

```text
campaings/<slug_de_campaña>/extracted/
Carpeta temporal donde se descomprime cada .miz al procesarlo.

campaings/<slug_de_campaña>/out_lua/
Aquí se guardan:

NOMBRE_BASE.lua (copia del diccionario extraído).

NOMBRE_BASE.translated.lua (resultado de la traducción).

Logs del traductor dcs_translate_*.log (que luego se mueven a log_orquestador/).

campaings/<slug_de_campaña>/finalizado/
.miz empaquetados listos para deploy.

campaings/<slug_de_campaña>/backup/
Copias de seguridad de .miz originales cuando toca.

log_orquestador/

web_orquestador_<pid>.log: log de la app web.

error.log: errores de traducción (ver siguiente sección).

logs_<campaña>_<timestamp>.zip: zip de logs por campaña al finalizar.
```

Nota: el directorio ROOT_DIR que seleccionas en la UI es la carpeta del juego con las campañas originales, típicamente algo como:
`C:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns`

</br>

## Estados de misiones

✨ Traducida: Existe NOMBRE_BASE.translated.lua en out_lua/ para esa misión.

✅ Deploy: Ya se empaquetó un .miz en finalizado/.

Si ejecutas modo miz sobre una misión “✨ Traducida”, al terminar la UI la cambiará automáticamente a ✅ Deploy (sin tener que re-escanear).

Captura de errores (flujo)

Durante la traducción (translate_lua)

Si el proceso falla, se registra un error genérico con campaña y misión.

Al finalizar cada traducción, el orquestador:

Lee todos los dcs_translate_*.log que el traductor dejó en out_lua/.

Extrae bloques que contengan ERROR: (por ejemplo, No se pudo parsear el JSON ni el sub-JSON…).

Registra cada bloque con su misión.

Persistencia:

Cada error se prepone en log_orquestador/error.log (los más nuevos arriba).

</br>

### UI

En la sección “Estado” aparece un panel “Errores recientes” con hasta 50 entradas, ordenadas de más nuevas a más antiguas.

Cada entrada incluye:

Cabecera: `[YYYY-MM-DD HH:MM:SS] campaña::misión`

Cuerpo: el texto completo del error (respetando saltos de línea y bloques ```json ...``` si aplica).

Ejemplo de línea de error (en el log)

```text
[2025-09-20 20:44:53] ERROR: C21::F5-E-C21
No se pudo parsear el JSON ni el sub-JSON. Respuesta cruda: ```json
[{"id": "id_4552f5780ba667bc", "es": "[El Escuadrón Agresor 65 está asignado al Grupo de Tácticas Adversarias 57, ubicado en Nellis"}, ...]
```

La cabecera incluye `campaña::misión` y el cuerpo mantiene el bloque JSON tal cual.

</br>
</br>

### ¿Cómo solucionar errores comunes?

#### 1. "No se pudo parsear el JSON…"

Revisa el dcs_translate_*.log asociado y el bloque de respuesta.

Suele deberse a que el modelo no cerró brackets/comillas o introdujo texto adicional fuera del JSON.

Prueba con:

Aumentar --timeout.

Reducir --batch-size (por ejemplo, 1–2).

Cambiar/ajustar --config (YAML con reglas más estrictas: “responder solo JSON válido”).

Probar otro modelo más estable para tareas estructuradas.

</br>

#### 2. "No aparece translated.lua o está vacío"

Asegúrate de que FILE_TARGET apunta al diccionario correcto dentro del .miz.
Por defecto: l10n/DEFAULT/dictionary (o l10n/RUS/dictionary, etc. según la campaña).

</br>

#### 3. "No detecta el modelo en LM Studio"

Verifica que la API local está activa (Developer → Enable Local Server).

Comprueba que la URL en --lm-url sea <http://localhost:1234/v1> (o la que corresponda).

Pulsa “🔄 Escanear LM Studio” para refrescar.

</br>
</br>

## EXTRA V1(BETA) - este script se integrará en el futuro en el modelo V2 para poder usar modelos públicos

Si queremos usar un modelo público (deepseek, chatgpt, etc) usar el script dentro de la carpeta `EXTRA V1(BETA)`.

Ten en cuenta que necesitarás una cuenta developer y pagar la suscripción a la API.

</br>
</br>

## REQUISITOS

- Requiere Python 3.8+
- LM Studio
- VSCODE (recomendado para trabajar con el script)

</br>
</br>

## UPDATES CHANGELOG

- v250921-2 (actualizado el 21/09/2025)

Se añade front para cargar el orquestador con Flask a través del navegador.

Se añade:

- Flask (web)
- Aviso de actualizaciones
- cmd

Se arregla problema de carga de los ficheros YML de PROMT/

--->

Lista las misiones en dos bloques: primero normales (C1, C2, …) y luego Flaming Cliffs (-FC-).

Pregunta si quieres incluir las -FC-.

Quita el tail en vivo de los logs y muestra un porcentaje global de progreso por misiones seleccionadas.

Mantiene intacto el modo deploy.

Conserva la auto-carga del modelo si el modo es translate o all.

Maneja nombres con espacios tipo C21 .miz.
