"""Comprueba conexión y disponibilidad del modelo sin generar contenido ni imprimir claves."""
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
import os
from src.paths import ENV_FILE
from src.ajustes import modelo_gemini


def comprobar(generar=False):
    load_dotenv(ENV_FILE)
    solicitado=modelo_gemini()
    if not os.getenv('GEMINI_API_KEY'):return dict(conexion=False,motivo='Falta GEMINI_API_KEY',modelo=solicitado)
    cliente=None
    try:
        cliente=genai.Client(api_key=os.environ['GEMINI_API_KEY'],http_options=types.HttpOptions(timeout=12000,retry_options=types.HttpRetryOptions(attempts=1)))
        modelos=list(cliente.models.list(config={'page_size':100}))
        nombres=[m.name.removeprefix('models/') for m in modelos]
        datos=dict(conexion=True,modelo=solicitado,modelo_disponible=solicitado in nombres,
            modelos_flash=[m for m in nombres if 'flash' in m][:12])
        if generar:
            try:
                cliente.models.generate_content(model=solicitado,contents='Responde solamente OK.',config=types.GenerateContentConfig(max_output_tokens=24))
                datos['generacion']='correcta'
            except Exception as e:
                datos['generacion']=dict(tipo=type(e).__name__,codigo=getattr(e,'code',None))
        return datos
    except Exception as e:
        return dict(conexion=False,tipo=type(e).__name__,codigo=getattr(e,'code',None),modelo=solicitado)
    finally:
        if cliente:cliente.close()


if __name__=='__main__':
    import sys
    print(json.dumps(comprobar('--generar' in sys.argv),ensure_ascii=False))
