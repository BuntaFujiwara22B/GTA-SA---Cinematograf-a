"""Selección por rol documentado; las fotos siguen siendo referencias visuales."""
import json
from src.paths import ASSETS
from src.datos_cache import leer_json
from src.escenas_semanticas import reparto_pedido


def catalogo_personajes():
    p=ASSETS/'personajes_roles.json'
    return leer_json(p)['actores'] if p.exists() else []


def elegir_reparto(plan, texto):
    roles=reparto_pedido(texto) or plan.roles
    existentes={int(p.stem) for p in (ASSETS/'actors').glob('*.png') if p.stem.isdigit()}
    previos=plan.actores_ids_sugeridos or ([plan.actor_id_sugerido] if plan.actor_id_sugerido is not None else [])
    if plan.actor_id_sugerido is not None:
        previos=[plan.actor_id_sugerido]+previos[1:]
    elegidos=[]
    catalogo=catalogo_personajes()
    for n in range(plan.cantidad_actores):
        rol=roles[n] if n<len(roles) else 'civil'
        candidatos=[a['model_id'] for a in catalogo if rol in a['roles'] and a['model_id'] in existentes]
        anterior=previos[n] if n<len(previos) else None
        # Un skin explícito conserva prioridad. El resto debe respetar un rol pedido.
        explicito=n==0 and __import__('re').search(r'\b(?:skin|modelo|npc)\s*(?:gta\s*)?\d+',texto.lower())
        if anterior in existentes and (explicito or rol=='civil' or anterior in candidatos): elegido=anterior
        elif candidatos: elegido=next((i for i in candidatos if i not in elegidos),candidatos[n%len(candidatos)])
        elif rol!='civil': raise ValueError(f'No hay un personaje catalogado para el rol {rol}.')
        else: elegido=next((i for i in [0,7,11,38,*sorted(existentes)] if i in existentes and i not in elegidos),0)
        elegidos.append(elegido)
    return elegidos


def contexto_reparto(texto):
    roles=set(reparto_pedido(texto))
    actores=catalogo_personajes()
    relevantes=[a for a in actores if roles.intersection(a['roles'])]
    return '\nREPARTO CON ROLES DOCUMENTADOS (peds.ide + capturas; respeta uniformes):\n'+json.dumps(relevantes or actores[:24],ensure_ascii=False)


def fotos_reparto(texto):
    roles=set(reparto_pedido(texto))
    encontrados=[]
    for rol in sorted(roles):
        encontrados.extend([a for a in catalogo_personajes() if rol in a['roles']][:2])
    return encontrados[:6]
