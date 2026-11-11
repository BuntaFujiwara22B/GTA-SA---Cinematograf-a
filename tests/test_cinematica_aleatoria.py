"""El azar combina tareas compilables, recursos existentes y ambientes coherentes."""
import configparser
import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.cinematica_aleatoria as azar
import src.mvp_mms as mms
from src.compilar_secuencia import capacidad_recorrido
from src.escenas_semanticas import estatica, validar_pasos
from src.paquete_mision import dependencias
from src.ubicaciones_escena import puntos_entrada


class CinematicaAleatoria(unittest.TestCase):
    actores = [0, 7, 11, 112]

    def test_semilla_reproduce_plan_reparto_y_ambiente(self):
        def datos(semilla):
            escena = azar.crear_escena_aleatoria(self.actores, random.Random(semilla))
            return escena | {'plan': escena['plan'].model_dump()}
        for semilla in (0, 1, 3, 7, 29):
            self.assertEqual(datos(semilla), datos(semilla))

    def test_cien_propuestas_completas_sin_inventar_mecanicas_o_recursos(self):
        titulos = set()
        calles = {r['id']: r for r in azar.rutas_disponibles()}
        lugares = {u['id']: u for u in azar.ubicaciones()}
        recorridos = {r['id']: r for r in azar.rutas_vehiculos()}
        coches = {v['model_id'] for v in azar.disponibles('vehicles')}
        for semilla in range(100):
            with self.subTest(semilla=semilla):
                escena = azar.crear_escena_aleatoria(self.actores, random.Random(semilla))
                p = escena['plan']
                titulos.add(escena['titulo'])
                self.assertTrue(p.es_valido)
                self.assertEqual(p.actores_ids_sugeridos, escena['actores'])
                self.assertEqual(p.actor_id_sugerido, escena['actores'][0])
                self.assertEqual(p.cantidad_actores, len(escena['actores']))
                self.assertEqual(len(set(escena['actores'])), len(escena['actores']))
                self.assertLessEqual(len(escena['actores']), 4)
                self.assertTrue(set(escena['actores']).issubset(self.actores))
                self.assertIn(escena['camara'], azar._CAMARAS)
                if p.accion == 'conducir_vehiculo':
                    self.assertEqual(p.cantidad_actores, 1)
                    self.assertIn(p.vehiculo_id_sugerido, coches)
                    self.assertEqual(escena['camara'], 'Tercera Persona')
                    lugar = recorridos[p.ruta_vehiculo_id]
                    self.assertEqual(lugar['entorno'], p.entorno_sugerido)
                else:
                    self.assertEqual(p.accion, 'secuencia')
                    self.assertGreaterEqual(len(p.pasos), 2)
                    validar_pasos(p.pasos, p.cantidad_actores, p.duracion_sugerida)
                    if estatica(p):
                        lugar = lugares[p.ubicacion_id_sugerida]
                        self.assertEqual(lugar['entorno'], p.entorno_sugerido)
                        self.assertIsNone(p.ruta_id_sugerida)
                    else:
                        lugar = calles[p.ruta_id_sugerida]
                        self.assertEqual(p.entorno_sugerido, 'ciudad')
                clave = p.entorno_sugerido if p.entorno_sugerido != 'ciudad' else lugar['zona']
                self.assertIn(p.clima_id_sugerido, azar._CLIMAS[clave])
                self.assertNotIn('comprobada', p.motivo_elecciones)
        self.assertEqual(len(titulos), 7)

    def test_compila_cada_guion_y_empaqueta_carrec_cuando_hay_conduccion(self):
        casos = {}
        for semilla in range(100):
            escena = azar.crear_escena_aleatoria(self.actores, random.Random(semilla))
            casos.setdefault(escena['titulo'], escena)
        with tempfile.TemporaryDirectory() as temporal, patch.object(mms, 'ROOT', Path(temporal)):
            carpeta = Path(temporal) / 'assets/actors'
            carpeta.mkdir(parents=True)
            for actor in self.actores:
                (carpeta / f'{actor}.png').touch()
            for titulo, escena in casos.items():
                with self.subTest(titulo=titulo):
                    p = escena['plan']
                    extra = {}
                    if p.accion == 'conducir_vehiculo':
                        ruta = next(r for r in azar.rutas_vehiculos() if r['id'] == p.ruta_vehiculo_id)
                        inicio, _ = puntos_entrada(ruta)
                        destino = tuple(ruta['puntos'][-1])
                        extra = dict(vehiculo_id=p.vehiculo_id_sugerido,
                            ruta_vehiculo_id=p.ruta_vehiculo_id, velocidad_kmh=p.velocidad_kmh_sugerida)
                    elif estatica(p):
                        inicio = tuple(next(u['posicion'] for u in azar.ubicaciones() if u['id'] == p.ubicacion_id_sugerida))
                        destino = None
                    else:
                        ruta = next(r for r in azar.rutas_disponibles() if r['id'] == p.ruta_id_sugerida)
                        inicio, destino = tuple(ruta['inicio']), tuple(ruta['destino'])
                        limite = capacidad_recorrido(p.pasos, p.duracion_sugerida)
                        distancia = math.dist(inicio, destino)
                        factor = min(1, limite / distancia)
                        destino = tuple(a + (b - a) * factor for a, b in zip(inicio, destino))
                    archivo = mms.exportar_escena(actor_id=p.actor_id_sugerido,
                        actores_ids=p.actores_ids_sugeridos, inicio=inicio, destino=destino,
                        accion=p.accion, pasos=[paso.model_dump() for paso in p.pasos],
                        duracion=p.duracion_sugerida, hora=p.hora_sugerida,
                        clima=p.clima_id_sugerido, descripcion=escena['texto'], **extra)
                    cfg = configparser.ConfigParser(interpolation=None)
                    cfg.optionxform = str
                    cfg.read_string(archivo.read_text(encoding='utf-8'))
                    self.assertEqual(cfg['OBJ_0']['GAME_WEATHER'], str(p.clima_id_sugerido))
                    self.assertEqual(cfg['OBJ_0']['GAME_TIME'], str(p.hora_sugerida))
                    recursos = dependencias(archivo)
                    self.assertEqual(any(r.startswith('Carrec/') for r in recursos), p.accion == 'conducir_vehiculo')
                    if p.accion == 'secuencia':
                        objetivos = {cfg[s]['OBJ'] for s in cfg if s.startswith('ACTION_A_') and cfg[s]['Type'] != '7'}
                        self.assertEqual(len(objetivos), len(p.pasos))

    def test_reparto_pequeno_y_catalogos_incompletos_no_inventan_relleno(self):
        for semilla in range(12):
            escena = azar.crear_escena_aleatoria([0, 0], random.Random(semilla))
            self.assertEqual(escena['actores'], [0])
        with patch.object(azar, 'rutas_disponibles', return_value=[]), \
                patch.object(azar, 'disponibles', return_value=[]):
            escena = azar.crear_escena_aleatoria(self.actores, random.Random(7))
            self.assertTrue(estatica(escena['plan']))
        with self.assertRaisesRegex(ValueError, 'personajes'):
            azar.crear_escena_aleatoria([], random.Random(1))
        with patch.object(azar, 'rutas_disponibles', return_value=[]), \
                patch.object(azar, 'ubicaciones', return_value=[]), \
                patch.object(azar, 'rutas_vehiculos', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'ubicaciones'):
                azar.crear_escena_aleatoria(self.actores, random.Random(1))


class RandomDesdeInterfaz(unittest.IsolatedAsyncioTestCase):
    async def test_siete_guiones_y_rutas_antes_rechazadas_generan_sin_api(self):
        import asyncio
        import flet as ft
        import main as app
        import src.banda_sonora as musica
        from src.paths import ASSETS
        from test_ui_mvp import PagePrueba, recorrer, evento
        from unittest.mock import AsyncMock

        actores = sorted(int(p.stem) for p in (ASSETS / 'actors').glob('*.png') if p.stem.isdigit())
        guiones = {}
        for semilla in range(100):
            escena = azar.crear_escena_aleatoria(actores, random.Random(semilla))
            guiones.setdefault(escena['titulo'], semilla)
        # Los nodos de las semillas 26/84/98 antes podían caer sobre tejados o
        # tener alturas incompatibles al pasar por la validación real de Flet.
        semillas = sorted(set(guiones.values()) | {26, 84, 98})
        with patch.object(ft.Container, 'update', lambda self: None), \
                patch.object(asyncio, 'sleep', new=AsyncMock()):
            for semilla in semillas:
                escena = azar.crear_escena_aleatoria(actores, random.Random(semilla))
                with self.subTest(semilla=semilla, titulo=escena['titulo']), \
                        tempfile.TemporaryDirectory() as temporal, \
                        patch.object(mms, 'ROOT', Path(temporal)), \
                        patch.object(musica, 'RAIZ', Path(temporal) / 'music'), \
                        patch.object(app, 'crear_escena_aleatoria', return_value=escena), \
                        patch.object(app, 'analizar_accion_usuario', side_effect=AssertionError('No debe consultar APIs')) as api:
                    carpeta = Path(temporal) / 'assets/actors'
                    carpeta.mkdir(parents=True)
                    for actor in actores:
                        (carpeta / f'{actor}.png').touch()
                    page = PagePrueba()
                    await app.main(page)
                    controles = list(recorrer(page.controls))
                    await evento(controles, 'on_crear_random').on_click(None)
                    api.assert_not_called()
                    mensajes = '\n'.join(str(c.value) for c in recorrer(page.controls) if isinstance(c, ft.Text))
                    self.assertTrue(page.controls[-1].visible, mensajes)
                    archivos = list((Path(temporal) / 'salida_mms').glob('*.mms'))
                    self.assertEqual(len(archivos), 1, mensajes)
                    recursos = dependencias(archivos[0])
                    self.assertEqual(any(r.startswith('Carrec/') for r in recursos),
                        escena['plan'].accion == 'conducir_vehiculo')
