# Cómo usarlo

Guarda tu fichero original como *_traducido, segun el input del usuario.

Ejecuta en tu PC (requiere Python 3.8+):

```bash

#!/bin/bash

# Preferente - Automatizada - automatiza todo el proceso (ejemplo con deepseek)
python orquestador.py --input-file misiones.txt --input-path misiones_origen --output-path misiones_traducidas --engine deepseek --keys keys.txt


# otras opciones
# Standalone - Motor automático y salida <file>_traducido.lua (necesaria extracción manual del fichero a traducir)
python traducir_dcs_dictionary_v1.py F5-E-C9.lua --engine deepseek --keys keys.txt


# Para modo silencioso
--quiet

# Para continuar despite errores
--skip-errors

# Para traducir todas las claves (no solo las objetivo)
--translate-all

# Para especificar modelo específico
--model gpt-4o-mini

```

El script solo traduce los valores de:

-- DictKey_ActionText*

-- DictKey_descriptionText*

-- DictKey_ActionRadioText*

-- DictKey_descriptionBlueTask*

Todo lo demás (nombres de grupos/unidades, ENFIELD, YOU, TOWER, etc.) permanece igual.

Mantiene los finales de línea dentro de las cadenas exactamente como en DCS ( \ antes del salto).


# ORQUESTADOR - orquestador.py

Cambiar el fichero target:

```python

def find_dictionary_file(extract_dir: Path):
    """Busca el archivo dictionary en la estructura descomprimida"""
    possible_paths = [
        extract_dir / 'l10n' / 'DEFAULT' / 'dictionary',
        extract_dir / 'l10n' / 'DEFAULT' / 'dictionary.lua',
        extract_dir / 'dictionary',
        extract_dir / 'dictionary.lua',
    ]

```

# PROMT - traducir_dcs_dictionary_v1.py

Modificar función:

```python

def build_prompt(items: list, style: str) -> dict:
    """
    Construye estructura independiente del proveedor.
    Devuelve {system_text, user_text_json_string}
    """
    # Importante: NO usar .format() con llaves JSON, para evitar KeyError por sustitución.
    system = (
        f"Eres un traductor especializado en frases de aviación militar para el simulador DCS World. "
        f"Traduce del inglés al español de España (es-ES) utilizando la fraseología técnica y militar aeronáutica adecuada. "
        f"**RESPETA Y NO TRADUZCAS BAJO NINGÚN CONCEPTO:** "
        f"- Todo el texto contenido entre corchetes [ej: [OVERLORD], [YOU]]. "
        f"- Acrónimos, códigos y términos breves OTAN/OTAN (ej: Scramble, Splash, Fox 1/2/3, SAR, CAP, SEAD, CAS, JTAC, AWACS, RTB, Bingo, Joker, Winchester, BRAA, Bullseye, Tally, Blind, No Joy, Spike, Magnum, Guns Guns Guns). "
        f"- Nombres en clave de la OTAN para equipos y aeronaves (ej: MiG-21 'Fishbed', Su-27 'Flanker', MiG-29 'Fulcrum', SA-6 'Gainful', ZSU-23-4 'Shilka'). "
        f"- Indicativos de radio (ej: ENFIELD 1-1, OVERLORD, HUMMER, TOWER, KNIFE 1-1). "
        f"- Modelos de aeronaves, armamento y sistemas (ej: F-5E, F-16C, Su-25T, AIM-9M, R-73, R-27ER, KH-25ML). "
        f"- Números, valores, unidades de medida y coordenadas (ej: 270 for 40, Angels 15, 450 knots, 15 NM, 350°). "
        f"- Nombres propios de lugares y calles (ej: Batumi, Kutaisi, Senaki, Gudauta). "
        f"**TRADUCCIÓN:** El estilo de la traducción debe ser {style}. "
        f"**PRECISIÓN:** La traducción debe ser extremadamente fiel al original. No inventes, añadas, omitas ni interpretes información. "
        f"**FORMATO:** Mantén escrupulosamente todos los caracteres de escape (\), saltos de línea, guiones y signos de puntuación del texto original. "
        f"**SALIDA:** Devuelve ÚNICA y EXCLUSIVAMENTE un objeto JSON válido, sin ningún otro texto antes o después, con la siguiente estructura exacta: "
        r'{"translations":[{"key":"DictKey_ActionText_1234", "text":"Texto traducido aquí."}]}'
    )
    user_payload = {"translations":[{"key":it["key"], "text":it["text"]} for it in items]}
    user = (
        "Traduce los 'text' a español (es-ES). No modifiques lo entre corchetes ni los acrónimos indicados. "
        "Mantén las barras invertidas \\ tal cual. Responde ÚNICAMENTE con JSON en el formato indicado.\n"
        + json.dumps(user_payload, ensure_ascii=False)
    )

```