"""Genera el capturador completo desde src/todo.txt sin tocar GTA."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATEGORIAS = ['STAND', 'SIT', 'LAY', 'WEAPON', 'CHAT', 'HURT', 'DANCE',
              'MIMIC', 'INTERACT', 'SEX', 'MOVE', 'CUTS', 'ATTACK', 'DEATH']


def generar():
    texto = (ROOT / 'src/todo.txt').read_text(encoding='utf-8').split('anim list', 1)[1]
    entradas = []
    orden_categorias = re.findall(r'^\[([^\]]+)\]', texto, re.M)
    orden_categorias = [c for c in orden_categorias if c in CATEGORIAS]
    if orden_categorias != CATEGORIAS:
        raise ValueError('Cambio el orden de las categorias: revisar el parser.')
    for cat in orden_categorias:
        bloque = re.search(r'^\[' + cat + r'\]\s*\n(.*?)(?=^\[|\Z)', texto, re.M | re.S)[1]
        filas = re.findall(r'^\s*(\d+)\s*=\s*([^,\r\n]+),\s*([^\r\n]+)', bloque, re.M)
        total = int(re.search(r'TOTAL\s*=\s*(\d+)', bloque, re.I)[1])
        if len(filas) != total or [int(f[0]) for f in filas] != list(range(1, total + 1)):
            raise ValueError(f'Conteo o indices incorrectos en {cat}')
        for idx, anim, lib in filas:
            anim, lib = anim.strip(), lib.strip()
            if not all(re.fullmatch(r'[A-Za-z0-9_.-]+', v) for v in (anim, lib)):
                raise ValueError(f'Nombre inesperado: {anim}, {lib}')
            entradas.append(dict(orden=len(entradas)+1, categoria=cat, idx=int(idx), anim=anim, lib=lib))
    huella = hashlib.sha256(json.dumps(entradas, sort_keys=True).encode()).hexdigest()[:12]
    s = (ROOT / 'animaciones_prueba.lua').read_text(encoding='utf-8')
    filas_lua = [f"    {{'{e['categoria']}', {e['idx']}, '{e['anim']}', '{e['lib']}'}}," for e in entradas]
    s = re.sub(r'local ANIMACIONES = \{.*?\n\}', 'local ANIMACIONES = {\n' + '\n'.join(filas_lua) + '\n}', s, count=1, flags=re.S)
    s = s.replace('AnimacionesPrueba', 'AnimacionesCatalogo').replace('animaciones_prueba_', 'animaciones_catalogo_')
    s = s.replace("%d/10 %s %s', orden,", "%d/%d %s %s', orden, #ANIMACIONES,")
    s = s.replace('Preparando prueba:', 'Preparando catalogo:')
    checkpoint = r'''
local completadas = {}
local rutaProgreso = getWorkingDirectory() .. '\\animaciones_progreso_HUELLA.txt'
local function cargarProgreso()
    completadas = {}
    local f = io.open(rutaProgreso, 'r')
    if not f then return end
    for linea in f:lines() do
        local n = tonumber(linea)
        if n and n >= 1 and n <= #ANIMACIONES then completadas[n] = true end
    end
    f:close()
end
local function guardarCompletada(orden)
    local f = assert(io.open(rutaProgreso, 'a'))
    assert(f:write(tostring(orden) .. '\n'))
    assert(f:flush())
    f:close()
    completadas[orden] = true
end
'''.replace('HUELLA', huella)
    # El progreso registra solicitudes completas; no garantiza PNG validos.
    s = s.replace('local function ejecutar()', checkpoint + '\nlocal function ejecutar()\n    cargarProgreso()')
    s = s.replace('        local a = ANIMACIONES[orden]', '        if not completadas[orden] then\n        local a = ANIMACIONES[orden]')
    s = s.replace('        if not ok then\n            registrar', '        if ok then guardarCompletada(orden) end\n        if not ok then\n            registrar')
    s = s.replace('        esperar(200)\n    end\nend', '        esperar(200)\n        end\n    end\nend')
    (ROOT / 'animaciones_catalogo.lua').write_text(s, encoding='utf-8')
    (ROOT / 'animaciones_catalogo_lista.json').write_text(json.dumps(dict(
        huella=huella, categorias=orden_categorias, total=len(entradas),
        animaciones=entradas), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Generadas {len(entradas)} animaciones en {len(orden_categorias)} categorias. Huella {huella}')


if __name__ == '__main__':
    generar()
