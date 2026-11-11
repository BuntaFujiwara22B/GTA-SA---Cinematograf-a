"""Preferencias explícitas de cámara; el montaje automático es la opción inicial.

Interpreta instrucciones del usuario, no la acción del personaje. Estas reglas no
entrenan un modelo ni eligen recursos del juego. El compilador valida el preset.
"""
import re
import unicodedata


NOMBRES_CAMARA = {
    'automatica': 'Montaje automático · cada 5 segundos',
    'fija': 'Cámara fija',
    'seguimiento_trasero': 'Seguimiento desde atrás',
    'costado': 'Seguimiento de costado',
    'giro_frontal': 'Giro frontal',
    'vehiculo_pov': 'Desde el asiento del vehículo',
}

_CAMARA = r'(?:camaras?|planos?|encuadres?|tomas?)'
_CAMBIO = r'(?:cambi\w*|altern\w*|rot\w*|intercal\w*|vari\w*)'


def _normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',str(texto or '').lower())
        if not unicodedata.combining(c)).split())


def nombre_camara(preset):
    return NOMBRES_CAMARA.get(preset, NOMBRES_CAMARA['automatica'])


def preferencia_camara(texto):
    """Devuelve un preset del exportador o ``automatica``.

    Un encuadre nombrado explícitamente se conserva. Si se piden varias cámaras
    se usa montaje; si además se pide después no cambiar, prevalece esa última
    instrucción. «Cámara fija detrás» significa seguimiento relativo al personaje.
    Las preferencias espaciales sin mención a cámara/plano no cambian la política.
    """
    t = _normalizar(texto)
    # «No quiero una cámara fija» no es una petición de mantener cámara fija.
    # Conservar los offsets permite resolver instrucciones sucesivas por orden.
    t = re.sub(r'\b(?:no quiero|no uses|no utilices|evita|sin)\s+'
        r'(?:(?:una?|la|el)\s+)?'+_CAMARA+r'\b[^,.;!?]*',
        lambda m:' '*len(m.group()),t)

    politicas=[]
    patrones_unica=(
        r'\b(?:no\s+(?:quiero\s+que\s+)?'+_CAMBIO+r'|sin\s+(?:cambios?|cortes?|alternancia))'
        r'\b[^.;!?]{0,55}\b'+_CAMARA+r'\b',
        r'\b(?:que\s+)?no\s+haya\s+(?:cambios?|cortes?)\s+de\s+'+_CAMARA+r'\b',
        r'\b'+_CAMARA+r'\b[^.;!?]{0,45}\bno\s+'
        r'(?:(?:debe(?:ria)?|tiene que|puede|va a)\s+)?'+_CAMBIO+r'\b',
        r'\b(?:un\s+(?:solo|unico)\s+plano|una\s+(?:sola|unica)\s+(?:camara|toma)|plano\s+secuencia)\b',
        r'\b(?:manten\w*|conserv\w*)\b[^.;!?]{0,35}\b(?:(?:la|el)\s+)?(?:mism[ao]\s+)?'+_CAMARA+r'\b',
    )
    spans_unica=[]
    for patron in patrones_unica:
        for m in re.finditer(patron,t):
            spans_unica.append(m.span())
            politicas.append((m.start(),False))
    # Quitar las negaciones al buscar cambios: «no cambies de cámara» conserva.
    cambios=t
    for a,b in sorted(spans_unica,reverse=True):cambios=cambios[:a]+' '*(b-a)+cambios[b:]
    patrones_auto=(
        r'\b'+_CAMBIO+r'\b[^.;!?]{0,70}\b'+_CAMARA+r'\b',
        r'\b'+_CAMARA+r'\b[^.;!?]{0,55}\b'+_CAMBIO+r'\b',
        r'\b(?:varias?|diferentes|distintas|multiples)\s+'+_CAMARA+r'\b',
        r'\bmontaje\s+automatico\b',
        r'\b'+_CAMARA+r'\b[^.;!?]{0,65}\bcada\s+(?:5|cinco)\s*(?:segundos?|s\b)',
    )
    for patron in patrones_auto:
        politicas.extend((m.start(),True) for m in re.finditer(patron,cambios))

    if politicas and max(politicas,key=lambda p:p[0])[1]:
        return 'automatica'

    # Solo los contextos que nombran el encuadre pueden elegir un preset.
    contextos=[]
    for m in re.finditer(r'\b'+_CAMARA+r'\b|\bpov\b',t):
        principio=max(t.rfind('.',0,m.start()),t.rfind(';',0,m.start()),t.rfind('!',0,m.start()))+1
        fin=len(t)
        for separador in '.;!':
            encontrado=t.find(separador,m.end())
            if encontrado!=-1:fin=min(fin,encontrado)
        contextos.append(t[max(principio,m.start()):min(fin,m.end()+115)])
    for contexto in reversed(contextos):
        if re.search(r'\b(?:pov|primera persona|desde el asiento|interior del (?:coche|auto|vehiculo))\b',contexto):
            return 'vehiculo_pov'
        if re.search(r'\b(?:giro frontal|gira\w* (?:por )?delante|orbit\w*)\b',contexto):
            return 'giro_frontal'
        if re.search(r'\b(?:costado|lateral|de lado)\b',contexto):
            return 'costado'
        if re.search(r'\b(?:detras|traser[ao]|desde atras|seguimiento|sigue|siga|seguir|siguiendo)\b',contexto):
            return 'seguimiento_trasero'
        if re.search(r'\b'+_CAMARA+r'\s+(?:(?:que (?:este|permanezca)|completamente|totalmente|en posicion)\s+)?'
            r'(?:fij[ao]|estatic[ao]|inmovil|sin mover)\b',contexto):
            return 'fija'
    return 'fija' if politicas else 'automatica'
