"""Mismo modelo local de los NPC: BRIA-RMBG ONNX. Nunca sobrescribe originales."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
from src.paths import ASSETS
from src.catalogos_entidades import disponibles


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limite',type=int,default=1000)
    parser.add_argument('--rapido',action='store_true');parser.add_argument('--rehacer',action='store_true')
    args=parser.parse_args()
    import onnxruntime as ort
    modelo=Path(__file__).resolve().parent/'.maintenance/models/u2netp.onnx' if args.rapido else Path.home()/'.rembg/models/bria-rmbg/bria-rmbg.onnx'
    if args.rapido and modelo.exists():
        import hashlib
        if hashlib.md5(modelo.read_bytes()).hexdigest()!='8e83ca70e441ab06c318d82300c84806':raise SystemExit('El modelo rápido no coincide con la huella publicada.')
    if not modelo.exists():raise SystemExit('No está el modelo BRIA usado para los NPC. No se descargó nada.')
    carpeta=ASSETS/'vehicles_cutouts';carpeta.mkdir(exist_ok=True)
    manifiesto=carpeta/'catalogo.json'
    datos=json.loads(manifiesto.read_text(encoding='utf-8')) if manifiesto.exists() else {'version':1,'resultados':{}}
    ops=ort.SessionOptions();ops.intra_op_num_threads=2;ops.inter_op_num_threads=1
    ops.log_severity_level=3
    ops.enable_cpu_mem_arena=False
    sesion=ort.InferenceSession(str(modelo),sess_options=ops,providers=['CPUExecutionProvider'])
    print('BRIA local cargado. Originales conservados.',flush=True)
    pendientes=[v for v in disponibles('vehicles') if args.rehacer or v['foto'] not in datos['resultados']]
    for v in pendientes[:args.limite]:
        original=ASSETS/v['foto']
        with Image.open(original) as im:
            im=im.convert('RGB')
            tam=320 if args.rapido else 1024
            a=np.asarray(im.resize((tam,tam),Image.Resampling.LANCZOS),dtype=np.float32)
            a=a/max(float(a.max()),1e-6)
            a=(a-np.array([.485,.456,.406],dtype=np.float32))/np.array([.229,.224,.225],dtype=np.float32)
            pred=sesion.run(None,{sesion.get_inputs()[0].name:a.transpose(2,0,1)[None]})[0].squeeze()
            pred=(pred-pred.min())/max(float(pred.max()-pred.min()),1e-6)
            mask=Image.fromarray((pred*255).astype('uint8')).resize(im.size,Image.Resampling.LANCZOS)
            mask=mask.point(lambda p:0 if p<20 else 255 if p>245 else p)
            rgba=im.convert('RGBA');rgba.putalpha(mask)
            bbox=mask.getbbox();area=float(np.mean(np.asarray(mask)>128))
            usable=bbox is not None and .003<area<.65
            if usable:
                rgba=rgba.crop(bbox)
                ruta=carpeta/(original.stem+'.png');rgba.save(ruta,optimize=True)
                datos['resultados'][v['foto']]=dict(archivo=ruta.relative_to(ASSETS).as_posix(),usable=True,
                    area=round(area,4),revision_visual=False,modelo='u2netp' if args.rapido else 'bria-rmbg')
            else:
                datos['resultados'][v['foto']]=dict(usable=False,motivo='Máscara fuera de los límites; conservar imagen original.')
        temporal=manifiesto.with_suffix('.tmp');temporal.write_text(json.dumps(datos,ensure_ascii=False,indent=2),encoding='utf-8');temporal.replace(manifiesto)
        print(f"{len(datos['resultados'])}/66 · {v['nombre']} · {'recortado' if usable else 'original'}",flush=True)


if __name__=='__main__':main()
