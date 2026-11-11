from src.paths import RESOURCE_ROOT
from src.datos_cache import leer_json
"""Fotografías relevantes para la consulta y análisis visual persistido."""
import io
import json
from pathlib import Path
from PIL import Image
from src.climas import ASSETS, preview_clima, NOMBRES

CATALOGO=ASSETS/'climas_analisis_visual.json'


def imagen_reducida(ruta):
    with Image.open(ruta) as im:
        im=im.convert('RGB')
        im.thumbnail((384,240))
        salida=io.BytesIO();im.save(salida,format='JPEG',quality=75)
        return salida.getvalue()


def contexto_climas():
    datos=leer_json(CATALOGO) if CATALOGO.exists() else {'resultados':{}}
    return ('\nAMBIENTACION: IDs reales de clima: '+json.dumps(dict(enumerate(NOMBRES)),ensure_ascii=False)
        +'\nAtardecer: depende de hora, normalmente 18 o 19, no es un ID de clima. '
        'Lluvia requiere clima 8 o 16. Las fotos son referencias; no prueban su ID ni el resultado en otro lugar. '
        'Analisis visual disponible de las fotografias:\n'+json.dumps(datos['resultados'],ensure_ascii=False))


def fotos_candidatas(ambiente,texto=''):
    hora=ambiente.get('hora_sugerida',12)
    clima=ambiente.get('clima_id_sugerido',0)
    combinaciones=[(hora,clima)]
    if clima in (8,16):combinaciones.extend([(hora,16 if clima==8 else 8),(hora,0)])
    elif hora in (18,19):combinaciones.extend([(19 if hora==18 else 18,clima),(hora,18)])
    resultado=[]
    for h,c in combinaciones:
        p=preview_clima(h,c)
        if p:resultado.append((p,imagen_reducida(ASSETS/p['archivo'])))
    if texto:
        from src.clip_visual import consulta_ambiente,buscar_fotos
        consulta=consulta_ambiente(texto)
        if consulta:
            existentes={p['archivo'] for p,_ in resultado}
            for candidata in buscar_fotos(consulta,2):
                p=ASSETS/candidata['archivo']
                if p.resolve().is_relative_to(ASSETS.resolve()) and p.is_file() and candidata['archivo'] not in existentes:
                    resultado.append((candidata,imagen_reducida(p)))
    return resultado
