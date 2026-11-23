"""Native Linux GNOME / KDE / Ubuntu AppIndicator (StatusNotifierItem + DBusMenu) via Gio D-Bus.

Renders live usage text (XAyatanaLabel: e.g. 'Claude 93% · Codex 0% · Agy 10%') AND the 4-bar gauge icon
directly inside the native Linux GNOME Top Panel bar alongside system indicators and the clock.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

SNI_NODE_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="XAyatanaLabel" type="s" access="read"/>
    <property name="XAyatanaLabelGuide" type="s" access="read"/>
    <property name="XAyatanaOrderingIndex" type="u" access="read"/>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ProvideXdgActivationToken">
      <arg name="token" type="s" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="XAyatanaSecondaryActivate">
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewIconThemePath">
      <arg type="s" name="icon_theme_path"/>
    </signal>
    <signal name="NewMenu"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
    <signal name="XAyatanaNewLabel">
      <arg type="s" name="label"/>
      <arg type="s" name="guide"/>
    </signal>
  </interface>
</node>
"""

DBUSMENU_NODE_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
  </interface>
</node>
"""


class LinuxTopPanelIndicator:
    """Exports org.kde.StatusNotifierItem + com.canonical.dbusmenu directly into the Linux GNOME Top Panel."""

    def __init__(
        self,
        icon_theme_dir: Path,
        icon_name: str,
        initial_label: str,
        on_activate_tab: Callable[[str], None],
        on_toggle_popover: Callable[[], None],
        on_toggle_floating_bar: Callable[[], None],
        on_refresh: Callable[[], None],
        on_quit: Callable[[], None],
        indicator_id: str = "agentbar",
        instance_index: int = 1,
        activate_tab_id: Optional[str] = None,
    ) -> None:
        from gi.repository import Gio, GLib

        self.Gio = Gio
        self.GLib = GLib
        self.icon_theme_dir = str(icon_theme_dir)
        self.icon_name = icon_name
        self.label = initial_label
        self.on_activate_tab = on_activate_tab
        self.on_toggle_popover = on_toggle_popover
        self.on_toggle_floating_bar = on_toggle_floating_bar
        self.on_refresh = on_refresh
        self.on_quit = on_quit
        self.indicator_id = indicator_id
        self.instance_index = instance_index
        self.activate_tab_id = activate_tab_id

        self.revision = 1
        self.menu_items: List[Dict[str, Any]] = []
        self.registered = False
        self.conn: Optional[Any] = None
        self.bus_name_id: Optional[int] = None
        self.sni_reg_id: Optional[int] = None
        self.menu_reg_id: Optional[int] = None

        self._rebuild_default_menu_items()
        self._start_dbus_service()

    def _rebuild_default_menu_items(
        self, engine_lines: Optional[List[Dict[str, str]]] = None
    ) -> None:
        items: List[Dict[str, Any]] = [
            {
                "id": 1,
                "label": "Show / Hide Usage",
                "action": self.on_toggle_popover,
            },
        ]
        next_id = 2
        if engine_lines:
            for el in engine_lines:
                eid = el["engine_id"]
                lbl = el["label"]
                items.append(
                    {
                        "id": next_id,
                        "label": lbl,
                        "action": (lambda tab=eid: self.on_activate_tab(tab)),
                    }
                )
                next_id += 1

        items.extend(
            [
                {"id": next_id, "type": "separator"},
                {
                    "id": next_id + 1,
                    "label": "👁 Show / Hide Floating Bar",
                    "action": self.on_toggle_floating_bar,
                },
                {
                    "id": next_id + 2,
                    "label": "⚙ Settings...",
                    "action": lambda: self.on_activate_tab("settings"),
                },
                {
                    "id": next_id + 3,
                    "label": "↻ Refresh Now",
                    "action": self.on_refresh,
                },
                {
                    "id": next_id + 4,
                    "label": "✕ Quit",
                    "action": self.on_quit,
                },
            ]
        )
        self.menu_items = items
        self.revision += 1

    def _start_dbus_service(self) -> None:
        Gio = self.Gio
        try:
            address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            flags = (
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
            )
            self.conn = Gio.DBusConnection.new_for_address_sync(
                address, flags, None, None
            )
            sni_info = Gio.DBusNodeInfo.new_for_xml(SNI_NODE_XML).interfaces[0]
            menu_info = Gio.DBusNodeInfo.new_for_xml(DBUSMENU_NODE_XML).interfaces[0]

            self.sni_reg_id = self.conn.register_object(
                "/StatusNotifierItem",
                sni_info,
                self._on_sni_method_call,
                self._on_sni_get_property,
                None,
            )
            self.menu_reg_id = self.conn.register_object(
                "/MenuBar",
                menu_info,
                self._on_menu_method_call,
                self._on_menu_get_property,
                None,
            )

            bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-{self.instance_index}"
            self.bus_name_id = Gio.bus_own_name_on_connection(
                self.conn,
                bus_name,
                Gio.BusNameOwnerFlags.NONE,
                lambda conn, name: self._register_with_watcher(name),
                None,
            )
        except Exception:
            self.registered = False

    def _register_with_watcher(self, service_name: str) -> None:
        if self.conn is None:
            return
        try:
            self.conn.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                self.GLib.Variant("(s)", (service_name,)),
                None,
                self.Gio.DBusCallFlags.NONE,
                1500,
                None,
            )
            self.registered = True
            for delay_ms in (400, 1250, 2100):
                self.GLib.timeout_add(delay_ms, self._emit_delayed_label)
        except Exception:
            self.registered = False

    def _emit_delayed_label(self) -> bool:
        if self.conn is not None:
            try:
                self.conn.emit_signal(
                    None,
                    "/StatusNotifierItem",
                    "org.kde.StatusNotifierItem",
                    "NewStatus",
                    self.GLib.Variant("(s)", ("Active",)),
                )
            except Exception:
                pass
        self.update_panel(self.label)
        return False

    def update_panel(
        self, new_label: str, engine_lines: Optional[List[Dict[str, str]]] = None
    ) -> None:
        """Update the text label and icon in the Linux GNOME Top Panel."""
        GLib = self.GLib
        self.label = new_label
        self._rebuild_default_menu_items(engine_lines)

        if self.conn is None:
            return
        try:
            # Emit XAyatanaNewLabel + PropertiesChanged + NewIcon
            self.conn.emit_signal(
                None,
                "/StatusNotifierItem",
                "org.kde.StatusNotifierItem",
                "XAyatanaNewLabel",
                GLib.Variant("(ss)", (self.label, "")),
            )
            self.conn.emit_signal(
                None,
                "/StatusNotifierItem",
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                GLib.Variant(
                    "(sa{sv}as)",
                    (
                        "org.kde.StatusNotifierItem",
                        {
                            "Id": GLib.Variant("s", self.indicator_id),
                            "Status": GLib.Variant("s", "Active"),
                            "XAyatanaLabel": GLib.Variant("s", self.label),
                        },
                        [],
                    ),
                ),
            )
            self.conn.emit_signal(
                None,
                "/StatusNotifierItem",
                "org.kde.StatusNotifierItem",
                "NewIcon",
                None,
            )
            self.conn.emit_signal(
                None,
                "/MenuBar",
                "com.canonical.dbusmenu",
                "LayoutUpdated",
                GLib.Variant("(ui)", (self.revision, 0)),
            )
        except Exception:
            pass

    def _on_sni_get_property(
        self,
        _conn: Any,
        _sender: str,
        _path: str,
        _iface: str,
        prop_name: str,
    ) -> Any:
        v = self.GLib.Variant
        if prop_name == "Category":
            return v("s", "ApplicationStatus")
        if prop_name == "Id":
            return v("s", self.indicator_id)
        if prop_name == "Title":
            return v("s", self.indicator_id)
        if prop_name == "Status":
            return v("s", "Active")
        if prop_name == "WindowId":
            return v("i", 0)
        if prop_name == "IconThemePath":
            return v("s", self.icon_theme_dir)
        if prop_name == "IconName":
            return v("s", self.icon_name)
        if prop_name in ("IconPixmap", "OverlayIconPixmap", "AttentionIconPixmap"):
            return v("a(iiay)", [])
        if prop_name in ("OverlayIconName", "AttentionIconName", "AttentionMovieName"):
            return v("s", "")
        if prop_name == "Menu":
            return v("o", "/MenuBar")
        if prop_name == "ItemIsMenu":
            return v("b", False)
        if prop_name == "XAyatanaLabel":
            return v("s", self.label)
        if prop_name == "XAyatanaLabelGuide":
            return v("s", "")
        if prop_name == "XAyatanaOrderingIndex":
            return v("u", self.instance_index)
        return None

    def _on_sni_method_call(
        self,
        _conn: Any,
        _sender: str,
        _path: str,
        _iface: str,
        method_name: str,
        _params: Any,
        invocation: Any,
    ) -> None:
        if method_name in (
            "Activate",
            "SecondaryActivate",
            "XAyatanaSecondaryActivate",
            "ContextMenu",
        ):
            if self.activate_tab_id:
                self.GLib.idle_add(self.on_activate_tab, self.activate_tab_id)
            else:
                self.GLib.idle_add(self.on_toggle_popover)
        invocation.return_value(None)

    def close(self) -> None:
        if self.bus_name_id is not None:
            self.Gio.bus_unown_name(self.bus_name_id)
            self.bus_name_id = None
        if self.conn is not None:
            try:
                if self.sni_reg_id is not None:
                    self.conn.unregister_object(self.sni_reg_id)
                if self.menu_reg_id is not None:
                    self.conn.unregister_object(self.menu_reg_id)
                self.conn.close_sync(None)
            except Exception:
                pass
            self.conn = None
        self.registered = False

    def _on_menu_get_property(
        self,
        _conn: Any,
        _sender: str,
        _path: str,
        _iface: str,
        prop_name: str,
    ) -> Any:
        v = self.GLib.Variant
        if prop_name == "Version":
            return v("u", 3)
        if prop_name == "TextDirection":
            return v("s", "ltr")
        if prop_name == "Status":
            return v("s", "normal")
        if prop_name == "IconThemePath":
            return v("as", [self.icon_theme_dir])
        return None

    def _item_to_props(self, item: Dict[str, Any]) -> Dict[str, Any]:
        v = self.GLib.Variant
        if item.get("type") == "separator":
            return {
                "type": v("s", "separator"),
                "visible": v("b", True),
                "enabled": v("b", True),
            }
        return {
            "type": v("s", "standard"),
            "label": v("s", str(item.get("label", ""))),
            "visible": v("b", True),
            "enabled": v("b", True),
        }

    def _on_menu_method_call(
        self,
        _conn: Any,
        _sender: str,
        _path: str,
        _iface: str,
        method_name: str,
        params: Any,
        invocation: Any,
    ) -> None:
        v = self.GLib.Variant

        if method_name == "GetLayout":
            parent_id, _depth, _prop_names = params.unpack()
            if parent_id == 0:
                children = []
                for it in self.menu_items:
                    it_props = self._item_to_props(it)
                    children.append(
                        v("(ia{sv}av)", (int(it["id"]), it_props, []))
                    )
                root_props = {"children-display": v("s", "submenu")}
                layout = (0, root_props, children)
                invocation.return_value(v("(u(ia{sv}av))", (self.revision, layout)))
            else:
                invocation.return_value(
                    v("(u(ia{sv}av))", (self.revision, (parent_id, {}, [])))
                )
            return

        if method_name == "GetGroupProperties":
            ids, _prop_names = params.unpack()
            res = []
            for it in self.menu_items:
                if int(it["id"]) in ids:
                    res.append((int(it["id"]), self._item_to_props(it)))
            invocation.return_value(v("(a(ia{sv}))", (res,)))
            return

        if method_name == "GetProperty":
            item_id, prop_name = params.unpack()
            for it in self.menu_items:
                if int(it["id"]) == item_id:
                    props = self._item_to_props(it)
                    val = props.get(prop_name, v("s", ""))
                    invocation.return_value(v("(v)", (val,)))
                    return
            invocation.return_value(v("(v)", (v("s", ""),)))
            return

        if method_name == "Event":
            item_id, event_id, _data, _ts = params.unpack()
            if event_id == "clicked":
                for it in self.menu_items:
                    if int(it["id"]) == item_id and callable(it.get("action")):
                        self.GLib.idle_add(it["action"])
                        break
            invocation.return_value(None)
            return

        if method_name == "EventGroup":
            events = params.unpack()[0]
            for item_id, event_id, _data, _ts in events:
                if event_id == "clicked":
                    for it in self.menu_items:
                        if int(it["id"]) == item_id and callable(it.get("action")):
                            self.GLib.idle_add(it["action"])
                            break
            invocation.return_value(v("(ai)", ([],)))
            return

        if method_name == "AboutToShow":
            invocation.return_value(v("(b)", (False,)))
            return

        if method_name == "AboutToShowGroup":
            invocation.return_value(v("(aiai)", ([], [])))
            return

        invocation.return_value(None)
