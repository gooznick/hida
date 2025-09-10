# cli_gui_qt.py
from __future__ import annotations

import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr

from PyQt6 import QtCore, QtGui, QtWidgets as QW

# Import your CLI entry
from hida.cli import main as hida_main


def split_ws_csv(s: str) -> list[str]:
    s = (s or "").strip()
    if not s:
        return []
    out = []
    for tok in s.replace(",", " ").split():
        if tok:
            out.append(tok)
    return out


class Runner(QtCore.QThread):
    finishedWithOutput = QtCore.pyqtSignal(int, str, str)  # rc, stdout, stderr

    def __init__(self, argv: list[str], parent=None):
        super().__init__(parent)
        self.argv = argv

    def run(self):
        buf_out, buf_err = io.StringIO(), io.StringIO()
        rc = 1
        try:
            with redirect_stdout(buf_out), redirect_stderr(buf_err):
                rc = hida_main(self.argv)
        except SystemExit as e:
            rc = int(e.code) if isinstance(e.code, int) else 1
        except Exception:
            # capture full traceback into stderr buffer
            buf_err.write(traceback.format_exc())
        finally:
            out_txt = buf_out.getvalue()
            err_txt = buf_err.getvalue()
            self.finishedWithOutput.emit(rc, out_txt, err_txt)


class LabeledLine:
    """Tiny helper for a label + line edit + optional browse button."""
    def __init__(self, text: str, parent_layout: QW.QGridLayout, row: int,
                 browse_kind: str | None = None, placeholder: str | None = None,
                 colspan: int = 1):
        self.label = QW.QLabel(text)
        self.edit = QW.QLineEdit()
        if placeholder:
            self.edit.setPlaceholderText(placeholder)
        parent_layout.addWidget(self.label, row, 0)
        parent_layout.addWidget(self.edit, row, 1, 1, colspan)
        self.button = None
        if browse_kind:
            self.button = QW.QPushButton("…")
            parent_layout.addWidget(self.button, row, 1 + colspan)
            if browse_kind == "open_file":
                self.button.clicked.connect(self._choose_file)
            elif browse_kind == "save_file":
                self.button.clicked.connect(self._save_file)
            elif browse_kind == "open_dir":
                self.button.clicked.connect(self._choose_dir)

    def _choose_file(self):
        path, _ = QW.QFileDialog.getOpenFileName(None, "Select file")
        if path:
            self.edit.setText(path)

    def _save_file(self):
        path, _ = QW.QFileDialog.getSaveFileName(None, "Save as")
        if path:
            self.edit.setText(path)

    def _choose_dir(self):
        path = QW.QFileDialog.getExistingDirectory(None, "Select directory")
        if path:
            self.edit.setText(path)

    def text(self) -> str:
        return self.edit.text().strip()


class MainWindow(QW.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("hida – GUI (PyQt6)")
        self.resize(1100, 820)

        cw = QW.QWidget()
        self.setCentralWidget(cw)
        v = QW.QVBoxLayout(cw)

        mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)

        # ───────────────── Tabs ─────────────────
        tabs = QW.QTabWidget()
        v.addWidget(tabs, 2)

        # ===== Tab 1: I/O + Outputs =====
        tab_main = QW.QWidget()
        tabs.addTab(tab_main, "Main")
        main_v = QW.QVBoxLayout(tab_main)

        # I/O
        io_box = QW.QGroupBox("I/O")
        main_v.addWidget(io_box)
        io_grid = QW.QGridLayout(io_box)

        self.inp = LabeledLine("Input (XML / JSON / Header):", io_grid, 0, "open_file")
        self.inc = LabeledLine("Include dirs (-I, space/comma):", io_grid, 1)
        self.castxml = LabeledLine("CastXML path:", io_grid, 2, "open_file")
        self.std = LabeledLine("C++ standard (--std):", io_grid, 3, None, placeholder="c++17")
        self.std.edit.setText("c++17")

        # Outputs
        out_box = QW.QGroupBox("Outputs")
        main_v.addWidget(out_box)
        out_grid = QW.QGridLayout(out_box)

        self.py_out = LabeledLine("Python out:", out_grid, 0, "save_file")
        self.assert_size = QW.QCheckBox("Assert size")
        self.py_verify = QW.QCheckBox("Verify Python")
        self.py_verify_size = QW.QCheckBox("Verify size")

        out_grid.addWidget(self.assert_size, 1, 0)
        out_grid.addWidget(self.py_verify, 1, 1)
        out_grid.addWidget(self.py_verify_size, 1, 2)

        self.hdr_out = LabeledLine("C++ header out:", out_grid, 2, "save_file")
        self.xml_out = LabeledLine("XML out (-x):", out_grid, 3, "save_file")
        self.json_out = LabeledLine("JSON IR out:", out_grid, 4, "save_file")

        main_v.addStretch(1)

        # ===== Tab 2: Parsing & Manipulators =====
        tab_manip = QW.QWidget()
        tabs.addTab(tab_manip, "Parsing & Manipulators")
        manip_v = QW.QVBoxLayout(tab_manip)

        pm_box = QW.QGroupBox("Parsing & Manipulators")
        manip_v.addWidget(pm_box)
        pm_grid = QW.QGridLayout(pm_box)

        # Row 0 flags (DASH-CASE)
        self.use_bool = QW.QCheckBox("Use bool")
        self.no_ignore_sys = QW.QCheckBox("Do not ignore system")
        self.verbose = QW.QCheckBox("Verbose")
        self.no_skip_failed = QW.QCheckBox("Do NOT skip failed parsing")
        pm_grid.addWidget(self.use_bool, 0, 0)
        pm_grid.addWidget(self.no_ignore_sys, 0, 1)
        pm_grid.addWidget(self.verbose, 0, 2)
        pm_grid.addWidget(self.no_skip_failed, 0, 3)

        # Regex filters
        self.name_inc = LabeledLine("Name include regexes:", pm_grid, 1)
        self.name_exc = LabeledLine("Name exclude regexes:", pm_grid, 2)
        self.src_inc = LabeledLine("Source include regexes:", pm_grid, 3)
        self.src_exc = LabeledLine("Source exclude regexes:", pm_grid, 4)

        # Typedefs/namespaces
        self.resolve_typedefs = QW.QCheckBox("Resolve typedefs")
        self.flatten_ns = QW.QCheckBox("Flatten namespaces")
        pm_grid.addWidget(self.resolve_typedefs, 5, 0)
        pm_grid.addWidget(self.flatten_ns, 5, 1)

        # Enums
        self.remove_enums = QW.QCheckBox("Remove enums")
        pm_grid.addWidget(self.remove_enums, 6, 0)
        self.enum_int_type = QW.QLineEdit("int32_t")
        pm_grid.addWidget(QW.QLabel("Enum int type:"), 6, 1)
        pm_grid.addWidget(self.enum_int_type, 6, 2)

        # Flatten
        self.flatten_structs = LabeledLine("Flatten structs (names):", pm_grid, 7)
        self.flatten_sep = LabeledLine("Flatten separator:", pm_grid, 8, None, placeholder="__")
        self.flatten_sep.edit.setText("__")
        self.flatten_arrays = QW.QCheckBox("Flatten arrays of composites")
        pm_grid.addWidget(self.flatten_arrays, 8, 2)

        # Focus
        self.focus = LabeledLine("Focus root names:", pm_grid, 9)

        # Padding & scrubbing
        self.pad_bit = QW.QCheckBox("Pad bitfield holes")
        self.pad_struct = QW.QCheckBox("Pad struct holes")
        self.fail_if_hole = QW.QCheckBox("Fail if hole")
        self.pad_bit.setChecked(True)
        self.pad_struct.setChecked(True)
        
        pm_grid.addWidget(self.pad_bit, 10, 0)
        pm_grid.addWidget(self.pad_struct, 10, 1)
        pm_grid.addWidget(self.fail_if_hole, 10, 2)

        self.rm_source = QW.QCheckBox("Remove source paths")
        self.rm_source_base = QW.QCheckBox("Keep only source basenames")
        pm_grid.addWidget(self.rm_source, 11, 0)
        pm_grid.addWidget(self.rm_source_base, 11, 1)

        manip_v.addStretch(1)

        # ───────────── Command + Run ─────────────
        bottom = QW.QHBoxLayout()
        v.addLayout(bottom)

        self.cmd_preview = QW.QPlainTextEdit()
        self.cmd_preview.setReadOnly(True)
        self.cmd_preview.setFont(mono)
        self.cmd_preview.setLineWrapMode(QW.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.cmd_preview.setMinimumHeight(70)  # multiline
        self.cmd_preview.setStyleSheet("color: green;")
        bottom.addWidget(self.cmd_preview, 1)

        self.btn_run = QW.QPushButton("Run")
        self.btn_run.setMinimumHeight(40)
        bottom.addWidget(self.btn_run, 0)

        # ───────────── Log (QTextEdit so we can color) ─────────────
        self.log = QW.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(mono)
        self.log.setMinimumHeight(360)  # bigger output box
        v.addWidget(self.log, 3)

        # Signals
        for w in self._all_inputs():
            if isinstance(w, QW.QLineEdit):
                w.textChanged.connect(self.refresh_cmd)
            elif isinstance(w, QW.QCheckBox):
                w.toggled.connect(self.refresh_cmd)
        self.btn_run.clicked.connect(self.on_run)

        self.refresh_cmd()

    # Collect all interactive inputs for live preview
    def _all_inputs(self):
        return [
            self.inp.edit, self.inc.edit, self.xml_out.edit, self.castxml.edit, self.std.edit,
            self.use_bool, self.no_ignore_sys, self.verbose, self.no_skip_failed,
            self.name_inc.edit, self.name_exc.edit, self.src_inc.edit, self.src_exc.edit,
            self.resolve_typedefs, self.flatten_ns, self.remove_enums, self.enum_int_type,
            self.flatten_structs.edit, self.flatten_sep.edit, self.flatten_arrays,
            self.focus.edit, self.pad_bit, self.pad_struct, self.fail_if_hole,
            self.rm_source, self.rm_source_base, self.py_out.edit, self.assert_size,
            self.py_verify, self.py_verify_size, self.hdr_out.edit, 
            self.json_out.edit
        ]

    def build_argv(self) -> list[str]:
        argv: list[str] = []
        inp = self.inp.text()
        if not inp:
            return []
        argv.append(inp)

        for inc in split_ws_csv(self.inc.text()):
            argv += ["-I", inc]


        if self.castxml.text():
            argv += ["--castxml", self.castxml.text()]
        if self.std.text():
            argv += ["--std", self.std.text()]

        # DASH-CASE FLAGS HERE
        if self.use_bool.isChecked():
            argv += ["--use-bool"]
        if self.no_ignore_sys.isChecked():
            argv += ["--do-not-ignore-system"]
        if self.verbose.isChecked():
            argv += ["--verbose"]
        if self.no_skip_failed.isChecked():
            argv += ["--do-not-skip-failed-parsing"]

        for r in split_ws_csv(self.name_inc.text()):
            argv += ["--name-include", r]
        for r in split_ws_csv(self.name_exc.text()):
            argv += ["--name-exclude", r]
        for r in split_ws_csv(self.src_inc.text()):
            argv += ["--source-include", r]
        for r in split_ws_csv(self.src_exc.text()):
            argv += ["--source-exclude", r]

        if self.resolve_typedefs.isChecked():
            argv += ["--resolve-typedefs"]
        if self.flatten_ns.isChecked():
            argv += ["--flatten-namespaces"]

        if self.remove_enums.isChecked():
            argv += ["--remove-enums"]
        if self.enum_int_type.text():
            argv += ["--enum-int-type", self.enum_int_type.text()]

        fl = split_ws_csv(self.flatten_structs.text())
        if fl:
            argv += ["--flatten-structs"] + fl
        if self.flatten_sep.text():
            argv += ["--flatten-sep", self.flatten_sep.text()]
        if self.flatten_arrays.isChecked():
            argv += ["--flatten-arrays"]

        foc = split_ws_csv(self.focus.text())
        if foc:
            argv += ["--focus"] + foc


        if self.pad_bit.isChecked():
            argv += ["--pad-bitfield-holes"]
        if self.pad_struct.isChecked():
            argv += ["--pad-struct-holes"]
        if self.fail_if_hole.isChecked():
            argv += ["--fail-if-hole"]

        if self.rm_source.isChecked():
            argv += ["--remove-source"]
        elif self.rm_source_base.isChecked():
            argv += ["--remove-source-basename"]

        # Outputs
        any_out = False
        if self.xml_out.text():
            any_out = True
            argv += ["-x", self.xml_out.text()]
        if self.py_out.text():
            any_out = True
            argv += ["--python", self.py_out.text()]
            if self.assert_size.isChecked():
                argv += ["--assert-size"]
            if self.py_verify.isChecked():
                argv += ["--python-verify"]
            if self.py_verify_size.isChecked():
                argv += ["--python-verify-size"]

        if self.hdr_out.text():
            any_out = True
            argv += ["--header", self.hdr_out.text()]
        if self.json_out.text():
            any_out = True
            argv += ["--json", self.json_out.text()]

        return argv if any_out else []

    def refresh_cmd(self):
        argv = self.build_argv()
        if argv:
            parts = [f"\"{a}\"" if (" " in a and not a.startswith("--")) else a for a in argv]
            txt = "hida " + " ".join(parts)
            self.cmd_preview.setPlainText(txt)
            self.cmd_preview.setStyleSheet("color: green;")
        else:
            self.cmd_preview.setPlainText("hida …")
            self.cmd_preview.setStyleSheet("color: blue;")

    def _append_stdout(self, text: str):
        if not text:
            return
        self.log.setTextColor(QtGui.QColor("black"))
        # preserve spacing
        self.log.append(text.rstrip("\n"))

    def _append_stderr(self, text: str):
        if not text:
            return
        self.log.setTextColor(QtGui.QColor("red"))
        self.log.append(text.rstrip("\n"))
        self.log.setTextColor(QtGui.QColor("black"))

    def on_run(self):
        argv = self.build_argv()
        if not argv:
            QW.QMessageBox.critical(self, "hida", "Pick an input and at least one output (Python/Header/XML/JSON).")
            return

        parts = [f"\"{a}\"" if (" " in a and not a.startswith("--")) else a for a in argv]
        self.cmd_preview.setPlainText("hida " + " ".join(parts))
        self.cmd_preview.setStyleSheet("color: green;")
        self.log.clear()
        self.btn_run.setEnabled(False)
        self.setCursor(QtCore.Qt.CursorShape.BusyCursor)

        self.runner = Runner(argv, self)
        self.runner.finishedWithOutput.connect(self.on_finished)
        self.runner.start()

    @QtCore.pyqtSlot(int, str, str)
    def on_finished(self, rc: int, out_txt: str, err_txt: str):
        # Always show stdout (black)
        self._append_stdout(out_txt)
        # Show stderr/exceptions in red
        self._append_stderr(err_txt)

        self.btn_run.setEnabled(True)
        self.unsetCursor()
        if rc == 0:
            QW.QMessageBox.information(self, "hida", "Done.")
        else:
            QW.QMessageBox.critical(self, "hida", f"Exited with code {rc}.")


def main():
    app = QW.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
