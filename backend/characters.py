from __future__ import annotations

import hashlib
import struct
from datetime import UTC, datetime
from pathlib import Path

from .models import CharacterSummary


_MASK = 0xFFFFFFFF
_XOR_KEY = 1431655765
_PRIME = 39916801
_MAGIC = 0x58434447
_MAX_SAVE_BYTES = 8 * 1024 * 1024
_MAX_STRING_CHARS = 512


class CharacterFormatError(ValueError):
    pass


class _CryptoReader:
    def __init__(self, data: bytes):
        if len(data) < 12 or len(data) > _MAX_SAVE_BYTES:
            raise CharacterFormatError("Invalid character save size")
        self.data = data
        self.position = 4
        raw_seed = struct.unpack_from("<I", data, 0)[0]
        self.state = (raw_seed ^ _XOR_KEY) & _MASK
        self.table = self._make_table(self.state)

    @staticmethod
    def _make_table(seed: int) -> tuple[int, ...]:
        values: list[int] = []
        value = seed
        for _ in range(256):
            value = (((value >> 1) | (value << 31)) & _MASK) * _PRIME & _MASK
            values.append(value)
        return tuple(values)

    def _take_encrypted(self, count: int) -> bytes:
        if count < 0 or count > _MAX_SAVE_BYTES or self.position + count > len(self.data):
            raise CharacterFormatError("Truncated character save")
        encrypted = self.data[self.position : self.position + count]
        self.position += count
        return encrypted

    def _update(self, encrypted: bytes) -> None:
        for byte in encrypted:
            self.state = (self.state ^ self.table[byte]) & _MASK

    def read_bytes(self, count: int) -> bytes:
        encrypted = self._take_encrypted(count)
        clear = bytearray(count)
        for index, byte in enumerate(encrypted):
            clear[index] = byte ^ (self.state & 0xFF)
            self._update(bytes([byte]))
        return bytes(clear)

    def read_uint(self) -> int:
        encrypted = self._take_encrypted(4)
        value = struct.unpack("<I", encrypted)[0] ^ self.state
        self._update(encrypted)
        return value & _MASK

    def read_int(self) -> int:
        value = self.read_uint()
        return value if value < 0x80000000 else value - 0x100000000

    def read_byte(self) -> int:
        encrypted = self._take_encrypted(1)
        value = encrypted[0] ^ (self.state & 0xFF)
        self._update(encrypted)
        return value

    def read_string(self, encoding: str) -> str:
        length = self.read_int()
        if length < 0 or length > _MAX_STRING_CHARS:
            raise CharacterFormatError("Invalid character string length")
        multiplier = 2 if encoding == "utf-16-le" else 1
        return self.read_bytes(length * multiplier).decode(encoding, errors="strict")


def read_character_header(path: Path) -> CharacterSummary:
    if path.is_symlink() or not path.is_file():
        raise CharacterFormatError("Character save is not a regular file")
    size = path.stat().st_size
    if size < 12 or size > _MAX_SAVE_BYTES:
        raise CharacterFormatError("Invalid character save size")
    reader = _CryptoReader(path.read_bytes())
    if reader.read_uint() != _MAGIC or reader.read_int() not in {1, 2}:
        raise CharacterFormatError("Unsupported character save")
    name = reader.read_string("utf-16-le").strip()
    reader.read_byte()  # sex flag
    class_name = reader.read_string("ascii").strip()
    level = reader.read_int()
    hardcore = reader.read_byte() == 1
    reader.read_byte()  # expansion flag
    if not name or not 0 <= level <= 100:
        raise CharacterFormatError("Invalid character header")
    relative_identity = str(path.parent).encode("utf-8", errors="replace")
    character_id = hashlib.sha256(relative_identity).hexdigest()[:16]
    modified = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    return CharacterSummary(
        character_id=character_id,
        name=name,
        level=level,
        hardcore=hardcore,
        class_name=class_name,
        modified_at=modified,
    )


class CharacterRepository:
    def __init__(self, steam_root: Path):
        self.steam_root = Path(steam_root)

    def list(self) -> tuple[CharacterSummary, ...]:
        userdata = self.steam_root / "userdata"
        if not userdata.is_dir():
            return ()
        def modified_time(path: Path) -> float:
            try:
                return path.stat().st_mtime if path.is_file() else 0
            except OSError:
                return 0

        saves = sorted(
            userdata.glob("*/219990/remote/save/main/_*/player.gdc"),
            key=modified_time,
            reverse=True,
        )[:100]
        characters: list[CharacterSummary] = []
        for save in saves:
            try:
                characters.append(read_character_header(save))
            except (CharacterFormatError, OSError, UnicodeError, struct.error):
                continue
        return tuple(characters)
