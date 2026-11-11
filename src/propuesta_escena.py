"""Completa una propuesta editable, conservando las elecciones válidas de la IA."""
from src.paths import ASSETS
from src.catalogos_entidades import disponibles
from src.ubicaciones_escena import elegir_ubicacion,elegir_ruta_vehiculo,ubicaciones
from src.escenas_semanticas import es_vehicular,usa_recorrido_vehicular


def completar_propuesta(plan,texto):
    p=plan.model_copy(deep=True)
    if not p.es_valido:return p
    actores=sorted(int(a.stem) for a in (ASSETS/'actors').glob('*.png') if a.stem.isdigit())
    if not actores:raise ValueError('No hay personajes disponibles para preparar la escena.')
    from src.reparto_escena import elegir_reparto
    plan_reparto=elegir_reparto(p,texto)
    p.actores_ids_sugeridos=plan_reparto
    p.actor_id_sugerido=plan_reparto[0]
    elegidos=plan_reparto
    p.actores_ids_sugeridos=elegidos[:p.cantidad_actores]
    p.actor_id_sugerido=elegidos[0]
    if p.hora_sugerida is None:p.hora_sugerida=12
    if p.clima_id_sugerido is None:
        p.clima_id_sugerido={'campo':14,'desierto':18}.get(p.entorno_sugerido,1)
    if es_vehicular(p):
        coches=disponibles('vehicles');ids={v['model_id'] for v in coches}
        if p.vehiculo_id_sugerido not in ids:
            t=texto.lower()
            candidatos=([420] if 'taxi' in t else [468,461] if 'moto' in t else [431] if 'bus' in t else
                        [596] if 'polic' in t else [426,405,400,411])
            p.vehiculo_id_sugerido=next((i for i in candidatos if i in ids),next(iter(ids),None))
        if p.vehiculo_id_sugerido is None:raise ValueError('No hay vehículos disponibles.')
    if p.accion=='animacion_sobre_vehiculo':
        from src.registro_capacidades import soportes_vehiculos
        if p.vehiculo_id_sugerido not in {v['model_id'] for v in soportes_vehiculos()}:
            raise ValueError('No hay una posición de techo preparada para ese modelo.')
    from src.escenas_semanticas import estatica, reparto_pedido
    p.roles=(reparto_pedido(texto) or p.roles)[:4]
    if not estatica(p):p.ubicacion_id_sugerida=None
    if 'puente' in texto.lower() and not estatica(p) and p.accion not in ('conducir_vehiculo','vehiculo_autonomo'):
        from src.calles_escena import elegir_calle
        p.ruta_id_sugerida=(elegir_calle(texto,p.duracion_sugerida) or {}).get('id')
    if p.accion=='secuencia':
        p.tipo_movimiento=next((s.accion for s in p.pasos if s.accion in ('caminar','correr','nadar','escaleras')),'caminar')
    if p.accion=='animacion_sobre_vehiculo':
        p.ubicacion_id_sugerida=None
        p.ruta_vehiculo_id=elegir_ruta_vehiculo(texto,p.ruta_vehiculo_id)['id']
    elif estatica(p):
        lugares=ubicaciones(p.entorno_sugerido)
        if 'puente' in texto.lower():lugares=[u for u in lugares if 'puente' in u.get('etiquetas',[])]
        elegido=next((u for u in lugares if u['id']==p.ubicacion_id_sugerida),None)
        if elegido is None:elegido=elegir_ubicacion(p.entorno_sugerido,texto)
        p.ubicacion_id_sugerida=elegido['id']
    elif usa_recorrido_vehicular(p):
        p.ruta_vehiculo_id=elegir_ruta_vehiculo(texto,p.ruta_vehiculo_id)['id']
    if not p.motivo_elecciones:
        p.motivo_elecciones=('Propuesta de '+p.fuente+': reparto disponible, ambiente y ubicación del catálogo. '
            'Puedes cambiar cualquiera de estas opciones.')
    return p
