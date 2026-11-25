"""Reads an sfnt font (TrueType, OpenType, a collection, or WOFF 1): its
table directory, the name table, maxp's glyph count and fvar's axes.
https://learn.microsoft.com/typography/opentype/spec/otff"""

NAME_IDS = {0: "Copyright", 1: "Family", 2: "Style", 4: "Full name", 5: "Version", 7: "Trademark",
            8: "Maker", 9: "Designer", 11: "Vendor website", 12: "Designer website", 13: "Licence",
            14: "Licence website", 16: "Typographic family", 17: "Typographic style", 19: "Sample text"}


def u16(d, at):
    return d[at] * 256 + d[at + 1]


def u32(d, at):
    return ((d[at] * 256 + d[at + 1]) * 256 + d[at + 2]) * 256 + d[at + 3]


def fixed(d, at):
    """A 16.16 fixed-point number."""
    whole = u16(d, at)
    if whole >= 32768:
        whole = whole - 65536
    return whole + u16(d, at + 2) / 65536


class Font:
    def __init__(self, data, index=0):
        self.data = data
        self.kind = "TrueType"
        self.count = 1
        self.tables = {}
        tag = data[:4]
        if tag == b"ttcf":
            self.count = u32(data, 8)
            base = u32(data, 12 + 4 * index)
            self.kind = "Collection"
            self._sfnt(base)
        elif tag == b"wOFF":
            self.kind = "WOFF"
            self._woff()
        elif tag == b"wOF2":
            raise ValueError("WOFF 2 fonts are compressed with Brotli, which this viewer cannot open.")
        elif tag in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
            self._sfnt(0)
        else:
            raise ValueError("This is not a font file.")
        if "CFF " in self.tables or "CFF2" in self.tables:
            self.outlines = "PostScript (CFF)"
        elif "glyf" in self.tables:
            self.outlines = "TrueType"
        else:
            self.outlines = "Bitmap"

    def _sfnt(self, base):
        if self.data[base:base + 4] == b"OTTO" and self.kind != "Collection":
            self.kind = "OpenType"
        n = u16(self.data, base + 4)
        for i in range(min(n, 200)):
            rec = base + 12 + 16 * i
            tag = self.data[rec:rec + 4].decode("utf-8", "replace")
            self.tables[tag] = (u32(self.data, rec + 8), u32(self.data, rec + 12), False, 0)

    def _woff(self):
        n = u16(self.data, 12)
        for i in range(min(n, 200)):
            rec = 44 + 20 * i
            tag = self.data[rec:rec + 4].decode("utf-8", "replace")
            offset, comp, orig = u32(self.data, rec + 4), u32(self.data, rec + 8), u32(self.data, rec + 12)
            self.tables[tag] = (offset, comp, comp < orig, orig)

    def table(self, tag):
        found = self.tables.get(tag)
        if found is None:
            return None
        offset, length, packed, orig = found
        raw = self.data[offset:offset + length]
        if packed:
            from wm.preview import inflate
            return inflate(raw, max=orig + 16)
        return raw

    def names(self):
        """{name id: text}, preferring Windows English, then any Windows, then Mac Roman."""
        d = self.table("name")
        out = {}
        if d is None or len(d) < 6:
            return out
        count = u16(d, 2)
        strings = u16(d, 4)
        best = {}
        for i in range(min(count, 2000)):
            rec = 6 + 12 * i
            if rec + 12 > len(d):
                break
            platform, encoding, language, nid = u16(d, rec), u16(d, rec + 2), u16(d, rec + 4), u16(d, rec + 6)
            length, offset = u16(d, rec + 8), u16(d, rec + 10)
            if nid not in NAME_IDS:
                continue
            raw = d[strings + offset:strings + offset + length]
            if platform == 3 or platform == 0:
                rank = 3 if (platform == 3 and language == 0x409) else 2
                chars = []
                j = 0
                while j + 1 < len(raw):
                    chars.append(chr(raw[j] * 256 + raw[j + 1]))
                    j = j + 2
                text = "".join(chars)
            elif platform == 1 and encoding == 0:
                rank = 1
                text = "".join(chr(b) for b in raw)
            else:
                continue
            if rank > best.get(nid, 0) and text.strip():
                best[nid] = rank
                out[nid] = text.strip()
        return out

    def glyphs(self):
        d = self.table("maxp")
        return u16(d, 4) if d is not None and len(d) >= 6 else None

    def axes(self):
        """[(tag, min, default, max, name id)] of a variable font."""
        d = self.table("fvar")
        if d is None or len(d) < 16:
            return []
        start = u16(d, 4)
        count = u16(d, 8)
        size = u16(d, 10)
        out = []
        for i in range(min(count, 64)):
            at = start + i * size
            if at + 20 > len(d):
                break
            out.append((d[at:at + 4].decode("utf-8", "replace"), fixed(d, at + 4), fixed(d, at + 8), fixed(d, at + 12), u16(d, at + 18)))
        return out
