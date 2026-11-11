"""Indexa las tandas completas. Nunca desplaza IDs para compensar fotos ausentes."""
import json
import re
from pathlib import Path
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def firma_visual(ruta):
    with Image.open(ruta) as imagen:
        rgb=np.asarray(imagen.convert('RGB').resize((96,54)),dtype=float)/255
    # Cuantiles por canal: toleran el cambio de encuadre de las horas 0 y 1.
    return np.concatenate([np.quantile(rgb[:,:,c],[.1,.25,.5,.75,.9]) for c in range(3)])


def alinear(fotos,referencias):
    """Alineación monótona con saltos: estimación visual, nunca verificación."""
    a=np.array([firma_visual(p) for p in fotos])
    b=np.array([firma_visual(p) for p in referencias])
    # Compensación moderada del cambio de iluminación entre horas nocturnas.
    a=a-np.median(a,axis=0)+np.median(b,axis=0)
    costes=np.sqrt(np.mean((a[:,None,:]-b[None,:,:])**2,axis=2))
    n,m=costes.shape
    dp=np.full((n+1,m+1),np.inf);dp[0,0]=0
    pasos={};penalizacion=.18
    for i in range(n+1):
        for j in range(m+1):
            if i<n and j<m and dp[i,j]+costes[i,j]<dp[i+1,j+1]:
                dp[i+1,j+1]=dp[i,j]+costes[i,j];pasos[i+1,j+1]=(i,j,'foto')
            if i<n and dp[i,j]+penalizacion<dp[i+1,j]:
                dp[i+1,j]=dp[i,j]+penalizacion;pasos[i+1,j]=(i,j,'extra')
            if j<m and dp[i,j]+penalizacion<dp[i,j+1]:
                dp[i,j+1]=dp[i,j]+penalizacion;pasos[i,j+1]=(i,j,'ausente')
    pares={};i,j=n,m
    while i or j:
        pi,pj,tipo=pasos[i,j]
        if tipo=='foto':pares[pj]=(fotos[pi],float(costes[pi,pj]))
        i,j=pi,pj
    return pares


def indexar(assets):
    ruta=assets/'climas_catalogo.json'
    previo=json.loads(ruta.read_text(encoding='utf-8')) if ruta.exists() else {}
    previews=[p for p in previo.get('previews',[]) if p.get('verificado') is True]
    ocupados={(p['hora'],p['clima_id']) for p in previews}
    tandas=[]
    for hora in range(24):
        carpeta=assets/f'hora_{hora}'
        fotos=list(carpeta.glob('*.png'))
        numeros={}
        for foto in fotos:
            m=re.fullmatch(r'Captura de pantalla \((\d+)\)\.png',foto.name)
            if m:
                numeros[int(m[1])]=foto
        ids=sorted(numeros)
        completa=len(fotos)==45 and len(ids)==45 and ids==list(range(ids[0],ids[0]+45))
        tandas.append(dict(hora=hora,fotos=len(fotos),estado='orden_completo' if completa else 'orden_ambiguo',
            primera=ids[0] if ids else None,ultima=ids[-1] if ids else None))
        if not completa:
            continue
        # La primera captura precede a aplicar el primer objetivo de clima.
        # Confirmado en hora 21 por el resultado en GTA: captura 1295 = clima 19,
        # mientras 1294 (la foto rosada anterior) corresponde al clima 18.
        for clima_id,n in enumerate(ids[1:]):
            if (hora,clima_id) not in ocupados:
                previews.append(dict(hora=hora,clima_id=clima_id,
                    minuto=hora if hora<=13 else None,
                    archivo=numeros[n].relative_to(assets).as_posix(),
                    asociacion='tanda_con_captura_inicial',verificado=False,
                    referencia='Desfase de una captura contrastado con GTA a hora 21, clima 19'))
    # Inspección de las capturas: la primera de hora 3 es diurna, anterior a
    # aplicar 03:03. Se usa el resto como referencia nocturna, desplazado uno.
    ref=sorted((assets/'hora_3').glob('*.png'),key=lambda p:int(re.search(r'\((\d+)\)',p.name)[1]))
    if len(ref)==45:
        previews=[p for p in previews if p.get('verificado') or p['hora'] not in range(6)]
        for hora in range(6):
            fotos=sorted((assets/f'hora_{hora}').glob('*.png'),key=lambda p:int(re.search(r'\((\d+)\)',p.name)[1]))
            if not fotos:continue
            pares=alinear(fotos,ref[1:]) if hora!=3 else {i:(p,0.0) for i,p in enumerate(ref[1:])}
            for clima_id,(foto,error) in pares.items():
                if (hora,clima_id) not in ocupados:
                    previews.append(dict(hora=hora,clima_id=clima_id,minuto=hora,
                        archivo=foto.relative_to(assets).as_posix(),asociacion='estimacion_visual_secuencial',
                        verificado=False,error_visual=round(error,5),referencia='hora_3; primera foto diurna excluida'))
    return dict(version=2,nota='ID de clima cero basado. Asociaciones por orden segun la guia o estimadas '
        'por alineacion visual nocturna. Ninguna estimacion prueba el clima real del mod; no inventar capturas ausentes.',
        previews=previews,tandas=tandas)


if __name__=='__main__':
    assets=ROOT/'assets'
    datos=indexar(assets)
    (assets/'climas_catalogo.json').write_text(json.dumps(datos,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Tandas completas:',sum(t['estado']=='orden_completo' for t in datos['tandas']))
    print('Tandas ambiguas:',[t['hora'] for t in datos['tandas'] if t['estado']=='orden_ambiguo'])
