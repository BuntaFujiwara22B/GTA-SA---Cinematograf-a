"""Instrucciones de entrega de una misión completa, listas para la interfaz."""
import flet as ft

from src.estilo_ui import ACENTO, FUENTE, SECUNDARIO, SUPERFICIE_ALTA, TEXTO


def instruccionesguardar_mision():
    """Devuelve una ayuda plegable sin rutas de juego específicas del equipo."""
    pasos = (
        'Pulsa Guardar misión completa.',
        'En la carpeta de tu GTA abre modloader y después SAMM(Stable). '
        'Crea una carpeta llamada MiEscena y entra en ella.',
        'Guarda allí el archivo .mms. El programa copia también el recorrido '
        'y la música que necesite la escena.',
        'Cierra GTA completamente, vuelve a abrirlo y carga MiEscena en Mission Maker.',
    )
    filas = []
    for numero, texto in enumerate(pasos, 1):
        filas.append(ft.Row([
            ft.Container(content=ft.Text(str(numero), size=13, color=ACENTO,
                weight=ft.FontWeight.W_600), width=28, height=28, border_radius=14,
                bgcolor=SUPERFICIE_ALTA, alignment=ft.Alignment(0, 0)),
            ft.Text(texto, size=14, color=TEXTO, font_family=FUENTE, expand=True),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START))
    return ft.ExpansionTile(
        title=ft.Text('Cómo probarla en GTA', size=15, color=TEXTO,
            font_family=FUENTE, weight=ft.FontWeight.W_600),
        subtitle=ft.Text('Dónde guardar la misión y cómo cargarla.', size=12,
            color=SECUNDARIO, font_family=FUENTE),
        controls=[ft.Container(content=ft.Column([
            *filas,
            ft.Text('Carpeta de destino', size=12, color=SECUNDARIO),
            ft.Text(r'modloader\SAMM(Stable)\MiEscena', size=13,
                font_family='Consolas', color=ACENTO, selectable=True),
            ft.Divider(height=8, color=SUPERFICIE_ALTA),
            ft.Text('Instalación automática', size=14, color=TEXTO,
                weight=ft.FontWeight.W_600),
            ft.Text('Si pulsas Instalar en GTA, selecciona la carpeta principal '
                'que contiene gta_sa.exe o gta.exe. El programa crea la carpeta '
                'de la misión y copia todos sus archivos automáticamente.',
                size=13, color=SECUNDARIO, font_family=FUENTE),
        ], spacing=16), padding=ft.Padding(12, 16, 12, 20))],
    )


instrucciones_guardar_mision = instruccionesguardar_mision
