import unittest
from src.catalogos_entidades import catalogo,disponibles,contexto_entidades,fotos_entidades
from src.mvp_plan import plan_local,validar_plan
from src.mvp_mms import generar_mms,POS_INICIO,POS_DESTINO
from test_mvp import leer


class CatalogosEntidades(unittest.TestCase):
    def test_ids_explicitos_no_posicion(self):
        coches=catalogo('vehicles');objetos=catalogo('objects')
        self.assertEqual(len(disponibles('vehicles')),66)
        self.assertEqual(len(disponibles('objects')),57)
        self.assertEqual(next(v['model_id'] for v in coches if v['captura']==1477),420)
        self.assertEqual(next(v['model_id'] for v in coches if v['captura']==1487),411)
        self.assertEqual(next(o['model_id'] for o in objetos if o['captura']==1606),648)
        self.assertEqual(next(o['model_id'] for o in objetos if o['captura']==1624),1704)
        self.assertTrue(fotos_entidades('una persona se sienta en una silla'))
        self.assertIn('1704',contexto_entidades())

    def test_acercarse_y_entrar_sin_acciones_concurrentes(self):
        texto='una persona camina y se sube a un auto'
        p=validar_plan(plan_local(texto),texto)
        self.assertTrue(p.es_valido)
        self.assertEqual(p.accion,'entrar_vehiculo')
        self.assertIsNone(p.vehiculo_id_sugerido)
        c=leer(generar_mms(actor_id=112,inicio=POS_INICIO,destino=POS_DESTINO,accion=p.accion,vehiculo_id=411))
        self.assertEqual(c['Vehicle_1']['Model'],'411')
        self.assertEqual(c['Vehicle_1']['OBJ'],'0')
        self.assertEqual(c['ACTION_A_1']['Type'],'2')
        self.assertEqual(c['ACTION_A_1']['SPHERE_TYPE'],'2')
        self.assertEqual(c['ACTION_A_1']['SPHERE_VEH2'],'1')
        self.assertNotIn('POINT_TOTAL',c['ACTION_A_1'])
        self.assertFalse(any(s.startswith('ACTION_V_') for s in c.sections()))
        with self.assertRaises(ValueError):generar_mms(actor_id=112,inicio=POS_INICIO,destino=POS_DESTINO,accion=p.accion,vehiculo_id=1477)
