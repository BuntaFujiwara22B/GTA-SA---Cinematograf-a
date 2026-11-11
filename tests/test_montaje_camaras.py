"""El montaje cambia cámaras sin adelantar/repetir tareas ni perder recursos."""
import configparser
import io
import unittest

from src.mvp_mms import generar_mms, POS_INICIO, POS_DESTINO
from src.montaje_camaras import aplicar_montaje
from src.ubicaciones_escena import rutas_vehiculos, puntos_entrada


def leer(texto):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read_string(texto)
    return cfg


def escribir(cfg):
    salida = io.StringIO()
    cfg.write(salida, space_around_delimiters=False)
    return salida.getvalue()


def temporizadores(cfg):
    return [(i, int(cfg[f'OBJ_{i}']['DIAL_TIME']))
        for i in range(1, int(cfg['MISSION']['SELECTED_OBJ'])+1)
        if cfg[f'OBJ_{i}'].get('Type') == '6']


def disparo(cfg, seccion):
    indice = int(cfg[seccion]['OBJ'])
    return sum(t for i, t in temporizadores(cfg) if i <= indice)


def textos_temporizados(cfg):
    """Une los fragmentos de un mismo subtítulo; conserva su ventana temporal."""
    resultado = []
    reloj = 0
    for i, duracion in temporizadores(cfg):
        texto = cfg[f'OBJ_{i}'].get('TEXT')
        if resultado and resultado[-1][2] == texto:
            resultado[-1] = (resultado[-1][0], reloj+duracion, texto)
        else:
            resultado.append((reloj, reloj+duracion, texto))
        reloj += duracion
    return resultado


class MontajeCamaras(unittest.TestCase):
    def caminar(self, **extra):
        return generar_mms(actor_id=112, inicio=POS_INICIO, destino=POS_DESTINO, **extra)

    def test_sesenta_segundos_son_doce_planos_con_sujeto_cerca_y_sin_repetir_caminar(self):
        original = self.caminar(duracion=60, adaptar_camara=True)
        cfg = leer(aplicar_montaje(original))
        self.assertEqual(cfg['MISSION']['AUTO_CAMERA_SHOTS'], '12')
        self.assertEqual(temporizadores(cfg), [(i, 5000) for i in range(1, 13)])
        camaras = [dict(cfg[f'OBJ_{i}']) for i in range(12)]
        self.assertTrue(all(c['PLA_CUM_MODE'] == '6' and c['CUM_ACTOR'] == '1' for c in camaras))
        perfiles = {(c['PLA_CUM_OX'], c['PLA_CUM_OY'], c['PLA_CUM_OZ']) for c in camaras}
        self.assertEqual(len(perfiles), 3)
        for cam in camaras:
            self.assertLess(abs(float(cam['PLA_CUM_OY'])), 20)
            self.assertLess(float(cam['PLA_CUM_OZ']), 10)
        self.assertNotIn('PLA_CUM', cfg['OBJ_12'])
        self.assertEqual(dict(cfg['ACTION_A_1']), dict(leer(original)['ACTION_A_1']))
        self.assertEqual([s for s in cfg if s.startswith('ACTION_A_')], ['ACTION_A_1'])

    def test_ultimo_plano_corto_no_prolonga_la_escena(self):
        for segundos, tiempos in ((1, [1000]), (5, [5000]), (7, [5000, 2000]), (12, [5000, 5000, 2000])):
            with self.subTest(segundos=segundos):
                cfg = leer(aplicar_montaje(self.caminar(duracion=segundos)))
                self.assertEqual([t for _, t in temporizadores(cfg)], tiempos)
                self.assertEqual(sum(t for _, t in temporizadores(cfg)), segundos*1000)

    def test_los_subtitulos_conservan_su_contenido_y_ventanas_originales(self):
        antes = leer(self.caminar(duracion=23, dialogos=['Un primer diálogo.', 'Ahora seguimos caminando.']))
        despues = leer(aplicar_montaje(escribir(antes)))
        self.assertEqual(textos_temporizados(antes), textos_temporizados(despues))
        self.assertEqual(sum(t for _, t in temporizadores(despues)), 23000)

    def test_remapea_el_objetivo_al_final_del_fragmento_y_no_al_primer_corte(self):
        from src.mvp_plan import plan_local
        p = plan_local('una persona saluda, luego camina y finalmente aplaude durante 30 segundos')
        self.assertTrue(p.es_valido)
        pasos = [s.model_dump() for s in p.pasos]
        for paso, duracion in zip(pasos, (8, 12, 10)):
            paso['duracion'] = duracion
        # La longitud de referencia cabe dentro del tiempo del paso caminar.
        fin = (POS_INICIO[0], POS_INICIO[1]-10, POS_INICIO[2])
        antes = leer(generar_mms(actor_id=112, inicio=POS_INICIO, destino=fin,
            accion='secuencia', pasos=pasos, duracion=30))
        despues = leer(aplicar_montaje(escribir(antes)))
        for seccion in antes:
            if seccion.startswith('ACTION_A_'):
                self.assertEqual(disparo(antes, seccion), disparo(despues, seccion), seccion)
                self.assertEqual({k:v for k,v in antes[seccion].items() if k != 'OBJ'},
                    {k:v for k,v in despues[seccion].items() if k != 'OBJ'})
        self.assertEqual(sum(t for _, t in temporizadores(despues)), 30000)
        # Una entidad que aparece a los 8 s debe conservar el instante de aparición.
        antes['Object_1'] = {'OBJ':'1', 'Created':'1', 'Model':'1234'}
        despues = leer(aplicar_montaje(escribir(antes)))
        self.assertEqual(disparo(antes, 'Object_1'), disparo(despues, 'Object_1'))

    def test_conduccion_conserva_espera_real_pausa_y_grabacion(self):
        r = rutas_vehiculos()[0]
        a, b = puntos_entrada(r)
        antes = leer(generar_mms(actor_id=112, inicio=a, destino=b, duracion=60,
            accion='conducir_vehiculo', vehiculo_id=411, ruta_vehiculo_id=r['id'], dialogos=['Vamos.']))
        despues = leer(aplicar_montaje(escribir(antes)))
        self.assertEqual(dict(antes['OBJ_1']), dict(despues['OBJ_1']))
        self.assertEqual(despues['OBJ_2']['DIAL_TIME'], '1000')
        self.assertEqual(despues['ACTION_V_1']['OBJ'], '2')
        self.assertEqual(dict(antes['ACTION_V_1']), dict(despues['ACTION_V_1']))
        self.assertEqual(dict(antes['ACTION_A_1']), dict(despues['ACTION_A_1']))
        self.assertEqual(sum(t for _,t in temporizadores(despues)), 61000)
        self.assertEqual([t for i,t in temporizadores(despues) if i > 2], [5000]*12)
        self.assertEqual(despues['MISSION']['AUTO_CAMERA_SHOTS'], '12')
        self.assertTrue(all(despues[f'OBJ_{i}']['PLA_CUM_MODE'] == '7'
            for i in range(2, 14)))

    def test_autonomo_sin_actores_y_techo_se_anclan_al_vehiculo(self):
        from src.capacidades_escena import candidata_local
        r = rutas_vehiculos()[0]
        a,b = puntos_entrada(r)
        for accion in ('vehiculo_autonomo', 'animacion_sobre_vehiculo'):
            with self.subTest(accion=accion):
                extras = {} if accion == 'vehiculo_autonomo' else dict(
                    animacion_sugerida=candidata_local('fumar')[1]['id'], vehiculo_en_movimiento=True)
                antes = leer(generar_mms(actor_id=112, inicio=a,destino=b, duracion=12,
                    accion=accion,vehiculo_id=426,ruta_vehiculo_id=r['id'],**extras))
                despues = leer(aplicar_montaje(escribir(antes)))
                self.assertEqual(despues['OBJ_0']['PLA_CUM_MODE'], '7')
                self.assertEqual(despues['OBJ_0']['CUM_VEH'], '1')
                for nombre in antes:
                    if nombre.startswith(('ACTION_A_', 'ACTION_V_')):
                        self.assertEqual(disparo(antes,nombre),disparo(despues,nombre))
                        self.assertEqual({k:v for k,v in antes[nombre].items() if k!='OBJ'},
                            {k:v for k,v in despues[nombre].items() if k!='OBJ'})

    def test_musica_permanece_solo_en_obj_cero_y_aplicacion_es_idempotente(self):
        cfg=leer(self.caminar(duracion=12))
        musica={'GAME_MUSIC':'tema.mp3','MUSIC_START':'1','MUSIC_PROGRESS':'0',
            'MUSIC_SPEED':'1','MUSIC_LOOP':'1','MUSIC_SHA256':'a'*64}
        cfg['OBJ_0'].update(musica)
        resultado=aplicar_montaje(escribir(cfg))
        despues=leer(resultado)
        self.assertEqual({k:despues['OBJ_0'][k] for k in musica},musica)
        self.assertFalse(any(k=='GAME_MUSIC' or k.startswith('MUSIC_') for n in despues
            if re_obj(n) and n!='OBJ_0' for k in despues[n]))
        self.assertEqual(aplicar_montaje(resultado),resultado)
        self.assertNotIn('\n',resultado.replace('\r\n',''))

    def test_rechaza_intervalos_y_referencias_que_no_puede_remapear(self):
        texto=self.caminar(duracion=10)
        for intervalo in (0,-1,True,1.5,999,60001):
            with self.assertRaises(ValueError): aplicar_montaje(texto,intervalo)
        cfg=leer(texto);cfg['ACTION_A_1']['OBJ']='999'
        with self.assertRaisesRegex(ValueError,'inexistente'):aplicar_montaje(escribir(cfg))


def re_obj(nombre):
    return nombre.startswith('OBJ_')


if __name__=='__main__':unittest.main()
