from __future__ import annotations
from pathlib import Path
from .cast_xml_parse import CastXmlParse


def parse(xml_path: str, **kwargs):
    """
    Helper function to parse a CastXML XML file with optional configuration parameters.
    """
    parser = CastXmlParse(**kwargs)
    return parser.parse_xml(Path(xml_path))
