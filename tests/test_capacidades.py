import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from src.mvp_plan import plan_local, analizar_peticion_mvp, comprobaciones_peticion
from src.mvp_mms import generar_mms, POS_INICIO, POS_DESTINO
import configparser
import math
from src.busqueda_animaciones import pistas_tecnicas


class Capacidades(unittest.TestCase):
    def setUp(self):
        import src.mvp_plan as modulo
        modulo._cache_analisis.clear()
        modulo._ultima_consulta=0
        modulo._api_bloqueada_hasta=0

    def test_movimientos_reales_del_mod(self):
        for texto,movimiento,modo in [('una persona corre en un puente','correr','2'),
            ('dos personas nadan','nadar','1'),('un personaje sube escaleras','escaleras','1'),
            ('dos personas caminan al lado de la playa','caminar','1')]:
            p=plan_local(texto)
            self.assertTrue(p.es_valido,texto)
            self.assertEqual(p.tipo_movimiento,movimiento)
            self.assertEqual(comprobaciones_peticion(texto),[True]*4)
            s=generar_mms(actor_id=112,inicio=POS_INICIO,destino=POS_DESTINO,
                actores_ids=[112]*p.cantidad_actores,accion=p.accion,tipo_movimiento=p.tipo_movimiento)
            self.assertEqual(s.count('POINT_MODE1='+modo),p.cantidad_actores)

    def test_cache_y_limite_evitan_consultas_duplicadas(self):
        import src.mvp_plan as modulo
        p=plan_local('una persona corre en un puente');p.fuente='Gemini 3.5 Flash'
        with patch.object(modulo,'_analizar_sin_cache',return_value=p) as llamada:
            primero=analizar_peticion_mvp('una persona corre en un puente')
            segundo=analizar_peticion_mvp('una persona corre en un puente')
            analizar_peticion_mvp('dos personas nadan')
            self.assertEqual(llamada.call_count,1)
            self.assertEqual(segundo.fuente,primero.fuente)
            segundo.resumen='editado'
            self.assertNotEqual(analizar_peticion_mvp('una persona corre en un puente').resumen,'editado')

    def test_429_detiene_nuevas_consultas(self):
        import src.mvp_plan as modulo
        with patch.object(modulo,'_api_bloqueada_hasta',float('inf')),patch.object(modulo,'_analizar_sin_cache') as llamada:
            self.assertTrue(analizar_peticion_mvp('una persona corre').es_valido)
            llamada.assert_not_called()
    def test_caminata_grupal_lluvia_y_atardecer(self):
        for texto,cantidad,clima,hora in [
            ('dos personas caminan bajo la lluvia',2,8,None),
            ('cuatro personajes caminan por el campo bajo la lluvia al atardecer',4,16,18),
            ('dos personas caminan al atardecer',2,0,18)]:
            p=plan_local(texto)
            self.assertTrue(p.es_valido,texto)
            self.assertEqual(p.cantidad_actores,cantidad)
            self.assertEqual(p.clima_id_sugerido,clima)
            self.assertEqual(p.hora_sugerida,hora)
            self.assertEqual(comprobaciones_peticion(texto),[True]*4)
            s=generar_mms(actor_id=112,actores_ids=[112]*cantidad,inicio=POS_INICIO,destino=POS_DESTINO,
                accion=p.accion,clima=clima,hora=hora or 12)
            ini=configparser.ConfigParser(interpolation=None);ini.optionxform=str;ini.read_string(s)
            for n in range(1,cantidad+1):
                self.assertEqual(ini[f'ACTION_A_{n}']['SPHERE_ACTOR'],str(n))
                self.assertEqual(ini[f'ACTION_A_{n}']['Type'],'4')
                ini_p=tuple(float(ini[f'ACTOR_{n}'][k]) for k in ('X','Y'))
                fin_p=tuple(float(ini[f'ACTION_A_{n}'][k]) for k in ('POINT_X1','POINT_Y1'))
                self.assertAlmostEqual(math.dist(ini_p,fin_p),math.dist(POS_INICIO[:2],POS_DESTINO[:2]),places=5)
            self.assertEqual(ini['OBJ_1']['GAME_WEATHER'],str(clima))
    def test_dos_bailan_sin_api_y_ambos_tienen_accion(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'','GROQ_API_KEY':''}),patch('src.mvp_plan.load_dotenv'):
            p=analizar_peticion_mvp('dos personas bailan en un puente')
        self.assertTrue(p.es_valido)
        self.assertEqual(p.animar_actores,[1,2])
        self.assertEqual(comprobaciones_peticion('dos personas bailan en un puente'),[True]*4)
        s=generar_mms(actor_id=112,actores_ids=[112,112],inicio=POS_INICIO,destino=None,
            accion=p.accion,animacion_sugerida=p.animacion_sugerida,animar_actores=p.animar_actores)
        self.assertEqual(s.count('ANIM=dance_loop'),2)
        self.assertIn('[ACTION_A_2]',s)

    def test_gemini_recibe_todo_descripciones_y_referencias(self):
        p=plan_local('dos personas bailan en un puente')
        cliente=MagicMock()
        cliente.models.generate_content.return_value=SimpleNamespace(text=p.model_dump_json())
        with patch.dict(os.environ,{'GEMINI_API_KEY':'prueba-no-real'}),patch('src.mvp_plan.load_dotenv'),patch('src.mvp_plan.genai.Client',return_value=cliente):
            resultado=analizar_peticion_mvp('dos personas bailan en un puente')
        self.assertTrue(resultado.es_valido)
        self.assertEqual(resultado.fuente,'Gemini 3.5 Flash')
        llamada=cliente.models.generate_content.call_args.kwargs
        contexto=llamada['config'].system_instruction
        self.assertIn(Path('src/todo.txt').read_text(encoding='utf-8'),contexto)
        self.assertIn('EVIDENCIA VISUAL AUTOMATICA',contexto)
        self.assertIn('REFERENCIAS CINEMATOGRAFICAS',contexto)
        self.assertTrue(any(getattr(getattr(p,'inline_data',None),'mime_type',None)=='image/jpeg' for p in llamada['contents']))
        cliente.close.assert_called_once()

    def test_luces_no_aprueban_limites_ni_acciones_desconocidas(self):
        self.assertFalse(comprobaciones_peticion('cinco personas bailan')[2])
        self.assertFalse(comprobaciones_peticion('bailar durante 90 segundos')[3])
        self.assertIsNone(comprobaciones_peticion('quiero algo indeterminado')[1])

    def test_barrer_no_es_llorar(self):
        self.assertFalse(any('llorar' in p for p in pistas_tecnicas({'anim':'sweep_1'})))
