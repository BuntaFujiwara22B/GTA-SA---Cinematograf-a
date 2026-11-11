import configparser
import hashlib
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import src.banda_sonora as musica
import src.mvp_mms as mms
from src.cinematica_aleatoria import crear_escena_aleatoria


class MusicaRandom(unittest.TestCase):
    def test_musica_no_se_reinicia_con_cada_dialogo_y_se_copia(self):
        with tempfile.TemporaryDirectory() as t,patch.object(musica,'RAIZ',Path(t)/'music'),patch.object(mms,'ROOT',Path(t)):
            archivo=musica.RAIZ/'feliz/Una canción.mp3';archivo.parent.mkdir(parents=True)
            archivo.write_bytes(b'audio de prueba')
            actores=Path(t)/'assets/actors';actores.mkdir(parents=True);(actores/'112.png').touch()
            ruta=mms.exportar_escena(actor_id=112,inicio=mms.POS_INICIO,destino=mms.POS_DESTINO,
                banda_sonora='feliz/Una canción.mp3',dialogos=['Hola','Adios'])
            c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.read(ruta,encoding='utf-8')
            self.assertEqual(c['OBJ_0']['MUSIC_SPEED'],'1')
            self.assertEqual(c['OBJ_0']['MUSIC_LOOP'],'1')
            self.assertEqual(c['OBJ_0']['MUSIC_SHA256'],hashlib.sha256(archivo.read_bytes()).hexdigest())
            self.assertNotIn('GAME_MUSIC',c['OBJ_1'])
            self.assertNotIn('GAME_MUSIC',c['OBJ_2'])
            self.assertEqual((ruta.parent/'Sounds'/c['OBJ_0']['GAME_MUSIC']).read_bytes(),archivo.read_bytes())
            self.assertEqual(musica.pistas('feliz'),['feliz/Una canción.mp3'])
            with self.assertRaises(ValueError):musica.resolver('../ajeno.mp3')

    def test_random_siempre_generable_sin_api(self):
        from src.escenas_semanticas import validar_pasos
        for semilla in range(40):
            escena=crear_escena_aleatoria([112,0,11,38],random.Random(semilla))
            p=escena['plan']
            self.assertTrue(p.es_valido)
            self.assertEqual(p.cantidad_actores,len(escena['actores']))
            self.assertIn(p.accion,('secuencia','conducir_vehiculo'))
            if p.accion=='secuencia':
                self.assertGreaterEqual(len(p.pasos),2)
                validar_pasos(p.pasos,p.cantidad_actores,p.duracion_sugerida)
            else:
                self.assertEqual(p.cantidad_actores,1)
                self.assertIsNotNone(p.ruta_vehiculo_id)
                self.assertIsNotNone(p.vehiculo_id_sugerido)
            self.assertEqual(len(escena['actores']),len(set(escena['actores'])))
