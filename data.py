from dataclasses import dataclass, field
from typing import List, Optional, Union
from enum import Enum, auto


@dataclass
class DefinitionBase:
    name: str  # Name of the symbol (type, enum, typedef, etc.)
    source: str  # Source ID from the CastXML document


@dataclass
class Field:
    name: str  # Name of the field
    c_type: str  # C/C++ type of the field
    elements: List[int]  # Array dimensions (empty if scalar)
    bitoffset: int  # Bit offset from the start of the struct/union
    size_in_bits: int = 0  # Size of the field in bits
    bitfield: bool = False  # True if the field is a bitfield


@dataclass
class ClassDefinition(DefinitionBase):
    alignment: int = 0  # Alignment requirement in bytes
    fields: List[Field] = field(default_factory=list)  # Fields in the struct/class
    size: int = 0  # Total size in bytes


@dataclass
class EnumName:
    name: str  # Name of the enumerator
    value: int  # Value assigned to the enumerator


@dataclass
class EnumDefinition(DefinitionBase):
    size: int = 0  # Size of the enum type in bytes
    enums: List[EnumName] = field(default_factory=list)  # Enumerators in the enum


@dataclass
class UnionDefinition(DefinitionBase):
    alignment: int = 0  # Alignment requirement in bytes
    fields: List[Field] = field(default_factory=list)  # Fields in the union
    size: int = 0  # Total size in bytes


@dataclass
class TypedefDefinition(DefinitionBase):
    definition: str = ""  # Actual type the typedef refers to
    elements: List[int] = field(
        default_factory=list
    )  # Array dimensions (empty if scalar)


@dataclass
class ConstantDefinition(DefinitionBase):
    c_type: str  # C/C++ type of the constant
    value: Union[int, float, str]  # Value of the constant
