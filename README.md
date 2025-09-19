# DCS-SPANISH-TRANSLATE-MODEL-V2

Traductor de misiones DCS al español utilizando un modelo (IA) local y LM Studio.

<br>
<br>

## REQUISITOS

- Requiere Python 3.8+
- LM Studio
- VSCODE (recomendado para trabajar con el script)

<br>
<br>

## USO

1. Instalación de LM STUDIO https://lmstudio.ai/

Configurar segun los requerientos de tu PC, lo ideal es activar el uso de la GPU.

Se elige el runtime compatible con tu equipo.


![alt text](images/1_LM_runtime.png)

![alt text](images/2_LM_hardware.png)


<br>
<br>

2. Una vez configurado instalar uno de estos dos modelos, o cualquier otro que quieras probar, se recomiendan los tipo "instruct", lo que he probado son estos dos:

(desde "Discover")

- `lmstudio-community/gemma-2-27b-it-GGUF` : mejor y mas preciso, pero mas lento.

- `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF` : más rápido, menos preciso.

![alt text](images/3_LM_search.png)

<br>
<br>

3. Configurar el archivo `config*.txt`

Estan los ejemplos en el propio fichero y en EXAMPLES.

<br>
<br>

4. Ejecutar el script en la terminal (powershell, cmd o bash) con:

(este llama a `dcs_lua_translate.py`)

```

# puedes pasarle cualquier archivo, "config-F5.txt" es un ejemplo pero es obligatorio pasarle el fichero.

python orquestador.py --config "config-F5.txt"

```

Lee lo que tengamos en `config-F5.txt`, importante dejarlo bien configurado y adaptado a tu equipo.

"ROOT_DIR: D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns" (CAMBIAR) indica donde tienes las misiones de DCS y las autodetecta.

"FILE_TARGET: l10n/DEFAULT/dictionary" le indicas donde estan el fichero a traducir dentro del .miz.

"ARGS" son los argumentos para la ejecución se puede dejar tal como está, pero sirve  para cambiar el modelo --lm-model.

"DEPLOY_DIR: D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns" (CAMBIAR) es donde desplegamos la campañas traducidas con la opción 4.

"DEPLOY_OVERWRITE: false" DEPLOY_OVERWRITE en config*.txt (true/false). Si true, sobrescribe los .miz originales con backup automático; si false, copia a Translated_ES/, en tu caperta del juego para que los sustituyas manualmente.

```txt

# EJEMPLOS

# opción simple de lanzamiento
# python orquestador.py --config "config-F5.txt"

# opción para elegir translator 
# python orquestador.py --config "config-F5.txt" --translator "dcs_lua_translate.py"


ROOT_DIR: D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns
FILE_TARGET: l10n/DEFAULT/dictionary
ARGS: "--config 2-completions-PROMT.yaml --batch-size 4 --timeout 200 --lm-model google/gemma-2-27b --lm-compat completions --lm-url http://localhost:1234/v1"

# Opcionales para deploy:
DEPLOY_DIR: D:\Program Files\Eagle Dynamics\DCS World\Mods\campaigns
DEPLOY_OVERWRITE: false

```

Elegimos una de las opciones:

```txt

1) translate  (extrae y traduce; NO reempaqueta)
2) miz        (NO traduce; reempaqueta; inserta traducción si existe)
3) all        (traduce y reempaqueta)
4) deploy     (copiar .miz finalizados al directorio del juego)

```

Cada una de las opciones está explicada en el propio script.

![alt text](images/4_terminal.png)

Podemos ir viendo las traducciones en tiempo real:

![alt text](images/5_LM_developer.png)

En la carpeta que se genera al lanzar la traducción `campaings\*`, se encuentran los ficheros de log, asi como un fichero tipo caché , donde se pueden modificar manualmente las traducciones y relanzar la traducción.

La carpeta `log_orquestador`, contiene logs.

<br>
<br>

## EXTRA V1(BETA)

Si queremos usar un modelo público (deepseek, chatgpt, etc) usar el script dentro de la carpeta `EXTRA V1(BETA)`.

Ten en cuenta que necesitarás una cuenta developer y pagar la suscripción a la API.
