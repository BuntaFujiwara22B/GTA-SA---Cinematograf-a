"""Recorre peticion -> elecciones -> exportacion con controles Flet reales, sin abrir GTA/API."""
import tempfile
import asyncio
import io
import zipfile
import random
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import flet as ft
import main as app
import src.mvp_mms as mms
from src.mvp_plan import plan_local


class PagePrueba:
    def __init__(self):
        self.window = SimpleNamespace(width=1100,height=900)
        self.width,self.height = 1100,900
        self.controls=[]
        self.services=[]
    def add(self,*controles): self.controls.extend(controles)
    def update(self): pass
    def run_task(self,*args): pass


def recorrer(controles):
    for c in controles:
        if not isinstance(c,ft.Control): continue
        yield c
        contenido=getattr(c,'content',None)
        if isinstance(contenido,ft.Control):
            yield from recorrer([contenido])
        yield from recorrer(getattr(c,'controls',[]) or [])


def evento(controles,nombre):
    return next(c for c in controles if getattr(getattr(c,'on_click',None),'__name__','')==nombre)


@patch.object(ft.Container,'update',lambda self:None)
class FlujoMVP(unittest.IsolatedAsyncioTestCase):
    async def test_fumar_en_techo_movil_y_estacionado_llega_al_mms_y_paquete(self):
        from test_mvp import leer
        from src.paquete_mision import dependencias
        for texto,movil in [('una persona fuma en el techo de un auto de movimiento',True),
            ('una persona fuma en el techo de un auto estacionado',False)]:
            with self.subTest(texto=texto),patch.object(app,'analizar_accion_usuario',side_effect=plan_local):
                page=PagePrueba();await app.main(page)
                controles=list(recorrer(page.controls))
                next(c for c in controles if isinstance(c,ft.TextField)).value=texto
                await evento(controles,'on_analizar').on_click(None)
                vehiculo=next(c for c in controles if isinstance(c,ft.Container) and c.tooltip=='Cambiar vehículo')
                self.assertTrue(vehiculo.visible)
                velocidad=next(c for c in controles if isinstance(c,ft.Slider) and c.min==10 and c.max==90)
                self.assertEqual(velocidad.visible,movil)
                self.assertTrue(any('anclaje pendientes' in str(getattr(c,'value','')) for c in controles))
                with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                    actores=Path(t)/'assets/actors';actores.mkdir(parents=True);(actores/'0.png').touch()
                    await evento(controles,'on_crear_mms').on_click(None)
                    archivos=list((Path(t)/'salida_mms').glob('*.mms'))
                    self.assertEqual(len(archivos),1)
                    c=leer(archivos[0].read_text(encoding='utf-8'))
                    self.assertEqual((c['ACTION_A_1']['Type'],c['ACTION_A_1']['SPHERE_TYPE']),('2','6'))
                    self.assertEqual(c['ACTION_A_2']['ANIM'],'M_smk_drag')
                    self.assertEqual(('ACTION_V_1' in c),movil)
                    self.assertEqual(any(n.startswith('Carrec/') for n in dependencias(archivos[0])),movil)

    async def test_resumen_hover_y_edicion_solo_con_decision_del_usuario(self):
        with patch.object(app,'analizar_accion_usuario',side_effect=plan_local):
            page=PagePrueba();await app.main(page)
            controles=list(recorrer(page.controls))
            next(c for c in controles if isinstance(c,ft.TextField)).value='dos personas se saludan en un puente'
            await evento(controles,'on_analizar').on_click(None)
            slide=next(c for c in controles if isinstance(c,ft.Container) and c.height==4500)
            self.assertEqual(slide.top,-2700)
            page.on_keyboard_event(SimpleNamespace(key='Arrow Up'))
            self.assertEqual(slide.top,-2700)
            tarjeta=next(c for c in controles if isinstance(c,ft.Container) and c.tooltip=='Cambiar clima y hora')
            overlay=tarjeta.content.controls[1].controls[1]
            self.assertEqual(overlay.opacity,.65)
            tarjeta.on_hover(SimpleNamespace(data='true',control=tarjeta));self.assertEqual(overlay.opacity,1)
            tarjeta.on_hover(SimpleNamespace(data='false',control=tarjeta));self.assertEqual(overlay.opacity,.65)
            tarjeta.on_click(None);self.assertEqual(slide.top,-1800)
            page.on_keyboard_event(SimpleNamespace(key='Arrow Up'));self.assertEqual(slide.top,-1800)
            evento(controles,'confirmar_clima').on_click(None);self.assertEqual(slide.top,-2700)
            ubicacion=next(c for c in controles if isinstance(c,ft.Container) and c.tooltip=='Cambiar ubicación')
            ubicacion.on_click(None);self.assertEqual(slide.top,-900)
            confirmar=next(c for c in controles if isinstance(c,ft.TextButton) and c.content=='Confirmar ubicación')
            confirmar.on_click(None);self.assertEqual(slide.top,-2700)
            evento(controles,'editar_camara').on_click(None)
            panel=next(c for c in controles if isinstance(c,ft.Column) and any(isinstance(t,ft.Text) and t.value=='Elige la cámara' for t in c.controls))
            self.assertTrue(panel.visible)
            evento(controles,'confirmar_edicion_camara').on_click(None)
            self.assertFalse(panel.visible);self.assertEqual(slide.top,-2700)
            duracion=next(c for c in controles if isinstance(c,ft.Slider) and c.min==1 and c.max==60)
            duracion.value=25;duracion.on_change(SimpleNamespace(control=duracion))
            self.assertTrue(any(isinstance(c,ft.Text) and c.value=='Duración del plano: 25 segundos' for c in controles))

    async def test_correr_en_puente_exporta_desde_resumen_sin_pixel_de_altura_falso(self):
        from test_mvp import leer
        with patch.object(app,'analizar_accion_usuario',side_effect=plan_local):
            page=PagePrueba();await app.main(page)
            controles=list(recorrer(page.controls))
            next(c for c in controles if isinstance(c,ft.TextField)).value='una persona corre en un puente'
            await evento(controles,'on_analizar').on_click(None)
            with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                actores=Path(t)/'assets/actors';actores.mkdir(parents=True);(actores/'0.png').touch()
                await evento(controles,'on_crear_mms').on_click(None)
                archivos=list((Path(t)/'salida_mms').glob('*.mms'))
                self.assertEqual(len(archivos),1)
                c=leer(archivos[0].read_text(encoding='utf-8'));tarea=c['ACTION_A_1']
                self.assertGreater(int(tarea['POINT_TOTAL']),1)
                self.assertTrue(all(abs(float(tarea[f'POINT_Z{i}'])-34.6)<.01 for i in range(1,int(tarea['POINT_TOTAL'])+1)))
                self.assertTrue(any('mapa 2D' in str(getattr(c,'value','')) for c in controles))

    async def test_cinco_ejemplos_generan_archivo_desde_la_interfaz(self):
        from evaluar_escenas import corpus
        from test_mvp import leer
        for caso in corpus()[:5]:
            with self.subTest(texto=caso['texto']),patch.object(app,'analizar_accion_usuario',side_effect=plan_local):
                page=PagePrueba();await app.main(page)
                controles=list(recorrer(page.controls))
                next(c for c in controles if isinstance(c,ft.TextField)).value=caso['texto']
                await evento(controles,'on_analizar').on_click(None)
                evento(controles,'confirmar_camara').on_click(None)
                with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                    actores=Path(t)/'assets/actors';actores.mkdir(parents=True)
                    for i in (0,7,21,158,161,280):(actores/f'{i}.png').touch()
                    await evento(controles,'on_crear_mms').on_click(None)
                    archivos=list((Path(t)/'salida_mms').glob('*.mms'))
                    avisos=[c.value for c in controles if isinstance(c,ft.Text) and c.value]
                    self.assertEqual(len(archivos),1,str(avisos[-12:]))
                    c=leer(archivos[0].read_text(encoding='utf-8'))
                    if 'puente' in caso['texto']:
                        self.assertAlmostEqual(float(c['ACTOR_1']['X']),-1167.094572,places=4)
                    if 'granjeros' in caso['texto']:
                        self.assertTrue(all(int(c[f'ACTOR_{i}']['Model']) in (158,161) for i in range(1,4)))

    async def test_propuesta_completa_solo_requiere_camara_y_musica(self):
        from test_mvp import leer
        frase='quiero que un personaje camine, se suba a un vehículo y ande por la cuidad'
        p=plan_local(frase)
        p.actor_id_sugerido=112;p.actores_ids_sugeridos=[112];p.vehiculo_id_sugerido=411
        p.hora_sugerida=17;p.clima_id_sugerido=4;p.fuente='Gemini simulada'
        p.motivo_elecciones='Propuesta urbana de la IA.'
        with patch.object(app,'analizar_accion_usuario',return_value=p):
            page=PagePrueba();await app.main(page)
            controles=list(recorrer(page.controls))
            next(c for c in controles if isinstance(c,ft.TextField)).value=frase
            await evento(controles,'on_analizar').on_click(None)
            # No confirma ni elige personajes, vehículo, mapa o clima.
            slide=next(c for c in controles if isinstance(c,ft.Container) and c.height==4500)
            self.assertEqual(slide.top,-2700)
            camara=next(c for c in controles if isinstance(c,ft.Container) and isinstance(getattr(c,'content',None),ft.Column)
                and any(isinstance(v,ft.Text) and v.value=='Exterior fija al coche' for v in c.content.controls))
            camara.on_click(None)
            evento(controles,'confirmar_camara').on_click(None)
            musica=next(c for c in controles if isinstance(c,ft.Dropdown) and c.label=='Banda sonora')
            self.assertEqual(musica.value,'ninguna')
            with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                carpeta=Path(t)/'assets/actors';carpeta.mkdir(parents=True);(carpeta/'112.png').touch()
                await evento(controles,'on_crear_mms').on_click(None)
                ruta=next((Path(t)/'salida_mms').glob('*.mms'))
                c=leer(ruta.read_text(encoding='utf-8'))
                self.assertIn('ACTION_V_1',c)
                self.assertEqual(c['ACTOR_1']['Model'],'112')
                self.assertEqual(c['Vehicle_1']['Model'],'411')
                self.assertEqual(c['OBJ_0']['GAME_WEATHER'],'4')
                self.assertEqual(c['OBJ_0']['GAME_TIME'],'17')
                self.assertNotIn('GAME_MUSIC',c['OBJ_0'])
                destino=Path(t)/'mission';destino.mkdir()
                with patch.object(ft.FilePicker,'save_file',new=AsyncMock(return_value=str(destino/'carro.mms'))) as guardar,patch.object(ft.Clipboard,'set',new=AsyncMock()) as copiar:
                    await evento(controles,'copiar_mms').on_click(None)
                    guardar.assert_awaited_once()
                    self.assertNotIn('src_bytes',guardar.await_args.kwargs)
                    copiar.assert_not_awaited()
                    self.assertTrue((destino/'carro.mms').is_file())
                    self.assertTrue(list((destino/'Carrec').glob('*.rrr')))
                with patch.object(ft.FilePicker,'save_file',new=AsyncMock(return_value=None)),patch.object(ft.Clipboard,'set',new=AsyncMock()) as copiar:
                    await evento(controles,'copiar_mms').on_click(None)
                    copiar.assert_not_awaited()

    async def test_subir_conducir_seleccionar_recorrido_velocidad_y_paquete(self):
        from src.ubicaciones_escena import rutas_vehiculos
        from test_mvp import leer
        with patch.object(app,'analizar_accion_usuario',side_effect=plan_local):
            page=PagePrueba();await app.main(page)
            controles=list(recorrer(page.controls))
            campo=next(c for c in controles if isinstance(c,ft.TextField))
            campo.value='una persona camina hasta un auto y luego lo maneja a 30 km/h'
            await evento(controles,'on_analizar').on_click(None)
            evento(controles,'confirmar_personaje').on_click(None)
            evento(controles,'confirmar_vehiculo').on_click(None)
            selector=next(c for c in controles if isinstance(c,ft.Dropdown) and c.label=='Recorrido del vehículo')
            self.assertTrue(selector.visible)
            selector.value=rutas_vehiculos()[0]['id']
            selector.on_select(SimpleNamespace(control=selector))
            velocidad=next(c for c in controles if isinstance(c,ft.Slider) and c.min==10 and c.max==90)
            self.assertTrue(velocidad.visible);self.assertEqual(velocidad.value,30)
            velocidad.value=25;velocidad.on_change(SimpleNamespace(control=velocidad))
            evento(controles,'confirmar_clima').on_click(None)
            pov=next(c for c in controles if isinstance(c,ft.Container) and isinstance(getattr(c,'content',None),ft.Text)
                and c.content.value=='Desde el asiento del vehículo')
            self.assertTrue(pov.visible)
            pov.on_click(None)
            with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                actores=Path(t)/'assets/actors';actores.mkdir(parents=True);(actores/'0.png').touch()
                with patch.object(app,'exportar_escena',wraps=mms.exportar_escena) as exportar:
                    await evento(controles,'on_crear_mms').on_click(None)
                    self.assertEqual(exportar.call_args.kwargs['velocidad_kmh'],25)
                    self.assertEqual(exportar.call_args.kwargs['ruta_vehiculo_id'],selector.value)
                salida=next((Path(t)/'salida_mms').glob('*.mms'))
                config=leer(salida.read_text(encoding='utf-8'))
                self.assertEqual(config['OBJ_1']['SPHERE_TYPE'],'5')
                self.assertEqual(config['OBJ_1']['PLA_CUM_MODE'],'7')
                self.assertEqual(config['OBJ_2']['PLA_CUM_ZOOM'],'112')
                with patch.object(ft.FilePicker,'save_file',new=AsyncMock(return_value='paquete.zip')) as guardar:
                    await evento(controles,'guardar_paquete_musica').on_click(None)
                    with zipfile.ZipFile(io.BytesIO(guardar.await_args.kwargs['src_bytes'])) as paquete:
                        self.assertTrue(any(s.startswith('Carrec/') for s in paquete.namelist()))

    async def test_pedir_auto_muestra_selector_y_exporta_model_elegido(self):
        with patch.object(app,'analizar_accion_usuario',side_effect=plan_local):
            page=PagePrueba();await app.main(page)
            controles=list(recorrer(page.controls))
            campo=next(c for c in controles if isinstance(c,ft.TextField))
            campo.value='una persona camina y se sube a un auto'
            await evento(controles,'on_analizar').on_click(None)
            evento(controles,'editar_vehiculo').on_click(None)
            panel=next(c for c in controles if isinstance(c,ft.Column) and any(
                getattr(getattr(v,'on_click',None),'__name__','')=='confirmar_vehiculo' for v in c.controls))
            self.assertTrue(panel.visible)
            siguiente=next(c for c in recorrer([panel]) if isinstance(c,ft.IconButton) and c.icon==ft.Icons.CHEVRON_RIGHT)
            siguiente.on_click(None)
            evento(controles,'confirmar_vehiculo').on_click(None)
            evento(controles,'usar_avenida_ejemplo').on_click(None)
            evento(controles,'confirmar_clima').on_click(None)
            with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                p=Path(t)/'assets/actors';p.mkdir(parents=True);(p/'0.png').touch()
                await evento(controles,'on_crear_mms').on_click(None)
                contenido=next((Path(t)/'salida_mms').glob('*.mms')).read_text(encoding='utf-8')
                self.assertIn('Model=421',contenido)
                self.assertIn('[Vehicle_1]',contenido)
                self.assertNotIn('[ACTION_V_',contenido)

    async def test_random_genera_y_ofrece_paquete_con_musica(self):
        import src.banda_sonora as musica
        from src.cinematica_aleatoria import crear_escena_aleatoria
        escena=crear_escena_aleatoria([0,112],random.Random(3))
        with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)),patch.object(musica,'RAIZ',Path(t)/'music'):
            audio=musica.RAIZ/'feliz/tema.mp3';audio.parent.mkdir(parents=True);audio.write_bytes(b'musica de prueba')
            actores=Path(t)/'assets/actors';actores.mkdir(parents=True)
            for i in (0,112):(actores/f'{i}.png').touch()
            page=PagePrueba()
            with patch.object(app,'analizar_accion_usuario',side_effect=plan_local) as ia,patch.object(app,'crear_escena_aleatoria',return_value=escena):
                await app.main(page)
                controles=list(recorrer(page.controls))
                await evento(controles,'on_crear_random').on_click(None)
                ia.assert_not_called()
                self.assertTrue(page.controls[-1].visible)
                with patch.object(ft.FilePicker,'save_file',new=AsyncMock(return_value='paquete.zip')) as guardar:
                    await evento(controles,'guardar_paquete_musica').on_click(None)
                    with zipfile.ZipFile(io.BytesIO(guardar.await_args.kwargs['src_bytes'])) as paquete:
                        self.assertEqual(len([s for s in paquete.namelist() if s.endswith('.mms')]),1)
                        self.assertEqual(len([s for s in paquete.namelist() if s.startswith('Sounds/')]),1)

    async def test_escribir_actualiza_semaforos_sin_consumir_api(self):
        page=PagePrueba()
        with patch.object(app,'analizar_accion_usuario',side_effect=plan_local) as analizar:
            await app.main(page)
            controles=list(recorrer(page.controls))
            campo=next(c for c in controles if isinstance(c,ft.TextField))
            for texto in ['una persona','una persona corre','una persona corre en un puente']:
                campo.value=texto
                await campo.on_change(SimpleNamespace(control=campo))
                await asyncio.sleep(.02)
            await asyncio.sleep(2.2)
            analizar.assert_not_called()
            luces=[c for c in controles if isinstance(c,ft.Container) and c.width==22 and c.height==22]
            self.assertEqual(len(luces),4)
            self.assertTrue(all(c.bgcolor==ft.Colors.GREEN for c in luces))
            await evento(controles,'on_analizar').on_click(None)
            analizar.assert_called_once_with('una persona corre en un puente')

    async def test_peticion_elecciones_y_archivo(self):
        page=PagePrueba()
        with patch.object(app,'analizar_accion_usuario',side_effect=plan_local):
            await app.main(page)
            controles=list(recorrer(page.controls))
            campo=next(c for c in controles if isinstance(c,ft.TextField))
            campo.value='quiero que un personaje camine por una avenida grande durante 20 segundos'
            await evento(controles,'on_analizar').on_click(None)
            self.assertTrue(campo.disabled)
            evento(controles,'confirmar_personaje').on_click(None)
            self.assertTrue(any(isinstance(c,ft.Image) and c.visible and isinstance(c.src,str)
                and (c.src.startswith('hora_12/') or c.src.startswith('ui/hora_12/')) for c in controles))
            crear=evento(controles,'on_crear_mms')
            # La edición manual no depende de un puente con GTA; las alturas
            # y pendientes del recorrido siguen validándose al exportar.
            mapa=next(c for c in controles if getattr(getattr(c,'on_scroll',None),'__name__','')=='zoom_mapa')
            mapa.on_tap_up(SimpleNamespace(local_position=SimpleNamespace(x=200,y=220)))
            evento(controles,'usar_avenida_ejemplo').on_click(None)
            self.assertFalse(any(getattr(getattr(c,'on_click',None),'__name__','')=='al_comprobar_ruta' for c in controles))
            self.assertFalse(any(isinstance(c,ft.Checkbox) for c in controles))
            evento(controles,'confirmar_clima').on_click(None)
            with patch.object(app,'evaluar_perfil',return_value=dict(estado='bloqueada',
                    mensaje='Hay un cambio brusco de altura.',puntos=[])),\
                    patch.object(app,'exportar_escena') as exportar:
                await crear.on_click(None)
                exportar.assert_not_called()
            self.assertTrue(any('cambio brusco de altura' in str(getattr(c,'value','')) for c in controles))
            with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                actores=Path(t)/'assets/actors'; actores.mkdir(parents=True)
                # El carrusel comienza por el ID real 0; el exportador solo necesita validar existencia.
                (actores/'0.png').touch()
                with patch.object(app,'evaluar_perfil',wraps=app.evaluar_perfil) as perfil:
                    await crear.on_click(None)
                    perfil.assert_called_once()
                archivos=list((Path(t)/'salida_mms').glob('*.mms'))
                self.assertEqual(len(archivos),1)
                contenido=archivos[0].read_text(encoding='utf-8')
                from test_mvp import leer
                config=leer(contenido)
                tiempos=[int(config[s]['DIAL_TIME']) for s in config
                    if s.startswith('OBJ_') and config[s].get('Type')=='6']
                self.assertEqual(tiempos,[5000]*4)
                self.assertIn('Type=4',contenido)
                visor=next(c for c in controles if isinstance(c,ft.TextField) and c.read_only)
                self.assertIn('[MISSION]',visor.value)
                self.assertTrue(any(getattr(c,'visible',False) for c in page.controls if c is page.controls[-1]))
                with patch.object(ft.Clipboard,'set',new=AsyncMock()) as copiar:
                    await evento(controles,'copiar_mms').on_click(None)
                    self.assertIn('[MISSION]',copiar.await_args.args[0])
                destino_guardado=Path(t)/'copia/elegido.mms'
                with patch.object(ft.FilePicker,'save_file',new=AsyncMock(return_value=str(destino_guardado))) as guardar:
                    await evento(controles,'guardar_mms_como').on_click(None)
                    self.assertNotIn('src_bytes',guardar.await_args.kwargs)
                    self.assertIn('[MISSION]',destino_guardado.read_text(encoding='utf-8'))
                evento(controles,'volver_edicion').on_click(None)
                self.assertFalse(page.controls[-1].visible)

    async def test_cuatro_personajes_ubicacion_estatica_y_clima(self):
        page=PagePrueba()
        def plan_con_clima(texto):
            p=plan_local(texto)
            p.hora_sugerida=21
            p.clima_id_sugerido=18
            return p
        with patch.object(app,'analizar_accion_usuario',side_effect=plan_con_clima):
            await app.main(page)
            controles=list(recorrer(page.controls))
            campo=next(c for c in controles if isinstance(c,ft.TextField))
            campo.value='cuatro personajes saludan'
            await evento(controles,'on_analizar').on_click(None)
            self.assertTrue(any(isinstance(c,ft.Image) and c.visible and c.src==app.vista_asset('hora_21/Captura de pantalla (1294).png') for c in controles))
            self.assertFalse(any(getattr(getattr(c,'on_click',None),'__name__','')=='al_comprobar_ruta' for c in controles))
            mapa=next(c for c in controles if getattr(getattr(c,'on_scroll',None),'__name__','')=='zoom_mapa')
            tam=mapa.content.width
            punto=SimpleNamespace(x=160,y=200)
            mapa.on_scroll(SimpleNamespace(local_position=punto,scroll_delta=SimpleNamespace(y=-200)))
            fondo=mapa.content.controls[0]
            esperado_x=(punto.x-fondo.left)/fondo.width*6000-3000
            esperado_y=3000-(punto.y-fondo.top)/fondo.height*6000
            mapa.on_tap_up(SimpleNamespace(local_position=punto))
            pin=next(c for c in mapa.content.controls if isinstance(getattr(c,'content',None),ft.Icon) and c.content.icon==ft.Icons.LOCATION_ON)
            self.assertEqual(pin.width,28)
            self.assertAlmostEqual(pin.left,146)
            crear=evento(controles,'on_crear_mms')
            confirmar=evento(controles,'confirmar_personaje')
            siguiente=next(c for c in controles if isinstance(c,ft.IconButton) and c.icon==ft.Icons.CHEVRON_RIGHT)
            slots=next(c for c in controles if isinstance(c,ft.Row) and len(c.controls)==4 and all(getattr(v,'tooltip',None)==f'Personaje {i+1}' for i,v in enumerate(c.controls)))
            for i in range(4):
                slots.controls[i].on_click(None)
                siguiente.on_click(None)
                confirmar.on_click(None)
            evento(controles,'confirmar_clima').on_click(None)
            evento(controles,'confirmar_camara').on_click(None)
            with patch.object(app,'exportar_escena',wraps=mms.exportar_escena) as exportar:
                with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)):
                    actores=Path(t)/'assets/actors';actores.mkdir(parents=True)
                    # Los IDs elegidos se verifican sobre los argumentos, sin sustituir las plantillas.
                    def salida(**datos):
                        for codigo in datos['actores_ids']:
                            (actores/f'{codigo}.png').touch()
                        return mms.exportar_escena(**datos)
                    exportar.side_effect=salida
                    await crear.on_click(None)
                    datos=exportar.call_args.kwargs
                    self.assertEqual(len(set(datos['actores_ids'])),4)
                    self.assertIsNone(datos['destino'])
                    self.assertEqual(datos['clima'],18)
                    self.assertEqual(datos['hora'],21)
                    self.assertAlmostEqual(datos['inicio'][0],esperado_x)
                    self.assertAlmostEqual(datos['inicio'][1],esperado_y)
                    contenido=next((Path(t)/'salida_mms').glob('*.mms')).read_text(encoding='utf-8')
                    self.assertIn('[ACTOR_4]',contenido)
                    from test_mvp import leer
                    config=leer(contenido)
                    self.assertEqual({config[s]['GAME_WEATHER'] for s in config
                        if s.startswith('OBJ_') and 'GAME_WEATHER' in config[s]},{'18'})
                    self.assertNotIn('GAME_WEATHER=19',contenido)


if __name__=='__main__': unittest.main()
