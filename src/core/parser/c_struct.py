"""
C struct parsing helpers for row-based binary decoding.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
import struct


@dataclass(frozen=True)
class CTypeSpec:
    """Normalized C type information."""

    kind: str
    size: int
    signed: bool = False


@dataclass(frozen=True)
class CStructField:
    """A single parsed C struct field."""

    name: str
    type_name: str
    kind: str
    size: int
    count: int = 1
    signed: bool = False
    bit_width: int = 0
    flexible_array: bool = False
    nested_definition: "CStructDefinition | None" = None

    @property
    def is_bitfield(self) -> bool:
        """Return whether the field is a bitfield."""
        return self.bit_width > 0

    @property
    def display_name(self) -> str:
        """Return a user-facing field label."""
        label = self.name
        if self.flexible_array:
            label += "[]"
        elif self.count > 1:
            label += f"[{self.count}]"
        if self.is_bitfield:
            label += f":{self.bit_width}"
        return label

    @property
    def total_size(self) -> int:
        """Return the total byte size occupied by the field."""
        if self.flexible_array or self.is_bitfield:
            return 0
        if self.nested_definition is not None:
            return self.nested_definition.total_size * self.count
        return self.size * self.count


@dataclass(frozen=True)
class CStructDefinition:
    """Parsed C struct definition."""

    name: str
    fields: list[CStructField]
    source: str = ""

    @property
    def total_size(self) -> int:
        """Return the fixed-size prefix of the packed struct."""
        offset = 0
        bit_container_size = 0
        bit_offset = 0

        for field in self.fields:
            if field.is_bitfield:
                container_bits = field.size * 8
                if (
                    bit_container_size != field.size
                    or bit_offset + field.bit_width > container_bits
                    or bit_offset == container_bits
                ):
                    if bit_container_size:
                        offset += bit_container_size
                    bit_container_size = field.size
                    bit_offset = 0

                bit_offset += field.bit_width
                if bit_offset == container_bits:
                    offset += bit_container_size
                    bit_container_size = 0
                    bit_offset = 0
                continue

            if bit_container_size:
                offset += bit_container_size
                bit_container_size = 0
                bit_offset = 0

            if field.flexible_array:
                continue
            offset += field.size * field.count

        if bit_container_size:
            offset += bit_container_size
        return offset


_TYPE_SPECS = {
    "bool": CTypeSpec("bool", 1, False),
    "char": CTypeSpec("char", 1, True),
    "signed char": CTypeSpec("int", 1, True),
    "unsigned char": CTypeSpec("int", 1, False),
    "int8_t": CTypeSpec("int", 1, True),
    "uint8_t": CTypeSpec("int", 1, False),
    "short": CTypeSpec("int", 2, True),
    "short int": CTypeSpec("int", 2, True),
    "signed short": CTypeSpec("int", 2, True),
    "signed short int": CTypeSpec("int", 2, True),
    "unsigned short": CTypeSpec("int", 2, False),
    "unsigned short int": CTypeSpec("int", 2, False),
    "int16_t": CTypeSpec("int", 2, True),
    "uint16_t": CTypeSpec("int", 2, False),
    "int": CTypeSpec("int", 4, True),
    "signed": CTypeSpec("int", 4, True),
    "signed int": CTypeSpec("int", 4, True),
    "unsigned": CTypeSpec("int", 4, False),
    "unsigned int": CTypeSpec("int", 4, False),
    "long": CTypeSpec("int", 4, True),
    "long int": CTypeSpec("int", 4, True),
    "signed long": CTypeSpec("int", 4, True),
    "signed long int": CTypeSpec("int", 4, True),
    "unsigned long": CTypeSpec("int", 4, False),
    "unsigned long int": CTypeSpec("int", 4, False),
    "int32_t": CTypeSpec("int", 4, True),
    "uint32_t": CTypeSpec("int", 4, False),
    "long long": CTypeSpec("int", 8, True),
    "long long int": CTypeSpec("int", 8, True),
    "signed long long": CTypeSpec("int", 8, True),
    "signed long long int": CTypeSpec("int", 8, True),
    "unsigned long long": CTypeSpec("int", 8, False),
    "unsigned long long int": CTypeSpec("int", 8, False),
    "int64_t": CTypeSpec("int", 8, True),
    "uint64_t": CTypeSpec("int", 8, False),
    "float": CTypeSpec("float", 4, False),
    "double": CTypeSpec("float", 8, False),
    "byte": CTypeSpec("int", 1, False),
    "word": CTypeSpec("int", 2, False),
    "dword": CTypeSpec("int", 4, False),
    "qword": CTypeSpec("int", 8, False),
}

_VAR_RE = re.compile(
    r"^(?P<name>[A-Za-z_]\w*)\s*(?:\[\s*(?P<count>\d*)\s*\])?\s*(?::\s*(?P<bit_width>\d+)\s*)?$"
)
_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_ATTRIBUTE_RE = re.compile(r"__attribute__\s*\(\(.*?\)\)", re.DOTALL)
_SORTED_TYPE_NAMES = sorted(_TYPE_SPECS.keys(), key=len, reverse=True)


def _strip_comments(definition: str) -> str:
    """Remove C-style comments from a struct definition."""
    return _COMMENT_RE.sub("", definition or "")


def _normalize_type_name(type_name: str) -> str:
    """Normalize qualifiers and whitespace in a C type string."""
    tokens = [
        token
        for token in re.split(r"\s+", (type_name or "").strip())
        if token and token not in {"const", "volatile", "static", "register"}
    ]
    return " ".join(tokens).lower()


def _split_declarations(body: str) -> list[str]:
    """Split the struct body into field declarations."""
    declarations = []
    current = []
    brace_depth = 0

    for char in body:
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)

        if char == ";" and brace_depth == 0:
            declaration = "".join(current).strip()
            current = []
            if not declaration or declaration.startswith("#pragma"):
                continue
            declarations.append(" ".join(declaration.split()))
            continue

        current.append(char)

    declaration = "".join(current).strip()
    if declaration and not declaration.startswith("#pragma"):
        declarations.append(" ".join(declaration.split()))
    return declarations


def _split_variables(var_part: str) -> list[str]:
    """Split a declaration's variable list, ignoring commas in nested braces."""
    variables = []
    current = []
    bracket_depth = 0

    for char in var_part:
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)

        if char == "," and bracket_depth == 0:
            variable = "".join(current).strip()
            current = []
            if variable:
                variables.append(variable)
            continue

        current.append(char)

    variable = "".join(current).strip()
    if variable:
        variables.append(variable)
    return variables


def _parse_variable_spec(raw_var: str, declaration: str, type_spec: CTypeSpec) -> tuple[str, int, bool, int]:
    """Parse variable suffixes like arrays and bitfields."""
    if raw_var.startswith("*"):
        raise ValueError(f"pointers are not supported: {raw_var}")

    var_match = _VAR_RE.match(raw_var)
    if not var_match:
        raise ValueError(f"invalid field declaration: {declaration}")

    raw_count = var_match.group("count")
    bit_width = int(var_match.group("bit_width") or "0")
    if ":" in raw_var and bit_width <= 0:
        raise ValueError(f"bitfield width must be positive: {declaration}")

    flexible_array = "[" in raw_var and raw_count == ""
    if flexible_array and bit_width:
        raise ValueError(f"flexible arrays cannot be bitfields: {declaration}")
    if bit_width > type_spec.size * 8:
        raise ValueError(f"bitfield width exceeds base type size: {declaration}")
    if bit_width and type_spec.kind not in {"int", "bool", "char"}:
        raise ValueError(f"unsupported bitfield type: {declaration}")

    count = 1
    if flexible_array:
        count = 0
    elif raw_count is not None:
        count = int(raw_count or "0")
        if count <= 0:
            raise ValueError(f"array size must be positive: {declaration}")

    return var_match.group("name"), count, flexible_array, bit_width


def _extract_struct_parts(declaration: str, require_suffix: bool = True) -> tuple[str, str, str]:
    """Extract struct tag, body, and suffix from a declaration."""
    prefix = "typedef struct" if declaration.startswith("typedef struct") else "struct"
    remainder = declaration[len(prefix):].strip()
    if "{" not in remainder:
        raise ValueError(f"unsupported struct reference: {declaration}")

    brace_start = remainder.find("{")
    tag = remainder[:brace_start].strip()
    brace_depth = 0
    body_chars = []
    end_index = -1

    for index in range(brace_start, len(remainder)):
        char = remainder[index]
        if char == "{":
            brace_depth += 1
            if brace_depth == 1:
                continue
        elif char == "}":
            brace_depth -= 1
            if brace_depth == 0:
                end_index = index
                break

        if brace_depth >= 1:
            body_chars.append(char)

    if end_index < 0:
        raise ValueError(f"unterminated nested struct: {declaration}")

    body = "".join(body_chars).strip()
    var_part = remainder[end_index + 1:].strip()
    if require_suffix and not var_part:
        raise ValueError(f"nested struct requires a field name: {declaration}")

    return tag, body, var_part


def _parse_declaration(
    declaration: str,
    type_registry: dict[str, CStructDefinition] | None = None,
) -> list[CStructField]:
    """Parse a single top-level field declaration."""
    registry = type_registry or {}
    if declaration.startswith("struct") and "{" in declaration:
        tag, nested_body, var_part = _extract_struct_parts(declaration)
        nested_fields = []
        for nested_declaration in _split_declarations(nested_body):
            nested_fields.extend(_parse_declaration(nested_declaration, registry))
        if not nested_fields:
            raise ValueError(f"nested struct has no supported fields: {declaration}")
        if any(field.flexible_array for field in nested_fields):
            raise ValueError(f"nested struct with flexible array is not supported: {declaration}")

        nested_definition = CStructDefinition(
            name=tag or "Anonymous",
            fields=nested_fields,
            source=nested_body,
        )
        nested_type_spec = CTypeSpec("struct", nested_definition.total_size, False)
        fields = []
        for raw_var in _split_variables(var_part):
            name, count, flexible_array, bit_width = _parse_variable_spec(
                raw_var, declaration, nested_type_spec
            )
            if bit_width:
                raise ValueError(f"struct fields cannot be bitfields: {declaration}")
            if flexible_array:
                raise ValueError(f"flexible array of struct is not supported: {declaration}")
            fields.append(
                CStructField(
                    name=name,
                    type_name=f"struct {tag}".strip(),
                    kind="struct",
                    size=nested_definition.total_size,
                    count=count,
                    signed=False,
                    bit_width=0,
                    flexible_array=False,
                    nested_definition=nested_definition,
                )
            )
        return fields

    normalized_decl = _normalize_type_name(declaration)
    matched_type = next(
        (
            candidate
            for candidate in _SORTED_TYPE_NAMES
            if normalized_decl == candidate or normalized_decl.startswith(candidate + " ")
        ),
        "",
    )

    normalized_type = matched_type
    type_spec = None
    nested_definition = None
    if normalized_type:
        type_spec = _TYPE_SPECS[normalized_type]
    else:
        matched_external_type = next(
            (
                candidate
                for candidate in sorted(registry.keys(), key=len, reverse=True)
                if normalized_decl == candidate or normalized_decl.startswith(candidate + " ")
            ),
            "",
        )
        if not matched_external_type:
            raise ValueError(f"invalid field declaration: {declaration}")
        normalized_type = matched_external_type
        nested_definition = registry[matched_external_type]
        type_spec = CTypeSpec("struct", nested_definition.total_size, False)

    var_part = declaration[len(normalized_type):].strip()
    if not var_part:
        raise ValueError(f"invalid field declaration: {declaration}")

    fields = []
    for raw_var in _split_variables(var_part):
        name, count, flexible_array, bit_width = _parse_variable_spec(
            raw_var, declaration, type_spec
        )
        if nested_definition is not None and bit_width:
            raise ValueError(f"struct fields cannot be bitfields: {declaration}")
        if nested_definition is not None and flexible_array:
            raise ValueError(f"flexible array of struct is not supported: {declaration}")
        fields.append(
            CStructField(
                name=name,
                type_name=normalized_type,
                kind=type_spec.kind,
                size=type_spec.size,
                count=count,
                signed=type_spec.signed,
                bit_width=bit_width,
                flexible_array=flexible_array,
                nested_definition=nested_definition,
            )
        )
    return fields


def _register_type_aliases(
    registry: dict[str, CStructDefinition],
    definition: CStructDefinition,
    tag: str,
    alias: str,
):
    """Register lookup names for a parsed struct definition."""
    if tag:
        registry[f"struct {tag.lower()}"] = definition
    if alias:
        registry[alias.lower()] = definition


def _parse_top_level_struct_definition(
    statement: str,
    registry: dict[str, CStructDefinition],
) -> CStructDefinition:
    """Parse a top-level struct definition and register its exported names."""
    is_typedef = statement.startswith("typedef struct")
    tag, body, suffix = _extract_struct_parts(statement, require_suffix=False)
    fields: list[CStructField] = []
    for declaration in _split_declarations(body):
        if "{" in declaration or "}" in declaration:
            if not declaration.startswith("struct"):
                raise ValueError(f"unsupported nested declaration: {declaration}")
        fields.extend(_parse_declaration(declaration, registry))

    if not fields:
        raise ValueError("struct has no supported fields")

    alias = suffix.strip()
    if "," in alias or " " in alias:
        raise ValueError(f"unsupported top-level struct suffix: {statement}")
    if alias and not is_typedef:
        raise ValueError(f"top-level struct variable declarations are not supported: {statement}")

    for field_index, field in enumerate(fields):
        if field.flexible_array and field_index != len(fields) - 1:
            raise ValueError("flexible array member must be the last field")

    definition = CStructDefinition(name=alias or tag or "Anonymous", fields=fields, source=statement)
    _register_type_aliases(registry, definition, tag, alias if is_typedef else "")
    return definition


def parse_c_struct_definition(definition: str) -> CStructDefinition:
    """Parse a packed C struct definition."""
    cleaned = _ATTRIBUTE_RE.sub("", _strip_comments(definition)).strip()
    if not cleaned:
        raise ValueError("empty struct definition")

    statements = _split_declarations(cleaned)
    if not statements:
        raise ValueError("struct has no fields")

    registry: dict[str, CStructDefinition] = {}
    root_declarations: list[str] = []
    parsed_definitions: list[CStructDefinition] = []

    for statement in statements:
        if (statement.startswith("typedef struct") or statement.startswith("struct")) and "{" in statement:
            parsed_definitions.append(_parse_top_level_struct_definition(statement, registry))
            continue
        root_declarations.append(statement)

    if root_declarations:
        fields: list[CStructField] = []
        for declaration in root_declarations:
            if "{" in declaration or "}" in declaration:
                if not declaration.startswith("struct"):
                    raise ValueError(f"unsupported nested declaration: {declaration}")
            fields.extend(_parse_declaration(declaration, registry))

        if not fields:
            raise ValueError("struct has no supported fields")
        for field_index, field in enumerate(fields):
            if field.flexible_array and field_index != len(fields) - 1:
                raise ValueError("flexible array member must be the last field")

        return CStructDefinition(name="Anonymous", fields=fields, source=definition)

    if parsed_definitions:
        return parsed_definitions[-1]

    raise ValueError("struct has no supported fields")


def _format_float(value: float) -> str:
    """Format floating point values with stable special-case output."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Inf" if value > 0 else "-Inf"
    return repr(value)


def _decode_char_bytes(raw: bytes) -> str:
    """Decode an ASCII byte string up to the first NUL byte."""
    visible = raw.split(b"\x00", 1)[0]
    if not visible:
        return ""
    return visible.decode("ascii", errors="replace")


def _format_int_value(raw: bytes, signed: bool, display_base: str, byteorder: str) -> str:
    """Format integer bytes in hex or decimal."""
    if display_base == "hex":
        unsigned_value = int.from_bytes(raw, byteorder=byteorder, signed=False)
        return f"0x{unsigned_value:0{len(raw) * 2}X}"
    value = int.from_bytes(raw, byteorder=byteorder, signed=signed)
    return str(value)


def _format_bool_value(raw: bytes, display_base: str) -> str:
    """Format boolean values."""
    if display_base == "hex":
        return f"0x{raw[0]:02X}"
    return "True" if raw[0] else "False"


def _format_bitfield_value(field: CStructField, value: int, display_base: str) -> str:
    """Format an extracted bitfield value."""
    if field.kind == "bool" and display_base != "hex":
        return "True" if value else "False"
    if display_base == "hex":
        width_chars = max(1, (field.bit_width + 3) // 4)
        unsigned_value = value & ((1 << field.bit_width) - 1)
        return f"0x{unsigned_value:0{width_chars}X}"
    return str(value)


def _format_float_value(raw: bytes, display_base: str, byteorder: str) -> str:
    """Format floating point values."""
    if display_base == "hex":
        value = int.from_bytes(raw, byteorder=byteorder, signed=False)
        return f"0x{value:0{len(raw) * 2}X}"
    fmt = "<f" if len(raw) == 4 and byteorder == "little" else ">f"
    if len(raw) == 8:
        fmt = "<d" if byteorder == "little" else ">d"
    return _format_float(struct.unpack(fmt, raw)[0])


def _format_char_value(raw: bytes, display_base: str) -> str:
    """Format a single char value."""
    if display_base == "hex":
        return f"0x{raw[0]:02X}"
    byte = raw[0]
    if 32 <= byte <= 126:
        return repr(chr(byte))
    return str(byte)


def _format_array_value(field: CStructField, raw: bytes, display_base: str, byteorder: str) -> str:
    """Format an array field."""
    if field.kind == "char":
        if display_base == "hex":
            return " ".join(f"{byte:02X}" for byte in raw)
        return _decode_char_bytes(raw)

    if field.flexible_array:
        element_count = len(raw) // max(1, field.size)
    else:
        element_count = field.count

    parts = []
    for index in range(element_count):
        chunk = raw[index * field.size:(index + 1) * field.size]
        parts.append(_format_scalar_value(field, chunk, display_base, byteorder))
    remainder = raw[element_count * field.size:]
    if remainder:
        if display_base == "hex":
            parts.append("tail:" + " ".join(f"{byte:02X}" for byte in remainder))
        else:
            parts.append("tail:" + " ".join(str(byte) for byte in remainder))
    return "[" + ", ".join(parts) + "]"


def _format_scalar_value(field: CStructField, raw: bytes, display_base: str, byteorder: str) -> str:
    """Format a scalar field value."""
    if field.kind == "int":
        return _format_int_value(raw, field.signed, display_base, byteorder)
    if field.kind == "bool":
        return _format_bool_value(raw, display_base)
    if field.kind == "float":
        return _format_float_value(raw, display_base, byteorder)
    if field.kind == "char":
        return _format_char_value(raw, display_base)
    return " ".join(f"{byte:02X}" for byte in raw)


def format_field_value(
    field: CStructField,
    raw: bytes,
    display_base: str = "hex",
    byteorder: str = "little",
) -> str:
    """Format raw bytes for a field."""
    if field.is_bitfield:
        return "N/A"
    required_size = len(raw) if field.flexible_array else field.total_size
    if len(raw) < required_size:
        return "N/A"
    if field.flexible_array or field.count > 1:
        return _format_array_value(field, raw, display_base, byteorder)
    return _format_scalar_value(field, raw, display_base, byteorder)


def _decode_bitfield_value(field: CStructField, raw: bytes, bit_offset: int, byteorder: str) -> int | None:
    """Extract a bitfield value from its storage unit."""
    if len(raw) < field.size:
        return None

    mask = (1 << field.bit_width) - 1
    unsigned_value = int.from_bytes(raw[:field.size], byteorder=byteorder, signed=False)
    value = (unsigned_value >> bit_offset) & mask
    if field.signed and field.bit_width > 0:
        sign_bit = 1 << (field.bit_width - 1)
        if value & sign_bit:
            value -= 1 << field.bit_width
    return value


def _decode_struct_rows(
    definition: CStructDefinition,
    payload: bytes,
    prefix: str,
    display_base: str,
    byteorder: str,
) -> list[tuple[CStructField, str]]:
    """Decode a struct definition into flattened rows."""
    offset = 0
    rows: list[tuple[CStructField, str]] = []
    bit_container_size = 0
    bit_offset = 0

    for field in definition.fields:
        full_name = f"{prefix}{field.name}" if prefix else field.name
        flat_field = replace(field, name=full_name)

        if field.is_bitfield:
            container_bits = field.size * 8
            if (
                bit_container_size != field.size
                or bit_offset + field.bit_width > container_bits
                or bit_offset == container_bits
            ):
                if bit_container_size:
                    offset += bit_container_size
                bit_container_size = field.size
                bit_offset = 0

            chunk = payload[offset:offset + field.size]
            value = _decode_bitfield_value(field, chunk, bit_offset, byteorder)
            rows.append((flat_field, "N/A" if value is None else _format_bitfield_value(field, value, display_base)))
            bit_offset += field.bit_width
            if bit_offset == container_bits:
                offset += bit_container_size
                bit_container_size = 0
                bit_offset = 0
            continue

        if bit_container_size:
            offset += bit_container_size
            bit_container_size = 0
            bit_offset = 0

        if field.nested_definition is not None:
            nested_size = field.nested_definition.total_size
            if nested_size <= 0:
                rows.append((flat_field, "N/A"))
                continue

            element_count = max(1, field.count)
            for index in range(element_count):
                nested_prefix = f"{full_name}."
                if field.count > 1:
                    nested_prefix = f"{full_name}[{index}]."
                chunk = payload[offset:offset + nested_size]
                rows.extend(
                    _decode_struct_rows(
                        field.nested_definition,
                        chunk,
                        nested_prefix,
                        display_base,
                        byteorder,
                    )
                )
                offset += nested_size
            continue

        if field.flexible_array:
            chunk = payload[offset:]
            rows.append((flat_field, format_field_value(field, chunk, display_base, byteorder)))
            offset = len(payload)
            continue

        chunk = payload[offset:offset + field.total_size]
        rows.append((flat_field, format_field_value(field, chunk, display_base, byteorder)))
        offset += field.total_size

    return rows


def decode_c_struct(
    definition: CStructDefinition,
    data: bytes,
    display_base: str = "hex",
    byteorder: str = "little",
) -> list[tuple[CStructField, str]]:
    """Decode row bytes according to a parsed C struct definition."""
    return _decode_struct_rows(
        definition,
        bytes(data or b""),
        "",
        display_base,
        byteorder,
    )
