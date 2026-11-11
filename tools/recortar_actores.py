"""Recorta el área del personaje en capturas del menú de selección."""
from PIL import Image
from src.paths import ASSETS


def recortar():
    carpeta = ASSETS / 'actors'
    if not carpeta.is_dir():
        print(f'No se encontró la carpeta: {carpeta}')
        return

    contador = 0
    for archivo in sorted(carpeta.glob('*.png')):
        try:
            with Image.open(archivo) as imagen:
                ancho, alto = imagen.size
                # Excluye los bordes del menú y conserva el personaje completo.
                caja = (int(ancho * .32), int(alto * .12), int(ancho * .68), int(alto * .95))
                recorte = imagen.crop(caja)
            recorte.save(archivo)
            recorte.close()
            contador += 1
            print(f'Recortada: {archivo.name}')
        except Exception as error:
            print(f'Error al procesar {archivo.name}: {error}')
    print(f'Imágenes recortadas: {contador}')


if __name__ == '__main__':
    recortar()
