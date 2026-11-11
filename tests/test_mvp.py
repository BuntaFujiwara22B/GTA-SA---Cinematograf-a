import configparser
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.mvp_mms as mms
from src.mvp_plan import plan_local, validar_plan, PlanMVP


def leer(texto):
    c = configparser.ConfigParser(interpolation=None)
    c.optionxform = str
    c.read_string(texto)
    return c


class ExportacionMVP(unittest.TestCase):
    def datos(self, **cambios):
        return dict(actor_id=112, inicio=mms.POS_INICIO, destino=mms.POS_DESTINO,
                    duracion=10, hora=12, clima=0) | cambios

    def test_referencia_caminar_conservada(self):
        c = leer(mms.generar_mms(**self.datos()))
        self.assertEqual(c.sections(), ['MISSION','OBJ_0','ACTOR_1','ACTION_A_1','OBJ_1'])
        self.assertEqual(c['ACTION_A_1']['Type'], '4')
        self.assertEqual(c['ACTION_A_1']['POINT_MODE1'], '1')
        self.assertEqual(c['ACTION_A_1']['LOG1'], 'MMS194')
        self.assertEqual(c['ACTION_A_1']['LOG2'], 'MMS253')
        self.assertAlmostEqual(float(c['OBJ_0']['PLA_CUM_X']), 2873.11)
        self.assertAlmostEqual(float(c['OBJ_0']['PLA_CUM_PY']), -1078.12)
        self.assertAlmostEqual(float(c['ACTION_A_1']['POINT_Z1']), 10.875)
        self.assertEqual(c['MISSION']['SHOW_INTRO'],'0')
        self.assertEqual(c['MISSION']['MPASS'],'~n~')
        self.assertEqual(c['OBJ_0']['HUD_OFF'],'1')
        self.assertEqual(c['OBJ_0']['RADAR_OFF'],'1')
        self.assertEqual(c['OBJ_1']['RADAR_OFF'],'1')
        self.assertEqual(c['OBJ_1']['HUD_OFF'],'1')

    def test_rotacion_traslacion_y_camara(self):
        c = leer(mms.generar_mms(**self.datos(inicio=(100,200,20),destino=(125,200,21),duracion=60,hora=24,clima=9)))
        self.assertAlmostEqual(float(c['ACTOR_1']['A']), 270)
        self.assertEqual(c['OBJ_1']['DIAL_TIME'], '60000')
        self.assertEqual(c['OBJ_0']['GAME_TIME'], '0')
        self.assertEqual(c['OBJ_0']['GAME_WEATHER'], '9')
        self.assertEqual(c['OBJ_1']['GAME_WEATHER'], '9')
        self.assertEqual(c['OBJ_1']['GAME_TIME'], '0')
        self.assertEqual(c['OBJ_1']['WEATHER_FREEZE'], '1')
        self.assertAlmostEqual(float(c['ACTION_A_1']['POINT_Z1']), 22)
        cam = tuple(float(c['OBJ_0'][k]) for k in ('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'))
        target = tuple(float(c['OBJ_0'][k]) for k in ('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ'))
        ax,ay = mms.camara_angulos(cam,target)
        self.assertAlmostEqual(float(c['OBJ_0']['PLA_CUM_inputX']),ax,places=4)
        self.assertAlmostEqual(float(c['OBJ_0']['PLA_CUM_inputY']),ay,places=4)

    def test_clima_20_y_minuto_se_exportan_sin_desplazamiento(self):
        c=leer(mms.generar_mms(**self.datos(hora=0,clima=20,minuto=0)))
        for s in ('OBJ_0','OBJ_1'):
            self.assertEqual(c[s]['GAME_WEATHER'],'20')
            self.assertEqual(c[s]['GAME_TIME'],'0')
        c=leer(mms.generar_mms(**self.datos(hora=4,clima=9,minuto=4)))
        self.assertEqual(c['OBJ_1']['GAME_MTIME'],'4')

    def test_camaras_actor_con_offsets_del_ejemplo(self):
        for tipo,x,y,z in [('seguimiento_trasero',-.08,-2.52,.96),('seguimiento_lateral',5.08,-.720001,0)]:
            with self.subTest(tipo=tipo):
                c=leer(mms.generar_mms(**self.datos(camara=tipo,inicio=(100,200,20),destino=(125,200,20))))
                self.assertEqual(c['OBJ_1']['PLA_CUM_MODE'],'6')
                self.assertEqual(c['OBJ_1']['CUM_ACTOR'],'1')
                for k,v in [('PLA_CUM_OX',x),('PLA_CUM_OY',y),('PLA_CUM_OZ',z)]:
                    self.assertAlmostEqual(float(c['OBJ_1'][k]),v)
                self.assertNotIn('Vehicle_1',c.sections())

    def test_camaras_fijas_corresponden_a_fotos_del_usuario(self):
        for tipo,seccion in [('fija','OBJ_3'),('costado','OBJ_4')]:
            ref=leer((mms.REFERENCIA.parent/'camaras_usuario.mms').read_text(encoding='utf-8'))
            origen=tuple(float(ref['ACTOR_1'][k]) for k in ('X','Y','Z'))
            a=math.radians(float(ref['ACTOR_1']['A']))
            destino=(origen[0]-3*math.sin(a),origen[1]+3*math.cos(a),origen[2])
            c=leer(mms.generar_mms(**self.datos(inicio=origen,destino=destino,camara=tipo)))
            self.assertEqual(c['OBJ_1']['PLA_CUM_MODE'],'3')
            for k in ('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z','PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ'):
                self.assertAlmostEqual(float(c['OBJ_1'][k]),float(ref[seccion][k]),places=5)
            self.assertNotIn('CUM_VEH',c['OBJ_1'])

    def test_reparto_cuatro_y_ubicacion_unica(self):
        p=plan_local('cuatro personajes saludan')
        self.assertTrue(p.es_valido)
        self.assertEqual(p.cantidad_actores,4)
        c=leer(mms.generar_mms(**self.datos(destino=None,accion='animacion',
            animacion_sugerida=p.animacion_sugerida,actores_ids=[112,112,112,112])))
        self.assertTrue(all(f'ACTOR_{n}' in c for n in range(1,5)))
        posiciones=[(c[f'ACTOR_{n}']['X'],c[f'ACTOR_{n}']['Y']) for n in range(1,5)]
        self.assertEqual(len(set(posiciones)),4)
        with self.assertRaises(ValueError):
            mms.generar_mms(**self.datos(actores_ids=[112]*5))

    def test_limites_y_ruta_invalida(self):
        for cambios in [dict(duracion=0),dict(duracion=61),dict(clima=45),dict(actor_id=999999),
            dict(destino=mms.POS_INICIO),dict(inicio=(math.nan,0,0)),dict(destino=(4000,0,0))]:
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                mms.generar_mms(**self.datos(**cambios))

    def test_dialogos_conservan_duracion_y_camara(self):
        c=leer(mms.generar_mms(**self.datos(dialogos=['Vamos por aqui.', 'Ya casi llegamos.'],camara='seguimiento_trasero')))
        self.assertEqual(c['OBJ_1']['TEXT'],'Vamos por aqui.')
        self.assertEqual(c['OBJ_2']['TEXT'],'Ya casi llegamos.')
        self.assertEqual(sum(int(c[s]['DIAL_TIME']) for s in ('OBJ_1','OBJ_2')),10000)
        self.assertEqual(c['OBJ_2']['CUM_ACTOR'],'1')
        self.assertEqual(c['ACTION_A_1']['OBJ'],'0')
        with self.assertRaises(ValueError):
            mms.generar_mms(**self.datos(duracion=1,dialogos=['Una frase demasiado larga para un segundo.']))

    def test_archivo_crlf_sin_inyeccion_ni_sobrescritura(self):
        with tempfile.TemporaryDirectory() as t, patch.object(mms,'ROOT',Path(t)):
            actores=Path(t)/'assets/actors'; actores.mkdir(parents=True)
            (actores/'112.png').touch()
            d=self.datos(titulo='Escena\n[OTRA]\nType=99')
            p1=mms.exportar_escena(**d); p2=mms.exportar_escena(**d)
            self.assertNotEqual(p1,p2)
            raw=p1.read_bytes()
            self.assertIn(b'\r\n',raw)
            self.assertNotIn(b'\n',raw.replace(b'\r\n',b''))
            self.assertEqual(set(leer(raw.decode()).sections()),
                {'MISSION','OBJ_0','OBJ_1','OBJ_2','ACTOR_1','ACTION_A_1'})
            self.assertTrue(p1.with_suffix('.json').is_file())


class PlanificacionMVP(unittest.TestCase):
    def test_saludo_a_otro_exporta_dos_actores(self):
        p=plan_local('un personaje saluda a otro personaje')
        self.assertTrue(p.es_valido)
        self.assertEqual(p.cantidad_actores,2)
        c=leer(mms.generar_mms(actor_id=112,inicio=mms.POS_INICIO,destino=mms.POS_DESTINO,
            accion=p.accion,animacion_sugerida=p.animacion_sugerida,segundo_actor_id=112))
        self.assertEqual(c['ACTION_A_1']['Type'],'3')
        self.assertEqual(c['ACTION_A_1']['SPHERE_ACTOR'],'1')
        self.assertEqual(c['ACTION_A_1']['ANIM'],'wave_loop')
        self.assertEqual(c['ACTION_A_1']['IFP'],'ON_LOOKERS')
        self.assertAlmostEqual(math.dist(tuple(float(c['ACTOR_1'][k]) for k in ('X','Y','Z')),
            tuple(float(c['ACTOR_2'][k]) for k in ('X','Y','Z'))),2,places=5)

    def test_peticion_y_duracion(self):
        p=plan_local('quiero que un personaje camine por una avenida grande durante un minuto')
        self.assertTrue(p.es_valido)
        self.assertEqual(p.duracion_sugerida,60)
        self.assertIsNone(p.actor_id_sugerido)

    def test_no_sustituir_acciones_no_soportadas(self):
        for s in ['cinco personajes caminan', 'un personaje conduce', 'caminar y disparar', 'caminar durante 90 segundos']:
            self.assertFalse(plan_local(s).es_valido,s)
        propuesta=PlanMVP(es_valido=True,resumen='Caminar')
        self.assertFalse(validar_plan(propuesta,'caminar y disparar').es_valido)


if __name__ == '__main__':
    unittest.main()
