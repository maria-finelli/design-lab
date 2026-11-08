#!/usr/bin/env python3
"""Data Double: a stunt double for production data.

Keeps the shape of the real data (uneven distributions, outliers, missing
values, label lengths, differences in scale) and drops its identity (names,
companies, places, emails, phones, ids, exact dates and values).

    python3 double.py mirror  data.json                   # one step: real data in, its double out

The one-step `mirror` guesses what every field is, makes the double, compares
the shape against the real data and checks for leaks. It saves the guesses as
data.spec.json: correct any field it got wrong and run mirror again.

The steps on their own, for more control:

    python3 double.py scan    data.json                   # shape of every field, plus a starter spec
    python3 double.py make    data.json spec.json         # writes data.double.json + data.mapping.json
    python3 double.py compare data.json data.double.json  # real vs double, field by field
    python3 double.py audit   data.mapping.json out/      # is any real identifier left in the output?
    python3 double.py grow    data.double.json spec.json --times 10   # a heavy dataset

Reads JSON (any shape: a list of records, or a nested document) and CSV, TSV
or PSV. Nested fields are named by path: "address.city", "items[].price",
"readings[]" for a list of numbers. Standard library only, Python 3.8+.

scan, profile and compare never print raw values: text is shown as a mask
("Aaaaa Aaaa 99") so whoever runs the tool (or the AI assistant running it)
can judge each field without reading the data.

`make` writes a mapping file (real -> double). It re-identifies everything:
keep it on your machine, never commit, upload or share it.

The spec format is documented in references/spec.md.
"""

import argparse, copy, csv, io, json, random, re, statistics, sys, unicodedata, uuid
from datetime import datetime, timedelta
from pathlib import Path

DROP = object()
MISSING_MARKERS = {"", "null", "none", "n/a", "na", "nan", "-", "--", "undefined", "nil"}

UNIT_RE = re.compile(r"^(\d{1,3})([A-Z]{1,2})$")
EMAIL_P = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
UUID_P = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
HEX_P = r"\b0x[0-9a-fA-F]{6,}L?\b"
PHONE_P = r"(?<![\w-])(?:\+?\d{1,2}[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?![\w-])"
UNIT_P = r"\b\d{1,3}[A-Z]{1,2}\b"
EMAIL_RE, UUID_RE, HEX_RE, PHONE_RE = (re.compile("^" + p + "$") for p in (EMAIL_P, UUID_P, HEX_P, PHONE_P))
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?$")
EPOCH_RE = re.compile(r"^\d{10}(\d{3})?$")
NUM_RE = re.compile(r"^(?P<pre>[$€£¥₹+~ ]{0,3})(?P<sign>-?)(?P<num>\d[\d,]*(?:\.\d+)?|\.\d+)(?P<suf>\D{0,12})$")
DATE_FORMATS = ["%m/%d/%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%Y/%m/%d", "%d.%m.%Y", "%b %d, %Y", "%d %b %Y"]

FIRST = ["Ada", "Bo", "Cyrus", "Dana", "Eli", "Farah", "Gus", "Hana", "Ines", "Jo", "Kofi", "Lena", "Mateo",
         "Nadia", "Omar", "Pia", "Quinn", "Rosa", "Sami", "Tess", "Uma", "Vik", "Wren", "Yuki", "Zane",
         "Amara", "Bastian", "Caroline", "Desmond", "Evangeline", "Florian", "Genevieve", "Harriet",
         "Ignatius", "Josephine", "Leopold", "Maximilian", "Octavia", "Penelope", "Rafferty", "Seraphina"]
LAST = ["Ng", "Li", "Fox", "Ruiz", "Shah", "Kim", "Okafor", "Brady", "Lindqvist", "Ferreira", "Whitfield",
        "Nwosu", "Herrera", "Castellanos", "Abernathy", "Montgomery", "Vasquez", "Delacroix", "Ishikawa",
        "Oyelaran", "Pemberton", "Rasmussen", "Szymanski", "Thibodeaux", "Vanderberg", "Achterberg"]
WORDS = ["Linden", "Alder", "Marlow", "Juniper", "Harrow", "Calloway", "Wexford", "Bellamy", "Orchard",
         "Fennel", "Ashby", "Brindle", "Cobalt", "Dunmore", "Elm", "Fairhaven", "Glenrock", "Hollis", "Ivy",
         "Kestrel", "Larkspur", "Millbrook", "Northgate", "Oakhurst", "Quarry", "Rowan", "Saltmarsh",
         "Thistle", "Underhill", "Vale", "Westerly", "Yarrow", "Atlas", "Beacon", "Cinder", "Drift", "Ember",
         "Fable", "Granite", "Harbor", "Indigo", "Jasper", "Keystone", "Lumen", "Meridian", "Nimbus", "Onyx",
         "Prism", "Quill", "Ridge", "Summit", "Tidal", "Umber", "Vector", "Willow", "Zephyr", "Ox", "Fir"]
PLACE_TYPES = ["Court", "Terrace", "Avenue", "Place", "Street", "Road", "Lane", "House", "Tower", "Commons",
               "Yards", "Square", "Gardens", "Point", "Station", "Plaza", "Heights", "Annex", "Way", "Row"]
ORG_TYPES = ["LLC", "Group", "Partners", "Holdings", "Co.", "Associates", "Collective", "Industries", "Labs",
             "Trust", "Inc.", "Studio", "Supply", "Management", "Logistics", "Cooperative"]
DOMAINS = ["example.com", "example.org", "example.net"]


# ---------------------------------------------------------------- load / save

def load(path, no_header=False):
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        return json.loads(text), {"type": "json"}
    delim = {".psv": "|", ".tsv": "\t", ".csv": ","}.get(p.suffix.lower())
    if not delim:
        delim = csv.Sniffer().sniff(text[:4000], "|,\t;").delimiter
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    rows = [r for r in rows if r]
    if no_header:
        header = [str(i) for i in range(max(len(r) for r in rows))]
    else:
        header, rows = rows[0], rows[1:]
    return [dict(zip(header, r)) for r in rows], {"type": "csv", "delim": delim, "header": header, "no_header": no_header}


def save(path, doc, fmt):
    p = Path(path)
    if fmt["type"] == "json":
        p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=fmt["delim"])
        if not fmt["no_header"]:
            w.writerow(fmt["header"])
        for r in doc:
            w.writerow([r.get(h, "") for h in fmt["header"]])


def out_path(src, tag):
    p = Path(src)
    stem = p.stem[: -len(".double")] if p.stem.endswith(".double") else p.stem
    return p.with_name(f"{stem}.{tag}{p.suffix}")


# ---------------------------------------------------------------- walking

class Walk:
    """Visits every leaf of a document, naming it by path ("a.b", "items[].price").

    Each object inside a list is a record: `enter`/`leave` fire around it, so
    all dates in one record can move together and keep their durations.
    """

    def __init__(self, leaf, skip=None, enter=None, leave=None, on_list=None):
        self.leaf, self.skip, self.enter, self.leave, self.on_list = leaf, skip, enter, leave, on_list

    def run(self, doc):
        if isinstance(doc, list):  # a top-level list is a list of records named from the root
            if self.on_list:
                self.on_list("", len(doc))
            out = [self.node(r, "", record=isinstance(r, dict)) for r in doc]
            return [r for r in out if r is not DROP]
        return self.node(doc, "", record=True)

    def node(self, v, sig, record=False):
        if isinstance(v, dict):
            if record and self.enter:
                self.enter()
            out = {}
            for k, child in v.items():
                cs = f"{sig}.{k}" if sig else str(k)
                if self.skip and self.skip(cs):
                    continue
                r = self.node(child, cs)
                if r is not DROP:
                    out[k] = r
            if record and self.leave:
                self.leave()
            return out
        if isinstance(v, list):
            if self.on_list:
                self.on_list(sig + "[]", len(v))
            out = [self.node(x, sig + "[]", record=isinstance(x, dict)) for x in v]
            return [x for x in out if x is not DROP]
        return self.leaf(sig, v)


def collect(doc):
    """All leaf values by path, plus list lengths by path."""
    values, lists = {}, {}

    def leaf(sig, v):
        values.setdefault(sig, []).append(v)
        return v

    Walk(leaf, on_list=lambda s, n: lists.setdefault(s, []).append(n)).run(doc)
    return values, lists


def is_missing(v):
    return v is None or (isinstance(v, str) and v.strip().lower() in MISSING_MARKERS)


def mask(v, n=36):
    s = str(v)
    out = re.sub(r"[A-Z]", "A", re.sub(r"[a-z]", "a", re.sub(r"\d", "9", s)))
    out = "".join("a" if (c.isalpha() and c not in "Aa") else c for c in out)
    return out if len(out) <= n else out[:n] + "..."


def ascii_fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


# ---------------------------------------------------------------- the doubler

class Doubler:
    IDENTITY = ("unit", "id", "hex", "uuid", "place", "org", "person", "label", "email", "phone")

    def __init__(self, spec):
        self.spec = spec
        self.fields = {k: (dict(v) if isinstance(v, dict) else {"kind": v}) for k, v in spec.get("fields", {}).items()}
        self.rng = random.Random(spec["seed"])
        self.maps, self.used, self.domains = {}, {}, {}
        self.floor_map, self.letter_map = {}, {}
        self.offsets = []
        self.text_units = spec.get("text_units", False)
        self._rx = None

    # -- config
    def conf(self, sig):
        c = self.fields.get(sig)
        if c is None and sig.endswith("[]"):
            c = self.fields.get(sig[:-2])
        return c or {"kind": "keep"}

    def kind(self, sig):
        return self.conf(sig).get("kind", "keep")

    # -- dates move per record
    def enter(self):
        h = self.spec.get("record_jitter_hours", 12)
        self.offsets.append(timedelta(weeks=self.spec["shift_weeks"], hours=self.rng.uniform(-h, h)))

    def leave(self):
        self.offsets.pop()

    def offset(self):
        return self.offsets[-1] if self.offsets else timedelta(weeks=self.spec["shift_weeks"])

    # -- memory: the same real value always gets the same double
    def remember(self, kind, real, make):
        m = self.maps.setdefault(kind, {})
        if real not in m:
            used = self.used.setdefault(kind, set())
            for _ in range(50):
                d = make()
                if d not in used and d != real:
                    break
            else:
                d = f"{make()} {len(used) + 2}"
            used.add(d)
            m[real] = d
        return m[real]

    # -- units: floors and letters are permuted, so the set keeps its floors,
    #    its letters per floor and its count
    def plan_units(self, doc):
        floors, letters = set(), set()

        def leaf(sig, v):
            k = self.kind(sig)
            if isinstance(v, str):
                found = [v.strip()] if k == "unit" else re.findall(UNIT_P, v) if (k == "text" and self.text_units) else []
                for u in found:
                    m = UNIT_RE.match(u)
                    if m:
                        floors.add(m.group(1)); letters.add(m.group(2))
            return v

        Walk(leaf).run(doc)
        fl, lt = sorted(floors, key=int), sorted(letters)
        sf, sl = fl[:], lt[:]
        self.rng.shuffle(sf); self.rng.shuffle(sl)
        self.floor_map, self.letter_map = dict(zip(fl, sf)), dict(zip(lt, sl))

    def unit(self, v):
        m = UNIT_RE.match(v.strip())
        if not m or m.group(1) not in self.floor_map:
            return self.ident(v)
        return self.remember("unit", v, lambda: self.floor_map[m.group(1)] + self.letter_map[m.group(2)])

    # -- format-preserving identifiers
    def ident(self, v):
        r = self.rng

        def make():
            return "".join(r.choice("0123456789") if c.isdigit() else
                           r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") if c.isupper() else
                           r.choice("abcdefghjkmnpqrstuvwxyz") if c.islower() else c for c in v)
        return self.remember("id", v, make)

    def hexid(self, v):
        body, suffix = v[2:].rstrip("L"), ("L" if v.endswith("L") else "")
        digits = "0123456789ABCDEF" if body.isupper() else "0123456789abcdef"
        return self.remember("hex", v, lambda: "0x" + "".join(self.rng.choice(digits) for _ in body) + suffix)

    def uuid_(self, v):
        def make():
            u = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
            return u.upper() if v.isupper() else u
        return self.remember("uuid", v, make)

    # -- names: length-matched, so truncation and wrapping behave like the real thing
    def candidate(self, kind, real):
        r, words = self.rng, real.split()
        fresh = lambda used: r.choice([w for w in WORDS if w not in used] or WORDS)  # no "Linden Linden"
        many = lambda n: r.sample(WORDS, min(n, len(WORDS)))
        if kind == "person":
            parts = [r.choice(FIRST)] + [r.choice(FIRST)[0] + "." for _ in range(max(0, len(words) - 2))] + [r.choice(LAST)]
            extra = lambda p: p[:-1] + [p[-1] + "-" + r.choice([x for x in LAST if x not in p[-1]])]
        elif kind == "place":
            lead = [str(r.randint(10 ** (len(words[0]) - 1), 10 ** len(words[0]) - 1))] if words and words[0].isdigit() else []
            parts = lead + many(max(1, len(words) - len(lead) - 1)) + [r.choice(PLACE_TYPES)]
            extra = lambda p: p[:-1] + [fresh(p), p[-1]]
        elif kind == "org":
            parts = many(max(1, len(words) - 1)) + [r.choice(ORG_TYPES)]
            extra = lambda p: [fresh(p)] + p
        else:  # label
            parts = many(max(1, len(words)))
            extra = lambda p: p + [fresh(p)]
        for _ in range(10):
            if len(" ".join(parts)) >= len(real) - 2:
                break
            parts = extra(parts)
        return " ".join(parts)

    def named(self, kind, real):
        def make():
            used = self.used.get(kind, set())
            pool = [self.candidate(kind, real) for _ in range(40)]
            pool = [c for c in pool if c not in used] or pool
            best = min(pool, key=lambda c: (abs(len(c) - len(real)), self.rng.random()))
            return best.upper() if real.isupper() else best.lower() if real.islower() else best
        return self.remember(kind, real, make)

    def email(self, v):
        def make():
            local, _, domain = v.rpartition("@")
            dkey = domain.lower()
            if dkey not in self.domains:
                # RFC 2606 / 6761 reserve example.com/.org/.net and the .example and .test TLDs: never a real inbox
                taken = set(self.domains.values())
                pool = [d for d in DOMAINS + [f"{w.lower()}.{t}" for w in WORDS for t in ("test", "example")] if d not in taken]
                self.domains[dkey] = min(pool, key=lambda c: (abs(len(c) - len(dkey)), self.rng.random())) if pool else f"site{len(taken)}.test"
            def local_part():
                first, last = ascii_fold(self.rng.choice(FIRST)).lower(), ascii_fold(self.rng.choice(LAST)).lower()
                if "." in local: return f"{first}.{last}"
                if "_" in local: return f"{first}_{last}"
                if re.search(r"\d", local): return f"{first}{self.rng.randint(1, 99)}"
                return self.rng.choice([first, f"{first[0]}{last}", last])
            lp = min((local_part() for _ in range(30)), key=lambda c: (abs(len(c) - len(local)), self.rng.random()))
            return f"{lp}@{self.domains[dkey]}"
        return self.remember("email", v, make)

    def phone(self, v):
        def make():
            d = re.findall(r"\d", v)
            new = [self.rng.choice("0123456789") for _ in d]
            if len(d) >= 10:  # NANP fictional range: area code + 555-01xx
                tail = [str(self.rng.randint(2, 9))] + [self.rng.choice("0123456789") for _ in range(2)] + list("55501") + [self.rng.choice("0123456789") for _ in range(2)]
                new = d[: len(d) - 10] + tail
            it = iter(new)
            return re.sub(r"\d", lambda _: next(it), v)
        return self.remember("phone", v, make)

    # -- values: one scale for the dataset, then a little jitter per value
    def number(self, v, c):
        if isinstance(v, bool):
            return v
        scale = c.get("scale", self.spec["scale"])
        jit = c.get("jitter", self.spec.get("jitter", 0.08))
        factor = scale * (1 + self.rng.uniform(-jit, jit))

        def clamp(x):
            if "min" in c: x = max(c["min"], x)
            if "max" in c: x = min(c["max"], x)
            return x

        if isinstance(v, (int, float)):
            out = clamp(v * factor)
            if isinstance(v, int):
                return int(round(out))
            s = repr(v)
            dec = min(len(s.split(".")[1]), 6) if "." in s and "e" not in s else 6
            return round(out, dec)
        m = NUM_RE.match(v.strip())
        if not m:
            return v
        num = m["num"].replace(",", "")
        n = float(num) * (-1 if m["sign"] else 1)
        out = clamp(n * factor)
        dec = len(num.split(".")[1]) if "." in num else 0
        body = f"{abs(out):,.{dec}f}" if "," in m["num"] else f"{abs(out):.{dec}f}"
        return m["pre"] + ("-" if out < 0 else "") + body + m["suf"]

    def date(self, v, offset):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)) or (isinstance(v, str) and EPOCH_RE.match(v.strip())):
            n = float(v)
            out = n + offset.total_seconds() * (1000 if n > 1e11 else 1)
            return str(int(out)) if isinstance(v, str) else int(out) if isinstance(v, int) else out
        s = v.strip()
        if ISO_RE.match(s):
            z = s.endswith("Z")
            d = datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T") if len(s) > 10 else s) + offset
            if len(s) == 10:
                return d.date().isoformat()
            out = d.isoformat() if "." in s else d.replace(microsecond=0).isoformat()
            if z:
                out = out.replace("+00:00", "Z")
            if "T" not in s:
                out = out.replace("T", " ", 1)
            return out
        for fmt in DATE_FORMATS:
            try:
                d = datetime.strptime(s, fmt)
            except ValueError:
                continue
            return (d + offset).strftime(fmt)
        return v

    # -- pass 1: every field except free text
    def leaf1(self, sig, v):
        c = self.conf(sig)
        k = c.get("kind", "keep")
        if k == "drop":
            return DROP
        if k in ("keep", "text") or is_missing(v):
            return v
        if k == "number": return self.number(v, c)
        if k == "date": return self.date(v, self.offset())
        s = str(v)
        if k == "unit": out = self.unit(s)
        elif k == "id": out = self.ident(s)
        elif k == "hex": out = self.hexid(s)
        elif k == "uuid": out = self.uuid_(s)
        elif k in ("place", "org", "person", "label"): out = self.named(k, s)
        elif k == "email": out = self.email(s)
        elif k == "phone": out = self.phone(s)
        else:
            sys.exit(f"unknown kind {k!r} for field {sig!r}")
        if isinstance(v, int) and not isinstance(v, bool) and out.isdigit():
            return int(out)
        return out

    # -- pass 2: free text, where every value mapped in pass 1 is replaced too
    def text_rx(self):
        if self._rx is None:
            self.known = {}
            for kind, m in self.maps.items():
                if kind == "unit" and not self.text_units:
                    continue
                for real, dbl in m.items():
                    if len(real) >= 3:
                        self.known[real] = dbl
                        self.known.setdefault(real.upper(), dbl.upper())
                        self.known.setdefault(real.lower(), dbl.lower())
            parts = []
            if self.known:
                alts = "|".join(re.escape(k) for k in sorted(self.known, key=len, reverse=True))
                parts.append(rf"(?P<known>(?<!\w)(?:{alts})(?!\w))")
            parts += [rf"(?P<email>{EMAIL_P})", rf"(?P<uuid>{UUID_P})", rf"(?P<hex>{HEX_P})", rf"(?P<phone>{PHONE_P})"]
            if self.text_units:
                parts.append(rf"(?P<unit>{UNIT_P})")
            self._rx = re.compile("|".join(parts))
        return self._rx

    def leaf2(self, sig, v):
        if self.kind(sig) != "text" or not isinstance(v, str) or is_missing(v):
            return v
        handlers = {"known": lambda s: self.known[s], "email": self.email, "uuid": self.uuid_,
                    "hex": self.hexid, "phone": self.phone, "unit": self.unit}
        return self.text_rx().sub(lambda m: handlers[m.lastgroup](m.group(0)), v)

    def make(self, doc):
        # terms: real strings that aren't a field of their own (a customer named only in notes)
        for real, kind in self.spec.get("terms", {}).items():
            self.fields["__term__"] = {"kind": kind}
            self.leaf1("__term__", real)
        self.fields.pop("__term__", None)
        self.plan_units(doc)
        out = Walk(self.leaf1, skip=lambda s: self.kind(s) == "drop", enter=self.enter, leave=self.leave).run(doc)
        return Walk(self.leaf2).run(out)


# ---------------------------------------------------------------- scan

def guess(sig, vals):
    name = sig.replace("[]", "").split(".")[-1].lower() if sig else "value"
    present = [v for v in vals if not is_missing(v)]
    s = [str(v) for v in present][:1000]
    if not s:
        return "keep", "always empty"
    if all(isinstance(v, bool) for v in present):
        return "keep", "true/false"
    distinct = len(set(s))
    has = lambda pat: re.search(pat, name)
    if all(UUID_RE.match(x) for x in s): return "uuid", "UUIDs"
    if all(HEX_RE.match(x) for x in s): return "hex", "hex serials"
    if all(EMAIL_RE.match(x) for x in s): return "email", "emails"
    if all(ISO_RE.match(x) for x in s): return "date", "ISO dates"
    if all(EPOCH_RE.match(x) for x in s) and has(r"time|date|_at$|^ts$|created|updated"): return "date", "epoch timestamps"
    if any(any(_strp(x, f) for f in DATE_FORMATS) for x in s[:5]) and all(any(_strp(x, f) for f in DATE_FORMATS) for x in s[:200]):
        return "date", "formatted dates"
    if has(r"phone|mobile|tel|fax|cell") or (all(PHONE_RE.match(x) for x in s) and not all(x.isdigit() for x in s)):
        return "phone", "phone numbers"
    if all(UNIT_RE.match(x) for x in s) and has(r"unit|apt|apartment|suite|room|seat|desk|stall|bay|lot|cabin|locker"):
        return "unit", "unit labels (floor + letter)"
    numeric = all(re.fullmatch(r"-?\d+(\.\d+)?", x) for x in s)
    if has(r"(^|_)(id|uuid|guid|key|serial|sku|zip|postal|postcode|account|acct|ssn|ein|vin|iban)$") or name.endswith("id"):
        return "id", "identifier: format kept, value replaced"
    if numeric:
        ints = all(re.fullmatch(r"-?\d+", x) for x in s)
        if ints and distinct == len(s) and len(s) > 20 and len({len(x) for x in s}) == 1 and len(s[0]) >= 5:
            return "id", "unique fixed-width integers: looks like an id, not a quantity"
        return "number", "numbers"
    if all(NUM_RE.match(x) for x in s):
        return "number", "formatted numbers"
    if has(r"^(name|full_?name|first_?name|last_?name|display_?name|user_?name|author|assignee|reporter|resident|tenant|employee|rep|manager|patient|student|member|contact)$") or \
            has(r"(contact|person|owner|customer|user|client|patient|employee|rep|manager|recipient|sender|signer)_?name$"):
        return "person", "probably a person"
    if has(r"company|org|organi[sz]ation|employer|vendor|supplier|client|customer|account_?name|brand|partner|agency|firm|owner"):
        return "org", "probably an organization"
    if has(r"address|street|building|property|site|location|store|venue|facility|branch|campus|clinic|school|warehouse"):
        return "place", "probably a place"
    if any(EMAIL_RE.match(x) is None and re.search(EMAIL_P, x) for x in s) or any(len(x) > 40 for x in s):
        return "text", "free text: names, emails and ids can hide inside it"
    if distinct <= 12 and len(s) >= 2 * distinct:
        return "keep", f"{distinct} repeated values: a category or status, keep it"
    if has(r"title|project|product|campaign|team|group|plan|deal|listing"):
        return "label", "a name: check whether it identifies anyone"
    return "keep", f"{distinct} distinct values: check it"


def _strp(x, f):
    try:
        datetime.strptime(x.strip(), f)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- profile / compare

def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def summarize(vals):
    present = [v for v in vals if not is_missing(v)]
    out = {"n": len(vals), "missing": 1 - len(present) / len(vals) if vals else 0, "distinct": len({str(v) for v in present})}
    nums = []
    for v in present:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            nums.append(float(v))
        elif isinstance(v, str):
            m = NUM_RE.match(v.strip())
            if m and not ISO_RE.match(v.strip()):
                nums.append(float(m["num"].replace(",", "")) * (-1 if m["sign"] else 1))
    if present and len(nums) >= 0.9 * len(present):
        med = statistics.median(nums)
        out.update(min=min(nums), median=med, p95=pct(nums, 0.95), max=max(nums),
                   spread=(max(nums) / med) if med else None, zeros=sum(1 for x in nums if x == 0) / len(nums))
    elif present:
        lens = [len(str(v)) for v in present]
        out.update(len_min=min(lens), len_median=statistics.median(lens), len_max=max(lens))
    return out


def profile(doc):
    values, lists = collect(doc)
    prof = {sig: summarize(v) for sig, v in values.items()}
    for sig, ns in lists.items():
        prof[f"{sig or '(records)'} #count"] = {"n": len(ns), "min": min(ns), "median": statistics.median(ns), "max": max(ns),
                                                "spread": (max(ns) / statistics.median(ns)) if statistics.median(ns) else None}
    return prof


def fmt_num(x):
    if x is None:
        return "-"
    if isinstance(x, float) and not x.is_integer():
        return f"{x:,.2f}"
    return f"{int(x):,}"


def describe(s):
    bits = [f"{s['n']} values"]
    if s.get("missing"):
        bits.append(f"{s['missing']:.0%} missing")
    if "distinct" in s:
        bits.append(f"{s['distinct']} distinct")
    if "median" in s:
        bits.append(f"min {fmt_num(s['min'])}, median {fmt_num(s['median'])}, max {fmt_num(s['max'])}")
        if s.get("spread"):
            bits.append(f"max is {s['spread']:.1f}x the median")
        if s.get("zeros"):
            bits.append(f"{s['zeros']:.0%} zeros")
    if "len_max" in s:
        bits.append(f"length {s['len_min']} to {s['len_max']} (median {s['len_median']:g})")
    return ", ".join(bits)


def drift(a, b):
    """What changed in the shape between real (a) and double (b)."""
    notes = []
    if abs(a.get("missing", 0) - b.get("missing", 0)) > 0.02:
        notes.append(f"missing {a['missing']:.0%} -> {b['missing']:.0%}")
    if "median" not in a and a.get("distinct") and abs(b.get("distinct", 0) - a["distinct"]) / a["distinct"] > 0.1:
        notes.append(f"distinct {a['distinct']} -> {b.get('distinct')}")
    if a.get("spread") and b.get("spread") and abs(b["spread"] - a["spread"]) / a["spread"] > 0.3:
        notes.append(f"max/median {a['spread']:.1f}x -> {b['spread']:.1f}x")
    if "zeros" in a and abs(a["zeros"] - b.get("zeros", 0)) > 0.02:
        notes.append(f"zeros {a['zeros']:.0%} -> {b.get('zeros', 0):.0%}")
    for k in ("len_max", "len_median"):
        if a.get(k) and b.get(k) is not None and abs(b[k] - a[k]) / a[k] > 0.25:
            notes.append(f"{k.replace('_', ' ')} {a[k]:g} -> {b[k]:g}")
    if ("median" in a) != ("median" in b):
        notes.append("type changed")
    return notes


# ---------------------------------------------------------------- grow

def grow(doc, spec, target):
    if not isinstance(doc, list):
        sys.exit("grow works on a list of records (a top-level JSON list, or a CSV)")
    rng = random.Random(spec.get("seed", 7) + 1)
    if target <= len(doc):
        keep = sorted(rng.sample(range(len(doc)), target))
        return [doc[i] for i in keep]
    d = Doubler({**spec, "seed": rng.randrange(10 ** 9), "shift_weeks": 0, "record_jitter_hours": spec.get("grow_jitter_hours", 48)})
    minter = Doubler({**spec, "seed": rng.randrange(10 ** 9)})
    values, _ = collect(doc)
    taken ={sig: {str(v) for v in vals} for sig, vals in values.items()}

    def fresh(sig, v, make):
        for _ in range(100):
            n = make(v)
            if str(n) not in taken.setdefault(sig, set()):
                taken[sig].add(str(n))
                return n
        return v

    def leaf(sig, v):
        c = d.conf(sig)
        k = c.get("kind", "keep")
        if is_missing(v) or k == "drop":
            return v
        if k == "number":
            return d.number(v, {**c, "scale": 1.0})
        if k == "date":
            return d.date(v, d.offset())
        if k in ("id", "hex", "uuid"):
            def mint(x):
                minter.maps = {}  # forget, so every copy gets a new value in the same format
                return {"id": minter.ident, "hex": minter.hexid, "uuid": minter.uuid_}[k](str(x))
            out = fresh(sig, v, mint)
            return int(out) if isinstance(v, int) and str(out).isdigit() else out
        return v

    out = list(doc)
    walker = Walk(leaf, enter=d.enter, leave=d.leave)
    while len(out) < target:
        out.append(walker.run([copy.deepcopy(rng.choice(doc))])[0])
    return out


# ---------------------------------------------------------------- audit

TEXT_EXT = {".html", ".htm", ".js", ".mjs", ".jsx", ".ts", ".tsx", ".json", ".csv", ".tsv", ".psv", ".md",
            ".txt", ".svg", ".css", ".vue", ".svelte", ".py", ".yml", ".yaml", ".xml", ".sql"}


def audit(mapping_path, targets, extra_terms):
    mapping = json.loads(Path(mapping_path).read_text())
    doubles = {d for k, m in mapping.items() if not k.startswith("_") for d in m.values()}
    reals = {}
    for kind, m in mapping.items():
        if kind.startswith("_") or kind == "unit":
            continue  # units are a permutation: real labels legitimately reappear as other units
        for real in m:
            if len(real) >= 3 and real not in doubles:
                reals[real] = kind
    for t in extra_terms:
        reals[t] = "term"
    if not reals:
        print("nothing to look for: the mapping is empty")
        return 0
    rx = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(r) for r in sorted(reals, key=len, reverse=True)) + r")(?!\w)", re.I)
    files = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files += [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in TEXT_EXT
                      and not any(part in (".git", "node_modules") for part in f.parts)]
        elif p.is_file():
            files.append(p)
    files = [f for f in files if not f.name.endswith(".mapping.json")]
    leaks = 0
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for m in rx.finditer(line):
                hit = next((r for r in reals if r.lower() == m.group(0).lower()), m.group(0))
                print(f"LEAK {f}:{i}  {reals.get(hit, '?')} {mask(hit)}")
                leaks += 1
    if leaks:
        print(f"\n{leaks} real identifier(s) found in {len(files)} file(s). Replace them and run audit again.")
        return 1
    print(f"clean: none of {len(reals)} real identifiers appear in {len(files)} file(s)")
    print("audit only knows the values in the mapping: also read the prose, images and URLs yourself")
    return 0



# ---------------------------------------------------------------- mirror

def mirror(args):
    """Real data in, its double out. Several files share one double, so a
    customer in accounts.csv gets the same stand-in in orders.json."""
    srcs = [Path(x) for x in args.data]
    loaded = [load(x, args.no_header) for x in args.data]
    base = srcs[0].with_name(srcs[0].stem) if len(srcs) == 1 else srcs[0].with_name("data-double")
    spec_path = Path(args.spec) if args.spec else Path(f"{base}.spec.json")
    if spec_path.exists():
        spec = json.loads(spec_path.read_text())
        print(f"using {spec_path}")
    else:
        values = {}
        for doc, _ in loaded:
            for sig, vals in collect(doc)[0].items():
                values.setdefault(sig, []).extend(vals)
        spec = {"fields": {}}
        print("what each field looks like:")
        for sig, vals in values.items():
            kind, why = guess(sig, vals)
            spec["fields"][sig] = kind
            print(f"  {sig:<28} {kind:<7} {why}")
    spec = resolve_spec(spec)
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"saved {spec_path}: fix any field guessed wrong, then run mirror again\n")

    d = Doubler(spec)
    combined = [doc for doc, _ in loaded]
    d.plan_units(combined)
    d.plan_units = lambda doc: None  # planned once across every file
    outs = [d.make(doc) for doc, _ in loaded]
    dests = []
    for src, out, (_, fmt) in zip(srcs, outs, loaded):
        dest = Path(args.out) if (args.out and len(srcs) == 1) else out_path(src, "double")
        save(dest, out, fmt)
        dests.append(dest)
    mp = Path(f"{base}.mapping.json")
    mp.write_text(json.dumps({"_params": {k: spec[k] for k in ("seed", "scale", "shift_weeks", "jitter")}, **d.maps}, indent=2, ensure_ascii=False) + "\n")

    print("shape check (real vs double):")
    total = drifted = 0
    for src, (doc, _), out in zip(srcs, loaded, outs):
        pa, pb = profile(doc), profile(out)
        for sig in pa:
            total += 1
            notes = drift(pa[sig], pb.get(sig, {})) if sig in pb else ["dropped"]
            if notes:
                drifted += 1
                print(f"  DRIFT {src.name} {sig}: " + "; ".join(notes))
    print(f"  {total} fields, " + (f"{drifted} drifted" if drifted else "the shape held"))
    print("\nleak check:")
    leaked = audit(str(mp), [str(x) for x in dests], [])
    print()
    for x in dests:
        print(f"wrote {x}")
    print(f"wrote {mp}  (re-identifies everything: keep it local, never share or commit it)")
    kept = [k for k, v in spec["fields"].items() if (v if isinstance(v, str) else v.get("kind")) == "keep"]
    if kept:
        print(f"left as they were: {', '.join(kept)}. Make sure none of them identifies anyone.")
    return leaked


# ---------------------------------------------------------------- cli

def resolve_spec(spec):
    """Fill in anything left out with a random choice, and say what was picked."""
    picked = []
    sysrand = random.SystemRandom()
    if "seed" not in spec:
        spec["seed"] = sysrand.randrange(1, 10 ** 6); picked.append(f'"seed": {spec["seed"]}')
    if "scale" not in spec:
        spec["scale"] = round(sysrand.choice([sysrand.uniform(0.85, 0.95), sysrand.uniform(1.05, 1.15)]), 3)
        picked.append(f'"scale": {spec["scale"]}')
    if "shift_weeks" not in spec:
        spec["shift_weeks"] = sysrand.choice([-1, 1]) * sysrand.randint(3, 12); picked.append(f'"shift_weeks": {spec["shift_weeks"]}')
    spec.setdefault("jitter", 0.08)
    spec.setdefault("record_jitter_hours", 12)
    if picked:
        print("picked: " + ", ".join(picked) + "  (add these to the spec to keep the double stable across rebuilds)")
    return spec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    mi = sub.add_parser("mirror", help="one step: real data in, its double out (scan + make + compare + audit)")
    mi.add_argument("data", nargs="+", help="one file, or several related files that must stay consistent with each other"); mi.add_argument("--spec", help="use this spec instead of <data>.spec.json or the guesses")
    mi.add_argument("-o", "--out"); mi.add_argument("--no-header", action="store_true")
    s = sub.add_parser("scan", help="shape of every field and a starter spec")
    s.add_argument("data"); s.add_argument("--write", metavar="SPEC", help="save the starter spec here")
    s.add_argument("--no-header", action="store_true")
    m = sub.add_parser("make", help="make the double")
    m.add_argument("data"); m.add_argument("spec"); m.add_argument("-o", "--out")
    m.add_argument("--no-header", action="store_true")
    p = sub.add_parser("profile", help="the shape of one dataset")
    p.add_argument("data"); p.add_argument("--no-header", action="store_true")
    c = sub.add_parser("compare", help="real vs double, field by field")
    c.add_argument("real"); c.add_argument("double"); c.add_argument("--no-header", action="store_true")
    a = sub.add_parser("audit", help="look for real identifiers in finished output")
    a.add_argument("mapping"); a.add_argument("paths", nargs="+")
    a.add_argument("--terms", nargs="*", default=[], help="more real strings to look for (a customer name that isn't in the data)")
    g = sub.add_parser("grow", help="resize a double: --times 10 for heavy, --rows 0 for empty")
    g.add_argument("data"); g.add_argument("spec"); g.add_argument("-o", "--out")
    g.add_argument("--times", type=float); g.add_argument("--rows", type=int)
    g.add_argument("--no-header", action="store_true")
    args = ap.parse_args()

    if args.cmd == "audit":
        sys.exit(audit(args.mapping, args.paths, args.terms))

    if args.cmd == "compare":
        ra, _ = load(args.real, args.no_header)
        rb, _ = load(args.double, args.no_header)
        pa, pb = profile(ra), profile(rb)
        drifted = 0
        for sig in pa:
            if sig not in pb:
                print(f"  {sig}: missing from the double (dropped?)")
                continue
            notes = drift(pa[sig], pb[sig])
            if notes:
                drifted += 1
                print(f"  DRIFT {sig}: " + "; ".join(notes))
        print(f"{len(pa)} fields compared, {drifted} drifted" + ("" if drifted else ": the shape held"))
        return

    if args.cmd == "mirror":
        sys.exit(mirror(args))

    doc, fmt = load(args.data, args.no_header)

    if args.cmd == "profile":
        n = len(doc) if isinstance(doc, list) else 1
        print(f"{n} records")
        for sig, st in profile(doc).items():
            print(f"  {sig}: {describe(st)}")
        return

    if args.cmd == "scan":
        values, lists = collect(doc)
        print(f"{len(doc) if isinstance(doc, list) else 1} records, {len(values)} fields. Values are masked (A = capital, a = letter, 9 = digit).\n")
        fields = {}
        for sig, vals in values.items():
            kind, why = guess(sig, vals)
            fields[sig] = kind
            ex = next((v for v in vals if not is_missing(v)), "")
            print(f"  {sig}  ->  {kind}   ({why}; e.g. {mask(ex)!r}; {describe(summarize(vals))})")
        for sig, ns in lists.items():
            if sig and ns:
                print(f"  {sig}  list length {min(ns)} to {max(ns)} (median {statistics.median(ns):g})")
        spec = {"fields": fields}
        print("\nstarter spec (check every field: scan guesses):")
        print(json.dumps(spec, indent=2))
        if args.write:
            Path(args.write).write_text(json.dumps(spec, indent=2) + "\n")
            print(f"\nwrote {args.write}")
        return

    spec = resolve_spec(json.loads(Path(args.spec).read_text()))

    if args.cmd == "make":
        d = Doubler(spec)
        out = d.make(doc)
        dest = Path(args.out) if args.out else out_path(args.data, "double")
        save(dest, out, fmt)
        mp = Path(args.data).with_name(Path(args.data).stem + ".mapping.json")
        mp.write_text(json.dumps({"_params": {k: spec[k] for k in ("seed", "scale", "shift_weeks", "jitter")}, **d.maps}, indent=2, ensure_ascii=False) + "\n")
        counts = ", ".join(f"{len(v)} {k}" for k, v in d.maps.items())
        print(f"wrote {dest}")
        print(f"wrote {mp}  ({counts or 'nothing mapped'}). It re-identifies everything: keep it local.")
        return

    if args.cmd == "grow":
        if args.rows is None and args.times is None:
            sys.exit("pass --times N or --rows N")
        target = args.rows if args.rows is not None else int(round(len(doc) * args.times))
        out = grow(doc, spec, target)
        tag = "empty" if target == 0 else f"x{args.times:g}" if args.times else f"{target}rows"
        dest = Path(args.out) if args.out else out_path(args.data, tag)
        save(dest, out, fmt)
        print(f"wrote {dest} ({len(out)} records)")


if __name__ == "__main__":
    main()
