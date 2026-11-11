"""Vision Groq: seis poses en tres laminas temporales; no modifica originales."""
import base64
import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from google.genai import errors
from PIL import Image, ImageDraw, ImageFont, ImageOps

MODELO_GROQ = 'qwen/qwen3.8-27b'


def preparar_laminas(partes):
    imagenes = [p.inline_data.data for p in partes if not isinstance(p, str) and p.inline_data is not None]
    textos = [p for p in partes if isinstance(p, str)]
    if len(imagenes) != 6:
        raise ValueError('Groq requiere las seis poses originales para esta adaptacion')
    contenido = [{'type': 'text', 'text': '\n'.join(textos) +
        '\nCada lamina contiene dos frames: superior y luego inferior. Las etiquetas FRAME 1..6 son los indices originales.'}]
    fuente = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
    for i in range(0, 6, 2):
        lamina = Image.new('RGB', (960, 1160), 'black')
        draw = ImageDraw.Draw(lamina)
        for j in range(2):
            y = j * 580
            draw.text((12, y + 4), f'FRAME {i+j+1}', font=fuente, fill='white')
            with Image.open(BytesIO(imagenes[i+j])) as im:
                miniatura = ImageOps.contain(im.convert('RGB'), (960, 540))
                lamina.paste(miniatura, ((960-miniatura.width)//2, y + 40 + (540-miniatura.height)//2))
        salida = BytesIO()
        lamina.save(salida, format='JPEG', quality=90)
        contenido.append({'type': 'image_url', 'image_url': {
            'url': 'data:image/jpeg;base64,' + base64.b64encode(salida.getvalue()).decode('ascii')}})
    return contenido


class ClienteGroq:
    def __init__(self, clave):
        self.clave = clave

    def generar(self, modelo, partes, instrucciones, esquema):
        if modelo != MODELO_GROQ:
            raise ValueError('Modelo Groq no configurado para este adaptador visual')
        cuerpo = dict(model=modelo, messages=[
            {'role': 'system', 'content': instrucciones +
             '\nDevuelve solo un objeto JSON con los valores, no el esquema. Esquema:\n' + json.dumps(esquema)},
            {'role': 'user', 'content': preparar_laminas(partes)}],
            response_format={'type': 'json_object'}, max_completion_tokens=1800,
            temperature=0.1, stream=False)
        request = Request('https://api.groq.com/openai/v1/chat/completions',
            data=json.dumps(cuerpo).encode('utf-8'), headers={
                'Authorization': 'Bearer ' + self.clave, 'Content-Type': 'application/json',
                'User-Agent': 'CatalogoAnimaciones/1.0'})
        try:
            with urlopen(request, timeout=180) as response:
                datos = json.load(response)
        except HTTPError as e:
            raise errors.ClientError(e.code, {'error': {'code': e.code,
                'message': f'Groq HTTP {e.code}'}}) from None
        opciones = datos.get('choices', [])
        if not opciones or not opciones[0].get('message', {}).get('content'):
            raise ValueError('Groq devolvio una respuesta vacia')
        texto = opciones[0]['message']['content'].strip()
        json.loads(texto)
        uso = datos.get('usage', {})
        print(f"Groq: respuesta recibida; tokens: {uso.get('total_tokens', 'no informado')}. No informa costo en esta respuesta.", flush=True)
        return SimpleNamespace(text=texto)
