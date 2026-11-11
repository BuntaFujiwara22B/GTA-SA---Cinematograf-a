"""Recupera pocas capturas reales por petición; no vuelve a analizar todo el catálogo."""
from src.catalogo_animaciones import CARPETA
from src.datos_cache import leer_json
from src.busqueda_animaciones import buscar_animaciones,normalizar
from src.capacidades_escena import candidata_local


def fotos_candidatas_animacion(texto,limite=4):
    archivo=CARPETA/'catalogo.json'
    if not archivo.exists():return []
    favorita=candidata_local(normalizar(texto))
    ids=([favorita[1]['id']] if favorita else [])+[o['id'] for o in buscar_animaciones(texto,limite=2)]
    datos=leer_json(archivo).get('animaciones',[])
    resultado=[]
    for identificador in dict.fromkeys(ids):
        entrada=next((a for a in datos if f"{a['categoria']}:{a['idx']}:{a['lib']}:{a['anim']}"==identificador),None)
        if entrada is None:continue
        fotos=[f for f in entrada.get('fotogramas',[]) if not f.get('revisar_por_tamano')]
        fotos=sorted(fotos,key=lambda f:abs(f['fase']-.55))[:2]
        for foto in fotos:
            p=(CARPETA/foto['archivo']).resolve()
            if not p.is_relative_to(CARPETA.resolve()) or not p.is_file() or p.stat().st_size<25000:continue
            resultado.append((dict(id=identificador,frame=foto['frame'],fase=foto['fase'],
                limitacion='Pose pausada: no demuestra duración, velocidad ni objetos presentes.'),p))
            if len(resultado)>=limite:return resultado
        if len(resultado)>=limite:return resultado
    return resultado
