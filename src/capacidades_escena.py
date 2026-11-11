"""Acciones con respaldo explícito en el catálogo; no equivalen a mecánicas de juego."""
import re
from functools import lru_cache
from src.catalogo_animaciones import cargar_opciones_animaciones

FAMILIAS=(
    ('bailar',r'\bbail\w*\b','DANCE',r'^dance_loop$|^DAN_Loop_A$'),
    ('saludar',r'\bsalud\w*\b',None,r'^wave_loop$'),
    ('aplaudir',r'\b(aplaud\w*|aplaus\w*)\b',None,r'^bd_clap$|clap'),
    ('rendirse',r'\b(rend\w*|rind\w*|manos arriba|levant\w* (?:las )?manos)\b',None,r'^handsup$'),
    ('mirar a los lados',r'\bmir\w* (?:a )?(?:los )?lados\b',None,r'^roadcross$'),
    ('rascarse',r'\b(rasc\w*|rasqu\w*)\b',None,r'^XPRESSscratch$'),
    ('tumbarse',r'\b(tumb\w*|acost\w*)\b','LAY',r'^Lay_Bac_Loop$'),
    ('vomitar',r'\bvomit\w*\b',None,r'vomit'),
    ('mostrar sorpresa',r'\b(sorpr\w*|sorpresa)\b','MIMIC',r'^facsurp$'),
    ('hablar',r'\b(habl\w*|convers\w*)\b','CHAT',r'^IDLE_chat$'),
    ('estirarse',r'\bestir\w*\b','STAND',r'^stretch$'),
    ('negar con la cabeza',r'\b(?:nieg\w*|neg\w*) con la cabeza\b','STAND',r'^shakehead_1$'),
    ('mostrar cansancio',r'\b(?:cansad\w*|agotad\w*|muestr\w* cansancio)\b','STAND',r'^idle_tired$'),
    ('encogerse por miedo',r'\b(?:asust\w*|atemoriz\w*|tiene miedo|tienen miedo)\b','STAND',r'^panic_cower$'),
    ('celebrar',r'\bcelebr\w*\b','STAND',r'^cheers_1$'),
    ('expresión de enfado',r'\b(?:enfad\w*|enoj\w*)\b','MIMIC',r'^facanger$'),
    ('expresión de curiosidad',r'\b(?:curios\w*)\b','MIMIC',r'^facurios$'),
    ('fumar',r'\b(?:fum(?:a|an|ar|ando|e|en|o)|furm\w*)\b','STAND',r'^M_smk_drag$'),
    ('reír',r'\b(?:reir\w*|rie|rien|riendo|risa|carcajad\w*)\b','CHAT',r'^Laugh_01$'),
    ('gesto de beber',r'\b(?:beb(?:e|en|er|iendo|a|an)|tom\w* (?:una |la )?bebida)\b','STAND',r'^drnkbr_prtl$'),
    ('gesto de comer',r'\b(?:com(?:e|en|er|iendo|a|an)|mastic\w*)\b','STAND',r'^EAT_Burger$'),
    ('hablar por teléfono',r'\b(?:habl\w*|convers\w*|llam\w*)\s+(?:por|con|usando|al)\s+(?:el |un |su )?(?:telefon\w*|celular)\b','STAND',r'^phone_talk$'),
)


@lru_cache(maxsize=1)
def opciones():
    return tuple(cargar_opciones_animaciones())


INTENCIONES_ENTRENADAS = dict(zip(
    ('bailar','saludar','aplaudir','rendirse','mirar_lados','rascarse','tumbarse',
     'vomitar','sorpresa','conversar','estirarse','negar_cabeza','cansancio','miedo',
     'celebrar','enfado','curiosidad','fumar','reir','beber','comer','telefono'),
    (f[0] for f in FAMILIAS)))


def candidata_aprendida(texto):
    from src.modelo_intenciones import predecir_intencion
    prediccion = predecir_intencion(texto)
    if not prediccion['aceptada']:
        return None
    titulo = INTENCIONES_ENTRENADAS.get(prediccion['intencion'])
    familia = next((f for f in FAMILIAS if f[0] == titulo), None)
    if familia is None:
        return None
    _, _, categoria, nombre = familia
    opcion = next((o for o in opciones() if (categoria is None or o['categoria'] == categoria)
                   and re.search(nombre, o['anim'], re.I)), None)
    if opcion is None:
        return None
    return titulo, dict(opcion, aprendizaje_supervisado=prediccion)


def candidata_local(texto, usar_modelo=True):
    # Una expresión específica («habla por teléfono») tiene prioridad sobre «habla».
    familias=sorted(FAMILIAS,key=lambda f:0 if f[0]=='hablar por teléfono' else 1)
    for titulo,patron,categoria,nombre in familias:
        if re.search(patron,texto):
            o=next((o for o in opciones() if (categoria is None or o['categoria']==categoria)
                and re.search(nombre,o['anim'],re.I)),None)
            return (titulo,o) if o else None
    return candidata_aprendida(texto) if usar_modelo else None
