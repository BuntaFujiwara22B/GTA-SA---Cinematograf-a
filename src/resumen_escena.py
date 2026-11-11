"""Tarjetas del resumen; editar requiere una acción explícita del usuario."""
import flet as ft
import flet.canvas as cv
from src.estilo_ui import FONDO, SUPERFICIE, BORDE, TEXTO, ACENTO, FUENTE
DESTINO = '#75B8FF'


def tarjeta(titulo,contenido,editar=None,width=330):
    vista=ft.Container(content=contenido,left=0,right=0,top=0,bottom=0,alignment=ft.Alignment(0,0))
    controles=[vista]
    icono=None
    if editar:
        icono=ft.Container(content=ft.IconButton(icon=ft.Icons.EDIT_OUTLINED,tooltip='Cambiar '+titulo.lower(),
            on_click=editar,icon_color=ACENTO,icon_size=18),right=0,top=0,bgcolor=FONDO,
            border_radius=14,opacity=.65,animate_opacity=ft.Animation(160))
        controles.append(icono)
    def hover(e):
        if icono:
            icono.opacity=1 if str(e.data).lower()=='true' else .65
            e.control.border=ft.Border.all(1,ACENTO if icono.opacity==1 else BORDE)
            e.control.update()
    control=ft.Container(content=ft.Column([
        ft.Text(titulo,font_family=FUENTE,size=17,weight=ft.FontWeight.W_600,color=TEXTO),
        ft.Stack(controles,expand=True),
    ],horizontal_alignment=ft.CrossAxisAlignment.START,spacing=16),width=width,height=300,
        padding=20,border=ft.Border.all(1,BORDE),border_radius=20,
        bgcolor=SUPERFICIE,on_hover=hover,on_click=editar,tooltip='Cambiar '+titulo.lower() if editar else None)
    return control,vista,icono


def miniatura_ubicacion(src,inicio,destino=None,width=244,height=156):
    puntos=[inicio]+([destino] if destino else [])
    cx=sum(p[0] for p in puntos)/len(puntos);cy=sum(p[1] for p in puntos)/len(puntos)
    # El encuadre considera ambos ejes: un recorrido largo o vertical conserva
    # sus dos extremos dentro de la miniatura, incluso en tarjetas estrechas.
    escalas=[width/400,height/300]
    if destino:
        dx,dy=abs(destino[0]-inicio[0]),abs(destino[1]-inicio[1])
        if dx:escalas.append(max(1,width-56)/dx)
        if dy:escalas.append(max(1,height-56)/dy)
    escala=min(escalas);tam=6000*escala
    controles=[ft.Image(src=src,width=tam,height=tam,fit=ft.BoxFit.FILL,
        left=width/2-(cx+3000)*escala,top=height/2-(3000-cy)*escala)]
    pantalla=lambda p:(width/2+(p[0]-cx)*escala,height/2-(p[1]-cy)*escala)
    if destino:
        a,b=pantalla(inicio),pantalla(destino)
        controles.append(cv.Canvas([cv.Line(*a,*b,paint=ft.Paint(color=ACENTO,stroke_width=3))],width=width,height=height))
    for i,p in enumerate(puntos):
        x,y=pantalla(p)
        controles.append(ft.Container(content=ft.Icon(ft.Icons.LOCATION_ON if i==0 else ft.Icons.FLAG,
            size=20,color=ACENTO if i==0 else DESTINO),left=x-14,top=y-28,width=28,height=28,
            bgcolor=FONDO,border_radius=14,alignment=ft.Alignment(0,0),tooltip='Inicio' if i==0 else 'Destino'))
    return ft.Container(content=ft.Stack(controles,width=width,height=height),width=width,height=height,
        border_radius=16,border=ft.Border.all(1,BORDE),bgcolor=FONDO,clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
