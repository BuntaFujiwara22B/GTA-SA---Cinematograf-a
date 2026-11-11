"""Controles visuales compartidos del estudio de escenas."""
import asyncio
import flet as ft

FONDO = '#0C100F'
SUPERFICIE = '#151B18'
SUPERFICIE_ALTA = '#1B241E'
BORDE = '#2B3730'
TEXTO = '#F1F5EF'
SECUNDARIO = '#A4B0A7'
ACENTO = '#D2F86B'
TINTA = '#17200D'
FUENTE = 'Segoe UI'


def estilo_boton(primario=False):
    return ft.ButtonStyle(
        color=TINTA if primario else TEXTO,
        bgcolor=ACENTO if primario else SUPERFICIE_ALTA,
        padding=ft.Padding.symmetric(horizontal=24, vertical=18),
        shape=ft.RoundedRectangleBorder(radius=14),
        text_style=ft.TextStyle(font_family=FUENTE, size=15, weight=ft.FontWeight.W_600),
    )


def encabezado(titulo, detalle=None):
    controles=[ft.Text(titulo, size=32, weight=ft.FontWeight.W_600, color=TEXTO)]
    if detalle:
        controles.append(ft.Text(detalle, size=14, color=SECUNDARIO))
    return ft.Column(controles, spacing=8)


def panel(contenido, padding=28, **kwargs):
    return ft.Container(content=contenido, padding=padding, bgcolor=SUPERFICIE,
        border=ft.Border.all(1, BORDE), border_radius=22, **kwargs)


def titulo_lcd(texto='¿Qué quieres crear?'):
    """Texto continuo: se ilumina un único glifo, sin casillas alrededor."""
    letras=[ft.TextSpan(c, style=ft.TextStyle(color='#59685D')) for c in texto]
    control=ft.Text(spans=letras, size=62, font_family='Namche Shape Origin',
        text_align=ft.TextAlign.CENTER, semantics_label=texto)
    return control, [letra for letra in letras if not letra.text.isspace()]


def encender_letra(letras, indice):
    for i, letra in enumerate(letras):
        letra.style.color=ACENTO if i==indice else '#59685D'
        letra.style.shadow=[ft.BoxShadow(blur_radius=16, color='#80D2F86B')]
        if i!=indice:
            letra.style.shadow=[]


def boton_glitch(texto, on_click, icono=ft.Icons.ARROW_FORWARD):
    """Una breve separación de color al pasar el ratón; el texto sigue legible."""
    capas=[ft.Text(texto,size=17,weight=ft.FontWeight.W_700,color=color,
        font_family=FUENTE,offset=ft.Offset(desplazamiento,0),opacity=0)
        for color,desplazamiento in (('#00CFDE',-.025),('#E460B3',.025))]
    frente=ft.Text(texto,size=17,weight=ft.FontWeight.W_700,color=TINTA,font_family=FUENTE)
    etiqueta=ft.Stack([*capas,frente])
    animando=[False]

    async def hover(e):
        if str(e.data).lower()!='true' or e.control.disabled or animando[0]:
            return
        animando[0]=True
        try:
            for capa in capas:capa.opacity=.75
            e.control.update()
            await asyncio.sleep(.09)
        finally:
            for capa in capas:capa.opacity=0
            animando[0]=False
            try:e.control.update()
            except RuntimeError:pass

    return ft.Container(content=ft.Row([etiqueta,ft.Icon(icono,color=TINTA,size=20)],
        tight=True,spacing=22,alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=ACENTO,padding=ft.Padding.symmetric(horizontal=30,vertical=19),
        border_radius=14,on_click=on_click,on_hover=hover,ink=True,
        animate_opacity=ft.Animation(160),tooltip=texto)
