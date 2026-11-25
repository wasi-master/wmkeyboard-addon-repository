"""Reads X.509 certificates, certificate requests and the PEM blocks they
come in: a small DER walker, enough for names, dates, keys and the
subjectAltName extension. RFC 5280."""

OIDS = {
    "2.5.4.3": "CN", "2.5.4.6": "C", "2.5.4.7": "L", "2.5.4.8": "ST", "2.5.4.10": "O", "2.5.4.11": "OU",
    "2.5.4.5": "serialNumber", "1.2.840.113549.1.9.1": "emailAddress", "0.9.2342.19200300.100.1.25": "DC",
    "1.2.840.113549.1.1.1": "RSA", "1.2.840.10045.2.1": "EC", "1.3.101.112": "Ed25519", "1.3.101.113": "Ed448",
    "1.2.840.113549.1.1.5": "SHA-1 with RSA", "1.2.840.113549.1.1.11": "SHA-256 with RSA",
    "1.2.840.113549.1.1.12": "SHA-384 with RSA", "1.2.840.113549.1.1.13": "SHA-512 with RSA",
    "1.2.840.113549.1.1.10": "RSA-PSS", "1.2.840.10045.4.3.2": "ECDSA with SHA-256",
    "1.2.840.10045.4.3.3": "ECDSA with SHA-384", "1.2.840.10045.4.3.4": "ECDSA with SHA-512",
    "1.2.840.10045.3.1.7": "P-256", "1.3.132.0.34": "P-384", "1.3.132.0.35": "P-521",
    "2.5.29.17": "subjectAltName", "2.5.29.19": "basicConstraints", "2.5.29.15": "keyUsage",
}


def read(d, at):
    """(tag, value start, value end) of the TLV at [at]."""
    tag = d[at]
    n = d[at + 1]
    at = at + 2
    if n >= 0x80:
        count = n - 0x80
        if count == 0 or count > 4:
            raise ValueError("This DER length is not supported.")
        n = 0
        for i in range(count):
            n = n * 256 + d[at + i]
        at = at + count
    if at + n > len(d):
        raise ValueError("The certificate is cut short.")
    return tag, at, at + n


def children(d, start, end):
    out = []
    at = start
    while at < end:
        tag, s, e = read(d, at)
        out.append((tag, s, e))
        at = e
    return out


def oid(d, s, e):
    first = d[s]
    parts = [str(first // 40), str(first % 40)]
    v = 0
    for b in d[s + 1:e]:
        v = v * 128 + (b & 0x7F)
        if b < 0x80:
            parts.append(str(v))
            v = 0
    return ".".join(parts)


def text(d, tag, s, e):
    raw = d[s:e]
    if tag == 0x1E:  # BMPString
        return "".join(chr(raw[i] * 256 + raw[i + 1]) for i in range(0, len(raw) - 1, 2))
    return raw.decode("utf-8", "replace")


def name(d, s, e):
    """A Name as "CN=example.com, O=Example, C=US" and its common name."""
    parts = []
    common = ""
    for _, rs, re_ in children(d, s, e):
        for _, as_, ae in children(d, rs, re_):
            pair = children(d, as_, ae)
            key = oid(d, pair[0][1], pair[0][2])
            value = text(d, pair[1][0], pair[1][1], pair[1][2])
            label = OIDS.get(key, key)
            parts.append(f"{label}={value}")
            if label == "CN" and not common:
                common = value
    return ", ".join(parts), common


def when(d, tag, s, e):
    raw = d[s:e].decode("utf-8", "replace")
    if tag == 0x17:  # UTCTime, YYMMDDHHMMSSZ
        year = int(raw[:2])
        raw = ("19" if year >= 50 else "20") + raw
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {raw[8:10]}:{raw[10:12]} UTC"


def hexed(b, sep=":"):
    h = b.hex().upper()
    return sep.join(h[i:i + 2] for i in range(0, len(h), 2))


def _key(d, s, e):
    """A SubjectPublicKeyInfo as "RSA 2048-bit" or "EC P-256"."""
    algo, bits = children(d, s, e)[:2]
    parts = children(d, algo[1], algo[2])
    kind = OIDS.get(oid(d, parts[0][1], parts[0][2]), "unknown")
    if kind == "RSA":
        try:
            seq = children(d, bits[1] + 1, bits[2])[0]
            modulus = children(d, seq[1], seq[2])[0]
            size = modulus[2] - modulus[1]
            if d[modulus[1]] == 0:
                size = size - 1
            return f"RSA {size * 8}-bit"
        except (ValueError, IndexError):
            return "RSA"
    if kind == "EC" and len(parts) > 1 and parts[1][0] == 0x06:
        return "EC " + OIDS.get(oid(d, parts[1][1], parts[1][2]), "curve")
    return kind


def _alt_names(d, s, e):
    out = []
    seq = children(d, s, e)[0]
    for tag, gs, ge in children(d, seq[1], seq[2]):
        if tag in (0x81, 0x82, 0x86):  # email, DNS, URI
            out.append(d[gs:ge].decode("utf-8", "replace"))
        elif tag == 0x87 and ge - gs == 4:
            out.append(".".join(str(b) for b in d[gs:ge]))
    return out


def certificate(d):
    """The facts of one DER certificate."""
    import hashlib
    tag, s, e = read(d, 0)
    whole = d[0:e]
    tbs, sig_algo = children(d, s, e)[:2]
    fields = children(d, tbs[1], tbs[2])
    i = 0
    version = 1
    if fields[0][0] == 0xA0:
        version = d[fields[0][2] - 1] + 1
        i = 1
    serial = d[fields[i][1]:fields[i][2]]
    issuer, issuer_cn = name(d, fields[i + 2][1], fields[i + 2][2])
    validity = children(d, fields[i + 3][1], fields[i + 3][2])
    subject, subject_cn = name(d, fields[i + 4][1], fields[i + 4][2])
    key = _key(d, fields[i + 5][1], fields[i + 5][2])
    alt = []
    ca = False
    for f in fields[i + 6:]:
        if f[0] != 0xA3:
            continue
        exts = children(d, f[1], f[2])[0]
        for _, xs, xe in children(d, exts[1], exts[2]):
            parts = children(d, xs, xe)
            label = OIDS.get(oid(d, parts[0][1], parts[0][2]), "")
            value = parts[-1]
            if label == "subjectAltName":
                alt = _alt_names(d, value[1], value[2])
            elif label == "basicConstraints":
                inner = children(d, value[1], value[2])
                seq = children(d, inner[0][1], inner[0][2]) if inner else []
                ca = bool(seq) and seq[0][0] == 0x01 and d[seq[0][1]] != 0
    sig = children(d, sig_algo[1], sig_algo[2])[0]
    return {
        "subject": subject, "subject_cn": subject_cn, "issuer": issuer, "issuer_cn": issuer_cn,
        "from": when(d, validity[0][0], validity[0][1], validity[0][2]),
        "until": when(d, validity[1][0], validity[1][1], validity[1][2]),
        "serial": hexed(serial[1:] if len(serial) > 1 and serial[0] == 0 else serial),
        "version": version, "key": key, "signature": OIDS.get(oid(d, sig[1], sig[2]), oid(d, sig[1], sig[2])),
        "alt": alt, "ca": ca, "self_signed": subject == issuer,
        "sha256": hexed(hashlib.sha256(whole).digest()), "sha1": hexed(hashlib.sha1(whole).digest()),
    }


def request(d):
    """A PKCS #10 certificate request's subject and key."""
    tag, s, e = read(d, 0)
    info = children(d, s, e)[0]
    fields = children(d, info[1], info[2])
    subject, cn = name(d, fields[1][1], fields[1][2])
    return {"subject": subject, "subject_cn": cn, "key": _key(d, fields[2][1], fields[2][2])}


def pem_blocks(text):
    """[(label, der bytes)] for each -----BEGIN label----- block."""
    import base64
    out = []
    at = 0
    while True:
        start = text.find("-----BEGIN ", at)
        if start < 0:
            break
        label_end = text.find("-----", start + 11)
        if label_end < 0:
            break
        label = text[start + 11:label_end]
        end = text.find("-----END " + label + "-----", label_end)
        if end < 0:
            break
        body = text[label_end + 5:end]
        lines = [l for l in body.replace("\r", "").split("\n") if l.strip() and ":" not in l]
        try:
            der = base64.b64decode("".join("".join(lines).split()))
        except ValueError:
            der = b""
        out.append((label, der))
        at = end + 1
    return out
