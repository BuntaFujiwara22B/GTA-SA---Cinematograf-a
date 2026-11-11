"""Correcciones revisadas y promoción de modelos sin tocar los pesos del proyecto."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import entrenar_intenciones as entrenamiento
from src import correcciones_intenciones as correcciones


RAIZ_PROYECTO = Path(__file__).resolve().parents[1]


def huellas(carpeta):
    return {nombre: hashlib.sha256((carpeta / nombre).read_bytes()).hexdigest()
            for nombre in ('metadata.json', 'pesos.npz') if (carpeta / nombre).exists()}


class EntrenamientoVersionado(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.corpus = self.raiz / 'datos_entrenamiento/intenciones_escena.json'
        self.corpus.parent.mkdir(parents=True)
        shutil.copy2(RAIZ_PROYECTO / 'datos_entrenamiento/intenciones_escena.json', self.corpus)
        self.activa = self.raiz / 'models/intenciones'
        self.activa.mkdir(parents=True)
        for nombre in ('metadata.json', 'pesos.npz'):
            shutil.copy2(RAIZ_PROYECTO / 'models/intenciones' / nombre, self.activa / nombre)
        self.huellas_iniciales = huellas(self.activa)
        self.pila = ExitStack()
        self.addCleanup(self.pila.close)
        self.pila.enter_context(patch.object(entrenamiento, 'ROOT', self.raiz))
        self.pila.enter_context(patch.object(entrenamiento, 'CORPUS', self.corpus))
        self.pila.enter_context(patch.object(entrenamiento, 'DESTINO', self.activa))
        self.pila.enter_context(patch.object(entrenamiento, 'INFORME', self.raiz / 'evaluaciones/activo.json'))
        self.pila.enter_context(patch.object(correcciones, 'ARCHIVO', self.raiz / 'correcciones.sqlite3'))

    def candidata_copia(self, nombre='candidata'):
        carpeta = self.raiz / nombre
        carpeta.mkdir()
        for archivo in ('metadata.json', 'pesos.npz'):
            shutil.copy2(self.activa / archivo, carpeta / archivo)
        metadata = json.loads((carpeta / 'metadata.json').read_text(encoding='utf-8'))
        metadata['id_modelo'] = nombre
        (carpeta / 'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
        return carpeta

    def aprobar(self, texto, intencion):
        registro = correcciones.registrar(texto, intencion)
        return correcciones.revisar(registro['id'], True)

    def test_correcciones_aprobadas_solo_amplian_entrenamiento_y_reservas_quedan_intactas(self):
        datos_originales, partes_originales = entrenamiento.cargar_corpus()
        corpus_original = self.corpus.read_bytes()
        nueva = self.aprobar('el artista ofrece palmadas rítmicas al finalizar el espectáculo', 'aplaudir')
        correcciones.registrar('un movimiento de hombros pendiente de examinar', 'bailar')
        rechazada = correcciones.registrar('gira su palma para despedirse', 'saludar')
        correcciones.revisar(rechazada['id'], False)
        reservado = partes_originales['validacion'][0]
        self.aprobar(reservado['texto'], reservado['intencion'])
        datos, partes, textos, etiquetas, resumen = entrenamiento.preparar_datos(usar_correcciones=True)
        self.assertEqual(datos, datos_originales)
        self.assertEqual(partes['validacion'], partes_originales['validacion'])
        self.assertEqual(partes['prueba'], partes_originales['prueba'])
        self.assertEqual(len(partes['entrenamiento']), len(partes_originales['entrenamiento']) + 1)
        self.assertEqual(partes['entrenamiento'][-1]['id'], 'correccion_' + nueva['id'])
        self.assertEqual(partes['entrenamiento'][-1]['particion'], 'entrenamiento')
        self.assertEqual(resumen['n_aprobadas'], 2)
        self.assertEqual(resumen['n_incorporadas'], 1)
        self.assertEqual(resumen['omitidas'][0]['motivo'], 'texto_reservado_validacion_o_prueba')
        self.assertEqual(len(textos), 3 * len(partes['entrenamiento']))
        self.assertEqual(len(textos), len(etiquetas))
        self.assertEqual(self.corpus.read_bytes(), corpus_original)
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)

    def test_sin_correcciones_aprobadas_entrenamiento_no_publica_nada(self):
        candidata = self.raiz / 'sin_aprobadas'
        correcciones.registrar('una expresión todavía no revisada', 'curiosidad')
        with self.assertRaisesRegex(ValueError, 'No hay correcciones aprobadas'):
            entrenamiento.entrenar(usar_correcciones=True, carpeta_version=candidata)
        self.assertFalse(candidata.exists())
        self.assertFalse((self.raiz / 'evaluaciones').exists())
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)

    def test_entrenamiento_real_crea_candidata_reproducible_y_conserva_activa(self):
        nueva = self.aprobar('el artista ofrece palmadas rítmicas al finalizar el espectáculo', 'aplaudir')
        carpeta = self.raiz / 'candidata_entrenada'
        informe = entrenamiento.entrenar(usar_correcciones=True, carpeta_version=carpeta)
        self.assertEqual(informe['estado'], 'candidata')
        self.assertNotIn('activacion', informe)
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)
        metadata = json.loads((carpeta / 'metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(set(metadata['clases']), set(correcciones.ETIQUETAS))
        self.assertEqual(metadata['particiones'], dict(entrenamiento=353, validacion=84, prueba=112))
        self.assertEqual(metadata['correcciones_revisadas']['n_incorporadas'], 1)
        self.assertEqual(metadata['sha256_pesos'], huellas(carpeta)['pesos.npz'])
        self.assertLess(informe['max_error_paridad_exportacion'], 1e-10)
        self.assertEqual(informe['prueba']['total'], 112)
        snapshot = json.loads((carpeta / 'corpus_utilizado.json').read_text(encoding='utf-8'))
        incorporada = next(e for e in snapshot['ejemplos'] if e['id'] == 'correccion_' + nueva['id'])
        self.assertEqual(incorporada['origen'], 'correccion_usuario_revisada')
        self.assertEqual(incorporada['particion'], 'entrenamiento')
        self.assertEqual(len(metadata['sha256_entrenamiento']), 64)
        self.assertTrue((carpeta / 'informe.json').is_file())
        self.assertFalse((self.activa / 'activacion.json').exists())

    def test_activacion_igual_guarda_respaldo_y_solo_consulta_validacion(self):
        carpeta = self.candidata_copia('igual-validacion')
        evaluar_original = entrenamiento.evaluar_particion
        conjuntos = []

        def evaluar_solo_validacion(ejemplos, modelo):
            self.assertEqual(len(ejemplos), 84)
            self.assertTrue(all(e['particion'] == 'validacion' for e in ejemplos))
            conjuntos.append([e['id'] for e in ejemplos])
            return evaluar_original(ejemplos, modelo)

        with patch.object(entrenamiento, 'evaluar_particion', side_effect=evaluar_solo_validacion) as evaluar:
            resultado = entrenamiento.activar_version(carpeta)
        self.assertEqual(evaluar.call_count, 2)
        self.assertEqual(conjuntos[0], conjuntos[1])
        self.assertEqual(resultado['modelo'], 'igual-validacion')
        respaldo = Path(resultado['respaldo'])
        self.assertEqual(huellas(respaldo), self.huellas_iniciales)
        self.assertEqual(huellas(self.activa), huellas(carpeta))
        self.assertTrue((self.activa / 'activacion.json').exists())

    def test_candidata_con_cero_aceptados_se_rechaza_sin_cambiar_activa(self):
        carpeta = self.candidata_copia('sin_cobertura')
        metadata = json.loads((carpeta / 'metadata.json').read_text(encoding='utf-8'))
        metadata['umbral'] = 1.0
        (carpeta / 'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'política de aceptación'):
            entrenamiento.activar_version(carpeta)
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)
        self.assertFalse((self.activa / 'versiones').exists())

    def test_candidata_corrupta_no_se_promueve(self):
        carpeta = self.candidata_copia('corrupta')
        (carpeta / 'pesos.npz').write_bytes(b'pesos corruptos')
        with patch.object(entrenamiento, 'evaluar_particion') as evaluar:
            with self.assertRaisesRegex(ValueError, 'no corresponden'):
                entrenamiento.activar_version(carpeta)
        evaluar.assert_not_called()
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)

    def test_corpus_distinto_no_se_promueve_ni_se_evalua(self):
        carpeta = self.candidata_copia('otro_corpus')
        metadata = json.loads((carpeta / 'metadata.json').read_text(encoding='utf-8'))
        metadata['sha256_corpus'] = '0' * 64
        (carpeta / 'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
        with patch.object(entrenamiento, 'evaluar_particion') as evaluar:
            with self.assertRaisesRegex(ValueError, 'corpus base actual'):
                entrenamiento.activar_version(carpeta)
        evaluar.assert_not_called()
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)

    def test_fallo_de_promocion_restaura_modelo_activo_desde_respaldo(self):
        carpeta = self.candidata_copia('fallo_de_copia')
        copiar_original = shutil.copy2

        def fallar_segundo_archivo(origen, destino, *args, **kwargs):
            if Path(destino) == self.activa / 'metadata.json.pendiente':
                raise OSError('fallo de disco simulado')
            return copiar_original(origen, destino, *args, **kwargs)

        with patch.object(entrenamiento.shutil, 'copy2', side_effect=fallar_segundo_archivo):
            with self.assertRaisesRegex(OSError, 'fallo de disco'):
                entrenamiento.activar_version(carpeta)
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)
        self.assertFalse((self.activa / 'activacion.json').exists())

    def test_activacion_independiente_actualiza_informes_y_conserva_prueba_historica(self):
        carpeta = self.candidata_copia('con_informe_compatible')
        metadata = json.loads((carpeta / 'metadata.json').read_text(encoding='utf-8'))
        prueba_historica = dict(total=112, nota='Resultado histórico; no recalcular al activar.')
        candidato = dict(modelo=metadata['id_modelo'], sha256_pesos=metadata['sha256_pesos'],
                         estado='candidata', prueba=prueba_historica)
        (carpeta / 'informe.json').write_text(json.dumps(candidato), encoding='utf-8')
        evaluar_original = entrenamiento.evaluar_particion

        def solo_validacion(ejemplos, modelo):
            self.assertTrue(all(e['particion'] == 'validacion' for e in ejemplos))
            return evaluar_original(ejemplos, modelo)

        with patch.object(entrenamiento, 'evaluar_particion', side_effect=solo_validacion) as evaluar:
            activacion = entrenamiento.activar_version(carpeta)
        self.assertEqual(evaluar.call_count, 2)
        publicado = json.loads(entrenamiento.INFORME.read_text(encoding='utf-8'))
        actualizado = json.loads((carpeta / 'informe.json').read_text(encoding='utf-8'))
        self.assertEqual(actualizado, publicado)
        self.assertEqual(publicado['estado'], 'activa')
        self.assertEqual(publicado['modelo'], metadata['id_modelo'])
        self.assertEqual(publicado['sha256_pesos'], metadata['sha256_pesos'])
        self.assertEqual(publicado['activacion'], activacion)
        self.assertEqual(publicado['prueba'], prueba_historica)
        self.assertEqual(publicado['validacion']['total'], 84)

    def test_informe_incompatible_impide_activacion_y_conserva_informe_anterior(self):
        carpeta = self.candidata_copia('informe_incompatible')
        metadata = json.loads((carpeta / 'metadata.json').read_text(encoding='utf-8'))
        reporte = dict(modelo=metadata['id_modelo'], sha256_pesos='0' * 64, estado='candidata')
        ruta_candidato = carpeta / 'informe.json'
        ruta_candidato.write_text(json.dumps(reporte), encoding='utf-8')
        entrenamiento.INFORME.parent.mkdir(parents=True)
        entrenamiento.INFORME.write_text('{"modelo":"activa_anterior"}', encoding='utf-8')
        informe_anterior = entrenamiento.INFORME.read_bytes()
        candidato_anterior = ruta_candidato.read_bytes()
        with patch.object(entrenamiento, 'evaluar_particion') as evaluar:
            with self.assertRaisesRegex(ValueError, 'informe de la candidata no corresponde'):
                entrenamiento.activar_version(carpeta)
        evaluar.assert_not_called()
        self.assertEqual(huellas(self.activa), self.huellas_iniciales)
        self.assertEqual(entrenamiento.INFORME.read_bytes(), informe_anterior)
        self.assertEqual(ruta_candidato.read_bytes(), candidato_anterior)
        self.assertFalse((self.activa / 'versiones').exists())

    def test_primera_activacion_fallida_no_deja_un_modelo_parcial(self):
        carpeta = self.candidata_copia('primera_instalacion')
        for nombre in ('metadata.json', 'pesos.npz'):
            (self.activa / nombre).unlink()
        copiar_original = shutil.copy2

        def fallar_segundo_archivo(origen, destino, *args, **kwargs):
            if Path(destino) == self.activa / 'metadata.json.pendiente':
                raise OSError('fallo de disco simulado durante primera instalación')
            return copiar_original(origen, destino, *args, **kwargs)

        with patch.object(entrenamiento.shutil, 'copy2', side_effect=fallar_segundo_archivo):
            with self.assertRaisesRegex(OSError, 'primera instalación'):
                entrenamiento.activar_version(carpeta)
        self.assertEqual(huellas(self.activa), {})
        self.assertFalse((self.activa / 'activacion.json').exists())
        self.assertFalse(entrenamiento.INFORME.exists())


if __name__ == '__main__':
    unittest.main()
