"""La interfaz entrega coche y música juntos, sin exponer un MMS parcial copiable."""
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import AsyncMock, patch

import flet as ft
import main as app
import src.banda_sonora as musica
import src.mvp_mms as mms
from src.mvp_plan import plan_local
from src.paquete_mision import dependencias
from src.ubicaciones_escena import rutas_vehiculos
from test_ui_mvp import PagePrueba, recorrer, evento


@patch.object(ft.Container,'update',lambda self:None)
class EntregaCompletaUI(unittest.IsolatedAsyncioTestCase):
    async def preparar(self,raiz):
        audio=musica.RAIZ/'feliz/ritmo.wav';audio.parent.mkdir(parents=True)
        with wave.open(str(audio),'wb') as archivo:
            archivo.setnchannels(1);archivo.setsampwidth(2);archivo.setframerate(22050)
            archivo.writeframes(b'\0\0'*2205)
        actores=raiz/'assets/actors';actores.mkdir(parents=True);(actores/'112.png').touch()
        p=plan_local('una persona conduce un auto en el campo')
        p.actor_id_sugerido=112;p.actores_ids_sugeridos=[112];p.vehiculo_id_sugerido=489
        p.ruta_vehiculo_id=rutas_vehiculos()[0]['id']
        page=PagePrueba()
        with patch.object(app,'analizar_accion_usuario',return_value=p):
            await app.main(page)
            controles=list(recorrer(page.controls))
            next(c for c in controles if isinstance(c,ft.TextField)).value='una persona conduce un auto en el campo'
            await evento(controles,'on_analizar').on_click(None)
        categoria=next(c for c in controles if isinstance(c,ft.Dropdown) and c.label=='Banda sonora')
        categoria.value='feliz';categoria.on_select(None)
        await evento(controles,'on_crear_mms').on_click(None)
        origen=next((raiz/'salida_mms').glob('*.mms'))
        return controles,origen

    async def test_coche_y_musica_se_guardan_juntos_y_no_se_exponen_como_texto_parcial(self):
        with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)),patch.object(musica,'RAIZ',Path(t)/'music'):
            raiz=Path(t);controles,origen=await self.preparar(raiz)
            visor=next(c for c in controles if isinstance(c,ft.TextField) and c.read_only)
            self.assertNotIn('[MISSION]',visor.value)
            self.assertIn('Carrec/',visor.value)
            self.assertIn('Sounds/',visor.value)
            self.assertIn('Guarda o instala la misión completa',visor.value)
            self.assertFalse(evento(controles,'copiar_mms').visible)
            guardar=evento(controles,'guardar_mms_como')
            self.assertIn('misión completa',guardar.content.lower())
            destino=raiz/'GTA/movimiento/carro.mms'
            with patch.object(ft.FilePicker,'save_file',new=AsyncMock(return_value=str(destino))) as selector,\
                    patch.object(ft.Clipboard,'set',new=AsyncMock()) as portapapeles:
                await guardar.on_click(None)
            selector.assert_awaited_once()
            self.assertNotIn('src_bytes',selector.await_args.kwargs)
            portapapeles.assert_not_awaited()
            entregados=dependencias(destino)
            self.assertEqual(len(entregados),3)
            self.assertEqual(destino.read_bytes(),origen.read_bytes())
            originales=dependencias(origen)
            for nombre,archivo in entregados.items():
                if nombre.startswith(('Sounds/','Carrec/')):
                    self.assertEqual(archivo.read_bytes(),originales[nombre].read_bytes())

    async def test_atajo_de_copia_con_recursos_guarda_mision_y_cancelar_no_pega_texto(self):
        with tempfile.TemporaryDirectory() as t,patch.object(mms,'ROOT',Path(t)),patch.object(musica,'RAIZ',Path(t)/'music'):
            raiz=Path(t);controles,_=await self.preparar(raiz)
            with patch.object(ft.FilePicker,'save_file',new=AsyncMock(return_value=None)) as selector,\
                    patch.object(ft.Clipboard,'set',new=AsyncMock()) as portapapeles:
                await evento(controles,'copiar_mms').on_click(None)
            selector.assert_awaited_once()
            portapapeles.assert_not_awaited()
            self.assertTrue(any(isinstance(c,ft.Text) and c.value=='Guardado cancelado.' for c in controles))
            self.assertFalse((raiz/'GTA').exists())


if __name__=='__main__':unittest.main()
