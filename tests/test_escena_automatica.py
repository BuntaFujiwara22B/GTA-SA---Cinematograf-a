import math
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.preparar_calles import leer_nodos,extraer
from src.calles_escena import elegir_calle
from src.ruta_colisiones import sugerir_ruta
from src.mvp_plan import plan_local,validar_plan
from src.mvp_mms import generar_mms,POS_INICIO,POS_DESTINO
from test_mvp import leer


class EscenaAutomatica(unittest.TestCase):
    def test_calles_salen_de_enlaces_peatonales_no_puntos_aislados(self):
        with tempfile.TemporaryDirectory() as t:
            nodos=b''.join(struct.pack('<IIhhhHHHHBBI',0,0,19200+i*160,-11600,184,0,i,0,i,1,1,1) for i in range(2))
            b=struct.pack('<5I',2,0,2,0,2)+nodos+struct.pack('<4H',0,1,0,0)
            (Path(t)/'NODES0.DAT').write_bytes(b)
            puntos,enlaces=leer_nodos(Path(t))
            self.assertEqual(enlaces[0,0],[(0,1)])
            self.assertEqual(puntos[0,1],(2420,-1450,23))
            self.assertEqual(len(extraer(Path(t))['rutas']),1)

    def test_ruta_sugerida_y_altura(self):
        p=plan_local('dos personas caminan por una calle de San Fierro')
        r=elegir_calle('San Fierro',10)
        self.assertEqual(p.ruta_id_sugerida,r['id'])
        with patch('src.calles_escena.rutas_disponibles',return_value=[r]):
            ini,fin=sugerir_ruta('ciudad',10,lambda x,y:r['inicio'][2],r['id'])
            self.assertEqual(ini[:2],tuple(r['inicio'][:2]))
            self.assertEqual(fin[:2],tuple(r['destino'][:2]))
            with self.assertRaises(ValueError):sugerir_ruta('ciudad',10,lambda x,y:500,r['id'])

    def test_conserva_propuesta_de_clima_y_respeta_peticion_explicita(self):
        p=plan_local('dos personas caminan por una calle')
        p.hora_sugerida=22;p.clima_id_sugerido=19
        p=validar_plan(p,'dos personas caminan por una calle')
        self.assertEqual(p.hora_sugerida,22)
        self.assertEqual(p.clima_id_sugerido,19)
        p=plan_local('dos personas caminan por una calle al atardecer')
        self.assertEqual(p.hora_sugerida,18)

    def test_encuadres_varian_sin_cambiar_estilo(self):
        for camara,modo in [('seguimiento_trasero','6'),('costado','3'),('fija','3')]:
            c=leer(generar_mms(actor_id=112,actores_ids=[112]*4,inicio=POS_INICIO,destino=POS_DESTINO,
                camara=camara,adaptar_camara=True))
            self.assertEqual(c['OBJ_1']['PLA_CUM_MODE'],modo)
            self.assertEqual(c['OBJ_0']['PLA_CUM_MODE'],'3')
            objetivo=[float(c['OBJ_1'][k]) for k in ('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ')]
            pos=[float(c['OBJ_1'][k]) for k in ('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z')]
            self.assertTrue(all(math.isfinite(v) for v in objetivo+pos))
            if modo=='6':
                self.assertEqual(float(c['OBJ_1']['PLA_CUM_OY']),-5)
                self.assertEqual(c['OBJ_1']['CUM_ACTOR'],'1')
            elif camara=='fija':self.assertGreater(pos[2]-objetivo[2],4)
