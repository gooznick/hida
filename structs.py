from dataclasses import dataclass, field
from typing import List, Optional, Union
from enum import Enum, auto


class NumericType(Enum):
    BOOL = auto()
    FLOAT = auto()
    SIGNED = auto()
    UNSIGNED = auto()
    POINTER = auto()


@dataclass
class CTypeInfo:
    numeric_type: Union[NumericType, None]
    bits: int


@dataclass
class Field:
    name: str  # Name of the field
    # type of the field
    type: Union[str, CTypeInfo]
    elements: List[int]  # Number of elements (for arrays)
    bitoffset: int  # offset [bits] from the beginning of the struct
    size_in_bits: int = 0  # size [bits] of the field
    bitfield: bool = False  # true if bitfield


@dataclass
class ClassDefinition:
    name: str = ""  # Name of the class
    alignment: int = 0  # Alignment value of the class
    # List of Field dataclasses
    fields: List[Field] = field(default_factory=list)
    size: int = 0  # total byte size of the class/struct


@dataclass
class EnumName:
    name: str
    value: int


@dataclass
class EnumDefinition:
    name: str = ""
    size: int = 0
    enums: List[EnumName] = field(default_factory=list)


@dataclass
class UnionDefinition:
    name: str = ""
    alignment: int = 0  # Alignment value of the union
    fields: List[Field] = field(default_factory=list)
    size: int = 0


@dataclass
class TypedefDefinition:
    name: str = ""  # Name of the class
    definition: str = ""  # Defined  class
