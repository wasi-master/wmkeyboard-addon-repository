# Tests for Fonts and Dev Files, run by tools/test_plugins.py under
# wm-python-cli. tests/ holds a tiny variable font (and its WOFF), certificates
# made with openssl, a hand-built torrent and property lists from plistlib.
# site.key is a stand-in: its body is not a real key.

import json


def shown(preview, name):
    r = plugin_test.preview(preview, "tests/" + name)
    assert r["ok"], name + ": " + json.dumps(r.get("error"))
    return r["ui"]["root"]


def words(tree):
    """Every string in the widget tree, in order, one per line."""
    out = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            out.append(n)
        elif isinstance(n, list):
            stack.extend(reversed(n))
        elif isinstance(n, dict):
            stack.extend(reversed([v for k, v in n.items() if k != "type"]))
    return "\n".join(out)


def find(tree, kind):
    found = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, list):
            stack.extend(reversed(n))
        elif isinstance(n, dict):
            if n.get("type") == kind:
                found.append(n)
            stack.extend(reversed(list(n.values())))
    return found


def has(text, *needles):
    for needle in needles:
        assert needle in text, "missing " + json.dumps(needle) + " in:\n" + text


# MARK: - fonts

root = shown("font", "tiny.ttf")
text = words(root)
has(text, "Tiny Sans", "Regular", "Version 1.002", "Small Foundry", "Ayesha Karim", "SIL Open Font License 1.1",
    "Glyphs", "TrueType · TrueType outlines", "Variable: 2 axes", "fvar", "glyf")
assert find(root, "font_sample"), "the font drawn in its own face"
axes = [t for t in find(root, "table") if t.get("header") == ["Axis", "Least", "Default", "Most"]][0]
assert axes["rows"] == [["wght", "100", "400", "900"], ["wdth", "75", "100", "125.50"]], axes["rows"]

root = shown("font", "tiny.woff")
has(words(root), "Tiny Sans", "WOFF · TrueType outlines")
assert not find(root, "font_sample"), "Android cannot draw a WOFF"

has(words(shown("font", "not-a-font.ttf")), "This is not a font file.")

# MARK: - certificates

root = shown("cert", "site.pem")
text = words(root)
has(text, "example.com", "C=BD, O=Example Ltd, CN=example.com", "Itself", "Valid from", "2026-11-25", "Valid until", "2027-11-25",
    "RSA 2048-bit", "SHA-256 with RSA", "12:34", "Also for: example.com, www.example.com, 10.0.0.1",
    "SHA-256  90:1B:BA:64:A3:B0:72:B9:C4:01:EF:01:F5:65:34:D1:2E:69:58:37:C9:E8:4E:87:36:47:2A:31:14:F1:F7:34")

text = words(shown("cert", "site.der"))
has(text, "SHA-256  90:1B:BA:64", "RSA 2048-bit")

text = words(shown("cert", "chain.pem"))
has(text, "2 certificates", "EC Root", "EC P-256", "ECDSA with SHA-256", "Can sign other certificates",
    "SHA-1  AD:72:CA:71:D3:B6:CE:93:76:4A:63:81:0E:31:D2:5F:8D:0D:FF:DA")

has(words(shown("cert", "site.csr")), "Certificate request", "CN=req.example.com", "RSA 2048-bit")
text = words(shown("cert", "site.key"))
has(text, "Private key", "keep this file secret")
assert "AAAA" not in text, "a key's body is never shown"
has(words(shown("cert", "id.pub")), "SSH public key", "ssh-ed25519", "ann@laptop")

# MARK: - torrents

root = shown("torrent", "photos.torrent")
text = words(root)
has(text, "Holiday photos", "1.0 MB", "Files", "2", "256.0 KB each", "7e2485c88c8a6490083c37f6a548a2f6255050a6",
    "2026-03-04", "Tool 1.0", "Shared with family", "day1/beach.jpg", "notes.txt", "2.0 KB",
    "magnet:?xt=urn:btih:7e2485c88c8a6490083c37f6a548a2f6255050a6&dn=Holiday+photos",
    "2 trackers", "udp://tracker.example:80", "https://t2.example/announce")

# MARK: - property lists

for name in ("Info.plist", "Binary.plist"):
    root = shown("plist", name)
    text = words(root)
    has(text, "CFBundleName", "Demo", "LSRequiresIPhoneOS", "true", "Count", "-3", "‹3 bytes›", "UIDeviceFamily · 2", "Nested · 1", "1.5")
has(words(shown("plist", "Binary.plist")), "Binary property list")
has(words(shown("plist", "Link.webloc")), "https://example.com/page")
root = shown("plist", "Localizable.strings")
assert find(root, "table")[0]["rows"] == [["hello", "Hola"], ["bye", "Adiós"]]
