-- UI Kitchen Sink: every widget, and every event, in one place.
--
-- Not useful on its own. It exists so you can see what each widget looks like
-- on a real keyboard, and watch what arrives in on_event when you touch it.
-- Copy the bits you want.

local log = {}
local checked = false
local disabled = false
local typed = ""
local working = false

--- Keeps the last few events, newest first.
local function note(line)
  table.insert(log, 1, line)
  while #log > 8 do table.remove(log) end
end

function on_event(e)
  -- Every event has a type and an id. Some carry a value.
  if e.type == "click" then
    note("click " .. e.id)
    if e.id == "toggle_enabled" then disabled = not disabled end
    if e.id == "work" then working = not working end
    if e.id == "clear" then log = {} end

  elseif e.type == "toggle" then
    note("toggle " .. e.id .. " = " .. tostring(e.value))
    if e.id == "demo_toggle" then checked = e.value end

  elseif e.type == "input_changed" then
    -- Fired for every keystroke into *this plugin's own box*. A plugin never
    -- sees keys typed anywhere else.
    note("input " .. e.id .. " = " .. e.value)
    typed = e.value

  elseif e.type == "tab_selected" then
    note("tab " .. e.id .. " #" .. e.index)
  end
end

local function event_log()
  if #log == 0 then
    return ui.label { text = "Touch something and the events show up here.", style = "caption" }
  end
  return ui.output { id = "log", text = table.concat(log, "\n"), mono = true, insertable = false }
end

function render()
  return ui.tabs {
    id = "sink",

    ui.page {
      title = "Text",
      ui.label { text = "A title label", style = "title" },
      ui.label { text = "A body label. This is the default style." },
      ui.label { text = "A caption label, for asides.", style = "caption" },
      ui.divider(),
      ui.output { id = "out", text = "An output block.\nIt gets Insert and Copy buttons." },
      ui.output { id = "mono", text = "mono = true keeps columns lined up", mono = true },
    },

    ui.page {
      title = "Controls",
      ui.button { id = "primary", text = "Primary button", style = "primary" },
      ui.button { id = "secondary", text = "Secondary button" },
      ui.button { id = "maybe", text = "Enabled toggles me", enabled = not disabled },
      ui.button { id = "toggle_enabled", text = disabled and "Enable it" or "Disable it" },
      ui.divider(),
      ui.toggle { id = "demo_toggle", label = "A toggle", checked = checked },
      ui.label {
        text = checked and "The toggle is on." or "The toggle is off.",
        style = "caption",
      },
    },

    ui.page {
      title = "Input",
      ui.input { id = "box", label = "A text box", placeholder = "Type or paste here" },
      ui.label { text = "You typed: " .. (typed == "" and "(nothing yet)" or typed) },
      ui.label {
        text = "The keyboard owns this box. Tap it, then use the keys; Paste puts " ..
          "the clipboard in it.",
        style = "caption",
      },
    },

    ui.page {
      title = "Layout",
      ui.label { text = "A row splits the width evenly:" },
      ui.row {
        ui.button { id = "one", text = "One" },
        ui.button { id = "two", text = "Two" },
        ui.button { id = "three", text = "Three" },
      },
      ui.spacer { height = 12 },
      ui.label { text = "Above is a 12pt spacer. Below is a divider." },
      ui.divider(),
      ui.button { id = "work", text = working and "Stop pretending" or "Pretend to work" },
      working and ui.progress() or ui.label { text = "(no progress bar)", style = "caption" },
    },

    ui.page {
      title = "Events",
      event_log(),
      ui.button { id = "clear", text = "Clear log" },
    },
  }
end
