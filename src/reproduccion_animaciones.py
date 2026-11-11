"""Decide entre repetir, terminar o conservar la última pose."""
import re
import unicodedata

MODOS={'auto','una_vez','mantener','bucle'}


def decidir_reproduccion(identificador,texto='',propuesta='auto'):
    if propuesta not in MODOS:raise ValueError('Modo de reproducción no válido.')
    t=''.join(c for c in unicodedata.normalize('NFD',texto.lower()) if not unicodedata.combining(c))
    nombre=(identificador or '').lower()
    una_vez=bool(re.search(r'\b(una (?:sola )?vez|sin (?:bucle|repetir)|no (?:se )?repit\w*|no repetir)\b',t))
    if re.search(r'\b(volv\w* a (?:la )?(?:normalidad|posicion inicial)|baj\w* (?:las )?manos)\b',t):
        return 'una_vez','La petición indica terminar el gesto y soltar la pose.'
    if not una_vez and re.search(r'\b(en bucle|repetid\w*|continuamente|sin parar)\b',t):
        return 'bucle','La petición pide repetir la acción.'
    if 'handsup' in nombre:
        return 'mantener','Levantar las manos una vez y conservarlas arriba.'
    if re.search(r'\b(mantener|mantengan|conservar)\b.*\b(pose|posicion)\b',t):
        return 'mantener','La petición pide conservar la pose final.'
    if una_vez:return 'una_vez','La petición pide ejecutar el gesto una sola vez.'
    if propuesta!='auto':return propuesta,'Comportamiento propuesto por el análisis de la escena.'
    if nombre.startswith('dance:') or 'idle_chat' in nombre:
        return 'bucle','Acción sostenida de baile, aplausos o conversación.'
    if ':smoking:m_smk_drag' in nombre or ':ped:phone_talk' in nombre:
        return 'bucle','Acción sostenida de fumar o conversar por teléfono; no crea objetos ni efectos por sí sola.'
    if 'lay_bac_loop' in nombre or 'facsurp' in nombre:
        return 'mantener','Conservar la postura o expresión al finalizar.'
    return 'una_vez','Gesto puntual; no repetirlo automáticamente sin una indicación.'
