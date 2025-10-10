# -*- coding: utf-8 -*-
"""In-progress code for a hotkey-editing GUI"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import html, logging, os, pprint
from typing import Any, Dict, Iterable, List, Tuple

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf

from quicktile.config import DEFAULTS
from quicktile.commands import commands

ICON_PATH = os.path.join(os.path.dirname(__file__), 'icon.svg')

log = logging.getLogger(__name__)


class GeneralConfigPane(Gtk.VBox):
    def __init__(self, *args, **kwargs):
        super(GeneralConfigPane, self).__init__(*args, **kwargs)

        self.movements_wrap = Gtk.CheckButton.new_with_label(
            " *-next and *-prev actions wrap around")
        self.margin_x = Gtk.SpinButton.new(
            Gtk.Adjustment(0, 0, 101, 1, 10, 1), 1, 0)
        self.margin_y = Gtk.SpinButton.new(
            Gtk.Adjustment(0, 0, 101, 1, 10, 1), 1, 0)

        margin_row = Gtk.HBox()
        margin_row.pack_start(
            Gtk.Label(label="Window margins: "), False, False, 0)
        margin_row.pack_start(self.margin_x, False, False, 0)
        margin_row.pack_start(Gtk.Label(label=" x "), False, False, 0)
        margin_row.pack_start(self.margin_y, False, False, 0)

        self.set_border_width(10)
        self.set_spacing(10)
        self.pack_start(margin_row, False, False, 0)
        self.pack_start(self.movements_wrap, False, False, 0)


class HotkeyConfigPane(Gtk.ScrolledWindow):
    """Scrolling list of editable keybindings"""

    def __init__(self, *args, **kwargs):
        super(HotkeyConfigPane, self).__init__(*args, **kwargs)

        self._store = Gtk.ListStore(str, str)  # [Accel, Action]
        self._actions = Gtk.ListStore(str)  # [Action]
        self._conflicting: List[Tuple[int, Gdk.ModifierType]] = []
        view = self._build_view(self._store, self._actions)
        self.add(view)

    def _build_view(self, store: Gtk.ListStore, actions: Gtk.ListStore
                    ) -> Gtk.TreeView:
        """Construct and return the view widget"""
        view = Gtk.TreeView(model=store)
        view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        view.set_property("activate-on-single-click", True)
        view.set_property("enable-grid-lines", Gtk.TreeViewGridLines.BOTH)
        view.connect("key-press-event", self._cb_keypress)
        view.connect("row-activated", self._cb_row_activated)

        key_renderer = Gtk.CellRendererAccel()
        key_renderer.set_property("editable", True)
        key_renderer.connect("accel-edited", self._cb_key_edited)
        key_column = Gtk.TreeViewColumn("Hotkey", key_renderer)
        key_column.set_cell_data_func(key_renderer, self._cb_key_data_func)
        key_column.set_expand(True)
        key_column.column_id = 'key'
        view.append_column(key_column)

        action_renderer = Gtk.CellRendererCombo()
        action_renderer.set_property("editable", True)
        action_renderer.set_property("model", actions)
        action_renderer.set_property("text-column", 0)
        action_renderer.set_property("has-entry", False)
        action_renderer.connect("edited", self._cb_action_edited)
        action_column = Gtk.TreeViewColumn("Action", action_renderer, text=1)
        action_column.set_cell_data_func(action_renderer,
            self._cb_action_data_func)
        action_column.set_expand(True)
        action_column.column_id = 'action'
        view.append_column(action_column)

        remove_renderer = Gtk.CellRendererPixbuf()
        remove_column = Gtk.TreeViewColumn(" ", remove_renderer)
        remove_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        remove_column.set_expand(False)
        remove_column.set_cell_data_func(remove_renderer,
            self._cb_remove_data_func)
        remove_column.column_id = 'add_remove'
        view.append_column(remove_column)

        view.set_property("has-tooltip", True)
        view.connect("query-tooltip", self._cb_query_tooltip)

        return view

    def _cb_action_edited(self, widget: Gtk.CellRendererAccel, path: str,
            text: str) -> None:
        """Handler for committing changes to hotkey cells"""
        self._store[path][1] = text.strip()
        self.ensure_new_row()

    def _cb_action_data_func(self, column: Gtk.TreeViewColumn,
            cell: Gtk.CellRendererCombo, model: Gtk.ListStore,
            treeiter: Gtk.TreeIter, _data: Any = None) -> None:
        """Data function to render action column in human-friendly form
        and implement unset indication"""
        text = model[treeiter][1].strip()
        cell.set_property("text", text)
        cell.set_property("markup", html.escape(text) if text
            else '<span color="gray">(unset)</span>')

    def _cb_key_data_func(self, column: Gtk.TreeViewColumn,
            cell: Gtk.CellRendererAccel, model: Gtk.ListStore,
            treeiter: Gtk.TreeIter, _data: Any = None) -> None:
        """Data function to render hotkey column in human-friendly form
        and implement warning about conflicting keybindings"""
        key = Gtk.accelerator_parse(model[treeiter][0])
        text = Gtk.accelerator_get_label(*key)
        cell.set_property("text", text)

        if key in self._conflicting:
            markup = '<span color="red">{}</span>'.format(html.escape(text))
        elif not text.strip():
            markup = '<span color="gray">(unset)</span>'
        else:
            markup = text
        cell.set_property("markup", markup)

    def _cb_key_edited(self, widget: Gtk.CellRendererAccel, path: str,
            accel_key: int, accel_mods: Gdk.ModifierType,
            hardware_keycode: int, _data: Any = None) -> None:
        """Handler for committing changes to hotkey cells"""
        self._store[path][0] = Gtk.accelerator_name(accel_key, accel_mods)
        self.ensure_new_row()
        self.update_collision_warnings()

    def _cb_keypress(self, widget: Gtk.TreeView, event: Gdk.EventKey) -> bool:
        """Handler for key-press-event on the view when not in edit mode"""
        if event.get_keyval()[1] != Gdk.KEY_Delete:
            return False

        # Get index-independent references before we start to modify anything
        model, selected = widget.get_selection().get_selected_rows()
        rows = [Gtk.TreeRowReference.new(model, x) for x in selected]

        for row in rows:
            self._remove_row(row)

        return True

    @staticmethod
    def _cb_query_tooltip(view: Gtk.Widget, x: int, y: int, kbd_mode: bool,
            tooltip: Gtk.Tooltip) -> bool:
        """Provide a tooltip for the column with the remove icons"""
        if kbd_mode:
            path, column = view.get_cursor()
            if not all([path, column]):
                return False
        else:
            result = view.get_path_at_pos(
                *view.convert_widget_to_bin_window_coords(x, y))
            if not result:
                return False
            path, column, _, _ = result

        if getattr(column, "column_id", None) == "add_remove":
            tooltip.set_text("Remove Hotkey")
            view.set_tooltip_cell(tooltip, path, column, None)
        else:
            tooltip.set_text("Click to select, click again to edit")
            view.set_tooltip_cell(tooltip, path, column, None)
        return True

    @staticmethod
    def _cb_remove_data_func(column: Gtk.TreeViewColumn,
            cell: Gtk.CellRendererPixbuf, model: Gtk.ListStore,
            treeiter: Gtk.TreeIter, data=None) -> None:
        """Data function to render remove button without a model column"""
        if model[treeiter][0] or model[treeiter][1]:
            cell.set_property("icon_name", "list-remove")
        else:
            cell.set_property("icon_name", "")

    def _cb_row_activated(self, view: Gtk.TreeView, path: Gtk.TreePath,
            column: Gtk.TreeViewColumn) -> bool:
        """Handler to implement clickable 'Remove Hotkey' button"""
        if getattr(column, "column_id", None) != "add_remove":
            return False

        self._remove_row(Gtk.TreeRowReference.new(self._store, path))
        return True

    @property
    def conflicting(self):
        """Read-only public interface for list of conflicting bindings"""
        return self._conflicting[:]

    def ensure_new_row(self):
        """Ensure there's a blank row at the bottom"""
        if self._store[-1][0] or self._store[-1][1]:
            self._store.append(["", ""])

    def get_rows(self) -> Dict[str, str]:
        """Get the updated state of the hotkeys, excluding incomplete rows"""
        output = {}
        action_names = [x[0] for x in self._actions]
        for row in self._store:
            # Omit rows with empty cells
            if not (row[0] and row[1]):
                continue

            # Warn on invalid rows that somehow managed to slip in
            # but don't delete them to avoid unnecessary potential data loss
            # (Assume that, if we received them, it's not our job to throw
            # them away)
            if row[1] not in action_names:
                log.warning("Unrecognized action name: %s", row[1])

            output[row[0]] = row[1]
        return output

    def set_actions(self, action_names: Iterable[str]) -> None:
        """Set the list of combo box entries for the actions column"""
        self._actions.clear()
        for name in sorted(action_names):
            self._actions.append([name])

    def set_rows(self, mappings: Dict[str, str]) -> None:
        """Set the list of rows in the view"""
        self._store.clear()
        for key, value in sorted(mappings.items()):
            self._store.append([key, value])
        self.ensure_new_row()
        self.update_collision_warnings()

    def _remove_row(self, row: Gtk.TreeRowReference) -> None:
        """Unified helper for removing a row while maintaining invariants"""
        if not row.valid():
            return

        concrete_row = self._store[row.get_path()]
        if concrete_row[0] or concrete_row[1]:
            self._store.remove(self._store.get_iter(row.get_path()))
        self.ensure_new_row()
        self.update_collision_warnings()

    def update_collision_warnings(self) -> None:
        """Update list of conflicting keybindings"""
        # Collect the collisions
        groups: Dict[Tuple[int, int], Gtk.TreePath] = {}
        tree_iter = self._store.get_iter_first()
        while tree_iter:
            path = self._store.get_path(tree_iter)
            binding = Gtk.accelerator_parse(self._store[path][0])
            groups.setdefault(binding, []).append(path)
            tree_iter = self._store.iter_next(tree_iter)

        self._conflicting = [x[0] for x in groups.items() if len(x[1]) > 1]


class ConfigDialog(Gtk.Dialog):
    """TODO: Just make this a widget/pane I can embed in a config window"""

    def __init__(self, *args, **kwargs):
        super(ConfigDialog, self).__init__(title="QuickTile Configuration",
            *args, **kwargs)
        self.set_default_size(400, 300)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_icon(GdkPixbuf.Pixbuf.new_from_file(ICON_PATH))

        self.general = GeneralConfigPane()
        self.hotkeys = HotkeyConfigPane()
        notebook = Gtk.Notebook()
        notebook.append_page(self.general, Gtk.Label(label="General"))
        notebook.append_page(self.hotkeys, Gtk.Label(label="Keybindings"))
        self.get_content_area().pack_start(notebook, True, True, 0)

        self.connect("response", self._cb_response)
        self.show_all()

    def _cb_response(self, widget, response_id):
        """Handler to prompt for confirmation if a conflict is OK'd"""
        if response_id == Gtk.ResponseType.OK and self.hotkeys.conflicting:
            msg = Gtk.MessageDialog(
                parent=self,
                text="You have assigned the same hotkey to more than one "
                "action.\nThis may result in unpredictable behaviour.\n\n"
                "Are you sure you want to continue?",
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
            )
            response = msg.run()
            msg.destroy()
            if response == Gtk.ResponseType.NO:
                widget.stop_emission_by_name("response")
                return True
        return False


if __name__ == "__main__":
    # Opt into allowing AltGr to be used for keybindings
    # TODO: Make sure I can actually *use* all the modifiers via XGrabKey
    Gtk.accelerator_set_default_mod_mask(
        Gtk.accelerator_get_default_mod_mask() | Gdk.ModifierType.MOD5_MASK)

    dialog = ConfigDialog()

    # TODO: Use the FULL command set as dynamically defined by the config file
    dialog.hotkeys.set_actions(commands)

    # TODO: Load from the QuickTile config file
    dialog.hotkeys.set_rows({str(DEFAULTS['general']['ModMask']) + x: str(y)
        for x, y in DEFAULTS['keys'].items()})

    dialog.connect("destroy", Gtk.main_quit)
    if dialog.run() == Gtk.ResponseType.OK:
        print("TODO: Update config to ",
            pprint.pformat(dialog.hotkeys.get_rows()))

# vim: set sw=4 sts=4 expandtab :
