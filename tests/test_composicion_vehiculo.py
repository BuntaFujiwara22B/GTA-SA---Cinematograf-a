import configparser
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from types import SimpleNamespace

from src.mvp_plan import plan_local,validar_plan,PlanMVP,comprobaciones_peticion
from src.mvp_mms import generar_mms,exportar_escena
from src.propuesta_escena import completar_propuesta
from src.registro_capacidades import registro,soportes_vehiculos

FRASE='una persona fuma en el techo de un auto de movimiento'


def preparar(t):return completar_propuesta(validar_plan(plan_local(t),t),t)


def datos(p):
    return dict(actor_id=p.actor_id_sugerido,actores_ids=p.actores_ids_sugeridos,inicio=(0,0,10),destino=None,
        accion=p.accion,animacion_sugerida=p.animacion_sugerida,pasos=[a.model_dump() for a in p.pasos],
        vehiculo_en_movimiento=p.vehiculo_en_movimiento,vehiculo_id=p.vehiculo_id_sugerido,
        ruta_vehiculo_id=p.ruta_vehiculo_id,duracion=p.duracion_sugerida)


def leer(texto):
    c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.read_string(texto);return c


class ComposicionVehiculo(unittest.TestCase):
    def test_fumar_se_reconoce_y_exporta_un_clip_real(self):
        for t in ('una persona fuma','dos personas fuman en un puente','quiero que una persona fume','una persona quiere furmar'):
            p=preparar(t)
            self.assertTrue(p.es_valido,t);self.assertEqual(p.animacion_sugerida,'STAND:133:SMOKING:M_smk_drag')
            self.assertEqual(comprobaciones_peticion(t),[True]*4)
        p=preparar('una persona fuma')
        c=leer(generar_mms(**datos(p)))
        self.assertEqual((c['ACTION_A_1']['ANIM'],c['ACTION_A_1']['IFP'],c['ACTION_A_1']['Loop']),('M_smk_drag','SMOKING','1'))
        self.assertNotIn('Vehicle_1',c)

    def test_frase_exacta_no_omite_techo_ni_movimiento(self):
        p=preparar(FRASE)
        self.assertTrue(p.es_valido);self.assertEqual(comprobaciones_peticion(FRASE),[True]*4)
        self.assertEqual(p.accion,'animacion_sobre_vehiculo');self.assertTrue(p.vehiculo_en_movimiento)
        c=leer(generar_mms(**datos(p)))
        a=c['ACTION_A_1'];clip=c['ACTION_A_2']
        self.assertEqual((a['Type'],a['SPHERE_TYPE'],a['SPHERE_ACTOR'],a['SPHERE_VEH2']),('2','6','1','1'))
        self.assertEqual((clip['Type'],clip['SPHERE_TYPE'],clip['TP']),('3','0','0'))
        self.assertEqual(clip['ANIM'],'M_smk_drag')
        self.assertEqual((a['OBJ'],clip['OBJ'],c['ACTION_V_1']['OBJ']),('0','0','0'))
        self.assertFalse(any(c[s].get('Type')=='2' for s in c if s.startswith('OBJ_')))
        self.assertAlmostEqual(float(c['ACTOR_1']['Z'])-float(c['Vehicle_1']['Z']),float(a['T_Z']))
        self.assertTrue(p.limitaciones)

    def test_no_confunde_sobre_un_puente_con_sobre_un_auto_cercano(self):
        from src.registro_capacidades import pide_techo_vehiculo
        for t in ('una persona fuma sobre un puente junto a un auto','una persona fuma en el techo de una casa cerca de un auto'):
            self.assertFalse(pide_techo_vehiculo(t))
        for t in ('una persona fuma encima del coche','una persona fuma en el techo del auto',
            'un coche con una persona fumando en el techo'):
            self.assertTrue(pide_techo_vehiculo(t),t)

    def test_no_se_degrada_a_un_gesto_en_suelo_por_respuesta_incompleta(self):
        p=PlanMVP(es_valido=False,resumen='No soportado',accion='animacion',fuente='Gemini simulada')
        p=completar_propuesta(validar_plan(p,FRASE),FRASE)
        self.assertTrue(p.es_valido);self.assertEqual(p.accion,'animacion_sobre_vehiculo')
        self.assertTrue(p.vehiculo_en_movimiento)

    def test_modelo_no_rechaza_una_capacidad_conocida_sin_otras_dependencias(self):
        p=validar_plan(PlanMVP(es_valido=False,resumen='No se puede',fuente='Gemini simulada'),'una persona fuma')
        self.assertTrue(p.es_valido);self.assertEqual(p.accion,'animacion')

    def test_tiempo_del_clip_del_modelo_se_ajusta_al_plano_y_no_prefiere_idle(self):
        from src.escenas_semanticas import PasoEscena
        p=PlanMVP(es_valido=True,resumen='Fumar en techo',accion='animacion_sobre_vehiculo',
            pasos=[PasoEscena(accion='animacion',animacion='STAND:135:SMOKING:M_smk_loop',duracion=15)],
            fuente='Groq simulada')
        p=validar_plan(p,FRASE)
        self.assertTrue(p.es_valido);self.assertEqual(p.pasos[0].duracion,10)
        self.assertEqual(p.pasos[0].animacion,'STAND:133:SMOKING:M_smk_drag')

    def test_clip_explicito_en_techo_conserva_id_pedido(self):
        t='Reproduce el clip STAND:135:SMOKING:M_smk_loop en el techo de un auto en movimiento'
        p=preparar(t)
        self.assertTrue(p.es_valido)
        self.assertEqual(p.pasos[0].animacion,'STAND:135:SMOKING:M_smk_loop')

    def test_tiempos_sugeridos_no_rechazan_una_composicion_valida(self):
        p=plan_local('una persona saluda y luego fuma sobre un coche en movimiento')
        for paso in p.pasos:paso.duracion=15
        p=validar_plan(p,'una persona saluda y luego fuma sobre un coche en movimiento')
        self.assertTrue(p.es_valido)
        self.assertTrue(all(s.duracion is None for s in p.pasos))

    def test_duraciones_por_paso_se_suman_y_no_se_toma_solo_la_primera(self):
        from src.mvp_plan import duracion_pedida
        self.assertEqual(duracion_pedida('saluda durante 5 segundos y fuma durante 10 segundos'),15)
        self.assertEqual(duracion_pedida('saluda 5 segundos y fuma 10 segundos, duración del plano: 20 segundos'),20)

    def test_ia_puede_usar_un_clip_real_aunque_la_frase_no_este_en_reglas(self):
        from src.escenas_semanticas import PasoEscena
        t='un personaje gesticula de forma informal sobre un auto en movimiento'
        self.assertFalse(plan_local(t).es_valido)
        p=PlanMVP(es_valido=True,resumen='Gesto informal',accion='animacion_sobre_vehiculo',
            pasos=[PasoEscena(accion='animacion',animacion='CHAT:5:ped:IDLE_chat')],fuente='Gemini simulada')
        self.assertTrue(validar_plan(p,t).es_valido)

    def test_coche_parado_no_genera_recorrido_y_respeta_una_vez(self):
        p=preparar('una persona fuma una sola vez en el techo de un coche estacionado')
        self.assertTrue(p.es_valido);self.assertFalse(p.vehiculo_en_movimiento)
        c=leer(generar_mms(**datos(p)))
        self.assertNotIn('ACTION_V_1',c);self.assertEqual(c['ACTION_A_2']['Loop'],'0')

    def test_varios_clips_mantienen_anclaje_y_duracion(self):
        p=preparar('una persona saluda y luego fuma en el techo de un taxi en movimiento')
        c=leer(generar_mms(**datos(p)))
        self.assertEqual(c['Vehicle_1']['Model'],'420')
        self.assertEqual((c['ACTION_A_2']['OBJ'],c['ACTION_A_3']['OBJ']),('0','1'))
        self.assertEqual((c['ACTION_A_2']['ANIM'],c['ACTION_A_3']['ANIM']),('wave_loop','M_smk_drag'))
        self.assertTrue(all(c[s]['Type']!='7' for s in c if s.startswith('ACTION_A_')))
        self.assertEqual(sum(int(c[s]['DIAL_TIME']) for s in c if c[s].get('DIAL_TIME')),10000)

    def test_dependencias_rechazos_explican_que_parte_falta(self):
        for t in ('una persona fuma dentro de un auto','una persona fuma y conduce un auto',
            'una persona fuma sentada en una silla','una persona fuma generando humo'):
            p=validar_plan(plan_local(t),t)
            self.assertFalse(p.es_valido,t)
            self.assertIn('animación',p.razon_rechazo)
            self.assertIn('existe',p.razon_rechazo)
        for t in ('dos personas fuman sobre un auto en movimiento','una persona camina fumando',
            'una persona fuma y dispara en el techo de un auto','una persona se sube al techo de un auto y fuma'):
            self.assertFalse(plan_local(t).es_valido,t)

    def test_no_asume_techo_preparado_para_todos_los_modelos(self):
        p=plan_local('una persona fuma en el techo de un infernus en movimiento')
        self.assertFalse(p.es_valido)
        p=preparar(FRASE);d=datos(p);d['vehiculo_id']=468
        with self.assertRaises(ValueError):generar_mms(**d)

    def test_paquete_contiene_carrec_solo_si_hay_movimiento(self):
        import src.mvp_mms as mms
        from src.paquete_mision import dependencias
        for t,mueve in [(FRASE,True),('una persona fuma sobre un coche aparcado',False)]:
            p=preparar(t)
            with tempfile.TemporaryDirectory() as td,patch.object(mms,'ROOT',Path(td)):
                carpeta=Path(td)/'assets/actors';carpeta.mkdir(parents=True);(carpeta/'0.png').touch()
                archivo=exportar_escena(**datos(p))
                self.assertEqual(any(n.startswith('Carrec/') for n in dependencias(archivo)),mueve)

    def test_registro_y_fotos_reales_estan_en_contexto_de_la_ia(self):
        import os
        import src.mvp_plan as modulo
        from src.evidencia_animaciones import fotos_candidatas_animacion
        evidencias=fotos_candidatas_animacion('una persona fuma')
        self.assertTrue(any(e['id']=='STAND:133:SMOKING:M_smk_drag' for e,_ in evidencias))
        cliente=MagicMock();cliente.models.generate_content.return_value=SimpleNamespace(text=plan_local(FRASE).model_dump_json())
        with patch.dict(os.environ,{'GEMINI_API_KEY':'prueba-sin-clave-real','GROQ_API_KEY':''}),patch.object(modulo,'load_dotenv'),\
            patch.object(modulo.genai,'Client',return_value=cliente),patch.object(modulo,'_pausas_proveedor',{}):
            p=modulo._analizar_sin_cache(FRASE)
        self.assertTrue(p.es_valido)
        llamada=cliente.models.generate_content.call_args.kwargs
        self.assertIn('REGISTRO DE CAPACIDADES',llamada['config'].system_instruction)
        self.assertTrue(any(isinstance(c,str) and c.startswith('Fotograma real de animación') for c in llamada['contents']))
        self.assertEqual(registro()['clips_exportables'],1263)
        self.assertTrue(all(v['offset'][2]>0 for v in soportes_vehiculos()))
