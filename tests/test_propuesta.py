import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from src.mvp_plan import plan_local,validar_plan,PlanMVP
from src.propuesta_escena import completar_propuesta
from src.ubicaciones_escena import elegir_ruta_vehiculo

FRASE='quiero que un personaje camine, se suba a un vehículo y ande por la cuidad'


class Propuesta(unittest.TestCase):
    def test_respuesta_gemini_llega_sin_perder_sus_elecciones_en_una_llamada(self):
        import src.mvp_plan as planificador
        respuesta=plan_local(FRASE)
        respuesta.actor_id_sugerido=112;respuesta.actores_ids_sugeridos=[112]
        respuesta.vehiculo_id_sugerido=411;respuesta.clima_id_sugerido=4;respuesta.hora_sugerida=17
        cliente=MagicMock()
        cliente.models.generate_content.return_value=SimpleNamespace(text=respuesta.model_dump_json())
        with patch.dict(os.environ,{'GEMINI_API_KEY':'clave-de-prueba','GROQ_API_KEY':''}),patch.object(planificador.genai,'Client',return_value=cliente):
            resultado=planificador._analizar_sin_cache(FRASE)
        cliente.models.generate_content.assert_called_once()
        self.assertTrue(resultado.fuente.startswith('Gemini'))
        self.assertEqual(resultado.accion,'conducir_vehiculo')
        self.assertEqual((resultado.actor_id_sugerido,resultado.vehiculo_id_sugerido,resultado.clima_id_sugerido,resultado.hora_sugerida),(112,411,4,17))

    def test_frase_exacta_no_termina_al_subir(self):
        for t in (FRASE,'un personaje se sube a un auto y recorre las calles',
                  'una persona entra a un coche y circula por la ciudad'):
            p=validar_plan(plan_local(t),t)
            self.assertTrue(p.es_valido)
            self.assertEqual(p.accion,'conducir_vehiculo')
        p=completar_propuesta(validar_plan(plan_local(FRASE),FRASE),FRASE)
        self.assertIsNotNone(p.ruta_vehiculo_id)
        self.assertEqual(elegir_ruta_vehiculo(identificador=p.ruta_vehiculo_id)['entorno'],'ciudad')

    def test_no_descarta_las_elecciones_validas_de_gemini(self):
        p=plan_local(FRASE)
        p.actor_id_sugerido=112;p.actores_ids_sugeridos=[112]
        p.vehiculo_id_sugerido=411;p.clima_id_sugerido=4;p.hora_sugerida=17
        p.motivo_elecciones='Escena urbana con un coche deportivo y cielo nublado.'
        p=completar_propuesta(validar_plan(p,FRASE),FRASE)
        self.assertEqual((p.actor_id_sugerido,p.vehiculo_id_sugerido,p.clima_id_sugerido,p.hora_sugerida),(112,411,4,17))
        self.assertEqual(p.actores_ids_sugeridos,[112])
        self.assertIn('coche deportivo',p.motivo_elecciones)

    def test_peticiones_explicitas_tienen_prioridad_y_propuesta_es_idempotente(self):
        t='un personaje skin 38 se sube a un auto y maneja bajo la lluvia al atardecer'
        p=plan_local(t);p.actor_id_sugerido=112;p.actores_ids_sugeridos=[112];p.clima_id_sugerido=19;p.hora_sugerida=3
        p=completar_propuesta(validar_plan(p,t),t)
        self.assertEqual(p.actor_id_sugerido,38)
        self.assertEqual(p.actores_ids_sugeridos,[38])
        self.assertEqual(p.clima_id_sugerido,8);self.assertEqual(p.hora_sugerida,18)
        self.assertEqual(p.model_dump(),completar_propuesta(p,t).model_dump())

    def test_bailar_completa_reparto_ambiente_y_lugar(self):
        t='cuatro personajes bailan en el campo'
        p=completar_propuesta(plan_local(t),t)
        self.assertEqual(len(set(p.actores_ids_sugeridos)),4)
        self.assertIsNotNone(p.clima_id_sugerido)
        self.assertIsNotNone(p.hora_sugerida)
        self.assertIsNotNone(p.ubicacion_id_sugerida)

    def test_ia_puede_interpretar_un_sinonimo_sin_degradarse_a_solo_entrar(self):
        t='un personaje se sube a un auto y empieza un viaje'
        p=plan_local(t);p.accion='conducir_vehiculo'
        self.assertEqual(validar_plan(p,t).accion,'conducir_vehiculo')
        t='un personaje hace un viaje en coche por la ciudad'
        p=PlanMVP(es_valido=True,resumen='Viaje urbano',accion='conducir_vehiculo',fuente='Gemini simulada')
        self.assertTrue(validar_plan(p,t).es_valido)
