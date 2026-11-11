"""Contrato de escenas: tareas nativas y clips reales, nunca nombres MMS inventados."""
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, Field


class PasoEscena(BaseModel):
    accion: Literal['caminar', 'correr', 'nadar', 'escaleras', 'saltar', 'animacion', 'apuntar']
    actores: list[int] = Field(default_factory=lambda: [1], min_length=1, max_length=4)
    objetivo_actor: int | None = Field(default=None, ge=1, le=4)
    animacion: str | None = None
    reproduccion: Literal['auto', 'una_vez', 'mantener', 'bucle'] = 'auto'
    duracion: int | None = Field(default=None, ge=1, le=60)


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if not unicodedata.combining(c))


ROLES = {
    'policia': r'polici\w*|agentes? de policia',
    'granjero': r'granjer\w*|campesin\w*|agricultor\w*',
    'criminal': r'criminal\w*|ladron\w*|delincuent\w*',
    'bombero': r'bomber\w*',
    'paramedico': r'paramedic\w*|medic\w*',
    'militar': r'militar\w*|soldad\w*',
    'guardia': r'guardias?|vigilantes?',
    'civil': r'civil(?:es)?|personas?|personajes?|actores?|npcs?|hombres?|mujer(?:es)?|amigos?|vecinos?|turistas?',
}
NUMEROS = {'un': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6}


def accion_de(plan):
    return plan if isinstance(plan,str) else plan.get('accion') if isinstance(plan,dict) else plan.accion


def es_vehicular(plan):
    return accion_de(plan) in ('entrar_vehiculo','conducir_vehiculo','vehiculo_autonomo','animacion_sobre_vehiculo')


def usa_recorrido_vehicular(plan):
    if accion_de(plan) in ('conducir_vehiculo','vehiculo_autonomo'):return True
    mueve=plan.get('vehiculo_en_movimiento',False) if isinstance(plan,dict) else getattr(plan,'vehiculo_en_movimiento',False)
    return accion_de(plan)=='animacion_sobre_vehiculo' and mueve


def reparto_pedido(texto):
    t = normalizar(texto)
    patron = '|'.join(f'(?P<{r}>{p})' for r, p in ROLES.items())
    resultado = []
    # Cuenta sujetos explícitos, incluidos «3 granjeros» y «un policía ... a un criminal».
    for m in re.finditer(r'\b(?P<n>\d+|un|una|dos|tres|cuatro|cinco|seis)\s+(?:' + patron + r')\b', t):
        n = int(m['n']) if m['n'].isdigit() else NUMEROS[m['n']]
        rol = next(r for r in ROLES if m[r] is not None)
        resultado.extend([rol] * min(n, 20))
    if not resultado:
        for rol, p in ROLES.items():
            if rol != 'civil' and re.search(r'\b(?:' + p + r')\b', t):
                resultado.append(rol)
    if re.search(r'\b(?:a|con) otr[oa](?: personaje| persona)?\b', t) and len(resultado) < 2:
        resultado.append('civil')
    return resultado


def acciones_texto(texto):
    """Orden de las menciones; la IA puede aportar un contrato más preciso."""
    from src.capacidades_escena import FAMILIAS, candidata_local
    t = normalizar(texto)
    halladas = []
    def negada(posicion):
        return bool(re.search(r'\b(?:no|sin)(?:\s+(?:quiero|que|se|debe|deben|puede|pueden|hacer|a|volver)){0,4}\s+$',t[max(0,posicion-70):posicion]))
    for accion, patron in (
        ('caminar', r'\b(camin\w*|pase\w*|andar|ande)\b'),
        ('correr', r'\b(corr\w*|trot\w*)\b'),
        ('nadar', r'\bnad(?:ar|a|an|e|en|ando)\b'),
        ('escaleras', r'\bsub\w* (?:las |unas )?escaleras\b'),
        ('saltar', r'\bsalt\w*\b'),
        ('apuntar', r'\bapunt\w*\b'),
    ):
        for m in re.finditer(patron, t):
            if not negada(m.start()):halladas.append((m.start(),m.end(),PasoEscena(accion=accion)))
    for titulo, patron, _, _ in FAMILIAS:
        for m in re.finditer(patron, t):
            candidata = candidata_local(m[0])
            if candidata and not negada(m.start()):
                halladas.append((m.start(),m.end(),PasoEscena(accion='animacion', animacion=candidata[1]['id'])))
    halladas.sort(key=lambda h:(h[0],-(h[1]-h[0])))
    resultado=[];fin_anterior=-1
    for inicio,fin,paso in halladas:
        if inicio>=fin_anterior:resultado.append(paso);fin_anterior=fin
    if not resultado:
        # El clasificador solo puede aportar un gesto único; no sustituye tareas nativas.
        from src.capacidades_escena import candidata_aprendida
        aprendida = candidata_aprendida(texto)
        if aprendida:
            resultado.append(PasoEscena(accion='animacion', animacion=aprendida[1]['id']))
    return resultado


def validar_pasos(pasos, cantidad, duracion):
    from src.capacidades_escena import opciones
    ids = {o['id'] for o in opciones()}
    if not 1 <= len(pasos) <= 8:
        raise ValueError('Usa entre una y ocho acciones por escena.')
    if duracion < sum(p.duracion or (2 if p.accion == 'saltar' else 1) for p in pasos):
        raise ValueError('La duración no alcanza para todas las acciones; aumenta los segundos.')
    for p in pasos:
        if len(p.actores) != len(set(p.actores)) or any(i < 1 or i > cantidad for i in p.actores):
            raise ValueError('Una acción apunta a un personaje que no existe en el reparto.')
        if p.accion == 'animacion' and p.animacion not in ids:
            raise ValueError('El clip de una acción no pertenece al catálogo.')
        if p.accion == 'apuntar' and (p.objetivo_actor is None or p.objetivo_actor > cantidad or p.objetivo_actor in p.actores):
            raise ValueError('Para apuntar debe haber otro personaje como objetivo.')
    return pasos


def duraciones_pasos(pasos, total):
    validar_pasos(pasos, max(max(p.actores + ([p.objetivo_actor] if p.objetivo_actor else [])) for p in pasos), total)
    tiempos = [p.duracion or (2 if p.accion == 'saltar' else 1) for p in pasos]
    libres = [i for i, p in enumerate(pasos) if p.duracion is None and p.accion != 'saltar']
    if not libres: libres = [len(pasos)-1]
    sobrante = total - sum(tiempos)
    for j, i in enumerate(libres):
        tiempos[i] += sobrante // len(libres) + int(j < sobrante % len(libres))
    return tiempos


def estatica(plan):
    accion = plan.get('accion') if isinstance(plan, dict) else plan.accion
    pasos = plan.get('pasos', []) if isinstance(plan, dict) else plan.pasos
    return (accion=='animacion_sobre_vehiculo' and not usa_recorrido_vehicular(plan)) or accion in ('animacion', 'apuntar', 'saltar') or (accion == 'secuencia' and not any(
        (p.get('accion') if isinstance(p, dict) else p.accion) in ('caminar', 'correr', 'nadar', 'escaleras') for p in pasos))
