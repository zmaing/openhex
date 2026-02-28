"""
Template Parser

Binary format templates for common file formats.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum, auto

import json
import os

from .basic import BasicParser, ParsedField, Endianness


class Architecture(Enum):
    """Binary architecture."""
    X86 = auto()
    X64 = auto()
    ARM = auto()
    ARM64 = auto()
    UNKNOWN = auto()


class BinaryFormat(Enum):
    """Binary file format."""
    ELF = auto()
    PE = auto()
    MACHO = auto()
    RAW = auto()
    UNKNOWN = auto()


class StructureTemplate(QObject):
    """
    Structure template for parsing binary formats.

    Defines fields and parsing rules for specific formats.
    """

    # Signals
    template_loaded = pyqtSignal(str)
    template_error = pyqtSignal(str)

    def __init__(self, name: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._name = name
        self._description: str = ""
        self._fields: List[Dict[str, Any]] = []
        self._endianness: Endianness = Endianness.LITTLE
        self._architecture: Architecture = Architecture.UNKNOWN
        self._format: BinaryFormat = BinaryFormat.UNKNOWN
        self._metadata: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Get template name."""
        return self._name

    @property
    def description(self) -> str:
        """Get description."""
        return self._description

    @property
    def fields(self) -> List[Dict[str, Any]]:
        """Get field definitions."""
        return self._fields.copy()

    @property
    def endianness(self) -> Endianness:
        """Get default endianness."""
        return self._endianness

    @property
    def architecture(self) -> Architecture:
        """Get target architecture."""
        return self._architecture

    @property
    def binary_format(self) -> BinaryFormat:
        """Get binary format."""
        return self._format

    @property
    def field_count(self) -> int:
        """Get number of fields."""
        return len(self._fields)

    def add_field(self, name: str, type: str, offset: int = -1,
                  length: int = 0, description: str = "", **kwargs):
        """
        Add field to template.

        Args:
            name: Field name
            type: Field type (uint8, uint16, string, etc.)
            offset: Field offset (-1 = auto/increment)
            length: Field length (0 = auto)
            description: Field description
        """
        field = {
            "name": name,
            "type": type,
            "offset": offset,
            "length": length,
            "description": description,
        }
        field.update(kwargs)
        self._fields.append(field)

    def remove_field(self, name: str) -> bool:
        """Remove field by name."""
        for i, field in enumerate(self._fields):
            if field["name"] == name:
                self._fields.pop(i)
                return True
        return False

    def get_field(self, name: str) -> Optional[Dict[str, Any]]:
        """Get field by name."""
        for field in self._fields:
            if field["name"] == name:
                return field
        return None

    def from_json(self, json_data: str) -> bool:
        """
        Load template from JSON.

        Args:
            json_data: JSON string

        Returns:
            True if successful
        """
        try:
            data = json.loads(json_data)
            return self._parse_json(data)
        except json.JSONDecodeError as e:
            self.template_error.emit(f"Invalid JSON: {e}")
            return False

    def from_file(self, path: str) -> bool:
        """
        Load template from file.

        Args:
            path: File path

        Returns:
            True if successful
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if self._parse_json(data):
                self.template_loaded.emit(self._name)
                return True
        except Exception as e:
            self.template_error.emit(f"Failed to load: {e}")
        return False

    def _parse_json(self, data: Dict[str, Any]) -> bool:
        """Parse JSON data."""
        try:
            self._name = data.get("name", "Unknown")
            self._description = data.get("description", "")
            self._fields = data.get("fields", [])
            self._metadata = data.get("metadata", {})

            endian_map = {
                "little": Endianness.LITTLE,
                "big": Endianness.BIG,
            }
            self._endianness = endian_map.get(
                data.get("endianness", "little"),
                Endianness.LITTLE
            )

            arch_map = {
                "x86": Architecture.X86,
                "x64": Architecture.X64,
                "arm": Architecture.ARM,
                "arm64": Architecture.ARM64,
            }
            self._architecture = arch_map.get(
                data.get("architecture", "unknown"),
                Architecture.UNKNOWN
            )

            format_map = {
                "elf": BinaryFormat.ELF,
                "pe": BinaryFormat.PE,
                "macho": BinaryFormat.MACHO,
            }
            self._binary_format = format_map.get(
                data.get("format", "unknown"),
                BinaryFormat.UNKNOWN
            )

            return True
        except Exception as e:
            self.template_error.emit(f"Parse error: {e}")
            return False

    def to_json(self) -> str:
        """Export template to JSON."""
        data = {
            "name": self._name,
            "description": self._description,
            "fields": self._fields,
            "endianness": "little" if self._endianness == Endianness.LITTLE else "big",
            "architecture": self._architecture.name.lower(),
            "format": self._binary_format.name.lower(),
            "metadata": self._metadata,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def save_to_file(self, path: str) -> bool:
        """
        Save template to file.

        Args:
            path: File path

        Returns:
            True if successful
        """
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.to_json())
            return True
        except Exception as e:
            self.template_error.emit(f"Save failed: {e}")
            return False


class TemplateParser(QObject):
    """
    Template-based parser for binary formats.

    Parses data according to structure templates.
    """

    # Signals
    parsing_started = pyqtSignal(StructureTemplate)
    parsing_progress = pyqtSignal(int, int)  # current, total
    parsing_finished = pyqtSignal(object)  # List[ParsedField]
    parsing_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._basic_parser = BasicParser()
        self._templates: Dict[str, StructureTemplate] = {}

        # Load built-in templates
        self._load_builtin_templates()

    def _load_builtin_templates(self):
        """Load built-in templates."""
        # ELF Header template
        elf = StructureTemplate("ELF Header")
        elf._description = "ELF Executable Format Header"
        elf._binary_format = BinaryFormat.ELF
        elf._endianness = Endianness.LITTLE
        elf.add_field("e_ident", "raw", offset=0, length=16, description="ELF identification")
        elf.add_field("e_type", "uint16", offset=16, description="Object file type")
        elf.add_field("e_machine", "uint16", offset=18, description="Architecture")
        elf.add_field("e_version", "uint32", offset=20, description="Object file version")
        elf.add_field("e_entry", "uint64", offset=24, description="Entry point virtual address")
        elf.add_field("e_phoff", "uint64", offset=32, description="Program header table file offset")
        elf.add_field("e_shoff", "uint64", offset=40, description="Section header table file offset")
        elf.add_field("e_flags", "uint32", offset=48, description="Processor-specific flags")
        elf.add_field("e_ehsize", "uint16", offset=52, description="ELF header size")
        elf.add_field("e_phentsize", "uint16", offset=54, description="Program header table entry size")
        elf.add_field("e_phnum", "uint16", offset=56, description="Program header table entry count")
        elf.add_field("e_shentsize", "uint16", offset=58, description="Section header table entry size")
        elf.add_field("e_shnum", "uint16", offset=60, description="Section header table entry count")
        elf.add_field("e_shstrndx", "uint16", offset=62, description="Section header string table index")
        self._templates["elf"] = elf

        # PE Header template (simplified)
        pe = StructureTemplate("PE Header")
        pe._description = "PE (Portable Executable) Header"
        pe._binary_format = BinaryFormat.PE
        pe._endianness = Endianness.LITTLE
        pe.add_field("machine", "uint16", offset=0, description="Target machine")
        pe.add_field("number_of_sections", "uint16", offset=2, description="Number of sections")
        pe.add_field("time_date_stamp", "uint32", offset=4, description="Timestamp")
        pe.add_field("pointer_to_symbol_table", "uint32", offset=8, description="Symbol table offset")
        pe.add_field("number_of_symbols", "uint32", offset=12, description="Symbol count")
        pe.add_field("optional_header_size", "uint16", offset=16, description="Optional header size")
        pe.add_field("characteristics", "uint16", offset=18, description="Characteristics")
        self._templates["pe"] = pe

    @property
    def templates(self) -> Dict[str, StructureTemplate]:
        """Get all templates."""
        return self._templates.copy()

    def get_template(self, name: str) -> Optional[StructureTemplate]:
        """Get template by name."""
        return self._templates.get(name)

    def add_template(self, template: StructureTemplate):
        """Add custom template."""
        self._templates[template.name] = template

    def remove_template(self, name: str) -> bool:
        """Remove template by name."""
        if name in self._templates:
            del self._templates[name]
            return True
        return False

    def parse(self, data: bytes, template: StructureTemplate) -> List[ParsedField]:
        """
        Parse data using template.

        Args:
            data: Binary data
            template: Structure template

        Returns:
            List of parsed fields
        """
        self.parsing_started.emit(template)

        fields = []
        offset = 0

        for field_def in template.fields:
            field_name = field_def.get("name", f"field_{len(fields)}")
            field_type = field_def.get("type", "byte")
            field_offset = field_def.get("offset", -1)
            field_length = field_def.get("length", 0)

            if field_offset >= 0:
                offset = field_offset

            if offset >= len(data):
                break

            parsed = self._basic_parser._parse_field(data, offset, field_type, field_length)
            if parsed:
                parsed.name = field_name
                fields.append(parsed)
                offset += parsed.length

        self.parsing_finished.emit(fields)
        return fields

    def parse_with(self, data: bytes, template_name: str) -> List[ParsedField]:
        """
        Parse data using named template.

        Args:
            data: Binary data
            template_name: Template name

        Returns:
            List of parsed fields
        """
        template = self._templates.get(template_name)
        if not template:
            self.parsing_error.emit(f"Template not found: {template_name}")
            return []
        return self.parse(data, template)
