"""Comprueba que pesos aprendidos resuelven nuevas peticiones y llegan al MMS.

No mide calidad visual en GTA ni consulta proveedores de IA. La prueba de ablación
exige que las frases nuevas no se reconozcan solamente mediante las reglas previas.
"""
import configparser
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from src import modelo_intenciones as modelo
from src.capacidades_escena import candidata_local
from src.mvp_mms import generar_mms
from src.mvp_plan import plan_local, validar_plan
from src.propuesta_escena import completar_propuesta


EJEMPLOS=(
    ('una persona se mueve al ritmo de la musica','bailar',{'dance_loop','DAN_Loop_A'}),
    ('una persona junta las palmas repetidamente','aplaudir',{'bd_clap','bd_clap1'}),
)


class ModeloIntenciones(unittest.TestCase):
    def test_caracteristicas_son_consistentes_con_mayusculas_y_tildes(self):
        self.assertEqual(modelo.caracteristicas('MÚSICA RÍTMICA'),modelo.caracteristicas('musica ritmica'))
        self.assertEqual(modelo.caracteristicas('123 !!!'),{})
        self.assertGreater(modelo.caracteristicas('palmas palmas')['w:palmas'],1)

    def test_nuevas_parafrasis_necesitan_pesos_entrenados(self):
        for texto,intencion,_ in EJEMPLOS:
            with self.subTest(texto=texto):
                self.assertIsNone(candidata_local(texto,usar_modelo=False))
                prediccion=modelo.predecir_intencion(texto)
                self.assertTrue(prediccion['aceptada'],prediccion)
                self.assertEqual(prediccion['intencion'],intencion)
                self.assertGreater(prediccion['puntuacion'],0)
                self.assertLessEqual(prediccion['puntuacion'],1)
                self.assertEqual(len(prediccion['sha256_pesos']),64)
                self.assertTrue(prediccion['modelo'])
                candidata=candidata_local(texto)
                self.assertIsNotNone(candidata)
                self.assertIn(candidata[1]['anim'],EJEMPLOS[0][2] if intencion=='bailar' else EJEMPLOS[1][2])

    def test_prediccion_aprendida_se_compila_a_animacion_real_con_procedencia(self):
        for texto,intencion,nombres in EJEMPLOS:
            with self.subTest(texto=texto):
                p=completar_propuesta(validar_plan(plan_local(texto),texto),texto)
                self.assertTrue(p.es_valido,p.razon_rechazo)
                self.assertEqual(p.accion,'animacion')
                self.assertTrue(p.fuente.startswith('Clasificador supervisado local'),p.fuente)
                evidencia=p.aprendizaje_supervisado
                self.assertEqual(evidencia['intencion'],intencion)
                self.assertEqual(evidencia['sha256_pesos'],modelo.predecir_intencion(texto)['sha256_pesos'])
                self.assertEqual(evidencia['modelo'],modelo.predecir_intencion(texto)['modelo'])
                contenido=generar_mms(actor_id=p.actor_id_sugerido,actores_ids=p.actores_ids_sugeridos,
                    inicio=(2100.,-1700.,13.),destino=None,duracion=p.duracion_sugerida,
                    hora=p.hora_sugerida,clima=p.clima_id_sugerido,accion=p.accion,
                    animacion_sugerida=p.animacion_sugerida,animar_actores=p.animar_actores,
                    reproduccion=p.reproduccion,pasos=[s.model_dump() for s in p.pasos],
                    descripcion=texto)
                cfg=configparser.ConfigParser(interpolation=None)
                cfg.optionxform=str
                cfg.read_string(contenido)
                clips=[cfg[s] for s in cfg if s.startswith('ACTION_A_') and cfg[s].get('Type')=='3']
                self.assertTrue(clips,'El plan no produjo ninguna tarea real de animación.')
                self.assertTrue(all(c['ANIM'] in nombres for c in clips))
                self.assertTrue(all(c['IFP'] for c in clips))

    def test_abstencion_en_negaciones_composiciones_mecanicas_y_desconocidos(self):
        frases=(
            '', ' ', '!!! @#$%', '123456',
            'una persona no baila', 'no quiero que aplauda', 'una persona nunca fuma',
            'una persona se mueve al ritmo y luego corre',
            'una persona junta las palmas mientras otro salta',
            'una persona camina', 'un personaje corre', 'una persona nada',
            'una persona apunta con un arma', 'sube las escaleras',
            'una persona conduce un coche', 'un auto recorre la ciudad',
            'una persona fuma sobre el techo de un taxi',
            'crea un dragon que vuele', 'una persona dispara',
            'quiero algo indeterminado', 'configura la resolucion de la pantalla',
            'calcula la raiz cuadrada de treinta', 'hay una mesa junto a la pared',
        )
        for texto in frases:
            with self.subTest(texto=texto):
                prediccion=modelo.predecir_intencion(texto)
                self.assertFalse(prediccion['aceptada'],prediccion)

    def test_ausencia_de_pesos_abstiene_y_conserva_las_reglas_existentes(self):
        with tempfile.TemporaryDirectory() as temporal,patch.object(modelo,'CARPETA_MODELO',Path(temporal)):
            self.assertEqual(modelo.firma_modelo(),((0,0),(0,0)))
            prediccion=modelo.predecir_intencion(EJEMPLOS[0][0])
            self.assertFalse(prediccion['aceptada'])
            self.assertIn(prediccion['motivo'],('modelo_no_entrenado','modelo_no_disponible_o_incompatible'))
            self.assertIsNone(candidata_local(EJEMPLOS[0][0]))
            self.assertIsNotNone(candidata_local('una persona baila'))
            self.assertTrue(plan_local('una persona baila').es_valido)

    def test_analizar_peticion_aprendida_no_necesita_consultar_proveedores(self):
        import src.mvp_plan as planificador
        with patch.object(planificador,'_analizar_sin_cache',side_effect=AssertionError('No se debe consultar una API.')) as consulta,\
                patch.object(planificador,'_ultima_consulta',0),patch.object(planificador,'_api_bloqueada_hasta',0):
            plan=planificador.analizar_peticion_final(EJEMPLOS[0][0])
        consulta.assert_not_called()
        self.assertTrue(plan.es_valido,plan.razon_rechazo)
        self.assertTrue(plan.fuente.startswith('Clasificador supervisado local'),plan.fuente)

    def test_inferencia_exportada_funciona_sin_sklearn_scipy_ni_joblib(self):
        codigo=textwrap.dedent('''
            import builtins,json
            importar_original=builtins.__import__
            def importar(nombre,*args,**kwargs):
                if nombre.split('.')[0] in {'sklearn','scipy','joblib'}:
                    raise ImportError('Paquete de entrenamiento bloqueado: '+nombre)
                return importar_original(nombre,*args,**kwargs)
            builtins.__import__=importar
            from src.modelo_intenciones import predecir_intencion
            print(json.dumps(predecir_intencion('una persona se mueve al ritmo de la musica')))
        ''')
        proceso=subprocess.run([sys.executable,'-c',codigo],cwd=Path(__file__).resolve().parents[1],
            capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(proceso.returncode,0,proceso.stderr)
        prediccion=json.loads(proceso.stdout)
        self.assertTrue(prediccion['aceptada'],prediccion)
        self.assertEqual(prediccion['intencion'],'bailar')

    def test_cache_distingue_carpetas_con_igual_tamano_y_fecha(self):
        texto=EJEMPLOS[0][0]
        fuente=modelo.CARPETA_MODELO
        original=modelo.predecir_intencion(texto)
        identificador=original['modelo']
        otro_identificador=identificador[0].upper()+identificador[1:]
        self.assertNotEqual(identificador,otro_identificador)
        with tempfile.TemporaryDirectory() as temporal:
            destino=Path(temporal)
            for nombre in ('metadata.json','pesos.npz'):shutil.copy2(fuente/nombre,destino/nombre)
            metadata=destino/'metadata.json'
            estado=metadata.stat()
            metadata.write_bytes(metadata.read_bytes().replace(identificador.encode(),otro_identificador.encode(),1))
            os.utime(metadata,ns=(estado.st_atime_ns,estado.st_mtime_ns))
            with patch.object(modelo,'CARPETA_MODELO',destino):
                otra=modelo.predecir_intencion(texto)
            self.assertTrue(otra['aceptada'],otra)
            self.assertEqual(otra['modelo'],otro_identificador)
            self.assertEqual(otra['sha256_pesos'],original['sha256_pesos'])


class TrazabilidadModeloUI(unittest.IsolatedAsyncioTestCase):
    async def test_interfaz_conserva_id_y_huella_en_el_plan_exportado(self):
        import flet as ft
        import main as app
        import src.mvp_mms as mms
        from test_ui_mvp import PagePrueba, recorrer, evento

        texto=EJEMPLOS[0][0]
        prediccion=modelo.predecir_intencion(texto)
        plan=completar_propuesta(validar_plan(plan_local(texto),texto),texto)
        with patch.object(ft.Container,'update',lambda self:None),\
                patch.object(app,'analizar_accion_usuario',return_value=plan):
            page=PagePrueba()
            await app.main(page)
            controles=list(recorrer(page.controls))
            next(c for c in controles if isinstance(c,ft.TextField)).value=texto
            await evento(controles,'on_analizar').on_click(None)
            with tempfile.TemporaryDirectory() as temporal,patch.object(mms,'ROOT',Path(temporal)):
                actores=Path(temporal)/'assets/actors'
                actores.mkdir(parents=True)
                for identificador in plan.actores_ids_sugeridos:(actores/f'{identificador}.png').touch()
                await evento(controles,'on_crear_mms').on_click(None)
                archivos=list((Path(temporal)/'salida_mms').glob('*.mms'))
                self.assertEqual(len(archivos),1)
                datos=json.loads(archivos[0].with_suffix('.json').read_text(encoding='utf-8'))
                evidencia=datos['plan']['aprendizaje_supervisado']
                self.assertEqual(evidencia['modelo'],prediccion['modelo'])
                self.assertEqual(evidencia['sha256_pesos'],prediccion['sha256_pesos'])
                self.assertEqual(evidencia['intencion'],'bailar')
                self.assertTrue(datos['plan']['fuente'].startswith('Clasificador supervisado local'))


if __name__=='__main__':unittest.main()
