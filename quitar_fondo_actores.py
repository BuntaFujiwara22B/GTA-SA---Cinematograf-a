import os
from PIL import Image
from rembg import remove

RUTA_ACTORES = os.path.join(os.path.dirname(__file__), "assets", "actors")

def procesar_transparencias():
    if not os.path.exists(RUTA_ACTORES):
        print(f"❌ No existe la carpeta {RUTA_ACTORES}")
        return

    archivos = [f for f in os.listdir(RUTA_ACTORES) if f.endswith(".png")]
    print(f"🔄 Procesando {len(archivos)} imágenes para quitar fondo...")

    for archivo in archivos:
        ruta_img = os.path.join(RUTA_ACTORES, archivo)
        try:
            inp = Image.open(ruta_img)
            out = remove(inp)
            out.save(ruta_img)
            print(f"✅ Fondo eliminado: {archivo}")
        except Exception as e:
            print(f"⚠️ Error en {archivo}: {e}")

if __name__ == "__main__":
    procesar_transparencias()