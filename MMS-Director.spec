# PyInstaller onedir: recursos compartidos, sin descomprimir varios GB en cada inicio.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files,collect_submodules

root=Path(SPECPATH)
ligero=os.getenv('MMS_BUILD_LIGHT')=='1'
datas=[(str(root/'build/resources'),'.')]+collect_data_files('flet')+collect_data_files('flet_desktop')
hidden=collect_submodules('google.genai')+['flet_desktop','PyQt6.QtSvg','PIL.WebPImagePlugin']
if not ligero:hidden+=['transformers.models.clip.modeling_clip','transformers.models.clip.processing_clip']
excludes=['rembg','onnxruntime','sklearn','joblib','scipy','pandas','matplotlib','IPython','notebook','tensorflow','keras','cv2','torchvision','torchaudio']
if ligero:excludes+=['torch','transformers']
a=Analysis([str(root/'launcher.py')],pathex=[str(root)],binaries=[],datas=datas,
    hiddenimports=hidden,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=excludes,noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='MMS-Director',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='MMS-Director')
