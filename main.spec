# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=[
        'MetaTrader5',
        'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
        'pystray', 'pystray._win32',
        'hid',
        'src.hardware', 'src.keyboard', 'src.key_renderer',
        'src.mt5_bridge', 'src.config', 'src.gui', 'src.logger',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name='YallaPips_Keyboard',
    debug=False,
    strip=False,
    upx=True,
    console=False,         # no terminal window — runs silently in tray
    icon=None,
    uac_admin=False,
)
