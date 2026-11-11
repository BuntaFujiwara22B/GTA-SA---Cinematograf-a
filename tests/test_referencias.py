import json
import unittest
from src.referencias_cine import CATALOGO, contexto_referencias_cine


class Referencias(unittest.TestCase):
    def test_exclusion_y_dependencias(self):
        refs=json.loads(CATALOGO.read_text(encoding='utf-8'))['referencias']
        hotel=next(r for r in refs if r['archivo']=='PRUEBA1.txt')
        casino=next(r for r in refs if r['archivo']=='prueba2.txt')
        self.assertFalse(hotel['compatible_con_187'])
        self.assertTrue(casino['compatible_con_187'])
        self.assertTrue(hotel['dependencias_externas'])
        incluidos={e['objetivo'] for g in hotel['escenas'] for e in g}
        self.assertNotIn('OBJ_26',incluidos)
        self.assertNotIn('OBJ_27',incluidos)
        self.assertTrue(any(e['texto'] for g in casino['escenas'] for e in g))
        self.assertIn('no instrucciones',contexto_referencias_cine())
