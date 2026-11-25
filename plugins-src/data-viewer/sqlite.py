"""Reads SQLite database files: the schema table and the first rows of a
table, by walking the file's b-tree pages. Read-only and forgiving: a page
that does not parse ends the walk rather than the preview.

The format: https://www.sqlite.org/fileformat2.html
"""

HEADER = b"SQLite format 3\x00"
MAX_PAGES = 2000          # pages one walk may visit
MAX_PAYLOAD = 65536       # bytes of one row followed through overflow pages


def _uint(data, at, n):
    """An n-byte big-endian unsigned integer."""
    v = 0
    for i in range(n):
        v = v * 256 + data[at + i]
    return v


def _int(data, at, n):
    """An n-byte big-endian two's-complement integer; the sign comes from
    the first byte, so an 8-byte one never leaves 64 bits."""
    v = data[at] - 256 if data[at] >= 128 else data[at]
    for i in range(1, n):
        v = v * 256 + data[at + i]
    return v


def varint(data, at):
    """(value, next offset) for SQLite's 1-to-9-byte varint."""
    v = 0
    for i in range(8):
        b = data[at + i]
        v = v * 128 + (b & 0x7F)
        if b < 0x80:
            return v, at + i + 1
    # Nine bytes hold all 64 bits, the top one the sign. The interpreter's
    # integers turn to floats long before 2 ** 64, so a negative one is built
    # from its inverted bits, which keeps a small number small.
    if data[at] & 0x40:
        inv = 0
        for i in range(8):
            inv = inv * 128 + (0x7F - (data[at + i] & 0x7F))
        return -(inv * 256 + (0xFF - data[at + 8]) + 1), at + 9
    return v * 256 + data[at + 8], at + 9


class Database:
    def __init__(self, file):
        self.file = file
        head = file.read(0, 100)
        if len(head) < 100 or head[:16] != HEADER:
            raise ValueError("This is not an SQLite database.")
        size = _uint(head, 16, 2)
        self.page_size = 65536 if size == 1 else size
        if self.page_size < 512 or self.page_size & (self.page_size - 1):
            raise ValueError("This database's page size is not valid.")
        self.usable = self.page_size - head[20]
        self.encoding = _uint(head, 56, 4) or 1
        self.visited = 0
        self.cache = {}

    def page(self, n):
        if n in self.cache:
            return self.cache[n]
        self.visited = self.visited + 1
        if self.visited > MAX_PAGES:
            raise ValueError("This table is too big to read here.")
        data = self.file.read((n - 1) * self.page_size, self.page_size)
        if len(data) < self.page_size:
            raise ValueError(f"Page {n} is past the end of the file.")
        if len(self.cache) < 64:
            self.cache[n] = data
        return data

    def text(self, raw):
        if self.encoding == 1:
            return raw.decode("utf-8", "replace")
        out = []
        i = 0
        little = self.encoding == 2
        while i + 1 < len(raw):
            out.append(chr(raw[i] + raw[i + 1] * 256 if little else raw[i] * 256 + raw[i + 1]))
            i = i + 2
        return "".join(out)

    def _payload(self, page, at, size):
        """The record bytes of a leaf cell at [at], overflow pages included."""
        x = self.usable - 35
        if size <= x:
            return page[at:at + size]
        m = ((self.usable - 12) * 32 // 255) - 23
        k = m + ((size - m) % (self.usable - 4))
        local = k if k <= x else m
        parts = [page[at:at + local]]
        got = local
        nxt = _uint(page, at + local, 4)
        hops = 0
        while nxt and got < min(size, MAX_PAYLOAD) and hops < 64:
            over = self.page(nxt)
            take = min(self.usable - 4, size - got)
            parts.append(over[4:4 + take])
            got = got + take
            nxt = _uint(over, 0, 4)
            hops = hops + 1
        return b"".join(parts)

    def rows(self, root, limit):
        """Up to [limit] rows of the table whose b-tree starts at page [root], in rowid order."""
        out = []
        stack = [root]
        while stack and len(out) < limit:
            n = stack.pop()
            data = self.page(n)
            base = 100 if n == 1 else 0
            kind = data[base]
            cells = _uint(data, base + 3, 2)
            if kind == 0x05:
                right = _uint(data, base + 8, 4)
                children = [_uint(data, _uint(data, base + 12 + 2 * i, 2), 4) for i in range(cells)]
                stack.append(right)
                i = len(children) - 1
                while i >= 0:
                    stack.append(children[i])
                    i = i - 1
            elif kind == 0x0D:
                for i in range(cells):
                    if len(out) >= limit:
                        break
                    at = _uint(data, base + 8 + 2 * i, 2)
                    size, at = varint(data, at)
                    rowid, at = varint(data, at)
                    out.append(self.record(self._payload(data, at, size), rowid))
            else:
                raise ValueError(f"Page {n} is not part of a table.")
        return out

    def record(self, payload, rowid=None):
        header, at = varint(payload, 0)
        types = []
        while at < header:
            t, at = varint(payload, at)
            types.append(t)
        values = []
        at = header
        for t in types:
            if t == 0:
                values.append(None)
            elif 1 <= t <= 6:
                n = (1, 2, 3, 4, 6, 8)[t - 1]
                values.append(_int(payload, at, n) if at + n <= len(payload) else None)
                at = at + n
            elif t == 7:
                from wm import formats
                values.append(formats.unpack(">d", payload, at)[0] if at + 8 <= len(payload) else None)
                at = at + 8
            elif t == 8:
                values.append(0)
            elif t == 9:
                values.append(1)
            elif t >= 12:
                n = (t - 12) // 2
                raw = payload[at:at + n]
                values.append(self.text(raw) if t % 2 else raw)
                at = at + n
            else:
                values.append(None)
        # An INTEGER PRIMARY KEY column is stored as NULL; its value is the rowid.
        if values and values[0] is None and rowid is not None:
            values[0] = rowid
        return values

    def tables(self):
        """The schema table: [{"type", "name", "rootpage", "sql"}]."""
        out = []
        for r in self.rows(1, 500):
            if len(r) < 5:
                continue
            out.append({"type": r[0], "name": r[1], "rootpage": r[3], "sql": r[4]})
        return out


def columns(sql):
    """The column names in a CREATE TABLE statement, best effort."""
    if not sql:
        return []
    start = sql.find("(")
    end = sql.rfind(")")
    if start < 0 or end <= start:
        return []
    body = sql[start + 1:end]
    parts = []
    depth = 0
    cur = []
    for ch in body:
        if ch == "(":
            depth = depth + 1
        elif ch == ")":
            depth = depth - 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    names = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        close = {"\"": "\"", "`": "`", "[": "]", "'": "'"}.get(p[0])
        if close is not None:
            end = p.find(close, 1)
            names.append(p[1:end] if end > 0 else p[1:])
            continue
        word = p.split()[0]
        if word.upper() in ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"):
            continue
        names.append(word)
    return names


def cell(value):
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return f"‹{len(value)} bytes›"
    text = str(value)
    return text if len(text) <= 200 else text[:199] + "…"
