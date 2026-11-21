# PyInstaller spec for Cosplay Studio (one-folder build).   run: build_exe.bat
import os
here = os.path.abspath(SPECPATH)
datas = [(os.path.join(here, f), ".") for f in ("anim_scan.json", "animations.json", "wardrobe.json", "profiles.json", "flags.json", "app.png")]
datas += [(os.path.join(here, "icons"), "icons"), (os.path.join(here, "prebuilt"), "prebuilt")]
excl = ["tkinter", "numpy", "PIL", "matplotlib", "unittest", "pydoc", "email", "http", "xmlrpc",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtOpenGL", "PySide6.QtSvg",
        "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtSerialPort", "PySide6.QtDesigner", "PySide6.QtHelp"]
a = Analysis([os.path.join(here, "app.py")], pathex=[here], datas=datas, hiddenimports=["build_mod"], excludes=excl)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Cosplay Studio", console=False, icon=os.path.join(here, "app.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="Cosplay Studio")
