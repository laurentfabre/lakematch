"""MurmurHash3 x86_32 over UTF-8, matching Spark ML's post-3.0 HashingTF.

Spark SQL hash() retains the older byte-tail variant. This standard Murmur3
expression uses only SQL built-ins and signed-safe 64-bit intermediates.
"""
from pyspark.sql import functions as F

MASK = 0xffffffff


def _u32(value):
    return value.bitwiseAND(F.lit(MASK))


def _bind(value, function):
    # Bind a complex expression to a lambda variable before reusing it. This
    # prevents exponential expression growth through rotations and xor shifts.
    return F.aggregate(F.array(value.cast('long')), F.lit(0).cast('long'), lambda _, bound: function(bound))


def _rotate(value, bits):
    return _u32(F.shiftleft(value, bits).bitwiseOR(F.shiftrightunsigned(value, 32 - bits)))


def _mix_key(value):
    # Signed forms of c1/c2 keep every multiplication within int64 before mask.
    return _bind(_u32(value * F.lit(-862048943)), lambda key:
        _u32(_rotate(key, 15) * F.lit(461845907)))


def hash_utf8(value, seed=42):
    encoded = F.encode(value, 'UTF-8')
    hexadecimal = F.hex(encoded)
    length = F.length(encoded)
    blocks = F.floor(length / F.lit(4)).cast('int')
    def byte(position):
        return F.conv(F.substring(hexadecimal, position * 2 + 1, F.lit(2)), 16, 10).cast('long')
    indices = F.when(blocks > 0, F.sequence(F.lit(0), blocks - 1)).otherwise(F.array().cast('array<int>'))
    def block(h, index):
        key = sum((byte(index * 4 + offset) * (1 << (8 * offset)) for offset in range(4)), F.lit(0).cast('long'))
        return _bind(h.bitwiseXOR(_mix_key(key)), lambda mixed: _u32(_rotate(mixed, 13) * 5 - 430675100))
    accumulated = F.aggregate(indices, F.lit(seed).cast('long'), block)
    tail_length = F.pmod(length, F.lit(4))
    tail = sum((F.when(tail_length > offset, byte(blocks * 4 + offset) * (1 << (8 * offset))).otherwise(0)
                for offset in range(3)), F.lit(0).cast('long'))
    with_tail = accumulated.bitwiseXOR(F.when(tail_length > 0, _mix_key(tail)).otherwise(F.lit(0)))
    mixed = _bind(with_tail.bitwiseXOR(length.cast('long')),
                  lambda h: _u32(h.bitwiseXOR(F.shiftrightunsigned(h, 16)) * F.lit(-2048144789)))
    mixed = _bind(mixed, lambda h: _u32(h.bitwiseXOR(F.shiftrightunsigned(h, 13)) * F.lit(-1028477387)))
    mixed = _bind(mixed, lambda h: h.bitwiseXOR(F.shiftrightunsigned(h, 16)))
    return _bind(mixed, lambda h: F.when(h >= (1 << 31), h - (1 << 32)).otherwise(h)).cast('int')
