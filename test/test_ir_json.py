import sys
import os

here = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(here, os.pardir))

from hida import parse, dumps, loads


def test_ir_json(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "complicated.xml"),
        use_bool=True,
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    ir = dumps(result)
    result2 = loads(ir)
    assert result == result2
