"""
AI Coder

Code generation functionality.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any, List

from .base import AIBase, AIProvider
from .local import LocalAI
from .cloud import CloudAI


class CodeGenerator(QObject):
    """
    AI-powered code generator.

    Generates parsing code from data structures.
    """

    # Signals
    generation_started = pyqtSignal(str)  # Language
    generation_finished = pyqtSignal(str, str)  # Language, code
    generation_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._ai_provider: Optional[AIBase] = None
        self._templates: Dict[str, str] = {}

        # Load built-in templates
        self._load_templates()

    def set_provider(self, provider: AIBase):
        """Set AI provider."""
        self._ai_provider = provider

    def _load_templates(self):
        """Load built-in code templates."""
        self._templates["c_struct"] = """// C Structure Definition
typedef struct {name} {{
{fields}
}} {name}_t;

// Parsing function
void parse_{name_lower}(const uint8_t* data, {name}_t* result) {{
{parser}
}}
"""

        self._templates["python_class"] = '''class {name}:
    """{description}"""

    def __init__(self):
{fields_init}
{parser}
'''

    def generate_structure_code(self, structure: Dict[str, Any],
                                language: str = "c") -> str:
        """
        Generate code for data structure.

        Args:
            structure: Structure definition
            language: Target language

        Returns:
            Generated code
        """
        self.generation_started.emit(language)

        try:
            name = structure.get("name", "Unknown")
            description = structure.get("description", "")
            fields = structure.get("fields", [])

            if language == "c":
                code = self._generate_c_code(name, description, fields)
            elif language == "python":
                code = self._generate_python_code(name, description, fields)
            elif language == "rust":
                code = self._generate_rust_code(name, description, fields)
            else:
                code = f"// Language '{language}' not supported"

            self.generation_finished.emit(language, code)
            return code

        except Exception as e:
            error = str(e)
            self.generation_error.emit(error)
            return f"// Error: {error}"

    def _generate_c_code(self, name: str, description: str,
                         fields: List[Dict[str, Any]]) -> str:
        """Generate C code."""
        # Build field definitions
        field_defs = []
        parser_lines = []

        for i, field in enumerate(fields):
            fname = field.get("name", f"field_{i}")
            ftype = field.get("type", "uint32_t")
            offset = field.get("offset", i * 4)

            field_defs.append(f"    {ftype} {fname};  // offset: {offset}")
            parser_lines.append(f"    memcpy(&result->{fname}, data + {offset}, sizeof({ftype}));")

        fields_str = "\n".join(field_defs)
        parser_str = "\n".join(parser_lines)

        template = self._templates.get("c_struct", "")
        code = template.format(
            name=name,
            name_lower=name.lower(),
            fields=fields_str,
            parser=parser_str,
            description=description
        )

        return code

    def _generate_python_code(self, name: str, description: str,
                             fields: List[Dict[str, Any]]) -> str:
        """Generate Python code."""
        # Build field definitions
        field_defs = []
        parser_lines = ["        # Copy data"]

        for i, field in enumerate(fields):
            fname = field.get("name", f"field_{i}")
            ftype = field.get("type", "uint32")
            offset = field.get("offset", i * 4)
            length = field.get("length", 4)

            field_defs.append(f"        self.{fname} = None  # offset: {offset}")
            parser_lines.append(f"        self.{fname} = data[{offset}:{offset + length}]")

        fields_str = "\n".join(field_defs)
        parser_str = "\n".join(parser_lines)

        template = self._templates.get("python_class", "")
        code = template.format(
            name=name,
            name_lower=name.lower(),
            fields=fields_str,
            parser=parser_str,
            description=description
        )

        return code

    def _generate_rust_code(self, name: str, description: str,
                           fields: List[Dict[str, Any]]) -> str:
        """Generate Rust code."""
        field_defs = []
        parser_lines = []

        for i, field in enumerate(fields):
            fname = field.get("name", f"field_{i}")
            ftype = field.get("type", "u32")
            offset = field.get("offset", i * 4)

            field_defs.append(f"    pub {fname}: {ftype},")
            parser_lines.append(
                f"        let {fname} = u32::from_le_bytes(data[{offset}:{offset + 4}].try_into().unwrap());"
            )

        fields_str = "\n".join(field_defs)
        parser_str = "\n".join(parser_lines)

        # Create field list for Rust Self initialization
        field_names = [f.get("name", f"field_{i}") for i, f in enumerate(fields)]
        field_list = ', '.join(field_names)

        code = f"""#[derive(Debug)]
pub struct {name} {{
{fields_str}
}}

impl {name} {{
    pub fn from_bytes(data: &[u8]) -> Self {{
{parser_str}
        Self {{ {field_list} }}
    }}
}}
"""

        return code

    def generate_parsing_function(self, data: bytes, language: str = "python") -> str:
        """
        Generate parsing function for raw data.

        Args:
            data: Sample data
            language: Target language

        Returns:
            Generated parsing function
        """
        provider = self._ai_provider or LocalAI()

        if not provider.is_available:
            return f"// AI provider not available"

        # Analyze data first
        analysis = provider.analyze(data, "Analyze this data structure and suggest parsing code.")

        prompt = f"""Generate a complete {language} function to parse this data:

Data (hex): {data[:64].hex()}

Analysis: {analysis}

Return ONLY the code, no explanations. Use proper syntax and error handling."""

        return provider.chat(prompt)

    def generate_serialization_code(self, structure: Dict[str, Any],
                                    language: str = "c") -> str:
        """
        Generate serialization (packing) code.

        Args:
            structure: Structure definition
            language: Target language

        Returns:
            Generated serialization code
        """
        name = structure.get("name", "Unknown")
        fields = structure.get("fields", [])

        if language == "c":
            # Build memcpy lines
            memcpy_lines = []
            for i, field in enumerate(fields):
                fname = field.get("name", f"field_{i}")
                flength = field.get("length", 4)
                memcpy_lines.append(f"    memcpy(buffer + offset, &data->{fname}, {flength});")

            memcpy_str = "\n".join(memcpy_lines)
            total_size = sum(f.get('length', 4) for f in fields)

            return f"""// Serialize {name} to bytes
int serialize_{name.lower()}(const {name}_t* data, uint8_t* buffer, int buffer_size) {{
    if (buffer_size < {total_size}) {{
        return -1;
    }}

    int offset = 0;
{memcpy_str}

    return offset;
}}
"""
        elif language == "python":
            # Build getattr lines
            getattr_lines = []
            for i, field in enumerate(fields):
                fname = field.get("name", f"field_{i}")
                flength = field.get("length", 4)
                getattr_lines.append(f'    result += getattr(obj, "{fname}", b"\\x00" * {flength})')

            getattr_str = "\n".join(getattr_lines)

            return f"""# Serialize {name} to bytes
def serialize_{name.lower()}(obj) -> bytes:
    result = b''
{getattr_str}
    return result
"""
        else:
            return f"// Serialization for {language} not implemented"

    def generate_binding(self, structure: Dict[str, Any],
                        source_lang: str = "c",
                        target_lang: str = "python") -> str:
        """
        Generate language binding.

        Args:
            structure: Structure definition
            source_lang: Source language
            target_lang: Target language

        Returns:
            Generated binding code
        """
        if target_lang == "python" and source_lang == "c":
            return self._generate_cffi_binding(structure)

        return f"// Binding {source_lang} -> {target_lang} not implemented"

    def _generate_cffi_binding(self, structure: Dict[str, Any]) -> str:
        """Generate Python CFFI binding for C structure."""
        name = structure.get("name", "Unknown")
        fields = structure.get("fields", [])

        # Build struct fields
        struct_fields = []
        for i, field in enumerate(fields):
            ftype = field.get("type", "uint32_t")
            fname = field.get("name", f"field_{i}")
            struct_fields.append(f"    {ftype} {fname};")

        struct_str = "\n".join(struct_fields)

        return f'''"""Python binding for {name}"""
from cffi import FFI

ffi = FFI()

# Define types
ffi.cdef("""
typedef struct {name} {{
{struct_str}
}} {name}_t;

void parse_{name.lower()}(const uint8_t* data, {name}_t* result);
void serialize_{name.lower()}(const {name}_t* data, uint8_t* buffer, int buffer_size);
""")

# Load library
lib = ffi.dlopen("./{name.lower()}.so")

class {name}:
    """Python wrapper for {name}"""

    def __init__(self):
        self._data = ffi.new("{name}_t*")

    @property
    def fields(self):
        # Build field dict
        field_dict = {{}}
        for i, field in enumerate(fields):
            fname = field.get("name", f"field_{{i}}")
            field_dict[fname] = self._data.__getattr__(fname)
        return field_dict

    @classmethod
    def from_bytes(cls, data: bytes) -> "{name}":
        """Parse from bytes"""
        obj = cls()
        if len(data) < ffi.sizeof("{name}_t"):
            raise ValueError("Data too small")
        lib.parse_{name.lower()}(ffi.cast("uint8_t*", ffi.from_buffer(data)), obj._data)
        return obj

    def to_bytes(self) -> bytes:
        """Serialize to bytes"""
        buffer = ffi.new("uint8_t[]", ffi.sizeof("{name}_t"))
        lib.serialize_{name.lower()}(self._data, buffer, ffi.sizeof("{name}_t"))
        return ffi.buffer(buffer)[:]
'''
