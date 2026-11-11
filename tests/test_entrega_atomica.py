"""Entrega completa y reversible de MMS, música y CARREC; sin escribir en GTA real."""
from contextlib import ExitStack
import configparser
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import src.banda_sonora as musica
import src.mvp_mms as mms
import src.paquete_mision as paquetes
from src.ubicaciones_escena import puntos_entrada, rutas_vehiculos


def leer(ruta):
    cfg=configparser.ConfigParser(interpolation=None)
    cfg.optionxform=str
    cfg.read(ruta,encoding='utf-8-sig')
    return cfg


def escribir(ruta,cfg):
    salida=io.StringIO();cfg.write(salida,space_around_delimiters=False)
    Path(ruta).write_text(salida.getvalue(),encoding='utf-8')


class EntregaAtomica(unittest.TestCase):
    def setUp(self):
        self.temporal=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz=Path(self.temporal.name)
        self.pila=ExitStack()
        self.addCleanup(self.pila.close)
        self.proyecto=self.raiz/'proyecto'
        self.pila.enter_context(patch.object(mms,'ROOT',self.proyecto))
        self.pila.enter_context(patch.object(musica,'RAIZ',self.raiz/'music'))
        actores=self.proyecto/'assets/actors';actores.mkdir(parents=True)
        (actores/'112.png').touch()
        audio=musica.RAIZ/'feliz/tema.wav';audio.parent.mkdir(parents=True)
        with wave.open(str(audio),'wb') as sonido:
            sonido.setnchannels(1);sonido.setsampwidth(2);sonido.setframerate(8000)
            sonido.writeframes(b'\x00\x00'*800)
        ruta=rutas_vehiculos()[0];inicio,destino=puntos_entrada(ruta)
        self.mision=mms.exportar_escena(actor_id=112,inicio=inicio,destino=destino,
            accion='conducir_vehiculo',vehiculo_id=489,ruta_vehiculo_id=ruta['id'],
            duracion=10,velocidad_kmh=30,banda_sonora='feliz/tema.wav')
        self.archivos=paquetes.dependencias(self.mision)
        self.config=leer(self.mision)
        self.carrec_rel=next(n for n in self.archivos if n.startswith('Carrec/'))
        self.audio_rel=next(n for n in self.archivos if n.startswith('Sounds/'))
        self.destino=self.raiz/'gta/modloader/SAMM(Stable)/movimiento/carro.mms'

    def preparar_anterior(self):
        self.destino.parent.mkdir(parents=True)
        original=b'[MISSION]\nNAME=Escena previa del usuario\n'
        manifiesto=b'[MISSION]\nCurrent=previa\nVersion=1.87\nOwner=Usuario original\nCustom=conservar\n\n[EXTRA]\nOtra=si\n'
        self.destino.write_bytes(original)
        (self.destino.parent/'mission_pack.ini').write_bytes(manifiesto)
        return original,manifiesto

    def test_referencia_nueva_sin_archivo_impide_entregar_mms_y_auxiliares(self):
        for tipo in ('carrec','musica'):
            with self.subTest(tipo=tipo):
                cfg=leer(self.mision)
                if tipo=='carrec':cfg['ACTION_V_1']['Carrec']='999999'
                else:cfg['OBJ_0']['GAME_MUSIC']='cancion_ausente.wav'
                fuente=self.mision.with_name('incompleta_'+tipo+'.mms')
                escribir(fuente,cfg)
                destino=self.raiz/tipo/'carro.mms'
                with self.assertRaisesRegex(ValueError,'Falta un archivo'):
                    paquetes.guardar_como(fuente,destino)
                self.assertFalse(destino.exists())
                self.assertFalse((destino.parent/self.carrec_rel).exists())
                self.assertFalse((destino.parent/self.audio_rel).exists())

    def test_guardar_entrega_mms_audio_carrec_y_selecciona_nombre_elegido(self):
        paquetes.guardar_como(self.mision,self.destino)
        entregados=paquetes.dependencias(self.destino)
        self.assertEqual(set(entregados),{'carro.mms',self.carrec_rel,self.audio_rel})
        self.assertEqual(self.destino.read_bytes(),self.mision.read_bytes())
        for relativa in (self.carrec_rel,self.audio_rel):
            self.assertEqual(hashlib.sha256(entregados[relativa].read_bytes()).digest(),
                             hashlib.sha256(self.archivos[relativa].read_bytes()).digest())
        manifiesto=leer(self.destino.parent/'mission_pack.ini')
        self.assertEqual(manifiesto['MISSION']['Current'],'carro')
        self.assertEqual(manifiesto['MISSION']['Version'],'1.87')

    def test_reemplazo_respalda_bytes_previos_y_conserva_datos_del_paquete(self):
        anterior,manifiesto=self.preparar_anterior()
        paquetes.guardar_como(self.mision,self.destino)
        respaldos=list(self.destino.parent.glob('carro.mms.*.bak'))
        self.assertEqual(len(respaldos),1)
        self.assertEqual(respaldos[0].read_bytes(),anterior)
        respaldo_manifiesto=list(self.destino.parent.glob('mission_pack.ini.*.bak'))
        self.assertEqual(len(respaldo_manifiesto),1)
        self.assertEqual(respaldo_manifiesto[0].read_bytes(),manifiesto)
        actual=leer(self.destino.parent/'mission_pack.ini')
        self.assertEqual(actual['MISSION']['Current'],'carro')
        self.assertEqual(actual['MISSION']['Owner'],'Usuario original')
        self.assertEqual(actual['MISSION']['Custom'],'conservar')
        self.assertEqual(actual['EXTRA']['Otra'],'si')

    def test_fallo_al_publicar_mms_revierte_auxiliares_y_conserva_mision_previa(self):
        anterior,manifiesto=self.preparar_anterior()
        escribir_original=paquetes._escribir_atomico
        intentados=[]
        def fallar_mms(destino,datos):
            destino=Path(destino);intentados.append(destino)
            if destino==self.destino:
                raise OSError('Fallo de disco al publicar MMS')
            escribir_original(destino,datos)
        with patch.object(paquetes,'_escribir_atomico',side_effect=fallar_mms):
            with self.assertRaisesRegex(OSError,'Fallo de disco'):
                paquetes.guardar_como(self.mision,self.destino)
        self.assertIn(self.destino.parent/self.carrec_rel,intentados)
        self.assertIn(self.destino.parent/self.audio_rel,intentados)
        self.assertLess(intentados.index(self.destino.parent/self.carrec_rel),intentados.index(self.destino))
        self.assertLess(intentados.index(self.destino.parent/self.audio_rel),intentados.index(self.destino))
        self.assertEqual(self.destino.read_bytes(),anterior)
        self.assertEqual((self.destino.parent/'mission_pack.ini').read_bytes(),manifiesto)
        self.assertFalse((self.destino.parent/self.carrec_rel).exists())
        self.assertFalse((self.destino.parent/self.audio_rel).exists())

    def test_id_global_en_otro_paquete_bloquea_guardado_e_instalacion(self):
        base=self.destino.parent.parent
        hermano=base/'otra_mision'/self.carrec_rel
        hermano.parent.mkdir(parents=True);hermano.write_bytes(b'grabacion ajena')
        for operacion in ('guardar','instalar'):
            with self.subTest(operacion=operacion):
                if operacion=='guardar':
                    destino=self.destino
                    llamada=lambda:paquetes.guardar_como(self.mision,destino)
                else:
                    gta=self.raiz/'gta';(gta/'gta_sa.exe').touch()
                    destino=base/self.mision.stem/self.mision.name
                    llamada=lambda:paquetes.instalar(self.mision,gta)
                with self.assertRaisesRegex(ValueError,'Otra misión de SAMM'):
                    llamada()
                self.assertFalse(destino.exists())
                self.assertEqual(hermano.read_bytes(),b'grabacion ajena')
                self.assertFalse((destino.parent/self.audio_rel).exists())

    def test_audio_alterado_no_se_entrega_aunque_conserve_nombre(self):
        cfg=leer(self.mision)
        cfg['OBJ_0']['MUSIC_SHA256']=hashlib.sha256(self.archivos[self.audio_rel].read_bytes()).hexdigest()
        escribir(self.mision,cfg)
        self.archivos[self.audio_rel].write_bytes(b'contenido diferente con el mismo nombre')
        with self.assertRaisesRegex(ValueError,'canción no corresponde'):
            paquetes.guardar_como(self.mision,self.destino)
        self.assertFalse(self.destino.exists())
        self.assertFalse(self.destino.parent.exists())


if __name__=='__main__':unittest.main()
