#!/usr/bin/env python3
"""
NEON VEINS — script compiler.

Reads the game script (tools/NEON_VEINS_script.txt, extracted from the
design document) and compiles the "Full Game Transcript" section into a
structured scene graph that the runtime story engine plays:

    js/data/script_data.js   ->  window.NV_DATA = {...}

Node types emitted (compact keys to keep the payload small):
    {"t":"scene","v":name}                       background / location change
    {"t":"n","v":text}                           narration
    {"t":"l","s":speaker,"v":text}               spoken line
    {"t":"sys","k":kind,"v":text}                HUD notification / tag
    {"t":"choice","p":prompt,"o":[{label,text,fx,b:[nodes]}]}
    {"t":"cond","each":bool,"b":[{"c":cond,"n":[nodes]}]}
    {"t":"play","m":mode,"d":desc,"boss":name,"k":count}
    {"t":"final"}                                six-door ending selector

Run:  python3 tools/build_script.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "NEON_VEINS_script.txt")
HTML = os.path.join(HERE, "..", "index.html")
BEGIN, END = "/*NV_DATA_BEGIN*/", "/*NV_DATA_END*/"

NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12}

STOP = set("""the a an of to and or in on at for with from by is are was were be been
it its this that their them they ghost ghost's if into out as who what when not no
""".split())

CHOICE_TAGS = ("PLAYER RESPONSE", "PLAYER CHOICE", "PLAYER APPROACH",
               "PLAYER TACTIC", "FINAL CHOICE")
BLOCK_TAGS = ("BRANCH", "TASK PATH")

SPEAKER_RE = re.compile(r"^([A-Z0-9][^:]{0,44}?): (.+)$")

# ---------------------------------------------------------------- helpers

def clean(s):
    return s.replace(" ", " ").strip()


def is_speaker(name):
    if not name or len(name) > 44:
        return False
    if name.startswith("Option") or name.startswith("Door "):
        return False
    base = re.sub(r"\([^)]*\)", "", name).strip()
    words = base.split()
    if not words or len(words) > 5:
        return False
    for w in words:
        if w.lower() in ("of", "the", "de", "van", "von", "and"):
            continue
        if not (w[0].isupper() or w[0].isdigit() or w[0] in "“\"'"):
            return False
    return True


def keywords(s):
    s = s.lower().replace("’", "'")
    ws = re.findall(r"[a-z0-9]+", s)
    return [w for w in ws if len(w) > 2 and w not in STOP]


def stem(w):
    return w[:5]


def overlap(a, b):
    sa = {stem(w) for w in keywords(a)}
    sb = {stem(w) for w in keywords(b)}
    if not sa or not sb:
        return 0
    return len(sa & sb)


# ------------------------------------------------------ stat heuristics
# Every option is scored against the five hidden world variables that the
# design document says drive the endings.
FX_RULES = [
    ("hope", 4, r"\b(help|rescue|save|protect|shelter|share|lifeline|teach|civilian|children|child|family|families|promise|gentle|calm|evacuate|resident|feed|together|people|community|everyone|heal|medic)"),
    ("hope", -3, r"\b(abandon|seal (the|off|it|them)|close the border|leave them|ignore|sacrifice|fastest)"),
    ("raven", 4, r"\b(honest|honesty|truth|full disclosure|trust|tell raven|raven|please stay|protective|loyal)"),
    ("raven", -4, r"\b(lie|conceal|deceive|hide it)"),
    ("raven", -1, r"\b(deflect)"),
    ("ai", 4, r"\b(listen|free|let (her|him|it|them) grow|independen|consent|let (her|him|it|them) choose|preserve|you're real|you are real|ascension|seed|restore|awaken|release|autonomy|let it decide|you get to decide|curious|question)"),
    ("ai", -4, r"\b(destroy|delete|erase|not real|shut (it|them) down|wipe|purge|control)"),
    ("corp", 4, r"\b(negotiate|deal|bribe|threaten|leverage|helix|sell|bluff|blackmail|seize|take control|command|exploit|profit|buy|bargain|ghost control|contract)"),
    ("voss", 4, r"\b(voss|forgive|evidence|record|expose|answer for|document|witness|archive|remember)"),
    ("voss", -3, r"\b(forget|bury|cover)"),
]
AUTONOMY_RE = re.compile(r"\b(free|let (her|him|it|them) (grow|choose|decide)|independen|consent|autonomy|you get to decide|you decide)", re.I)
CONTROL_RE = re.compile(r"\b(take control|seize|ghost control|rule|absolute|command it|own it)", re.I)


def option_fx(label, text):
    s = (label + " " + text).lower().replace("’", "'")
    fx = {}
    for stat, amt, pat in FX_RULES:
        if re.search(pat, s):
            fx[stat] = fx.get(stat, 0) + amt
    for k in list(fx):
        fx[k] = max(-6, min(6, fx[k]))
        if fx[k] == 0:
            del fx[k]
    flags = []
    if AUTONOMY_RE.search(s):
        flags.append("autonomy")
    if CONTROL_RE.search(s):
        flags.append("control")
    return fx, flags


STAT_TAG_RE = [
    ("raven", r"raven trust"), ("voss", r"voss integrity"), ("hope", r"civilian hope"),
    ("corp", r"corporate leverage"), ("ai", r"ai sympathy"),
]


def tag_fx(text):
    """[RELATIONSHIP PATH: Raven Trust increases.] style tags."""
    s = text.lower()
    fx = {}
    for stat, pat in STAT_TAG_RE:
        if re.search(pat, s):
            if re.search(r"decreas|falls|drops|lower|loses|damag", s):
                fx[stat] = -5
            else:
                fx[stat] = 5
    return fx


# ------------------------------------------------- gameplay classification
DIALOGUE_RE = re.compile(r"\b(talk|speak|negotiat|hear |dialogue|meet each|accompany|attend|verify|examine|balance|assign|constellation|call witnesses|tribunal|last night|before choosing|guide noah|farewell tour|first session|handover|allocation|reconstruct tomas|walk through the hall|rewrite the directive|choose the descent|organize shelter|learn the truth|speak with)", re.I)
DEFEND_RE = re.compile(r"\b(defend|protect|hold|survive|siege)", re.I)
ARENA_RE = re.compile(r"\b(win (five|three) rounds|arena|fight)", re.I)
HACK_RE = re.compile(r"\b(restore|stabili[sz]e|connect|isolate|install|breach|open the|power|repair|disconnect|map the)", re.I)
EXPLORE_RE = re.compile(r"\b(walk|explore|search|recover|reconstruct|visit|investigate|locate|follow|track|recover|gather|enter five|enter four|find)", re.I)
INFIL_RE = re.compile(r"\b(infiltrate|board|traverse|descend|cross|escape|reach|intercept|enter|stop|wake)", re.I)
HOSTILE_RE = re.compile(r"\b(drone|helix|attack|assault|swarm|diver|cleaner|guard|soldier|dominion|enem|while)", re.I)


def classify(desc):
    d = desc
    if DIALOGUE_RE.search(d):
        return None
    if ARENA_RE.search(d):
        mode = "arena"
    elif DEFEND_RE.search(d):
        mode = "defend"
    elif HACK_RE.search(d):
        mode = "hack"
    elif EXPLORE_RE.search(d):
        mode = "explore" if not HOSTILE_RE.search(d) else "retrieve"
    elif INFIL_RE.search(d):
        mode = "infiltrate"
    else:
        return None
    k = 3
    m = re.search(r"\b(one|two|three|four|five|six|seven|eight|twelve)\b", d.lower())
    if m:
        k = NUMWORDS[m.group(1)]
    m = re.search(r"\b(\d+)\b", d)
    if m and not re.search(r"chapter|sq", d.lower()):
        k = int(m.group(1))
    k = max(1, min(6, k))
    return mode, k


# ------------------------------------------------------------ tokenizer

def tokenize(lines):
    toks = []
    for raw in lines:
        s = clean(raw)
        if not s:
            continue
        m = re.match(r"^Chapter (\d+[A-F]?) — (.+)$", s)
        if m:
            toks.append(("chapter", m.group(1), m.group(2)))
            continue
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            m = re.match(r"^([A-Z0-9 ’'\-—/&,.]+?)(?::\s*(.*))?$", inner)
            if m and m.group(1).isupper():
                toks.append(("tag", m.group(1).strip(), (m.group(2) or "").strip()))
            else:
                toks.append(("tag", "QUOTE", inner))
            continue
        m = re.match(r"^Option — (.+)$", s)
        if m:
            body = m.group(1)
            label, text = body, ""
            mq = re.match(r"^“(.+)”\.?$", body)
            if mq:
                label, text = "", mq.group(1)
            else:
                mm = re.match(r"^([^:“]+?):\s*(.*)$", body)
                if mm:
                    label, text = mm.group(1).strip(), mm.group(2).strip()
                    if text.startswith("“") and text.endswith("”"):
                        text = text[1:-1]
                    elif text:
                        # descriptive action, not spoken
                        label = label + " — " + text
                        text = ""
                label = label.rstrip(".")
            toks.append(("option", label, text))
            continue
        m = re.match(r"^Door (One|Two|Three|Four|Five|Six) — (.+)$", s)
        if m:
            toks.append(("door", m.group(1), m.group(2)))
            continue
        if s.startswith("If ") or s.startswith("If,"):
            m = re.match(r"^If (.+?):\s*$", s)
            if m:
                toks.append(("if", m.group(1), ""))
            else:
                m = re.match(r"^If ([^,]+),\s*(.+)$", s)
                if m:
                    rest = m.group(2)
                    toks.append(("if", m.group(1), rest[0].upper() + rest[1:]))
                else:
                    toks.append(("if", s[3:].rstrip(".:"), ""))
            continue
        if s.startswith("Otherwise"):
            rest = re.sub(r"^Otherwise[,:]?\s*", "", s)
            toks.append(("else", "", rest[:1].upper() + rest[1:] if rest else ""))
            continue
        m = SPEAKER_RE.match(s)
        if m and is_speaker(m.group(1)):
            toks.append(("line", m.group(1).strip(), m.group(2).strip()))
            continue
        toks.append(("narr", s, ""))
    return toks


# --------------------------------------------------------------- parser

SYS_KIND = {
    "MISSION COMPLETE": "mission", "NEW MISSION UNLOCKED": "unlock",
    "SIDE QUEST UNLOCKED": "side", "NEW SIDE QUEST UNLOCKED": "side",
    "SIDE QUEST COMPLETE": "sidedone", "NEW SIDE QUESTS AVAILABLE": "side",
    "JOURNAL ENTRY UNLOCKED": "journal", "JOURNAL ENTRY UPDATED": "journal",
    "NEW OBJECTIVE": "objective", "OPTIONAL OBJECTIVE": "objective",
    "BONUS OBJECTIVE": "objective", "PAPER STAR COLLECTED": "star",
    "MEMORY FRAGMENT": "memory", "MYSTERY LOGGED": "mystery",
    "MYSTERY RESOLVED": "mystery", "CONSEQUENCE": "consequence",
    "RELATIONSHIP PATH": "relation", "WORLD AREA UNLOCKED": "area",
    "AREA DISCOVERED": "area", "EVIDENCE ACQUIRED": "evidence",
    "HELIX INTERLUDE": "interlude", "INTERLUDE": "interlude",
    "SIDE CHAPTER": "interlude", "ENDING RELEVANCE": "consequence",
    "LEGENDARY MYSTERY THREAD ADVANCED": "mystery",
}


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    # A sequence continues until a stop condition decided by `stop(tok, ctx)`.
    def seq(self, stop, depth=0):
        out = []
        while True:
            tok = self.peek()
            if tok is None or tok[0] == "chapter" or stop(tok, out):
                return out
            kind = tok[0]
            if kind == "tag":
                name, val = tok[1], tok[2]
                if name == "SCENE CHANGE TO":
                    self.i += 1
                    continue
                if name == "SCENE":
                    if depth > 0 and stop(("scene",), out):
                        return out
                    self.i += 1
                    out.append({"t": "scene", "v": val})
                    continue
                if name in CHOICE_TAGS or name.startswith("PLAYER RESPONSE"):
                    self.i += 1
                    out.append(self.choice(val, name, depth))
                    continue
                if name in BLOCK_TAGS:
                    out.append(self.block_group(depth))
                    continue
                if name == "VARIATION" or name == "EPILOGUE VARIATIONS":
                    if name == "EPILOGUE VARIATIONS":
                        self.i += 1
                        continue
                    out.append(self.variation_group(depth))
                    continue
                if name in ("GAMEPLAY", "BOSS ENCOUNTER"):
                    self.i += 1
                    out.append({"t": "gp", "k": name, "v": val})
                    continue
                self.i += 1
                if name == "QUOTE":
                    out.append({"t": "sys", "k": "quote", "v": val})
                    continue
                kindname = SYS_KIND.get(name, "tag")
                node = {"t": "sys", "k": kindname, "v": (name.title() + (": " + val if val else "")) if kindname == "tag" else val or name.title()}
                if kindname in ("mission", "unlock", "side", "sidedone", "journal", "area", "objective", "star", "evidence"):
                    node["h"] = name.title()
                fx = tag_fx(val) if kindname in ("relation", "consequence") else {}
                if fx:
                    node["fx"] = fx
                out.append(node)
                continue
            if kind == "option" or kind == "door":
                # stray option without a header: treat as its own choice
                out.append(self.choice("", "PLAYER RESPONSE", depth))
                continue
            if kind in ("if", "else"):
                out.append(self.if_group(depth, None))
                continue
            self.i += 1
            if kind == "line":
                out.append({"t": "l", "s": tok[1], "v": tok[2]})
            else:
                out.append({"t": "n", "v": tok[1]})

    def choice(self, prompt, tagname, depth):
        opts = []
        final = tagname == "FINAL CHOICE"
        while self.peek() and self.peek()[0] in ("option", "door"):
            t = self.peek()
            self.i += 1
            if t[0] == "door":
                continue
            label, text = t[1], t[2]
            fx, flags = option_fx(label, text)
            o = {"label": label, "text": text, "b": []}
            if fx:
                o["fx"] = fx
            if flags:
                o["f"] = flags
            opts.append(o)
        if final:
            # swallow trailing "[THIS CHOICE IS PERMANENT.]"
            return {"t": "final"}
        # consequences/relationship tags between options and branches
        pre = []
        while self.peek() and self.peek()[0] == "tag" and self.peek()[1] in ("CONSEQUENCE", "RELATIONSHIP PATH", "OPTIONAL OBJECTIVE", "BONUS OBJECTIVE", "ENDING RELEVANCE"):
            t = self.peek()
            self.i += 1
            k = SYS_KIND.get(t[1], "tag")
            n = {"t": "sys", "k": k, "v": t[2]}
            fx = tag_fx(t[2])
            if fx:
                n["fx"] = fx
            pre.append(n)
        nxt = self.peek()
        runtime = []
        if nxt and (nxt[0] in ("if", "else") or (depth == 0 and nxt[0] == "tag" and nxt[1] in BLOCK_TAGS)):
            if nxt[0] in ("if", "else"):
                grp = self.if_group(depth, opts)
                keep, rt = [], []
                for b in grp["b"]:
                    (keep if self.attachable(b["c"], opts) else rt).append(b)
                grp["b"] = keep
                if rt:
                    runtime.append({"t": "cond", "b": rt})
            else:
                grp = self.block_group(depth, opts)
            if grp["b"]:
                self.attach(opts, grp)
        node = {"t": "choice", "p": prompt, "o": opts}
        if not opts:
            return {"t": "n", "v": prompt} if prompt else {"t": "sys", "k": "tag", "v": "…"}
        if pre or runtime:
            return {"t": "seq", "n": [node] + pre + runtime}
        return node

    @staticmethod
    def attachable(c, opts):
        if not c:
            return True
        if re.search(r"chapter|earlier|previous|survived|alive|was |were |had ", c, re.I):
            return False
        if imperative(c):
            return True
        if len(keywords(c)) <= 2:
            return True
        return any(overlap(o["label"] + " " + o["text"], c) >= 2 for o in opts)

    def attach(self, opts, grp):
        """Map the conditional blocks that follow a choice onto its options."""
        blocks = grp["b"]
        used = set()
        leftovers = []
        # pass 1: keyword overlap
        scores = []
        for oi, o in enumerate(opts):
            src = o["label"] + " " + o["text"]
            for bi, b in enumerate(blocks):
                sc = overlap(src, b["c"]) if b["c"] else 0
                if sc > 0:
                    scores.append((sc, -abs(oi - bi), oi, bi))
        scores.sort(reverse=True)
        assigned = {}
        for sc, _, oi, bi in scores:
            if oi in assigned:
                continue
            if bi in used and len(blocks) >= len(opts):
                continue
            assigned[oi] = bi
            used.add(bi)
        # pass 2: equal counts -> positional for anything unmatched
        if len(blocks) == len(opts):
            for oi in range(len(opts)):
                if oi not in assigned:
                    for bi in range(len(blocks)):
                        if bi not in used:
                            assigned[oi] = bi
                            used.add(bi)
                            break
        # pass 3: short keyword conditions ("If Curious:") positional by label
        for oi, bi in assigned.items():
            opts[oi]["b"] = blocks[bi]["n"]
        for bi, b in enumerate(blocks):
            if bi not in used and not b["c"]:
                # "Otherwise" -> every option that got nothing
                for oi, o in enumerate(opts):
                    if oi not in assigned:
                        o["b"] = b["n"]
            elif bi not in used:
                leftovers.append(b)
        # unmatched blocks go to every option that received nothing
        if leftovers:
            free = [oi for oi in range(len(opts)) if oi not in assigned]
            if free:
                for oi in free:
                    opts[oi]["b"] = [{"t": "cond", "b": leftovers}] if len(leftovers) > 1 else leftovers[0]["n"]

    def if_group(self, depth, opts):
        blocks = []
        while self.peek() and self.peek()[0] in ("if", "else"):
            t = self.peek()
            self.i += 1
            cond = t[1] if t[0] == "if" else ""
            body = []
            if t[2]:
                body.append({"t": "n", "v": t[2]})
            inline = bool(t[2])
            state = {"dialogue": False, "narr": 0}

            def stop(tok, out, inline=inline, state=state):
                if tok[0] in ("if", "else", "option", "door", "scene"):
                    return True
                if tok[0] == "tag":
                    return tok[1] not in ("CONSEQUENCE", "RELATIONSHIP PATH", "PAPER STAR COLLECTED", "MEMORY FRAGMENT", "EVIDENCE ACQUIRED", "JOURNAL ENTRY UPDATED", "MYSTERY LOGGED", "QUOTE")
                if tok[0] == "line":
                    state["dialogue"] = True
                    return False
                if tok[0] == "narr":
                    if state["dialogue"] or inline:
                        return True
                    state["narr"] += 1
                    return state["narr"] > 2
                return False
            body += self.seq(stop, depth + 1)
            blocks.append({"c": cond, "n": body})
        return {"t": "cond", "b": blocks}

    def block_group(self, depth, opts=None):
        blocks = []
        while self.peek() and self.peek()[0] == "tag" and self.peek()[1] in BLOCK_TAGS:
            t = self.peek()
            self.i += 1

            def stop(tok, out):
                if tok[0] == "scene":
                    return True
                return tok[0] == "tag" and (tok[1] in BLOCK_TAGS or tok[1] in ("SCENE", "SCENE CHANGE TO", "MISSION COMPLETE"))
            body = self.seq(stop, depth + 1)
            blocks.append({"c": t[2], "n": body})
        return {"t": "cond", "b": blocks, "br": 1}

    def variation_group(self, depth):
        blocks = []
        while self.peek() and self.peek()[0] == "tag" and self.peek()[1] == "VARIATION":
            t = self.peek()
            self.i += 1

            def stop(tok, out):
                if tok[0] == "scene":
                    return True
                return tok[0] == "tag" and tok[1] in ("VARIATION", "FINAL SCENE", "SCENE", "SCENE CHANGE TO", "EPILOGUE VARIATIONS") or (tok[0] == "tag" and tok[1].startswith("ENDING "))
            body = self.seq(stop, depth + 1)
            blocks.append({"c": t[2], "n": body})
        return {"t": "cond", "b": blocks, "each": 1}


def flatten(nodes):
    out = []
    for n in nodes:
        if n.get("t") == "seq":
            out.extend(flatten(n["n"]))
            continue
        if n.get("t") == "choice":
            for o in n["o"]:
                o["b"] = flatten(o["b"])
                if "post" in o:
                    o["post"] = flatten(o["post"])
        if n.get("t") == "cond":
            for b in n["b"]:
                b["n"] = flatten(b["n"])
        out.append(n)
    return out


# ------------------------------------- free-standing action conditions
PAST_WORDS = set("""was were had did kept told gave made chose left took saved spared
freed erased preserved destroyed completed restored received recovered released
accepted refused rejected protected let trusted found""".split())
NEG_RE = re.compile(r"\b(not|n't|never|failed|without|no)\b", re.I)


def imperative(cond):
    """'Ghost powers the fire doors' -> 'Power the fire doors'."""
    m = re.match(r"^Ghost (\w+)(.*)$", cond)
    if not m:
        return None
    verb, rest = m.group(1), m.group(2)
    if verb == "is":
        verb = "be"
    elif verb in PAST_WORDS or verb.endswith("ed"):
        return None
    elif verb.endswith("ies"):
        verb = verb[:-3] + "y"
    elif re.search(r"(sh|ch|ss|x|z)es$", verb):
        verb = verb[:-2]
    elif verb.endswith("s") and not verb.endswith("ss"):
        verb = verb[:-1]
    else:
        return None
    rest = rest.replace(" their ", " your ").replace(" them", " them")
    return (verb[:1].upper() + verb[1:] + rest).strip()


def stems(s):
    return sorted({stem(w) for w in keywords(s) if not w.isdigit() and w not in ("chapter", "chapters", "ghost", "mission")})


def refine(nodes):
    """Turn unattached present-tense 'If Ghost does X' groups into player
    decisions, and annotate runtime conditions with keyword stems."""
    out = []
    for n in nodes:
        t = n.get("t")
        if t == "choice":
            for o in n["o"]:
                o["b"] = refine(o["b"])
                o["ok"] = stems(o["label"] + " " + o["text"])
        elif t == "cond":
            for b in n["b"]:
                b["n"] = refine(b["n"])
            if not n.get("each") and not n.get("br"):
                acts = [imperative(b["c"]) if b["c"] else None for b in n["b"]]
                if all(acts) and acts:
                    opts = []
                    for a, b in zip(acts, n["b"]):
                        o = {"label": a, "text": "", "b": b["n"]}
                        fx, fl = option_fx(a, "")
                        if fx:
                            o["fx"] = fx
                        if fl:
                            o["f"] = fl
                        o["ok"] = stems(a)
                        opts.append(o)
                    if len(opts) == 1:
                        opts.append({"label": "Keep moving", "text": "", "b": [], "ok": ["keep", "movin"]})
                    out.append({"t": "choice", "p": "", "o": opts, "auto": 1})
                    continue
            for b in n["b"]:
                if b["c"]:
                    b["ck"] = stems(b["c"])
                    if NEG_RE.search(b["c"]):
                        b["neg"] = 1
        out.append(n)
    return out


# -------------------------------------------------- gameplay placement

def place_gameplay(chap, nodes):
    """Convert [GAMEPLAY]/[BOSS ENCOUNTER]/[NEW OBJECTIVE] markers into playable
    operations. Returns number of operations placed."""
    count = [0]
    last_objective = [None]

    def walk(ns, depth):
        out = []
        i = 0
        while i < len(ns):
            n = ns[i]
            t = n.get("t")
            if t == "gp":
                if n["k"] == "BOSS ENCOUNTER":
                    desc = n["v"].title()
                    # absorb an immediately following GAMEPLAY/NEW OBJECTIVE for the boss brief
                    brief = ""
                    j = i + 1
                    while j < len(ns) and j <= i + 2:
                        nn = ns[j]
                        if nn.get("t") == "gp" and nn["k"] == "GAMEPLAY":
                            brief = nn["v"]
                            ns[j] = {"t": "skip"}
                        elif nn.get("t") == "sys" and nn.get("k") == "objective":
                            brief = nn["v"]
                        j += 1
                    out.append({"t": "sys", "k": "boss", "v": desc})
                    out.append({"t": "play", "m": "boss", "d": brief or ("Defeat " + desc), "boss": desc, "k": 1})
                    count[0] += 1
                else:
                    cl = classify(n["v"])
                    out.append({"t": "sys", "k": "objective", "v": n["v"], "h": "Operation"})
                    if cl and depth == 0:
                        out.append({"t": "play", "m": cl[0], "d": n["v"], "k": cl[1]})
                        count[0] += 1
                i += 1
                continue
            if t == "skip":
                i += 1
                continue
            if t == "sys" and n.get("k") == "objective" and n.get("h") == "New Objective":
                last_objective[0] = (len(out), n["v"], depth)
            if t == "choice":
                for o in n["o"]:
                    o["b"] = walk(o["b"], depth + 1)
            if t == "cond":
                for b in n["b"]:
                    b["n"] = walk(b["n"], depth + 1)
            out.append(n)
            i += 1
        return out

    nodes = walk(nodes, 0)

    # Promote action objectives into operations when a chapter has few.
    if count[0] < 2:
        promoted = 0
        res = []
        for n in nodes:
            res.append(n)
            if n.get("t") == "sys" and n.get("k") == "objective" and n.get("h") == "New Objective" and promoted < 2 - count[0]:
                cl = classify(n["v"])
                if cl and cl[0] in ("defend", "infiltrate", "hack", "retrieve", "arena"):
                    res.append({"t": "play", "m": cl[0], "d": n["v"], "k": cl[1]})
                    promoted += 1
        count[0] += promoted
        nodes = res
    return nodes, count[0]


def ensure_operation(chap_id, title, nodes):
    """Chapters with no marked gameplay get an infiltration op at the
    most action-heavy scene so every chapter is playable."""
    scenes = [i for i, n in enumerate(nodes) if n.get("t") == "scene"]
    if not scenes:
        return nodes
    action = re.compile(r"\b(drone|soldier|cleaner|run|chase|escape|attack|fire|shoot|alarm|guard|pursuit|hunt|breach|fight|collapse)", re.I)
    best, best_score = scenes[len(scenes) // 2], -1
    for si, idx in enumerate(scenes):
        end = scenes[si + 1] if si + 1 < len(scenes) else len(nodes)
        text = " ".join(n.get("v", "") for n in nodes[idx:end] if n.get("t") in ("n", "l"))
        sc = len(action.findall(text))
        if sc > best_score:
            best, best_score = idx, sc
    name = nodes[best]["v"]
    # insert after the first few narrative beats of that scene
    ins = best + 1
    k = 0
    while ins < len(nodes) and nodes[ins].get("t") in ("n", "l") and k < 3:
        ins += 1
        k += 1
    mode = "infiltrate" if best_score > 0 else "explore"
    op = [{"t": "sys", "k": "objective", "v": "Get through " + name.title(), "h": "Operation"},
          {"t": "play", "m": mode, "d": "Get through " + name.title(), "k": 3}]
    return nodes[:ins] + op + nodes[ins:]


def chapter_one(nodes):
    """Tutorial escape across the lattice + Warden-3 boss on the rooftop."""
    out = []
    for n in nodes:
        if n.get("t") == "n" and n["v"].startswith("During the confrontation"):
            out.append({"t": "sys", "k": "boss", "v": "Warden-3"})
            out.append({"t": "play", "m": "boss", "boss": "Warden-3", "k": 1,
                        "d": "Break Warden-3's prediction visor. Hack the two relay pylons to drop the shield."})
        out.append(n)
        if n.get("t") == "scene" and n["v"].startswith("NEON HEIGHTS — EXTERIOR"):
            out.append({"t": "sys", "k": "objective", "v": "Escape the tower and reach the rooftop transmitter.", "h": "Operation"})
            out.append({"t": "play", "m": "infiltrate", "k": 2, "tut": 1,
                        "d": "Escape the tower. Reach the rooftop transmitter. Optional: rescue trapped residents."})
    return out


# ---------------------------------------------------------------- main

def act_of(num):
    if num <= 10:
        return 1
    if num <= 20:
        return 2
    if num <= 30:
        return 3
    if num <= 40:
        return 4
    return 5


ACT_TITLES = {1: "Ghosts of the Grid", 2: "Shadow War", 3: "Fractured City",
              4: "Machine Gods", 5: "Ascension"}


def section(lines, start, end):
    return lines[start:end]


def main():
    with open(SRC, encoding="utf-8") as f:
        lines = f.read().split("\n")

    t_start = next(i for i, l in enumerate(lines) if l.strip() == "7. Full Game Transcript")
    transcript = lines[t_start + 2:]

    # Codex: setting premise + ending blurbs + mission synopses
    premise = []
    for l in lines[1:10]:
        if l.strip():
            premise.append(clean(l))
    endings = {}
    for i, l in enumerate(lines):
        m = re.match(r"^Ending ([A-F]) — (.+)$", l.strip())
        if m and i + 1 < len(lines) and lines[i + 1].startswith("Choice:"):
            endings[m.group(1)] = {"title": m.group(2), "desc": clean(lines[i + 1])}
    missions = {}
    for i, l in enumerate(lines[:1270]):
        m = re.match(r"^(?:✓ )?Mission (\d+) — (.+)$", l.strip())
        if m and int(m.group(1)) not in missions:
            body = clean(lines[i + 1]) if i + 1 < len(lines) else ""
            body = re.sub(r"^[A-Z][a-z ]+\.\s", "", body)
            missions[int(m.group(1))] = {"title": m.group(2), "syn": body[:900]}

    toks = tokenize(transcript)
    chapters = []
    cur = None
    chunks = []
    for t in toks:
        if t[0] == "chapter":
            cur = {"id": t[1], "title": t[2], "toks": []}
            chunks.append(cur)
        elif cur is not None:
            cur["toks"].append(t)

    total_ops = 0
    for ch in chunks:
        p = Parser(ch["toks"])
        nodes = []
        while p.peek() is not None:
            before = p.i
            nodes += p.seq(lambda tok, out: False)
            if p.i == before:
                p.i += 1
        nodes = refine(flatten(nodes))
        if ch["id"] == "1":
            nodes = chapter_one(nodes)
        is_ending = bool(re.match(r"^70[A-F]$", ch["id"]))
        nodes, ops = place_gameplay(ch["id"], nodes)
        if ops == 0 and not is_ending and ch["id"] != "1":
            nodes = ensure_operation(ch["id"], ch["title"], nodes)
            ops = 1
        total_ops += ops
        num = int(re.match(r"\d+", ch["id"]).group(0))
        entry = {
            "id": ch["id"], "title": ch["title"], "n": nodes, "ops": ops,
            "ending": ch["id"][-1] if is_ending else None,
        }
        if not is_ending:
            # chapter -> campaign mission mapping (main chapters follow the M1..M50 order)
            entry["act"] = act_of(min(50, round(num * 50 / 69)) if num > 40 else num)
        else:
            entry["act"] = 5
        chapters.append(entry)

    data = {
        "premise": premise,
        "acts": ACT_TITLES,
        "endings": endings,
        "missions": missions,
        "chapters": chapters,
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    with open(HTML, encoding="utf-8") as f:
        html = f.read()
    a, b = html.index(BEGIN) + len(BEGIN), html.index(END)
    html = html[:a] + "window.NV_DATA=" + payload + ";" + html[b:]
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # report
    def count(ns, acc):
        for n in ns:
            acc[n["t"]] = acc.get(n["t"], 0) + 1
            if n["t"] == "choice":
                for o in n["o"]:
                    count(o["b"], acc)
                    count(o.get("post", []), acc)
            if n["t"] == "cond":
                for b in n["b"]:
                    count(b["n"], acc)
        return acc
    acc = {}
    modes = {}
    for c in chapters:
        count(c["n"], acc)

        def m(ns):
            for n in ns:
                if n["t"] == "play":
                    modes[n["m"]] = modes.get(n["m"], 0) + 1
                if n["t"] == "choice":
                    for o in n["o"]:
                        m(o["b"])
                if n["t"] == "cond":
                    for b in n["b"]:
                        m(b["n"])
        m(c["n"])
    print("chapters:", len(chapters), "ops:", total_ops)
    print("nodes:", acc)
    print("modes:", modes)
    print("html bytes:", os.path.getsize(HTML))


if __name__ == "__main__":
    main()
