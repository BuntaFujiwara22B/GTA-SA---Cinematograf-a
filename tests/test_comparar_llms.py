import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import comparar_llms as benchmark
from src.mvp_plan import plan_local


class ComparacionLLMsTests(unittest.TestCase):
    def test_json_invalido_no_cuenta_como_correcto(self):
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = benchmark.evaluar(benchmark.corpus()[0], 'no es JSON', Path(carpeta))
        self.assertFalse(resultado['correcto'])
        self.assertFalse(resultado['json_valido'])
        self.assertFalse(resultado['mms_generado'])

    def test_exportacion_y_contrato_de_caminata(self):
        caso = benchmark.corpus()[3]
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = benchmark.evaluar(caso, plan_local(caso['texto']).model_dump_json(), Path(carpeta))
            self.assertTrue(resultado['correcto'], resultado.get('error_evaluacion'))
            archivo = Path(carpeta) / (caso['id'] + '.mms')
            self.assertTrue(archivo.exists())
            self.assertEqual(hashlib.sha256(archivo.read_bytes()).hexdigest(), resultado['sha256_mms'])
            self.assertNotIn(b'\r\r\n', archivo.read_bytes())

    def test_informe_parcial_no_publica_porcentaje_definitivo(self):
        with tempfile.TemporaryDirectory() as carpeta, patch.object(benchmark, 'BASE', Path(carpeta)):
            benchmark.guardar(Path(carpeta)/'resultados/gemini/escena_0001.json', dict(
                id='escena_0001', firma_experimento='prueba', respuesta_api=True, correcto=True, mms_generado=True))
            benchmark.guardar(Path(carpeta)/'resultados/gemini/escena_0002.json', dict(
                firma_experimento='prueba', respuesta_api=False))
            informe = benchmark.resumir([None]*100, 'prueba')
        fila = informe['modelos'][0]
        self.assertIsNone(fila['porcentaje'])
        self.assertEqual(fila['respuestas'], 1)
        self.assertEqual(fila['errores_api'], 1)
        self.assertEqual(fila['porcentaje_parcial'], 100)

    def test_grafica_solo_compara_los_mismos_casos(self):
        casos = [dict(id='escena_0001'), dict(id='escena_0002')]
        with tempfile.TemporaryDirectory() as carpeta, patch.object(benchmark, 'BASE', Path(carpeta)):
            for alias in benchmark.MODELOS:
                benchmark.guardar(Path(carpeta)/f'resultados/{alias}/escena_0001.json', dict(
                    id='escena_0001', firma_experimento='prueba', respuesta_api=True, correcto=True))
            benchmark.guardar(Path(carpeta)/'resultados/gemini/escena_0002.json', dict(
                id='escena_0002', firma_experimento='prueba', respuesta_api=True, correcto=False))
            informe = benchmark.resumir(casos, 'prueba')
        self.assertEqual(informe['casos_comunes'], ['escena_0001'])
        self.assertTrue(informe['preliminar'])
        self.assertTrue(all(f['porcentaje_comparable'] == 100 for f in informe['modelos']))

    def test_cliente_rechaza_modelos_de_pago(self):
        from src.acceso_benchmark import generar
        with self.assertRaises(ValueError):
            generar('openrouter', 'modelo/de-pago', 'sistema', 'petición')

    def test_respuesta_en_bloque_json(self):
        caso = benchmark.corpus()[3]
        contenido = '```json\n' + plan_local(caso['texto']).model_dump_json() + '\n```'
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = benchmark.evaluar(caso, contenido, Path(carpeta))
        self.assertTrue(resultado['correcto'], resultado.get('error_evaluacion'))


if __name__ == '__main__':
    unittest.main()
