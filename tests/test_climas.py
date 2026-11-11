import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import src.climas as climas
from indexar_climas import alinear
import numpy as np


class Climas(unittest.TestCase):
    def test_regresion_foto_rosada_no_es_tormenta_de_arena(self):
        self.assertEqual(climas.preview_clima(21,18)['archivo'],'hora_21/Captura de pantalla (1294).png')
        self.assertEqual(climas.preview_clima(21,19)['archivo'],'hora_21/Captura de pantalla (1295).png')
        self.assertEqual(climas.preview_clima(12,19)['archivo'],'hora_12/Captura de pantalla (890).png')
    def test_saltar_fotos_ausentes_sin_cambiar_ids(self):
        with patch.object(climas,'preview_clima',side_effect=lambda h,c: {'archivo':'foto.png'} if c in (2,20) else None):
            self.assertEqual(climas.clima_con_foto(0,19),20)
            self.assertEqual(climas.clima_con_foto(0,19,-1),2)
            self.assertEqual(climas.clima_con_foto(0,21),2)
        with patch.object(climas,'preview_clima',return_value=None):
            self.assertIsNone(climas.clima_con_foto(0,20))
    def test_ids_niebla_y_soleado(self):
        self.assertEqual(len(climas.NOMBRES),23)
        self.assertIn('Niebla',climas.NOMBRES[9])
        self.assertIn('Soleado',climas.NOMBRES[10])

    def test_no_asignar_foto_sin_verificacion(self):
        with tempfile.TemporaryDirectory() as t,patch.object(climas,'ASSETS',Path(t)):
            (Path(t)/'foto.png').touch()
            p={'hora':15,'clima_id':9,'archivo':'foto.png','verificado':False}
            (Path(t)/'climas_catalogo.json').write_text(json.dumps({'previews':[p]}))
            self.assertIsNone(climas.foto_verificada(15,9))
            p['verificado']=True
            (Path(t)/'climas_catalogo.json').write_text(json.dumps({'previews':[p]}))
            self.assertEqual(climas.foto_verificada(15,9),'foto.png')
            self.assertIsNone(climas.foto_verificada(15,10))

    def test_no_confundir_clima_con_posicion_de_archivo(self):
        with tempfile.TemporaryDirectory() as t,patch.object(climas,'ASSETS',Path(t)):
            (Path(t)/'foto.png').touch()
            p={'hora':0,'clima_id':20,'archivo':'foto.png','verificado':False,
               'asociacion':'estimacion_visual_secuencial','minuto':0}
            (Path(t)/'climas_catalogo.json').write_text(json.dumps({'previews':[p]}))
            self.assertEqual(climas.preview_clima(24,20)['archivo'],'foto.png')
            self.assertIsNone(climas.preview_clima(0,19))
            self.assertIsNone(climas.foto_verificada(0,20))

    def test_alineacion_descarta_extra_y_conserva_hueco(self):
        with patch('indexar_climas.firma_visual',side_effect=lambda x:np.full(15,x)):
            pares=alinear([-.7,0,.3,.6],[0,.3,.6])
            self.assertEqual([pares[i][0] for i in range(3)],[0,.3,.6])
            pares=alinear([0,.6],[0,.3,.6])
            self.assertNotIn(1,pares)
            self.assertEqual(pares[2][0],.6)
