"""Correcciones locales revisables; ninguna etiqueta se incorpora automáticamente.

La aprobación expresa una revisión del usuario dentro de la aplicación. No acredita
anotación científica independiente ni validación visual de una escena en GTA.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from uuid import uuid4

from src.modelo_intenciones import caracteristicas, normalizar
from src.paths import DATA_ROOT

CARPETA = DATA_ROOT / 'datos_entrenamiento'
ARCHIVO = CARPETA / 'correcciones.sqlite3'
_CARPETA_INICIAL = CARPETA

ETIQUETAS = {
    'bailar': 'Bailar',
    'saludar': 'Saludar con la mano',
    'aplaudir': 'Aplaudir',
    'rendirse': 'Levantar las manos / rendirse',
    'mirar_lados': 'Mirar a los lados',
    'rascarse': 'Rascarse',
    'tumbarse': 'Tumbarse',
    'vomitar': 'Gesto de vomitar',
    'sorpresa': 'Mostrar sorpresa',
    'conversar': 'Conversar',
    'estirarse': 'Estirarse',
    'negar_cabeza': 'Negar con la cabeza',
    'cansancio': 'Mostrar cansancio',
    'miedo': 'Mostrar miedo',
    'celebrar': 'Celebrar',
    'enfado': 'Mostrar enfado',
    'curiosidad': 'Mostrar curiosidad',
    'fumar': 'Gesto de fumar',
    'reir': 'Reír',
    'beber': 'Gesto de beber',
    'comer': 'Gesto de comer',
    'telefono': 'Hablar por teléfono',
    'desconocido': 'Otra acción / fuera de estos gestos',
}
ESTADOS = ('pendiente', 'aprobada', 'rechazada')


def _ruta():
    """Permite seleccionar otro archivo o carpeta en pruebas y herramientas locales."""
    archivo = Path(ARCHIVO)
    return Path(CARPETA) / archivo.name if archivo.parent == _CARPETA_INICIAL else archivo


def _ahora():
    return datetime.now(timezone.utc).isoformat()


def _texto_normalizado(texto):
    return ' '.join(normalizar(texto).split())


def _preparar_texto(texto):
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError('Escribe una petición antes de guardar la corrección.')
    texto = texto.strip()
    if len(texto) > 500:
        raise ValueError('La petición puede tener como máximo 500 caracteres.')
    if '\x00' in texto:
        raise ValueError('La petición contiene un carácter no admitido.')
    return texto


def _prediccion_publica(prediccion):
    """Conserva solo evidencia del clasificador; descarta claves y campos arbitrarios."""
    if not isinstance(prediccion, dict):
        return {}
    salida = {}
    if isinstance(prediccion.get('aceptada'), bool):
        salida['aceptada'] = prediccion['aceptada']
    intencion = prediccion.get('intencion')
    if isinstance(intencion, str) and intencion in ETIQUETAS:
        salida['intencion'] = intencion
    for clave in ('puntuacion', 'margen', 'cobertura_vocabulario', 'umbral'):
        valor = prediccion.get(clave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if 0 <= valor <= 1 and math.isfinite(valor):
                salida[clave] = float(valor)
    for clave in ('modelo', 'motivo'):
        valor = prediccion.get(clave)
        if isinstance(valor, str):
            salida[clave] = valor[:160]
    huella = prediccion.get('sha256_pesos')
    if isinstance(huella, str) and re.fullmatch(r'[0-9a-fA-F]{64}', huella):
        salida['sha256_pesos'] = huella.lower()
    return salida


def _conectar(escritura=False):
    ruta = _ruta()
    if escritura:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        conexion = sqlite3.connect(str(ruta), timeout=10)
    else:
        # Las lecturas no crean una base de datos ni escriben revisiones implícitas.
        uri = 'file:' + quote(ruta.resolve().as_posix(), safe='/:') + '?mode=ro'
        conexion = sqlite3.connect(uri, uri=True, timeout=10)
    conexion.row_factory = sqlite3.Row
    return conexion


def _crear_tabla(conexion):
    conexion.execute('''CREATE TABLE IF NOT EXISTS correcciones (
        id TEXT PRIMARY KEY,
        texto TEXT NOT NULL,
        texto_normalizado TEXT NOT NULL,
        intencion TEXT NOT NULL,
        estado TEXT NOT NULL CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
        prediccion_json TEXT NOT NULL,
        creado_utc TEXT NOT NULL,
        actualizado_utc TEXT NOT NULL,
        revisado_utc TEXT,
        UNIQUE(texto_normalizado, intencion)
    )''')


def _registro(fila):
    resultado = dict(fila)
    resultado['prediccion'] = json.loads(resultado.pop('prediccion_json'))
    resultado['origen'] = 'correccion_usuario'
    return resultado


def registrar(texto, intencion, prediccion=None):
    """Guarda una propuesta pendiente; repetirla conserva la revisión existente."""
    texto = _preparar_texto(texto)
    if not isinstance(intencion, str) or intencion not in ETIQUETAS:
        raise ValueError('Selecciona una intención válida para la corrección.')
    texto_normalizado = _texto_normalizado(texto)
    evidencia = json.dumps(_prediccion_publica(prediccion), ensure_ascii=False, allow_nan=False)
    ahora = _ahora()
    with closing(_conectar(escritura=True)) as conexion:
        with conexion:
            _crear_tabla(conexion)
            conexion.execute('''INSERT INTO correcciones
                (id, texto, texto_normalizado, intencion, estado, prediccion_json,
                 creado_utc, actualizado_utc, revisado_utc)
                VALUES (?, ?, ?, ?, 'pendiente', ?, ?, ?, NULL)
                ON CONFLICT(texto_normalizado, intencion) DO NOTHING''',
                (uuid4().hex, texto, texto_normalizado, intencion, evidencia, ahora, ahora))
            fila = conexion.execute('''SELECT * FROM correcciones
                WHERE texto_normalizado = ? AND intencion = ?''',
                (texto_normalizado, intencion)).fetchone()
        return _registro(fila)


def listar(estado='pendiente'):
    """Devuelve registros en orden de creación; None incluye todos los estados."""
    if estado is not None and estado not in ESTADOS:
        raise ValueError('El estado de revisión no es válido.')
    if not _ruta().exists():
        return []
    with closing(_conectar()) as conexion:
        # Dos altas pueden compartir fecha por la resolución del reloj. El
        # rowid conserva su orden de inserción; un UUID aleatorio no lo hace.
        if estado is None:
            filas = conexion.execute('SELECT * FROM correcciones ORDER BY creado_utc, rowid').fetchall()
        else:
            filas = conexion.execute('''SELECT * FROM correcciones WHERE estado = ?
                ORDER BY creado_utc, rowid''', (estado,)).fetchall()
    return [_registro(fila) for fila in filas]


def revisar(identificador, aprobar):
    """Aprueba o rechaza por acción explícita; la aprobación no inicia entrenamiento."""
    if not isinstance(aprobar, bool):
        raise ValueError('La revisión debe indicar aprobar o rechazar.')
    if not isinstance(identificador, str) or not identificador or not _ruta().exists():
        raise ValueError('No existe esa corrección.')
    estado = 'aprobada' if aprobar else 'rechazada'
    with closing(_conectar(escritura=True)) as conexion:
        # Bloquea escrituras competidoras antes de comprobar etiquetas contradictorias.
        conexion.execute('BEGIN IMMEDIATE')
        with conexion:
            fila = conexion.execute('SELECT * FROM correcciones WHERE id = ?',
                                     (identificador,)).fetchone()
            if fila is None:
                raise ValueError('No existe esa corrección.')
            if aprobar:
                conflicto = conexion.execute('''SELECT id FROM correcciones
                    WHERE texto_normalizado = ? AND estado = 'aprobada'
                      AND intencion != ? AND id != ? LIMIT 1''',
                    (fila['texto_normalizado'], fila['intencion'], identificador)).fetchone()
                if conflicto:
                    raise ValueError('Ese texto ya tiene otra etiqueta aprobada; recházala antes de cambiarla.')
            if fila['estado'] != estado:
                ahora = _ahora()
                conexion.execute('''UPDATE correcciones
                    SET estado = ?, actualizado_utc = ?, revisado_utc = ? WHERE id = ?''',
                    (estado, ahora, ahora, identificador))
                fila = conexion.execute('SELECT * FROM correcciones WHERE id = ?',
                                         (identificador,)).fetchone()
        return _registro(fila)


def _firma_rasgos(texto):
    return tuple(sorted(caracteristicas(texto).items()))


def obtener_aprobadas(corpus_base):
    """Exporta solo correcciones revisadas y ajenas a ejemplos ya conocidos/reservados.

    No modifica el corpus ni la base de datos. Los registros excluidos permanecen
    disponibles para revisión y aparecen con su motivo en el resumen.
    """
    aprobadas = listar('aprobada')
    base = corpus_base.get('ejemplos', [])
    clases = set(corpus_base.get('clases', ETIQUETAS))
    entrenamiento_textos, entrenamiento_rasgos = {}, {}
    reservados_textos, reservados_rasgos, grupos_reservados = set(), set(), set()
    identificadores = {e['id'] for e in base}
    for e in base:
        texto = _texto_normalizado(e['texto'])
        rasgos = _firma_rasgos(e['texto'])
        if e['particion'] in ('validacion', 'prueba'):
            reservados_textos.add(texto)
            if rasgos:
                reservados_rasgos.add(rasgos)
            grupos_reservados.add(e['grupo'])
        else:
            entrenamiento_textos.setdefault(texto, set()).add(e['intencion'])
            if rasgos:
                entrenamiento_rasgos.setdefault(rasgos, set()).add(e['intencion'])
    incorporadas, omitidas = [], []
    nuevos_textos, nuevos_rasgos = {}, {}
    for registro in aprobadas:
        texto = registro['texto_normalizado']
        intencion = registro['intencion']
        rasgos = _firma_rasgos(registro['texto'])
        identificador = 'correccion_' + registro['id']
        motivo = None
        if intencion not in clases:
            motivo = 'etiqueta_fuera_del_corpus'
        elif identificador in grupos_reservados:
            motivo = 'grupo_reservado'
        elif texto in reservados_textos:
            motivo = 'texto_reservado_validacion_o_prueba'
        elif rasgos and rasgos in reservados_rasgos:
            motivo = 'caracteristicas_reservadas_validacion_o_prueba'
        elif not rasgos:
            motivo = 'sin_caracteristicas_informativas'
        elif texto in entrenamiento_textos or rasgos in entrenamiento_rasgos:
            etiquetas = entrenamiento_textos.get(texto, set()) | entrenamiento_rasgos.get(rasgos, set())
            motivo = 'duplicado_entrenamiento' if etiquetas == {intencion} else 'conflicto_etiqueta_entrenamiento'
        elif identificador in identificadores:
            motivo = 'identificador_existente'
        elif texto in nuevos_textos or rasgos in nuevos_rasgos:
            etiqueta = nuevos_textos.get(texto, nuevos_rasgos.get(rasgos))
            motivo = 'duplicado_correcciones' if etiqueta == intencion else 'conflicto_etiqueta_correcciones'
        if motivo:
            omitidas.append(dict(id=registro['id'], motivo=motivo))
            continue
        incorporadas.append(dict(id=identificador, texto=registro['texto'], intencion=intencion,
            particion='entrenamiento', grupo=identificador, origen='correccion_usuario_revisada',
            estado='aprobada'))
        nuevos_textos[texto] = intencion
        nuevos_rasgos[rasgos] = intencion
    return incorporadas, dict(n_aprobadas=len(aprobadas), n_incorporadas=len(incorporadas), omitidas=omitidas)
