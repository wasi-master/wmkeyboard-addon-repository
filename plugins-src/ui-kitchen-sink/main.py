# UI Kitchen Sink: every widget, and every event, in one place.
#
# Not useful on its own. It exists so you can see what each widget looks like
# on a real keyboard, and watch what arrives in on_event when you touch it.
# Copy the bits you want.

import time

log = []
checked = False
disabled = False
typed = ""
working = False
picked = None  # seconds since the epoch, or None


def note(line):
    """Keeps the last few events, newest first."""
    global log
    log = [line] + log[:7]


def on_event(e):
    global checked, disabled, typed, working, picked, log
    # Every event has a type and an id; some carry a value or an index. An
    # event is a dict, and it also answers attribute reads, so e.type works
    # as well as e["type"].
    kind = e["type"]
    eid = e["id"]
    if kind == "click":
        note("click " + eid)
        if eid == "toggle_enabled":
            disabled = not disabled
        if eid == "work":
            working = not working
        if eid == "clear":
            log = []

    elif kind == "toggle":
        note("toggle " + eid + " = " + str(e["value"]))
        if eid == "demo_toggle":
            checked = e["value"]

    elif kind == "input_changed":
        # Fired for every keystroke into *this plugin's own box*. A plugin
        # never sees keys typed anywhere else.
        note("input " + eid + " = " + e["value"])
        typed = e["value"]

    elif kind == "tab_selected":
        note("tab " + eid + " #" + str(e["index"]))

    elif kind == "date_changed":
        # value is seconds, as time.time() gives, or None when the date was cleared.
        value = e.get("value")
        shown = time.format("yyyy-MM-dd HH:mm", value) if value is not None else "None"
        note("date " + eid + " = " + shown)
        picked = value


def event_log():
    if not log:
        return ui.label("Touch something and the events show up here.", style="caption")
    return ui.output("\n".join(log), id="log", mono=True, insertable=False)


def render():
    return ui.tabs(
        "sink",
        ui.page(
            "Text",
            ui.label("A title label", style="title"),
            ui.label("A body label. This is the default style."),
            ui.label("A caption label, for asides.", style="caption"),
            ui.divider(),
            ui.output("An output block.\nIt gets Insert and Copy buttons.", id="out"),
            ui.output("mono=True keeps columns lined up", id="mono", mono=True),
        ),
        ui.page(
            "Controls",
            ui.button("primary", "Primary button", style="primary"),
            ui.button("secondary", "Secondary button"),
            ui.button("maybe", "Enabled toggles me", enabled=not disabled),
            ui.button("toggle_enabled", "Enable it" if disabled else "Disable it"),
            ui.divider(),
            ui.toggle("demo_toggle", "A toggle", checked=checked),
            ui.label("The toggle is on." if checked else "The toggle is off.", style="caption"),
        ),
        ui.page(
            "Input",
            ui.input("box", label="A text box", placeholder="Type or paste here"),
            ui.label("You typed: " + (typed if typed != "" else "(nothing yet)")),
            ui.label(
                "The keyboard owns this box. Tap it, then use the keys; Paste puts "
                "the clipboard in it.",
                style="caption",
            ),
        ),
        ui.page(
            "Date",
            ui.date("when", label="A date and time", value=picked, time=True),
            ui.label(
                "Picked: " + time.format("EEEE d MMMM yyyy, HH:mm", picked)
                if picked is not None else "Nothing picked yet."
            ),
            ui.label(
                "The keyboard draws the buttons. You get each new value in on_event "
                "and draw whatever you keep. Leave out time for a date alone.",
                style="caption",
            ),
        ),
        ui.page(
            "Layout",
            ui.label("A row splits the width evenly:"),
            ui.row(
                ui.button("one", "One"),
                ui.button("two", "Two"),
                ui.button("three", "Three"),
            ),
            ui.spacer(height=12),
            ui.label("Above is a 12pt spacer. Below is a divider."),
            ui.divider(),
            ui.button("work", "Stop pretending" if working else "Pretend to work"),
            ui.progress() if working else ui.label("(no progress bar)", style="caption"),
        ),
        ui.page(
            "Events",
            event_log(),
            ui.button("clear", "Clear log"),
        ),
    )
