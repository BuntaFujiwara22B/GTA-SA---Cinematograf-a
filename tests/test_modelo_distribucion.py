"""Los pesos supervisados son recursos de ejecución independientes de CLIP."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.preparar_distribucion as distribucion


class ModeloDistribucion(unittest.TestCase):
    def test_copia_metadata_y_pesos_sin_necesitar_clip_ni_red(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz=Path(temporal)/'origen'
            destino=Path(temporal)/'paquete'
            fuente=raiz/'models/intenciones'
            fuente.mkdir(parents=True)
            (fuente/'metadata.json').write_bytes(b'{"version":1}')
            (fuente/'pesos.npz').write_bytes(b'pesos-supervisados')
            with patch.object(distribucion,'ROOT',raiz):
                distribucion.copiar_modelo_intenciones(destino)
            for nombre in ('metadata.json','pesos.npz'):
                self.assertEqual((destino/'models/intenciones'/nombre).read_bytes(),(fuente/nombre).read_bytes())
            self.assertFalse((destino/'models/clip').exists())

    def test_no_inventa_modelo_si_no_hay_entrenamiento(self):
        with tempfile.TemporaryDirectory() as temporal:
            destino=Path(temporal)/'paquete'
            with patch.object(distribucion,'ROOT',Path(temporal)/'origen'):
                distribucion.copiar_modelo_intenciones(destino)
            self.assertFalse(destino.exists())

    def test_rechaza_un_artefacto_incompleto_antes_de_copiar(self):
        for existente,faltante in (('metadata.json','pesos.npz'),('pesos.npz','metadata.json')):
            with self.subTest(existente=existente),tempfile.TemporaryDirectory() as temporal:
                raiz=Path(temporal)/'origen'
                fuente=raiz/'models/intenciones'
                fuente.mkdir(parents=True)
                (fuente/existente).touch()
                destino=Path(temporal)/'paquete'
                with patch.object(distribucion,'ROOT',raiz),self.assertRaisesRegex(RuntimeError,faltante):
                    distribucion.copiar_modelo_intenciones(destino)
                self.assertFalse(destino.exists())


if __name__=='__main__':unittest.main()
