"""
Parser Package

Binary data parsers for various formats.
"""

from .basic import BasicParser
from .template import TemplateParser, StructureTemplate
from .auto import AutoParser
from .c_struct import CStructDefinition, CStructField, decode_c_struct, parse_c_struct_definition

__all__ = [
    "BasicParser",
    "TemplateParser",
    "StructureTemplate",
    "AutoParser",
    "CStructDefinition",
    "CStructField",
    "decode_c_struct",
    "parse_c_struct_definition",
]
