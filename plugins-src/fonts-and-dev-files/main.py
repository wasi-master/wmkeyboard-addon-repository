# Fonts and Dev Files: fonts drawn in their own face, X.509 certificates,
# .torrent files and Apple property lists.

import json

from wm import plugin, ui, formats

import fonts
import plist
import x509

SAMPLE = "The quick brown fox jumps over the lazy dog 0123456789"


# MARK: - fonts

@plugin.preview("font")
def show_font(file):
    try:
        font = fonts.Font(file.data)
    except ValueError as error:
        ui.empty(str(error))
        return
    names = font.names()
    family = names.get(16) or names.get(1) or file.name
    style = names.get(17) or names.get(2) or ""
    ui.label(family, style="headline")
    if style:
        ui.label(style, style="title")
    if font.kind != "WOFF":
        ui.font_sample(names.get(19) or SAMPLE, sizes=[14, 22, 36])
    rows = []
    for nid, label in ((4, "Full name"), (5, "Version"), (8, "Maker"), (9, "Designer"), (12, "Designer website"),
                       (0, "Copyright"), (7, "Trademark"), (13, "Licence"), (14, "Licence website")):
        if nid in names:
            value = names[nid]
            rows.append([label, value if len(value) <= 600 else value[:599] + "…"])
    glyphs = font.glyphs()
    if glyphs is not None:
        rows.append(["Glyphs", f"{glyphs:,}"])
    rows.append(["Format", font.kind + (f", {font.count} fonts" if font.count > 1 else "") + " · " + font.outlines + " outlines"])
    ui.table(rows)
    axes = font.axes()
    if axes:
        with ui.section(f"Variable: {len(axes)} axes", collapsible=True):
            ui.table([[tag, _num(lo), _num(mid), _num(hi)] for tag, lo, mid, hi, nid in axes],
                     header=["Axis", "Least", "Default", "Most"], align=["start", "end", "end", "end"])
    ui.caption("Tables: " + ", ".join(sorted(t.strip() for t in font.tables.keys())))


def _num(x):
    return str(int(x)) if x == int(x) else f"{x:.2f}"


# MARK: - certificates

def _show_certificate(c, open_):
    title = c["subject_cn"] or c["subject"] or "Certificate"
    with ui.section(title, collapsible=True, open=open_):
        rows = [["Issued to", c["subject"]], ["Issued by", "Itself" if c["self_signed"] else c["issuer"]],
                ["Valid from", c["from"]], ["Valid until", c["until"]], ["Key", c["key"]],
                ["Signature", c["signature"]], ["Serial", c["serial"]], ["Version", str(c["version"])]]
        if c["ca"]:
            rows.append(["Authority", "Can sign other certificates"])
        ui.table(rows)
        if c["alt"]:
            ui.label("Also for: " + ", ".join(c["alt"][:40]) + (f" and {len(c['alt']) - 40} more" if len(c["alt"]) > 40 else ""))
        ui.output("SHA-256  " + c["sha256"], mono=True, insertable=False)
        ui.output("SHA-1  " + c["sha1"], mono=True, insertable=False)


@plugin.preview("cert")
def show_cert(file):
    data = file.data
    if data.startswith(b"ssh-") or data.startswith(b"ecdsa-"):
        bits = data.decode("utf-8", "replace").split()
        ui.label("SSH public key", style="title")
        ui.table([["Type", bits[0]], ["Comment", " ".join(bits[2:]) if len(bits) > 2 else ""]])
        return
    text = data.decode("utf-8", "replace") if data.find(b"-----BEGIN ") >= 0 else ""
    blocks = x509.pem_blocks(text) if text else [("CERTIFICATE", data)]
    if not blocks:
        ui.empty("No certificate or key was found in this file.")
        return
    certs = [b for b in blocks if b[0] in ("CERTIFICATE", "X509 CERTIFICATE", "TRUSTED CERTIFICATE")]
    if len(certs) > 1:
        ui.caption(f"{len(certs)} certificates")
    shown = 0
    for label, der in blocks[:30]:
        if label in ("CERTIFICATE", "X509 CERTIFICATE", "TRUSTED CERTIFICATE"):
            try:
                _show_certificate(x509.certificate(der), shown == 0)
            except (ValueError, IndexError):
                ui.caption("A certificate here could not be read.")
            shown = shown + 1
        elif label in ("CERTIFICATE REQUEST", "NEW CERTIFICATE REQUEST"):
            try:
                r = x509.request(der)
                with ui.section("Certificate request", collapsible=True, open=shown == 0):
                    ui.table([["Subject", r["subject"]], ["Key", r["key"]]])
            except (ValueError, IndexError):
                ui.caption("The certificate request could not be read.")
            shown = shown + 1
        elif "PRIVATE KEY" in label:
            # Never shown: only what kind of key the file holds.
            kind = label.replace("PRIVATE KEY", "").strip() or "PKCS #8"
            ui.item("Private key", subtitle=f"{kind} · keep this file secret", icon="key")
            shown = shown + 1
        elif "PUBLIC KEY" in label:
            ui.item("Public key", subtitle=label.title(), icon="key")
            shown = shown + 1
        else:
            ui.item(label.title(), subtitle=f"{len(der)} bytes", icon="description")


# MARK: - torrents

def _skip(d, at):
    """Where the bencoded value at [at] ends."""
    c = d[at]
    if c == 105:
        return d.find(b"e", at) + 1
    if c in (108, 100):
        at = at + 1
        while d[at] != 101:
            at = _skip(d, at)
        return at + 1
    colon = d.find(b":", at)
    return colon + 1 + int(d[at:colon].decode())


def info_hash(d):
    """The SHA-1 of the bencoded info dictionary: the torrent's identity."""
    import hashlib
    at = 1
    while at < len(d) and d[at] != 101:
        colon = d.find(b":", at)
        n = int(d[at:colon].decode())
        key = d[colon + 1:colon + 1 + n]
        at = colon + 1 + n
        end = _skip(d, at)
        if key == b"info":
            return hashlib.sha1(d[at:end]).hexdigest()
        at = end
    return None


def _date(seconds):
    """A Unix time as YYYY-MM-DD (UTC): Howard Hinnant's civil_from_days."""
    z = seconds // 86400 + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    y = yoe + era * 400 + (1 if m <= 2 else 0)
    return f"{y}-{m:02d}-{d:02d}"


def _size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n = n / 1024


def _s(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


@plugin.preview("torrent")
def show_torrent(file):
    try:
        t = formats.bencode(file.data)
    except (ValueError, IndexError):
        ui.empty("This is not a torrent file.")
        return
    if not isinstance(t, dict) or not isinstance(t.get("info"), dict):
        ui.empty("This is not a torrent file.")
        return
    info = t["info"]
    name = _s(info.get("name.utf-8", info.get("name", file.name)))
    ui.label(name, style="headline")
    files = []
    if "files" in info:
        for f in info["files"]:
            path = f.get("path.utf-8", f.get("path", []))
            files.append(("/".join(_s(p) for p in path), f.get("length", 0)))
    else:
        files.append((name, info.get("length", 0)))
    total = sum(n for p, n in files)
    rows = [["Size", _size(total)], ["Files", f"{len(files):,}"], ["Pieces", f"{_size(info.get('piece length', 0))} each"]]
    digest = info_hash(file.data)
    if digest:
        rows.append(["Info hash", digest])
    if isinstance(t.get("creation date"), int):
        rows.append(["Created", _date(t["creation date"])])
    for key, label in (("created by", "Made with"), ("comment", "Comment")):
        if key in t:
            rows.append([label, _s(t[key])])
    if info.get("private") == 1:
        rows.append(["Private", "Only its own trackers"])
    ui.table(rows)
    if digest:
        ui.output("magnet:?xt=urn:btih:" + digest + "&dn=" + name.replace(" ", "+"), mono=True)
    with ui.section(f"{len(files)} file" + ("" if len(files) == 1 else "s"), collapsible=True, open=len(files) <= 50):
        ui.table([[p, _size(n)] for p, n in files[:500]], header=["File", "Size"], align=["start", "end"])
    trackers = []
    if "announce" in t:
        trackers.append(_s(t["announce"]))
    for tier in t.get("announce-list", []):
        for url in tier:
            if _s(url) not in trackers:
                trackers.append(_s(url))
    if trackers:
        with ui.section(f"{len(trackers)} trackers", collapsible=True, open=False):
            for url in trackers[:100]:
                ui.label(url)


# MARK: - property lists

def _plain(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, bytes):
        return f"‹{len(v)} bytes›"
    if isinstance(v, dict) and len(v) == 1 and ("$date" in v or "$uid" in v):
        return str(list(v.values())[0])
    return str(v)


def _leaf(v):
    return not isinstance(v, (dict, list)) or (isinstance(v, dict) and len(v) == 1 and ("$date" in v or "$uid" in v))


def show_plist_value(v, depth, budget):
    budget[0] = budget[0] - 1
    if budget[0] <= 0:
        return
    if isinstance(v, dict):
        leaves = [[k, _plain(x)] for k, x in v.items() if _leaf(x)]
        if leaves:
            ui.table(leaves[:300], header=["Key", "Value"])
        for k, x in v.items():
            if not _leaf(x):
                with ui.section(f"{k} · {len(x)}", collapsible=True, open=depth == 0):
                    show_plist_value(x, depth + 1, budget)
    elif isinstance(v, list):
        if all(_leaf(x) for x in v):
            ui.table([[str(i), _plain(x)] for i, x in enumerate(v[:300])], header=["#", "Value"])
        else:
            for i, x in enumerate(v[:100]):
                with ui.section(f"[{i}]", collapsible=True, open=False):
                    show_plist_value(x, depth + 1, budget)
    else:
        ui.output(_plain(v), mono=True)


def strings_file(text):
    """A .strings file: "key" = "value"; pairs."""
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if not s.startswith("\""):
            continue
        end = s.find("\"", 1)
        eq = s.find("=", end)
        if end < 0 or eq < 0:
            continue
        value = s[eq + 1:].strip().rstrip(";").strip()
        out.append([s[1:end], value[1:-1] if value.startswith("\"") and value.endswith("\"") else value])
    return out


@plugin.preview("plist")
def show_plist(file):
    if file.extension == "strings" and not file.data.startswith(b"bplist00"):
        pairs = strings_file(file.text())
        if pairs:
            ui.caption(f"{len(pairs)} strings")
            ui.table(pairs[:500], header=["Key", "Text"])
            return
    try:
        value = plist.parse(file.data)
    except (ValueError, IndexError) as error:
        ui.empty(str(error) or "This property list could not be read.")
        return
    if file.extension == "webloc" and isinstance(value, dict) and "URL" in value:
        ui.label("Link", style="title")
        ui.output(str(value["URL"]))
        return
    ui.caption("Binary property list" if file.data.startswith(b"bplist00") else "Property list")
    show_plist_value(value, 0, [1500])
