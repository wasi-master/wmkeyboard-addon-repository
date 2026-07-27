-- Todo List: the storage example.
--
-- Shows the one capability a plugin can ask for. `wm.storage` is a small
-- string-to-string map that belongs to this plugin alone, lives on this device
-- only, and is deleted when the plugin is uninstalled. It is declared in
-- plugin.json, so the user sees it before installing.
--
-- Note what is *not* here: no network, no reading your messages. This list
-- cannot leave the phone, because there is nothing in the sandbox to send it
-- with.

local items = {}
local draft = ""

-- ---------------------------------------------------------------- storage ---

--- Reads the saved list. Stored as JSON in one key, which is simpler than
--- juggling a key per item and stays well inside the quota.
local function load()
  local raw = wm.storage.get("items")
  if not raw then return end
  local decoded = wm.json.decode(raw)
  if type(decoded) == "table" then
    items = decoded
  end
end

local function save()
  local ok, err = wm.storage.set("items", wm.json.encode(items))
  if not ok then
    -- Over quota, most likely. Say so rather than silently losing an item.
    wm.log("could not save: " .. tostring(err))
  end
end

-- Runs once, when the plugin is opened.
load()

-- ----------------------------------------------------------------- events ---

function on_event(e)
  if e.type == "input_changed" and e.id == "draft" then
    draft = e.value

  elseif e.type == "toggle" then
    -- Toggle ids are "done:<n>", so the number says which item was ticked.
    local index = tonumber(e.id:match("^done:(%d+)$"))
    if index and items[index] then
      items[index].done = e.value
      save()
    end

  elseif e.type == "click" then
    if e.id == "add" and draft ~= "" then
      items[#items + 1] = { text = draft, done = false }
      draft = ""
      wm.ui.set_input("draft", "")
      save()

    elseif e.id == "clear_done" then
      local kept = {}
      for _, item in ipairs(items) do
        if not item.done then kept[#kept + 1] = item end
      end
      items = kept
      save()
    end
  end
end

-- ----------------------------------------------------------------- render ---

function render()
  local rows = {}

  rows[#rows + 1] = ui.row {
    ui.input { id = "draft", placeholder = "Something to do" },
    ui.button { id = "add", text = "Add", style = "primary" },
  }
  rows[#rows + 1] = ui.divider()

  if #items == 0 then
    rows[#rows + 1] = ui.label { text = "Nothing on the list.", style = "caption" }
  else
    local remaining = 0
    for index, item in ipairs(items) do
      if not item.done then remaining = remaining + 1 end
      rows[#rows + 1] = ui.toggle {
        id = "done:" .. index,
        label = item.text,
        checked = item.done,
      }
    end
    rows[#rows + 1] = ui.label {
      text = remaining .. " of " .. #items .. " left",
      style = "caption",
    }
    rows[#rows + 1] = ui.button { id = "clear_done", text = "Clear finished" }
  end

  return ui.column(rows)
end
