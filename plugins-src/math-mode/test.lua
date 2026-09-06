-- Golden tests for Math Mode, run on the real interpreter:
--
--   java -cp luaj-jse-3.0.1.jar lua plugins-src/math-mode/test.lua
--
-- (tools/test_plugins.py finds or fetches the jar and runs every plugin's
-- test.lua.) Two things are stubbed: the `ui.*` prelude the keyboard injects,
-- and the `wm` host table. Everything else is exactly what runs on a phone.
--
-- Newlines, carriage returns and tabs are written as ␊ ␍ ␉ in the corpus so
-- that LaTeX backslashes need no escaping.
--
-- Text crosses the host boundary per UTF-16 unit, so astral characters reach
-- the script as CESU-8. The corpus file is plain UTF-8; both columns are
-- re-encoded here before comparing, the same way the host would hand them
-- over.

local here = arg and arg[0] and arg[0]:match("^(.*)[/\\]") or "."

-- ---- host stubs ----------------------------------------------------------

ui = {}
function ui.column(t) return { type = "column", children = t } end
function ui.row(t) return { type = "row", children = t } end
function ui.label(t) return { type = "label", text = t.text, style = t.style } end
function ui.output(t)
  return { type = "output", id = t.id, text = t.text, mono = t.mono, insertable = t.insertable, copyable = t.copyable }
end
function ui.button(t) return { type = "button", id = t.id, text = t.text, style = t.style, enabled = t.enabled } end
function ui.toggle(t) return { type = "toggle", id = t.id, label = t.label, checked = t.checked } end
function ui.input(t) return { type = "input", id = t.id, label = t.label, placeholder = t.placeholder } end
function ui.spacer(t) return { type = "spacer", height = t and t.height } end
function ui.divider() return { type = "divider" } end
function ui.progress() return { type = "progress" } end
function ui.tabs(t) return { type = "tabs", id = t.id, pages = t } end
function ui.page(t) return { title = t.title, children = t } end

local store = {}
local writes = {}
wm = {
  api_version = 1, plugin_id = "com.wasimaster.mathmode", plugin_version = "test",
  log = function() end,
  ui = { set_input = function(id, text) writes[#writes + 1] = { id, text } end },
  storage = {
    get = function(k) return store[k] end,
    set = function(k, v) store[k] = v; return true end,
    remove = function(k) store[k] = nil end,
    keys = function() local r = {} for k in pairs(store) do r[#r + 1] = k end return r end,
  },
  json = { encode = function() return nil, "unused" end, decode = function() return nil, "unused" end },
}

-- ---- helpers -------------------------------------------------------------

local byte, char, floor = string.byte, string.char, math.floor

local function encode(cp)
  if cp < 0x80 then return char(cp) end
  if cp < 0x800 then return char(0xC0 + floor(cp / 0x40), 0x80 + cp % 0x40) end
  return char(0xE0 + floor(cp / 0x1000), 0x80 + floor(cp / 0x40) % 0x40, 0x80 + cp % 0x40)
end

--- UTF-8 -> CESU-8: every 4-byte sequence becomes two 3-byte surrogates.
local function cesu(s)
  return (s:gsub("[\240-\247][\128-\191][\128-\191][\128-\191]", function(q)
    local b1, b2, b3, b4 = byte(q, 1, 4)
    local cp = (b1 - 0xF0) * 0x40000 + (b2 - 0x80) * 0x1000 + (b3 - 0x80) * 0x40 + (b4 - 0x80)
    local v = cp - 0x10000
    return encode(0xD800 + floor(v / 0x400)) .. encode(0xDC00 + v % 0x400)
  end))
end

local function unescape(s)
  return (s:gsub("␊", "\n"):gsub("␍", "\r"):gsub("␉", "\t"))
end

local function utf16_units(s)
  local n = 0
  for i = 1, #s do
    local b = byte(s, i)
    if b < 0x80 or b >= 0xC0 then n = n + 1 end
  end
  return n
end

local function show(s)
  return (s:gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\t", "\\t"))
end

local OPT_FLAGS = {
  chem = { "chem", true }, nominus = { "minus", false }, dot = { "times", false },
  words = { "words", true }, rootline = { "rootline", true }, italic = { "italic", true },
  noprime = { "prime", false }, nofrac = { "frac", false }, nosmall = { "small", false },
}

-- ---- load the plugin ----------------------------------------------------

local chunk, err = loadfile(here .. "/main.lua")
if not chunk then print("cannot load main.lua: " .. tostring(err)); os.exit(1) end
chunk()
assert(type(convert) == "function", "main.lua must export convert()")
assert(type(default_options) == "function", "main.lua must export default_options()")
assert(type(render) == "function" and type(on_event) == "function")

-- ---- walk a rendered tree ----------------------------------------------

local function walk(node, visit)
  if type(node) ~= "table" then return end
  if node.type then visit(node) end
  if node.children then for _, c in ipairs(node.children) do walk(c, visit) end end
  if node.pages then
    for _, p in ipairs(node.pages) do
      if p.children then for _, c in ipairs(p.children) do walk(c, visit) end end
    end
  end
end

local function outputs(tree)
  local r = {}
  walk(tree, function(n) if n.type == "output" then r[#r + 1] = n.text or "" end end)
  return r
end

local function check_tree(tree, label, fails)
  local nodes, deepest = 0, 0
  local function depth(node, d)
    if type(node) ~= "table" then return end
    if node.type then nodes = nodes + 1 end
    if d > deepest then deepest = d end
    for _, key in ipairs({ "text", "label", "placeholder", "title" }) do
      local s = node[key]
      if type(s) == "string" and utf16_units(s) > 2048 then
        fails[#fails + 1] = label .. ": " .. key .. " has " .. utf16_units(s) .. " units (limit 2048)"
      end
    end
    if node.children then for _, c in ipairs(node.children) do depth(c, d + 1) end end
    if node.pages then
      if #node.pages > 8 then fails[#fails + 1] = label .. ": more than 8 tabs" end
      for _, p in ipairs(node.pages) do
        nodes = nodes + 1
        for _, key in ipairs({ "title" }) do
          local s = p[key]
          if type(s) == "string" and utf16_units(s) > 2048 then fails[#fails + 1] = label .. ": long tab title" end
        end
        if p.children then for _, c in ipairs(p.children) do depth(c, d + 2) end end
      end
    end
  end
  depth(tree, 1)
  if nodes > 256 then fails[#fails + 1] = label .. ": " .. nodes .. " nodes (limit 256)" end
  if deepest > 12 then fails[#fails + 1] = label .. ": tree depth " .. deepest .. " (limit 12)" end
end

-- ---- the corpus ---------------------------------------------------------

local fails, total = {}, 0
local f = assert(io.open(here .. "/cases.txt", "rb"))
local lineno = 0
for line in f:lines() do
  lineno = lineno + 1
  line = line:gsub("\r$", "")
  if line ~= "" and line:sub(1, 1) ~= "#" then
    local fields = {}
    for field in (line .. "\t"):gmatch("(.-)\t") do fields[#fields + 1] = field end
    local opts = default_options()
    local input, expected
    if fields[1]:sub(1, 1) == "@" then
      for name in fields[1]:sub(2):gmatch("[^,]+") do
        local flag = OPT_FLAGS[name]
        if not flag then print("line " .. lineno .. ": unknown option tag " .. name); os.exit(2) end
        opts[flag[1]] = flag[2]
      end
      input, expected = fields[2], fields[3]
    else
      input, expected = fields[1], fields[2]
    end
    if not input or not expected then
      print("line " .. lineno .. ": expected two tab-separated columns"); os.exit(2)
    end
    input, expected = cesu(unescape(input)), cesu(unescape(expected))
    total = total + 1

    -- 1. the engine directly
    local got = convert(input, opts)
    if got ~= expected then
      fails[#fails + 1] = ("line %d: %s\n    expected  %s\n    got       %s"):format(lineno, show(input), show(expected), show(got))
    end

    -- 2. the real event path: toggles, then a keystroke, then render()
    for key, value in pairs(opts) do on_event({ type = "toggle", id = key, value = value }) end
    on_event({ type = "input_changed", id = "expr", value = input })
    local tree = render()
    local outs = outputs(tree)
    local joined = table.concat(outs)
    if joined ~= expected then
      fails[#fails + 1] = ("line %d (event path): %s\n    expected  %s\n    got       %s"):format(lineno, show(input), show(expected), show(joined))
    end
    check_tree(tree, "line " .. lineno, fails)
  end
end
f:close()

-- reset options for the rest
for key, value in pairs(default_options()) do on_event({ type = "toggle", id = key, value = value }) end

-- ---- adversarial inputs ---------------------------------------------------

local function big(name, input, expect_unchanged)
  total = total + 1
  local t0 = os.clock()
  local ok, got = pcall(convert, input, default_options())
  local took = os.clock() - t0
  if not ok then
    fails[#fails + 1] = name .. ": convert raised " .. tostring(got)
    return
  end
  if expect_unchanged and got ~= input then
    fails[#fails + 1] = name .. ": expected the input back unchanged"
  end
  if took > 1.0 then fails[#fails + 1] = ("%s: took %.2fs"):format(name, took) end
  on_event({ type = "input_changed", id = "expr", value = input })
  local tree = render()
  for n, o in ipairs(outputs(tree)) do
    if utf16_units(o) > 2000 then fails[#fails + 1] = name .. ": output chunk " .. n .. " has " .. utf16_units(o) .. " units" end
  end
  check_tree(tree, name, fails)
  return got
end

big("8K carets", ("^"):rep(8192), true)
big("8K opens", ("("):rep(8192), true)
big("deep nest", ("("):rep(4096) .. "x" .. (")"):rep(4096) .. "^2", true)
big("caret chain", "a" .. ("^b"):rep(2000))
big("slash chain", "1" .. ("/2"):rep(2000), true)
big("8K word", ("z"):rep(8192), true)
big("frac chain", ("\\frac{"):rep(1000), true)
big("quotes", ('"'):rep(4000))
big("emoji", cesu(("😀"):rep(2048)), true)
do
  local got = big("many lines", ("x^2\n"):rep(2000))
  if got ~= ("x²\n"):rep(2000) then fails[#fails + 1] = "many lines: wrong conversion" end
  on_event({ type = "input_changed", id = "expr", value = ("x^2\n"):rep(2000) })
  local outs = outputs(render())
  if #outs < 2 then fails[#fails + 1] = "many lines: expected the output to be chunked, got " .. #outs .. " block(s)" end
  if table.concat(outs) ~= ("x²\n"):rep(2000) then fails[#fails + 1] = "many lines: chunks do not join back to the whole" end
end

-- ---- panel behaviour ------------------------------------------------------

total = total + 1
on_event({ type = "click", id = "clear" })
on_event({ type = "input_changed", id = "expr", value = "x^2" })
writes = {}
on_event({ type = "click", id = "sym:π" })
if #writes ~= 1 or writes[1][1] ~= "expr" or writes[1][2] ~= "x^2π" then
  fails[#fails + 1] = "symbol tap: expected one set_input('expr', 'x^2π'), got " .. #writes
end
if table.concat(outputs(render())) ~= "x²π" then fails[#fails + 1] = "symbol tap: output did not update" end

total = total + 1
on_event({ type = "toggle", id = "chem", value = true })
if not (store.options and store.options:find("chem=1", 1, true)) then
  fails[#fails + 1] = "toggle: chem=1 was not written to storage (" .. tostring(store.options) .. ")"
end
on_event({ type = "click", id = "reset_opts" })
if not (store.options and store.options:find("chem=0", 1, true)) then
  fails[#fails + 1] = "reset: chem=0 was not written to storage"
end

total = total + 1
on_event({ type = "click", id = "clear" })
local empty = render()
if #outputs(empty) ~= 0 then fails[#fails + 1] = "empty box should show a caption, not an output block" end
check_tree(empty, "empty panel", fails)

-- ---- report ---------------------------------------------------------------

if #fails > 0 then
  print(("%d of %d checks failed:"):format(#fails, total))
  for _, msg in ipairs(fails) do print("  " .. msg) end
  os.exit(1)
end
print(("math-mode: %d checks passed"):format(total))
