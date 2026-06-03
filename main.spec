# -*- mode: python ; coding: utf-8 -*-
import os
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[SPECPATH],
    binaries=[],
datas=[
    (os.path.join(SPECPATH, 'config.json'), '.'),
    (os.path.join(SPECPATH, 'src'), 'src'),
],
hiddenimports=[
    'numpy',
    'numpy.core',
    'numpy.core.multiarray',
    'numpy.core._multiarray_umath',
    'numpy.core._methods',
    'numpy.core.fromnumeric',
    'numpy.core.numerictypes',
    'numpy.lib',
    'numpy.lib.stride_tricks',
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
