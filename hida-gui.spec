# hida_gui.spec — one-file GUI build (PyQt6)
# Produces: dist/hida-gui(.exe)

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
hidden = []

# PyQt6 is optional at install-time, but required for the GUI exe build:
hidden += collect_submodules("PyQt6")          # help PyInstaller find all Qt modules/hooks

# Bundle the Windows-bundled castxml.exe (and LICENSE) only on Windows
if sys.platform == "win32":
    datas += collect_data_files(
        "hida._vendor.castxml.windows",
        includes=["*.exe", "*.txt", "*.md"],
        excludes=[],
    )

block_cipher = None

a = Analysis(
    ['src/hida/cli_gui.py'],        # entry module for your CLI
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='hida-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,             # GUI: no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                 # e.g. 'assets/hida.ico' (Windows) or '.icns' on macOS
)
