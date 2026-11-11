import unittest
from src.mvp_plan import plan_local, validar_plan
from src.mvp_mms import generar_mms,POS_INICIO
from src.reproduccion_animaciones import decidir_reproduccion
from test_mvp import leer


class Reproduccion(unittest.TestCase):
    def test_cuatro_manos_arriba_una_vez_y_mantener(self):
        p=plan_local('4 personajes levantan las manos durante 20 segundos')
        self.assertEqual(p.reproduccion,'mantener')
        # Una propuesta de bucle injustificada no reintroduce el error observado.
        p.reproduccion='bucle'
        p=validar_plan(p,'4 personajes levantan las manos durante 20 segundos')
        c=leer(generar_mms(actor_id=112,actores_ids=[112]*4,inicio=POS_INICIO,destino=None,
            accion='animacion',animacion_sugerida=p.animacion_sugerida,animar_actores=p.animar_actores,
            reproduccion=p.reproduccion,duracion=20))
        for n in range(1,5):
            self.assertEqual(c[f'ACTION_A_{n}']['Loop'],'0')
            self.assertEqual(c[f'ACTION_A_{n}']['Freeze'],'1')
        self.assertEqual(c['OBJ_1']['DIAL_TIME'],'20000')

    def test_baile_continuo_y_gestos_puntuales(self):
        self.assertEqual(plan_local('dos personas bailan').reproduccion,'bucle')
        self.assertEqual(plan_local('un personaje saluda').reproduccion,'una_vez')
        self.assertEqual(decidir_reproduccion('DANCE:3:DANCING:dance_loop','bailar una sola vez')[0],'una_vez')
        self.assertEqual(decidir_reproduccion('STAND:1:ped:handsup','levanta manos en bucle')[0],'bucle')
        self.assertEqual(decidir_reproduccion('STAND:1:ped:handsup','levanta y baja las manos')[0],'una_vez')
