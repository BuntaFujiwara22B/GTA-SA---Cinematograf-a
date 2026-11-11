"""La petición puede conservar un encuadre sin confundirlo con la acción."""
import unittest

from src.preferencias_camara import preferencia_camara


class PreferenciasCamara(unittest.TestCase):
    def test_solo_las_instrucciones_de_camara_cambian_el_montaje_por_defecto(self):
        for texto in ('una persona camina durante 60 segundos',
            'un actor se queda fijo en su lugar al atardecer',
            'camina detrás de otra persona, sin música y con clima fijo',
            'un personaje quieto frente al vehículo',
            'un actor inmóvil frente a la cámara',
            'un personaje con la mirada fija en la cámara', '', None):
            with self.subTest(texto=texto):self.assertEqual(preferencia_camara(texto),'automatica')

    def test_presets_explicitos_se_conservan(self):
        casos=(
            ('cámara fija detrás del actor todo el tiempo','seguimiento_trasero'),
            ('una persona camina, cámara desde atrás durante toda la escena','seguimiento_trasero'),
            ('la cámara sigue al personaje','seguimiento_trasero'),
            ('cámara estática toda la escena','fija'),
            ('quiero un plano fijo del entorno','fija'),
            ('mantén una cámara lateral los 60 segundos','costado'),
            ('una cámara de costado, sin cortes','costado'),
            ('cámara POV durante todo el viaje','vehiculo_pov'),
            ('cámara en primera persona desde el asiento','vehiculo_pov'),
            ('quiero una cámara con giro frontal','giro_frontal'),
        )
        for texto,preset in casos:
            with self.subTest(texto=texto):self.assertEqual(preferencia_camara(texto),preset)

    def test_instrucciones_de_plano_unico_y_negaciones_de_cambios(self):
        for texto in ('sin cambios de cámara','no cambies de cámara',
            'quiero que no haya cambios de cámara','un solo plano durante 60 segundos',
            'plano secuencia de una caminata','conserva el mismo encuadre'):
            with self.subTest(texto=texto):self.assertEqual(preferencia_camara(texto),'fija')
        self.assertEqual(preferencia_camara('no cambies de cámara, mantenla detrás del actor'),'seguimiento_trasero')

    def test_pedir_cambios_no_congela_un_preset_mencionado_entre_los_planos(self):
        for texto in ('cambia de cámara cada 5 segundos','alterna cámaras cada cinco segundos',
            'varias cámaras: una detrás del actor y otra del entorno',
            'cámara fija cinco segundos, luego cambia de cámara',
            'no quiero una cámara fija. Quiero varias cámaras',
            'montaje automático de una caminata'):
            with self.subTest(texto=texto):self.assertEqual(preferencia_camara(texto),'automatica')

    def test_la_ultima_instruccion_explicita_resuelve_una_correccion_del_usuario(self):
        self.assertEqual(preferencia_camara('varias cámaras. Mejor un solo plano detrás del actor'),
            'seguimiento_trasero')
        self.assertEqual(preferencia_camara('un solo plano. Mejor cambia de cámara cada 5 segundos'),
            'automatica')
        self.assertEqual(preferencia_camara('no quiero una cámara fija, quiero una cámara detrás del actor'),
            'seguimiento_trasero')

    def test_negacion_despues_de_la_mencion_de_camara_conserva_el_plano(self):
        for texto in ('quiero que la cámara no cambie durante toda la escena',
            'la cámara no debe cambiar', 'la cámara no tiene que cambiar durante los 60 segundos'):
            with self.subTest(texto=texto):self.assertEqual(preferencia_camara(texto),'fija')
        self.assertEqual(preferencia_camara('la cámara detrás del actor no debe cambiar'),
            'seguimiento_trasero')


if __name__=='__main__':unittest.main()
