"""Settings window (GTK 4 + libadwaita). Each tab is a Page subclass listed in
PAGES; future settings get their own Page there."""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import (BUS_NAME, HINGE_SOURCE, INTERFACE, OBJECT_PATH, SETTINGS_APP_ID,  # noqa: E402
               __version__, fmt, updates)

RECENT_MAX = 50
VARIANT_TYPES = {"blocklist": "as", "update_check": "b", "integrations": "as"}  # everything else is a scale ("d")


# [doc:ui-client]
class DaemonClient:
    """Thin wrapper around the daemon's D-Bus API (starts it via activation)."""

    def __init__(self):
        self.proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES, None,
            BUS_NAME, OBJECT_PATH, INTERFACE, None)

    def _call(self, method, params=None):
        return self.proxy.call_sync(method, params, Gio.DBusCallFlags.NONE, 10000, None)

    def status(self):
        return self._call("Status").unpack()[0]

    def settings(self):
        return self._call("GetSettings").unpack()[0]

    def recent(self):
        return [tuple(call) for call in self._call("RecentCalls").unpack()[0]]

    def update(self, **changes):
        variants = {key: GLib.Variant(VARIANT_TYPES.get(key, "d"), value)
                    for key, value in changes.items()}
        self._call("SetSettings", GLib.Variant("(a{sv})", (variants,)))

    def check_updates(self):
        self._call("CheckForUpdates")


# [doc:ui-page-base]
class Page(Adw.PreferencesPage):
    """One tab. Subclasses set key/title_text/icon, build rows, and react to
    daemon signals in on_signal()."""

    key = title_text = icon = ""

    def __init__(self, client, toast):
        super().__init__(title=self.title_text, icon_name=self.icon)
        self.client = client
        self.toast = toast

    def guard(self, func, *args, **kwargs):
        """Run a daemon call; show failures as a toast instead of raising."""
        try:
            return func(*args, **kwargs)
        except GLib.Error as exc:
            self.toast(fmt.remote_error(exc.message))
            return None

    def on_signal(self, name, args):
        pass

    def open_uri(self, uri):
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as exc:
            self.toast(exc.message)


SCALE_ROWS = (
    ("default_scale", "Default scale",
     "GNOME's display scale, used in laptop mode. Saved permanently; GNOME asks to confirm"),
    ("tablet_scale", "Temporary zoom",
     "Used in tablet mode and when switched with the shortcut; never saved to GNOME"),
)


# [doc:ui-scaling]
class ScalingPage(Page):
    key, title_text, icon = "scaling", "Scaling", "video-display-symbolic"

    def __init__(self, client, toast):
        super().__init__(client, toast)
        self._updating = False
        self.rows = {}
        self.subtitles = {}
        current = Adw.PreferencesGroup(title="Current state")
        self.status_row = Adw.ActionRow(title="Mode", use_markup=False)
        current.add(self.status_row)
        self.warning_row = Adw.ActionRow(title="Tablet mode detection unreliable",
                                         use_markup=False, visible=False,
                                         css_classes=["warning"])
        self.warning_row.add_prefix(Gtk.Image(icon_name="dialog-warning-symbolic"))
        fix = Gtk.Button(label="How to fix", valign=Gtk.Align.CENTER, css_classes=["flat"],
                         tooltip_text=updates.TROUBLESHOOTING_DOC_URL)
        fix.connect("clicked", lambda _b: self.open_uri(updates.TROUBLESHOOTING_DOC_URL))
        self.warning_row.add_suffix(fix)
        current.add(self.warning_row)
        self.add(current)
        self.scale_group = Adw.PreferencesGroup(title="Scale")
        self.add(self.scale_group)
        self.refresh()

    def refresh(self):
        settings = self.guard(self.client.settings)
        if settings is not None:
            if not self.rows:
                self._build_rows(settings["supported_scales"])
            self._show_settings(settings)
        self._show_status(self.guard(self.client.status))

    def _show_status(self, status):
        if status:
            follow = "manual override" if status["manual"] else "following the hinge"
            self.status_row.set_subtitle(
                f"{status['mode'].capitalize()} · {fmt.percent(status['scale'])} · {follow}")

    # [doc:ui-scale-rows]
    def _build_rows(self, supported):
        """Dropdown of the scales Mutter offers; spin row if it offers none
        (e.g. apply_command backend)."""
        supported = sorted(supported)
        for key, title, subtitle in SCALE_ROWS:
            if supported:
                model = Gtk.StringList.new([fmt.percent(s) for s in supported])
                row = Adw.ComboRow(title=title, subtitle=subtitle, model=model)
                row.connect("notify::selected", self._on_selected, key)
            else:
                row = Adw.SpinRow.new_with_range(100, 400, 1)
                row.set_title(title)
                row.set_subtitle(subtitle)
                row.set_digits(2)
                row.connect("notify::value", self._on_value, key)
            self.rows[key] = (row, supported)
            self.subtitles[key] = subtitle
            self.scale_group.add(row)

    def _show_settings(self, settings):
        self._updating = True
        try:
            for key, (row, supported) in self.rows.items():
                if supported:
                    row.set_selected(fmt.nearest_index(supported, settings[key]))
                else:
                    row.set_value(settings[key] * 100)
            warning = settings.get("sensor_warning", "")
            self.warning_row.set_visible(bool(warning))
            self.warning_row.set_subtitle(warning)
            pending = settings.get("default_pending")
            self.rows["default_scale"][0].set_subtitle(
                "Waiting for confirmation in GNOME’s dialog…" if pending
                else self.subtitles["default_scale"])
        finally:
            self._updating = False

    def _on_selected(self, row, _pspec, key):
        if not self._updating:
            self.guard(self.client.update, **{key: self.rows[key][1][row.get_selected()]})

    def _on_value(self, row, _pspec, key):
        if not self._updating:
            self.guard(self.client.update, **{key: row.get_value() / 100})

    def on_signal(self, name, args):
        if name == "SettingsChanged" and self.rows:
            self._show_settings(args[0])
        elif name == "ModeChanged":
            self._show_status(self.guard(self.client.status))


CATEGORY_TITLES = {"dock": "Docks", "launcher": "Launchers", "desktop": "Desktop"}
CATEGORY_ORDER = ("dock", "launcher", "desktop")


# [doc:ui-integrations]
class IntegrationsPage(Page):
    """One switch per installed integration, grouped by category; rebuilt
    only when the list or its state changes."""

    key, title_text, icon = "integrations", "Integrations", "application-x-addon-symbolic"

    def __init__(self, client, toast):
        super().__init__(client, toast)
        self.groups = []
        self.items = None
        self.refresh()

    def refresh(self):
        settings = self.guard(self.client.settings)
        if settings is not None:
            self._show(settings.get("integrations", []))

    def _how_button(self):
        button = Gtk.Button(label="How to add", valign=Gtk.Align.CENTER, css_classes=["flat"],
                            tooltip_text=updates.INTEGRATIONS_DOC_URL)
        button.connect("clicked", lambda _b: self.open_uri(updates.INTEGRATIONS_DOC_URL))
        return button

    def _show(self, items):
        items = [dict(item) for item in items]
        if items == self.items:
            return
        self.items = items
        for group in self.groups:
            self.remove(group)
        self.groups = []
        intro = ("Applied while the device is folded into tablet mode, "
                 "and undone when you unfold it.")
        if not items:
            group = Adw.PreferencesGroup(title="Tablet mode integrations", description=intro)
            group.add(Adw.ActionRow(
                title="No integrations installed", use_markup=False,
                subtitle="Add your own with “How to add”."))
            group.set_header_suffix(self._how_button())
            self.groups.append(group)
        categories = sorted({item["category"] for item in items},
                            key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99, c))
        for category in categories:
            group = Adw.PreferencesGroup(title=CATEGORY_TITLES.get(category, category.title()))
            if not self.groups:
                group.set_description(intro)
                group.set_header_suffix(self._how_button())
            for item in (i for i in items if i["category"] == category):
                subtitle = item["note"] or item["description"]
                if item["active"]:
                    subtitle = f"Active now · {subtitle}"
                row = Adw.SwitchRow(title=item["title"], subtitle=subtitle, use_markup=False,
                                    active=item["enabled"],
                                    sensitive=item["available"] or item["enabled"])
                row.connect("notify::active", self._on_toggle, item["id"])
                group.add(row)
            self.groups.append(group)
        for group in self.groups:
            self.add(group)

    def _on_toggle(self, row, _pspec, integration_id):
        enabled = {item["id"] for item in self.items if item["enabled"]}
        (enabled.add if row.get_active() else enabled.discard)(integration_id)
        self.guard(self.client.update, integrations=sorted(enabled))

    def on_signal(self, name, args):
        if name == "SettingsChanged":
            self._show(args[0].get("integrations", []))


# [doc:ui-sources]
class SourcesPage(Page):
    key, title_text, icon = "sources", "Sources", "system-run-symbolic"

    def __init__(self, client, toast):
        super().__init__(client, toast)
        self.calls, self.blocklist = [], []
        recent = Adw.PreferencesGroup(
            title="Recent calls",
            description="Who used the trigger API since the daemon started, newest first; "
                        "hinge changes are listed for context. Trigger a call with "
                        "“kohaku-tabletd toggle” from a terminal, a key binding or a script.")
        how = Gtk.Button(label="How to trigger", valign=Gtk.Align.CENTER, css_classes=["flat"],
                         tooltip_text=updates.TRIGGERS_DOC_URL)
        how.connect("clicked", lambda _b: self.open_uri(updates.TRIGGERS_DOC_URL))
        recent.set_header_suffix(how)
        self.recent_box = self._list_box("No calls yet")
        recent.add(self.recent_box)
        blocked = Adw.PreferencesGroup(
            title="Blocklist",
            description="Trigger calls from these sources are refused. Names match the sources above.")
        self.block_box = self._list_box(None)
        blocked.add(self.block_box)
        self.add(recent)
        self.add(blocked)
        self.refresh()

    @staticmethod
    def _list_box(placeholder):
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        if placeholder:
            box.set_placeholder(Gtk.Label(label=placeholder, margin_top=12, margin_bottom=12,
                                          css_classes=["dim-label"]))
        return box

    def refresh(self):
        settings = self.guard(self.client.settings)
        calls = self.guard(self.client.recent)
        if settings is not None:
            self.blocklist = list(settings["blocklist"])
        if calls is not None:
            self.calls = calls
        self._render_recent()
        self._render_blocklist()

    # [doc:ui-recent]
    def _render_recent(self):
        self.recent_box.remove_all()
        for time_ms, action, source, chain, blocked in reversed(self.calls):
            row = Adw.ActionRow(title=source, use_markup=False,
                                subtitle=f"{action} · {fmt.when(time_ms)} · {chain}")
            if blocked:
                row.add_prefix(Gtk.Image(icon_name="action-unavailable-symbolic",
                                         tooltip_text="Refused (blocked)"))
            if source != HINGE_SOURCE:
                is_blocked = source in self.blocklist
                button = Gtk.Button(label="Unblock" if is_blocked else "Block",
                                    valign=Gtk.Align.CENTER, css_classes=["flat"])
                button.connect("clicked", self._on_block, source, not is_blocked)
                row.add_suffix(button)
            self.recent_box.append(row)

    # [doc:ui-blocklist]
    def _render_blocklist(self):
        self.block_box.remove_all()
        for name in self.blocklist:
            row = Adw.ActionRow(title=name, use_markup=False)
            button = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Remove",
                                valign=Gtk.Align.CENTER, css_classes=["flat"])
            button.connect("clicked", self._on_block, name, False)
            row.add_suffix(button)
            self.block_box.append(row)
        entry = Adw.EntryRow(title="Add a source by name", show_apply_button=True)
        entry.connect("apply", lambda row: self._on_block(row, row.get_text(), True))
        self.block_box.append(entry)

    def _on_block(self, _widget, source, block):
        names = set(self.blocklist)
        (names.add if block else names.discard)(source.strip())
        self.guard(self.client.update, blocklist=sorted(n for n in names if n))

    def on_signal(self, name, args):
        if name == "CallRecorded":
            self.calls = (self.calls + [tuple(args)])[-RECENT_MAX:]
            self._render_recent()
        elif name == "SettingsChanged":
            self.blocklist = list(args[0]["blocklist"])
            self._render_recent()
            self._render_blocklist()


# [doc:ui-about]
class AboutPage(Page):
    key, title_text, icon = "about", "About", "help-about-symbolic"

    def __init__(self, client, toast):
        super().__init__(client, toast)
        self._updating = False
        self._release_url = updates.RELEASES_URL
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_bottom=6)
        header.append(Gtk.Image(icon_name=SETTINGS_APP_ID, pixel_size=128,
                                css_classes=["icon-dropshadow"]))
        header.append(Gtk.Label(label="Tablet Mode", css_classes=["title-1"]))
        header.append(Gtk.Label(label="kohaku-tabletd", css_classes=["dim-label"]))
        top = Adw.PreferencesGroup()
        top.add(header)
        self.add(top)
        project = Adw.PreferencesGroup(title="kohaku-tabletd")
        project.add(Adw.ActionRow(title="Version", subtitle=__version__, use_markup=False))
        link = Adw.ActionRow(title="Source code", subtitle=updates.REPO_URL,
                             activatable=True, use_markup=False)
        link.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
        link.connect("activated", lambda _row: self.open_uri(updates.REPO_URL))
        project.add(link)
        self.add(project)

        group = Adw.PreferencesGroup(title="Updates")
        self.switch = Adw.SwitchRow(
            title="Check for updates",
            subtitle="Daily against GitHub releases, with a notification when a new version is out")
        self.switch.connect("notify::active", self._on_toggle)
        self.status_row = Adw.ActionRow(title="Status", use_markup=False)
        self.release_button = Gtk.Button(label="Open release", valign=Gtk.Align.CENTER,
                                         css_classes=["suggested-action"], visible=False)
        self.release_button.connect("clicked", lambda _b: self.open_uri(self._release_url))
        self.check_button = Gtk.Button(label="Check now", valign=Gtk.Align.CENTER)
        self.check_button.connect("clicked", lambda _b: self.guard(self.client.check_updates))
        self.status_row.add_suffix(self.release_button)
        self.status_row.add_suffix(self.check_button)
        group.add(self.switch)
        group.add(self.status_row)
        self.add(group)
        self.refresh()

    def refresh(self):
        settings = self.guard(self.client.settings)
        if settings is not None:
            self._show(settings)

    def _show(self, settings):
        self._updating = True
        try:
            self.switch.set_active(settings["update_check"])
        finally:
            self._updating = False
        self.status_row.set_subtitle(fmt.update_summary(settings))
        self._release_url = settings["update_url"] or updates.RELEASES_URL
        self.release_button.set_visible(settings["update_state"] == "available")
        self.check_button.set_sensitive(settings["update_state"] != "checking")

    def _on_toggle(self, row, _pspec):
        if not self._updating:
            self.guard(self.client.update, update_check=row.get_active())

    def on_signal(self, name, args):
        if name == "SettingsChanged":
            self._show(args[0])


# [doc:ui-pages]
PAGES = (ScalingPage, IntegrationsPage, SourcesPage, AboutPage)  # future settings: add a Page subclass here


# [doc:ui-window]
class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, app, client):
        super().__init__(application=app, title="Tablet Mode", default_width=600, default_height=680)
        self.overlay = Adw.ToastOverlay()
        stack = Adw.ViewStack()
        self.pages = [page_class(client, self.toast) for page_class in PAGES]
        for page in self.pages:
            stack.add_titled_with_icon(page, page.key, page.title_text, page.icon)
        self.overlay.set_child(stack)
        header = Adw.HeaderBar(
            title_widget=Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE))
        view = Adw.ToolbarView(content=self.overlay)
        view.add_top_bar(header)
        self.set_content(view)
        client.proxy.connect("g-signal", self._on_signal)

    def toast(self, message):
        self.overlay.add_toast(Adw.Toast(title=GLib.markup_escape_text(message)))

    def _on_signal(self, _proxy, _sender, name, params):
        args = params.unpack()
        for page in self.pages:
            page.on_signal(name, args)


def _error_window(app, message):
    window = Adw.ApplicationWindow(application=app, title="Tablet Mode",
                                   default_width=480, default_height=360)
    view = Adw.ToolbarView(content=Adw.StatusPage(
        icon_name="dialog-error-symbolic", title="Daemon not reachable",
        description=GLib.markup_escape_text(message)))
    view.add_top_bar(Adw.HeaderBar())
    window.set_content(view)
    return window


# [doc:ui-app]
class SettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=SETTINGS_APP_ID)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(SETTINGS_APP_ID)

    def do_activate(self):
        window = self.get_active_window()
        if window is None:
            try:
                client = DaemonClient()
                client.settings()
            except GLib.Error as exc:
                window = _error_window(self, fmt.remote_error(exc.message))
            else:
                window = SettingsWindow(self, client)
        window.present()


def main():
    return SettingsApp().run([sys.argv[0]])
