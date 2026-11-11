"""Analisis reanudable durante varias horas, sin comprar ni ampliar cuotas."""
import argparse
import json
import time
import os
from dotenv import load_dotenv
from datetime import datetime

from analizar_animaciones import CATALOGO, SALIDA, ROOT, analizar
from src.groq_animaciones import MODELO_GROQ
from src.openrouter_animaciones import descubrir_gratuitos


def pendientes():
    total = len(json.loads(CATALOGO.read_text(encoding='utf-8'))['animaciones'])
    hechos = len(json.loads(SALIDA.read_text(encoding='utf-8'))['resultados']) if SALIDA.exists() else 0
    return total - hechos


def ejecutar(horas, espera, pausa):
    load_dotenv(ROOT / '.env')
    limite_tiempo = time.monotonic() + horas * 3600
    while pendientes() and time.monotonic() < limite_tiempo:
        print(f'\n{datetime.now():%H:%M:%S}: quedan {pendientes()} animaciones.', flush=True)
        modelos = ['gemini-3.5-flash', 'gemini-3.7-flash', 'gemini-3.1-flash-lite']
        if os.getenv('GROQ_API_KEY'):
            modelos.append('groq:' + MODELO_GROQ)
        try:
            modelos += descubrir_gratuitos()
        except Exception as e:
            print(f'No se pudo actualizar OpenRouter ({type(e).__name__}); se conserva Gemini.', flush=True)
        (SALIDA.parent / 'modelos_noche.json').write_text(json.dumps(modelos, indent=2), encoding='utf-8')
        try:
            analizar(0, True, modelos[0], pausa, modelos)
        except RuntimeError:
            raise  # no competir con otro proceso que ya escribe el catalogo
        except Exception as e:
            print(f'Ciclo interrumpido ({type(e).__name__}); avance en disco conservado.', flush=True)
        if not pendientes():
            break
        segundos = min(espera * 60, max(0, limite_tiempo - time.monotonic()))
        print(f'Quedan {pendientes()}. Espera de hasta {segundos / 60:.0f} minutos antes de reintentar.', flush=True)
        final_espera = time.monotonic() + segundos
        while time.monotonic() < final_espera:
            time.sleep(min(30, max(0, final_espera - time.monotonic())))
    print(f'Sesion terminada. Pendientes: {pendientes()}.', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--horas', type=float, default=12, help='Ventana para iniciar ciclos; un ciclo en curso puede excederla')
    p.add_argument('--espera', type=float, default=60, help='Minutos entre ciclos cuando aun quedan pendientes')
    p.add_argument('--pausa', type=float, default=15, help='Segundos entre animaciones')
    args = p.parse_args()
    if args.horas <= 0 or args.espera < 1 or args.pausa < 0:
        p.error('horas > 0, espera >= 1 y pausa >= 0')
    try:
        ejecutar(args.horas, args.espera, args.pausa)
    except KeyboardInterrupt:
        print('\nDetenido. Puedes reanudar con el mismo comando.')
