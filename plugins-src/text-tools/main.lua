-- Text Tools: change case, encode, and count.
--
-- Everything here works on text the user typed or pasted into the box at the
-- top. That is how any plugin gets text -- there is no API for reading what
-- you are writing, so the user hands it over on purpose, and can see exactly
-- what they handed over.

local text = ""
local output = ""

-- ----------------------------------------------------------------- base64 ---

local ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

local function base64_encode(input)
  local out = {}
  for i = 1, #input, 3 do
    local a, b, c = input:byte(i, i + 2)
    local n = a * 65536 + (b or 0) * 256 + (c or 0)
    local chunk = {
      math.floor(n / 262144) % 64,
      math.floor(n / 4096) % 64,
      math.floor(n / 64) % 64,
      n % 64,
    }
    -- Two padding cases: one leftover byte gives two '=', two gives one.
    local keep = 4
    if not b then keep = 2 elseif not c then keep = 3 end
    for j = 1, keep do
      out[#out + 1] = ALPHABET:sub(chunk[j] + 1, chunk[j] + 1)
    end
    for _ = keep + 1, 4 do out[#out + 1] = "=" end
  end
  return table.concat(out)
end

local function base64_decode(input)
  local clean = input:gsub("[^%w+/=]", ""):gsub("=", "")
  local out = {}
  local bits, count = 0, 0
  for i = 1, #clean do
    local value = ALPHABET:find(clean:sub(i, i), 1, true)
    if value then
      bits = bits * 64 + (value - 1)
      count = count + 6
      if count >= 8 then
        count = count - 8
        local byte = math.floor(bits / 2 ^ count) % 256
        out[#out + 1] = string.char(byte)
        -- Drop the bits we just spent. Without this `bits` keeps growing and
        -- runs out of double precision after a dozen or so characters.
        bits = bits % 2 ^ count
      end
    end
  end
  return table.concat(out)
end

-- -------------------------------------------------------------- hex & url ---

local function hex_encode(input)
  return (input:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end

local function hex_decode(input)
  local clean = input:gsub("%s", "")
  return (clean:gsub("%x%x", function(pair) return string.char(tonumber(pair, 16)) end))
end

local function url_encode(input)
  return (input:gsub("[^%w%-._~]", function(c) return string.format("%%%02X", c:byte()) end))
end

local function url_decode(input)
  return (input:gsub("%%(%x%x)", function(pair) return string.char(tonumber(pair, 16)) end))
end

-- ---------------------------------------------------------------- counting --

local function statistics(input)
  local words = 0
  for _ in input:gmatch("%S+") do words = words + 1 end
  local lines = 0
  for _ in (input .. "\n"):gmatch("[^\n]*\n") do lines = lines + 1 end
  if input == "" then lines = 0 end
  local letters = 0
  for _ in input:gmatch("%a") do letters = letters + 1 end
  return ("%d characters\n%d letters\n%d words\n%d lines")
    :format(#input, letters, words, lines)
end

-- ----------------------------------------------------------------- events ---

local ACTIONS = {
  upper = function(s) return s:upper() end,
  lower = function(s) return s:lower() end,
  title = function(s) return (s:gsub("(%a)([%w']*)", function(a, b) return a:upper() .. b:lower() end)) end,
  reverse = function(s) return s:reverse() end,
  b64_encode = base64_encode,
  b64_decode = base64_decode,
  hex_encode = hex_encode,
  hex_decode = hex_decode,
  url_encode = url_encode,
  url_decode = url_decode,
  stats = statistics,
}

function on_event(e)
  if e.type == "input_changed" and e.id == "text" then
    text = e.value
  elseif e.type == "click" then
    local action = ACTIONS[e.id]
    if action then output = action(text) end
    if e.id == "clear" then
      text = ""
      output = ""
      -- Ask the keyboard to empty the box; we do not own it ourselves.
      wm.ui.set_input("text", "")
    end
  end
end

function render()
  return ui.column {
    ui.input { id = "text", label = "Text", placeholder = "Type or paste, then pick an action" },

    ui.tabs {
      id = "tools",

      ui.page {
        title = "Case",
        ui.row {
          ui.button { id = "upper", text = "UPPER" },
          ui.button { id = "lower", text = "lower" },
        },
        ui.row {
          ui.button { id = "title", text = "Title Case" },
          ui.button { id = "reverse", text = "esreveR" },
        },
      },

      ui.page {
        title = "Encode",
        ui.row {
          ui.button { id = "b64_encode", text = "Base64" },
          ui.button { id = "b64_decode", text = "un-Base64" },
        },
        ui.row {
          ui.button { id = "hex_encode", text = "Hex" },
          ui.button { id = "hex_decode", text = "un-Hex" },
        },
        ui.row {
          ui.button { id = "url_encode", text = "URL" },
          ui.button { id = "url_decode", text = "un-URL" },
        },
      },

      ui.page {
        title = "Count",
        ui.button { id = "stats", text = "Count it", style = "primary" },
      },
    },

    ui.divider(),
    output ~= "" and ui.output { id = "out", text = output, mono = true }
      or ui.label { text = "Results appear here.", style = "caption" },
    ui.button { id = "clear", text = "Clear" },
  }
end
