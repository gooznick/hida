# hida_cli.spec — one-file console build (no PyQt6)
# Produces: dist/hida(.exe)

import sys
from PyInstaller.utils.hooks import collect_data_files

# Bundle the Windows-bundled castxml.exe (and LICENSE) only on Windows
datas = []
if sys.platform == "win32":
    datas += collect_data_files(
        "hida.bin",
        includes=["*.exe", "*.txt"],
        excludes=[],
    )
datas += collect_data_files(
    "hida.img",
    includes=["*.ico", "*.jpg"],
    excludes=[],
)
block_cipher = None

a = Analysis(
    ['src/hida/cli.py'],        # entry module for your CLI
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file build: pass binaries/zipfiles/datas into EXE
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='hida',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,              # console app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="src/hida/img/hida.ico",
)
