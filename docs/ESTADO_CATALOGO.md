# Estado y trabajo local completado

Se verificaron los 7578 PNG (5,5 GB): 1263 animaciones con seis archivos cada una, sin errores de integridad PNG ni IDs faltantes/duplicados respecto a `src/todo.txt`. El detalle esta en `assets/animations/catalogo_completo/informe_integridad.json`. La comprobacion no certifica el contenido visual: las capturas azules tambien pueden ser PNG validos. 185 archivos estan marcados por tamano bajo como indicio, no como diagnostico.

En el momento de la auditoria habia 51 descripciones automaticas, 36 por revisar y 1212 pendientes. Se conservaron originales, catalogos y descripciones. No se hicieron consultas a servicios de IA.

## Buscar sin API

```powershell
python -m tools.buscar_animacion levantar las manos
python -m tools.buscar_animacion hablar por telefono
python -m tools.buscar_animacion fumar cigarrillo
python -m tools.buscar_animacion correr
```

La busqueda compara terminos en espanol con pistas conservadoras de nombres tecnicos y descripciones existentes. No genera descripciones visuales ni adivina nombres opacos. Por ejemplo, `handsup` sugiere levantar las manos, pero `cs_1_a1` no se traduce sin evidencia. Todo resultado es una candidata, no una garantia de que la animacion encaje. Los IDs provienen de todo.txt.

Al reiniciar la app, las consultas incluyen estas candidatas locales como orientacion adicional. Se mantiene el listado completo y las marcas de incertidumbre. La seleccion final en la app sigue necesitando un modelo con cuota; la herramienta de consola funciona sin red.

## Repetir auditoria

```powershell
python -u auditar_catalogo.py
```

Lee las imagenes y escribe solo el informe. No borra ni altera capturas, no requiere claves y no gasta cuota. Los nuevos scripts no quedan ejecutandose en segundo plano tras este trabajo.
