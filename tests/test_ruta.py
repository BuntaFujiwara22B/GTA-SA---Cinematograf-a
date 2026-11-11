import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import src.ruta_colisiones as rutas


class Ruta(unittest.IsolatedAsyncioTestCase):
    async def test_respuesta_correlacionada(self):
        with tempfile.TemporaryDirectory() as t,patch.object(rutas,'CARPETA',Path(t)):
            async def gta():
                while not (Path(t)/'solicitud.txt').exists(): await asyncio.sleep(.01)
                identificador=(Path(t)/'solicitud.txt').read_text().split(',')[0]
                (Path(t)/'respuesta.json').write_text(json.dumps(dict(id=identificador,estado='bloqueada',mensaje='Hay un muro')))
            tarea=asyncio.create_task(gta())
            r=await rutas.comprobar_en_gta((0,0,10),(10,0,10),timeout=1)
            await tarea
            self.assertEqual(r['estado'],'bloqueada')

    async def test_sin_respuesta_nunca_libre(self):
        with tempfile.TemporaryDirectory() as t,patch.object(rutas,'CARPETA',Path(t)):
            (Path(t)/'respuesta.json').write_text('{"id":"viejo","estado":"libre"}')
            r=await rutas.comprobar_en_gta((0,0,10),(10,0,10),timeout=.1)
            self.assertEqual(r['estado'],'sin_comprobar')

    async def test_desnivel_intermedio(self):
        self.assertTrue(rutas.revisar_desniveles((0,0,0),(20,0,0),lambda x,y:10 if 8<x<12 else 0))
        self.assertEqual(rutas.revisar_desniveles((0,0,5),(20,0,5),lambda x,y:5),'')

    async def test_descenso_suave_mayor_de_quince_metros(self):
        altura=lambda x,y:60-x*.35-y*.1
        perfil=rutas.evaluar_perfil((0,0,60),(100,0,25),altura)
        self.assertEqual(perfil['estado'],'apto')
        self.assertGreater(len(perfil['puntos']),2)
        self.assertEqual(rutas.revisar_superficie_elevada((0,0,60),(100,0,25),altura),'')

    async def test_mismos_extremos_no_ocultan_un_corte_intermedio(self):
        p=rutas.evaluar_perfil((0,0,20),(30,0,20),lambda x,y:2 if 10<x<20 else 20)
        self.assertEqual(p['estado'],'bloqueada')

    async def test_puente_real_con_pixel_de_estructura_superior(self):
        from visor_mapa import GestorAlturas
        from src.calles_escena import rutas_disponibles
        r=next(r for r in rutas_disponibles() if r['id']=='ped_puente_ejemplo_usuario')
        g=GestorAlturas();a,b=r['inicio'],r['destino']
        self.assertGreater(g.obtener_z((a[0]+b[0])/2,(a[1]+b[1])/2),60)
        p=rutas.evaluar_perfil(a,b,g.obtener_z)
        self.assertEqual(p['estado'],'incierto')
        self.assertTrue(all(abs(x[2]-33.6)<.01 for x in p['puntos']))
        self.assertEqual(rutas.sugerir_ruta('ciudad',10,g.obtener_z,r['id']),(tuple(a),tuple(b)))

    async def test_palabra_puente_no_omite_comprobacion_de_ruta_arbitraria(self):
        p=rutas.evaluar_perfil((100,0,10),(120,0,10),lambda x,y:80 if 108<x<112 else 10,superficie='puente')
        self.assertEqual(p['estado'],'bloqueada')
        p=rutas.evaluar_perfil((100,0,10),(120,0,25),lambda x,y:10+(x-100)*.75,superficie='puente')
        self.assertEqual(p['estado'],'bloqueada')

    async def test_pendiente_extrema_y_coordenadas_sin_superficie_se_rechazan(self):
        self.assertEqual(rutas.evaluar_perfil((0,0,100),(20,0,10),lambda x,y:100-4.5*x)['estado'],'bloqueada')
        self.assertEqual(rutas.evaluar_perfil((0,0,20),(20,0,20),lambda x,y:0)['estado'],'bloqueada')

    async def test_sugerencia_campo_sin_api(self):
        inicio,destino=rutas.sugerir_ruta('campo',10,lambda x,y:8)
        self.assertEqual(inicio,(-450,-450,8))
        self.assertGreaterEqual(__import__('math').dist(inicio[:2],destino[:2]),2)
        self.assertLessEqual(__import__('math').dist(inicio[:2],destino[:2]),150)

    async def test_no_sugiere_ruta_sobre_agua(self):
        with self.assertRaises(ValueError):
            rutas.sugerir_ruta('campo',10,lambda x,y:0)

    async def test_superficie_tipo_tejado(self):
        altura=lambda x,y:10 if abs(y)<3 else 2
        self.assertIn('tejado',rutas.revisar_superficie_elevada((0,0,10),(12,0,10),altura))
