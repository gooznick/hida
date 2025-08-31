# src/hida/ir_json_simple.py
from __future__ import annotations

from typing import get_origin, Tuple
import json, inspect
from dataclasses import is_dataclass, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Type
from hida import data as _data_mod  # your dataclasses live here


def _registry() -> Dict[str, Type]:
    reg: Dict[str, Type] = {}
    for name, obj in vars(_data_mod).items():
        if inspect.isclass(obj) and is_dataclass(obj):
            reg[name] = obj
    return reg


def _enc(x: Any) -> Any:
    if is_dataclass(x) and not isinstance(x, type):
        d = {"__kind__": type(x).__name__}
        for f in fields(x):
            d[f.name] = _enc(getattr(x, f.name))
        return d
    if isinstance(x, (list, tuple)):
        return [_enc(i) for i in x]
    if isinstance(x, dict):
        return {str(k): _enc(v) for k, v in x.items()}
    return x


def _dec(x, reg):
    if isinstance(x, dict) and "__kind__" in x:
        d = dict(x)
        kind = d.pop("__kind__")
        cls = reg.get(kind)
        if cls is None:
            raise KeyError(f"Unknown kind: {kind}")
        kwargs = {k: _dec(v, reg) for k, v in d.items()}

        # Normalize tuple-typed fields in your IR:
        for key in ("namespace", "elements", "fields", "enums"):
            if key in kwargs and isinstance(kwargs[key], list):
                kwargs[key] = tuple(kwargs[key])

        return cls(**kwargs)
    if isinstance(x, list):
        return [_dec(i, reg) for i in x]
    if isinstance(x, dict):
        return {k: _dec(v, reg) for k, v in x.items()}
    return x


def dumps(defs: Sequence[Any], *, indent: Optional[int] = 2) -> str:
    return json.dumps([_enc(d) for d in defs], indent=indent, ensure_ascii=False)


def dump(defs: Sequence[Any], path: str | Path, *, indent: Optional[int] = 2) -> None:
    Path(path).write_text(dumps(defs, indent=indent), encoding="utf-8")


def loads(text: str) -> List[Any]:
    reg = _registry()
    data = json.loads(text)
    if not isinstance(data, list):
        raise TypeError("Expected a JSON array")
    return [_dec(item, reg) for item in data]


def load(path: str | Path) -> List[Any]:
    return loads(Path(path).read_text(encoding="utf-8"))
