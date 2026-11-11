import flet as ft
import flet.canvas as cv
import asyncio
import math
import random
import os
import time
from src.mvp_plan import analizar_peticion_final as analizar_accion_usuario
from src.mvp_plan import comprobaciones_peticion
from src.mvp_mms import exportar_escena, POS_INICIO, POS_DESTINO
from src.vista_mapa import VistaMapa
from src.ruta_colisiones import evaluar_perfil, sugerir_ruta
from src.climas import NOMBRES as NOMBRES_CLIMA, preview_clima, clima_con_foto
from src.banda_sonora import pistas
from src.cinematica_aleatoria import crear_escena_aleatoria
from src.catalogos_entidades import disponibles
from visor_mapa import GestorAlturas
from detector_entorno import detectar_entorno_gta
from src.paths import ASSETS, vista_asset
from src.ubicaciones_escena import elegir_ubicacion,elegir_ruta_vehiculo,rutas_vehiculos,puntos_entrada
from src.paquete_mision import zip_mision,guardar_como,dependencias,instalar as instalar_mision
from src.propuesta_escena import completar_propuesta
from src.escenas_semanticas import estatica as es_estatica,es_vehicular,usa_recorrido_vehicular
from src.estilo_ui import (FONDO, SUPERFICIE, SUPERFICIE_ALTA, BORDE, TEXTO,
    SECUNDARIO, ACENTO, TINTA, FUENTE, estilo_boton, encabezado, panel,
    titulo_lcd, encender_letra, boton_glitch)
from src.preferencias_camara import preferencia_camara
from src.ayuda_mision import instruccionesguardar_mision

# ---------------------------------------------------------
# UTILIDADES DE LA INTERFAZ
# ---------------------------------------------------------
def posicion_local(e, defecto=(0.0, 0.0)):
    """Lee la posición local de un evento de gesto (compatible con distintas versiones de Flet)."""
    lp = getattr(e, "local_position", None)
    if lp is not None:
        return float(lp.x), float(lp.y)
    lx = getattr(e, "local_x", None)
    ly = getattr(e, "local_y", None)
    if lx is not None and ly is not None:
        return float(lx), float(ly)
    return defecto


def buscar_imagen_mapa():
    """Busca en assets/ una imagen del mapa de San Andreas (ruta relativa a assets_dir)."""
    if not ASSETS.exists():
        return None
    candidatas = []
    for raiz, carpetas, archivos in os.walk(ASSETS):
        carpetas[:] = [d for d in carpetas if d != "actors" and not d.startswith("hora_")]
        for f in archivos:
            nombre = f.lower()
            if nombre.endswith((".png", ".jpg", ".jpeg", ".webp")) and "map" in nombre and "height" not in nombre:
                ruta = os.path.join(raiz, f)
                candidatas.append((os.path.getsize(ruta), ruta))
    if not candidatas:
        return None
    candidatas.sort(reverse=True)
    ruta = candidatas[0][1].replace("\\", "/")
    return os.path.relpath(ruta,ASSETS).replace("\\","/")


# ---------------------------------------------------------
# INTERFAZ PRINCIPAL (FLET 1.0+)
# ---------------------------------------------------------
async def main(page: ft.Page):
    page.title = "MMS-Director"
    page.theme_mode = ft.ThemeMode.DARK
    page.fonts = {'Namche Shape Origin': 'fonts/NamcheShape-Origin.ttf'}
    page.theme = ft.Theme(font_family=FUENTE,color_scheme_seed=ACENTO,
        scaffold_bgcolor=FONDO,color_scheme=ft.ColorScheme(primary=ACENTO,
            on_primary=TINTA,surface=SUPERFICIE,on_surface=TEXTO,outline=BORDE),
        text_button_theme=ft.TextButtonTheme(style=estilo_boton()))
    page.bgcolor = FONDO
    page.padding = 32
    page.window.width = 1200
    page.window.height = 900
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO  # Solo Fase 1; en la Fase 2 la navegación es por deslizamiento animado

    def alto():
        return int(page.height or page.window.height or 800)

    def ancho():
        return int(page.width or page.window.width or 1000)

    def actualizar_vista(control):
        # En uso real actualiza solo esta rama; los dobles de prueba no tienen página.
        try:control.update()
        except RuntimeError:page.update()

    fase1_activa = [True]
    sesion_activa=[True]
    titulo, letras_titulo = titulo_lcd()
    encender_letra(letras_titulo,0)
    contenedor_titulo = ft.Container(
        content=ft.Column([
            ft.Text('MMS / DIRECTOR',size=12,color=SECUNDARIO,
                style=ft.TextStyle(letter_spacing=4,weight=ft.FontWeight.W_600)),
            titulo,
        ],spacing=22,horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.only(bottom=28),
        opacity=1,
        animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
    )
    espacio_superior = ft.Container(height=28)

    async def iluminar_titulo():
        indice=0
        while sesion_activa[0]:
            if fase1_activa[0]:
                encender_letra(letras_titulo,indice)
                try:contenedor_titulo.update()
                except RuntimeError:break
                indice=(indice+1)%len(letras_titulo)
            await asyncio.sleep(.16 if fase1_activa[0] else .5)

    def al_desconectar(e):
        sesion_activa[0]=False

    def al_conectar(e):
        if not sesion_activa[0]:
            sesion_activa[0]=True
            page.run_task(iluminar_titulo)

    page.on_disconnect=al_desconectar
    page.on_connect=al_conectar

    # Estado visible de la petición, sin consumir consultas de IA al escribir.
    GRIS = '#4A574E'
    luces = [
        ft.Container(width=22, height=22, border_radius=11, bgcolor=GRIS, tooltip="Petición escrita"),
        ft.Container(width=22, height=22, border_radius=11, bgcolor=GRIS, tooltip="Acción y análisis de IA"),
        ft.Container(width=22, height=22, border_radius=11, bgcolor=GRIS, tooltip="Máximo cuatro personajes"),
        ft.Container(width=22, height=22, border_radius=11, bgcolor=GRIS, tooltip="Duración de 1 a 60 segundos"),
    ]
    etiquetas_luces=[ft.Text(t,size=12,color=SECUNDARIO) for t in ('Descripción','Acción','Personajes','Duración')]
    semaforos_row = ft.Row(controls=[ft.Row([luz,etiqueta],spacing=9,tight=True)
        for luz,etiqueta in zip(luces,etiquetas_luces)],
        alignment=ft.MainAxisAlignment.CENTER,spacing=28,wrap=True,run_spacing=12)

    def mostrar_estados(estados):
        nombres=('Descripción','Acción','Personajes','Duración')
        for luz,etiqueta,nombre,estado in zip(luces,etiquetas_luces,nombres,estados):
            estado_texto='Correcto' if estado is True else 'Revisar' if estado is False else 'Por analizar'
            luz.bgcolor=ft.Colors.GREEN if estado is True else ft.Colors.RED if estado is False else ft.Colors.AMBER
            luz.tooltip=nombre+': '+estado_texto
            etiqueta.value=nombre+' · '+estado_texto

    # ---------------------------------------------------------
    # LECTURA DE ACTORES (assets_dir="assets")
    # ---------------------------------------------------------
    ACTORES_BD = {"todos": []}
    ruta_os_actores = str(ASSETS/"actors")
    if os.path.exists(ruta_os_actores):
        archivos_png = [f for f in os.listdir(ruta_os_actores) if f.endswith(".png")]
        archivos_png.sort(key=lambda x: int(x.replace(".png", "")) if x.replace(".png", "").isdigit() else 0)
        for archivo in archivos_png:
            actor_id = archivo.replace(".png", "")
            ACTORES_BD["todos"].append((f"Skin GTA {actor_id}", actor_id, f"actors/{archivo}"))
    hay_actores = bool(ACTORES_BD["todos"])
    if not hay_actores:
        ACTORES_BD["todos"] = [("Falta Imagen", "0", "actors/0.png")]

    # ESTADOS
    eleccion_actor = {"id": ACTORES_BD["todos"][0][1], "nombre": ACTORES_BD["todos"][0][0]}
    eleccion_ubicacion = {"x": 2490.0, "y": -1670.0, "z": 14.5, "entorno": "ciudad"}
    eleccion_hora = {"valor": 12}
    eleccion_clima = {"valor": 0}
    eleccion_camara = {"tipo": "Montaje automático"}
    plan_escena = {"texto": "", "resumen": "", "fuente": ""}
    eleccion_destino = {"x": POS_DESTINO[0], "y": POS_DESTINO[1], "z": POS_DESTINO[2]}
    puntos_marcados = {"inicio": False, "destino": False}
    modo_mapa = {"valor": "inicio"}
    recorrido_coche={'ruta':None}
    propuesta_activa={'activa':False,'ruta_automatica':False}
    edicion_activa={'seccion':None}
    resultado_activo = [False]
    lbl_resumen_escena = ft.Text("", size=14, color=SECUNDARIO, text_align=ft.TextAlign.CENTER)

    # ---------------------------------------------------------
    # NAVEGACIÓN ENTRE SECCIONES (deslizamiento animado, un gesto = una sección)
    # ---------------------------------------------------------
    TOTAL_SECCIONES = 5
    seccion_actual = [0]
    ultimo_cambio = [0.0]
    sobre_mapa = [False]
    gesto_scroll = {"ultimo": 0.0, "delta": 0.0, "consumido": False}

    def ir_a_seccion(i):
        i = max(0, min(TOTAL_SECCIONES - 1, i))
        if propuesta_activa['activa']:
            if i in (0,1,2) and edicion_activa['seccion']!=i:return
            if edicion_activa['seccion'] is not None and i not in (edicion_activa['seccion'],3):return
        if i>0 and any(v is None for v in reparto['ids']):
            lbl_reparto.value='Confirma cada personaje antes de elegir la ubicación.'
            page.update()
            return
        if i>0 and es_vehicular(plan_escena) and not vehiculo_elegido['confirmado']:
            mostrar_vehiculos()
            return
        if i>2 and not clima_confirmado[0]:
            i=2
        if i == seccion_actual[0]:
            if i==3:refrescar_propuesta()
            return
        seccion_actual[0] = i
        if i==3:
            edicion_activa['seccion']=None
            refrescar_propuesta()
        ultimo_cambio[0] = time.monotonic()
        slide.top = -i * alto()
        slide.update()

    def abrir_edicion(i):
        edicion_activa['seccion']=i
        ir_a_seccion(i)
        if i==1:centrar_mapa()

    def desplazar_seccion(dy):
        if fase1_activa[0] or resultado_activo[0]:
            return
        if propuesta_activa['activa'] and seccion_actual[0]==3:return
        if sobre_mapa[0] and seccion_actual[0] == 1:
            return  # sobre el mapa la rueda hace zoom
        ahora = time.monotonic()
        if ahora - gesto_scroll["ultimo"] > 0.22:
            gesto_scroll.update(delta=0.0, consumido=False)
        gesto_scroll["ultimo"] = ahora
        if gesto_scroll["consumido"]:
            return
        if dy * gesto_scroll["delta"] < 0:
            gesto_scroll["delta"] = 0.0
        gesto_scroll["delta"] += dy
        if abs(gesto_scroll["delta"]) < 18:
            return
        if ahora - ultimo_cambio[0] < 0.55:
            return
        gesto_scroll["consumido"] = True
        ir_a_seccion(seccion_actual[0] + (1 if gesto_scroll["delta"] > 0 else -1))

    def on_rueda(e):
        dy = getattr(e, "scroll_delta_y", None)
        if dy is None:
            sd = getattr(e, "scroll_delta", None)
            dy = getattr(sd, "y", 0) if sd is not None else 0
        desplazar_seccion(dy)

    def al_iniciar_gesto(e):
        gesto_scroll.update(ultimo=0.0, delta=0.0, consumido=False)

    def al_deslizar_touchpad(e):
        # Windows/Flutter puede emitir pan/zoom en vez de eventos de rueda.
        if abs(e.scale - 1.0) > 0.03:
            return
        desplazar_seccion(-e.focal_point_delta.y)

    def on_tecla(e):
        if fase1_activa[0] or resultado_activo[0]:
            return
        if e.key in ("Arrow Down", "Page Down"):
            ir_a_seccion(seccion_actual[0] + 1)
        elif e.key in ("Arrow Up", "Page Up"):
            ir_a_seccion(seccion_actual[0] - 1)

    page.on_keyboard_event = on_tecla

    # ---------------------------------------------------------
    # SECCIÓN 1: PERSONAJE GIGANTE
    # ---------------------------------------------------------
    idx_actor = [0]
    reparto={'ids':[None], 'activo':0}
    vehiculo_elegido={'id':None,'confirmado':False,'indice':0}
    clima_confirmado=[False]
    captura_mostrada={}
    ambientacion_confirmada={}

    # Recortar solo para la vista: los PNG originales no se modifican.
    from functools import lru_cache
    from io import BytesIO
    from PIL import Image

    @lru_cache(maxsize=12)
    def imagen_actor(ruta):
        ligera=vista_asset(ruta)
        if ligera!=ruta:return ligera
        try:
            with Image.open(ASSETS / ruta) as imagen:
                imagen = imagen.convert("RGBA")
                limites = imagen.getchannel("A").getbbox()
                if limites:
                    imagen = imagen.crop(limites)
                salida = BytesIO()
                imagen.save(salida, format="PNG")
                return salida.getvalue()
        except (OSError, ValueError):
            return ruta

    img_actor = ft.Image(
        src=imagen_actor(ACTORES_BD["todos"][0][2]),
        fit=ft.BoxFit.CONTAIN,
        width=int(ancho() * 0.55),
        height=int(alto() * 0.70),
        visible=hay_actores,
    )

    vecinos_actor = []
    tarjetas_actor = []
    for paso in (-1, 1):
        vecino = ft.Image(
            src=imagen_actor(ACTORES_BD["todos"][paso % len(ACTORES_BD["todos"])][2]),
            fit=ft.BoxFit.CONTAIN,
            gapless_playback=True,
        )
        vecinos_actor.append(vecino)
        tarjetas_actor.append(ft.Container(
            content=ft.Stack([
                vecino,
                ft.Container(left=0, right=0, top=0, bottom=0, blur=3),
            ]),
            opacity=0.42,
            visible=hay_actores and len(ACTORES_BD["todos"]) > 1,
            on_click=lambda e, direccion=paso: nav_actor(direccion),
            tooltip="Personaje anterior" if paso == -1 else "Personaje siguiente",
        ))

    carrusel_actor = ft.Stack(
        [*tarjetas_actor, img_actor],
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    def dimensionar_carrusel(w, h):
        carrusel_actor.width = w
        carrusel_actor.height = int(h * 0.62)
        img_actor.width = int(w * 0.38)
        img_actor.height = carrusel_actor.height
        img_actor.left = (w - img_actor.width) / 2
        img_actor.top = 0
        for i, tarjeta in enumerate(tarjetas_actor):
            tarjeta.width = int(w * 0.27)
            tarjeta.height = int(carrusel_actor.height * 0.73)
            tarjeta.left = int(w * (0.03 if i == 0 else 0.70))
            tarjeta.top = (carrusel_actor.height - tarjeta.height) / 2
            tarjeta.content.width = tarjeta.width
            tarjeta.content.height = tarjeta.height
            vecinos_actor[i].width = tarjeta.width
            vecinos_actor[i].height = tarjeta.height

    dimensionar_carrusel(max(1, ancho() - 176), alto())

    lbl_actor_nom = ft.Text(
        f"| Personaje elegido: {eleccion_actor['nombre']} |",
        font_family=FUENTE, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500,
    )

    def nav_actor(step):
        lista = ACTORES_BD["todos"]
        idx_actor[0] = (idx_actor[0] + step) % len(lista)
        nombre, code, path = lista[idx_actor[0]]
        eleccion_actor.update({"id": code, "nombre": nombre})
        img_actor.src = imagen_actor(path)
        for imagen, paso in zip(vecinos_actor, (-1, 1)):
            imagen.src = imagen_actor(lista[(idx_actor[0] + paso) % len(lista)][2])
        lbl_actor_nom.value = f"| Personaje elegido: {nombre} |"
        if propuesta_activa['activa']:
            reparto['ids'][reparto['activo']]=int(code)
            refrescar_reparto()
        actualizar_vista(carrusel_actor)

    lbl_reparto=ft.Text('Personaje 1 de 1',size=28,weight=ft.FontWeight.W_600)
    slots_reparto=ft.Row(alignment=ft.MainAxisAlignment.CENTER,spacing=16)

    def elegir_slot(indice):
        reparto['activo']=indice
        codigo=reparto['ids'][indice]
        if codigo is not None:
            idx_actor[0]=next(i for i,(_,c,_) in enumerate(ACTORES_BD['todos']) if c==str(codigo))
            nav_actor(0)
        refrescar_reparto()
        page.update()

    def refrescar_reparto():
        slots_reparto.controls=[]
        for i,codigo in enumerate(reparto['ids']):
            foto=next((p for _,c,p in ACTORES_BD['todos'] if c==str(codigo)),None)
            contenido=ft.Image(src=imagen_actor(foto),width=58,height=76,fit=ft.BoxFit.CONTAIN) if foto else ft.Icon(ft.Icons.PERSON_OUTLINE,size=32,color=SECUNDARIO)
            slots_reparto.controls.append(ft.Container(content=contenido,width=86,height=96,
                alignment=ft.Alignment(0,0),border_radius=16,
                border=ft.Border.all(2,ACENTO if i==reparto['activo'] else BORDE),
                bgcolor=SUPERFICIE_ALTA if i==reparto['activo'] else SUPERFICIE,
                tooltip=f'Personaje {i+1}',on_click=lambda e,n=i:elegir_slot(n)))
        lbl_reparto.value=f"Personaje {reparto['activo']+1} de {len(reparto['ids'])}"

    def confirmar_personaje(e):
        reparto['ids'][reparto['activo']]=int(eleccion_actor['id'])
        if None in reparto['ids']:
            reparto['activo']=reparto['ids'].index(None)
            refrescar_reparto()
        else:
            refrescar_reparto()
            ir_a_seccion(3 if propuesta_activa['activa'] else 1)
        page.update()

    refrescar_reparto()

    fila_actor=ft.Row([
        ft.IconButton(icon=ft.Icons.CHEVRON_LEFT,icon_size=48,icon_color=SECUNDARIO,on_click=lambda e:nav_actor(-1)),
        carrusel_actor,
        ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT,icon_size=48,icon_color=SECUNDARIO,on_click=lambda e:nav_actor(1)),
    ],alignment=ft.MainAxisAlignment.CENTER,spacing=0)
    btn_confirmar_personaje=ft.TextButton('Confirmar personaje',height=52,style=estilo_boton(True),on_click=confirmar_personaje)
    cuerpo_actor=ft.Column([slots_reparto,fila_actor],spacing=20,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,scroll=ft.ScrollMode.AUTO,expand=True)
    seccion_actor = ft.Container(
        content=ft.Column([
            ft.Row([lbl_reparto,btn_confirmar_personaje],alignment=ft.MainAxisAlignment.SPACE_BETWEEN,wrap=True,run_spacing=12),
            cuerpo_actor,
        ],spacing=24,expand=True),
        height=alto(),
        width=ancho(),
        alignment=ft.Alignment(0, 0),
        padding=ft.Padding.symmetric(horizontal=24,vertical=28),
    )
    lista_vehiculos=disponibles('vehicles')
    foto_vehiculo=ft.Image(src=vista_asset(lista_vehiculos[0]['foto']) if lista_vehiculos else '',
        width=680,height=380,fit=ft.BoxFit.CONTAIN)
    lbl_vehiculo=ft.Text('',size=17)

    def nav_vehiculo(paso):
        if not lista_vehiculos:return
        vehiculo_elegido['indice']=(vehiculo_elegido['indice']+paso)%len(lista_vehiculos)
        v=lista_vehiculos[vehiculo_elegido['indice']]
        vehiculo_elegido.update(id=v['model_id'],confirmado=False)
        foto_vehiculo.src=vista_asset(v['foto'])
        lbl_vehiculo.value=v['nombre']
        page.update()

    def mostrar_vehiculos(e=None):
        panel_vehiculos.visible=True
        fila_actor.visible=slots_reparto.visible=btn_confirmar_personaje.visible=False
        lbl_reparto.value='Elige el vehículo de la escena'
        nav_vehiculo(0)
        ir_a_seccion(0)

    def confirmar_vehiculo(e):
        if vehiculo_elegido['id'] is None:return
        vehiculo_elegido['confirmado']=True
        ir_a_seccion(3 if propuesta_activa['activa'] else 1)

    def volver_al_personaje(e):
        panel_vehiculos.visible=False
        fila_actor.visible=slots_reparto.visible=btn_confirmar_personaje.visible=True
        refrescar_reparto()
        page.update()

    panel_vehiculos=ft.Column([
        lbl_vehiculo,ft.TextButton('Confirmar vehículo',height=52,style=estilo_boton(True),on_click=confirmar_vehiculo),
        ft.Row([ft.IconButton(icon=ft.Icons.CHEVRON_LEFT,on_click=lambda e:nav_vehiculo(-1)),foto_vehiculo,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT,on_click=lambda e:nav_vehiculo(1))],alignment=ft.MainAxisAlignment.CENTER),
        ft.TextButton('Cambiar personaje',on_click=volver_al_personaje),
    ],spacing=24,visible=False,horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    cuerpo_actor.controls.append(panel_vehiculos)

    # ---------------------------------------------------------
    # SECCIÓN 2: MAPA TÁCTICO YA ABIERTO (clic = colocar ubicación)
    # ---------------------------------------------------------
    TAM_MAPA = max(260, min(int(alto() * 0.66), ancho()-96, 640))
    vista_mapa=VistaMapa(TAM_MAPA)
    MUNDO = 6000.0  # coordenadas de -3000 a 3000

    def gta_a_px(x, y):
        return (x + 3000.0) / MUNDO * TAM_MAPA, (3000.0 - y) / MUNDO * TAM_MAPA

    def px_a_gta(px, py):
        return px / TAM_MAPA * MUNDO - 3000.0, 3000.0 - py / TAM_MAPA * MUNDO

    gestor_alturas = GestorAlturas()  # mismo gestor (con caché de tiles) que usa el visor PyQt

    def obtener_z(x, y):
        return gestor_alturas.obtener_z(x, y)

    def obtener_entorno(x, y, z):
        return str(detectar_entorno_gta(x, y, z)).lower()

    lbl_info_coordenadas = ft.Text(
        "", size=13, color=SECUNDARIO, text_align=ft.TextAlign.CENTER,
    )

    ini_x, ini_y = gta_a_px(eleccion_ubicacion["x"], eleccion_ubicacion["y"])
    marcador = ft.Container(
        left=ini_x - 14, top=ini_y - 28,
        width=28,height=28,
        content=ft.Icon(ft.Icons.LOCATION_ON, color=ACENTO, size=28),
    )
    marcador_destino = ft.Container(
        left=0, top=0, visible=False,
        width=28,height=28,
        content=ft.Icon(ft.Icons.FLAG, color=ft.Colors.BLUE_700, size=28),
    )

    def actualizar_ruta():
        estatica=es_estatica(plan_escena)
        px, py = vista_mapa.a_pantalla(*gta_a_px(eleccion_destino['x'], eleccion_destino['y']))
        marcador_destino.left, marcador_destino.top = px-14, py-28
        marcador_destino.visible = puntos_marcados['destino'] and not estatica
        distancia = math.hypot(eleccion_destino['x']-eleccion_ubicacion['x'], eleccion_destino['y']-eleccion_ubicacion['y'])
        lbl_ruta.value = (f"{distancia:.0f} m de recorrido" if all(puntos_marcados.values()) else
                          "Selecciona los dos puntos en el mapa")
        if estatica:
            lbl_ruta.value='Toca el mapa para elegir la ubicación'
        elif usa_recorrido_vehicular(plan_escena) and recorrido_coche['ruta']:
            r=recorrido_coche['ruta']
            lbl_ruta.value=f"{r['longitud']:.0f} m de recorrido"
        pintar_recorrido()

    lbl_ruta = ft.Text("Selecciona la ubicación", size=13, color=SECUNDARIO)

    def firma_ruta():
        return tuple(eleccion_ubicacion[k] for k in ('x','y','z')) + tuple(eleccion_destino[k] for k in ('x','y','z')) + (
            (recorrido_coche['ruta']['id'],) if usa_recorrido_vehicular(plan_escena) and recorrido_coche['ruta'] else ())

    def elegir_punto(tipo):
        modo_mapa['valor'] = tipo
        btn_inicio.bgcolor = ACENTO if tipo == 'inicio' else SUPERFICIE_ALTA
        btn_destino.bgcolor = ACENTO if tipo == 'destino' else SUPERFICIE_ALTA
        btn_inicio.content.color = TINTA if tipo == 'inicio' else TEXTO
        btn_destino.content.color = TINTA if tipo == 'destino' else TEXTO
        page.update()

    btn_inicio = ft.Container(content=ft.Text("Inicio",weight=ft.FontWeight.W_600,color=TINTA),
        padding=ft.Padding.symmetric(horizontal=24,vertical=13),border_radius=12,bgcolor=ACENTO,
        on_click=lambda e: elegir_punto('inicio'))
    btn_destino = ft.Container(content=ft.Text("Destino",weight=ft.FontWeight.W_600,color=TEXTO),
        padding=ft.Padding.symmetric(horizontal=24,vertical=13),border_radius=12,bgcolor=SUPERFICIE_ALTA,
        on_click=lambda e: elegir_punto('destino'))

    def usar_avenida_ejemplo(e):
        if usa_recorrido_vehicular(plan_escena) or plan_escena.get('accion')=='animacion_sobre_vehiculo':
            otra_ubicacion(e)
            return
        eleccion_ubicacion.update(dict(zip(('x','y','z'),POS_INICIO)), entorno='ciudad')
        eleccion_destino.update(dict(zip(('x','y','z'),POS_DESTINO)))
        puntos_marcados.update(inicio=True, destino=True)
        colocar_marcador(*POS_INICIO[:2])
        actualizar_ruta()
        lbl_info_coordenadas.value = "Recorrido de ejemplo seleccionado"
        page.update()

    def aplicar_recorrido(ruta):
        recorrido_coche['ruta']=ruta
        propuesta_activa['ruta_automatica']=True
        origen,_=puntos_entrada(ruta)
        if plan_escena.get('accion')=='animacion_sobre_vehiculo':origen=tuple(ruta['puntos'][0])
        eleccion_ubicacion.update(dict(zip(('x','y','z'),origen)),entorno='ciudad')
        eleccion_destino.update(dict(zip(('x','y','z'),ruta['puntos'][-1])))
        selector_ruta_auto.value=ruta['id']
        puntos_marcados.update(inicio=True,destino=True)
        colocar_marcador(*origen[:2]);actualizar_ruta()

    def otra_ubicacion(e):
        if usa_recorrido_vehicular(plan_escena) or plan_escena.get('accion')=='animacion_sobre_vehiculo':
            aplicar_recorrido(elegir_ruta_vehiculo(plan_escena.get('texto','')))
        elif es_estatica(plan_escena):
            lugar=elegir_ubicacion(plan_escena.get('entorno','ciudad'),plan_escena.get('texto',''))
            x,y,z=lugar['posicion']
            eleccion_ubicacion.update(x=x,y=y,z=z,entorno=lugar['entorno'])
            eleccion_destino.update(x=x,y=y+3,z=z)
            puntos_marcados.update(inicio=True,destino=True)
            colocar_marcador(x,y);actualizar_ruta()
            lbl_ruta.value=lugar['nombre']
        page.update()

    def seleccionar_ruta_auto(e):
        aplicar_recorrido(elegir_ruta_vehiculo(identificador=e.control.value))
        page.update()

    selector_ruta_auto=ft.Dropdown(label='Recorrido del vehículo',width=520,visible=False,
        options=[ft.DropdownOption(r['id'],r['nombre']) for r in rutas_vehiculos()],on_select=seleccionar_ruta_auto)
    btn_otra_ubicacion=ft.TextButton('Otra ubicación',icon=ft.Icons.SHUFFLE,on_click=otra_ubicacion,visible=False)

    def colocar_marcador(x, y):
        px, py = vista_mapa.a_pantalla(*gta_a_px(x, y))
        marcador.left = px - 14
        marcador.top = py - 28

    RUTA_MAPA_FIJA = "locations/sa_map_full.webp"  # relativa a assets_dir
    if (ASSETS/RUTA_MAPA_FIJA).exists():
        ruta_mapa = RUTA_MAPA_FIJA
    else:
        ruta_mapa = buscar_imagen_mapa()
    if ruta_mapa:
        fondo_mapa = ft.Image(src=ruta_mapa, width=TAM_MAPA, height=TAM_MAPA, fit=ft.BoxFit.FILL)
    else:
        fondo_mapa = ft.Container(
            width=TAM_MAPA, height=TAM_MAPA, bgcolor=ft.Colors.BLUE_GREY_100, alignment=ft.Alignment(0, 0),
            content=ft.Text(
                "Mapa no disponible", text_align=ft.TextAlign.CENTER, size=14,
            ),
        )

    def al_tocar_mapa(e):
        lx, ly = posicion_local(e, (TAM_MAPA / 2, TAM_MAPA / 2))
        lx,ly=vista_mapa.a_mapa(lx,ly)
        lx = max(0.0, min(float(TAM_MAPA), lx))
        ly = max(0.0, min(float(TAM_MAPA), ly))
        x, y = px_a_gta(lx, ly)
        if usa_recorrido_vehicular(plan_escena) or plan_escena.get('accion')=='animacion_sobre_vehiculo':
            indice=-1 if modo_mapa['valor']=='destino' else 0
            ruta=min(rutas_vehiculos(),key=lambda r:math.dist((x,y),r['puntos'][indice][:2]))
            aplicar_recorrido(ruta)
            lbl_info_coordenadas.value='Recorrido cercano seleccionado'
            page.update()
            return
        propuesta_activa['ruta_automatica']=False
        z = obtener_z(x, y)
        if plan_escena.get('tipo_movimiento')=='nadar':
            if z>0.5:
                lbl_info_coordenadas.value='Ese punto parece tierra. Marca una zona de agua para nadar.'
                page.update()
                return
            z=0.0
        if modo_mapa['valor'] == 'destino' and not es_estatica(plan_escena):
            eleccion_destino.update(x=x, y=y, z=z)
            puntos_marcados['destino'] = True
            actualizar_ruta()
            page.update()
            return
        entorno = obtener_entorno(x, y, z)
        eleccion_ubicacion.update({"x": x, "y": y, "z": z, "entorno": entorno})
        colocar_marcador(x, y)
        puntos_marcados['inicio'] = True
        actualizar_ruta()
        lbl_info_coordenadas.value = ''
        page.update()

    capa_mapa=ft.Container(content=fondo_mapa,left=0,top=0,width=TAM_MAPA,height=TAM_MAPA)
    linea_recorrido=cv.Canvas(width=TAM_MAPA,height=TAM_MAPA,left=0,top=0)
    def pintar_recorrido():
        linea_recorrido.shapes=[]
        if usa_recorrido_vehicular(plan_escena) and recorrido_coche['ruta']:
            puntos=[vista_mapa.a_pantalla(*gta_a_px(*p[:2])) for p in recorrido_coche['ruta']['puntos']]
        elif not es_estatica(plan_escena) and all(puntos_marcados.values()):
            puntos=[vista_mapa.a_pantalla(*gta_a_px(p['x'],p['y'])) for p in (eleccion_ubicacion,eleccion_destino)]
        else:return
        linea_recorrido.shapes=[cv.Path([cv.Path.MoveTo(*puntos[0]),*[cv.Path.LineTo(*p) for p in puntos[1:]]],
            paint=ft.Paint(stroke_width=4,color=ACENTO,style=ft.PaintingStyle.STROKE))]
    lienzo_mapa=ft.Stack([capa_mapa,linea_recorrido,marcador,marcador_destino],width=TAM_MAPA,height=TAM_MAPA,
        clip_behavior=ft.ClipBehavior.HARD_EDGE)
    escala_gesto=[1.0]

    def pintar_mapa():
        capa_mapa.left,capa_mapa.top=vista_mapa.x,vista_mapa.y
        capa_mapa.width=capa_mapa.height=TAM_MAPA*vista_mapa.escala
        fondo_mapa.width=fondo_mapa.height=TAM_MAPA*vista_mapa.escala
        colocar_marcador(eleccion_ubicacion['x'],eleccion_ubicacion['y'])
        px,py=vista_mapa.a_pantalla(*gta_a_px(eleccion_destino['x'],eleccion_destino['y']))
        marcador_destino.left,marcador_destino.top=px-14,py-28
        pintar_recorrido()
        actualizar_vista(lienzo_mapa)

    def zoom_mapa(e):
        sobre_mapa[0]=True
        delta=getattr(e,'scroll_delta',None)
        dy=getattr(e,'scroll_delta_y',getattr(delta,'y',0))
        px,py=posicion_local(e,(TAM_MAPA/2,TAM_MAPA/2))
        vista_mapa.zoom(math.exp(-max(-300,min(300,dy))*0.002),px,py)
        pintar_mapa()

    def iniciar_mapa(e):
        sobre_mapa[0]=True
        escala_gesto[0]=1.0

    def mover_mapa(e):
        sobre_mapa[0]=True
        p=e.local_focal_point
        vista_mapa.mover(e.focal_point_delta.x,e.focal_point_delta.y)
        vista_mapa.zoom(e.scale/escala_gesto[0],p.x,p.y)
        escala_gesto[0]=e.scale
        pintar_mapa()

    mapa_zoom=ft.GestureDetector(content=lienzo_mapa,on_tap_up=al_tocar_mapa,on_scroll=zoom_mapa,
        on_scale_start=iniciar_mapa,on_scale_update=mover_mapa,drag_interval=16,
        mouse_cursor=ft.MouseCursor.GRAB)

    def hover_mapa(e):
        sobre_mapa[0] = str(e.data).lower() == "true"

    def acercar_mapa(factor):
        vista_mapa.zoom(factor,TAM_MAPA/2,TAM_MAPA/2)
        pintar_mapa()

    def centrar_mapa(e=None):
        # Encuadra ambos extremos del recorrido; también sirve después de arrastrar.
        ini=gta_a_px(eleccion_ubicacion['x'],eleccion_ubicacion['y'])
        fin=ini if es_estatica(plan_escena) else gta_a_px(eleccion_destino['x'],eleccion_destino['y'])
        extension=max(abs(ini[0]-fin[0]),abs(ini[1]-fin[1]),TAM_MAPA/6)
        vista_mapa.escala=max(1,min(9,TAM_MAPA*.60/extension))
        vista_mapa.x=TAM_MAPA/2-(ini[0]+fin[0])/2*vista_mapa.escala
        vista_mapa.y=TAM_MAPA/2-(ini[1]+fin[1])/2*vista_mapa.escala
        vista_mapa.limitar()
        pintar_mapa()

    herramientas_mapa=panel(ft.Column([
        ft.IconButton(icon=ft.Icons.ADD,tooltip='Acercar mapa',icon_color=TEXTO,on_click=lambda e:acercar_mapa(1.4)),
        ft.IconButton(icon=ft.Icons.REMOVE,tooltip='Alejar mapa',icon_color=TEXTO,on_click=lambda e:acercar_mapa(1/1.4)),
        ft.IconButton(icon=ft.Icons.CENTER_FOCUS_STRONG,tooltip='Centrar recorrido',icon_color=ACENTO,on_click=centrar_mapa),
    ],spacing=2),padding=4,right=14,top=14)
    superficie_mapa=ft.Stack([mapa_zoom,herramientas_mapa],width=TAM_MAPA,height=TAM_MAPA)
    mapa_marco = ft.Container(
        content=superficie_mapa,
        width=TAM_MAPA, height=TAM_MAPA,
        border=ft.Border.all(1, BORDE),border_radius=24,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        on_hover=hover_mapa,
    )

    controles_ruta=ft.Row([btn_inicio,btn_destino,
        ft.IconButton(icon=ft.Icons.ROUTE,tooltip='Usar recorrido de ejemplo',on_click=usar_avenida_ejemplo)],
        alignment=ft.MainAxisAlignment.CENTER,spacing=12)
    ayuda_mapa=ft.Text('',size=12,color=SECUNDARIO,visible=False)
    seccion_mapa = ft.Container(
        content=ft.Column(
            [
                ft.Row([ft.Text("Ubicación",size=32,weight=ft.FontWeight.W_600),
                    ft.TextButton('Confirmar ubicación',height=52,style=estilo_boton(True),
                        on_click=lambda e:ir_a_seccion(3 if propuesta_activa['activa'] else 2))],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,wrap=True,run_spacing=12),
                ft.Column([
                    controles_ruta,selector_ruta_auto,mapa_marco,
                    ft.Row([lbl_ruta,btn_otra_ubicacion],alignment=ft.MainAxisAlignment.CENTER,spacing=20,wrap=True),
                    lbl_info_coordenadas,
                ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=20,scroll=ft.ScrollMode.AUTO,expand=True),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=24,expand=True,
        ),
        height=alto(),
        width=ancho(),
        alignment=ft.Alignment(0, 0),
        padding=ft.Padding.symmetric(horizontal=32,vertical=28),
    )

    # ---------------------------------------------------------
    # SECCIÓN 3: AMBIENTE Y PREVISUALIZACIÓN
    # ---------------------------------------------------------
    img_clima_centro = ft.Image(src="hora_12/none.jpg", fit=ft.BoxFit.COVER, width=420, height=260, visible=False)
    placeholder_clima = ft.Container(
        content=ft.Icon(ft.Icons.WB_SUNNY_OUTLINED,size=60,color=ACENTO),
        width=420,height=260,bgcolor=SUPERFICIE_ALTA,alignment=ft.Alignment(0,0),
    )
    lbl_hora_dial = ft.Text("12:00",size=17,weight=ft.FontWeight.W_600)
    lbl_clima_dial = ft.Text("Soleado",size=17,weight=ft.FontWeight.W_600)
    lbl_ambiente_propuesto=ft.Text('Elige la hora y el clima de la escena.',size=13,color=ft.Colors.GREY_600)

    def actualizar_imagen_tiempo_real():
        h = eleccion_hora["valor"]
        c = eleccion_clima["valor"]
        lbl_hora_dial.value = f"{h:02d}:00"
        lbl_clima_dial.value = NOMBRES_CLIMA[c]
        captura = preview_clima(h,c)
        lbl_hora_dial.value=f"{h%24:02d}:{((captura or {}).get('minuto') or 0):02d}"
        captura_mostrada.clear()
        captura_mostrada.update(hora=h%24,clima=c,minuto=0,archivo=None)
        if captura:
            captura_mostrada.update(hora=h%24,clima=captura['clima_id'],
                minuto=captura.get('minuto') or 0,archivo=captura['archivo'])
        preview = captura['archivo'] if captura else None
        origen=('Asociación estimada comparando las capturas; pendiente de comprobar en GTA.'
            if captura and captura.get('asociacion')=='estimacion_visual_secuencial' else
            'Asociación por orden de la tanda; pendiente de comprobar en GTA.')
        img_clima_centro.tooltip = (f"{h%24:02d}:{(captura.get('minuto') or 0):02d} · GAME_WEATHER={c}. "+origen
            if captura and not captura.get('verificado') else None)
        dial_clima.tooltip=f'GAME_WEATHER={c} · {NOMBRES_CLIMA[c]}'
        dial_hora.tooltip=f"{h%24:02d}:{((captura or {}).get('minuto') or 0):02d}"
        if preview:
            img_clima_centro.src = vista_asset(preview)
            img_clima_centro.visible = True
            placeholder_clima.visible = False
        else:
            img_clima_centro.visible = False
            placeholder_clima.visible = True
            icono = (ft.Icons.WATER_DROP if c in (8,16) else ft.Icons.CLOUD if c in (4,7,9,12,15,19)
                     else ft.Icons.WB_SUNNY_OUTLINED)
            placeholder_clima.content = ft.Column([
                ft.Icon(icono,size=64,color=ft.Colors.BLUE_GREY_500),
                ft.Text(NOMBRES_CLIMA[c],size=18,weight=ft.FontWeight.BOLD,text_align=ft.TextAlign.CENTER),
                ft.Text("No hay fotos disponibles para esta hora",size=12,color=ft.Colors.GREY_700),
            ],alignment=ft.MainAxisAlignment.CENTER,horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        actualizar_vista(relojes_panel)

    # --- Reloj de horas (0 a 24, arriba = 0/24) ---
    def al_cambiar_hora(frac):
        previo = eleccion_hora["valor"]
        v = int(round(frac * 24))
        if v >= 24 or v == 0:
            v = 24 if previo >= 12 else 0
        if v == previo:
            return
        eleccion_hora["valor"] = v
        clima_confirmado[0]=False
        set_frac_hora(v / 24)
        actualizar_imagen_tiempo_real()

    dial_hora=ft.Slider(min=0,max=23,divisions=23,value=12,label="{value} h",
        active_color=ACENTO,
        on_change=lambda e:al_cambiar_hora(float(e.control.value)/24))

    def set_frac_hora(frac):
        dial_hora.value=max(0,min(23,round(frac*24)))

    # --- Reloj de clima (1 a 45) ---
    def al_cambiar_clima(frac):
        v = int(round(frac * 23)) % 23
        delta=(v-eleccion_clima['valor']+11)%23-11
        disponible=clima_con_foto(eleccion_hora['valor'],v,1 if delta>=0 else -1)
        if disponible is not None:
            v=disponible
        set_frac_clima(v/23)
        if v == eleccion_clima["valor"]:
            page.update()
            return
        eleccion_clima["valor"] = v
        clima_confirmado[0]=False
        set_frac_clima(v / 23)
        actualizar_imagen_tiempo_real()

    dial_clima=ft.Slider(min=0,max=22,divisions=22,value=0,label="Clima {value}",
        active_color=ACENTO,
        on_change=lambda e:al_cambiar_clima(float(e.control.value)/23))

    def set_frac_clima(frac):
        dial_clima.value=max(0,min(22,round(frac*23)))

    vista_clima=ft.Stack([placeholder_clima,img_clima_centro])
    marco_clima=ft.Container(content=vista_clima,border_radius=20,clip_behavior=ft.ClipBehavior.HARD_EDGE)
    relojes_panel=ft.Column([
        marco_clima,
        ft.Column([lbl_hora_dial,dial_hora],spacing=0),
        ft.Column([lbl_clima_dial,dial_clima],spacing=0),
    ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=24)

    def dimensionar_clima():
        w=int(min(1000,max(240,ancho()-80),max(180,alto()-300)*16/9))
        h=round(w*9/16)
        for control in (img_clima_centro,placeholder_clima,vista_clima,marco_clima):
            control.width,control.height=w,h
        img_clima_centro.fit=ft.BoxFit.CONTAIN
        dial_hora.width=dial_clima.width=w
        relojes_panel.width=w

    dimensionar_clima()

    def set_camara(tipo, btn_ref):
        eleccion_camara["tipo"] = tipo
        for b in [btn_cam_auto,btn_cam_pov,btn_cam_3p,btn_cam_lateral,btn_cam_fija,btn_cam_giro]:
            b.bgcolor = SUPERFICIE
            b.border=ft.Border.all(1,BORDE)
        btn_ref.bgcolor = SUPERFICIE_ALTA
        btn_ref.border=ft.Border.all(2,ACENTO)
        page.update()

    btn_cam_auto=ft.Container(content=ft.Column([
        ft.Icon(ft.Icons.SWITCH_VIDEO_OUTLINED,size=84,color=ACENTO),
        ft.Text('Montaje automático',size=17,weight=ft.FontWeight.W_600),
        ft.Text('Cambia de plano cada 5 segundos',size=13,color=SECUNDARIO),
    ],spacing=16,horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER),
        width=376,height=265,padding=18,border=ft.Border.all(2,ACENTO),border_radius=20,bgcolor=SUPERFICIE_ALTA,
        on_click=lambda e:set_camara('Montaje automático',btn_cam_auto))
    btn_cam_pov = ft.Container(
        content=ft.Text("Desde el asiento del vehículo", font_family=FUENTE, weight=ft.FontWeight.BOLD),
        padding=18,border=ft.Border.all(1,BORDE),border_radius=20,bgcolor=SUPERFICIE,
        disabled=True, opacity=0.35, tooltip="Encuadre interior del ejemplo de vehículo",
        on_click=lambda e: set_camara("POV (Primera Persona)", btn_cam_pov),
    )
    btn_cam_3p = ft.Container(
        content=ft.Text("Seguimiento desde atrás", font_family=FUENTE, weight=ft.FontWeight.BOLD),
        padding=18,border=ft.Border.all(1,BORDE),border_radius=20,bgcolor=SUPERFICIE,
        on_click=lambda e: set_camara("Tercera Persona", btn_cam_3p),
    )
    btn_cam_lateral = ft.Container(
        content=ft.Text("Seguimiento de costado", font_family=FUENTE, weight=ft.FontWeight.BOLD),
        padding=18,border=ft.Border.all(1,BORDE),border_radius=20,bgcolor=SUPERFICIE,
        on_click=lambda e: set_camara("Seguimiento lateral", btn_cam_lateral),
    )
    btn_cam_fija = ft.Container(
        content=ft.Text("Fija elevada (ejemplo)", font_family=FUENTE, weight=ft.FontWeight.BOLD),
        padding=18,border=ft.Border.all(1,BORDE),border_radius=20,bgcolor=SUPERFICIE,
        on_click=lambda e: set_camara("Cámara Fija Cinematográfica", btn_cam_fija),
    )
    btn_cam_giro=ft.Container(content=ft.Column([
        ft.Icon(ft.Icons.ROTATE_RIGHT,size=96,color=ACENTO),
        ft.Text('Giro suave por delante',size=16),
    ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER),
        width=360,height=260,padding=18,border=ft.Border.all(1,BORDE),border_radius=20,bgcolor=SUPERFICIE,
        on_click=lambda e:set_camara('Giro frontal',btn_cam_giro))
    lbl_camara_auto=ft.Text('Al conducir, la cámara quedará vinculada al coche después de que suba el personaje.',
        visible=False,text_align=ft.TextAlign.CENTER)
    for tarjeta,imagen,nombre in [(btn_cam_3p,'trasera','Tercera persona'),
        (btn_cam_lateral,'costado','De costado'),(btn_cam_fija,'elevada','Elevada')]:
        tarjeta.padding=18
        tarjeta.content=ft.Column([
            ft.Image(src=f'camaras/{imagen}.png',width=320,height=180,fit=ft.BoxFit.COVER,border_radius=12),
            ft.Text(nombre,size=16,text_align=ft.TextAlign.CENTER),
        ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=16)

    def dimensionar_camaras():
        w=max(200,min(340,(ancho()-160)/2))
        h=round(w*9/16)
        for tarjeta in (btn_cam_3p,btn_cam_lateral,btn_cam_fija):
            tarjeta.content.controls[0].width=w
            tarjeta.content.controls[0].height=h
        btn_cam_auto.width=btn_cam_giro.width=btn_cam_pov.width=w+36
        btn_cam_auto.height=btn_cam_giro.height=btn_cam_pov.height=h+74
        btn_cam_giro.content.controls[0].size=min(86,h*.7)
    dimensionar_camaras()

    def confirmar_clima(e):
        if not captura_mostrada:
            return
        ambientacion_confirmada.clear()
        ambientacion_confirmada.update(captura_mostrada)
        clima_confirmado[0]=True
        ir_a_seccion(3)

    def confirmar_camara(e):
        ir_a_seccion(4)

    lbl_duracion = ft.Text("Duración del plano: 10 segundos", font_family=FUENTE, size=14)

    def cambiar_duracion(e):
        nombre='Duración de la conducción' if usa_recorrido_vehicular(plan_escena) else 'Duración del plano'
        lbl_duracion.value = f"{nombre}: {round(float(e.control.value))} segundos"
        page.update()

    slider_duracion = ft.Slider(min=1, max=60, divisions=59, value=10, label="{value} s",
        width=440, on_change=cambiar_duracion)
    lbl_velocidad=ft.Text('Velocidad del vehículo: 35 km/h',visible=False)
    def cambiar_velocidad(e):
        lbl_velocidad.value=f'Velocidad del vehículo: {round(float(e.control.value))} km/h'
        page.update()
    slider_velocidad=ft.Slider(min=10,max=90,divisions=80,value=35,label='{value} km/h',width=440,
        visible=False,on_change=cambiar_velocidad)
    campo_dialogos = ft.TextField(label="Diálogos (opcional, una frase por línea)", multiline=True,
        min_lines=1, max_lines=3, width=680,
        hint_text="Personaje: Debo llegar antes de que anochezca.")
    categoria_musica=ft.Dropdown(label='Banda sonora',value='ninguna',width=270,
        options=[ft.DropdownOption('ninguna','Sin música'),ft.DropdownOption('mistica','Mística · Backrooms'),ft.DropdownOption('feliz','Feliz')])
    pista_musica=ft.Dropdown(label='Canción',value='aleatoria',width=360,visible=False)
    lbl_musica=ft.Text('Sin banda sonora seleccionada.',size=13,color=SECUNDARIO)

    def actualizar_pistas(e=None):
        lista=pistas(categoria_musica.value) if categoria_musica.value!='ninguna' else []
        pista_musica.visible=categoria_musica.value!='ninguna'
        pista_musica.options=[ft.DropdownOption('aleatoria','Elegir una canción al generar')]+[
            ft.DropdownOption(p,p.rsplit('/',1)[-1]) for p in lista]
        pista_musica.value='aleatoria'
        lbl_musica.value=(f'{len(lista)} canciones disponibles.' if lista else
            'Esta categoría aún no tiene canciones. Añade audio a la carpeta de música de la aplicación.' if pista_musica.visible else
            'Sin banda sonora seleccionada.')
        page.update()

    categoria_musica.on_select=actualizar_pistas
    lbl_exportacion = ft.Text("", selectable=True, size=13, text_align=ft.TextAlign.CENTER)
    archivo_resultado = {"ruta": None, "contenido": "",'banda_sonora':None}
    selector_archivo = ft.FilePicker()
    portapapeles = ft.Clipboard()
    page.services.extend([selector_archivo, portapapeles])
    vista_archivo = ft.TextField(value="", read_only=True, multiline=True, min_lines=6,max_lines=12,
        text_size=13, text_style=ft.TextStyle(font_family=FUENTE,color=SECUNDARIO),
        border=ft.OutlineInputBorder(border_radius=12),border_color=BORDE)
    lbl_archivo_nombre = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
    lbl_resultado_estado = ft.Text("", size=14,selectable=True)

    async def copiar_mms(e):
        try:
            archivos=await asyncio.to_thread(dependencias,archivo_resultado['ruta'])
            if len(archivos)>1:
                # Una escena con recursos externos se entrega completa al archivo destino.
                # Copiar solo el MMS deja Carrec y Sounds de la misión anterior en el juego.
                await guardar_mms_como(e)
                return
            await portapapeles.set(archivo_resultado['contenido'])
            lbl_resultado_estado.value = "Contenido del .mms copiado al portapapeles."
        except Exception as error:
            lbl_resultado_estado.value = 'No se completó la copia: '+str(error)+'. Usa Guardar paquete completo.'
        page.update()

    async def guardar_mms_como(e):
        try:
            ruta = await selector_archivo.save_file(dialog_title="Guardar misión completa",
                file_name=archivo_resultado['ruta'].name,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['mms'])
            lbl_resultado_estado.value = "Archivo guardado en la ubicación elegida." if ruta else "Guardado cancelado."
            if ruta:
                await asyncio.to_thread(guardar_como,archivo_resultado['ruta'],ruta)
                lbl_resultado_estado.value='Misión completa guardada en '+os.path.dirname(ruta)+'. Reinicia GTA y carga esa carpeta en Mission Maker.'
        except (OSError,ValueError) as error:
            lbl_resultado_estado.value = "No se pudo completar el guardado: "+str(error)
        page.update()

    async def guardar_paquete_musica(e):
        try:
            contenido=await asyncio.to_thread(zip_mision,archivo_resultado['ruta'])
            ruta=await selector_archivo.save_file(dialog_title='Guardar misión completa',
                file_name=archivo_resultado['ruta'].stem+'.zip',file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=['zip'],src_bytes=contenido)
            lbl_resultado_estado.value='Paquete guardado. Extrae todo el ZIP en una carpeta propia dentro de modloader/SAMM(Stable), antes de cargar la misión.' if ruta else 'Guardado cancelado.'
        except (OSError,ValueError) as error:
            lbl_resultado_estado.value=str(error)
        page.update()

    async def instalar_en_gta(e):
        from src.ajustes import ajustes
        gta=ajustes().get('gta_path','')
        try:
            if not gta:
                gta=await selector_archivo.get_directory_path(dialog_title='Selecciona la carpeta que contiene gta_sa.exe o gta.exe')
                if not gta:return
            destino=await asyncio.to_thread(instalar_mision,archivo_resultado['ruta'],gta)
            lbl_resultado_estado.value=f'Instalada en {destino.name}. Carga esa misión en Mission Maker. Si GTA estaba abierto, reinícialo para cargar los recorridos.'
        except (ValueError,OSError) as error:lbl_resultado_estado.value=str(error)
        page.update()

    def volver_edicion(e):
        resultado_activo[0] = False
        panel_resultado.visible = False
        panel_fase2.visible = True
        page.update()

    def volver_inicio(e):
        resultado_activo[0]=False
        fase1_activa[0]=True
        panel_resultado.visible=panel_fase2.visible=False
        for control in (contenedor_titulo,cuadro_texto,controles_inferiores,espacio_superior,espacio_relleno):
            control.visible=True
        contenedor_titulo.opacity=controles_inferiores.opacity=1
        campo.disabled=False
        btn_random.disabled=False
        lbl_analisis.value=''
        page.scroll=ft.ScrollMode.AUTO
        page.padding=32
        set_boton(bool((campo.value or '').strip()))
        page.update()

    btn_copiar_mms=ft.TextButton("Copiar contenido",on_click=copiar_mms)
    btn_corregir=ft.TextButton('Corregir interpretación',on_click=lambda e:abrir_correcciones(e))
    panel_resultado = ft.Container(visible=False, width=ancho(), height=alto(), padding=36,
        content=ft.Column([
            ft.Row([ft.TextButton('Volver a editar',icon=ft.Icons.ARROW_BACK,on_click=volver_edicion),
                ft.TextButton('Nueva escena',on_click=volver_inicio)],alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=8),
            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE,size=48,color=ACENTO),
            ft.Text("Tu misión está lista",size=36,weight=ft.FontWeight.W_600),
            ft.Text('Guarda la escena con todos sus recursos para reproducirla en el juego.',size=15,color=SECUNDARIO),
            panel(ft.Column([
                lbl_archivo_nombre,
                ft.Text('Guarda dentro de modloader / SAMM(Stable) / una carpeta para tu misión.',
                    size=13,color=SECUNDARIO),
                ft.Row([ft.TextButton("Guardar misión completa...",icon=ft.Icons.DOWNLOAD_OUTLINED,
                    height=54,style=estilo_boton(True),on_click=guardar_mms_como),
                    ft.TextButton('Instalar en GTA',height=54,icon=ft.Icons.SPORTS_ESPORTS_OUTLINED,on_click=instalar_en_gta)],
                    wrap=True,spacing=16,run_spacing=12),
                lbl_resultado_estado,
                instruccionesguardar_mision(),
                ft.ExpansionTile(title=ft.Text('Archivos de la misión',size=15),controls=[vista_archivo]),
                ft.Row([ft.TextButton('Guardar paquete ZIP',on_click=guardar_paquete_musica),btn_copiar_mms,btn_corregir],
                    spacing=16,wrap=True,run_spacing=10),
            ],spacing=24),width=920),
        ],spacing=20,scroll=ft.ScrollMode.AUTO,horizontal_alignment=ft.CrossAxisAlignment.CENTER,expand=True))

    generando=[False]
    lbl_error_resumen=ft.Text('',color=ft.Colors.RED_700,text_align=ft.TextAlign.CENTER,width=800)
    def avisar_exportacion(texto):
        lbl_exportacion.value=texto
        lbl_error_resumen.value=texto

    async def on_crear_mms(e):
        if generando[0]:return
        avisar_exportacion('')
        if any(v is None for v in reparto['ids']):
            avisar_exportacion('Confirma todos los personajes del reparto.')
            page.update()
            return
        if es_vehicular(plan_escena) and not vehiculo_elegido['confirmado']:
            avisar_exportacion('Confirma el vehículo que deseas usar.')
            page.update()
            return
        estatica=es_estatica(plan_escena)
        conduccion=usa_recorrido_vehicular(plan_escena)
        if not puntos_marcados['inicio'] or (not estatica and not puntos_marcados['destino']):
            avisar_exportacion("Primero marca inicio y destino en el mapa, o usa la avenida del ejemplo.")
            page.update()
            return
        firma = firma_ruta()
        if (conduccion or plan_escena.get('accion')=='animacion_sobre_vehiculo') and not recorrido_coche['ruta']:
            avisar_exportacion('Elige un recorrido de vehículo.')
            page.update()
            return
        if not estatica and not conduccion and not 2 <= math.dist(firma[:2],firma[3:5]) <= 150:
            avisar_exportacion("El recorrido debe medir entre 2 y 150 metros. Acerca el destino en el mapa.")
            page.update()
            return
        perfil = evaluar_perfil(firma[:3],firma[3:6],obtener_z,tipo=plan_escena.get('tipo_movimiento','caminar'),
            superficie=plan_escena.get('lugar_tipo')) if not estatica and not conduccion and plan_escena.get('tipo_movimiento')!='nadar' else None
        if perfil and perfil['estado']=='bloqueada':
            avisar_exportacion(perfil['mensaje'])
            page.update()
            return
        if not clima_confirmado[0] or not ambientacion_confirmada:
            avisar_exportacion('Confirma el clima que aparece en la foto antes de generar.')
            page.update()
            return
        generando[0]=True
        btn_crear.disabled = btn_generar_resumen.disabled = True
        avisar_exportacion("Generando la escena...")
        page.update()
        try:
            banda=None
            if categoria_musica.value!='ninguna':
                lista=pistas(categoria_musica.value)
                if not lista:raise ValueError('Esta categoría no tiene canciones. Añade archivos o selecciona Sin música.')
                banda=random.choice(lista) if pista_musica.value=='aleatoria' else pista_musica.value
            ruta = await asyncio.to_thread(exportar_escena,
                actor_id=reparto['ids'][0], actores_ids=list(reparto['ids']),
                inicio=tuple(eleccion_ubicacion[k] for k in ('x','y','z')),
                destino=None if estatica else tuple(eleccion_destino[k] for k in ('x','y','z')),
                duracion=round(slider_duracion.value), hora=ambientacion_confirmada['hora'],
                clima=ambientacion_confirmada['clima'],
                minuto=ambientacion_confirmada['minuto'], titulo="Escena cinematográfica",
                camara={'Montaje automático':'automatica','Tercera Persona':'seguimiento_trasero',
                    'Seguimiento lateral':'costado','Giro frontal':'giro_frontal',
                    'POV (Primera Persona)':'vehiculo_pov','Cámara Fija Cinematográfica':'fija'}[eleccion_camara['tipo']],
                dialogos=[t.strip() for t in (campo_dialogos.value or '').splitlines() if t.strip()],
                accion=plan_escena.get('accion','caminar'),
                vehiculo_en_movimiento=plan_escena.get('vehiculo_en_movimiento',False),
                pasos=plan_escena.get('pasos',[]),roles=plan_escena.get('roles',[]),
                tipo_movimiento=plan_escena.get('tipo_movimiento','caminar'),
                perfil_recorrido=perfil['puntos'] if perfil else None,
                adaptar_camara=True,
                banda_sonora=banda,
                reproduccion=plan_escena.get('reproduccion','auto'),
                vehiculo_id=vehiculo_elegido['id'] if es_vehicular(plan_escena) else None,
                ruta_vehiculo_id=recorrido_coche['ruta']['id'] if conduccion or plan_escena.get('accion')=='animacion_sobre_vehiculo' else None,
                velocidad_kmh=round(slider_velocidad.value),
                animacion_sugerida=plan_escena.get('animacion_sugerida'),
                animar_actores=plan_escena.get('animar_actores',[1]),
                descripcion=plan_escena['texto'], plan=dict(plan_escena))
            archivo_resultado.update(ruta=ruta, contenido=ruta.read_bytes().decode('utf-8'),banda_sonora=banda)
            archivos=await asyncio.to_thread(dependencias,ruta)
            tiene_auxiliares=len(archivos)>1
            btn_copiar_mms.visible=not tiene_auxiliares
            vista_archivo.value = (
                'Guarda o instala la misión completa para usar recorrido y música.\n\n'
                'Archivos de esta escena:\n'+'\n'.join('• '+nombre for nombre in archivos)+
                '\n\nOrigen: '+str(ruta.parent)+
                '\n\nUsa «Guardar misión completa...» para elegir el archivo del juego, '
                'o «Instalar en GTA» para crear una misión propia.'
            ) if tiene_auxiliares else archivo_resultado['contenido']
            lbl_archivo_nombre.value = ruta.name
            lbl_resultado_estado.value = 'Escena generada. Guarda la misión completa o instálala en GTA.'
            if plan_escena.get('accion')=='animacion_sobre_vehiculo':
                lbl_resultado_estado.value+=' Composición experimental: altura y anclaje pendientes de revisar en GTA.'
            if perfil and perfil['estado']=='incierto':lbl_resultado_estado.value+=' '+perfil['mensaje']
            resultado_activo[0] = True
            panel_fase2.visible = False
            panel_resultado.visible = True
            avisar_exportacion("")
        except (ValueError, OSError) as error:
            avisar_exportacion(str(error))
        finally:
            generando[0]=False
            btn_crear.disabled = btn_generar_resumen.disabled = False
            page.update()

    btn_crear = boton_glitch('Generar cinemática',on_crear_mms,ft.Icons.MOVIE_OUTLINED)

    seccion_relojes = ft.Container(
        content=ft.Column(
            [
                ft.Text('Ambiente',size=32,weight=ft.FontWeight.W_600),
                relojes_panel,
                lbl_ambiente_propuesto,
                ft.TextButton('Confirmar',height=52,style=estilo_boton(True),on_click=confirmar_clima),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=24,scroll=ft.ScrollMode.AUTO,
        ),height=alto(),width=ancho(),alignment=ft.Alignment(0,0),
        padding=ft.Padding.symmetric(horizontal=32,vertical=28),
    )

    resumen_propuesta=ft.Text('',width=820,size=16,color=SECUNDARIO,text_align=ft.TextAlign.CENTER)
    fotos_propuesta=ft.Row(alignment=ft.MainAxisAlignment.CENTER,spacing=12)
    aviso_propuesta=ft.Text('',size=12,color=SECUNDARIO,text_align=ft.TextAlign.CENTER,visible=False)
    def refrescar_propuesta():
        resumen_propuesta.value=plan_escena.get('texto','')
        con_vehiculo=vehiculo_elegido['id'] is not None and es_vehicular(plan_escena)
        columnas=min(3,max(1,int((ancho()-40)//354)))
        ancho_tarjeta=max(260,min(420,(ancho()-72-24*(columnas-1))/columnas))
        for tarjeta in (tarjeta_personajes,tarjeta_ambiente,tarjeta_ubicacion,tarjeta_vehiculo,tarjeta_camara):tarjeta.width=ancho_tarjeta
        ancho_vista=int(ancho_tarjeta-40)
        fotos_propuesta.controls=[ft.Image(src=imagen_actor(f'actors/{codigo}.png'),width=48,height=68,fit=ft.BoxFit.CONTAIN) for codigo in reparto['ids'] if codigo is not None]
        if plan_escena.get('accion')=='vehiculo_autonomo':fotos_propuesta.controls=[]
        n=max(1,len(reparto['ids']))
        vista_personajes.content=ft.Row([ft.Image(src=imagen_actor(f'actors/{codigo}.png'),width=min(130,(ancho_vista-18)/n),
            height=216,fit=ft.BoxFit.CONTAIN) for codigo in reparto['ids'] if codigo is not None],
            alignment=ft.MainAxisAlignment.CENTER,spacing=6)
        tarjeta_personajes.visible=plan_escena.get('accion')!='vehiculo_autonomo'
        tarjeta_vehiculo.visible=con_vehiculo
        vista_vehiculo.content=ft.Image(src=foto_vehiculo.src,width=ancho_vista,height=216,fit=ft.BoxFit.CONTAIN)
        vista_ambiente.content=ft.Column([
            ft.Image(src=img_clima_centro.src,width=ancho_vista,height=178,fit=ft.BoxFit.COVER,border_radius=12) if img_clima_centro.visible else ft.Icon(ft.Icons.CLOUD_OUTLINED,size=72,color=ACENTO),
            ft.Text(f'{eleccion_hora["valor"]%24:02d}:00 · {NOMBRES_CLIMA[eleccion_clima["valor"]]}',size=12,text_align=ft.TextAlign.CENTER),
        ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=4)
        from src.resumen_escena import miniatura_ubicacion
        ini=tuple(eleccion_ubicacion[k] for k in ('x','y','z'))
        fin=None if es_estatica(plan_escena) else tuple(eleccion_destino[k] for k in ('x','y','z'))
        vista_ubicacion.content=miniatura_ubicacion(ruta_mapa or 'locations/sa_map_full.webp',ini,fin,width=ancho_vista,height=216)
        nombre=eleccion_camara['tipo']
        foto={'Tercera Persona':'trasera','Seguimiento lateral':'costado','Cámara Fija Cinematográfica':'elevada'}.get(nombre)
        icono=(ft.Icons.SWITCH_VIDEO_OUTLINED if nombre=='Montaje automático' else
            ft.Icons.ROTATE_RIGHT if nombre=='Giro frontal' else ft.Icons.DIRECTIONS_CAR)
        imagen=(ft.Image(src=f'camaras/{foto}.png',width=ancho_vista,height=178,fit=ft.BoxFit.COVER,border_radius=12) if foto else
            ft.Icon(icono,size=90,color=ACENTO))
        if es_vehicular(plan_escena) and nombre=='Tercera Persona':nombre='Exterior del vehículo'
        detalle='Seguimiento, entorno y plano general · cada 5 s' if nombre=='Montaje automático' else 'Un encuadre durante toda la escena'
        vista_camara.content=ft.Column([imagen,ft.Text(nombre,size=15),ft.Text(detalle,size=12,color=SECUNDARIO)],
            spacing=12,horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        aviso_propuesta.value=plan_escena.get('limitaciones',[''])[0] if plan_escena.get('limitaciones') else ''
        aviso_propuesta.visible=bool(aviso_propuesta.value)
        tarjeta_duracion.width=ancho_tarjeta
        slider_duracion.width=ancho_vista

    def editar_vehiculo(e):
        edicion_activa['seccion']=0
        mostrar_vehiculos(e)

    def editar_camara(e):
        edicion_activa['seccion']='camara'
        resumen_panel.visible=False
        panel_edicion_camara.visible=True
        page.update()

    def confirmar_edicion_camara(e):
        edicion_activa['seccion']=None
        panel_edicion_camara.visible=False
        resumen_panel.visible=True
        refrescar_propuesta()
        page.update()

    from src.resumen_escena import tarjeta
    tarjeta_personajes,vista_personajes,_=tarjeta('Personajes',fotos_propuesta,lambda e:abrir_edicion(0))
    tarjeta_ambiente,vista_ambiente,_=tarjeta('Clima y hora',ft.Container(),lambda e:abrir_edicion(2))
    tarjeta_ubicacion,vista_ubicacion,_=tarjeta('Ubicación',ft.Container(),lambda e:abrir_edicion(1))
    tarjeta_camara,vista_camara,_=tarjeta('Cámara',ft.Container(),editar_camara)
    tarjeta_vehiculo,vista_vehiculo,_=tarjeta('Vehículo',ft.Container(),editar_vehiculo)
    tarjeta_vehiculo.visible=False
    tarjeta_duracion,_,_=tarjeta('Duración',ft.Column([
        ft.Icon(ft.Icons.TIMER_OUTLINED,size=42,color=ACENTO),lbl_duracion,slider_duracion],spacing=24,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER),width=420)
    slider_duracion.width=350
    btn_generar_resumen=boton_glitch('Generar cinemática',on_crear_mms,ft.Icons.MOVIE_OUTLINED)
    galeria_resumen=ft.Row([tarjeta_personajes,tarjeta_ambiente,tarjeta_ubicacion,tarjeta_vehiculo,tarjeta_camara,tarjeta_duracion],
        alignment=ft.MainAxisAlignment.CENTER,wrap=True,run_spacing=24,spacing=24)
    resumen_panel=ft.Column([
        ft.Row([ft.Text('Tu escena',size=34,weight=ft.FontWeight.W_600),btn_generar_resumen],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,spacing=28,wrap=True,run_spacing=14),
        resumen_propuesta,
        ft.Column([galeria_resumen],scroll=ft.ScrollMode.AUTO,expand=True),
        lbl_error_resumen,
        ft.Row([ft.TextButton('Música y diálogos',on_click=confirmar_camara),
            ft.TextButton('Cambiar descripción',on_click=volver_inicio)],
            alignment=ft.MainAxisAlignment.CENTER,spacing=18,wrap=True),aviso_propuesta,
    ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=24,expand=True)
    panel_edicion_camara=ft.Column([
        ft.Text('Elige la cámara',size=32,weight=ft.FontWeight.W_600),
        ft.Text('El montaje alterna planos cada 5 s. Las otras opciones mantienen un único encuadre.',
            size=13,color=SECUNDARIO,text_align=ft.TextAlign.CENTER),
        ft.TextButton('Confirmar cámara',height=52,style=estilo_boton(True),on_click=confirmar_edicion_camara),
        ft.Column([ft.Row([btn_cam_auto,btn_cam_3p,btn_cam_lateral,btn_cam_fija,btn_cam_giro,btn_cam_pov],
            alignment=ft.MainAxisAlignment.CENTER,spacing=24,run_spacing=24,wrap=True),lbl_camara_auto],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=20,scroll=ft.ScrollMode.AUTO,expand=True),
    ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=24,visible=False,expand=True)
    seccion_camaras=ft.Container(content=ft.Column([resumen_panel,panel_edicion_camara],expand=True),
        padding=ft.Padding(32,32,32,24),height=alto(),width=ancho(),alignment=ft.Alignment(0,0))

    seccion_exportar=ft.Container(
        content=ft.Column([
                encabezado('Sonido y diálogo','Añade una banda sonora y subtítulos a tu escena.'),
                panel(ft.Column([
                    lbl_velocidad,slider_velocidad,campo_dialogos,
                    ft.Row([categoria_musica,pista_musica],wrap=True,spacing=20,run_spacing=20),
                    lbl_musica,ft.TextButton('Actualizar canciones',on_click=actualizar_pistas),
                ],spacing=28),width=820),
                btn_crear,
                lbl_exportacion,
                ft.TextButton('Volver a la escena',on_click=lambda e:ir_a_seccion(3)),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=28,scroll=ft.ScrollMode.AUTO,
        ),
        height=alto(),
        width=ancho(),
        alignment=ft.Alignment(0, 0),
        padding=ft.Padding.symmetric(horizontal=32,vertical=28),
    )

    secciones = [seccion_actor, seccion_mapa, seccion_relojes, seccion_camaras, seccion_exportar]

    # ---------------------------------------------------------
    # CONTENEDOR FASE 2: tira vertical que se desliza con animación (60 fps)
    # ---------------------------------------------------------
    slide = ft.Container(
        content=ft.Column(secciones, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        left=0,
        top=0,
        width=ancho(),
        height=alto() * TOTAL_SECCIONES,
        animate_position=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
    )

    viewport = ft.Stack([slide], width=ancho(), height=alto(), clip_behavior=ft.ClipBehavior.HARD_EDGE)

    panel_fase2 = ft.Container(
        content=ft.GestureDetector(
            content=ft.Container(content=viewport, bgcolor=ft.Colors.TRANSPARENT),
            on_scroll=on_rueda,
            on_scale_start=al_iniciar_gesto,
            on_scale_update=al_deslizar_touchpad,
            drag_interval=16,
        ),
        visible=False,
        opacity=0,
        height=alto(),
        width=ancho(),
        animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_OUT),
    )

    def al_redimensionar(e):
        nonlocal TAM_MAPA
        h, w = alto(), ancho()
        for s in secciones:
            s.height = h
            s.width = w
        slide.width = w
        slide.height = h * TOTAL_SECCIONES
        slide.top = -seccion_actual[0] * h
        viewport.width = w
        viewport.height = h
        panel_fase2.height = h
        panel_fase2.width = w
        panel_resultado.width, panel_resultado.height = w, h
        nuevo_tam=max(260,min(int(h*.66),w-96,640))
        if nuevo_tam!=TAM_MAPA:
            razon=nuevo_tam/TAM_MAPA
            vista_mapa.x*=razon
            vista_mapa.y*=razon
            TAM_MAPA=vista_mapa.tam=nuevo_tam
            vista_mapa.limitar()
            for control in (lienzo_mapa,linea_recorrido,superficie_mapa,mapa_marco):
                control.width=control.height=nuevo_tam
            pintar_mapa()
        cuadro_texto.width=guia_capacidades.width=min(820,max(260,w-80))
        titulo.size=max(32,min(62,(w-80)/15))
        foto_vehiculo.width=max(240,min(680,w-192))
        campo_dialogos.width=max(220,min(740,w-152))
        seccion_exportar.content.controls[1].width=max(260,min(820,w-80))
        dimensionar_carrusel(max(1, w - 176), h)
        dimensionar_clima()
        dimensionar_camaras()
        if propuesta_activa['activa']:refrescar_propuesta()
        page.update()

    page.on_resize = al_redimensionar

    def abrir_correcciones(e):
        import sqlite3
        from src import correcciones_intenciones as correcciones
        from src.modelo_intenciones import predecir_intencion

        texto_corregido=ft.TextField(label='Petición que quieres corregir',value=campo.value or '',
            multiline=True,min_lines=2,max_lines=4,max_length=500)
        etiqueta=ft.Dropdown(label='Gesto que querías representar',value=None,
            options=[ft.DropdownOption(k,v) for k,v in correcciones.ETIQUETAS.items()])
        estado=ft.Text('',size=12)
        cantidad=ft.Text('',size=12)
        detalle=ft.Text('Selecciona una corrección para revisar su frase y etiqueta.',selectable=True)
        filtro=ft.Dropdown(label='Estado de revisión',value='pendiente',options=[
            ft.DropdownOption('pendiente','Pendientes'),ft.DropdownOption('aprobada','Aprobadas'),
            ft.DropdownOption('rechazada','Rechazadas')])
        selector=ft.Dropdown(label='Corrección pendiente',value=None,options=[])
        registros={}

        def seleccionar_correccion(e):
            fila=registros.get(selector.value)
            detalle.value=(f"Petición: {fila['texto']}\nEtiqueta propuesta: "
                +correcciones.ETIQUETAS[fila['intencion']]+f"\nEstado: {fila['estado']}") if fila else 'Selecciona una corrección para revisar su frase y etiqueta.'
            aprobar.disabled=fila is None or fila['estado']=='aprobada'
            descartar.disabled=fila is None or fila['estado']=='rechazada'
            page.update()

        selector.on_select=seleccionar_correccion

        def refrescar_correcciones():
            registros.clear();selector.options=[];selector.value=None
            detalle.value='Selecciona una corrección para revisar su frase y etiqueta.'
            aprobar.disabled=descartar.disabled=True
            cantidad.value=''
            selector.label='Corrección '+filtro.value
            filas=correcciones.listar(estado=filtro.value)
            registros.update((f['id'],f) for f in filas)
            selector.options=[ft.DropdownOption(f['id'],
                f['texto'][:70]+' · '+correcciones.ETIQUETAS[f['intencion']]) for f in filas]
            cantidad.value=f"Correcciones {dict(pendiente='pendientes',aprobada='aprobadas',rechazada='rechazadas')[filtro.value]}: {len(filas)}"

        def filtrar_correcciones(e):
            try:
                refrescar_correcciones()
                estado.value=''
            except (ValueError,OSError,sqlite3.Error) as error:
                estado.value='No se pudieron cargar las correcciones: '+str(error)
            page.update()

        filtro.on_select=filtrar_correcciones

        def guardar_correccion(e):
            try:
                if not etiqueta.value:
                    raise ValueError('Elige el gesto correcto antes de guardar.')
                texto=texto_corregido.value or ''
                fila=correcciones.registrar(texto,etiqueta.value,predecir_intencion(texto))
                filtro.value=fila['estado']
                refrescar_correcciones()
                estado.value=('Guardada para revisión. Revisa y aprueba la etiqueta para incluirla en un próximo entrenamiento.'
                    if fila['estado']=='pendiente' else 'La corrección ya estaba registrada con estado: '+fila['estado']+'.')
            except (ValueError,OSError,sqlite3.Error) as error:
                estado.value='No se pudo guardar la corrección: '+str(error)
            page.update()

        def revisar_seleccion(aceptar):
            try:
                if selector.value not in registros:
                    raise ValueError('Selecciona y revisa una corrección de la lista.')
                correcciones.revisar(selector.value,aceptar)
                refrescar_correcciones()
                estado.value=('Etiqueta aprobada para un próximo entrenamiento. El modelo actual sigue sin cambios.'
                    if aceptar else 'Corrección descartada; no se usará para entrenar.')
            except (ValueError,OSError,sqlite3.Error) as error:
                estado.value='No se pudo revisar la corrección: '+str(error)
            page.update()

        def aprobar_etiqueta(e):
            revisar_seleccion(True)

        def descartar_correccion(e):
            revisar_seleccion(False)

        aprobar=ft.TextButton('Aprobar etiqueta',on_click=aprobar_etiqueta,disabled=True)
        descartar=ft.TextButton('Descartar',on_click=descartar_correccion,disabled=True)
        try:
            refrescar_correcciones()
        except (ValueError,OSError,sqlite3.Error) as error:
            estado.value='No se pudieron cargar las correcciones: '+str(error)
        dialogo=ft.AlertDialog(modal=True,title=ft.Text('Correcciones de interpretación'),
            content=ft.Column([
                ft.Text('Indica un solo gesto. Puedes guardar una corrección aunque el análisis haya fallado.'),
                texto_corregido,etiqueta,ft.TextButton('Guardar para revisión',on_click=guardar_correccion),
                ft.Divider(),ft.Text('Revisar correcciones'),filtro,cantidad,selector,detalle,
                ft.Row([aprobar,descartar]),estado,
                ft.Text('Las aprobaciones se incorporan al volver a entrenar; guardar o revisar no inicia entrenamiento.',size=12),
            ],tight=True,width=560,height=540,scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton('Cerrar',on_click=lambda e:page.pop_dialog())])
        page.show_dialog(dialogo)

    # ---------------------------------------------------------
    # BACKEND: LÓGICA ORIGINAL DE NOTA ADHESIVA E IA (INTACTA)
    # ---------------------------------------------------------
    async def on_analizar(e,plan_preparado=None):
        if debounce_task[0]:
            debounce_task[0].cancel()
            debounce_task[0]=None
        campo.disabled=True
        btn_random.disabled=True
        set_boton(False)
        lbl_analisis.value = "Analizando la escena y las animaciones..."
        luces[1].bgcolor = ft.Colors.AMBER
        page.update()

        texto = campo.value
        try:
            resultado = plan_preparado if plan_preparado is not None else await asyncio.to_thread(analizar_accion_usuario, texto)
            resultado=completar_propuesta(resultado,texto)
        except Exception as error:
            print(f"Error IA: {error}")
            luces[1].bgcolor = ft.Colors.RED
            lbl_analisis.value = f"No se pudo preparar la escena: {error}"
            campo.disabled=False
            btn_random.disabled=False
            set_boton(True)
            page.update()
            return

        if not resultado.es_valido:
            mostrar_estados(comprobaciones_peticion(texto))
            lbl_analisis.value = resultado.razon_rechazo
            luces[1].bgcolor = ft.Colors.RED if resultado.fuente.startswith(('Gemini','Groq')) else ft.Colors.AMBER
            campo.disabled=False
            btn_random.disabled=False
            set_boton(True)
            page.update()
            return

        lbl_analisis.value=('Escena compatible. Análisis: '+resultado.fuente+'.')

        plan_escena.update(texto=texto, resumen=resultado.resumen, fuente=resultado.fuente,
            aprendizaje_supervisado=dict(resultado.aprendizaje_supervisado),
            vehiculo_en_movimiento=resultado.vehiculo_en_movimiento,limitaciones=resultado.limitaciones,
            lugar_tipo=resultado.lugar_tipo,
            pasos=[p.model_dump() for p in resultado.pasos],roles=resultado.roles,
            accion=resultado.accion, animacion_sugerida=resultado.animacion_sugerida,
            animar_actores=resultado.animar_actores,tipo_movimiento=resultado.tipo_movimiento,
            ruta_id_sugerida=resultado.ruta_id_sugerida,reproduccion=resultado.reproduccion,
            razon_reproduccion=resultado.razon_reproduccion,entorno=resultado.entorno_sugerido.lower(),motivo=resultado.motivo_elecciones)
        recorrido_coche['ruta']=None
        propuesta_activa.update(activa=True,ruta_automatica=False)
        edicion_activa['seccion']=None
        resumen_panel.visible=True
        panel_edicion_camara.visible=False
        reparto.update(ids=list(resultado.actores_ids_sugeridos),activo=0)
        vehiculo_elegido.update(id=resultado.vehiculo_id_sugerido,confirmado=resultado.vehiculo_id_sugerido is not None,indice=0)
        panel_vehiculos.visible=False
        from src.registro_capacidades import soportes_vehiculos
        permitidos={v['model_id'] for v in soportes_vehiculos()} if resultado.accion=='animacion_sobre_vehiculo' else None
        lista_vehiculos[:]=[v for v in disponibles('vehicles') if permitidos is None or v['model_id'] in permitidos]
        fila_actor.visible=slots_reparto.visible=btn_confirmar_personaje.visible=True
        if resultado.vehiculo_id_sugerido is not None:
            vehiculo_elegido['indice']=next((i for i,v in enumerate(lista_vehiculos) if v['model_id']==resultado.vehiculo_id_sugerido),0)
            foto_vehiculo.src=vista_asset(lista_vehiculos[vehiculo_elegido['indice']]['foto'])
            lbl_vehiculo.value=lista_vehiculos[vehiculo_elegido['indice']]['nombre']
        ambientacion_confirmada.clear()
        refrescar_reparto()
        clima_confirmado[0]=False
        seccion_actual[0]=0
        modo_mapa['valor']='inicio'
        btn_inicio.content.value='Inicio'
        btn_destino.content.value='Destino'
        estatica=es_estatica(resultado)
        conduccion=usa_recorrido_vehicular(resultado)
        btn_cam_pov.visible=es_vehicular(resultado)
        btn_cam_pov.disabled=not btn_cam_pov.visible
        btn_cam_pov.opacity=1
        vehicular=es_vehicular(resultado)
        if resultado.accion=='animacion_sobre_vehiculo':btn_cam_pov.visible=False
        for tarjeta in (btn_cam_fija,btn_cam_lateral,btn_cam_giro):tarjeta.visible=not vehicular
        btn_cam_3p.content.controls[1].value='Exterior fija al coche' if vehicular else 'Tercera persona'
        preferida=preferencia_camara(texto)
        if preferida=='vehiculo_pov' and not btn_cam_pov.visible:preferida='seguimiento_trasero'
        if vehicular and preferida in ('fija','costado','giro_frontal'):preferida='seguimiento_trasero'
        nombre,boton={
            'automatica':('Montaje automático',btn_cam_auto),
            'seguimiento_trasero':('Tercera Persona',btn_cam_3p),
            'costado':('Seguimiento lateral',btn_cam_lateral),
            'fija':('Cámara Fija Cinematográfica',btn_cam_fija),
            'giro_frontal':('Giro frontal',btn_cam_giro),
            'vehiculo_pov':('POV (Primera Persona)',btn_cam_pov),
        }[preferida]
        set_camara(nombre,boton)
        selector_ruta_auto.visible=conduccion or resultado.accion=='animacion_sobre_vehiculo'
        btn_otra_ubicacion.visible=estatica or conduccion
        btn_otra_ubicacion.content='Otro recorrido' if conduccion else 'Otra ubicación'
        slider_velocidad.visible=lbl_velocidad.visible=conduccion
        slider_velocidad.value=resultado.velocidad_kmh_sugerida or random.choice([25,30,35,40,45])
        lbl_velocidad.value=f'Velocidad del vehículo: {slider_velocidad.value} km/h'
        lbl_camara_auto.visible=conduccion
        lbl_camara_auto.value=('La cámara seguirá al vehículo sin conductor visible.' if resultado.accion=='vehiculo_autonomo'
            else 'Al conducir, la cámara quedará vinculada al coche después de que suba el personaje.')
        ayuda_mapa.value='Rueda: zoom · arrastrar: mover · clic: marcar ubicación.'
        controles_ruta.visible=not estatica
        lbl_info_coordenadas.value=''
        lbl_resumen_escena.value = f"{resultado.resumen}\nPlan: {resultado.fuente}"
        slider_duracion.value = resultado.duracion_sugerida
        campo_dialogos.value = '\n'.join(resultado.dialogos)
        lbl_duracion.value=('Duración de la conducción' if conduccion else 'Duración del plano')+f': {resultado.duracion_sugerida} segundos'
        eleccion_hora['valor']=12
        eleccion_clima['valor']=0
        set_frac_hora(12/24)
        set_frac_clima(0)
        lbl_ambiente_propuesto.value=('Ambiente propuesto según tu petición. Puedes ajustarlo y confirmar.'
            if resultado.hora_sugerida is not None or resultado.clima_id_sugerido is not None else
            'No pediste un ambiente: elige la hora y el clima y pulsa Confirmar.')
        if resultado.hora_sugerida is not None:
            eleccion_hora['valor'] = resultado.hora_sugerida
            set_frac_hora(resultado.hora_sugerida / 24)
        if resultado.clima_id_sugerido is not None:
            eleccion_clima['valor'] = resultado.clima_id_sugerido
            set_frac_clima(resultado.clima_id_sugerido / 23)
        if resultado.actor_id_sugerido is not None:
            for i, (nombre, code, path) in enumerate(ACTORES_BD['todos']):
                if code == str(resultado.actor_id_sugerido):
                    idx_actor[0] = i
                    eleccion_actor.update(id=code, nombre=nombre)
                    img_actor.src = imagen_actor(path)
                    for imagen, paso in zip(vecinos_actor, (-1, 1)):
                        imagen.src = imagen_actor(ACTORES_BD['todos'][(i+paso) % len(ACTORES_BD['todos'])][2])
                    lbl_actor_nom.value = f"| Personaje elegido: {nombre} |"
                    break

        mostrar_estados((True,True,True,True))
        page.update()
        await asyncio.sleep(0.4)

        campo.disabled = True
        contenedor_titulo.opacity = 0
        controles_inferiores.opacity = 0
        page.update()
        await asyncio.sleep(0.4)

        fase1_activa[0] = False
        contenedor_titulo.visible = False
        controles_inferiores.visible = False
        cuadro_texto.visible = False
        espacio_superior.visible = False
        espacio_relleno.visible = False

        # AUTO-MARCADO SEGÚN IA
        entorno_ia = resultado.entorno_sugerido.lower()
        try:
            lugar=None
            if resultado.accion=='animacion_sobre_vehiculo':
                ruta=elegir_ruta_vehiculo(texto,resultado.ruta_vehiculo_id)
                aplicar_recorrido(ruta)
                inicio=tuple(ruta['puntos'][0]);destino=tuple(ruta['puntos'][-1])
            elif estatica:
                from src.ubicaciones_escena import ubicaciones
                lugar=next((u for u in ubicaciones(entorno_ia) if u['id']==resultado.ubicacion_id_sugerida),None) or elegir_ubicacion(entorno_ia,texto)
                inicio=tuple(lugar['posicion']);destino=(inicio[0],inicio[1]+3,inicio[2])
            elif conduccion:
                ruta=elegir_ruta_vehiculo(texto,resultado.ruta_vehiculo_id)
                aplicar_recorrido(ruta)
                inicio,_=puntos_entrada(ruta);destino=tuple(ruta['puntos'][-1])
            else:inicio, destino = sugerir_ruta(entorno_ia, resultado.duracion_sugerida, obtener_z,resultado.ruta_id_sugerida)
            if resultado.accion=='secuencia' and not estatica:
                from src.compilar_secuencia import capacidad_recorrido
                limite=capacidad_recorrido(resultado.pasos,resultado.duracion_sugerida)
                distancia=math.dist(inicio,destino)
                if distancia>limite:
                    factor=limite/distancia
                    destino=tuple(a+(b-a)*factor for a,b in zip(inicio,destino))
            if resultado.tipo_movimiento=='nadar':
                raise ValueError('Marca inicio y destino dentro del agua para nadar. No se ha verificado una zona acuática automáticamente.')
            if resultado.tipo_movimiento=='escaleras':
                raise ValueError('Marca la base y la parte alta de unas escaleras reales. El mapa no identifica escaleras automáticamente.')
            eleccion_ubicacion.update(dict(zip(('x','y','z'),inicio)),entorno=entorno_ia)
            eleccion_destino.update(dict(zip(('x','y','z'),destino)))
            puntos_marcados.update(inicio=True,destino=True)
            propuesta_activa['ruta_automatica']=True
            colocar_marcador(*inicio[:2])
            actualizar_ruta()
            lbl_info_coordenadas.value = ''
            if resultado.accion=='animacion_sobre_vehiculo':
                lbl_ruta.value='Vehículo y personaje sobre el techo'
            elif estatica:
                lbl_ruta.value=lugar['nombre']
            elif conduccion:
                btn_inicio.content.value='Inicio'
                btn_destino.content.value='Final'
            elif resultado.accion=='entrar_vehiculo':
                btn_inicio.content.value='Personaje'
                btn_destino.content.value='Vehículo'
                lbl_ruta.value='Selecciona la posición de cada uno'
        except ValueError as error:
            puntos_marcados.update(inicio=False,destino=False)
            marcador_destino.visible = False
            lbl_info_coordenadas.value = str(error)

        page.scroll = None
        page.padding = ft.Padding.all(0)
        al_redimensionar(None)
        centrar_mapa()
        actualizar_imagen_tiempo_real()
        ambientacion_confirmada.update(captura_mostrada)
        clima_confirmado[0]=True
        refrescar_propuesta()
        tarjeta_vehiculo.visible=es_vehicular(resultado)
        seccion_actual[0]=3
        slide.top=-3*alto()

        panel_fase2.visible = True
        page.update()
        await asyncio.sleep(0.05)
        panel_fase2.opacity = 1
        page.update()

    random_en_curso=[False]

    async def on_crear_random(e):
        if random_en_curso[0]:return
        random_en_curso[0]=True
        btn_random.disabled=True
        if debounce_task[0]:debounce_task[0].cancel()
        lbl_analisis.value='Preparando una escena…'
        page.update()
        try:
            escena=await asyncio.to_thread(crear_escena_aleatoria,[int(c) for _,c,_ in ACTORES_BD['todos']])
            campo.value=escena['texto']
            await on_analizar(e,escena['plan'])
            reparto.update(ids=escena['actores'],activo=0)
            refrescar_reparto()
            if not puntos_marcados['inicio']:usar_avenida_ejemplo(None)
            set_camara('Montaje automático',btn_cam_auto)
            categorias=[c for c in ('mistica','feliz') if pistas(c)]
            sugerida=escena.get('categoria_musica')
            categoria_musica.value=sugerida if sugerida in categorias else random.choice(categorias) if categorias else 'ninguna'
            actualizar_pistas()
            confirmar_clima(None)
            await on_crear_mms(e)
        except (ValueError,OSError) as error:
            mensaje=f'No se pudo generar la cinemática aleatoria: {error}'
            if not fase1_activa[0]:volver_inicio(None)
            lbl_analisis.value=mensaje
        finally:
            random_en_curso[0]=False
            btn_random.disabled=False
            page.update()

    btn_random=ft.TextButton('Crear cinemática random',icon=ft.Icons.SHUFFLE,
        style=estilo_boton(),height=62,on_click=on_crear_random)

    btn_analizar = boton_glitch('Analizar',on_analizar)
    btn_analizar.disabled=True
    btn_analizar.opacity=.35

    def set_boton(activo: bool):
        btn_analizar.disabled = not activo
        btn_analizar.opacity = 1 if activo else 0.35
        page.update()

    lbl_analisis = ft.Text('',width=760,text_align=ft.TextAlign.CENTER,size=14,color=SECUNDARIO)

    async def usar_ejemplo(e,texto):
        campo.value=texto
        await validar_texto(type('Cambio',(),{'control':campo})())
        page.update()

    ejemplos=(
        ('Un encuentro', 'Dos personas saludan y luego hablan en la ciudad durante 24 segundos'),
        ('Un paseo en coche', 'Una persona se sube a un auto y conduce en el campo al atardecer durante 30 segundos'),
        ('Una celebración', 'Tres personas bailan y luego aplauden en la playa durante 24 segundos'),
    )
    async def elegir_ejemplo(e):
        await usar_ejemplo(e,e.control.data)

    guia_capacidades=ft.ExpansionTile(title=ft.Text('Qué puedes pedir',size=14,color=SECUNDARIO),
        controls=[ft.Container(content=ft.Column([
            ft.Row([ft.TextButton(nombre,on_click=elegir_ejemplo,data=texto) for nombre,texto in ejemplos],
                wrap=True,spacing=12,run_spacing=12),
            ft.Text('Caminar o correr, gestos como saludar y bailar, acciones consecutivas y recorridos en coche.',
                size=14,color=TEXTO),
            ft.Text('Hasta cuatro personajes y 60 segundos. Puedes ajustar ubicación, clima, cámara, música y subtítulos.',
                size=13,color=SECUNDARIO),
            ft.Text('Los recursos son del catálogo de GTA. Los gestos no añaden objetos o efectos; '
                'el programa no crea modelos 3D ni voces.',size=13,color=SECUNDARIO),
            ft.Row([ft.Container(width=8,height=8,border_radius=4,bgcolor=color)
                for color in (ft.Colors.GREEN,ft.Colors.AMBER,ft.Colors.RED)],spacing=7,tight=True),
            ft.Text('Verde: correcto · Ámbar: requiere análisis · Rojo: revisa la petición',size=12,color=SECUNDARIO),
        ],spacing=16),padding=ft.Padding(12,16,12,20))],width=820)
    controles_inferiores = ft.Container(
        content=ft.Column([semaforos_row,
            ft.Row([btn_analizar,btn_random],alignment=ft.MainAxisAlignment.CENTER,
                spacing=18,wrap=True,run_spacing=14),
            lbl_analisis,guia_capacidades],spacing=24,horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        opacity=1, animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
    )

    debounce_task = [None]

    async def validar_texto(e):
        texto = e.control.value.lower()
        if debounce_task[0]:
            debounce_task[0].cancel()
        if len(texto.strip()) == 0:
            for luz,etiqueta,nombre in zip(luces,etiquetas_luces,('Descripción','Acción','Personajes','Duración')):
                luz.bgcolor = GRIS
                luz.tooltip=etiqueta.value=nombre
            lbl_analisis.value=''
            set_boton(False)
            page.update()
            return

        async def chequeo_local():
            try:
                await asyncio.sleep(.45)
                estados=await asyncio.to_thread(comprobaciones_peticion,texto)
                if e.control.value.lower()!=texto:return
                mostrar_estados(estados)
                lbl_analisis.value=('Revisa la cantidad de personajes o la duración.' if not (estados[2] and estados[3]) else
                    'La acción necesita confirmación al analizar.' if estados[1] is not True else '')
                set_boton(estados[0] and estados[2] and estados[3])
                page.update()
            except asyncio.CancelledError:
                pass

        debounce_task[0] = asyncio.create_task(chequeo_local())

    campo = ft.TextField(
        hint_text="Dos personas se saludan al atardecer, luego caminan por la ciudad…",
        hint_style=ft.TextStyle(font_family=FUENTE,size=21,color='#708076'),
        text_style=ft.TextStyle(font_family=FUENTE,size=22,weight=ft.FontWeight.W_500,color=TEXTO),
        cursor_color=ACENTO,border=ft.NoInputBorder(),multiline=True,min_lines=4,max_lines=6,on_change=validar_texto,
    )

    cuadro_texto = panel(campo,width=min(820,max(260,ancho()-80)),padding=28,
        shadow=ft.BoxShadow(blur_radius=42,color='#20000000',offset=ft.Offset(0,16)))

    espacio_relleno = ft.Container(height=24)

    btn_corregir.on_click=abrir_correcciones

    page.add(espacio_superior, contenedor_titulo, cuadro_texto, espacio_relleno, controles_inferiores, panel_fase2, panel_resultado)
    al_redimensionar(None)
    page.run_task(iluminar_titulo)


if __name__ == "__main__":
    ft.run(main, assets_dir=str(ASSETS))
