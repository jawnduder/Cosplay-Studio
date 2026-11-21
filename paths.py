"""Where Cosplay Studio finds its files, from source (python app.py) or packaged (Cosplay Studio.exe).
DATA: read-only data shipped with the tool (catalog JSONs, icons, prebuilt). USER: writable files (settings, flags edits,
projects, builds) - next to the .exe (portable), or %APPDATA%\\Cosplay Studio if that folder can't be written."""
import os, sys
VERSION = "1.0.1"
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    DATA = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    USER = os.path.dirname(sys.executable)
    try:
        t = os.path.join(USER, ".write_test"); open(t, "w").close(); os.remove(t)
    except OSError:
        USER = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Cosplay Studio")
else:
    DATA = USER = os.path.dirname(os.path.abspath(__file__))
os.makedirs(USER, exist_ok=True)
def data(*p): return os.path.join(DATA, *p)
def user(*p): return os.path.join(USER, *p)
CONFIG = user("studio_config.json")
PROJECTS = user("Projects") if FROZEN else USER
DEFAULT_BUILDS = user("Builds") if FROZEN else os.path.join(os.path.dirname(USER), "builds")
