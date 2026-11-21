# Cosplay Studio

A Windows desktop tool for **Clair Obscur: Expedition 33** that gives every outfit and haircut its own exploration
animations (idle, walk, run, sprint, sprint start) and builds a ready-to-install mod (.pak / .utoc / .ucas, or a .zip
for Vortex). Pure Python + PySide6; it reads and writes Unreal Engine 5.4 cooked and IoStore files itself (no retoc,
UAssetGUI or game files needed at runtime).

## Run from source

Requires Python 3.10+ on Windows.

```
python -m pip install PySide6
python app.py
```

## Build the executable (the file released on Nexus Mods)

```
build_exe.bat
```

`build_exe.bat` runs `python -m pip install --upgrade pyinstaller PySide6`, then
`python -m PyInstaller --noconfirm --clean CosplayStudio.spec`, and writes:

- `..\dist\Cosplay Studio\Cosplay Studio.exe` (one-folder build, no installer)
- `..\release\CosplayStudio_1.0.1.zip` (that folder zipped)

The .exe is an unmodified PyInstaller bootloader running the Python files in this repository.

## Layout

| Path | What it is |
| --- | --- |
| `app.py` | the window (PySide6) |
| `model.py` | catalog, project files, warnings |
| `generator.py` | turns a project into data-table rows and blend spaces |
| `writer.py`, `cooked.py` | write cooked UE 5.4 assets (data table, blend spaces) |
| `zen.py`, `iostore.py`, `cityhash.py`, `blake3.py` | convert to Zen packages and pack the IoStore container |
| `build_mod.py` | the build pipeline (also usable from the command line) |
| `paths.py` | where data and user files live (source vs packaged) |
| `*.json`, `icons/` | catalog data extracted from the game (animations, wardrobe items, profiles, icons) |
| `prebuilt/` | the modified `BP_CharacterSkinComponent` (animation logic, same for every build) and the blend space template |
| `tools/` | scripts used to produce the catalog and the prebuilt logic file from the game's files (not needed to run or build) |

The tools import the main modules: run them from the repository root with `set PYTHONPATH=.`.

## Credits and licenses

See `THIRD_PARTY_NOTICES.txt`. Game content belongs to Sandfall Interactive / Kepler Interactive.
