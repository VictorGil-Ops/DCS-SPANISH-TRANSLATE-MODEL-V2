# DCS-SPANISH-TRANSLATE-MODEL-V2

Traductor de misiones DCS al español utilizando un modelo (IA) local y LM Studio.

Versiones:

v250921 (latest)

</br>

## DCS Orquestador Traductor (Web)

### ¿Cómo se ejecuta?

Opción fácil (recomendada): PowerShell `run-orquestador.ps1`

Coloca run-orquestador.ps1 en la misma carpeta que app.py.

Haz clic derecho → Run with PowerShell (o Ejecutar con PowerShell).

#### El script

Comprueba si tienes Python 3.

Si no lo detecta, te ofrece instalarlo automáticamente con winget.

Crea (o reutiliza) un entorno virtual .venv/.

Actualiza pip e instala dependencias (mínimo flask y requests, o todas las de tu requirements.txt si existe).

Arranca app.py.

Abre automaticamente tu navegador predeterminado en <http://localhost:5000> (tarda unos ~40 segundos con todo ya instalado, si no tarda un poco mas)

Necesitas LM Studio para traducir con modelos locales (ver sugerencias). Si no hay modelo cargado/servidor activo, la UI te avisará y podrás pulsar “🔄 Escanear LM Studio” para refrescar la lista.

Opción manual (para usuarios avanzados)

```powershell

# 1) Ve a la carpeta del proyecto
cd .\ruta\al\proyecto

# 2) (opcional) crear venv e instalar dependencias
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install flask requests

# 3) Ejecutar la app
.\.venv\Scripts\python .\app.py
# Luego abre http://localhost:5000 en tu navegador

```

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

- v250921 (actualizado el 21/09/2025)

Se añade front para cargar el orquestador con Flask a través del navegador.

Lista las misiones en dos bloques: primero normales (C1, C2, …) y luego Flaming Cliffs (-FC-).

Pregunta si quieres incluir las -FC-.

Quita el tail en vivo de los logs y muestra un porcentaje global de progreso por misiones seleccionadas.

Mantiene intacto el modo deploy.

Conserva la auto-carga del modelo si el modo es translate o all.

Maneja nombres con espacios tipo C21 .miz.
