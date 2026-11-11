"""Correcciones con controles Flet reales y SQLite temporal, sin API ni entrenamiento."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import flet as ft
import main as app
from src import correcciones_intenciones as correcciones
from src.modelo_intenciones import CARPETA_MODELO
from test_ui_mvp import PagePrueba, recorrer, evento


class PageConDialogos(PagePrueba):
    def __init__(self):
        super().__init__()
        self.dialogos=[]

    def show_dialog(self, dialogo):
        self.dialogos.append(dialogo)

    def pop_dialog(self):
        return self.dialogos.pop()


def controles_dialogo(page):
    dialogo=page.dialogos[-1]
    return list(recorrer([dialogo.content,*dialogo.actions]))


@patch.object(ft.Container,'update',lambda self:None)
class CorreccionesUI(unittest.IsolatedAsyncioTestCase):
    async def preparar(self, texto):
        page=PageConDialogos()
        await app.main(page)
        controles=list(recorrer(page.controls))
        next(c for c in controles if isinstance(c,ft.TextField)).value=texto
        return page,controles

    async def test_guardar_exige_etiqueta_y_aprobar_requiere_seleccion_explicita(self):
        texto='quiero que junte las palmas al terminar la presentación'
        pesos=CARPETA_MODELO/'pesos.npz'
        huella_antes=hashlib.sha256(pesos.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as t,patch.object(correcciones,'ARCHIVO',Path(t)/'correcciones.sqlite3'):
            page,controles=await self.preparar(texto)
            evento(controles,'abrir_correcciones').on_click(None)
            dialogo=controles_dialogo(page)
            etiqueta=next(c for c in dialogo if isinstance(c,ft.Dropdown) and c.label=='Gesto que querías representar')
            self.assertIsNone(etiqueta.value)
            guardar=evento(dialogo,'guardar_correccion')
            guardar.on_click(None)
            self.assertEqual(correcciones.listar(),[])
            self.assertTrue(any('Elige el gesto correcto' in str(getattr(c,'value','')) for c in dialogo))
            etiqueta.value='aplaudir'
            guardar.on_click(None)
            pendientes=correcciones.listar()
            self.assertEqual(len(pendientes),1)
            self.assertEqual(pendientes[0]['texto'],texto)
            self.assertEqual(pendientes[0]['intencion'],'aplaudir')
            self.assertEqual(pendientes[0]['estado'],'pendiente')
            aprobar=evento(dialogo,'aprobar_etiqueta')
            self.assertTrue(aprobar.disabled)
            aprobar.on_click(None)
            self.assertEqual(len(correcciones.listar()),1)
            selector=next(c for c in dialogo if isinstance(c,ft.Dropdown) and c.label=='Corrección pendiente')
            self.assertIsNone(selector.value)
            selector.value=pendientes[0]['id']
            selector.on_select(SimpleNamespace(control=selector))
            self.assertFalse(aprobar.disabled)
            self.assertTrue(any(texto in str(getattr(c,'value','')) and
                correcciones.ETIQUETAS['aplaudir'] in str(getattr(c,'value','')) for c in dialogo))
            aprobar.on_click(None)
            self.assertEqual(correcciones.listar(),[])
            self.assertEqual(len(correcciones.listar(estado='aprobada')),1)
            self.assertTrue(any('próximo entrenamiento' in str(getattr(c,'value','')) for c in dialogo))
        self.assertEqual(hashlib.sha256(pesos.read_bytes()).hexdigest(),huella_antes)

    async def test_revision_desde_dialogo_de_correcciones_descarta_solo_la_elegida(self):
        with tempfile.TemporaryDirectory() as t,patch.object(correcciones,'ARCHIVO',Path(t)/'correcciones.sqlite3'):
            primera=correcciones.registrar('mueve el cuerpo con música','bailar')
            segunda=correcciones.registrar('atiende el móvil','telefono')
            page,controles=await self.preparar('una persona camina')
            evento(controles,'abrir_correcciones').on_click(None)
            dialogo=controles_dialogo(page)
            selector=next(c for c in dialogo if isinstance(c,ft.Dropdown) and c.label=='Corrección pendiente')
            self.assertEqual(len(selector.options),2)
            selector.value=primera['id']
            selector.on_select(SimpleNamespace(control=selector))
            evento(dialogo,'descartar_correccion').on_click(None)
            self.assertEqual([r['id'] for r in correcciones.listar()],[segunda['id']])
            self.assertEqual(correcciones.listar(estado='aprobada'),[])
            self.assertTrue(any('no se usará para entrenar' in str(getattr(c,'value','')) for c in dialogo))

    async def test_error_de_almacenamiento_se_muestra_sin_cerrar_la_aplicacion(self):
        with patch.object(correcciones,'listar',side_effect=sqlite3.OperationalError('base no disponible')):
            page,controles=await self.preparar('una persona sonríe')
            evento(controles,'abrir_correcciones').on_click(None)
            dialogo=controles_dialogo(page)
            self.assertTrue(any('No se pudieron cargar las correcciones' in str(getattr(c,'value',''))
                for c in dialogo))
            self.assertEqual(len(page.dialogos),1)

    async def test_corregir_una_etiqueta_ya_aprobada_desde_la_interfaz(self):
        texto='el personaje junta sus palmas varias veces'
        with tempfile.TemporaryDirectory() as t,patch.object(correcciones,'ARCHIVO',Path(t)/'correcciones.sqlite3'):
            page,controles=await self.preparar(texto)
            evento(controles,'abrir_correcciones').on_click(None)
            dialogo=controles_dialogo(page)
            etiqueta=next(c for c in dialogo if isinstance(c,ft.Dropdown) and c.label=='Gesto que querías representar')
            filtro=next(c for c in dialogo if isinstance(c,ft.Dropdown) and c.label=='Estado de revisión')
            selector=next(c for c in dialogo if isinstance(c,ft.Dropdown) and c.label=='Corrección pendiente')
            guardar=evento(dialogo,'guardar_correccion')
            aprobar=evento(dialogo,'aprobar_etiqueta')
            descartar=evento(dialogo,'descartar_correccion')
            self.assertEqual(filtro.value,'pendiente')
            etiqueta.value='bailar'
            guardar.on_click(None)
            equivocada=correcciones.listar()[0]
            selector.value=equivocada['id']
            selector.on_select(SimpleNamespace(control=selector))
            aprobar.on_click(None)
            self.assertEqual(correcciones.listar('aprobada')[0]['intencion'],'bailar')

            filtro.value='aprobada'
            filtro.on_select(SimpleNamespace(control=filtro))
            self.assertIsNone(selector.value)
            self.assertTrue(descartar.disabled)
            selector.value=equivocada['id']
            selector.on_select(SimpleNamespace(control=selector))
            self.assertTrue(aprobar.disabled)
            self.assertFalse(descartar.disabled)
            self.assertTrue(any('Estado: aprobada' in str(getattr(c,'value','')) for c in dialogo))
            descartar.on_click(None)
            self.assertEqual(correcciones.listar('aprobada'),[])

            etiqueta.value='aplaudir'
            guardar.on_click(None)
            self.assertEqual(filtro.value,'pendiente')
            correcta=correcciones.listar()[0]
            self.assertEqual(correcta['intencion'],'aplaudir')
            selector.value=correcta['id']
            selector.on_select(SimpleNamespace(control=selector))
            aprobar.on_click(None)
            self.assertEqual([r['intencion'] for r in correcciones.listar('aprobada')],['aplaudir'])

            # Una rechazada puede proponerse de nuevo, pero el conflicto aprobado se conserva.
            filtro.value='rechazada'
            filtro.on_select(SimpleNamespace(control=filtro))
            selector.value=equivocada['id']
            selector.on_select(SimpleNamespace(control=selector))
            self.assertFalse(aprobar.disabled)
            self.assertTrue(descartar.disabled)
            aprobar.on_click(None)
            self.assertTrue(any('otra etiqueta aprobada' in str(getattr(c,'value','')) for c in dialogo))
            self.assertEqual([r['intencion'] for r in correcciones.listar('aprobada')],['aplaudir'])

            recuperable=correcciones.registrar('el actor hace un gesto de bienvenida','saludar')
            correcciones.revisar(recuperable['id'],False)
            filtro.on_select(SimpleNamespace(control=filtro))
            selector.value=recuperable['id']
            selector.on_select(SimpleNamespace(control=selector))
            aprobar.on_click(None)
            self.assertEqual({r['intencion'] for r in correcciones.listar('aprobada')},{'aplaudir','saludar'})


if __name__=='__main__':
    unittest.main()
