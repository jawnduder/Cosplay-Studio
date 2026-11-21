"""Cosplay Studio - desktop window (PySide6).   run: python app.py"""
import os, sys, json, traceback
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap, QAction, QColor, QPainter, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QTabBar, QLabel, QPushButton, QGridLayout, QDialog, QLineEdit, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox, QPlainTextEdit, QFormLayout, QDialogButtonBox, QFrame, QSplitter,
    QInputDialog, QToolButton, QMenu)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paths, model
from model import SLOTS, SLOT_LABEL, CHARACTERS, short
CONFIG = paths.CONFIG
SOURCES = [("All sources", None), ("Heroes", "hero"), ("Enemies", "enemy"), ("NPCs", "npc"), ("Animation packs", "library"), ("Other", "other")]
EDIT_BADGE = QColor(230, 170, 60)

def load_cfg():
    try: cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}
    except (OSError, ValueError): cfg = {}
    if not cfg.get("output"): cfg["output"] = paths.DEFAULT_BUILDS
    cfg.setdefault("zip", True)
    return cfg

# ------------------------------------------------------------------ animation picker
class AnimPicker(QDialog):
    def __init__(self, cat, slot, current, parent=None):
        super().__init__(parent); self.cat, self.choice = cat, None
        self.setWindowTitle("Choose %s animation" % slot); self.resize(900, 600)
        v = QVBoxLayout(self)
        row = QHBoxLayout(); v.addLayout(row)
        self.q = QLineEdit(); self.q.setPlaceholderText("Search name, owner or path..."); row.addWidget(self.q, 3)
        self.src = QComboBox(); [self.src.addItem(n, s) for n, s in SOURCES]; row.addWidget(self.src)
        self.sl = QComboBox(); self.sl.addItem("Any slot", None); [self.sl.addItem(SLOT_LABEL[s], s) for s in SLOTS if s != "sprint_start"]; row.addWidget(self.sl)
        self.sl.setCurrentIndex({"idle": 1, "walk": 2, "run": 3, "sprint": 4, "sprint_start": 4}.get(slot, 0))
        self.world = QCheckBox("World locomotion only"); row.addWidget(self.world)
        self.battle = QCheckBox("Hide battle"); self.battle.setChecked(True); row.addWidget(self.battle)
        self.t = QTableWidget(0, 5); self.t.setHorizontalHeaderLabels(["Animation", "Owner", "Source", "Slot", "Notes"])
        self.t.setSelectionBehavior(QAbstractItemView.SelectRows); self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); self.t.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.t.verticalHeader().hide(); v.addWidget(self.t)
        self.info = QLabel("Current: " + short(current)); v.addWidget(self.info)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); v.addWidget(b)
        b.accepted.connect(self.take); b.rejected.connect(self.reject); self.t.doubleClicked.connect(self.take)
        for w in (self.q,): w.textChanged.connect(self.fill)
        for w in (self.src, self.sl): w.currentIndexChanged.connect(self.fill)
        for w in (self.world, self.battle): w.toggled.connect(self.fill)
        self.fill()
    def fill(self):
        rows = list(self.cat.search(self.q.text(), self.src.currentData(), self.sl.currentData(), self.battle.isChecked(), self.world.isChecked()))[:3000]
        self.t.setRowCount(len(rows))
        for i, a in enumerate(rows):
            note = self.cat.bugged(a["path"])
            vals = [a["name"], a["owner"], a["source"], a["slot"] or "", ("⚠ " + note) if note else ("world set" if a["locomotion"] else "")]
            for j, val in enumerate(vals):
                it = QTableWidgetItem(val); it.setData(Qt.UserRole, a["path"]); it.setToolTip(a["path"])
                if note: it.setForeground(QColor(220, 90, 70))
                self.t.setItem(i, j, it)
    def take(self):
        r = self.t.currentRow()
        if r < 0: return
        self.choice = self.t.item(r, 0).data(Qt.UserRole); self.accept()

# ------------------------------------------------------------------ enemy set picker
class SetPicker(QDialog):
    def __init__(self, cat, parent=None):
        super().__init__(parent); self.choice = None; self.setWindowTitle("Use an enemy / NPC world set"); self.resize(700, 500)
        v = QVBoxLayout(self); self.q = QLineEdit(); self.q.setPlaceholderText("Filter..."); v.addWidget(self.q)
        self.lst = QListWidget(); v.addWidget(self.lst); self.sets = cat.sets; self.cat = cat
        self.sprint = QCheckBox("Also use the run as sprint (marked as a copy)"); self.sprint.setChecked(True); v.addWidget(self.sprint)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); v.addWidget(b)
        b.accepted.connect(self.take); b.rejected.connect(self.reject); self.lst.itemDoubleClicked.connect(self.take)
        self.q.textChanged.connect(self.fill); self.fill()
    def fill(self):
        self.lst.clear()
        for s in self.sets:
            if self.q.text().lower() not in s["name"].lower(): continue
            bug = any(self.cat.bugged(s.get(k)) for k in ("idle", "walk", "run") if s.get(k))
            it = QListWidgetItem(("⚠ " if bug else "") + "%s   —   idle: %s   walk: %s   run: %s" % (s["name"], short(s.get("idle")), short(s.get("walk")), short(s.get("run"))))
            it.setData(Qt.UserRole, s); self.lst.addItem(it)
    def take(self):
        it = self.lst.currentItem()
        if it: self.choice = dict(it.data(Qt.UserRole)); self.choice["_sprint"] = self.sprint.isChecked(); self.accept()

# ------------------------------------------------------------------ settings
class Settings(QDialog):
    KEYS = [("output", "Build output folder (where the .pak / .utoc / .ucas or .zip go)", True)]
    def __init__(self, cfg, parent=None):
        super().__init__(parent); self.setWindowTitle("Settings"); self.cfg = dict(cfg); self.resize(760, 260)
        f = QFormLayout(self); self.ed = {}
        for k, label, is_dir in self.KEYS:
            row = QHBoxLayout(); e = QLineEdit(self.cfg.get(k, "")); b = QPushButton("Browse...")
            b.clicked.connect(lambda _=False, e=e, d=is_dir: self.browse(e, d)); row.addWidget(e); row.addWidget(b)
            w = QWidget(); w.setLayout(row); f.addRow(label, w); self.ed[k] = e
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); f.addRow(bb); bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
    def browse(self, e, is_dir):
        p = QFileDialog.getExistingDirectory(self, "Choose folder", e.text()) if is_dir else QFileDialog.getOpenFileName(self, "Choose file", e.text())[0]
        if p: e.setText(os.path.normpath(p))
    def result_cfg(self):
        for k, e in self.ed.items(): self.cfg[k] = e.text().strip()
        return self.cfg

def open_in_explorer(path):
    """Explorer with the file selected (or the folder opened)."""
    import subprocess
    if not path: return
    if os.path.isfile(path): subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif os.path.isdir(path): os.startfile(path) if hasattr(os, "startfile") else subprocess.Popen(["xdg-open", path])
    elif os.path.isdir(os.path.dirname(path)): open_in_explorer(os.path.dirname(path))

# ------------------------------------------------------------------ build worker
class BuildWorker(QThread):
    line = Signal(str); done = Signal(bool, str)
    def __init__(self, cfg, assignments, name, pack, zip_=False):
        super().__init__(); self.cfg, self.a, self.name, self.pack, self.zip = cfg, assignments, name, pack, zip_
    def run(self):
        try:
            import build_mod
            ok, res = build_mod.build(self.cfg, self.a, self.name, self.pack, log=lambda s: self.line.emit(str(s)), do_zip=self.zip)
            self.done.emit(ok, str(res))
        except Exception:
            self.done.emit(False, traceback.format_exc())

class BuildDialog(QDialog):
    def __init__(self, cfg, assignments, parent=None):
        super().__init__(parent); self.setWindowTitle("Build mod"); self.resize(700, 450)
        v = QVBoxLayout(self); f = QFormLayout(); v.addLayout(f)
        self.name = QLineEdit("CosplayStudio_MyMod"); f.addRow("Mod name", self.name)
        self.zip = QCheckBox("Compress the .pak / .utoc / .ucas into a .zip (for Vortex)"); self.zip.setChecked(bool(cfg.get("zip", True))); f.addRow("", self.zip)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); v.addWidget(self.log)
        self.go = QPushButton("Build"); v.addWidget(self.go); self.go.clicked.connect(self.start)
        self.cfg, self.a = cfg, assignments
    def start(self, *_):
        try:
            self.go.setEnabled(False); self.log.clear(); self.log.appendPlainText("Starting build...")
            zip_ = self.zip.isChecked()
            self.cfg["zip"] = self.zip.isChecked()
            try: json.dump(self.cfg, open(CONFIG, "w"), indent=1)
            except OSError: pass
            self.w = BuildWorker(self.cfg, self.a, self.name.text().strip() or "CosplayStudio_MyMod", True, zip_)
            self.w.line.connect(self.log.appendPlainText); self.w.done.connect(self.on_done); self.w.start()
        except Exception:
            self.log.appendPlainText(traceback.format_exc()); self.go.setEnabled(True)
    def on_done(self, ok, msg):
        self.log.appendPlainText(("\nDONE: " if ok else "\nFAILED: ") + msg); self.go.setEnabled(True)
        box = QMessageBox(self); box.setWindowTitle("Complete" if ok else "Build failed")
        box.setIcon(QMessageBox.Information if ok else QMessageBox.Warning)
        box.setText(("Build complete:\n" if ok else "The build failed:\n") + msg)
        copy = box.addButton("Copy to clipboard", QMessageBox.ActionRole)
        folder = box.addButton("Open builds folder", QMessageBox.ActionRole)
        close = box.addButton("Close", QMessageBox.AcceptRole)
        try: folder.clicked.disconnect()
        except (RuntimeError, TypeError): pass
        folder.clicked.connect(lambda: open_in_explorer(msg if ok and os.path.exists(msg) else self.cfg.get("output", "")))
        try: copy.clicked.disconnect()                # don't let the copy button close the popup
        except (RuntimeError, TypeError): pass
        copy.clicked.connect(lambda: (QApplication.clipboard().setText(self.log.toPlainText()), copy.setText("Copied")))
        box.exec()
        if box.clickedButton() is close: self.accept()

# ------------------------------------------------------------------ main window
class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Cosplay Studio " + paths.VERSION); self.resize(1400, 860)
        self.cfg = load_cfg()
        self.cat = model.Catalog(self.cfg); self.proj = model.Project()
        self.char, self.kind, self.item = CHARACTERS[0], "outfit", None
        self._build_menu(); self._build_ui(); self.refresh_grid()
    def _proj_dir(self):
        d = os.path.dirname(self.proj.path) if self.proj.path else paths.PROJECTS
        os.makedirs(d, exist_ok=True); return d
    # menus
    def _build_menu(self):
        m = self.menuBar().addMenu("&File")
        for text, fn, key in (("New project", self.new, "Ctrl+N"), ("Open project...", self.open, "Ctrl+O"), ("Save project", self.save, "Ctrl+S"),
                              ("Save project as...", self.save_as, None), (None, None, None), ("Settings...", self.settings, None), ("Quit", self.close, "Ctrl+Q")):
            if text is None: m.addSeparator(); continue
            a = QAction(text, self); a.triggered.connect(fn); m.addAction(a)
            if key: a.setShortcut(key)
        b = self.menuBar().addMenu("&Build"); a = QAction("Build mod...", self); a.setShortcut("Ctrl+B"); a.triggered.connect(self.build); b.addAction(a)
    # layout
    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root); v = QVBoxLayout(root)
        top = QHBoxLayout(); v.addLayout(top)
        self.chars = QTabBar(); [self.chars.addTab(c) for c in CHARACTERS]; self.chars.currentChanged.connect(self.on_char); top.addWidget(self.chars)
        top.addStretch(1)
        self.kinds = QTabBar(); self.kinds.addTab("Outfits"); self.kinds.addTab("Haircuts"); self.kinds.currentChanged.connect(self.on_kind); top.addWidget(self.kinds)
        split = QSplitter(); v.addWidget(split, 1)
        self.grid = QListWidget(); self.grid.setViewMode(QListWidget.IconMode); self.grid.setIconSize(QSize(150, 150))
        self.grid.setGridSize(QSize(176, 200)); self.grid.setResizeMode(QListWidget.Adjust); self.grid.setMovement(QListWidget.Static)
        self.grid.setWordWrap(True); self.grid.currentItemChanged.connect(self.on_item); split.addWidget(self.grid)
        self.detail = QWidget(); split.addWidget(self.detail); split.setSizes([820, 560])
        d = QVBoxLayout(self.detail)
        self.pic = QLabel(); self.pic.setFixedSize(220, 220); self.pic.setAlignment(Qt.AlignCenter); d.addWidget(self.pic, 0, Qt.AlignHCenter)
        self.title = QLabel(); f = self.title.font(); f.setPointSize(16); f.setBold(True); self.title.setFont(f); d.addWidget(self.title)
        self.sub = QLabel(); self.sub.setStyleSheet("color: gray"); self.sub.setTextInteractionFlags(Qt.TextSelectableByMouse); d.addWidget(self.sub)
        g = QGridLayout(); d.addLayout(g); self.slot_w = {}
        for r, s in enumerate(SLOTS):
            g.addWidget(QLabel("<b>%s</b>" % SLOT_LABEL[s]), r, 0)
            val = QLabel(); val.setWordWrap(True); val.setTextInteractionFlags(Qt.TextSelectableByMouse); g.addWidget(val, r, 1)
            ch = QPushButton("Choose..."); ch.clicked.connect(lambda _=False, s=s: self.choose(s)); g.addWidget(ch, r, 2)
            kp = QPushButton("Keep"); kp.setToolTip("Keep the item's own animation"); kp.clicked.connect(lambda _=False, s=s: self.keep(s)); g.addWidget(kp, r, 3)
            self.slot_w[s] = (val, ch, kp)
        g.setColumnStretch(1, 1)
        row = QHBoxLayout(); d.addLayout(row)
        self.use_set = QPushButton("Use enemy / NPC set..."); self.use_set.clicked.connect(self.apply_set); row.addWidget(self.use_set)
        self.copy_from = QPushButton("Copy from item..."); self.copy_from.clicked.connect(self.copy_item); row.addWidget(self.copy_from)
        self.reset = QPushButton("Reset item"); self.reset.clicked.connect(self.reset_item); row.addWidget(self.reset)
        self.apply_all = QCheckBox("Apply to every outfit of this character that doesn't set its own")
        self.apply_all.setToolTip("Expedition is the character's base outfit. Off: only Expedition changes (other outfits get the "
                                  "vanilla animations written into them). On: every outfit that inherits these slots changes too.")
        self.apply_all.toggled.connect(self.on_apply_all); d.addWidget(self.apply_all)
        self.notes = QLabel(); self.notes.setWordWrap(True); d.addWidget(self.notes); d.addStretch(1)
        self.status = self.statusBar()
    # ---------------- grid
    def on_char(self, i): self.char = CHARACTERS[i]; self.refresh_grid()
    def on_kind(self, i): self.kind = ("outfit", "haircut")[i]; self.refresh_grid()
    def item_icon(self, it):
        p = self.cat.icon(it); pm = QPixmap(p) if p and os.path.exists(p) else QPixmap(150, 150)
        if not (p and os.path.exists(p)): pm.fill(QColor(60, 60, 60))
        pm = pm.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if self.proj.edited(it):
            painter = QPainter(pm); painter.setBrush(EDIT_BADGE); painter.setPen(Qt.NoPen); painter.drawEllipse(pm.width() - 30, 6, 24, 24)
            painter.setPen(Qt.black); fnt = QFont(); fnt.setBold(True); painter.setFont(fnt); painter.drawText(pm.width() - 30, 6, 24, 24, Qt.AlignCenter, "✎"); painter.end()
        return QIcon(pm)
    def refresh_grid(self):
        keep = self.item["id"] if self.item else None
        self.grid.blockSignals(True); self.grid.clear(); sel = None
        for it in self.cat.items_for(self.char, self.kind):
            w = QListWidgetItem(self.item_icon(it), it["name"] + (" (default)" if it.get("default") else ""))
            w.setData(Qt.UserRole, it); w.setToolTip(it["class"]); self.grid.addItem(w)
            if it["id"] == keep: sel = w
        self.grid.blockSignals(False)
        self.grid.setCurrentItem(sel or self.grid.item(0)); self.update_status()
    def on_item(self, cur, prev=None):
        self.item = cur.data(Qt.UserRole) if cur else None; self.refresh_detail()
    def refresh_badge(self):
        w = self.grid.currentItem()
        if w: w.setIcon(self.item_icon(self.item))
    # ---------------- detail
    def refresh_detail(self):
        it = self.item
        for wdg in [self.use_set, self.copy_from, self.reset] + [x for t in self.slot_w.values() for x in t[1:]]: wdg.setEnabled(bool(it))
        if not it: return
        p = self.cat.icon(it); pm = QPixmap(p) if p and os.path.exists(p) else QPixmap()
        self.pic.setPixmap(pm.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation) if not pm.isNull() else QPixmap())
        self.title.setText("%s — %s" % (it["character"], it["name"]))
        self.sub.setText("%s   |   %s" % (it["kind"].title(), it["class"].rsplit("/", 1)[1]))
        cur, mine = self.cat.current(it), self.proj.get(it)
        is_base = it["kind"] == "outfit" and it.get("default")
        self.apply_all.setVisible(bool(is_base)); self.apply_all.blockSignals(True)
        self.apply_all.setChecked(bool(mine.get("_all"))); self.apply_all.setEnabled(bool([k for k in mine if not k.startswith("_")]))
        self.apply_all.blockSignals(False)
        cps = model.copies(mine, cur)
        for s in SLOTS:
            val, ch, kp = self.slot_w[s]
            if s == "sprint_start" and s not in mine and "sprint" in mine:
                txt = "<span style='color:gray'>none (cleared with the new sprint)</span>"
            elif s in mine:
                note = self.cat.bugged(mine[s]); a = self.cat.anim_by_path.get(mine[s], {})
                txt = "<span style='color:#e6aa3c'>%s</span> <span style='color:gray'>(%s)</span>" % (short(mine[s]), a.get("owner", "?"))
                if note: txt += " <span style='color:#dc5a46'>⚠ %s</span>" % note
            else:
                txt = "<span style='color:gray'>keep: %s</span>" % short(cur.get(s)) if self.kind == "outfit" else "<span style='color:gray'>keep (outfit decides)</span>"
            if s in cps: txt += " <span style='color:#6fa8dc'>⧉ copy of %s</span>" % cps[s]
            val.setText(txt); kp.setEnabled(s in mine)
        notes = []
        if self.kind == "haircut":
            notes.append("Haircut slots apply unless the worn outfit changes the same group (idle / walk+run / sprint) in this build. "
                         "Vanilla Esquie and Osquio outfits always keep theirs.")
        if ("walk" in mine) != ("run" in mine) and ("walk" in mine or "run" in mine):
            notes.append("Only one of walk / run is set: the other stays the character's own.")
        for h, o, grp in model.conflicts(self.cat, self.proj, it["character"]):
            if it["name"] in (h, o): notes.append("Overlap: outfit %s wins over haircut %s for %s." % (o, h, ", ".join(grp)))
        self.notes.setText("\n".join(notes))
    def choose(self, slot):
        cur = self.proj.get(self.item).get(slot) or self.cat.current(self.item).get(slot)
        d = AnimPicker(self.cat, slot, cur, self)
        if d.exec() == QDialog.Accepted and d.choice:
            self.proj.set_slot(self.item, slot, d.choice)
            hs = self.cat.hero_starts.get(d.choice) if slot == "sprint" else None
            if hs and self.proj.get(self.item).get("sprint_start") != hs[1]:
                if QMessageBox.question(self, "Sprint start", "%s's sprint has its own sprint start (%s). Use it too?" % (hs[0], short(hs[1]))) == QMessageBox.Yes:
                    self.proj.set_slot(self.item, "sprint_start", hs[1])
            self.changed()
    def on_apply_all(self, on):
        if self.item and self.proj.set_option(self.item, "_all", bool(on)): self.changed()
    def keep(self, slot): self.proj.set_slot(self.item, slot, None); self.changed()
    def reset_item(self): self.proj.clear(self.item); self.changed()
    def apply_set(self):
        d = SetPicker(self.cat, self)
        if d.exec() == QDialog.Accepted and d.choice:
            s = d.choice
            for k in ("idle", "walk", "run"):
                if s.get(k): self.proj.set_slot(self.item, k, s[k])
            if s.get("_sprint") and s.get("run"): self.proj.set_slot(self.item, "sprint", s["run"])
            self.changed()
    def copy_item(self):
        names = [x for x in self.cat.items if self.proj.edited(x) and x is not self.item]
        if not names: QMessageBox.information(self, "Copy from item", "No other edited items yet."); return
        labels = ["%s — %s (%s)" % (x["character"], x["name"], x["kind"]) for x in names]
        pick, ok = QInputDialog.getItem(self, "Copy from item", "Copy every assigned slot from:", labels, 0, False)
        if ok:
            src = names[labels.index(pick)]
            for s, p in self.proj.get(src).items():
                if not s.startswith("_"): self.proj.set_slot(self.item, s, p)
            self.changed()
    def changed(self): self.refresh_detail(); self.refresh_badge(); self.update_status()
    def update_status(self):
        self.status.showMessage("%d edited items%s%s" % (self.proj.count(), ("   |   " + os.path.basename(self.proj.path)) if self.proj.path else "", "  *" if self.proj.dirty else ""))
    # ---------------- files
    def confirm_discard(self):
        if not self.proj.dirty: return True
        r = QMessageBox.question(self, "Unsaved changes", "Save the current project first?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save: return self.save()
        return r == QMessageBox.Discard
    def new(self):
        if self.confirm_discard(): self.proj = model.Project(); self.refresh_grid()
    def open(self):
        if not self.confirm_discard(): return
        p, _ = QFileDialog.getOpenFileName(self, "Open project", self._proj_dir(), "Cosplay Studio project (*.json)")
        if p: self.proj = model.Project(); self.proj.load(p); self.refresh_grid()
    def save(self):
        if not self.proj.path: return self.save_as()
        self.proj.save(self.proj.path); self.update_status(); return True
    def save_as(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save project", self._proj_dir(), "Cosplay Studio project (*.json)")
        if not p: return False
        self.proj.save(p); self.update_status(); return True
    def settings(self):
        d = Settings(self.cfg, self)
        if d.exec() == QDialog.Accepted: self.cfg = d.result_cfg(); json.dump(self.cfg, open(CONFIG, "w"), indent=1)
    def build(self):
        if not self.proj.count(): QMessageBox.information(self, "Build", "Nothing assigned yet."); return
        BuildDialog(self.cfg, self.proj.assignments(), self).exec()
    def closeEvent(self, e):
        e.accept() if self.confirm_discard() else e.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    if os.path.exists(paths.data("app.png")): app.setWindowIcon(QIcon(paths.data("app.png")))
    pal = app.palette()
    for role, col in (("Window", (37, 37, 40)), ("Base", (28, 28, 30)), ("AlternateBase", (45, 45, 48)), ("Button", (50, 50, 54)),
                      ("Text", (230, 230, 230)), ("WindowText", (230, 230, 230)), ("ButtonText", (230, 230, 230)), ("Highlight", (200, 140, 50)),
                      ("HighlightedText", (0, 0, 0)), ("ToolTipBase", (50, 50, 54)), ("ToolTipText", (230, 230, 230))):
        pal.setColor(getattr(pal.ColorRole, role), QColor(*col))
    app.setPalette(pal)
    w = Main(); w.show(); sys.exit(app.exec())
