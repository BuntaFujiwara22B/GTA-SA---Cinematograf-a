"""Transformación del mapa en píxeles de pantalla; zoom anclado al cursor."""
from dataclasses import dataclass


@dataclass
class VistaMapa:
    tam: float
    escala: float = 1.0
    x: float = 0.0
    y: float = 0.0

    def limitar(self):
        minimo = self.tam * (1 - self.escala)
        self.x = max(minimo, min(0, self.x))
        self.y = max(minimo, min(0, self.y))

    def zoom(self, factor, px, py):
        nueva = max(1.0, min(12.0, self.escala * factor))
        razon = nueva / self.escala
        self.x = px - (px - self.x) * razon
        self.y = py - (py - self.y) * razon
        self.escala = nueva
        self.limitar()

    def mover(self, dx, dy):
        self.x += dx
        self.y += dy
        self.limitar()

    def a_pantalla(self, px, py):
        return self.x + px*self.escala, self.y + py*self.escala

    def a_mapa(self, px, py):
        return (px-self.x)/self.escala, (py-self.y)/self.escala
