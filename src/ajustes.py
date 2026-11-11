"""Configuración por usuario; las claves nunca se incluyen en la distribución."""
import os
from pathlib import Path
from dotenv import load_dotenv,set_key
from src.paths import DATA_ROOT,ENV_FILE,RESOURCE_ROOT
from src.datos_cache import leer_json

CONFIG=DATA_ROOT/'config.json'


def ajustes():
    return leer_json(CONFIG) if CONFIG.exists() else {}


def modelo_gemini():
    return os.getenv('GEMINI_MODEL') or ajustes().get('gemini_model','gemini-3.5-flash')


def guardar(clave,modelo,gta):
    import json
    DATA_ROOT.mkdir(parents=True,exist_ok=True)
    if clave.strip():
        if '\n' in clave or '\r' in clave:raise ValueError('La clave debe ocupar una sola línea.')
        if not ENV_FILE.exists():ENV_FILE.touch()
        set_key(str(ENV_FILE),'GEMINI_API_KEY',clave.strip())
        os.environ['GEMINI_API_KEY']=clave.strip()
    if not modelo.strip() or len(modelo)>120:raise ValueError('Indica un nombre de modelo válido.')
    datos=dict(ajustes(),gemini_model=modelo.strip(),gta_path=gta.strip())
    temp=CONFIG.with_suffix('.tmp');temp.write_text(json.dumps(datos,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(CONFIG)
    os.environ['GEMINI_MODEL']=modelo.strip()


def instalar_comprobador():
    import re
    import shutil
    gta=Path(ajustes().get('gta_path',''))
    if not gta.is_absolute() or not (gta/'gta.exe').is_file():
        raise ValueError('Configura la carpeta que contiene tu gta.exe.')
    moon=gta/'moonloader'
    if not moon.is_dir():raise ValueError('Esta instalación no tiene MoonLoader.')
    ipc=DATA_ROOT/'ruta_mvp';ipc.mkdir(parents=True,exist_ok=True)
    base=ipc.as_posix()+'/'
    if "'" in base:raise ValueError('La ruta de datos contiene un apóstrofo no compatible con este comprobador.')
    lua=(RESOURCE_ROOT/'comprobar_ruta_mvp.lua').read_text(encoding='utf-8')
    lua=re.sub(r"local BASE='[^']*'",lambda _:"local BASE='"+base+"'",lua,count=1)
    destino=moon/'comprobar_ruta_mvp.lua'
    if destino.exists():
        backup=destino.with_suffix('.lua.bak')
        if not backup.exists():shutil.copy2(destino,backup)
    destino.write_text(lua,encoding='utf-8')
    return destino
