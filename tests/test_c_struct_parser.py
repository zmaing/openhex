"""
Tests for C struct parsing and row decoding.
"""

from src.core.parser.c_struct import decode_c_struct, parse_c_struct_definition


def test_parse_typedef_struct_with_arrays_and_multiple_declarations():
    """The parser should accept common packed-style field declarations."""
    definition = parse_c_struct_definition(
        """
        typedef struct Packet {
            uint8_t type, flags;
            uint16_t size;
            char tag[2];
        } Packet;
        """
    )

    assert definition.name == "Packet"
    assert [field.name for field in definition.fields] == ["type", "flags", "size", "tag"]
    assert definition.total_size == 6


def test_decode_c_struct_supports_hex_and_decimal_views():
    """Decoded values should switch between hex and decimal formatting."""
    definition = parse_c_struct_definition(
        """
        typedef struct {
            uint8_t type;
            uint16_t size;
            char tag[2];
        } Packet;
        """
    )
    data = bytes([0xAB, 0x34, 0x12, 0x48, 0x49])

    hex_rows = decode_c_struct(definition, data, display_base="hex")
    dec_rows = decode_c_struct(definition, data, display_base="decimal")

    assert [value for _field, value in hex_rows] == ["0xAB", "0x1234", "48 49"]
    assert [value for _field, value in dec_rows] == ["171", "4660", "HI"]


def test_decode_c_struct_supports_bitfields_and_flexible_arrays():
    """Bitfields should share storage and flexible arrays should consume remaining bytes."""
    definition = parse_c_struct_definition(
        """
        typedef struct {
            uint8_t kind;
            uint8_t enabled:1;
            uint8_t mode:2;
            uint8_t reserved:5;
            uint8_t payload[];
        } Packet;
        """
    )
    data = bytes([0x01, 0x8D, 0xAA, 0xBB])

    hex_rows = decode_c_struct(definition, data, display_base="hex")
    dec_rows = decode_c_struct(definition, data, display_base="decimal")

    assert definition.total_size == 2
    assert [field.display_name for field, _value in hex_rows] == [
        "kind",
        "enabled:1",
        "mode:2",
        "reserved:5",
        "payload[]",
    ]
    assert [value for _field, value in hex_rows] == ["0x01", "0x1", "0x2", "0x11", "[0xAA, 0xBB]"]
    assert [value for _field, value in dec_rows] == ["1", "1", "2", "17", "[170, 187]"]


def test_decode_c_struct_supports_nested_struct_fields():
    """Nested inline structs should flatten into dotted field paths."""
    definition = parse_c_struct_definition(
        """
        typedef struct {
            uint8_t kind;
            struct {
                uint8_t version;
                uint8_t flags:3;
                uint8_t reserved:5;
            } header;
            uint8_t payload[2];
        } Packet;
        """
    )
    data = bytes([0x01, 0x02, 0x1D, 0xAA, 0xBB])

    hex_rows = decode_c_struct(definition, data, display_base="hex")
    dec_rows = decode_c_struct(definition, data, display_base="decimal")

    assert definition.total_size == 5
    assert [field.display_name for field, _value in hex_rows] == [
        "kind",
        "header.version",
        "header.flags:3",
        "header.reserved:5",
        "payload[2]",
    ]
    assert [value for _field, value in hex_rows] == ["0x01", "0x02", "0x5", "0x03", "[0xAA, 0xBB]"]
    assert [value for _field, value in dec_rows] == ["1", "2", "5", "3", "[170, 187]"]


def test_decode_c_struct_supports_external_struct_type_references():
    """Separate struct definitions should be reusable from later root structs."""
    definition = parse_c_struct_definition(
        """
        typedef struct {
            uint8_t version;
            uint8_t flags:3;
            uint8_t reserved:5;
        } Header;

        struct Footer {
            uint16_t crc;
        };

        typedef struct {
            Header header;
            struct Footer footer;
            uint8_t payload[2];
        } Packet;
        """
    )
    data = bytes([0x02, 0x1D, 0x34, 0x12, 0xAA, 0xBB])

    hex_rows = decode_c_struct(definition, data, display_base="hex")
    dec_rows = decode_c_struct(definition, data, display_base="decimal")

    assert definition.name == "Packet"
    assert definition.total_size == 6
    assert [field.display_name for field, _value in hex_rows] == [
        "header.version",
        "header.flags:3",
        "header.reserved:5",
        "footer.crc",
        "payload[2]",
    ]
    assert [value for _field, value in hex_rows] == ["0x02", "0x5", "0x03", "0x1234", "[0xAA, 0xBB]"]
    assert [value for _field, value in dec_rows] == ["2", "5", "3", "4660", "[170, 187]"]
