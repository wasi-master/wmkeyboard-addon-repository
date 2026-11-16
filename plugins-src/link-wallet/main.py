# Link wallet: the links you open often, as buttons in the keyboard.
#
# A tap opens the link in the app the phone uses for it. A hold opens the
# link's own page: type it into the field, copy, share, rename, change the
# address, move it, delete it. Add in the header starts from whatever link was
# copied last. No sync and no account: the links are kept in the plugin's
# storage on the phone.

from wm import plugin, ui, share, field, clipboard

import links

saved = plugin.state(persist=True, key="wallet", items=[], next_id=1)
# The editor's boxes: what it is for ("add", "edit" or "rename"), the link it
# changes, the step ("url", then "title") and the words typed so far.
form = plugin.state(mode=None, link=None, step="url", url="", title="", error="")
view = plugin.state(undo=None)

UNDO_SECONDS = 8


def index_of(link_id):
    for i, item in enumerate(saved.items):
        if item["id"] == link_id:
            return i
    return None


def link_of(link_id):
    i = index_of(link_id)
    return None if i is None else saved.items[i]


def put(items):
    saved.items = items


def say(text):
    ui.toast(text)


# ------------------------------------------------------------- opening ----

def open_link(link_id):
    item = link_of(link_id)
    if item is None:
        return
    try:
        share.open(item["url"], ask=False)
    except ValueError:
        say("That link can't be opened.")
    except PermissionError:
        say("Turn on Share for Link wallet in its plugin settings to open links.")


# -------------------------------------------------------------- adding ----

def copied_link():
    """The link on the clipboard, if the user lets the plugin read it."""
    try:
        return links.first_link_in(clipboard.get() or "") or ""
    except PermissionError:
        return ""


@plugin.command("Add", icon="add", id="add")
def start_add():
    if len(saved.items) >= links.MOST_LINKS:
        say("The wallet is full: " + str(links.MOST_LINKS) + " links.")
        return
    form.update(mode="add", link=None, step="url", url=copied_link(), title="", error="")
    plugin.push(editor, title="Add a link")


def start_edit(link_id):
    item = link_of(link_id)
    if item is None:
        return
    form.update(mode="edit", link=link_id, step="url", url=item["url"], title=item["title"], error="")
    plugin.push(editor, title="Change link")


def start_rename(link_id):
    item = link_of(link_id)
    if item is None:
        return
    form.update(mode="rename", link=link_id, step="title", url=item["url"], title=item["title"], error="")
    plugin.push(editor, title="Rename")


def url_typed(value):
    form.url = value
    form.error = ""


def title_typed(value):
    form.title = value


def paste():
    try:
        text = clipboard.get() or ""
    except PermissionError:
        say("Turn on Read the clipboard for Link wallet in its plugin settings to paste here.")
        return
    form.url = links.first_link_in(text) or text.strip()
    form.error = ""


def url_next(value=None):
    if value is not None:
        form.url = value
    clean = links.normalise(form.url)
    if clean is None:
        form.error = "That isn't a web address. Type one like example.com or https://example.com/page."
        return
    form.url = clean
    form.error = ""
    form.step = "title"
    if form.mode == "add" and not form.title.strip():
        form.title = links.host_of(clean)


def save(value=None):
    if value is not None:
        form.title = value
    title = links.clean_title(form.title, form.url)
    items = list(saved.items)
    if form.mode == "add":
        items.append({"id": saved.next_id, "title": title, "url": form.url})
        saved.next_id = saved.next_id + 1
    else:
        i = index_of(form.link)
        if i is None:
            plugin.back()
            return
        item = dict(items[i])
        item["title"] = title
        if form.mode == "edit":
            item["url"] = form.url
        items[i] = item
    put(items)
    form.update(mode=None, link=None, step="url", url="", title="", error="")
    plugin.back()


def cancel():
    form.update(mode=None, link=None, step="url", url="", title="", error="")
    plugin.back()


def editor():
    if form.step == "url":
        ui.input(label="Address", value=form.url, kind="url", placeholder="https://example.com",
                 on_change=url_typed, on_submit=url_next, key="url")
        if form.error:
            ui.label(form.error, color="danger")
        else:
            ui.caption("A name like example.com gets https:// in front.")
        ui.row(ui.button("Paste", icon="content_paste", on_click=paste, key="paste"),
               ui.button("Cancel", on_click=cancel, key="cancel"),
               ui.button("Next", primary=True, on_click=url_next, key="next"))
    else:
        if form.mode != "rename":
            ui.caption(form.url)
        ui.input(label="Name on the button", value=form.title, placeholder=links.host_of(form.url),
                 on_change=title_typed, on_submit=save, key="title")
        ui.row(ui.button("Cancel", on_click=cancel, key="cancel"),
               ui.button("Save", primary=True, on_click=save, key="save"))


# ------------------------------------------------------- a link's page ----

def type_it(link_id):
    item = link_of(link_id)
    if item is not None:
        field.insert(item["url"])
        plugin.back()


def copy_it(link_id):
    item = link_of(link_id)
    if item is not None:
        clipboard.set(item["url"])
        say("Copied")
        plugin.back()


def share_it(link_id):
    item = link_of(link_id)
    if item is not None:
        share.text(item["url"], title=item["title"])


def move(link_id, by):
    i = index_of(link_id)
    if i is None:
        return
    to = max(0, min(len(saved.items) - 1, i + by))
    if to == i:
        return
    items = list(saved.items)
    item = items.pop(i)
    items.insert(to, item)
    put(items)


def delete(link_id):
    i = index_of(link_id)
    if i is None:
        return
    items = list(saved.items)
    item = items.pop(i)
    put(items)
    view.undo = {"index": i, "link": item}
    plugin.after(UNDO_SECONDS, forget_undo, name="undo")
    plugin.back()


def forget_undo():
    view.undo = None


def undo():
    gone = view.undo
    view.undo = None
    plugin.cancel("undo")
    if gone is None or index_of(gone["link"]["id"]) is not None:
        return
    items = list(saved.items)
    items.insert(min(gone["index"], len(items)), gone["link"])
    put(items)


def link_page(link_id):
    def draw():
        i = index_of(link_id)
        if i is None:
            ui.empty("This link is gone.", icon="link_off")
            return
        item = saved.items[i]
        last = len(saved.items) - 1
        ui.caption(item["url"])
        actions = [
            ui.item("Open", icon="open_in_new", on_click=lambda: open_link(link_id)),
            ui.item("Type it", subtitle="Into the field you're typing in", icon="keyboard",
                    on_click=lambda: type_it(link_id)),
            ui.item("Copy", icon="content_copy", on_click=lambda: copy_it(link_id)),
            ui.item("Share", icon="share", on_click=lambda: share_it(link_id)),
            ui.item("Rename", icon="edit", on_click=lambda: start_rename(link_id)),
            ui.item("Change link", icon="link", on_click=lambda: start_edit(link_id)),
        ]
        if i > 0:
            actions.append(ui.item("Move back", icon="arrow_back", on_click=lambda: move(link_id, -1)))
        if i < last:
            actions.append(ui.item("Move forward", icon="arrow_forward", on_click=lambda: move(link_id, 1)))
        actions.append(ui.item("Delete", icon="delete", on_click=lambda: delete(link_id)))
        ui.list(actions, key="actions")
        ui.caption("Place " + str(i + 1) + " of " + str(last + 1) + ".")
    return draw


def held(link_id):
    item = link_of(link_id)
    if item is not None:
        plugin.push(link_page(link_id), title=item["title"])


# --------------------------------------------------------------- panel ----

def button_for(item):
    link_id = item["id"]
    return ui.card(
        ui.label(item["title"], style="title"),
        ui.caption(links.host_of(item["url"])),
        on_click=lambda: open_link(link_id),
        on_hold=lambda: held(link_id),
        key="link" + str(link_id),
    )


def render():
    if view.undo is not None:
        ui.row(ui.label("Deleted " + view.undo["link"]["title"], color="muted"),
               ui.button("Undo", on_click=undo, key="undo"))
    if not saved.items:
        ui.empty("No links yet. Copy a link, then tap Add.", icon="bookmarks", action="Add a link",
                 on_click=start_add)
        return
    ui.grid(*[button_for(item) for item in saved.items], columns=2)
    ui.caption("Tap a link to open it. Hold one to type, copy, share, rename, move or delete it.")
