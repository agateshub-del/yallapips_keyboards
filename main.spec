import os
import sys
import glob

block_cipher = None

# Find hidapi.dll - check hid package folder AND System32
hid_dll = glob.glob(os.path.join(sys.prefix, '**', 'hidapi.dll'), recursive=True)
hid_dll += glob.glob('C:/Windows/System32/hidapi.dll')
hid_bins = [(dll, '.') for dll in hid_dll]

a = Analysis(
    ['main.py'],
    pathex=[SPECPATH],
    binaries=hid_bins,
    datas=[
        (os.path.join(SPECPATH, 'config.json'), '.'),
        (os.path.join(SPECPATH, 'src'), 'src'),
    ],
    hiddenimports=[
        'numpy', 'numpy.core', 'numpy.core.multiarray',
        'numpy.core._multiarray_umath',
        'MetaTrader5',
        'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
        'pystray', 'pystray._win32',
        'pywinusb', 'pywinusb.hid',
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
    debug=False, strip=False, upx=True,
    console=False, icon=None,
)
