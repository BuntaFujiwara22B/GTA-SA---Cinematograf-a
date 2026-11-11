"""Prueba una secuencia sin escribir el catalogo compartido con el analizador nocturno."""
import json
import os
from dotenv import load_dotenv
from google.genai import types
from tools.analizar_animaciones import CATALOGO, SALIDA, ROOT, INSTRUCCIONES, Descripcion
from src.groq_animaciones import ClienteGroq, MODELO_GROQ


def main():
    load_dotenv(ROOT / '.env')
    clave = os.getenv('GROQ_API_KEY')
    if not clave:
        raise ValueError('Falta GROQ_API_KEY en .env')
    catalogo = json.loads(CATALOGO.read_text(encoding='utf-8'))
    resultados = json.loads(SALIDA.read_text(encoding='utf-8'))['resultados']
    pendientes = [a for a in catalogo['animaciones'] if
        f"{a['categoria']}:{a['idx']}:{a['lib']}:{a['anim']}" not in resultados]
    a = pendientes[0] if pendientes else catalogo['animaciones'][0]
    print(f"Prueba Groq: {a['categoria']}:{a['idx']}:{a['lib']}:{a['anim']}", flush=True)
    partes = [f"Categoria: {a['categoria']}; indice: {a['idx']}; anim: {a['anim']}; biblioteca: {a['lib']}."]
    for f in sorted(a['fotogramas'], key=lambda f: f['frame']):
        partes.append(f"FRAME {f['frame']} (fase {f['fase']})")
        partes.append(types.Part.from_bytes(data=(CATALOGO.parent / f['archivo']).read_bytes(), mime_type='image/png'))
    respuesta = ClienteGroq(clave).generar(MODELO_GROQ, partes, INSTRUCCIONES, Descripcion.model_json_schema())
    analisis = Descripcion.model_validate_json(respuesta.text)
    salida = CATALOGO.parent / 'prueba_groq.json'
    salida.write_text(json.dumps(dict(modelo='groq:' + MODELO_GROQ,
        categoria=a['categoria'], idx=a['idx'], anim=a['anim'], lib=a['lib'],
        analisis=analisis.model_dump()), ensure_ascii=False, indent=2), encoding='utf-8')
    print('Prueba valida guardada en ' + str(salida))


if __name__ == '__main__':
    main()
