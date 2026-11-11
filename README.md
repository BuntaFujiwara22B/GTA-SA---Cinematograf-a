# MMS-Director

Genera archivos `.mms` para crear escenas en GTA San Andreas con Mission Maker.
Automatiza la preparación de personajes, acciones, ubicaciones y ambiente para
ahorrar horas de configuración manual.

## Instalación

En Windows, con Python 3.12 y Git instalados, abre PowerShell y ejecuta:

```powershell
git clone https://github.com/BuntaFujiwara22B/GTA-SA---Cinematograf-a.git
cd GTA-SA---Cinematograf-a
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para reproducir los archivos generados necesitas GTA San Andreas con Mission Maker.

## Configurar Gemini

Crea una clave de API en [Google AI Studio](https://aistudio.google.com/api-keys).
En la carpeta del proyecto, crea un archivo llamado `.env` con este contenido:

```dotenv
GEMINI_API_KEY=tu_clave_de_api
GEMINI_MODEL=gemini-3.5-flash
```

Sustituye `tu_clave_de_api` por tu clave y usa un modelo Gemini disponible en tu
cuenta. Inicia el programa:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Cómo funciona

Escribe la escena que quieres crear, por ejemplo:

> Una persona camina por la playa al atardecer.

Gemini interpreta la petición y propone los personajes, las acciones, el lugar y
el ambiente usando los catálogos del programa. La aplicación convierte ese plan
en un archivo `.mms`.

Revisa la propuesta, elige la cámara y genera la escena. Los archivos se guardan
en `salida_mms/`. Usa **Instalar en GTA** y selecciona la carpeta del juego para
copiar la misión y sus recursos, o **Guardar misión completa** para elegir dónde
guardarla.
