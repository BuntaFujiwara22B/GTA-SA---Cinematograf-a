"""Vistas ligeras para Flet; fotos y catálogos originales intactos."""
from pathlib import Path
from PIL import Image
from src.paths import ASSETS


def main():
    archivos=list((ASSETS/'actors').glob('*.png'))
    for carpeta in ['vehicles','objects','camaras']+[f'hora_{i}' for i in range(24)]:
        archivos.extend((ASSETS/carpeta).glob('*.png'))
    total_antes=total_despues=0
    for p in archivos:
        relativa=p.relative_to(ASSETS)
        destino=ASSETS/'ui'/relativa.with_suffix('.webp')
        total_antes+=p.stat().st_size
        if not destino.exists() or destino.stat().st_mtime_ns<p.stat().st_mtime_ns:
            with Image.open(p) as im:
                im=im.convert('RGBA' if p.parent.name=='actors' else 'RGB')
                if p.parent.name=='actors':
                    bbox=im.getchannel('A').getbbox()
                    if bbox:im=im.crop(bbox)
                    im.thumbnail((600,850))
                else:im.thumbnail((1280,720))
                destino.parent.mkdir(parents=True,exist_ok=True)
                im.save(destino,format='WEBP',quality=86,lossless=p.parent.name=='actors',method=4)
        total_despues+=destino.stat().st_size
    print(f'{len(archivos)} vistas: {total_antes/1024**2:.1f} -> {total_despues/1024**2:.1f} MiB',flush=True)


if __name__=='__main__':main()
