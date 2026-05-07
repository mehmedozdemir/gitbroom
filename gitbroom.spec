# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/gitbroom/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/gitbroom/ui/theme/style_dark.qss', 'gitbroom/ui/theme'),
        ('src/gitbroom/ui/theme/style_light.qss', 'gitbroom/ui/theme'),
    ],
    hiddenimports=[
        'gitbroom',
        'gitbroom.core',
        'gitbroom.core.branch',
        'gitbroom.core.cleaner',
        'gitbroom.core.models',
        'gitbroom.core.repo',
        'gitbroom.core.scorer',
        'gitbroom.config',
        'gitbroom.config.settings',
        'gitbroom.gitlab',
        'gitbroom.gitlab.client',
        'gitbroom.gitlab.enricher',
        'gitbroom.ui',
        'gitbroom.ui.app',
        'gitbroom.ui.main_window',
        'gitbroom.ui.workers',
        'gitbroom.ui.theme.theme',
        'gitbroom.ui.models.branch_table_model',
        'gitbroom.ui.widgets.branch_detail',
        'gitbroom.ui.widgets.branch_table',
        'gitbroom.ui.widgets.commit_detail_dialog',
        'gitbroom.ui.widgets.delete_dialog',
        'gitbroom.ui.widgets.diff_highlighter',
        'gitbroom.ui.widgets.repo_selector',
        'gitbroom.ui.widgets.settings_dialog',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'git',
        'gitdb',
        'smmap',
        'tomllib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'unittest', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GitBroom',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GitBroom',
)
