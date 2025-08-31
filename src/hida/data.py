from dataclasses import dataclass, field
from typing import Tuple, Optional, Union
from enum import Enum, auto


@dataclass(frozen=True)
class TypeBase:
    name: str  # Name of the symbol (type, enum, typedef, etc.)
    namespace: Tuple[str] = field(
        default_factory=tuple
    )  # nested namespaces (tuple if none)

    @property
    def fullname(self) -> str:
        return (
            "::".join(list(self.namespace) + [self.name])
            if self.namespace
            else self.name
        )


@dataclass(frozen=True)
class DefinitionBase(TypeBase):
    source: str = ""  # Source ID from the CastXML document


@dataclass(frozen=True)
class Field:
    name: str  # Name of the field
    type: TypeBase  # C/C++ type of the field
    elements: Tuple[int]  # Array dimensions (empty if scalar)
    bitoffset: int  # Bit offset from the start of the struct/union
    size_in_bits: int = 0  # Size of the field in bits
    bitfield: bool = False  # True if the field is a bitfield


@dataclass(frozen=True)
class ClassDefinition(DefinitionBase):
    alignment: int = 0  # Alignment requirement in bytes
    fields: Tuple[Field] = field(default_factory=tuple)  # Fields in the struct/class
    size: int = 0  # Total size in bytes


@dataclass(frozen=True)
class EnumName:
    name: str  # Name of the enumerator
    value: int  # Value assigned to the enumerator


@dataclass(frozen=True)
class EnumDefinition(DefinitionBase):
    size: int = 0  # Size of the enum type in bytes
    enums: Tuple[EnumName] = field(default_factory=tuple)  # Enumerators in the enum


@dataclass(frozen=True)
class UnionDefinition(DefinitionBase):
    alignment: int = 0  # Alignment requirement in bytes
    fields: Tuple[Field] = field(default_factory=tuple)  # Fields in the union
    size: int = 0  # Total size in bytes


@dataclass(frozen=True)
class TypedefDefinition(DefinitionBase):
    type: TypeBase = field(
        default_factory=TypeBase
    )  # Actual type the typedef refers to
    elements: Tuple[int] = field(
        default_factory=tuple
    )  # Array dimensions (empty if scalar)


@dataclass(frozen=True)
class ConstantDefinition(DefinitionBase):
    type: TypeBase = field(default_factory=TypeBase)  # C/C++ type of the constant
    value: Union[int, float, str] = ""  # Value of the constant
