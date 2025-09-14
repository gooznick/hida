# HIDA

<img src="src/hida/img/hida.jpeg" alt="HIDA Logo" style="width: 40%; min-width: 200px;" />

**HIDA** (Header-based Interface Data Adapter) is a helper utility for extracting structured metadata from **C/C++ headers** using [CastXML](https://github.com/CastXML/CastXML).  


It can generate **Python dataclasses, C headers, JSON, and more** — making it easy to bridge between low-level code and higher-level tools.


---

## ✨ Features

- Parse C/C++ headers via CastXML
- Convert to multiple formats:
  - **Python** (dataclasses, validation helpers)
  - **C/C++ headers** (rewritten / flattened)
  - **JSON IR** intermediate form
- Manipulators and filters:
  - Flatten structs, typedefs, namespaces
  - Remove sources or enums
  - Regex include/exclude filters
  - Fill / assert struct/bitfield holes
- Optional **GUI (PyQt6)** with live command preview
- Bundled **CastXML binary for Windows**
- Scriptable CLI

---

## 📦 Installation

### Core (CLI only)
```bash
pip install hida
````

### With GUI (requires PyQt6)

```bash
pip install "hida[gui]"
```

### From source

```bash
git clone https://github.com/hida.git
cd hida
pip install -e .           # CLI only
pip install -e '.[gui]'    # with GUI
```

---

## 🚀 Usage

### CLI

Basic command:

```bash
hida input.h --python out.py --header out.h --json out.json
```

Show help:

```bash
hida --help
```

Show version:

```bash
hida --version
```

Run CastXML forwarding:

```bash
hida input.h -I include/dir --std c++17
```

### GUI

If you installed with `hida[gui]`:

```bash
hida-gui
```

The GUI provides tabs for:

* Input / output configuration
* Parsing & manipulation options
* Live command preview
* Run + output log
* **About/Version** tab with diagnostics and CastXML detection

---

## ⚙️ CastXML Integration

* **Windows**: HIDA bundles `castxml.exe` and will use it automatically.
* **Linux**: Install CastXML (Ubuntu/Debian): `sudo apt install castxml`


You can override the binary with:

```bash
hida input.h --castxml /path/to/castxml
```

## 🛠️ Development

### Build wheel & sdist

```bash
python -m build
```

### Run tests

```bash
pytest
```

### Build single-file executables

(Requires PyInstaller)

* CLI:

  ```bash
  pyinstaller --clean -y hida_cli.spec
  ```
* GUI:

  ```bash
  pyinstaller --clean -y hida_gui.spec
  ```

## 🤖 About This Codebase

Most of **HIDA** was written in close collaboration with **ChatGPT-5**.  
The design, CLI, PyQt6 GUI, CastXML integration, packaging, and even much of the documentation were drafted iteratively with the help of the model, and then refined, tested, and structured by the maintainer.

The maintainer continues to review, test, and evolve the codebase — but the bulk of the initial implementation is a showcase of what can be achieved with ChatGPT-5 as a coding partner.
