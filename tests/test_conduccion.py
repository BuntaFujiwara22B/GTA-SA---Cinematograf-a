import io
import math
import random
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import src.mvp_mms as mms
import src.banda_sonora as musica
from src.conduccion import FRAME,grabacion
from src.mvp_plan import plan_local,validar_plan,comprobaciones_peticion
from src.ubicaciones_escena import ubicaciones,rutas_vehiculos,elegir_ubicacion,elegir_ruta_vehiculo,puntos_entrada
from src.paquete_mision import zip_mision,guardar_como,instalar,validar_grabacion
from test_mvp import leer


class Conduccion(unittest.TestCase):
    def test_rechaza_grabacion_de_otra_ubicacion_y_archivo_incompleto(self):
        datos=grabacion([(0,0,1),(0,100,1)],10,30)
        validar_grabacion(datos,(0,0,1))
        with self.assertRaisesRegex(ValueError,'lejos del vehículo'):
            validar_grabacion(datos,(-1626,-1086,102))
        with self.assertRaises(ValueError):validar_grabacion(datos[:-1],(0,0,1))

    def test_interpretar_subir_y_conducir_sin_degradarlo_a_gesto(self):
        for frase in ('una persona se sube a un auto y empieza a manejar',
                      'un personaje camina hasta un coche y después conduce',
                      'un personaje conduce un carro'):
            p=validar_plan(plan_local(frase),frase)
            self.assertTrue(p.es_valido,frase)
            self.assertEqual(p.accion,'conducir_vehiculo')
            self.assertEqual(comprobaciones_peticion(frase),[True]*4)
        self.assertFalse(plan_local('dos personas se suben y manejan un auto').es_valido)
        self.assertFalse(plan_local('una persona conduce un auto a 200 km/h').es_valido)
        self.assertFalse(plan_local('una persona baila y luego conduce un coche').es_valido)
        self.assertEqual(plan_local('una persona se sube a un coche sin conducir').accion,'entrar_vehiculo')

    def test_ubicaciones_variadas_por_entorno_y_region(self):
        self.assertGreaterEqual(len(ubicaciones()),100)
        self.assertEqual(len({p['id'] for p in ubicaciones()}),len(ubicaciones()))
        for entorno in ('ciudad','campo','playa','desierto'):
            lugares={elegir_ubicacion(entorno,rng=random.Random(i))['id'] for i in range(30)}
            self.assertGreater(len(lugares),10)
        self.assertEqual(elegir_ubicacion('ciudad','San Fierro')['zona'],'San Fierro')
        self.assertEqual(elegir_ruta_vehiculo('Las Venturas')['zona'],'Las Venturas')

    def test_espera_real_y_camara_coche_sin_rutas_simultaneas(self):
        r=rutas_vehiculos()[0];a,b=puntos_entrada(r)
        c=leer(mms.generar_mms(actor_id=112,inicio=a,destino=b,accion='conducir_vehiculo',vehiculo_id=411,
            ruta_vehiculo_id=r['id'],duracion=20,dialogos=['Hola','Vamos'],adaptar_camara=True,camara='giro_frontal'))
        self.assertEqual(c['ACTION_A_1']['SPHERE_TYPE'],'2')
        self.assertEqual(c['ACTION_A_1']['OBJ'],'0')
        self.assertEqual(c['ACTION_V_1']['OBJ'],'2')
        self.assertEqual(c['OBJ_1']['Type'],'2')
        self.assertEqual(c['OBJ_1']['SPHERE_TYPE'],'5')
        self.assertNotIn('DIAL_TIME',c['OBJ_1'])
        self.assertEqual(c['OBJ_1']['PLA_CUM_MODE'],'7')
        self.assertEqual(c['OBJ_1']['CUM_VEH'],'1')
        self.assertEqual(c['OBJ_2']['DIAL_TIME'],'1000')
        self.assertEqual(c['OBJ_2']['PLA_CUM_MODE'],'7')
        self.assertNotIn('PLA_CUM',c['OBJ_3'])
        self.assertEqual([c[s]['TEXT'] for s in ('OBJ_3','OBJ_4')],['Hola','Vamos'])
        self.assertEqual(sum(int(c[s]['DIAL_TIME']) for s in ('OBJ_3','OBJ_4')),20000)
        self.assertEqual(tuple(float(c['Vehicle_1'][k]) for k in ('X','Y','Z')),tuple(r['puntos'][0]))

    def test_camaras_y_final_carrec_corresponden_al_ejemplo(self):
        r=rutas_vehiculos()[0];a,b=puntos_entrada(r)
        for tipo,offsets,zoom in [('vehiculo_pov',(-.0399999,-.840001,.52),112),('fija',(0,-5.92,2.04),70),('costado',(0,-5.92,2.04),70)]:
            c=leer(mms.generar_mms(actor_id=112,inicio=a,destino=b,accion='conducir_vehiculo',vehiculo_id=411,
                ruta_vehiculo_id=r['id'],camara=tipo,duracion=10,velocidad_kmh=30,adaptar_camara=True))
            for clave,valor in zip(('PLA_CUM_OX','PLA_CUM_OY','PLA_CUM_OZ'),offsets):
                self.assertAlmostEqual(float(c['OBJ_2'][clave]),valor)
            self.assertEqual(c['OBJ_2']['CUM_VEH'],'1')
            self.assertEqual(int(c['OBJ_2']['PLA_CUM_ZOOM']),zoom)
            datos=grabacion(r['puntos'],10,30)
            final=FRAME.unpack_from(datos,len(datos)-32)[-3:]
            for clave,valor in zip(('CARR_X','CARR_Y','CARR_Z'),final):
                self.assertAlmostEqual(float(c['ACTION_V_1'][clave]),valor)

    def test_velocidad_modifica_recorrido_y_no_todo_va_al_maximo(self):
        puntos=[(0,0,1),(0,100,1),(0,250,1)]
        lento=grabacion(puntos,20,20);rapido=grabacion(puntos,20,60)
        self.assertEqual(FRAME.size,32)
        self.assertEqual(len(lento),201*32)
        self.assertLess(FRAME.unpack_from(lento,len(lento)-32)[-2],FRAME.unpack_from(rapido,len(rapido)-32)[-2])
        for datos,maximo in ((lento,20),(rapido,60)):
            anteriores=None
            for offset in range(0,len(datos),32):
                frame=FRAME.unpack_from(datos,offset)
                self.assertLessEqual(math.sqrt(sum((v/16383.5*50*3.6)**2 for v in frame[1:4])),maximo+.05)
                if anteriores is not None:self.assertGreater(frame[0],anteriores)
                anteriores=frame[0]
            self.assertEqual(FRAME.unpack_from(datos,len(datos)-32)[1:4],(0,0,0))

    def test_paquete_transportable_musica_y_carrec_e_instalacion_aislada(self):
        r=rutas_vehiculos()[0];a,b=puntos_entrada(r)
        with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)/'proyecto'),patch.object(musica,'RAIZ',Path(t)/'music'):
            actores=mms.ROOT/'assets/actors';actores.mkdir(parents=True);(actores/'112.png').touch()
            audio=musica.RAIZ/'mistica/canción larga de prueba.mp3';audio.parent.mkdir(parents=True);audio.write_bytes(b'audio')
            ruta=mms.exportar_escena(actor_id=112,inicio=a,destino=b,accion='conducir_vehiculo',vehiculo_id=411,
                ruta_vehiculo_id=r['id'],velocidad_kmh=25,banda_sonora='mistica/'+audio.name)
            with zipfile.ZipFile(io.BytesIO(zip_mision(ruta))) as z:
                self.assertIn('mission_pack.ini',z.namelist())
                self.assertEqual(len([p for p in z.namelist() if p.startswith('Carrec/')]),1)
                self.assertEqual(len([p for p in z.namelist() if p.startswith('Sounds/')]),1)
            destino=Path(t)/'copia/escena.mms';guardar_como(ruta,destino)
            self.assertTrue((destino.parent/'Carrec').is_dir())
            gta=Path(t)/'gta';(gta/'modloader/SAMM(Stable)').mkdir(parents=True);(gta/'gta.exe').touch()
            instalada=instalar(ruta,gta)
            self.assertTrue((instalada/'mission_pack.ini').is_file())
            with self.assertRaises(ValueError):instalar(ruta,gta)

    def test_giro_frontal_es_corto_y_dirigido_al_actor(self):
        c=leer(mms.generar_mms(actor_id=112,inicio=mms.POS_INICIO,destino=None,accion='animacion',
            animacion_sugerida='DANCE:3:DANCING:dance_loop',camara='giro_frontal',duracion=20))
        self.assertEqual(c['OBJ_1']['PLA_CUM_MODE'],'1')
        self.assertLessEqual(int(c['OBJ_1']['PLA_CUM_TIME_MS']),4000)
        self.assertNotEqual(c['OBJ_0']['PLA_CUM_X'],c['OBJ_1']['PLA_CUM_X'])
        self.assertEqual(c['OBJ_0']['PLA_CUM_PX'],c['OBJ_1']['PLA_CUM_PX'])
