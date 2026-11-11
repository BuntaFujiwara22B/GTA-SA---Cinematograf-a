"""Audio global de Mission Maker: contrato del mod y contenido que se entrega."""
import configparser
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import wave
import zipfile
from unittest.mock import patch

from src import banda_sonora as musica
from src import mvp_mms as mms
from src.paquete_mision import guardar_como, zip_mision


def audio_wav(muestras=bytes(800)):
    salida=io.BytesIO()
    with wave.open(salida,'wb') as archivo:
        archivo.setnchannels(1);archivo.setsampwidth(1);archivo.setframerate(8000)
        archivo.writeframes(muestras)
    return salida.getvalue()


class AudioMision(unittest.TestCase):
    def test_audio_global_arranca_con_fundido_y_se_entrega_con_su_nombre_exacto(self):
        with tempfile.TemporaryDirectory() as temporal,\
                patch.object(musica,'RAIZ',Path(temporal)/'music'),\
                patch.object(mms,'ROOT',Path(temporal)/'proyecto'):
            pista=musica.RAIZ/'feliz/Música al atardecer.wav'
            pista.parent.mkdir(parents=True);datos=audio_wav();pista.write_bytes(datos)
            actores=mms.ROOT/'assets/actors';actores.mkdir(parents=True);(actores/'112.png').touch()
            origen=mms.exportar_escena(actor_id=112,inicio=mms.POS_INICIO,destino=mms.POS_DESTINO,
                banda_sonora='feliz/'+pista.name,dialogos=['Primer diálogo','Segundo diálogo'])
            cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str
            cfg.read(origen,encoding='utf-8-sig')
            global_=cfg['OBJ_0']
            # GameSet.txt busca GAME_MUSIC en Sounds y usa estos campos para el stream global.
            self.assertEqual(global_['MUSIC_START'],'1')
            self.assertEqual(global_['MUSIC_PROGRESS'],'0')
            self.assertEqual(global_['MUSIC_SPEED'],'1')
            self.assertEqual(global_['MUSIC_LOOP'],'1')
            self.assertEqual(global_['MUSIC_SHA256'],hashlib.sha256(datos).hexdigest())
            self.assertTrue(global_['GAME_MUSIC'].isascii())
            self.assertEqual(sum('GAME_MUSIC' in cfg[s] for s in cfg.sections()),1)
            self.assertFalse(any('MUSIC_END' in cfg[s] for s in cfg.sections()))
            destino=Path(temporal)/'instalada/carro.mms'
            guardar_como(origen,destino)
            self.assertEqual((destino.parent/'Sounds'/global_['GAME_MUSIC']).read_bytes(),datos)
            with zipfile.ZipFile(io.BytesIO(zip_mision(origen))) as paquete:
                self.assertEqual(paquete.read('Sounds/'+global_['GAME_MUSIC']),datos)
            self.assertEqual(pista.read_bytes(),datos)

    def test_cambiar_contenido_de_una_cancion_no_reutiliza_el_nombre_anterior(self):
        with tempfile.TemporaryDirectory() as temporal,patch.object(musica,'RAIZ',Path(temporal)/'music'):
            pista=musica.RAIZ/'feliz/cancion.wav';pista.parent.mkdir(parents=True)
            primera=audio_wav(bytes(80));pista.write_bytes(primera)
            original=musica.copiar_pista('feliz/cancion.wav',Path(temporal)/'mision')
            segunda=audio_wav(bytes([128])*80);pista.write_bytes(segunda)
            nueva=musica.copiar_pista('feliz/cancion.wav',Path(temporal)/'mision')
            self.assertNotEqual(original.name,nueva.name)
            self.assertEqual(original.read_bytes(),primera)
            self.assertEqual(nueva.read_bytes(),segunda)

    def test_copia_diferente_no_se_sobrescribe_silenciosamente(self):
        with tempfile.TemporaryDirectory() as temporal,patch.object(musica,'RAIZ',Path(temporal)/'music'):
            pista=musica.RAIZ/'feliz/cancion.wav';pista.parent.mkdir(parents=True)
            pista.write_bytes(audio_wav())
            _,nombre=musica.resolver('feliz/cancion.wav')
            destino=Path(temporal)/'mision/Sounds'/nombre
            destino.parent.mkdir(parents=True);destino.write_bytes(b'otra grabacion o copia incompleta')
            with self.assertRaisesRegex(ValueError,'copia de audio diferente'):
                musica.copiar_pista('feliz/cancion.wav',destino.parent.parent)
            self.assertEqual(destino.read_bytes(),b'otra grabacion o copia incompleta')

    def test_cancion_vacia_no_se_anuncia_como_audio_disponible_para_exportacion(self):
        with tempfile.TemporaryDirectory() as temporal,patch.object(musica,'RAIZ',Path(temporal)/'music'):
            pista=musica.RAIZ/'feliz/vacia.mp3';pista.parent.mkdir(parents=True);pista.touch()
            with self.assertRaisesRegex(ValueError,'vacía'):
                musica.configuracion_musica('feliz/vacia.mp3')
            with self.assertRaisesRegex(ValueError,'vacía'):
                musica.copiar_pista('feliz/vacia.mp3',Path(temporal)/'mision')
            self.assertFalse((Path(temporal)/'mision/Sounds').exists())


if __name__=='__main__':unittest.main()
