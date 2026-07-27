-- Cipher Tool: Caesar and Vigenere, encode and decode.
--
-- This is the plugin the getting-started guide builds step by step, so it
-- sticks to the plainest Lua that does the job.
--
-- The shape every plugin has:
--   * some state in local variables at the top,
--   * on_event(e) to change that state when the user does something,
--   * render() to describe what should be on screen right now.
--
-- The keyboard calls render() after every event, so you never update the UI
-- yourself -- you change a variable and describe the result.

-- ---------------------------------------------------------------- state ----

-- What the user has typed into each box. The keyboard owns the boxes; it
-- tells us the contents through input_changed events.
local message = ""
local shift = "3"
local keyword = ""
local output = ""

-- --------------------------------------------------------------- ciphers ----

--- Shifts every letter by `by`, wrapping within its own case.
local function caesar(text, by)
  by = by % 26
  return (text:gsub("%a", function(c)
    local base = c:match("%u") and 65 or 97
    return string.char((c:byte() - base + by) % 26 + base)
  end))
end

--- Vigenere: the same idea, but the shift comes from a repeating keyword.
local function vigenere(text, key, direction)
  local letters = key:lower():gsub("%A", "")
  if letters == "" then return text end
  local index = 0
  return (text:gsub("%a", function(c)
    index = index + 1
    local at = (index - 1) % #letters + 1
    local by = letters:byte(at) - 97
    return caesar(c, direction * by)
  end))
end

-- --------------------------------------------------------------- events ----

function on_event(e)
  if e.type == "input_changed" then
    if e.id == "message" then message = e.value end
    if e.id == "shift" then shift = e.value end
    if e.id == "keyword" then keyword = e.value end

  elseif e.type == "click" then
    local by = tonumber(shift) or 0
    if e.id == "caesar_encode" then output = caesar(message, by) end
    if e.id == "caesar_decode" then output = caesar(message, -by) end
    if e.id == "vigenere_encode" then output = vigenere(message, keyword, 1) end
    if e.id == "vigenere_decode" then output = vigenere(message, keyword, -1) end

  elseif e.type == "tab_selected" then
    -- Switching tabs clears a result that belonged to the other cipher.
    output = ""
  end
end

-- --------------------------------------------------------------- render ----

--- The result box. Shared by both tabs, so it lives in its own function.
local function result()
  if output == "" then
    return ui.label { text = "Type something and pick a button.", style = "caption" }
  end
  -- insertable puts the keyboard's own Insert button under the text, which is
  -- how a result reaches whatever the user is writing in. A plugin cannot type
  -- on its own -- the user taps Insert.
  return ui.output { id = "result", text = output, mono = true }
end

function render()
  return ui.tabs {
    id = "cipher",

    ui.page {
      title = "Caesar",
      ui.input { id = "message", label = "Message", placeholder = "Type or paste" },
      ui.input { id = "shift", label = "Shift", placeholder = "3" },
      ui.row {
        ui.button { id = "caesar_encode", text = "Encode", style = "primary" },
        ui.button { id = "caesar_decode", text = "Decode" },
      },
      result(),
    },

    ui.page {
      title = "Vigenere",
      ui.input { id = "message", label = "Message", placeholder = "Type or paste" },
      ui.input { id = "keyword", label = "Keyword", placeholder = "lemon" },
      ui.row {
        ui.button { id = "vigenere_encode", text = "Encode", style = "primary" },
        ui.button { id = "vigenere_decode", text = "Decode" },
      },
      result(),
    },
  }
end
