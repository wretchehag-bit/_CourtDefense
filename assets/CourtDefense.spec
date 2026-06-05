# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Court Defense AI
# Build: python -m PyInstaller assets/CourtDefense.spec --distpath dist --buildpath build_tmp -y

a = Analysis(
    ['../run_app.py'],
    pathex=['../src'],
    binaries=[],
    datas=[
        ('../src/court_defense', 'court_defense'),  # Bundle entire package
    ],
    hiddenimports=[
        'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.messagebox',
        'court_defense', 'court_defense.core', 'court_defense.api',
        'faster_whisper', 'anthropic', 'fastapi', 'uvicorn', 'pywebview',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CourtDefense',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
