"""
Template Manager

管理二进制格式模板
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Optional, Dict, Any

from .template import StructureTemplate, BinaryFormat


class TemplateManager(QObject):
    """
    Template manager.

    Manages built-in and custom structure templates.
    """

    # Signals
    template_selected = pyqtSignal(StructureTemplate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._templates: Dict[str, StructureTemplate] = {}
        self._current_template: Optional[StructureTemplate] = None
        self._load_builtin_templates()

    def _load_builtin_templates(self):
        """Load built-in templates."""
        # ELF Header
        self._templates["elf"] = self._create_elf_template()

        # PE Header
        self._templates["pe"] = self._create_pe_template()

        # Mach-O Header
        self._templates["macho"] = self._create_macho_template()

        # BMP
        self._templates["bmp"] = self._create_bmp_template()

        # WAV
        self._templates["wav"] = self._create_wav_template()

        # PNG
        self._templates["png"] = self._create_png_template()

    def _create_elf_template(self) -> StructureTemplate:
        """Create ELF header template."""
        template = StructureTemplate("ELF Header")
        template._description = "Executable and Linkable Format header"
        template._format = BinaryFormat.ELF

        template._fields = [
            {"name": "e_ident", "offset": 0, "size": 16, "type": "bytes", "desc": "ELF identification"},
            {"name": "e_type", "offset": 16, "size": 2, "type": "uint16", "desc": "Object file type"},
            {"name": "e_machine", "offset": 18, "size": 2, "type": "uint16", "desc": "Architecture"},
            {"name": "e_version", "offset": 20, "size": 4, "type": "uint32", "desc": "Object file version"},
            {"name": "e_entry", "offset": 24, "size": 4, "type": "uint32", "desc": "Entry point virtual address"},
            {"name": "e_phoff", "offset": 28, "size": 4, "type": "uint32", "desc": "Program header table file offset"},
            {"name": "e_shoff", "offset": 32, "size": 4, "type": "uint32", "desc": "Section header table file offset"},
            {"name": "e_flags", "offset": 36, "size": 4, "type": "uint32", "desc": "Processor-specific flags"},
            {"name": "e_ehsize", "offset": 40, "size": 2, "type": "uint16", "desc": "ELF header size"},
            {"name": "e_phentsize", "offset": 42, "size": 2, "type": "uint16", "desc": "Program header table entry size"},
            {"name": "e_phnum", "offset": 44, "size": 2, "type": "uint16", "desc": "Program header table entry count"},
            {"name": "e_shentsize", "offset": 46, "size": 2, "type": "uint16", "desc": "Section header table entry size"},
            {"name": "e_shnum", "offset": 48, "size": 2, "type": "uint16", "desc": "Section header table entry count"},
            {"name": "e_shstrndx", "offset": 50, "size": 2, "type": "uint16", "desc": "Section header string table index"},
        ]

        return template

    def _create_pe_template(self) -> StructureTemplate:
        """Create PE header template."""
        template = StructureTemplate("PE Header")
        template._description = "Portable Executable header"
        template._format = BinaryFormat.PE

        template._fields = [
            {"name": "Machine", "offset": 0, "size": 2, "type": "uint16", "desc": "Target machine"},
            {"name": "NumberOfSections", "offset": 2, "size": 2, "type": "uint16", "desc": "Number of sections"},
            {"name": "TimeDateStamp", "offset": 4, "size": 4, "type": "uint32", "desc": "Timestamp"},
            {"name": "PointerToSymbolTable", "offset": 8, "size": 4, "type": "uint32", "desc": "COFF symbol table offset"},
            {"name": "NumberOfSymbols", "offset": 12, "size": 4, "type": "uint32", "desc": "Number of symbols"},
            {"name": "SizeOfOptionalHeader", "offset": 16, "size": 2, "type": "uint16", "desc": "Optional header size"},
            {"name": "Characteristics", "offset": 18, "size": 2, "type": "uint16", "desc": "File characteristics"},
        ]

        return template

    def _create_macho_template(self) -> StructureTemplate:
        """Create Mach-O header template."""
        template = StructureTemplate("Mach-O Header")
        template._description = "Mach Object file header"
        template._format = BinaryFormat.MACHO

        template._fields = [
            {"name": "magic", "offset": 0, "size": 4, "type": "uint32", "desc": "Magic number"},
            {"name": "cputype", "offset": 4, "size": 4, "type": "uint32", "desc": "CPU type"},
            {"name": "cpusubtype", "offset": 8, "size": 4, "type": "uint32", "desc": "CPU subtype"},
            {"name": "filetype", "offset": 12, "size": 4, "type": "uint32", "desc": "File type"},
            {"name": "ncmds", "offset": 16, "size": 4, "type": "uint32", "desc": "Number of load commands"},
            {"name": "sizeofcmds", "offset": 20, "size": 4, "type": "uint32", "desc": "Size of load commands"},
            {"name": "flags", "offset": 24, "size": 4, "type": "uint32", "desc": "Flags"},
        ]

        return template

    def _create_bmp_template(self) -> StructureTemplate:
        """Create BMP header template."""
        template = StructureTemplate("BMP Header")
        template._description = "Bitmap file header"

        template._fields = [
            {"name": "bfType", "offset": 0, "size": 2, "type": "uint16", "desc": "Signature (BM)"},
            {"name": "bfSize", "offset": 2, "size": 4, "type": "uint32", "desc": "File size"},
            {"name": "bfReserved1", "offset": 6, "size": 2, "type": "uint16", "desc": "Reserved"},
            {"name": "bfReserved2", "offset": 8, "size": 2, "type": "uint16", "desc": "Reserved"},
            {"name": "bfOffBits", "offset": 10, "size": 4, "type": "uint32", "desc": "Pixel data offset"},
            {"name": "biSize", "offset": 14, "size": 4, "type": "uint32", "desc": "Header size"},
            {"name": "biWidth", "offset": 18, "size": 4, "type": "int32", "desc": "Width"},
            {"name": "biHeight", "offset": 22, "size": 4, "type": "int32", "desc": "Height"},
            {"name": "biPlanes", "offset": 26, "size": 2, "type": "uint16", "desc": "Color planes"},
            {"name": "biBitCount", "offset": 28, "size": 2, "type": "uint16", "desc": "Bits per pixel"},
        ]

        return template

    def _create_wav_template(self) -> StructureTemplate:
        """Create WAV header template."""
        template = StructureTemplate("WAV Header")
        template._description = "Wave audio file header"

        template._fields = [
            {"name": "RIFF", "offset": 0, "size": 4, "type": "bytes", "desc": "RIFF signature"},
            {"name": "FileSize", "offset": 4, "size": 4, "type": "uint32", "desc": "File size - 8"},
            {"name": "WAVE", "offset": 8, "size": 4, "type": "bytes", "desc": "WAVE signature"},
            {"name": "fmt", "offset": 12, "size": 4, "type": "bytes", "desc": "fmt chunk ID"},
            {"name": "fmtSize", "offset": 16, "size": 4, "type": "uint32", "desc": "fmt chunk size"},
            {"name": "AudioFormat", "offset": 20, "size": 2, "type": "uint16", "desc": "Audio format"},
            {"name": "NumChannels", "offset": 22, "size": 2, "type": "uint16", "desc": "Number of channels"},
            {"name": "SampleRate", "offset": 24, "size": 4, "type": "uint32", "desc": "Sample rate"},
            {"name": "ByteRate", "offset": 28, "size": 4, "type": "uint32", "desc": "Byte rate"},
            {"name": "BlockAlign", "offset": 32, "size": 2, "type": "uint16", "desc": "Block align"},
            {"name": "BitsPerSample", "offset": 34, "size": 2, "type": "uint16", "desc": "Bits per sample"},
        ]

        return template

    def _create_png_template(self) -> StructureTemplate:
        """Create PNG header template."""
        template = StructureTemplate("PNG Header")
        template._description = "Portable Network Graphics header"

        template._fields = [
            {"name": "Signature", "offset": 0, "size": 8, "type": "bytes", "desc": "PNG signature"},
            {"name": "IHDR_Length", "offset": 8, "size": 4, "type": "uint32", "desc": "IHDR chunk length"},
            {"name": "IHDR_Type", "offset": 12, "size": 4, "type": "bytes", "desc": "IHDR type"},
            {"name": "IHDR_Width", "offset": 16, "size": 4, "type": "uint32", "desc": "Image width"},
            {"name": "IHDR_Height", "offset": 20, "size": 4, "type": "uint32", "desc": "Image height"},
            {"name": "IHDR_BitDepth", "offset": 24, "size": 1, "type": "uint8", "desc": "Bit depth"},
            {"name": "IHDR_ColorType", "offset": 25, "size": 1, "type": "uint8", "desc": "Color type"},
            {"name": "IHDR_Compression", "offset": 26, "size": 1, "type": "uint8", "desc": "Compression"},
            {"name": "IHDR_Filter", "offset": 27, "size": 1, "type": "uint8", "desc": "Filter"},
            {"name": "IHDR_Interlace", "offset": 28, "size": 1, "type": "uint8", "desc": "Interlace"},
        ]

        return template

    def get_template(self, name: str) -> Optional[StructureTemplate]:
        """Get template by name."""
        return self._templates.get(name.lower())

    def get_template_names(self) -> List[str]:
        """Get list of available template names."""
        return list(self._templates.keys())

    def get_all_templates(self) -> List[StructureTemplate]:
        """Get all templates."""
        return list(self._templates.values())

    def detect_format(self, data: bytes) -> Optional[str]:
        """Auto-detect file format from data."""
        if len(data) < 16:
            return None

        # Check ELF
        if data[:4] == b'\x7fELF':
            return "elf"

        # Check PE
        if data[:2] == b'MZ':
            # Could be PE, check for PE signature at offset 0x3C
            if len(data) > 0x40:
                pe_offset = int.from_bytes(data[0x3C:0x40], 'little')
                if len(data) > pe_offset + 2 and data[pe_offset:pe_offset+2] == b'PE':
                    return "pe"

        # Check Mach-O
        if data[:4] in (b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
                         b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe'):
            return "macho"

        # Check PNG
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return "png"

        # Check WAV
        if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
            return "wav"

        # Check BMP
        if data[:2] == b'BM':
            return "bmp"

        return None

    def select_template(self, name: str):
        """Select active template."""
        template = self.get_template(name)
        if template:
            self._current_template = template
            self.template_selected.emit(template)

    @property
    def current_template(self) -> Optional[StructureTemplate]:
        """Get current template."""
        return self._current_template
