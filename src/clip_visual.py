"""CLIP local opcional: índice persistente y carga perezosa fuera de la interfaz."""
import io
import json
import os
import threading
from functools import lru_cache
from pathlib import Path
from src.paths import RESOURCE_ROOT, DATA_ROOT

MODELO='openai/clip-vit-base-patch32'
INDICE=DATA_ROOT/'cache/clip_climas.npz'
if not INDICE.exists() and (RESOURCE_ROOT/'cache/clip_climas.npz').exists():
    INDICE=RESOURCE_ROOT/'cache/clip_climas.npz'
_cerrojo=threading.Lock()
_modelo=None
_procesador=None


def ubicacion_modelo():
    carpeta=RESOURCE_ROOT/'models/clip'
    return str(carpeta) if (carpeta/'config.json').is_file() else MODELO


def cargar_modelo():
    global _modelo,_procesador
    with _cerrojo:
        if _modelo is None:
            import torch
            from transformers import CLIPModel,CLIPProcessor
            torch.set_num_threads(max(1,min(2,os.cpu_count() or 1)))
            _modelo=CLIPModel.from_pretrained(ubicacion_modelo(),local_files_only=True).eval()
            _procesador=CLIPProcessor.from_pretrained(ubicacion_modelo(),local_files_only=True)
        return _modelo,_procesador


def _tensor(valor):
    if hasattr(valor,'pooler_output'):return valor.pooler_output
    if hasattr(valor,'text_embeds'):return valor.text_embeds
    if hasattr(valor,'image_embeds'):return valor.image_embeds
    return valor


@lru_cache(maxsize=48)
def vector_texto(texto):
    import torch
    modelo,procesador=cargar_modelo()
    with torch.inference_mode():
        v=_tensor(modelo.get_text_features(**procesador(text=[texto],return_tensors='pt',padding=True)))
        v=v/v.norm(dim=-1,keepdim=True)
    return v.cpu().numpy()[0]


def buscar_fotos(texto,limite=3):
    """Solo consulta un índice ya preparado; no descarga pesos durante el uso."""
    if not INDICE.exists():return []
    try:
        import numpy as np
        with np.load(INDICE,allow_pickle=False) as d:
            vectores=d['vectores'];archivos=d['archivos']
        vector=vector_texto(texto)
        puntuaciones=vectores@vector
        indices=np.argsort(puntuaciones)[-limite:][::-1]
        return [dict(archivo=str(archivos[i]),similitud=float(puntuaciones[i]),fuente='CLIP local; no verifica el ID de clima') for i in indices]
    except (ImportError,OSError,ValueError,RuntimeError):
        return []


def consulta_ambiente(texto):
    t=texto.lower()
    partes=[]
    for claves,ingles in [(('lluv','llov'),'rainy weather'),(('atardecer','ocaso'),'sunset'),
        (('amanecer',),'sunrise'),(('noche',),'night'),(('niebla','neblina'),'foggy weather'),(('solead',),'sunny weather')]:
        if any(c in t for c in claves):partes.append(ingles)
    return 'a screenshot of Grand Theft Auto San Andreas with '+' and '.join(partes) if partes else None
