import unittest
from src.vista_mapa import VistaMapa


class ZoomMapa(unittest.TestCase):
    def test_zoom_conserva_punto_bajo_cursor(self):
        v=VistaMapa(500)
        punto=v.a_mapa(130,370)
        v.zoom(4,130,370)
        self.assertEqual(v.a_mapa(130,370),punto)
        v.mover(-50,20)
        punto=v.a_mapa(240,220)
        v.zoom(1.2,240,220)
        self.assertAlmostEqual(v.a_mapa(240,220)[0],punto[0])
        self.assertAlmostEqual(v.a_mapa(240,220)[1],punto[1])

    def test_limites_y_coordenadas_tras_zoom(self):
        v=VistaMapa(500)
        v.zoom(50,250,250)
        self.assertEqual(v.escala,12)
        self.assertEqual(v.a_pantalla(*v.a_mapa(80,90)),(80,90))
        v.mover(-10000,10000)
        self.assertEqual((v.x,v.y),(-5500,0))
        v.zoom(.001,250,250)
        self.assertEqual((v.escala,v.x,v.y),(1,0,0))
