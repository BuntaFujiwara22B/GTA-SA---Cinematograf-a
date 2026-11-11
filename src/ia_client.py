import os
import time
from typing import List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from pydantic import BaseModel
from src.catalogo_animaciones import cargar_contexto_animaciones, cargar_opciones_animaciones
from src.busqueda_animaciones import contexto_candidatas
from src.referencias_cine import contexto_referencias_cine

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODELOS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
]
REINTENTOS_POR_MODELO = 3
ERRORES_TEMPORALES = {429, 500, 503, 504}

class AnalisisEscena(BaseModel):
    es_valido: bool
    razon_rechazo: str
    actores_sugeridos: List[str]
    vehiculo_sugerido: Optional[str]
    animacion_sugerida: Optional[str]
    entorno_sugerido: str  # "campo", "ciudad", "interior", "desierto", "playa"
    clima_sugerido: str
    camara_sugerida: str

def cargar_base_datos() -> str:
    try:
        ruta = os.path.join(os.path.dirname(__file__), "todo.txt")
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

INSTRUCCIONES_BASE = """
Eres el director técnico del mod Mission Maker de GTA San Andreas.
Analiza la descripción del usuario y mapea sus ideas a los IDs EXACTOS de la base de datos proporcionada.

Reglas:
1. Viabilidad: Determina si la acción es factible en el juego (sin volar, sin magia, máx 4 personas).
2. Mapeo: Devuelve los IDs de 'todo.txt' para actores, vehículo y animación.
3. Entorno: Clasifica el ambiente principal de la escena estrictamente en una de estas opciones: "campo", "ciudad", "desierto", "playa", "interior".

BASE DE DATOS DEL MOD:
"""

def _llamar_modelo(modelo: str, texto_usuario: str, contexto_completo: str) -> AnalisisEscena:
    respuesta = client.models.generate_content(
        model=modelo,
        contents=f'Descripción de la escena: "{texto_usuario}"',
        config=types.GenerateContentConfig(
            system_instruction=contexto_completo,
            response_mime_type="application/json",
            response_schema=AnalisisEscena,
            temperature=0.1,
        ),
    )
    if respuesta.parsed is not None:
        return respuesta.parsed
    return AnalisisEscena.model_validate_json(respuesta.text)

def analizar_accion_usuario(texto_usuario: str) -> AnalisisEscena:
    ultimo_error = None
    contexto_completo = INSTRUCCIONES_BASE + "\n" + cargar_base_datos() + cargar_contexto_animaciones() + contexto_candidatas(texto_usuario) + contexto_referencias_cine()
    ids_animaciones = {opcion['id'] for opcion in cargar_opciones_animaciones()}

    for modelo in MODELOS:
        for intento in range(1, REINTENTOS_POR_MODELO + 1):
            try:
                resultado = _llamar_modelo(modelo, texto_usuario, contexto_completo)
                if resultado.animacion_sugerida is not None and resultado.animacion_sugerida not in ids_animaciones:
                    print("Animacion sugerida fuera del catalogo; se descarta para evitar un ID inexistente.")
                    resultado.animacion_sugerida = None
                print(f"(Modelo usado: {modelo})")
                return resultado
            except errors.APIError as e:
                ultimo_error = e
                if e.code in ERRORES_TEMPORALES:
                    espera = 2 ** (intento - 1)
                    time.sleep(espera)
                else:
                    break

    raise RuntimeError(f"Error con la API: {ultimo_error}")
