"""Persistencia y revisión humana explícita de datos para entrenamiento posterior."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from src import correcciones_intenciones as correcciones


def ejemplo(identificador, texto, intencion, particion):
    return dict(id=identificador, texto=texto, intencion=intencion,
                particion=particion, grupo=identificador)


class CorreccionesIntenciones(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / 'datos/correcciones.sqlite3'
        self.parche = patch.object(correcciones, 'ARCHIVO', self.ruta)
        self.parche.start()
        self.addCleanup(self.parche.stop)

    def aprobar(self, texto, intencion='bailar'):
        registro = correcciones.registrar(texto, intencion)
        return correcciones.revisar(registro['id'], True)

    def test_lecturas_sin_datos_no_crean_archivos(self):
        self.assertEqual(correcciones.listar(), [])
        self.assertEqual(correcciones.obtener_aprobadas({'clases': correcciones.ETIQUETAS,
                                                        'ejemplos': []})[0], [])
        self.assertFalse(self.ruta.exists())
        self.assertFalse(self.ruta.parent.exists())

    def test_registro_persistente_y_evidencia_sin_campos_arbitrarios(self):
        prediccion = dict(aceptada=True, intencion='bailar', puntuacion=.8, margen=.7,
            cobertura_vocabulario=.9, umbral=.6, modelo='modelo-v1', sha256_pesos='a'*64,
            motivo='clasificacion_supervisada', GEMINI_API_KEY='secreto', api_key='secreto',
            prompt='dato arbitrario', cabeceras={'Authorization': 'secreto'})
        registro = correcciones.registrar('  El actor sigue una melodía con sus pasos  ', 'bailar', prediccion)
        self.assertEqual(registro['estado'], 'pendiente')
        self.assertEqual(len(registro['id']), 32)
        self.assertTrue(registro['creado_utc'].endswith('+00:00'))
        self.assertEqual(registro['texto'], 'El actor sigue una melodía con sus pasos')
        self.assertEqual(registro['prediccion']['modelo'], 'modelo-v1')
        self.assertNotIn('api_key', registro['prediccion'])
        self.assertNotIn('secreto', json.dumps(registro))
        self.assertIsNone(registro['revisado_utc'])
        self.assertEqual(correcciones.listar()[0], registro)
        with closing(sqlite3.connect(self.ruta)) as conexion:
            self.assertEqual(conexion.execute('SELECT COUNT(*) FROM correcciones').fetchone()[0], 1)

    def test_revision_es_explicita_idempotente_y_no_entrena(self):
        registro = correcciones.registrar('se mueve siguiendo una canción', 'bailar')
        self.assertEqual(correcciones.listar('aprobada'), [])
        revisada = correcciones.revisar(registro['id'], True)
        self.assertEqual(revisada['estado'], 'aprobada')
        self.assertIsNotNone(revisada['revisado_utc'])
        self.assertEqual(correcciones.revisar(registro['id'], True), revisada)
        self.assertEqual(correcciones.listar(), [])
        self.assertEqual(correcciones.listar('aprobada'), [revisada])
        rechazada = correcciones.revisar(registro['id'], False)
        self.assertEqual(rechazada['estado'], 'rechazada')
        self.assertEqual(len(correcciones.listar(None)), 1)
        self.assertFalse((self.ruta.parent / 'metadata.json').exists())

    def test_evidencia_descarta_valores_invalidos_sin_interpretarlos(self):
        evidencia = dict(intencion=['bailar'], puntuacion=float('nan'), margen=float('inf'),
                         cobertura_vocabulario=10**500, umbral=True,
                         modelo={'api_key': 'secreto'}, sha256_pesos='no-es-huella')
        registro = correcciones.registrar('un movimiento novedoso', 'desconocido', evidencia)
        self.assertEqual(registro['prediccion'], {})

    def test_duplicados_normalizados_conservan_revision(self):
        aprobada = self.aprobar('El actor sigue la MÚSICA')
        duplicada = correcciones.registrar('el actor  sigue la musica', 'bailar', {'modelo': 'otro'})
        self.assertEqual(duplicada, aprobada)
        self.assertEqual(len(correcciones.listar(None)), 1)
        rechazada = correcciones.revisar(aprobada['id'], False)
        self.assertEqual(correcciones.registrar('el actor sigue la música', 'bailar'), rechazada)

    def test_aprobacion_contradictoria_requiere_rechazar_etiqueta_anterior(self):
        anterior = self.aprobar('el actor mueve los brazos')
        otra = correcciones.registrar('el actor mueve los brazos', 'saludar')
        with self.assertRaisesRegex(ValueError, 'otra etiqueta aprobada'):
            correcciones.revisar(otra['id'], True)
        self.assertEqual(correcciones.listar()[0]['estado'], 'pendiente')
        correcciones.revisar(anterior['id'], False)
        self.assertEqual(correcciones.revisar(otra['id'], True)['estado'], 'aprobada')

    def test_texto_sql_se_guarda_como_dato(self):
        texto = "un actor dice '); DROP TABLE correcciones; --"
        primero = correcciones.registrar(texto, 'desconocido')
        segundo = correcciones.registrar('algo diferente', 'desconocido')
        self.assertEqual(primero['texto'], texto)
        self.assertEqual(len(correcciones.listar()), 2)
        self.assertEqual(correcciones.revisar(segundo['id'], True)['estado'], 'aprobada')

    def test_validacion_no_crea_registros_invalidos(self):
        for texto, etiqueta in [('', 'bailar'), ('  ', 'bailar'), (None, 'bailar'),
                                ('x'*501, 'bailar'), ('texto', 'inventada'),
                                ('texto', None), ('con\x00nulo', 'desconocido')]:
            with self.subTest(texto=repr(texto), etiqueta=etiqueta), self.assertRaises(ValueError):
                correcciones.registrar(texto, etiqueta)
        self.assertEqual(correcciones.listar(), [])
        with self.assertRaises(ValueError):
            correcciones.listar('inventado')
        with self.assertRaises(ValueError):
            correcciones.revisar('inexistente', True)
        with self.assertRaises(ValueError):
            correcciones.revisar('inexistente', 'sí')

    def test_lectura_exporta_solo_aprobadas_sin_modificar_corpus_o_sqlite(self):
        valida = self.aprobar('el protagonista se despide agitando su palma', 'saludar')
        negativa = self.aprobar('construye una casa flotante', 'desconocido')
        pendiente = correcciones.registrar('ritmo nuevo', 'bailar')
        rechazada = correcciones.registrar('otro ritmo', 'bailar')
        correcciones.revisar(rechazada['id'], False)
        base = {'clases': correcciones.ETIQUETAS, 'ejemplos': []}
        anterior = copy.deepcopy(base)
        bytes_antes = self.ruta.read_bytes()
        registros, resumen = correcciones.obtener_aprobadas(base)
        self.assertEqual(base, anterior)
        self.assertEqual(self.ruta.read_bytes(), bytes_antes)
        self.assertEqual(resumen, dict(n_aprobadas=2, n_incorporadas=2, omitidas=[]))
        self.assertEqual({r['id'] for r in registros}, {'correccion_'+valida['id'], 'correccion_'+negativa['id']})
        for r in registros:
            self.assertEqual(r['particion'], 'entrenamiento')
            self.assertEqual(r['grupo'], r['id'])
            self.assertEqual(r['estado'], 'aprobada')
            self.assertEqual(r['origen'], 'correccion_usuario_revisada')
        self.assertEqual(correcciones.listar()[0]['id'], pendiente['id'])

    def test_excluye_textos_y_caracteristicas_de_todas_las_particiones(self):
        base = dict(clases=correcciones.ETIQUETAS, ejemplos=[
            ejemplo('train_1', 'baila siguiendo el ritmo', 'bailar', 'entrenamiento'),
            ejemplo('train_2', 'junta sus palmas', 'aplaudir', 'entrenamiento'),
            ejemplo('val_1', 'agita la mano', 'saludar', 'validacion'),
            ejemplo('test_1', 'se lleva el teléfono a la oreja', 'telefono', 'prueba'),
        ])
        casos = [
            ('BAILA siguiendo el ritmo', 'bailar', 'duplicado_entrenamiento'),
            ('junta sus palmas', 'saludar', 'conflicto_etiqueta_entrenamiento'),
            ('Agita la mano', 'saludar', 'texto_reservado_validacion_o_prueba'),
            ('una persona agita la mano', 'saludar', 'caracteristicas_reservadas_validacion_o_prueba'),
            ('se lleva el telefono a la oreja', 'telefono', 'texto_reservado_validacion_o_prueba'),
            ('el actor se lleva el teléfono a la oreja', 'telefono', 'caracteristicas_reservadas_validacion_o_prueba'),
        ]
        esperados = {}
        for texto, etiqueta, motivo in casos:
            registro = self.aprobar(texto, etiqueta)
            esperados[registro['id']] = motivo
        registros, resumen = correcciones.obtener_aprobadas(base)
        self.assertEqual(registros, [])
        self.assertEqual({r['id']: r['motivo'] for r in resumen['omitidas']}, esperados)
        self.assertEqual(resumen['n_aprobadas'], 6)

    def test_excluye_correcciones_equivalentes_y_conflictos_de_rasgos(self):
        # Un reloj de resolución limitada puede devolver la misma fecha para
        # varias inserciones. Los UUID inversos impiden un desempate accidental
        # por el identificador en lugar del orden en que se guardaron.
        with patch.object(correcciones, '_ahora', return_value='2026-11-11T12:00:00+00:00'),\
                patch.object(correcciones, 'uuid4', side_effect=[UUID(int=n) for n in (4, 3, 2, 1)]):
            primero = self.aprobar('balancea los hombros al compás', 'bailar')
            segundo = self.aprobar('una persona balancea los hombros al compás', 'bailar')
            tercero = self.aprobar('el actor balancea los hombros al compás', 'saludar')
            sin_rasgos = self.aprobar('12345 !!!', 'desconocido')
        self.assertEqual([r['id'] for r in correcciones.listar(None)],
            [r['id'] for r in (primero, segundo, tercero, sin_rasgos)])
        registros, resumen = correcciones.obtener_aprobadas({'clases': correcciones.ETIQUETAS, 'ejemplos': []})
        self.assertEqual([r['id'] for r in registros], ['correccion_'+primero['id']])
        omitidas = {r['id']: r['motivo'] for r in resumen['omitidas']}
        self.assertEqual(omitidas[segundo['id']], 'duplicado_correcciones')
        self.assertEqual(omitidas[tercero['id']], 'conflicto_etiqueta_correcciones')
        self.assertEqual(omitidas[sin_rasgos['id']], 'sin_caracteristicas_informativas')

    def test_carpeta_de_datos_tambien_es_configurable(self):
        original = correcciones._CARPETA_INICIAL / 'correcciones.sqlite3'
        carpeta = Path(self.temporal.name) / 'otra_carpeta'
        with patch.object(correcciones, 'ARCHIVO', original), patch.object(correcciones, 'CARPETA', carpeta):
            correcciones.registrar('un gesto de prueba', 'desconocido')
        self.assertTrue((carpeta/'correcciones.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
