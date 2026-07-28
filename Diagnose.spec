# -*- mode: python ; coding: utf-8 -*-
# Build: .venv\Scripts\pyinstaller Diagnose.spec
# Output: dist\CM Diagnose.exe  (console app — timings print live)

a = Analysis(
    ['diagnose.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pyodbc',
        'monthly_schedule',
        'monthly_schedule.db',
        'win32com',
        'win32com.client',
        'PyQt6.QtNetwork',
        'pywinauto',
        'pywinauto.controls.uia_controls',
        'comtypes',
        'comtypes.stream',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'pytest_qt', 'openpyxl'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CM Diagnose',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='bowery-emblem.ico',
)
