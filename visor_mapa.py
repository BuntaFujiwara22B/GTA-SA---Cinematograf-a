import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QWidget, QLabel, QPushButton, QHBoxLayout, QGraphicsEllipseItem
)
from PyQt6.QtGui import QPixmap, QWheelEvent, QPainter, QColor, QPen, QBrush
from PyQt6.QtCore import Qt
from PIL import Image

from detector_entorno import detectar_entorno_gta
from src.paths import RESOURCE_ROOT

DIR_PROYECTO = str(RESOURCE_ROOT)
RUTA_MAPA = os.path.join(DIR_PROYECTO, "assets", "locations", "sa_map_full.webp")
RUTA_HEIGHTS = os.path.join(DIR_PROYECTO, "assets", "heights")


class GestorAlturas:
    def __init__(self, ruta_base=RUTA_HEIGHTS):
        self.ruta_base = ruta_base
        self.cache = {}

    def obtener_z(self, gta_x: float, gta_y: float) -> float:
        map_x = (gta_x + 3000) / 2.0
        map_y = (3000 - gta_y) / 2.0
        
        tile_x = max(0, min(5, int(map_x // 500)))
        tile_y = max(0, min(5, int(map_y // 500)))
        
        nombre_archivo = f"height-{tile_y}-{tile_x}.png"
        ruta_completa = os.path.join(self.ruta_base, nombre_archivo)
        
        if not os.path.exists(ruta_completa):
            return 0.0
            
        if nombre_archivo not in self.cache:
            try:
                self.cache[nombre_archivo] = Image.open(ruta_completa).convert("RGB")
            except Exception:
                return 0.0
            
        img = self.cache[nombre_archivo]
        norm_x = (map_x % 500) / 500.0
        norm_y = (map_y % 500) / 500.0
        
        pixel_x = int(norm_x * (img.width - 1))
        pixel_y = int(norm_y * (img.height - 1))
        
        try:
            r, g, b = img.getpixel((pixel_x, pixel_y))
            z = ((r << 8) | g) / 10.0
            return round(z, 2)
        except Exception:
            return 0.0


class MapaInteractivo(QGraphicsView):
    def __init__(self, label_coords, callback_seleccion):
        super().__init__()
        self.label_coords = label_coords
        self.callback_seleccion = callback_seleccion
        self.escena = QGraphicsScene(self)
        self.setScene(self.escena)

        self.pixmap = QPixmap(RUTA_MAPA) 
        self.escena.addPixmap(self.pixmap)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.map_width = self.pixmap.width()
        self.map_height = self.pixmap.height()
        
        self.gestor_z = GestorAlturas()
        self.marcador = None

    def poner_marcador_pixel(self, px: float, py: float):
        if self.marcador:
            self.escena.removeItem(self.marcador)
        
        radio = 8
        self.marcador = QGraphicsEllipseItem(px - radio, py - radio, radio * 2, radio * 2)
        self.marcador.setBrush(QBrush(QColor(255, 0, 0, 220)))
        self.marcador.setPen(QPen(QColor(255, 255, 255), 2))
        self.escena.addItem(self.marcador)

    def seleccionar_coordenada(self, px: float, py: float):
        x_gta = (px / self.map_width) * 6000 - 3000
        y_gta = 3000 - (py / self.map_height) * 6000
        z_gta = self.gestor_z.obtener_z(x_gta, y_gta)
        entorno = detectar_entorno_gta(x_gta, y_gta, z_gta)

        self.poner_marcador_pixel(px, py)
        self.label_coords.setText(
            f"X: {x_gta:.2f} | Y: {y_gta:.2f} | Z: {z_gta:.2f} | Entorno: {entorno.upper()}"
        )

        if self.callback_seleccion:
            self.callback_seleccion(x_gta, y_gta, z_gta, entorno)

    def wheelEvent(self, event: QWheelEvent):
        zoom_in = 1.15
        zoom_out = 1.0 / zoom_in
        if event.angleDelta().y() > 0:
            self.scale(zoom_in, zoom_in)
        else:
            self.scale(zoom_out, zoom_out)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            punto_escena = self.mapToScene(event.pos())
            self.seleccionar_coordenada(punto_escena.x(), punto_escena.y())


class SelectorMapaWindow(QWidget):
    def __init__(self, x_init=0.0, y_init=0.0):
        super().__init__()
        self.setWindowTitle("SA-MP GIS Clone - Marcador Táctico de Escenas")
        self.resize(1050, 820)
        self.coords_seleccionadas = (x_init, y_init, 0.0, "ciudad")

        layout = QVBoxLayout(self)

        self.label_coords = QLabel("Haz clic en el mapa para marcar el punto de la escena...")
        self.label_coords.setStyleSheet(
            "font-size: 17px; font-family: 'Courier New'; font-weight: bold; padding: 10px; background: #FFFDF0; border: 2px solid black;"
        )

        self.visor_mapa = MapaInteractivo(self.label_coords, self._on_coord_update)
        
        btn_confirmar = QPushButton("CONFIRMAR UBICACIÓN Y USAR EN LA ESCENA")
        btn_confirmar.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32; color: white; font-family: 'Courier New';
                font-weight: bold; font-size: 16px; padding: 12px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #1B5E20; }
        """)
        btn_confirmar.clicked.connect(self.close)

        layout.addWidget(self.label_coords)
        layout.addWidget(self.visor_mapa)
        layout.addWidget(btn_confirmar)

        # Posicionar marcador inicial sugerido
        px = ((x_init + 3000) / 6000) * self.visor_mapa.map_width
        py = ((3000 - y_init) / 6000) * self.visor_mapa.map_height
        self.visor_mapa.seleccionar_coordenada(px, py)

    def _on_coord_update(self, x, y, z, entorno):
        self.coords_seleccionadas = (x, y, z, entorno)


def abrir_selector_mapa(x_init=2490.0, y_init=-1670.0):
    """Abre la ventana de PyQt6 y devuelve las coordenadas (x, y, z, entorno) seleccionadas."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    ventana = SelectorMapaWindow(x_init, y_init)
    ventana.show()
    app.exec()
    return ventana.coords_seleccionadas


if __name__ == "__main__":
    coords = abrir_selector_mapa(200.0, -100.0)
    print("Resultado selección:", coords)