"""Reads Apple property lists: the XML kind and the binary bplist00 kind,
into dicts, lists, strings, numbers, booleans and bytes."""

MAX_OBJECTS = 20000


def _int_be(d, at, n):
    v = 0
    for i in range(n):
        v = v * 256 + d[at + i]
    return v


def binary(d):
    if d[:8] != b"bplist00" or len(d) < 40:
        raise ValueError("This is not a binary property list.")
    t = len(d) - 32
    offset_size = d[t + 6]
    ref_size = d[t + 7]
    count = _int_be(d, t + 8, 8)
    top = _int_be(d, t + 16, 8)
    table = _int_be(d, t + 24, 8)
    if count > MAX_OBJECTS or table + count * offset_size > t:
        raise ValueError("This property list is too big to show.")
    offsets = [_int_be(d, table + i * offset_size, offset_size) for i in range(count)]
    seen = {"n": 0}

    def length(at, low):
        if low != 0x0F:
            return low, at + 1
        marker = d[at + 1]
        n = 1
        for _ in range(marker & 0x0F):
            n = n * 2
        return _int_be(d, at + 2, n), at + 2 + n

    def obj(i, depth):
        seen["n"] = seen["n"] + 1
        if depth > 32 or seen["n"] > MAX_OBJECTS or i >= count:
            return None
        at = offsets[i]
        m = d[at]
        high = m // 16
        low = m % 16
        if m == 0x08:
            return False
        if m == 0x09:
            return True
        if high == 0x0:
            return None
        if high == 0x1:
            n = 1
            for _ in range(low):
                n = n * 2
            # Only 8-byte integers are signed; the sign comes from the first
            # byte so a small negative number stays a small integer.
            v = d[at + 1] - 256 if n == 8 and d[at + 1] >= 128 else d[at + 1]
            for k in range(1, n):
                v = v * 256 + d[at + 1 + k]
            return v
        if high == 0x2:
            from wm import formats
            return formats.unpack(">f" if low == 2 else ">d", d, at + 1)[0]
        if high == 0x3:
            from wm import formats
            seconds = formats.unpack(">d", d, at + 1)[0]
            return {"$date": seconds + 978307200}
        if high == 0x4:
            n, start = length(at, low)
            return d[start:start + n]
        if high == 0x5:
            n, start = length(at, low)
            return d[start:start + n].decode("utf-8", "replace")
        if high == 0x6:
            n, start = length(at, low)
            return "".join(chr(d[start + 2 * k] * 256 + d[start + 2 * k + 1]) for k in range(n))
        if high == 0x8:
            return {"$uid": _int_be(d, at + 1, low + 1)}
        if high in (0xA, 0xC):
            n, start = length(at, low)
            return [obj(_int_be(d, start + k * ref_size, ref_size), depth + 1) for k in range(n)]
        if high == 0xD:
            n, start = length(at, low)
            out = {}
            for k in range(n):
                key = obj(_int_be(d, start + k * ref_size, ref_size), depth + 1)
                out[str(key)] = obj(_int_be(d, start + (n + k) * ref_size, ref_size), depth + 1)
            return out
        return None

    return obj(top, 0)


def _xml_value(e):
    kind = e.name
    if kind == "dict":
        out = {}
        key = None
        for c in e.children:
            if c.name == "key":
                key = c.all_text()
            elif key is not None:
                out[key] = _xml_value(c)
                key = None
        return out
    if kind == "array":
        return [_xml_value(c) for c in e.children]
    if kind == "true":
        return True
    if kind == "false":
        return False
    if kind == "integer":
        try:
            return int(e.all_text().strip())
        except ValueError:
            return e.all_text().strip()
    if kind == "real":
        try:
            return float(e.all_text().strip())
        except ValueError:
            return e.all_text().strip()
    if kind == "data":
        import base64
        try:
            return base64.b64decode("".join(e.all_text().split()))
        except ValueError:
            return b""
    if kind == "date":
        return {"$date": e.all_text().strip()}
    return e.all_text()


def parse(data):
    """A property list's top value, binary or XML."""
    if data[:8] == b"bplist00":
        return binary(data)
    from wm.preview import xml
    root = xml(data, max_nodes=100000)
    top = root if root.name == "plist" else root.first("plist")
    if top is None:
        raise ValueError("This is not a property list.")
    kids = top.children
    if not kids:
        return None
    return _xml_value(kids[0])
