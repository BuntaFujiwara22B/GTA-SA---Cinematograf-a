# Evidencia del ANIMA.mms editado por el usuario

Se conserva una copia completa en `templates/seguimiento_vehiculo_referencia.mms`. El texto pegado en el chat era una version anterior; el archivo guardado incluye OBJ_0 a OBJ_5, Vehicle_1, ACTION_A_2 y ACTION_V_1.

## Camaras incorporadas al exportador

- OBJ_1: seguimiento del actor, PLA_CUM_MODE=6 y CUM_ACTOR=1. Offsets OX=-0.52, OY=-3.84, OZ=0.72.
- OBJ_2: seguimiento lateral del actor, modo 6. Offsets OX=5.08, OY=-0.720001, OZ=0.
- Se mantienen los offsets locales y se trasladan/rotan las posiciones iniciales alrededor del actor. Se exporta la variante elegida, sin introducir vehiculos ni acciones de otro tipo en una caminata.
- OBJ_3 y OBJ_4 usan modo 7, CUM_VEH=1 y tienen otros offsets. Esto se conserva como referencia de la camara del vehiculo, todavia no se exporta automaticamente.

Los modos trasero y lateral ya aparecen en la app. Se comprobaron campos, offsets y estructura; falta reproducir las nuevas exportaciones dentro de GTA. POV y seguimiento frontal siguen pendientes de ejemplos.

## El coche arranca antes de subir el personaje

En el ejemplo:

1. Vehicle_1 se crea con OBJ=3.
2. ACTION_A_2 tiene Type=2, OBJ=3, SPHERE_ACTOR=1 y SPHERE_VEH2=1; es la accion de subir que preparo el usuario.
3. ACTION_V_1 tiene Type=2, OBJ=3 y SPHERE_VEH=1; es el desplazamiento del coche.

Ambas acciones se activan en el mismo objetivo. El orden de las secciones del archivo no establece que la segunda espere a terminar la primera. El coche no tiene una dependencia que confirme que el actor entro antes de iniciar su recorrido. Ademas, al terminar la caminata, el actor queda a unos 11 m de la posicion inicial del coche.

La secuencia deseada es crear el coche -> acercar/subir al actor -> comprobar que esta dentro y en el asiento correcto -> activar la ruta del vehiculo. Mover la accion del coche al objetivo siguiente con una espera fija solo reduce la carrera; no garantiza que el actor haya subido. Falta un ejemplo de un objetivo/condicion del mod que espere a tener al actor dentro del vehiculo para exportarlo con garantia de esa dependencia. No se inventaron campos para esa condicion ni se modifico el ANIMA.mms del juego.
