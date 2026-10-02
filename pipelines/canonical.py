"""Architecture Suite canonical JSON profile v1 (``canonical-json``), for sealing snapshots.

Reference: ``contracts/canonical-json.md`` of the suite (Document Studio repository, copied byte for byte in each repository
of the suite) and its shared vectors (``tests/fixtures/canonical-json.vectors.json``). A value is serialisable or REFUSED;
nothing is approximated.

``json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`` is NOT this profile: it writes ``1.0`` and ``1e-07``
(the profile: ``1``, ``1e-7``), orders keys by code point instead of UTF-16 code unit, and accepts ``NaN`` and numbers
beyond ``2**53 - 1``. Use this module for every seal that a suite component may verify.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

MAX_SAFE = 2**53 - 1


class CanonicalError(ValueError):
    """A value the profile refuses. ``code`` is the profile's error code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _number(value: int | float) -> str:
    if isinstance(value, int):
        if abs(value) > MAX_SAFE:
            raise CanonicalError("CANONICAL_UNSAFE_INTEGER", f"{value} exceeds 2**53 - 1 (write it as a string)")
        return str(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise CanonicalError("CANONICAL_NON_FINITE_NUMBER", "NaN and infinities do not exist in JSON")
    if abs(value) > MAX_SAFE:
        raise CanonicalError("CANONICAL_UNSAFE_INTEGER", f"{value!r} exceeds 2**53 - 1 in magnitude")
    if value == 0:
        return "0"  # also -0.0
    sign, digits, exponent = Decimal(repr(value)).as_tuple()
    assert isinstance(exponent, int)
    s = "".join(map(str, digits)).rstrip("0") or "0"
    n = len(digits) + exponent  # value = 0.<digits> * 10**n (trailing zeros of the digit string do not move it)
    k = len(s)
    if k <= n <= 21:
        text = s + "0" * (n - k)
    elif 0 < n <= 21:
        text = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        text = "0." + "0" * (-n) + s
    else:  # ECMAScript Number::toString exponent form
        e = n - 1
        mantissa = s if k == 1 else s[0] + "." + s[1:]
        text = f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"
    return ("-" if sign else "") + text


def _string(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as err:
        raise CanonicalError("CANONICAL_LONE_SURROGATE", "an unpaired surrogate cannot be sealed") from err
    return json.dumps(value, ensure_ascii=False)


def _key(key: str) -> bytes:
    return key.encode("utf-16-be", "surrogatepass")  # UTF-16 code unit order, as JavaScript sorts


def dumps(value: Any) -> str:
    """The canonical text of ``value``; raises :class:`CanonicalError` for anything the profile refuses."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int | float):
        return _number(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, list):
        return "[" + ",".join(dumps(v) for v in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise CanonicalError("CANONICAL_UNSUPPORTED_TYPE", "object keys must be strings")
        return "{" + ",".join(f"{_string(k)}:{dumps(value[k])}" for k in sorted(value, key=_key)) + "}"
    raise CanonicalError("CANONICAL_UNSUPPORTED_TYPE", f"{type(value).__name__} is not JSON (tuple, set, datetime, Decimal, bytes... are refused)")


def loads(text: str) -> Any:
    """Strict reader: ``NaN`` / ``Infinity`` literals are refused at parse time (Python's reader accepts them)."""

    def refuse(constant: str) -> Any:
        raise CanonicalError("CANONICAL_NON_FINITE_NUMBER", f"{constant} is not JSON")

    return json.loads(text, parse_constant=refuse)


def sha256(value: Any) -> str:
    """``sha256:<64 hex>`` of the canonical text of ``value`` (the checksum of a snapshot's ``data``)."""
    return "sha256:" + hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()
