# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Auto-collect hidapi DLL and data files
hid_datas    = collect_data_files('hid')
hid_binaries = collect_dynamic_libs('hid')

a = Analysis(
    ['main.py'],
    pathex=[SPECPATH],
    binaries=hid_binaries,
    datas=hid_datas + [
        (os.path.join(SPECPATH, 'config.json'), '.'),
        (os.path.join(SPECPATH, 'src'), 'src'),
    ],
    hiddenimports=[
        'numpy',
        'numpy.core',
        'numpy.core.multiarray',
        'numpy.core._multiarray_umath',
        'MetaTrader5',
        'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
        'pystray', 'pystray._win32',
        'hid',
        'src.hardware',
        'src.keyboard',
        'src.key_renderer',
        'src.mt5_bridge',
        'src.config',
        'src.gui',
        'src.logger',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='YallaPips_Keyboard',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)
