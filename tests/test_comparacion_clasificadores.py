"""Comprueba la separación de datos y el carácter no destructivo del benchmark."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import comparar_clasificadores as comparacion


def ejemplo(identificador, texto, clase, grupo=None):
    return dict(id=identificador, texto=texto, intencion=clase, grupo=grupo or identificador)


class ComparacionClasificadores(unittest.TestCase):
    def test_seis_algoritmos_distintos_con_parametros_prefijados(self):
        modelos = comparacion.clasificadores()
        self.assertEqual(len(modelos), 6)
        self.assertEqual(len({type(m) for m in modelos.values()}), 6)
        self.assertEqual(modelos['Regresión logística'].C, 12)
        self.assertEqual(modelos['SVM lineal'].C, 1)
        self.assertEqual(modelos['SGD logístico'].random_state, 42)

    def test_vocabulario_y_idf_no_aprenden_de_validacion(self):
        train = [ejemplo('a', 'ritmo musical', 'bailar'), ejemplo('b', 'palmadas', 'aplaudir')]
        vectorizador, tfidf, matriz, etiquetas = comparacion.ajustar_representacion(train)
        idf = tfidf.idf_.copy()
        vocabulario = dict(vectorizador.vocabulary_)
        reserva = comparacion.transformar(vectorizador, tfidf, ['xilofonoreservado'])
        self.assertNotIn('w:xilofonoreservado', vectorizador.vocabulary_)
        self.assertEqual(vectorizador.vocabulary_, vocabulario)
        self.assertTrue((tfidf.idf_ == idf).all())
        self.assertEqual(matriz.shape[0], 6)
        self.assertEqual(reserva.shape[0], 1)
        self.assertEqual(len(etiquetas), 6)

    def test_curva_separa_grupos_antes_del_aumento_y_conserva_clases(self):
        filas = [ejemplo(f'{c}{i}', f'frase {c} {i}', c, f'{c}{i//2}')
                 for c in ('bailar', 'aplaudir') for i in range(8)]
        seleccionadas = comparacion.seleccionar_grupos(filas, .5, 42)
        grupos = {e['grupo'] for e in seleccionadas}
        self.assertEqual({e['intencion'] for e in seleccionadas}, {'bailar', 'aplaudir'})
        self.assertEqual(len(seleccionadas), 8)
        self.assertTrue(all(e in seleccionadas for e in filas if e['grupo'] in grupos))
        self.assertEqual(seleccionadas, comparacion.seleccionar_grupos(filas, .5, 42))

    def test_escritura_de_informe_no_sustituye_modelo_activo(self):
        with tempfile.TemporaryDirectory() as temporal, patch.object(comparacion, 'ROOT', Path(temporal)):
            carpeta = Path(temporal) / 'models/intenciones'
            carpeta.mkdir(parents=True)
            (carpeta / 'metadata.json').write_text('{"activo":true}')
            (carpeta / 'pesos.npz').write_bytes(b'pesos del modelo activo')
            antes = comparacion.huellas_modelo()
            fila = dict(nombre='Ejemplo', validacion=dict(exactitud=.8, f1_macro=.7),
                        prueba=dict(exactitud=.6, f1_macro=.5), segundos_ajuste=.01,
                        latencia=dict(mediana_ms=.2, p95_ms=.3))
            destino = Path(temporal) / 'evaluaciones'
            comparacion.guardar_informe(dict(clasificadores=[fila]), destino)
            self.assertEqual(antes, comparacion.huellas_modelo())
            self.assertEqual(json.loads((destino / 'comparacion_clasificadores.json').read_text(
                encoding='utf-8'))['clasificadores'][0]['prueba']['f1_macro'], .5)
            self.assertIn('prueba_f1_macro', (destino / 'comparacion_clasificadores.csv').read_text(
                encoding='utf-8-sig'))


if __name__ == '__main__':
    unittest.main()
