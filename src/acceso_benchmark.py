"""Clientes de API para el benchmark, sin respaldo local ni cambios de cuentas."""
import json
import os
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.mvp_plan import _detalle_api

OR = 'https://openrouter.ai/api/v1/'
GOOGLE = 'https://generativelanguage.googleapis.com/v1beta/'
_turno = threading.Lock()
_ultima = 0.


def peticion(url, headers, datos=None):
    req = Request(url, data=json.dumps(datos).encode('utf-8') if datos is not None else None,
                  headers=dict(headers, **{'Content-Type': 'application/json', 'User-Agent': 'MMS-Benchmark/2.0'}))
    with urlopen(req, timeout=90) as r:
        return json.load(r)


def catalogo_gratuito():
    datos = peticion(OR + 'models', {})
    return {m['id']: m for m in datos['data'] if m['id'].endswith(':free') and
            float(m['pricing']['prompt']) == float(m['pricing']['completion']) == 0}


def generar(proveedor, modelo, system, user, max_tokens=8192):
    global _ultima
    if proveedor == 'google':
        clave = os.environ['GEMINI_API_KEY']
        original = peticion(GOOGLE + 'models/' + modelo + ':generateContent',
            {'x-goog-api-key': clave}, {
                'systemInstruction': {'parts': [{'text': system}]},
                'contents': [{'role': 'user', 'parts': [{'text': user}]}],
                'generationConfig': {'temperature': .1, 'maxOutputTokens': max_tokens},
            })
        candidatos = original.get('candidates', [])
        partes = candidatos[0].get('content', {}).get('parts', []) if candidatos else []
        contenido = ''.join(p.get('text', '') for p in partes if not p.get('thought'))
        return dict(original=original, contenido=contenido, usage=original.get('usageMetadata', {}))
    if proveedor != 'openrouter' or not modelo.endswith(':free'):
        raise ValueError('Solo se permiten variantes gratuitas explícitas de OpenRouter.')
    with _turno:
        time.sleep(max(0, 3.1-(time.monotonic()-_ultima)))
        _ultima = time.monotonic()
    original = peticion(OR + 'chat/completions',
        {'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY']}, {
            'model': modelo, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'temperature': .1, 'max_tokens': max_tokens,
            'provider': {'allow_fallbacks': False, 'max_price': {'prompt': 0, 'completion': 0}},
        })
    contenido = (original.get('choices') or [{}])[0].get('message', {}).get('content') or ''
    return dict(original=original, contenido=contenido, usage=original.get('usage', {}))


def probar(previos=()):
    """Prueba de acceso independiente de las respuestas del experimento."""
    pruebas = [('google', 'gemini-3.5-flash'),
               ('openrouter', 'baidu/ernie-5.5-flash-preview:free'),
               ('openrouter', 'nvidia/nemotron-3.5-super-vl:free'),
               ('openrouter', 'dots-studio/dots-3-note-preview:free'),
               ('openrouter', 'cohere/north-mini-code:free'),
               ('openrouter', 'liquid/lfm-3-1.7b:free')]
    informe = []
    for proveedor, modelo in pruebas:
        previo = next((r for r in previos if r['modelo'] == modelo and r.get('acceso')), None)
        if previo:
            informe.append(previo)
            continue
        r = dict(proveedor=proveedor, modelo=modelo)
        try:
            respuesta = generar(proveedor, modelo, 'Responde brevemente.', 'Escribe OK.', max_tokens=64)
            r.update(acceso=True, contenido=respuesta['contenido'])
        except HTTPError as e:
            r.update(acceso=False, codigo=e.code, detalle=_detalle_api(e))
        except Exception as e:
            r.update(acceso=False, tipo=type(e).__name__)
        informe.append(r)
        print(modelo, 'accesible' if r['acceso'] else r.get('codigo', r.get('tipo')), flush=True)
    return informe
