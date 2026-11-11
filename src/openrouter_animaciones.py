"""Adaptador REST para vision en OpenRouter; admite exclusivamente variantes :free."""
import base64
import json
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from google.genai import errors

URL = 'https://openrouter.ai/api/v1'


def ficha_gratuita_visual(ficha):
    precio = ficha.get('pricing', {})
    try:
        return (ficha.get('id', '').endswith(':free')
            and all(float(precio.get(c, 'inf')) == 0 for c in ('prompt', 'completion'))
            and all(float(precio.get(c, 0) or 0) == 0 for c in ('request', 'image'))
            and 'image' in ficha.get('architecture', {}).get('input_modalities', [])
            and 'text' in ficha.get('architecture', {}).get('output_modalities', []))
    except (ValueError, TypeError):
        return False


def descubrir_gratuitos():
    fichas = [f for f in solicitar_json('/models')['data'] if ficha_gratuita_visual(f)]
    # Primero el que ya funciono, despues modelos con salida estructurada.
    fichas.sort(key=lambda f: (f['id'] != 'nvidia/nemotron-3.5-super-vl:free',
        'structured_outputs' not in f.get('supported_parameters', []), f['id']))
    return ['openrouter:' + f['id'] for f in fichas]


def solicitar_json(ruta, clave=None, datos=None):
    headers = {'Accept': 'application/json'}
    if clave:
        headers['Authorization'] = 'Bearer ' + clave
    if datos is not None:
        headers['Content-Type'] = 'application/json'
    request = Request(URL + ruta, headers=headers,
                      data=json.dumps(datos).encode('utf-8') if datos is not None else None)
    try:
        with urlopen(request, timeout=180) as response:
            return json.load(response)
    except HTTPError as e:
        # No incluir headers, clave ni imagenes en excepciones o registros.
        raise errors.ClientError(e.code, {'error': {'code': e.code,
            'message': f'OpenRouter HTTP {e.code}'}}) from None


class ClienteOpenRouter:
    def __init__(self, clave):
        self.clave = clave
        self.modelos_verificados = set()
        self.fichas = {}

    def verificar_modelo(self, modelo):
        if not modelo.endswith(':free'):
            raise ValueError('OpenRouter: solo se permiten variantes :free.')
        if modelo in self.modelos_verificados:
            return
        disponibles = solicitar_json('/models')['data']
        ficha = next((m for m in disponibles if m['id'] == modelo), None)
        if ficha is None:
            raise errors.ClientError(404, {'error': {'code': 404, 'message': 'Modelo no disponible'}})
        precio = ficha.get('pricing', {})
        if any(float(precio.get(campo, 'inf')) != 0 for campo in ('prompt', 'completion')):
            raise ValueError('OpenRouter: el modelo no tiene precio cero confirmado.')
        if any(float(precio.get(campo, 0) or 0) != 0 for campo in ('request', 'image')):
            raise ValueError('OpenRouter: se detecto un cargo adicional.')
        if 'image' not in ficha.get('architecture', {}).get('input_modalities', []):
            raise ValueError('OpenRouter: el modelo no admite imagenes.')
        self.modelos_verificados.add(modelo)
        self.fichas[modelo] = ficha

    def generar(self, modelo, partes, instrucciones, esquema):
        self.verificar_modelo(modelo)
        esquema = dict(esquema, additionalProperties=False)
        contenido = []
        for parte in partes:
            if isinstance(parte, str):
                contenido.append({'type': 'text', 'text': parte})
            elif parte.inline_data is not None:
                datos = parte.inline_data
                encoded = base64.b64encode(datos.data).decode('ascii')
                contenido.append({'type': 'image_url', 'image_url': {
                    'url': f'data:{datos.mime_type};base64,{encoded}'}})
            else:
                raise ValueError('Tipo de contenido no admitido por OpenRouter')
        parametros = self.fichas[modelo].get('supported_parameters', [])
        mensaje = instrucciones + '\nDevuelve los VALORES del analisis como objeto JSON, no un esquema ni un objeto properties.'
        formato = {}
        if 'structured_outputs' in parametros:
            formato = {'type': 'json_schema', 'json_schema': {
                'name': 'descripcion_animacion', 'strict': True, 'schema': esquema}}
        else:
            mensaje += '\nEsquema de los valores esperados (NO copiar el esquema):\n' + json.dumps(esquema)
            if 'response_format' in parametros:
                formato = {'type': 'json_object'}
        cuerpo = dict(
            model=modelo,
            messages=[{'role': 'system', 'content': mensaje},
                {'role': 'user', 'content': contenido}],
            provider={'max_price': {'prompt': 0, 'completion': 0}, 'require_parameters': True},
            stream=False)
        if formato:
            cuerpo['response_format'] = formato
        if 'temperature' in parametros:
            cuerpo['temperature'] = 0.1
        if 'max_tokens' in parametros:
            cuerpo['max_tokens'] = 4096
        respuesta = solicitar_json('/chat/completions', self.clave, cuerpo)
        if respuesta.get('error'):
            codigo = int(respuesta['error'].get('code', 502))
            raise errors.ClientError(codigo, {'error': {'code': codigo, 'message': 'OpenRouter devolvio un error'}})
        opciones = respuesta.get('choices', [])
        if not opciones:
            raise ValueError('OpenRouter no devolvio una respuesta')
        contenido = opciones[0].get('message', {}).get('content')
        if not isinstance(contenido, str) or not contenido.strip():
            raise ValueError('OpenRouter devolvio contenido vacio o bloqueado')
        texto = contenido.strip()
        if texto.startswith('```') and texto.endswith('```'):
            texto = texto.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        # Verificar JSON antes de devolver; el analizador valida el esquema completo.
        json.loads(texto)
        uso = respuesta.get('usage', {})
        return SimpleNamespace(text=texto, costo=uso.get('cost'))
