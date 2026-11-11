import configparser
import unittest
from src.mvp_mms import generar_mms
from src.ruta_colisiones import evaluar_perfil
from src.perfil_ruta import validar_perfil


def leer(s):
    c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.read_string(s);return c


class PerfilMMS(unittest.TestCase):
    def test_descenso_exporta_alturas_intermedias_y_final(self):
        a,b=(0,0,50),(100,0,15)
        p=evaluar_perfil(a,b,lambda x,y:50-.35*x)
        c=leer(generar_mms(actor_id=0,inicio=a,destino=b,perfil_recorrido=p['puntos']))
        accion=c['ACTION_A_1'];n=int(accion['POINT_TOTAL'])
        self.assertGreater(n,2)
        self.assertAlmostEqual(float(accion[f'POINT_Z{n}']),16)
        self.assertGreater(float(accion['POINT_Z1']),float(accion[f'POINT_Z{n}']))

    def test_terreno_curvo_no_se_aplana_entre_extremos_iguales(self):
        a,b=(0,0,20),(40,0,20)
        perfil=[(0,0,20),(10,0,24),(20,0,28),(30,0,24),(40,0,20)]
        c=leer(generar_mms(actor_id=0,inicio=a,destino=b,perfil_recorrido=perfil))
        self.assertEqual(c['ACTION_A_1']['POINT_Z2'],'29')

    def test_secuencia_conserva_perfil_y_participantes(self):
        a,b=(0,0,30),(20,0,22)
        perfil=[(0,0,30),(5,0,29),(10,0,27),(15,0,24),(20,0,22)]
        c=leer(generar_mms(actor_id=0,actores_ids=[0,7],inicio=a,destino=b,duracion=30,accion='secuencia',
            perfil_recorrido=perfil,pasos=[dict(accion='caminar',actores=[1,2]),dict(accion='correr',actores=[1,2])]))
        tareas=[c[s] for s in c if s.startswith('ACTION_A_') and c[s]['Type']=='4']
        self.assertEqual(len(tareas),4)
        ultimas=[a for a in tareas if a['OBJ']=='1']
        for tarea in ultimas:self.assertAlmostEqual(float(tarea[f'POINT_Z{tarea["POINT_TOTAL"]}']),23)

    def test_perfil_ajeno_retroceso_pared_y_pendiente_violenta(self):
        a,b=(0,0,20),(20,0,20)
        for perfil in [[a,(25,0,20)], [a,(10,0,20),(8,0,20),b],
            [a,(10,10,20),b], [a,(10,0,100),b]]:
            with self.assertRaises(ValueError):validar_perfil(perfil,a,b)
        with self.assertRaises(ValueError):generar_mms(actor_id=0,inicio=(0,0,20),destino=(10,0,50))
