"""El montaje y las preferencias del usuario llegan al MMS desde Flet real."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import flet as ft
import main as app
import src.mvp_mms as mms
from src.mvp_plan import plan_local
from test_mvp import leer
from test_ui_mvp import PagePrueba, recorrer, evento


PETICION = 'una persona camina por una avenida durante 60 segundos'


@patch.object(ft.Container, 'update', lambda self: None)
class MontajeDesdeInterfaz(unittest.IsolatedAsyncioTestCase):
    async def preparar(self, texto):
        page = PagePrueba()
        await app.main(page)
        controles = list(recorrer(page.controls))
        await self.analizar(controles, texto)
        return page, controles

    async def analizar(self, controles, texto):
        campo = next(c for c in controles if isinstance(c, ft.TextField))
        campo.value = texto
        with patch.object(app, 'analizar_accion_usuario', side_effect=plan_local):
            await evento(controles, 'on_analizar').on_click(None)

    async def exportar(self, controles, raiz):
        actores = raiz / 'assets/actors'
        actores.mkdir(parents=True, exist_ok=True)
        (actores / '0.png').touch()
        anteriores = set((raiz / 'salida_mms').glob('*.mms'))
        with patch.object(mms, 'ROOT', raiz), \
                patch.object(app, 'exportar_escena', wraps=mms.exportar_escena) as exportar:
            await evento(controles, 'on_crear_mms').on_click(None)
        nuevas = set((raiz / 'salida_mms').glob('*.mms')) - anteriores
        avisos = [c.value for c in controles if isinstance(c, ft.Text) and c.value]
        self.assertEqual(len(nuevas), 1, str(avisos[-15:]))
        self.assertTrue(exportar.called)
        archivo = nuevas.pop()
        return leer(archivo.read_text(encoding='utf-8')), exportar.call_args.kwargs

    @staticmethod
    def temporizados(config):
        return [config[s] for s in config if s.startswith('OBJ_') and s != 'OBJ_0'
            and config[s].get('Type') == '6']

    async def test_peticion_sin_camara_exporta_doce_planos_sin_reiniciar_caminata(self):
        _, controles = await self.preparar(PETICION)
        with tempfile.TemporaryDirectory() as temporal:
            cfg, datos = await self.exportar(controles, Path(temporal))
        self.assertEqual(datos['camara'], 'automatica')
        planos = self.temporizados(cfg)
        self.assertEqual(len(planos), 12)
        self.assertEqual([int(p['DIAL_TIME']) for p in planos], [5000] * 12)
        self.assertEqual(sum(int(p['DIAL_TIME']) for p in planos), 60000)
        self.assertEqual(len([s for s in cfg if s.startswith('ACTION_A_')]), 1)
        self.assertEqual(cfg['ACTION_A_1']['Type'], '4')
        self.assertEqual(cfg['ACTION_A_1']['OBJ'], '0')
        encuadres = {tuple(p.get(k) for k in (
            'PLA_CUM_MODE', 'PLA_CUM_OX', 'PLA_CUM_OY', 'PLA_CUM_OZ', 'PLA_CUM_ZOOM'))
            for p in planos}
        self.assertGreaterEqual(len(encuadres), 3)

    async def test_instruccion_de_camara_fija_detras_conserva_el_plano_completo(self):
        texto = PETICION + ', con cámara fija detrás del actor durante toda la escena'
        self.assertTrue(plan_local(texto).es_valido)
        _, controles = await self.preparar(texto)
        with tempfile.TemporaryDirectory() as temporal:
            cfg, datos = await self.exportar(controles, Path(temporal))
        self.assertEqual(datos['camara'], 'seguimiento_trasero')
        planos = self.temporizados(cfg)
        self.assertEqual(len(planos), 1)
        self.assertEqual(int(planos[0]['DIAL_TIME']), 60000)
        self.assertEqual(planos[0]['PLA_CUM_MODE'], '6')
        self.assertEqual(planos[0]['CUM_ACTOR'], '1')

    async def test_eleccion_manual_se_respeta_y_nueva_peticion_restablece_montaje(self):
        _, controles = await self.preparar(PETICION)
        evento(controles, 'editar_camara').on_click(None)
        tercera_persona = next(c for c in controles if isinstance(c, ft.Container)
            and isinstance(c.content, ft.Column)
            and any(isinstance(t, ft.Text) and t.value == 'Tercera persona' for t in c.content.controls))
        tercera_persona.on_click(None)
        evento(controles, 'confirmar_edicion_camara').on_click(None)
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            cfg, datos = await self.exportar(controles, raiz)
            self.assertEqual(datos['camara'], 'seguimiento_trasero')
            self.assertEqual(len(self.temporizados(cfg)), 1)
            evento(controles, 'volver_inicio').on_click(None)
            await self.analizar(controles, PETICION)
            cfg, datos = await self.exportar(controles, raiz)
            self.assertEqual(datos['camara'], 'automatica')
            self.assertEqual(len(self.temporizados(cfg)), 12)

    async def test_ayuda_distingue_carpeta_para_guardar_de_raiz_para_instalar(self):
        page = PagePrueba()
        await app.main(page)
        controles = list(recorrer(page.controls))
        ayudas = [c for c in controles if isinstance(c, ft.ExpansionTile)
            and isinstance(c.title, ft.Text) and c.title.value == 'Cómo probarla en GTA']
        self.assertEqual(len(ayudas), 1)
        textos = '\n'.join(c.value or '' for c in recorrer([ayudas[0]]) if isinstance(c, ft.Text))
        self.assertIn('Guardar misión completa', textos)
        self.assertIn('SAMM(Stable)', textos)
        self.assertIn('MiEscena', textos)
        self.assertIn('Instalar en GTA', textos)
        self.assertIn('carpeta principal', textos)
        self.assertIn('gta_sa.exe', textos)
        self.assertIn('Mission Maker', textos)


if __name__ == '__main__':
    unittest.main()
