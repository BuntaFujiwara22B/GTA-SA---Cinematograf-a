import configparser
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluar_escenas import corpus, comprobar
from src.mvp_plan import plan_local, validar_plan, PlanMVP
from src.propuesta_escena import completar_propuesta
from src.escenas_semanticas import PasoEscena, validar_pasos
from src.mvp_mms import generar_mms, exportar_escena


def preparar(texto):
    return completar_propuesta(validar_plan(plan_local(texto),texto),texto)


def leer(s):
    c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.read_string(s);return c


class EscenasSemanticas(unittest.TestCase):
    def test_corpus_mas_de_mil_peticiones_naturales_y_contratos_variados(self):
        casos=corpus()
        self.assertGreaterEqual(len(casos),1000)
        self.assertEqual(len(casos),len({c['texto'] for c in casos}))
        self.assertGreater(len({tuple(c['esperado'].get('acciones',[])) for c in casos}),100)
        self.assertFalse(any('Reproduce el clip' in c['texto'] for c in casos))

    def test_los_cinco_ejemplos_y_la_frase_de_la_captura(self):
        for caso in corpus()[:6]:
            with self.subTest(texto=caso['texto']):comprobar(caso,preparar(caso['texto']))

    def test_no_degrada_secuencia_a_solo_caminar(self):
        t='una persona salta, baila y corre'
        p=validar_plan(PlanMVP(es_valido=True,resumen='Caminar',fuente='Gemini simulada'),t)
        self.assertEqual([p.accion for p in p.pasos],['saltar','animacion','correr'])

    def test_propuesta_ia_con_ruta_no_se_convierte_en_estatica_por_ubicacion_sobrante(self):
        p=plan_local('una persona salta, baila y corre')
        p.ubicacion_id_sugerida='lugar_15_1869';p.tipo_movimiento='caminar'
        p=completar_propuesta(p,'una persona salta, baila y corre')
        self.assertIsNone(p.ubicacion_id_sugerida)
        self.assertEqual(p.tipo_movimiento,'correr')

    def test_ia_admite_parafrasis_que_no_coincida_con_reglas_locales(self):
        t='Necesito un transeúnte recorriendo la avenida a pie'
        self.assertFalse(plan_local(t).es_valido)
        p=validar_plan(PlanMVP(es_valido=True,resumen='Paseo urbano',accion='caminar',fuente='Gemini simulada'),t)
        self.assertTrue(p.es_valido)

    def test_reparto_de_tres_granjeros_conserva_roles_sin_civil_de_relleno(self):
        p=preparar('3 granjeros caminan por el campo')
        self.assertEqual(p.cantidad_actores,3)
        self.assertTrue(all(i in (158,161) for i in p.actores_ids_sugeridos))
        self.assertEqual(p.model_dump(),completar_propuesta(p,'3 granjeros caminan por el campo').model_dump())

    def test_puente_con_posicion_del_ejemplo_y_no_calle_aleatoria(self):
        p=preparar('dos personas se saludan en un puente')
        self.assertEqual(p.ubicacion_id_sugerida,'puente_ejemplo_usuario')
        self.assertEqual(p.animar_actores,[1,2])

    def test_objetivos_ordenan_salto_baile_carrera_sin_tareas_concurrentes(self):
        p=preparar('una persona salta, baila y corre')
        c=leer(generar_mms(actor_id=0,inicio=(2100,-1700,13),destino=(2100,-1690,13),
            accion='secuencia',pasos=[p.model_dump() for p in p.pasos]))
        acciones=[c[s] for s in c if s.startswith('ACTION_A_') and c[s]['Type']!='7']
        self.assertEqual([a['OBJ'] for a in acciones],['0','1','2'])
        self.assertEqual([a['Type'] for a in acciones],['5','3','4'])
        self.assertEqual(acciones[0]['SPHERE_TYPE'],'14')
        self.assertEqual(acciones[1]['ANIM'],'dance_loop')
        self.assertEqual(acciones[2]['POINT_MODE1'],'2')
        self.assertEqual(sum(int(c[s]['DIAL_TIME']) for s in c if c[s].get('DIAL_TIME')),10000)

    def test_reemplazar_ruta_conserva_espera_nativa_para_cancelar_hilo_previo(self):
        c=leer(generar_mms(actor_id=0,inicio=(2100,-1700,13),destino=(2100,-1692,13),
            accion='secuencia',pasos=[dict(accion='caminar'),dict(accion='correr')]))
        acciones=[c[s] for s in c if s.startswith('ACTION_A_')]
        self.assertEqual([a['Type'] for a in acciones],['7','4','4'])
        self.assertEqual([a['OBJ'] for a in acciones],['0','0','1'])

    def test_apuntar_crea_arma_y_vinculo_al_otro_actor(self):
        p=preparar('un policía apunta a un criminal')
        c=leer(generar_mms(actor_id=p.actor_id_sugerido,actores_ids=p.actores_ids_sugeridos,
            inicio=(2100,-1700,13),destino=None,accion=p.accion,pasos=[p.model_dump() for p in p.pasos]))
        a=next(c[s] for s in c if s.startswith('ACTION_A_') and c[s]['Type']=='1')
        self.assertEqual((a['SPHERE_TYPE'],a['SPHERE_ACTOR'],a['SPHERE_ACTOR2']),('2','1','2'))
        self.assertEqual(c['ACTOR_1']['Weapon'],'22')

    def test_dialogos_no_alteran_objetivos_de_acciones_ni_duracion(self):
        p=preparar('una persona salta, luego camina por una calle')
        c=leer(generar_mms(actor_id=0,inicio=(2100,-1700,13),destino=(2100,-1695,13),
            accion='secuencia',pasos=[p.model_dump() for p in p.pasos],dialogos=['Hola.','Vamos.']))
        self.assertEqual(sum(int(c[s]['DIAL_TIME']) for s in c if c[s].get('DIAL_TIME')),10000)
        mover=next(c[s] for s in c if s.startswith('ACTION_A_') and c[s]['Type']=='4')
        antes=sum(int(c[f'OBJ_{n}']['DIAL_TIME']) for n in range(1,int(mover['OBJ'])+1))
        self.assertEqual(antes,2000)
        self.assertTrue(any(c[s].get('TEXT')=='Vamos.' for s in c))

    def test_rechaza_clips_blancos_o_tiempos_imposibles(self):
        for pasos,tiempo in [([PasoEscena(accion='apuntar',objetivo_actor=1)],10),
            ([PasoEscena(accion='animacion',animacion='inventado')],10),
            ([PasoEscena(accion='saltar')]*8,10)]:
            with self.assertRaises(ValueError):validar_pasos(pasos,1,tiempo)
        with self.assertRaises(ValueError):
            generar_mms(actor_id=0,inicio=(2100,-1700,13),destino=(2200,-1700,13),accion='secuencia',
                pasos=[dict(accion='saltar'),dict(accion='caminar')])

    def test_no_inventa_simultaneidad_y_no_ejecuta_acciones_negadas(self):
        p=plan_local('una persona camina sin correr')
        self.assertTrue(p.es_valido)
        self.assertEqual([s.accion for s in p.pasos],['caminar'])
        self.assertFalse(plan_local('una persona no baila').es_valido)
        t='un personaje baila mientras otro corre'
        self.assertFalse(plan_local(t).es_valido)
        self.assertFalse(validar_plan(PlanMVP(es_valido=True,resumen='Secuencia',accion='secuencia',
            pasos=[PasoEscena(accion='caminar')],fuente='Gemini simulada'),t).es_valido)

    def test_duracion_explicita_en_palabras_y_valor_por_defecto(self):
        for frase,duracion in [('dos personas bailan durante treinta y cinco segundos',35),
            ('una persona salta durante medio minuto',30),('dos personas se saludan en un puente',10)]:
            p=plan_local(frase);p.duracion_sugerida=5
            p=validar_plan(p,frase)
            self.assertEqual(p.duracion_sugerida,duracion)
        self.assertFalse(validar_plan(plan_local('baila durante dos minutos'),'baila durante dos minutos').es_valido)

    def test_auto_solo_exporta_carrec_empaquetable_y_sin_actor_visible(self):
        import src.mvp_mms as mms
        from src.ubicaciones_escena import elegir_ruta_vehiculo,puntos_entrada
        from src.paquete_mision import dependencias
        p=preparar('un auto conduce solo en la cuidad')
        a,b=puntos_entrada(elegir_ruta_vehiculo(identificador=p.ruta_vehiculo_id))
        with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
            actores=Path(t)/'assets/actors';actores.mkdir(parents=True);(actores/'0.png').touch()
            archivo=exportar_escena(actor_id=0,inicio=a,destino=b,accion=p.accion,
                vehiculo_id=p.vehiculo_id_sugerido,ruta_vehiculo_id=p.ruta_vehiculo_id,camara='vehiculo_pov')
            c=leer(archivo.read_text(encoding='utf-8'))
            self.assertFalse(any(s.startswith(('ACTOR_','ACTION_A_')) for s in c))
            self.assertEqual(c['ACTION_V_1']['OBJ'],'0')
            self.assertEqual(c['OBJ_1']['PLA_CUM_ZOOM'],'112')
            self.assertTrue(any(p.startswith('Carrec/') for p in dependencias(archivo)))

    def test_gemini_recibe_contrato_de_secuencias_roles_y_fotos(self):
        import os
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        import src.mvp_plan as modulo
        cliente=MagicMock()
        p=plan_local('un policía apunta a un criminal')
        cliente.models.generate_content.return_value=SimpleNamespace(text=p.model_dump_json())
        with patch.dict(os.environ,{'GEMINI_API_KEY':'clave-ficticia','GROQ_API_KEY':''}),patch.object(modulo,'load_dotenv'),\
            patch.object(modulo.genai,'Client',return_value=cliente),patch.object(modulo,'_pausas_proveedor',{}):
            resultado=modulo._analizar_sin_cache('un policía apunta a un criminal')
        self.assertTrue(resultado.es_valido)
        llamada=cliente.models.generate_content.call_args.kwargs
        self.assertIn('REPARTO CON ROLES DOCUMENTADOS',llamada['config'].system_instruction)
        self.assertIn('accion=secuencia',llamada['config'].system_instruction)
        self.assertTrue(any(isinstance(c,str) and 'Referencia de personaje:' in c for c in llamada['contents']))
