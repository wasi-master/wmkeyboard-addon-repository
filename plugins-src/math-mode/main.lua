-- Math Mode: type math the way you say it and get real Unicode.
--
--   x^2 -> x²        sqrt(2) -> √2      pi -> π        int_0^1 -> ∫₀¹
--   1/2 -> ½         a/b -> a⁄b         H_2O -> H₂O    \frac{a}{b} -> a⁄b
--   x in RR -> x ∈ ℝ  bb(R) -> 𝐑        f'(x) -> f′(x) 30 deg -> 30°
--
-- Anything it does not understand passes through untouched, and half-typed
-- input never breaks: the whole box is converted again after every keystroke,
-- so `x^` stays `x^` until the `2` arrives.
--
-- Shape of the engine: a byte tokenizer, then one left-to-right pass over a
-- stack of "pieces". Postfix things (^ _ ' ! /) look back at the piece before
-- them; prefix things (sqrt, bb, \frac) wait on the stack until their
-- argument closes. No recursion and no patterns over the whole text, so an
-- 8 KB paste converts inside the per-event budget.
--
-- Strings are bytes here (Lua 5.2, no utf8 library). Glyphs in the Basic
-- Multilingual Plane are written as literals; anything above it (𝐛𝐨𝐥𝐝,
-- 𝑖𝑡𝑎𝑙𝑖𝑐, 𝔣𝔯𝔞𝔨𝔱𝔲𝔯) is emitted as CESU-8 — each UTF-16 half as its own
-- three-byte sequence — because that is what the host's decoder expects.

local byte, char, sub, find = string.byte, string.char, string.sub, string.find
local concat, remove = table.concat, table.remove
local floor = math.floor

-- ================================================================ encoding ==

--- Code point -> UTF-8 (BMP) or CESU-8 (astral).
local function chr(cp)
  if cp < 0x80 then return char(cp) end
  if cp < 0x800 then return char(0xC0 + floor(cp / 0x40), 0x80 + cp % 0x40) end
  if cp < 0x10000 then
    return char(0xE0 + floor(cp / 0x1000), 0x80 + floor(cp / 0x40) % 0x40, 0x80 + cp % 0x40)
  end
  local v = cp - 0x10000
  return chr(0xD800 + floor(v / 0x400)) .. chr(0xDC00 + v % 0x400)
end

--- UTF-16 units in s, which is what every host limit counts. Under CESU-8
--- that is exactly the number of bytes that are not continuation bytes.
local function units(s)
  local n = 0
  for i = 1, #s do
    local b = byte(s, i)
    if b < 0x80 or b >= 0xC0 then n = n + 1 end
  end
  return n
end

local function is_cont(b) return b ~= nil and b >= 0x80 and b < 0xC0 end

--- Index of the last byte of the character that starts at i. A whole
--- multibyte sequence; a CESU-8 high surrogate takes its low surrogate with
--- it; a stray or truncated byte counts as one character on its own.
local function char_end(s, i)
  local b = byte(s, i)
  if not b or b < 0x80 then return i end
  local want = (b >= 0xF0 and 3) or (b >= 0xE0 and 2) or (b >= 0xC0 and 1) or 0
  local e = i
  for j = i + 1, i + want do
    if not is_cont(byte(s, j)) then break end
    e = j
  end
  if b == 0xED and e == i + 2 then
    local b2 = byte(s, i + 1)
    if b2 >= 0xA0 and b2 <= 0xAF and byte(s, i + 3) == 0xED then
      local b5 = byte(s, i + 4)
      if b5 and b5 >= 0xB0 and b5 <= 0xBF and is_cont(byte(s, i + 5)) then e = i + 5 end
    end
  end
  return e
end

--- Code point of the (well-formed, BMP) character spanning i..e; anything
--- else reports as 0x10000, which no table has an entry for.
local function cp_at(s, i, e)
  local b = byte(s, i)
  local len = e - i + 1
  if len == 1 then return b end
  if len == 2 then return (b - 0xC0) * 0x40 + (byte(s, i + 1) - 0x80) end
  if len == 3 then
    return (b - 0xE0) * 0x1000 + (byte(s, i + 1) - 0x80) * 0x40 + (byte(s, i + 2) - 0x80)
  end
  return 0x10000
end

local function is_combining(cp)
  return (cp >= 0x300 and cp <= 0x36F) or (cp >= 0x20D0 and cp <= 0x20FF)
end

--- Splits s into whole characters.
local function chars_of(s)
  local out, i, n = {}, 1, #s
  while i <= n do
    local e = char_end(s, i)
    out[#out + 1] = sub(s, i, e)
    i = e + 1
  end
  return out
end

-- ================================================================== tables ==

local GREEK, GREEK_CP = {}, {}
do
  local names = {
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
    "lambda", "mu", "nu", "xi", "omicron", "pi", "rho", "sigma", "tau", "upsilon", "phi",
    "chi", "psi", "omega",
  }
  local cps = {
    0x3B1, 0x3B2, 0x3B3, 0x3B4, 0x3B5, 0x3B6, 0x3B7, 0x3B8, 0x3B9, 0x3BA,
    0x3BB, 0x3BC, 0x3BD, 0x3BE, 0x3BF, 0x3C0, 0x3C1, 0x3C3, 0x3C4, 0x3C5, 0x3C6,
    0x3C7, 0x3C8, 0x3C9,
  }
  for k, name in ipairs(names) do
    local cp = cps[k]
    GREEK[name] = chr(cp)
    GREEK_CP[name] = cp
    local up = sub(name, 1, 1):upper() .. sub(name, 2)
    GREEK[up] = chr(cp - 0x20)
    GREEK_CP[up] = cp - 0x20
  end
  GREEK.varepsilon = "ε"
  GREEK.vartheta = "ϑ"
  GREEK.varpi = "ϖ"
  GREEK.varrho = "ϱ"
  GREEK.varsigma = "ς"
  GREEK.varphi = "φ"
end

-- LaTeX draws these two differently from the bare words.
local GREEK_CMD = { epsilon = "ϵ", phi = "ϕ" }

-- Words that become a symbol on their own. Anything here is an atom (it can
-- carry ^ and _) unless it is also listed in OP_WORDS below.
local SYM = {
  oo = "∞", infty = "∞", infinity = "∞",
  hbar = "ℏ", ell = "ℓ", aleph = "ℵ", nabla = "∇", grad = "∇", del = "∂", partial = "∂",
  emptyset = "∅", varnothing = "∅",
  RR = "ℝ", NN = "ℕ", ZZ = "ℤ", QQ = "ℚ", CC = "ℂ", HH = "ℍ", PP = "ℙ", FF = chr(0x1D53D),
  AA = "∀", EE = "∃",
  times = "×", cross = "×", xx = "×", cdot = "⋅", div = "÷",
  pm = "±", mp = "∓", leq = "≤", le = "≤", geq = "≥", ge = "≥", neq = "≠", ne = "≠",
  approx = "≈", equiv = "≡", propto = "∝", sim = "∼", simeq = "≃", cong = "≅",
  notin = "∉", ni = "∋", subset = "⊂", subseteq = "⊆", supset = "⊃", supseteq = "⊇",
  union = "∪", cup = "∪", intersect = "∩", cap = "∩", setminus = "∖",
  bigcup = "⋃", bigcap = "⋂", bigoplus = "⨁", bigotimes = "⨂", oplus = "⊕", otimes = "⊗",
  forall = "∀", exists = "∃", nexists = "∄", therefore = "∴", because = "∵",
  implies = "⇒", iff = "⇔", xor = "⊻", nand = "⊼", nor = "⊽", neg = "¬",
  top = "⊤", bot = "⊥",
  sum = "∑", prod = "∏", coprod = "∐", int = "∫", integral = "∫", iint = "∬", iiint = "∭",
  oint = "∮",
  perp = "⊥", parallel = "∥", circ = "∘", bullet = "•", star = "⋆", dagger = "†",
  cdots = "⋯", vdots = "⋮", ddots = "⋱", ldots = "…",
  permil = "‰", qed = "∎", blacksquare = "■", triangle = "△", diamond = "◇",
  langle = "⟨", rangle = "⟩", lfloor = "⌊", rfloor = "⌋", lceil = "⌈", rceil = "⌉",
}

-- Only reachable with a backslash: too English, or LaTeX-only spellings.
local SYM_CMD = {
  to = "→", ["in"] = "∈", land = "∧", lor = "∨", lnot = "¬", wedge = "∧", vee = "∨",
  rightarrow = "→", leftarrow = "←", Rightarrow = "⇒", Leftarrow = "⇐",
  leftrightarrow = "↔", Leftrightarrow = "⇔", mapsto = "↦", longrightarrow = "⟶",
  degree = "°", prime = "′", square = "□", Box = "□", dots = "…", mid = "∣",
  ["and"] = "∧", ["or"] = "∨", ["not"] = "¬", vdash = "⊢", models = "⊨",
}

-- Symbols that behave as operators: never a base for ^ or _, never a fraction
-- operand.
local OP_WORDS = {}
for _, w in ipairs({
  "times", "cross", "xx", "cdot", "div", "pm", "mp", "leq", "le", "geq", "ge", "neq", "ne",
  "approx", "equiv", "propto", "sim", "simeq", "cong", "notin", "ni", "subset", "subseteq",
  "supset", "supseteq", "union", "cup", "intersect", "cap", "setminus", "oplus", "otimes",
  "implies", "iff", "xor", "nand", "nor", "neg", "perp", "parallel", "circ", "bullet", "star",
  "forall", "exists", "nexists", "therefore", "because", "AA", "EE", "top", "bot",
  "to", "in", "land", "lor", "lnot", "wedge", "vee", "rightarrow", "leftarrow", "Rightarrow",
  "Leftarrow", "leftrightarrow", "Leftrightarrow", "mapsto", "longrightarrow", "and", "or",
  "not", "vdash", "models", "mid", "langle", "rangle", "lfloor", "rfloor", "lceil", "rceil",
}) do OP_WORDS[w] = true end

-- English words that are operators only when the user asks for it.
local WORD_OPS = { ["and"] = "∧", ["or"] = "∨", ["not"] = "¬", ["to"] = "→" }

-- Function names stay as text. They matter in two places: `sin^2` reads as
-- sin², and `e^ln(x)` must not turn into eˡⁿ(x).
local FUNCS = {}
for _, w in ipairs({
  "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh",
  "tanh", "ln", "log", "exp", "lim", "max", "min", "sup", "inf", "det", "dim", "ker", "gcd",
  "lcm", "arg", "deg", "mod", "argmax", "argmin", "sgn", "tr", "rank", "span", "Re", "Im",
  "limsup", "liminf",
}) do FUNCS[w] = true end
local STRICT_FUNCS = {}
for _, w in ipairs({
  "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh",
  "tanh", "ln", "log", "exp",
}) do STRICT_FUNCS[w] = true end

local ACCENT = {
  vec = chr(0x20D7), hat = chr(0x302), bar = chr(0x304), conj = chr(0x304),
  dot = chr(0x307), ddot = chr(0x308), tilde = chr(0x303), overline = chr(0x305),
  underline = chr(0x332), check = chr(0x30C), breve = chr(0x306), acute = chr(0x301),
  grave = chr(0x300), widehat = chr(0x302), widetilde = chr(0x303),
}
local WRAP = {
  abs = { "|", "|" }, norm = { "‖", "‖" }, floor = { "⌊", "⌋" }, ceil = { "⌈", "⌉" },
}
local STYLE = {
  bold = { up = 0x1D400, lo = 0x1D41A, dg = 0x1D7CE, gup = 0x1D6A8, glo = 0x1D6C2 },
  italic = { up = 0x1D434, lo = 0x1D44E, gup = 0x1D6E2, glo = 0x1D6FC, ex = { h = 0x210E } },
  script = {
    up = 0x1D49C, lo = 0x1D4B6,
    ex = { B = 0x212C, E = 0x2130, F = 0x2131, H = 0x210B, I = 0x2110, L = 0x2112, M = 0x2133,
      R = 0x211B, e = 0x212F, g = 0x210A, o = 0x2134 },
  },
  fraktur = { up = 0x1D504, lo = 0x1D51E, ex = { C = 0x212D, H = 0x210C, I = 0x2111, R = 0x211C, Z = 0x2128 } },
  double = {
    up = 0x1D538, lo = 0x1D552, dg = 0x1D7D8,
    ex = { C = 0x2102, H = 0x210D, N = 0x2115, P = 0x2119, Q = 0x211A, R = 0x211D, Z = 0x2124 },
  },
  sans = { up = 0x1D5A0, lo = 0x1D5BA, dg = 0x1D7E2 },
  mono = { up = 0x1D670, lo = 0x1D68A, dg = 0x1D7F6 },
}
local STYLE_NAME = {
  bb = "bold", bf = "bold", mathbf = "bold", textbf = "bold",
  it = "italic", mathit = "italic",
  cc = "script", cal = "script", mathcal = "script", mathscr = "script",
  fr = "fraktur", mathfrak = "fraktur",
  bbb = "double", mathbb = "double",
  sf = "sans", mathsf = "sans",
  tt = "mono", mathtt = "mono",
}
-- \text{...} and friends: the inside is left exactly as typed.
local VERBATIM_CMD = { text = true, mathrm = true, operatorname = true, textrm = true, mbox = true }

-- Prefix functions. `bare` ones also take a single atom without brackets
-- (`sqrt 2`); `glyph` ones show their symbol as soon as they are typed.
local PREFIX = {}
for _, w in ipairs({ "root", "abs", "norm", "floor", "ceil", "binom", "frac", "dfrac", "tfrac" }) do
  PREFIX[w] = true
end
for name in pairs(ACCENT) do PREFIX[name] = true end
for name in pairs(STYLE_NAME) do PREFIX[name] = true end
PREFIX.sqrt = true
PREFIX.cbrt = true
local ROOT_GLYPH = { sqrt = "√", cbrt = "∛" }
local ROOT_BY_INDEX = { ["2"] = "√", ["3"] = "∛", ["4"] = "∜" }

local SUP, SUB, SCRIPT_GLYPH = {}, {}, {}
do
  local function load(map, pairs_)
    for _, p in ipairs(pairs_) do
      map[p[1]] = p[2]
      SCRIPT_GLYPH[p[2]] = true
    end
  end
  load(SUP, {
    { "0", "⁰" }, { "1", "¹" }, { "2", "²" }, { "3", "³" }, { "4", "⁴" }, { "5", "⁵" },
    { "6", "⁶" }, { "7", "⁷" }, { "8", "⁸" }, { "9", "⁹" },
    { "+", "⁺" }, { "-", "⁻" }, { "=", "⁼" }, { "(", "⁽" }, { ")", "⁾" },
    { "a", "ᵃ" }, { "b", "ᵇ" }, { "c", "ᶜ" }, { "d", "ᵈ" }, { "e", "ᵉ" }, { "f", "ᶠ" },
    { "g", "ᵍ" }, { "h", "ʰ" }, { "i", "ⁱ" }, { "j", "ʲ" }, { "k", "ᵏ" }, { "l", "ˡ" },
    { "m", "ᵐ" }, { "n", "ⁿ" }, { "o", "ᵒ" }, { "p", "ᵖ" }, { "r", "ʳ" }, { "s", "ˢ" },
    { "t", "ᵗ" }, { "u", "ᵘ" }, { "v", "ᵛ" }, { "w", "ʷ" }, { "x", "ˣ" }, { "y", "ʸ" },
    { "z", "ᶻ" },
    { "A", "ᴬ" }, { "B", "ᴮ" }, { "D", "ᴰ" }, { "E", "ᴱ" }, { "G", "ᴳ" }, { "H", "ᴴ" },
    { "I", "ᴵ" }, { "J", "ᴶ" }, { "K", "ᴷ" }, { "L", "ᴸ" }, { "M", "ᴹ" }, { "N", "ᴺ" },
    { "O", "ᴼ" }, { "P", "ᴾ" }, { "R", "ᴿ" }, { "T", "ᵀ" }, { "U", "ᵁ" }, { "V", "ⱽ" },
    { "W", "ᵂ" },
    { "β", "ᵝ" }, { "γ", "ᵞ" }, { "δ", "ᵟ" }, { "ε", "ᵋ" }, { "θ", "ᶿ" }, { "ι", "ᶥ" },
    { "φ", "ᵠ" }, { "χ", "ᵡ" },
  })
  load(SUB, {
    { "0", "₀" }, { "1", "₁" }, { "2", "₂" }, { "3", "₃" }, { "4", "₄" }, { "5", "₅" },
    { "6", "₆" }, { "7", "₇" }, { "8", "₈" }, { "9", "₉" },
    { "+", "₊" }, { "-", "₋" }, { "=", "₌" }, { "(", "₍" }, { ")", "₎" },
    { "a", "ₐ" }, { "e", "ₑ" }, { "h", "ₕ" }, { "i", "ᵢ" }, { "j", "ⱼ" }, { "k", "ₖ" },
    { "l", "ₗ" }, { "m", "ₘ" }, { "n", "ₙ" }, { "o", "ₒ" }, { "p", "ₚ" }, { "r", "ᵣ" },
    { "s", "ₛ" }, { "t", "ₜ" }, { "u", "ᵤ" }, { "v", "ᵥ" }, { "x", "ₓ" },
    { "β", "ᵦ" }, { "γ", "ᵧ" }, { "ρ", "ᵨ" }, { "φ", "ᵩ" }, { "χ", "ᵪ" },
  })
end

local VULGAR = {
  ["1/2"] = "½", ["1/3"] = "⅓", ["2/3"] = "⅔", ["1/4"] = "¼", ["3/4"] = "¾",
  ["1/5"] = "⅕", ["2/5"] = "⅖", ["3/5"] = "⅗", ["4/5"] = "⅘", ["1/6"] = "⅙", ["5/6"] = "⅚",
  ["1/7"] = "⅐", ["1/8"] = "⅛", ["3/8"] = "⅜", ["5/8"] = "⅝", ["7/8"] = "⅞", ["1/9"] = "⅑",
  ["1/10"] = "⅒",
}

-- Longest match first. `<-` in front of a digit is handled in the tokenizer.
local OPS = {
  { "<==>", "⇔" }, { "<-->", "⟷" },
  { "<=>", "⇔" }, { "<->", "↔" }, { "-->", "⟶" }, { "<--", "⟵" }, { "==>", "⇒" },
  { "<==", "⇐" }, { "|->", "↦" }, { "|--", "⊢" }, { "|==", "⊨" }, { "===", "≡" },
  { "=/=", "≠" }, { "+/-", "±" }, { "-/+", "∓" }, { "...", "…" },
  { "<=", "≤" }, { ">=", "≥" }, { "!=", "≠" }, { "<>", "≠" }, { "~=", "≅" }, { "~~", "≈" },
  { "->", "→" }, { "<-", "←" }, { "=>", "⇒" }, { "+-", "±" }, { "-+", "∓" }, { "**", "**" },
  { "||", "‖" }, { "<<", "≪" }, { ">>", "≫" }, { ":=", "≔" }, { "=:", "≕" }, { "-:", "÷" },
}

local ELEMENTS = {}
for w in ([[H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn
  Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm
  Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U
  Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og]]):gmatch("%a+") do
  ELEMENTS[w] = true
end

-- ============================================================== tokenizer ==

local function is_digit(b) return b ~= nil and b >= 48 and b <= 57 end
local function is_upper(b) return b ~= nil and b >= 65 and b <= 90 end
local function is_lower(b) return b ~= nil and b >= 97 and b <= 122 end
local function is_alpha(b) return is_upper(b) or is_lower(b) end
local function is_alnum(b) return is_alpha(b) or is_digit(b) end
local function is_space(b) return b == 32 or b == 9 or b == 10 or b == 13 end

local MAX_SPLIT = 10 -- longest word that splits off a digit: "varepsilon0"

--- `sqrt2` is `sqrt` and `2`; `DeltaH` is `Delta` and `H`. Never letter to
--- letter (`pixel`, `sqrtx`), and only for names the engine knows.
local function split_point(word)
  local n = #word
  local limit = n - 1
  if limit > MAX_SPLIT then limit = MAX_SPLIT end
  for len = limit, 2, -1 do
    local head = sub(word, 1, len)
    local nb = byte(word, len + 1)
    if is_digit(nb) then
      if SYM[head] or GREEK[head] or PREFIX[head] then return len end
    elseif is_upper(nb) then
      if GREEK[head] then return len end
    end
  end
  -- nZZ, xRR: a lowercase run followed by one of the blackboard sets
  if n >= 3 and n <= 4 then
    local tail = sub(word, n - 1)
    local head = sub(word, 1, n - 2)
    if SYM[tail] and is_upper(byte(tail)) and is_upper(byte(tail, 2)) and not find(head, "[^%l]") then
      return n - 2
    end
  end
  return nil
end

--- Splits text into tokens {k=kind, v=text, s=start, e=end}.
--- Kinds: num word cmd quote verb op open close ws raw other.
local function tokenize(text)
  local toks = {}
  local n = #text
  local i = 1
  local function push(k, v, s, e)
    local t = { k = k, v = v, s = s, e = e }
    toks[#toks + 1] = t
    return t
  end
  while i <= n do
    local b = byte(text, i)
    if is_space(b) then
      local j, nl = i, false
      while j <= n do
        local c = byte(text, j)
        if c == 10 or c == 13 then nl = true elseif c ~= 32 and c ~= 9 then break end
        j = j + 1
      end
      push("ws", sub(text, i, j - 1), i, j - 1).nl = nl
      i = j
    elseif is_digit(b) or (b == 46 and is_digit(byte(text, i + 1))) then
      local j = i
      while is_digit(byte(text, j)) do j = j + 1 end
      if byte(text, j) == 46 and is_digit(byte(text, j + 1)) then
        j = j + 1
        while is_digit(byte(text, j)) do j = j + 1 end
      end
      local c = byte(text, j)
      if c == 101 or c == 69 then
        local k = j + 1
        local d = byte(text, k)
        if d == 43 or d == 45 then k = k + 1 end
        if is_digit(byte(text, k)) then
          while is_digit(byte(text, k)) do k = k + 1 end
          j = k
        end
      end
      push("num", sub(text, i, j - 1), i, j - 1)
      i = j
    elseif is_alpha(b) then
      local j = i + 1
      while is_alnum(byte(text, j)) do j = j + 1 end
      local word = sub(text, i, j - 1)
      local cut = split_point(word)
      if cut then
        push("word", sub(word, 1, cut), i, i + cut - 1)
        i = i + cut
      else
        push("word", word, i, j - 1)
        i = j
      end
    elseif b == 92 then -- backslash
      local c = byte(text, i + 1)
      if is_alpha(c) then
        local j = i + 2
        while is_alpha(byte(text, j)) do j = j + 1 end
        push("cmd", sub(text, i + 1, j - 1), i, j - 1)
        i = j
      elseif c and c ~= 92 and c ~= 32 and c < 0x80 and not is_alnum(c) and not is_space(c) then
        push("cmd", sub(text, i + 1, i + 1), i, i + 1)
        i = i + 2
      else
        push("other", "\\", i, i)
        i = i + 1
      end
    elseif b == 34 then -- a "quoted" region is left exactly as typed
      local j = find(text, '"', i + 1, true)
      if j then
        push("quote", sub(text, i + 1, j - 1), i, j)
        i = j + 1
      else
        push("verb", sub(text, i), i, n)
        i = n + 1
      end
    elseif b == 40 or b == 91 or b == 123 then
      push("open", char(b), i, i)
      i = i + 1
    elseif b == 41 or b == 93 or b == 125 then
      push("close", char(b), i, i)
      i = i + 1
    elseif b >= 0x80 then
      local j = i
      while j <= n and byte(text, j) >= 0x80 do j = char_end(text, j) + 1 end
      local run = sub(text, i, j - 1)
      local prev = toks[#toks]
      local first_end = char_end(text, i)
      if prev and (prev.k == "word" or prev.k == "raw") and prev.e == i - 1
        and is_combining(cp_at(text, i, first_end)) then
        prev.v = prev.v .. run
        prev.k = "raw"
        prev.e = j - 1
      else
        push("raw", run, i, j - 1)
      end
      i = j
    else
      local matched = false
      for _, op in ipairs(OPS) do
        local key = op[1]
        local len = #key
        if sub(text, i, i + len - 1) == key then
          local j = i + len
          if key == "..." and byte(text, j) == 46 then
            while byte(text, j) == 46 do j = j + 1 end
            push("other", sub(text, i, j - 1), i, j - 1)
          elseif key == "**" and byte(text, j) == 42 then
            while byte(text, j) == 42 do j = j + 1 end
            push("other", sub(text, i, j - 1), i, j - 1)
          elseif key == "<-" and (is_digit(byte(text, j)) or byte(text, j) == 46) then
            push("op", "<", i, i)
            j = i + 1
          else
            push("op", key, i, j - 1).glyph = op[2]
          end
          i = j
          matched = true
          break
        end
      end
      if not matched then
        push("op", char(b), i, i)
        i = i + 1
      end
    end
  end
  return toks
end

-- ================================================================ helpers ==

--- Every character of s (spaces excepted) has a form in map.
local function scriptable(s, map)
  if s == "" then return false end
  local seen = false
  for _, c in ipairs(chars_of(s)) do
    if c ~= " " and c ~= "\t" then
      if not map[c] then return false end
      seen = true
    end
  end
  return seen
end

local function map_script(s, map)
  local out = {}
  for _, c in ipairs(chars_of(s)) do
    if c ~= " " and c ~= "\t" then out[#out + 1] = map[c] end
  end
  return concat(out)
end

--- s consists only of superscript/subscript glyphs already.
local function all_script(s)
  if s == "" then return false end
  for _, c in ipairs(chars_of(s)) do
    if not SCRIPT_GLYPH[c] then return false end
  end
  return true
end

local function is_plain_digits(s)
  if s == "" then return false end
  for i = 1, #s do
    if not is_digit(byte(s, i)) then return false end
  end
  return true
end

local function styled(s, style)
  local st = STYLE[style]
  local out = {}
  for _, c in ipairs(chars_of(s)) do
    local b = byte(c)
    local cp
    if #c == 1 then
      if st.ex and st.ex[c] then cp = st.ex[c]
      elseif is_upper(b) then cp = st.up + (b - 65)
      elseif is_lower(b) then cp = st.lo + (b - 97)
      elseif is_digit(b) and st.dg then cp = st.dg + (b - 48)
      end
    elseif #c == 2 then
      local g = cp_at(c, 1, 2)
      if st.glo and g >= 0x3B1 and g <= 0x3C9 then cp = st.glo + (g - 0x3B1)
      elseif st.gup and g >= 0x391 and g <= 0x3A9 then cp = st.gup + (g - 0x391)
      end
    end
    out[#out + 1] = cp and chr(cp) or c
  end
  return concat(out)
end

local function accented(s, mark)
  local out = {}
  for _, c in ipairs(chars_of(s)) do
    out[#out + 1] = c
    if c ~= " " then out[#out + 1] = mark end
  end
  return concat(out)
end

local function prime_run(n)
  local out = {}
  while n >= 4 do
    out[#out + 1] = "⁗"
    n = n - 4
  end
  if n == 3 then out[#out + 1] = "‴" elseif n == 2 then out[#out + 1] = "″" elseif n == 1 then out[#out + 1] = "′" end
  return concat(out)
end

-- =============================================================== renderer ==

local DEFAULTS = {
  minus = true, times = true, frac = true, small = true, words = false,
  prime = true, chem = false, italic = false, rootline = false,
}
OPTION_KEYS = { "minus", "times", "frac", "small", "words", "prime", "chem", "italic", "rootline" }

function default_options()
  local o = {}
  for k, v in pairs(DEFAULTS) do o[k] = v end
  return o
end

local MAX_DEPTH = 32

--- The engine. text in, Unicode out. Never throws for any input; the caller
--- still wraps it in pcall because "never" is a strong word.
local function render_math(text, o)
  local toks = tokenize(text)
  local nt = #toks
  local out = {}   -- the piece stack
  local opens = {} -- indices of open-bracket markers in `out`
  local i = 1

  -- ---- small accessors -------------------------------------------------

  local function top() return out[#out] end

  --- Next non-whitespace token after index k, plus whether any whitespace
  --- was skipped and whether it held a newline.
  local function peek(k)
    local j = k + 1
    local ws, nl = false, false
    while j <= nt and toks[j].k == "ws" do
      ws = true
      nl = nl or toks[j].nl
      j = j + 1
    end
    return toks[j], j, ws, nl
  end

  local function tok_is_atom_start(t)
    return t and (t.k == "num" or t.k == "word" or t.k == "raw" or t.k == "cmd" or t.k == "open"
      or t.k == "quote")
  end

  local function is_base(p)
    return p and (p.atom or p.bar) and not p.pend
  end

  local function literal(t, src)
    src = src or t
    return { t = t, src = src, kind = "lit", supok = SUP[src] ~= nil, subok = SUB[src] ~= nil }
  end

  local function atom(t, src, kind)
    return {
      t = t, src = src, atom = true, kind = kind,
      supok = scriptable(src, SUP), subok = scriptable(src, SUB),
    }
  end

  local function literalize(p)
    p.pend = nil
    p.atom = false
    p.kind = "lit"
    if p.ws_before then p.t = p.ws_before .. p.t end
    if p.ws_after then p.t = p.t .. p.ws_after end
    p.ws_before, p.ws_after = nil, nil
    p.supok, p.subok = false, false
  end

  local function in_arg_group()
    local m = opens[#opens]
    return m and out[m].arg
  end

  -- ---- building blocks -------------------------------------------------

  --- Builds a fraction piece from two operand pieces.
  local function make_frac(left, right, chain, allow_small, parens_rule)
    local lt, rt = left.t, right.t
    if parens_rule then
      if left.grp and left.has_op then lt = "(" .. left.inner_t .. ")" elseif left.grp then lt = left.inner_t end
      if right.grp and right.has_op then rt = "(" .. right.inner_t .. ")" elseif right.grp then rt = right.inner_t end
    end
    local p = { atom = true, kind = "frac", mod = "frac", supok = false, subok = false }
    p.src = left.src .. "/" .. right.src
    local plain = not chain and allow_small and o.small
      and left.kind == "num" and right.kind == "num" and not left.mod and not right.mod
      and not left.signed and not right.signed and not left.juxt
      and is_plain_digits(left.src) and is_plain_digits(right.src)
    if plain then
      local v = VULGAR[left.src .. "/" .. right.src]
      p.t = v or (map_script(left.src, SUP) .. "⁄" .. map_script(right.src, SUB))
      p.vulgar = true
    elseif chain then
      p.t = lt .. "/" .. rt
      p.chain = true
    elseif o.frac then
      p.t = lt .. "⁄" .. rt
    else
      p.t = lt .. "/" .. rt
    end
    return p
  end

  local function make_binom(n, k)
    if n.supok and k.subok then
      return atom("(" .. map_script(n.src, SUP) .. map_script(k.src, SUB) .. ")", "(" .. n.src .. " " .. k.src .. ")", "binom")
    end
    return nil
  end

  --- Merges base, pend(^/_), arg at k-1, k, k+1 into one atom at k-1.
  local function attach_at(k)
    local base, pend, arg = out[k - 1], out[k], out[k + 1]
    local sup = pend.pend == "sup"
    local map = sup and SUP or SUB
    local ok = sup and arg.supok or (not sup and arg.subok)
    if arg.guard then ok = false end
    local m = { atom = true, kind = base.kind, mod = sup and "sup" or "sub", bar = base.bar,
      supok = false, subok = false }
    if arg.circ and sup then
      m.t = base.t .. "°"
    elseif arg.primecmd and sup then
      m.t = base.t .. "′"
    elseif arg.kind == "raw" and all_script(arg.t) then
      m.t = base.t .. arg.t
    elseif ok then
      local bt = base.t
      if sup and base.kind == "root" and not base.mod then bt = "(" .. bt .. ")" end
      m.t = bt .. map_script(arg.grp and arg.inner_src or arg.src, map)
    else
      local inner
      if arg.grp then
        inner = arg.single and arg.inner_t or arg.t
      elseif arg.mod or arg.kind == "frac" then
        inner = "(" .. arg.t .. ")"
      else
        inner = arg.t
      end
      m.t = base.t .. pend.t .. inner
    end
    m.src = base.src .. pend.src .. arg.src
    out[k - 1] = m
    remove(out, k + 1)
    remove(out, k)
  end

  --- Applies the pending prefix function at k to the atom at k+1. Returns
  --- true when it consumed the atom (or kept waiting with it absorbed).
  local function apply_at(k)
    local fn, arg = out[k], out[k + 1]
    local name = fn.name
    local function consume(p)
      out[k] = p
      remove(out, k + 1)
    end
    local function absorb() -- multi-argument function: keep waiting
      fn.t = fn.t .. arg.t
      fn.src = fn.src .. arg.src
      remove(out, k + 1)
    end
    if fn.family == "root" then
      if name == "root" and not fn.index then
        if arg.grp then fn.index = arg; absorb(); return true end
        literalize(fn); return false
      end
      if (name == "sqrt") and not fn.index and arg.grp and arg.bracket == "[" then
        fn.index = arg; absorb(); return true
      end
      if not arg.grp and not fn.bare then literalize(fn); return false end
      local glyph = fn.glyph
      if fn.index then
        local idx = fn.index
        local key = idx.single and idx.inner_src or nil
        glyph = key and ROOT_BY_INDEX[key]
        if not glyph then
          if idx.supok then glyph = map_script(idx.inner_src, SUP) .. "√" else literalize(fn); return false end
        end
      end
      local body
      if arg.grp then
        if arg.single and arg.inner_mod ~= "sup" and arg.inner_mod ~= "prime" and arg.inner_kind ~= "frac" then
          body = arg.inner_t
        elseif o.rootline then
          body = accented(arg.inner_t, chr(0x305))
        else
          body = "(" .. arg.inner_t .. ")"
        end
      else
        body = arg.t
      end
      local p = { t = glyph .. body, src = fn.src .. arg.src, atom = true, kind = "root", supok = false, subok = false }
      consume(p)
      return true
    elseif fn.family == "accent" then
      if arg.grp and arg.simple then
        consume({ t = accented(arg.inner_t, ACCENT[name]), src = arg.inner_src, atom = true, kind = "accent", supok = false, subok = false })
        return true
      end
      literalize(fn); return false
    elseif fn.family == "wrap" then
      if arg.grp then
        local w = WRAP[name]
        consume({ t = w[1] .. arg.inner_t .. w[2], src = fn.src .. arg.src, atom = true, kind = "wrap", supok = false, subok = false })
        return true
      end
      literalize(fn); return false
    elseif fn.family == "style" then
      if arg.grp and arg.inner_t ~= "" then
        consume({ t = styled(arg.inner_t, STYLE_NAME[name]), src = arg.inner_src, atom = true, kind = "style", supok = false, subok = false })
        return true
      end
      literalize(fn); return false
    elseif fn.family == "binom" then
      if not arg.grp then literalize(fn); return false end
      if arg.pair then
        local p = make_binom(arg.pair[1], arg.pair[2])
        if p then consume(p); return true end
        literalize(fn); return false
      end
      if not fn.num then fn.num = arg; absorb(); return true end
      local num = fn.num.single and fn.num.single_piece
      local den = arg.single and arg.single_piece
      local p = num and den and make_binom(num, den)
      if p then consume(p); return true end
      literalize(fn); return false
    elseif fn.family == "frac" then
      if not arg.grp then literalize(fn); return false end
      if not fn.num then fn.num = arg; absorb(); return true end
      local num, den = fn.num, arg
      local p = make_frac(num.single and num.single_piece or num, den.single and den.single_piece or den, false, true, true)
      consume(p)
      return true
    end
    literalize(fn)
    return false
  end

  --- Resolves every pending piece from the top of the stack down to index
  --- lo: attach what has an argument, spell out what does not.
  local function flush(lo)
    local k = #out
    while k >= lo do
      local p = out[k]
      if p and p.pend then
        local nxt = out[k + 1]
        if p.pend == "open" then
          literalize(p)
        elseif nxt and nxt.atom then
          if p.pend == "sup" or p.pend == "sub" then
            attach_at(k)
          elseif p.pend == "fn" then
            apply_at(k)
          elseif p.pend == "frac" then
            local left = out[k - 1]
            if is_base(left) then
              local f = make_frac(left, nxt, false, not in_arg_group(), false)
              out[k - 1] = f
              remove(out, k + 1)
              remove(out, k)
            else
              literalize(p)
            end
          end
        else
          literalize(p)
        end
      end
      k = k - 1
    end
  end

  --- After an atom lands on top: attach pending ^ _ / and prefix functions
  --- below it, unless something to the right should bind first.
  local function settle()
    while true do
      local k = #out
      local a = out[k]
      if not (a and a.atom) then return end
      local below = out[k - 1]
      local nxt, _, ws, nl = peek(i)
      if nxt and nxt.k == "op" and (nxt.v == "'" or nxt.v == "!") and not ws then return end
      local coming = nxt and nxt.k == "op" and (nxt.v == "^" or nxt.v == "_" or nxt.v == "**") and not nl
      if coming then
        local pend_sup = below and below.pend == "sup"
        if below and (below.pend == "sup" or below.pend == "sub") and not (pend_sup and nxt.v ~= "_") then
          attach_at(k - 1)
        elseif below and below.pend == "fn" then
          if not apply_at(k - 1) then return end
        else
          return
        end
      elseif below and below.pend then
        if below.pend == "sup" or below.pend == "sub" then
          attach_at(k - 1)
        elseif below.pend == "fn" then
          if not apply_at(k - 1) then return end
        elseif below.pend == "frac" then
          local left = out[k - 2]
          if is_base(left) then
            local chain = nxt and nxt.k == "op" and nxt.v == "/" and not ws
            local f = make_frac(left, a, chain, not in_arg_group(), false)
            out[k - 2] = f
            remove(out, k)
            remove(out, k - 1)
          else
            literalize(below)
            return
          end
        else
          return
        end
      else
        return
      end
    end
  end

  --- Before a postfix (' or !) lands on the top atom, anything pending right
  --- under it — a ^, a _, or a prefix function — binds first.
  local function resolve_below(tp)
    while tp and tp.atom do
      local below = out[#out - 1]
      if below and (below.pend == "sup" or below.pend == "sub") then
        attach_at(#out - 1)
      elseif below and below.pend == "fn" then
        if not apply_at(#out - 1) then break end
      else
        break
      end
      tp = top()
    end
    return tp
  end

  --- Pushes an atom, merging a waiting sign into it first.
  local function push_atom(p)
    local tp = out[#out]
    if tp and tp.sign then
      out[#out] = nil
      p.t = tp.t .. p.t
      p.src = tp.src .. p.src
      p.signed = true
    end
    local prev = toks[i - 1]
    if prev and (prev.k == "num" or prev.k == "word" or prev.k == "raw" or prev.k == "close" or prev.k == "quote") then
      p.juxt = true
    end
    out[#out + 1] = p
    settle()
  end

  local function push_pend(p)
    out[#out + 1] = p
  end

  --- Skips one whitespace run (no newline) after the current token when a
  --- usable argument follows; remembers it for the literal fallback.
  local function skip_ws_after(p, want_atom)
    local nx = toks[i + 1]
    if nx and nx.k == "ws" and not nx.nl then
      local after = toks[i + 2]
      if after and (after.k == "open" or (want_atom and tok_is_atom_start(after))) then
        p.ws_after = nx.v
        i = i + 1
      end
    end
  end

  local function push_prefix(name, family, t, src, glyph, bare)
    local p = { pend = "fn", name = name, family = family, t = t, src = src, glyph = glyph, bare = bare }
    push_pend(p)
    skip_ws_after(p, bare)
  end

  --- Symbol lookup for a word or a backslash command.
  local function symbol_for(word, is_cmd)
    local g = is_cmd and GREEK_CMD[word] or nil
    g = g or GREEK[word] or SYM[word]
    if not g and is_cmd then g = SYM_CMD[word] end
    return g
  end

  local function push_symbol(word, glyph, is_cmd)
    if OP_WORDS[word] then
      out[#out + 1] = { t = glyph, src = word, kind = "op" }
    else
      local p = atom(glyph, glyph, "sym")
      if word == "circ" then p.circ = true end
      push_atom(p)
    end
  end

  --- Closes the group whose marker sits at index m.
  local function close_group(m, closer)
    flush(m + 1)
    local marker = out[m]
    local inner = {}
    for k = m + 1, #out do inner[#inner + 1] = out[k] end
    local tt, ss = {}, {}
    local count, has_op, simple, supok, subok = 0, false, true, true, true
    local last_atom
    for _, p in ipairs(inner) do
      tt[#tt + 1] = p.t
      ss[#ss + 1] = p.src or p.t
      if p.kind ~= "ws" then
        count = count + 1
        if p.atom then
          last_atom = p
          if p.mod or not (p.kind == "num" or p.kind == "word" or p.kind == "sym" or p.kind == "raw") then simple = false end
        else
          has_op = true
          simple = false
        end
        if not p.supok then supok = false end
        if not p.subok then subok = false end
      else
        simple = false
      end
    end
    -- (n choose k) and (a, b) shapes for binomials
    local pair
    if #inner == 5 and inner[1].atom and inner[3].kind == "word" and inner[3].t == "choose" and inner[5].atom then
      pair = { inner[1], inner[5] }
    elseif #inner == 3 and inner[1].atom and inner[2].src == "," and inner[3].atom then
      pair = { inner[1], inner[3] }
    end
    for k = #out, m, -1 do out[k] = nil end
    opens[#opens] = nil
    local inner_t = concat(tt)
    local g = {
      atom = true, grp = true, bracket = marker.bracket, kind = "grp",
      inner_t = inner_t, inner_src = concat(ss),
      t = marker.bracket .. inner_t .. closer,
      src = marker.bracket .. concat(ss) .. closer,
      has_op = has_op, simple = simple and count > 0,
      single = count == 1 and last_atom ~= nil and not has_op,
      supok = supok and count > 0, subok = subok and count > 0,
      pair = pair,
    }
    if g.single then
      g.single_piece = last_atom
      g.inner_mod = last_atom.mod
      g.inner_kind = last_atom.kind
      if last_atom.circ then g.circ = true end
      if last_atom.kind == "frac" then g.single = false end
    end
    if pair and #inner == 5 then
      local b = make_binom(pair[1], pair[2])
      if b then push_atom(b); return end
    end
    push_atom(g)
  end

  -- ---- the pass -------------------------------------------------------

  while i <= nt do
    local tk = toks[i]
    local k, v = tk.k, tk.v

    if k == "ws" then
      out[#out + 1] = { t = v, src = v, kind = "ws", supok = true, subok = true }

    elseif k == "num" then
      local p = atom(v, v, "num")
      local prev = toks[i - 1]
      if o.chem and prev and prev.k == "close" and is_plain_digits(v) then
        p.t = map_script(v, SUB)
        p.mod = "sub"
        p.supok, p.subok = false, false
      end
      push_atom(p)

    elseif k == "raw" or k == "quote" or k == "verb" then
      if k == "quote" and v == "" then
        out[#out + 1] = literal('""')
      else
        local p = atom(v, v, k == "raw" and "raw" or "quote")
        if k ~= "raw" then p.supok, p.subok = false, false end
        push_atom(p)
      end

    elseif k == "open" then
      if #opens >= MAX_DEPTH then
        out[#out + 1] = literal(v)
      else
        local tp = top()
        local marker = { pend = "open", bracket = v, t = v, src = v }
        if tp and (tp.pend == "sup" or tp.pend == "sub") then marker.arg = true end
        out[#out + 1] = marker
        opens[#opens + 1] = #out
      end

    elseif k == "close" then
      local m = opens[#opens]
      local pairs_ = { ["("] = ")", ["["] = "]", ["{"] = "}" }
      if m and pairs_[out[m].bracket] == v then
        close_group(m, v)
      else
        out[#out + 1] = literal(v)
      end

    elseif k == "word" then
      local nxt, _, ws_after, nl_after = peek(i)
      local prev = toks[i - 1]
      local prev_ws = prev and prev.k == "ws"
      local prev_tok = prev_ws and toks[i - 2] or prev
      local tp = top()
      local handled = false

      -- chemistry: H2O
      if o.chem and is_upper(byte(v)) and find(v, "%d") and not find(v, "%l%l") then
        local okc, t, j = true, {}, 1
        while j <= #v do
          local sym = sub(v, j, j)
          if is_lower(byte(v, j + 1)) then sym = sym .. sub(v, j + 1, j + 1) end
          if not (is_upper(byte(sym)) and ELEMENTS[sym]) then okc = false; break end
          j = j + #sym
          local ds = j
          while is_digit(byte(v, j)) do j = j + 1 end
          t[#t + 1] = sym .. map_script(sub(v, ds, j - 1), SUB)
        end
        if okc then
          local p = atom(concat(t), v, "word")
          p.mod = "sub"
          p.supok, p.subok = false, false
          push_atom(p)
          handled = true
        end
      end

      if handled then
        -- done
      elseif v == "x" and prev_ws and not prev.nl and prev_tok and prev_tok.k == "num"
        and ws_after and not nl_after and nxt and nxt.k == "num" then
        out[#out + 1] = { t = "×", src = "x", kind = "op" }
      elseif v == "in" and prev_ws and prev_tok and (prev_tok.k == "num" or prev_tok.k == "word"
        or prev_tok.k == "raw" or prev_tok.k == "close") and ws_after and nxt
        and ((nxt.k == "word" and (is_upper(byte(nxt.v)) or SYM[nxt.v] or GREEK[nxt.v]))
          or nxt.k == "open" or nxt.k == "raw" or nxt.k == "cmd") then
        -- x in RR, x in {1,2}, x not in A
        local below = out[#out - 1]
        if tp and tp.kind == "ws" and below and below.kind == "word" and below.src == "not" and not below.mod then
          out[#out] = nil
          out[#out] = { t = "∉", src = "notin", kind = "op" }
        else
          out[#out + 1] = { t = "∈", src = "in", kind = "op" }
        end
      elseif (v == "deg" or v == "degree" or v == "degrees") and tp
        and ((tp.atom and tp.kind == "num" and not prev_ws) or (tp.kind == "ws" and not prev.nl
          and out[#out - 1] and out[#out - 1].atom and out[#out - 1].kind == "num")) then
        local unit
        if nxt and nxt.k == "word" and (nxt.v == "C" or nxt.v == "F") and ws_after and not nl_after then
          unit = nxt.v
        end
        if unit then
          out[#out + 1] = { t = "°" .. unit, src = "deg" .. unit, kind = "unit" }
          i = i + 2
        else
          if tp.kind == "ws" then out[#out] = nil end
          local num = out[#out]
          num.t = num.t .. "°"
          num.src = num.src .. "deg"
          num.supok, num.subok = false, false
          num.mod = "unit"
        end
      elseif v == "degC" or v == "degF" then
        out[#out + 1] = { t = "°" .. sub(v, 4, 4), src = v, kind = "unit" }
      elseif v == "angle" and ws_after and not nl_after and nxt and nxt.k == "word" and is_upper(byte(nxt.v)) then
        out[#out + 1] = { t = "∠", src = v, kind = "op" }
      elseif v == "dot" and not (nxt and nxt.k == "open" and not ws_after) then
        if prev_ws and ws_after then
          out[#out + 1] = { t = "⋅", src = v, kind = "op" }
        else
          push_atom(atom(v, v, "word"))
        end
      elseif WORD_OPS[v] and o.words and (prev_ws or i == 1 or (prev and prev.k == "open"))
        and (ws_after or (v == "not" and nxt and nxt.k == "open")) then
        out[#out + 1] = { t = WORD_OPS[v], src = v, kind = "op" }
      elseif PREFIX[v] then
        if ROOT_GLYPH[v] then
          push_prefix(v, "root", ROOT_GLYPH[v], v, ROOT_GLYPH[v], true)
        elseif v == "root" then
          push_prefix(v, "root", v, v, nil, false)
        elseif ACCENT[v] then
          push_prefix(v, "accent", v, v)
        elseif WRAP[v] then
          push_prefix(v, "wrap", v, v)
        elseif STYLE_NAME[v] then
          push_prefix(v, "style", v, v)
        elseif v == "binom" then
          push_prefix(v, "binom", v, v)
        else
          push_prefix(v, "frac", v, v)
        end
      elseif symbol_for(v, false) then
        push_symbol(v, symbol_for(v, false), false)
      else
        local p = atom(v, v, "word")
        if FUNCS[v] then
          local nx = toks[i + 1]
          if (nx and nx.k == "open") or (STRICT_FUNCS[v] and ws_after and not nl_after and tok_is_atom_start(nxt)) then
            p.guard = true
          end
        end
        if o.italic and #v <= 2 and not FUNCS[v] and not find(v, "%d")
          and not (#v == 2 and sub(v, 1, 1) == "d") and not (tp and (tp.pend == "sup" or tp.pend == "sub"))
          and not in_arg_group() then
          p.t = styled(v, "italic")
        end
        push_atom(p)
      end

    elseif k == "cmd" then
      local nxt, _, ws_after = peek(i)
      local tp = top()
      local b = byte(v)
      if not is_alpha(b) then
        -- \, \; \: are thin spaces, \! is nothing, anything else is itself
        if v == "," or v == ";" or v == ":" then
          out[#out + 1] = { t = " ", src = " ", kind = "ws", supok = true, subok = true }
        elseif v == "!" then
          -- nothing
        else
          out[#out + 1] = literal(v)
        end
      elseif v == "left" or v == "right" then
        local nx = toks[i + 1]
        if nx and nx.k == "op" and nx.v == "." then i = i + 1 end
      elseif v == "quad" then
        out[#out + 1] = { t = chr(0x2003), src = " ", kind = "ws", supok = true, subok = true }
      elseif v == "qquad" then
        out[#out + 1] = { t = chr(0x2003) .. chr(0x2003), src = " ", kind = "ws", supok = true, subok = true }
      elseif VERBATIM_CMD[v] then
        local nx = toks[i + 1]
        if nx and nx.k == "open" and nx.v == "{" then
          local depth, j = 0, i + 1
          local closed
          while j <= nt do
            local t = toks[j]
            if t.k == "open" and t.v == "{" then depth = depth + 1
            elseif t.k == "close" and t.v == "}" then
              depth = depth - 1
              if depth == 0 then closed = j; break end
            end
            j = j + 1
          end
          if closed then
            local body = sub(text, toks[i + 1].e + 1, toks[closed].s - 1)
            local p = atom(body, body, "quote")
            p.supok, p.subok = false, false
            push_atom(p)
            i = closed
          else
            out[#out + 1] = literal("\\" .. v)
          end
        else
          out[#out + 1] = literal("\\" .. v)
        end
      elseif v == "circ" and tp and (tp.pend == "sup" or (tp.pend == "open" and tp.arg)) then
        push_atom({ t = "∘", src = "circ", atom = true, kind = "sym", circ = true, supok = false, subok = false })
      elseif v == "prime" then
        if tp and tp.pend == "sup" then
          push_atom({ t = "′", src = "prime", atom = true, kind = "sym", primecmd = true, supok = false, subok = false })
        else
          out[#out + 1] = { t = "′", src = v, kind = "op" }
        end
      elseif v == "sqrt" then
        push_prefix("sqrt", "root", "√", "\\sqrt", "√", true)
      elseif v == "frac" or v == "dfrac" or v == "tfrac" then
        push_prefix(v, "frac", "\\" .. v, "\\" .. v)
      elseif v == "binom" then
        push_prefix(v, "binom", "\\" .. v, "\\" .. v)
      elseif ACCENT[v] then
        push_prefix(v, "accent", "\\" .. v, "\\" .. v)
      elseif STYLE_NAME[v] then
        push_prefix(v, "style", "\\" .. v, "\\" .. v)
      elseif WRAP[v] then
        push_prefix(v, "wrap", "\\" .. v, "\\" .. v)
      elseif symbol_for(v, true) then
        push_symbol(v, symbol_for(v, true), true)
      elseif FUNCS[v] then
        push_atom(atom(v, v, "word"))
      else
        out[#out + 1] = literal("\\" .. v)
      end

    elseif k == "other" then
      out[#out + 1] = literal(v)

    elseif k == "op" then
      local tp = top()
      local nx = toks[i + 1]
      local prev = toks[i - 1]

      if v == "^" or v == "_" or v == "**" then
        local base = tp
        local ws_before
        if tp and tp.kind == "ws" and not prev.nl and is_base(out[#out - 1]) then
          ws_before = tp.t
          base = out[#out - 1]
        end
        if is_base(base) and v ~= "_" and nx and nx.k == "op" and nx.v == "*" then
          if ws_before then out[#out] = nil end
          base.t = base.t .. "*"
          base.src = base.src .. "*"
          base.mod = "sup"
          base.supok, base.subok = false, false
          i = i + 1
        elseif is_base(base) then
          if ws_before then out[#out] = nil end
          local p = { pend = (v == "_") and "sub" or "sup", t = v, src = v, ws_before = ws_before }
          push_pend(p)
          skip_ws_after(p, true)
        else
          out[#out + 1] = literal(v)
        end

      elseif v == "/" then
        if is_base(tp) and prev and prev.k ~= "ws" and nx and nx.k ~= "ws" and not (nx.k == "op" and nx.v == "/") then
          local below = out[#out - 1]
          if tp.chain or (below and below.chainslash) then
            out[#out + 1] = { t = "/", src = "/", kind = "lit", chainslash = true }
          else
            push_pend({ pend = "frac", t = "/", src = "/" })
          end
        else
          out[#out + 1] = literal("/")
        end

      elseif v == "-" or v == "+" then
        local glyph = (v == "-" and o.minus) and "−" or v
        if tp and (tp.pend == "sup" or tp.pend == "sub" or tp.pend == "frac") then
          if tok_is_atom_start(nx) then
            out[#out + 1] = { t = glyph, src = v, sign = true, kind = "sign" }
          else
            push_atom({ t = glyph, src = v, atom = true, kind = "sign", supok = true, subok = true })
          end
        elseif o.chem and tp and tp.atom and tp.mod == "sup" and tp.justsup and not tok_is_atom_start(nx) then
          tp.t = tp.t .. SUP[v]
          tp.src = tp.src .. v
        elseif v == "-" then
          local at_line_start = (i == 1) or (prev and prev.k == "ws" and (prev.nl or i == 2))
          if at_line_start and nx and nx.k == "ws" then
            out[#out + 1] = literal("-")
          elseif prev and prev.k == "word" and nx and nx.k == "word" and #nx.v >= 2
            and not SYM[nx.v] and not GREEK[nx.v] then
            out[#out + 1] = literal("-")
          else
            out[#out + 1] = { t = glyph, src = "-", kind = "op", supok = true, subok = true }
          end
        else
          out[#out + 1] = { t = "+", src = "+", kind = "op", supok = true, subok = true }
        end

      elseif v == "*" then
        out[#out + 1] = { t = o.times and "×" or "⋅", src = "*", kind = "op" }

      elseif v == "'" then
        tp = resolve_below(tp)
        local j = i
        while toks[j + 1] and toks[j + 1].k == "op" and toks[j + 1].v == "'" do j = j + 1 end
        local n = j - i + 1
        local after = toks[j + 1]
        local ok = o.prime and tp and tp.atom and not tp.pend
          and ((tp.kind == "word" and #tp.src == 1) or tp.grp or tp.mod or tp.kind == "raw" or tp.kind == "sym"
            or tp.kind == "root" or tp.kind == "accent" or tp.kind == "wrap" or tp.kind == "style")
          and not (after and after.k == "word")
        if ok then
          tp.t = tp.t .. prime_run(n)
          tp.src = tp.src .. string.rep("'", n)
          tp.mod = "prime"
          tp.supok, tp.subok = false, false
          i = j
          settle()
        else
          for _ = 1, n do out[#out + 1] = literal("'") end
          i = j
        end

      elseif v == "!" then
        tp = resolve_below(tp)
        if nx and nx.k == "word" and nx.v == "in" then
          out[#out + 1] = { t = "∉", src = "!in", kind = "op" }
          i = i + 1
        elseif tp and tp.atom and not tp.pend then
          tp.t = tp.t .. "!"
          tp.src = tp.src .. "!"
          tp.supok, tp.subok = false, false
          tp.mod = tp.mod or "fact"
          settle()
        else
          out[#out + 1] = literal("!")
        end

      elseif v == "|" or v == "||" then
        out[#out + 1] = { t = (v == "||") and "‖" or "|", src = v, kind = "op", bar = true }

      elseif tk.glyph then
        local g = tk.glyph
        if v == "<=>" and o.chem then g = "⇌" end
        out[#out + 1] = { t = g, src = v, kind = "op" }

      else
        out[#out + 1] = literal(v)
      end
    end

    -- chem: remember an atom that just took a superscript so a trailing sign can join it
    local tp = out[#out]
    if tp and tp.atom then tp.justsup = (tp.mod == "sup") and (k == "num" or k == "word" or k == "close" or k == "raw") or nil end
    i = i + 1
  end

  flush(1)
  local parts = {}
  for _, p in ipairs(out) do parts[#parts + 1] = p.t end
  return concat(parts)
end

--- Public entry: never raises.
function convert(text, opts)
  if text == nil or text == "" then return "" end
  local o = opts or DEFAULTS
  local ok, result = pcall(render_math, text, o)
  if ok then return result end
  if wm and wm.log then wm.log("convert failed: " .. tostring(result)) end
  return text
end

-- ================================================================ chunking ==

local OUTPUT_LIMIT = 2000

--- Splits s into pieces of at most OUTPUT_LIMIT UTF-16 units, cutting at a
--- newline or space where one is near.
local function chunk(s)
  local pieces = {}
  local cs = chars_of(s)
  local start, count, last_break = 1, 0, nil
  local n = #cs
  local k = 1
  while k <= n do
    local c = cs[k]
    local u = (#c == 6 and byte(c) == 0xED) and 2 or 1
    if count + u > OUTPUT_LIMIT then
      local cut = last_break or (k - 1)
      pieces[#pieces + 1] = concat(cs, "", start, cut)
      start = cut + 1
      count = 0
      last_break = nil
      k = start
    else
      count = count + u
      if c == "\n" or c == " " then last_break = k end
      k = k + 1
    end
  end
  if start <= n then pieces[#pieces + 1] = concat(cs, "", start, n) end
  return pieces
end

-- ================================================================= panel ==

local opts = default_options()
local expr = ""
local output = ""
local chunks = {}

local function encode_opts()
  local parts = {}
  for _, key in ipairs(OPTION_KEYS) do parts[#parts + 1] = key .. "=" .. (opts[key] and "1" or "0") end
  return concat(parts, ";")
end

local function decode_opts(s)
  if type(s) ~= "string" then return end
  for key, val in s:gmatch("(%a+)=(%d)") do
    if DEFAULTS[key] ~= nil then opts[key] = (val == "1") end
  end
end

local function save_opts()
  if wm and wm.storage then wm.storage.set("options", encode_opts()) end
end

local function reconvert()
  output = convert(expr, opts)
  chunks = chunk(output)
end

do
  local ok, saved = pcall(function() return wm and wm.storage and wm.storage.get("options") end)
  if ok and saved then decode_opts(saved) end
end

local SYMBOL_ROWS = {
  { "α", "β", "γ", "δ", "ε", "θ" },
  { "λ", "μ", "π", "σ", "φ", "ω" },
  { "Δ", "Σ", "Π", "Ω", "∞", "∂" },
  { "±", "×", "÷", "⋅", "√", "∛" },
  { "≤", "≥", "≠", "≈", "≡", "∝" },
  { "→", "←", "↔", "⇒", "⇔", "↦" },
  { "∫", "∬", "∮", "∑", "∏", "∇" },
  { "∈", "∉", "⊂", "⊆", "∪", "∩" },
  { "∀", "∃", "∧", "∨", "¬", "∴" },
  { "ℝ", "ℕ", "ℤ", "ℚ", "ℂ", "∅" },
  { "°", "′", "″", "∠", "⊥", "⁄" },
}

local OPTION_LABELS = {
  minus = "Typographic minus (−)",
  times = "Multiply with × (off: ⋅)",
  frac = "Fraction slash a⁄b (off: a/b)",
  small = "Small number fractions ½ ³⁄₄",
  words = "Word operators: and, or, not, to",
  prime = "Apostrophe as prime f′",
  chem = "Chemistry: H2O → H₂O",
  italic = "Italic variables 𝑥𝑦",
  rootline = "Overline after √ (experimental)",
}

local HELP = {
  { "Powers and indices", "x^2 → x²   x_1 → x₁   x^(n+1) → xⁿ⁺¹   10^-3 → 10⁻³   A^T → Aᵀ\nBraces work too: x^{10}. What has no small form stays as x^(…)." },
  { "Roots", "sqrt(2) → √2   sqrt(x+1) → √(x+1)   cbrt(8) → ∛8   root(n)(x) → ⁿ√x" },
  { "Fractions", "1/2 → ½   22/7 → ²²⁄₇   a/b → a⁄b   (a+b)/(c+d) → (a+b)⁄(c+d)\nSpaced 1 / 2 and chains a/b/c are left alone. \\frac{a}{b} works." },
  { "Greek", "alpha beta gamma … omega → α β γ … ω, Delta Omega → Δ Ω, pi → π, vartheta → ϑ" },
  { "Operators", "<= >= != → ≤ ≥ ≠   +- → ±   ~~ → ≈   ~= → ≅   === → ≡   := → ≔\n* → ×   a - b → a − b   ... → …   ||v|| → ‖v‖   2 x 3 → 2 × 3" },
  { "Arrows", "-> → →   <- → ←   <-> → ↔   => → ⇒   <=> → ⇔   |-> → ↦   --> → ⟶" },
  { "Calculus", "int_0^1 → ∫₀¹   sum_(i=1)^n → ∑ᵢ₌₁ⁿ   prod, oint, iint\nlim_(x->oo) → lim_(x→∞)   partial → ∂   nabla → ∇   oo → ∞   d/dx → d⁄dx" },
  { "Sets and logic", "x in RR → x ∈ ℝ   notin subset subseteq union intersect setminus\nforall exists therefore implies iff → ∀ ∃ ∴ ⇒ ⇔   RR NN ZZ QQ CC → ℝ ℕ ℤ ℚ ℂ\nand, or, not, to convert only with the option on." },
  { "Functions and marks", "f'(x) → f′(x)   sin^2(x) → sin²(x)   abs(x) → |x|   norm(v) → ‖v‖   floor ceil\nvec(v) hat(x) bar(x) dot(x) ddot(x) tilde(x) → v⃗ x̂ x̄ ẋ ẍ x̃   30 deg → 30°" },
  { "Styles", "bb(A) → 𝐀   bbb(R) → ℝ   cc(L) → ℒ   fr(g) → 𝔤   sf(A) → 𝖠   tt(x) → 𝚡   it(x) → 𝑥" },
  { "LaTeX", "\\alpha \\frac{1}{2} \\sqrt{2} \\int_0^\\infty \\mathbb{R} \\hat{x} \\text{words} all work.\n\\left \\right are dropped; \\, is a space." },
  { "Leave things alone", "\"quoted text\" is never converted. \\* \\/ \\^ \\_ give the plain character." },
}

function on_event(e)
  if e.type == "input_changed" and e.id == "expr" then
    expr = e.value or ""
    reconvert()
  elseif e.type == "toggle" then
    if DEFAULTS[e.id] ~= nil then
      opts[e.id] = e.value and true or false
      save_opts()
      reconvert()
    end
  elseif e.type == "click" then
    local sym = e.id:match("^sym:(.+)$")
    if sym then
      expr = expr .. sym
      wm.ui.set_input("expr", expr)
      reconvert()
    elseif e.id == "clear" then
      expr = ""
      wm.ui.set_input("expr", "")
      reconvert()
    elseif e.id == "reset_opts" then
      opts = default_options()
      save_opts()
      reconvert()
    end
  end
end

local function symbols_page()
  local page = { title = "Symbols" }
  for _, row in ipairs(SYMBOL_ROWS) do
    local r = {}
    for _, s in ipairs(row) do r[#r + 1] = ui.button { id = "sym:" .. s, text = s } end
    page[#page + 1] = ui.row(r)
  end
  page[#page + 1] = ui.label { text = "Tap to add to the box above.", style = "caption" }
  return ui.page(page)
end

local function options_page()
  local page = { title = "Options" }
  for _, key in ipairs(OPTION_KEYS) do
    page[#page + 1] = ui.toggle { id = key, label = OPTION_LABELS[key], checked = opts[key] }
  end
  page[#page + 1] = ui.button { id = "reset_opts", text = "Reset options" }
  return ui.page(page)
end

local function help_page()
  local page = { title = "Help" }
  for _, h in ipairs(HELP) do
    page[#page + 1] = ui.label { text = h[1], style = "title" }
    page[#page + 1] = ui.label { text = h[2], style = "caption" }
  end
  return ui.page(page)
end

function render()
  local col = {
    ui.input { id = "expr", label = "Math", placeholder = "x^2 + sqrt(2) = pi/4" },
  }
  if expr == "" then
    col[#col + 1] = ui.label {
      text = "Type math the way you say it: x^2, sqrt(2), pi, 1/2, int_0^1, x in RR. The Unicode version appears here, ready to insert.",
      style = "caption",
    }
  else
    for n, c in ipairs(chunks) do
      col[#col + 1] = ui.output { id = n == 1 and "out" or ("out" .. n), text = c }
    end
    if #chunks > 1 then
      col[#col + 1] = ui.label { text = "Long result, shown in " .. #chunks .. " parts.", style = "caption" }
    end
  end
  col[#col + 1] = ui.tabs { id = "tabs", symbols_page(), options_page(), help_page() }
  col[#col + 1] = ui.button { id = "clear", text = "Clear" }
  return ui.column(col)
end
