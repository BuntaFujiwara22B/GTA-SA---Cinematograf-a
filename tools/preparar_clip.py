"""Indexa fotografías con CLIP en CPU; reanudable, sin llamadas a una API."""
import os
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS','1')
from pathlib import Path
import json
from src.paths import ASSETS
from src.clip_visual import cargar_modelo,_tensor,INDICE


def main():
    import numpy as np
    import torch
    from PIL import Image
    fotos=sorted(p for h in range(24) for p in (ASSETS/f'hora_{h}').glob('*.png'))
    archivos=[];vectores=[]
    if INDICE.exists():
        with np.load(INDICE,allow_pickle=False) as d:
            archivos=list(d['archivos']);vectores=list(d['vectores'])
    hechos=set(archivos)
    pendientes=[p for p in fotos if p.relative_to(ASSETS).as_posix() not in hechos]
    print(f'CLIP: {len(archivos)} indexadas, {len(pendientes)} pendientes. Cargando pesos locales...',flush=True)
    modelo,procesador=cargar_modelo()
    INDICE.parent.mkdir(parents=True,exist_ok=True)
    for i in range(0,len(pendientes),8):
        lote=pendientes[i:i+8]
        imagenes=[]
        for p in lote:
            with Image.open(p) as im:imagenes.append(im.convert('RGB'))
        with torch.inference_mode():
            v=_tensor(modelo.get_image_features(**procesador(images=imagenes,return_tensors='pt')))
            v=v/v.norm(dim=-1,keepdim=True)
        vectores.extend(v.cpu().numpy());archivos.extend(p.relative_to(ASSETS).as_posix() for p in lote)
        temporal=INDICE.with_suffix('.tmp.npz')
        np.savez_compressed(temporal,archivos=np.array(archivos,dtype=str),vectores=np.array(vectores,dtype=np.float32))
        temporal.replace(INDICE)
        for im in imagenes:im.close()
        print(f'CLIP: {len(archivos)}/{len(fotos)}',flush=True)
    print('Índice visual completado.',flush=True)


if __name__=='__main__':main()
