import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.datos_cache import leer_json
from tools.limpiar_duplicados import limpiar


class Portabilidad(unittest.TestCase):
    def test_datos_separados_de_recursos_instalados(self):
        archivo=Path(__file__).resolve().parents[1]/'src/paths.py'
        with tempfile.TemporaryDirectory() as t,patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',str(Path(t)/'paquete'),create=True),patch.object(sys,'executable',str(Path(t)/'Programa/app.exe')),patch.dict(os.environ,{'LOCALAPPDATA':str(Path(t)/'usuario')}):
            spec=importlib.util.spec_from_file_location('rutas_congeladas',archivo)
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
            self.assertEqual(mod.ASSETS,Path(t)/'paquete/assets')
            self.assertEqual(mod.DATA_ROOT,Path(t)/'usuario/MMS-Director')
            self.assertNotEqual(mod.ENV_FILE.parent,mod.RESOURCE_ROOT)

    def test_cache_se_invalida_con_cambios(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'datos.json';p.write_text('{"v":1}')
            self.assertEqual(leer_json(p)['v'],1)
            p.write_text('{"v":222}')
            self.assertEqual(leer_json(p)['v'],222)

    def test_limpieza_solo_borra_duplicados_exactos(self):
        with tempfile.TemporaryDirectory() as t:
            raiz=Path(t)
            for carpeta in ('objects','Objetos'):(raiz/'assets'/carpeta).mkdir(parents=True)
            (raiz/'assets/objects/mesa.png').write_bytes(b'original')
            copia=raiz/'assets/Objetos/captura.png';copia.write_bytes(b'original')
            unica=raiz/'assets/Objetos/unica.png';unica.write_bytes(b'unica')
            self.assertEqual(len(limpiar(raiz)),1)
            self.assertTrue(copia.exists())
            limpiar(raiz,True)
            self.assertFalse(copia.exists())
            self.assertTrue(unica.exists())
