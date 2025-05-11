import pytest
from dataclasses import dataclass
from typing import List

from data_helpers import filter_by_source_regexes  # update as needed


@dataclass
class DefinitionBase:
    name: str
    source: str


@pytest.fixture
def sample_definitions() -> List[DefinitionBase]:
    return [
        DefinitionBase("A", "/usr/include/stdio.h"),
        DefinitionBase("B", "/home/user/project/foo.h"),
        DefinitionBase("C", "C:\\Program Files\\Microsoft SDKs\\bar.h"),
        DefinitionBase("D", "/usr/local/include/something.h"),
        DefinitionBase("E", "D:\\MyLib\\custom\\baz.h"),
    ]


def test_include_regex(sample_definitions):
    # Include only user/project headers
    result = filter_by_source_regexes(sample_definitions, include=r"/home/user/")
    assert len(result) == 1
    assert result[0].name == "B"


def test_exclude_regex(sample_definitions):
    # Exclude system headers (Linux-style)
    result = filter_by_source_regexes(sample_definitions, exclude=r"^/usr/include/")
    assert all(d.name != "A" for d in result)


def test_include_and_exclude(sample_definitions):
    # Include all .h files, but exclude ones from Windows SDKs
    result = filter_by_source_regexes(
        sample_definitions,
        include=r"\.h$",
        exclude=r"Program Files|Microsoft"
    )
    assert all("Microsoft" not in d.source for d in result)
    assert "C" not in [d.name for d in result]


def test_no_filters(sample_definitions):
    # No filtering: return all
    result = filter_by_source_regexes(sample_definitions)
    assert len(result) == len(sample_definitions)


def test_include_as_list(sample_definitions):
    # List of includes: both user and system headers
    result = filter_by_source_regexes(sample_definitions, include=[r"/usr/", r"/home/user/"])
    names = [d.name for d in result]
    assert "A" in names and "B" in names
