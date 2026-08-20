from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from backend.characters import CharacterRepository


MASK = 0xFFFFFFFF


def encrypted_character_header(
    name: str, level: int, class_name: str = "tagSkillClassName0101", hardcore: bool = False
) -> bytes:
    seed = 0x1234ABCD
    table: list[int] = []
    value = seed
    for _ in range(256):
        value = (((value >> 1) | (value << 31)) & MASK) * 39916801 & MASK
        table.append(value)
    state = seed
    output = bytearray(struct.pack("<I", seed ^ 1431655765))

    def write_bytes(clear: bytes) -> None:
        nonlocal state
        for byte in clear:
            encrypted = byte ^ (state & 0xFF)
            output.append(encrypted)
            state = (state ^ table[encrypted]) & MASK

    def write_uint(number: int) -> None:
        nonlocal state
        encrypted_value = (number & MASK) ^ state
        encrypted = struct.pack("<I", encrypted_value)
        output.extend(encrypted)
        for byte in encrypted:
            state = (state ^ table[byte]) & MASK

    def write_byte(number: int) -> None:
        write_bytes(bytes([number]))

    def write_string(text: str, encoding: str) -> None:
        write_uint(len(text))
        write_bytes(text.encode(encoding))

    write_uint(0x58434447)
    write_uint(1)
    write_string(name, "utf-16-le")
    write_byte(1)
    write_string(class_name, "ascii")
    write_uint(level)
    write_byte(1 if hardcore else 0)
    write_byte(1)
    return bytes(output)


class CharacterRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.steam_root = Path(self.temporary_directory.name) / "Steam"
        self.save_dir = (
            self.steam_root / "userdata/123/219990/remote/save/main/_TestHero"
        )
        self.save_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_lists_character_name_level_mode_without_returning_save_path(self) -> None:
        (self.save_dir / "player.gdc").write_bytes(
            encrypted_character_header("Test Hero", 73, hardcore=True)
        )
        characters = CharacterRepository(self.steam_root).list()
        self.assertEqual(len(characters), 1)
        self.assertEqual(characters[0].name, "Test Hero")
        self.assertEqual(characters[0].level, 73)
        self.assertTrue(characters[0].hardcore)
        self.assertNotIn("/", characters[0].character_id)

    def test_ignores_malformed_and_oversized_saves(self) -> None:
        (self.save_dir / "player.gdc").write_bytes(b"not a character")
        self.assertEqual(CharacterRepository(self.steam_root).list(), ())


if __name__ == "__main__":
    unittest.main()
