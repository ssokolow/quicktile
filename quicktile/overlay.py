"""Grid overlay for visual window tiling"""

__author__ = "Greg"
__license__ = "GNU GPL 2.0 or later"

import logging
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GLib

from .util import Rectangle

log = logging.getLogger(__name__)


class GridOverlay(Gtk.Window):
    """A centered grid overlay dialog for visual window tiling.

    Uses POPUP window type to avoid WM focus stealing issues.
    """

    def __init__(self, winman, monitor_geom, rows=3, cols=3):
        super().__init__()
        self.winman = winman
        self.monitor_geom = Rectangle(*monitor_geom)
        self.rows = rows
        self.cols = cols

        self.first_corner = None
        self.second_corner = None
        self.selection_active = False
        self.target_window = None  # Store the window to reposition

        self._setup_window()
        self._setup_events()

    def _setup_window(self):
        """Configure the overlay window properties."""
        # POPUP type is designed for transient UI like menus/overlays
        # It doesn't get decorated and WM treats it specially
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_accept_focus(True)
        self.set_focus_on_map(True)
        self.set_app_paintable(True)

        # Size: ~half screen, centered on monitor
        overlay_width = int(self.monitor_geom.width * 0.5)
        overlay_height = int(self.monitor_geom.height * 0.5)
        overlay_x = self.monitor_geom.x + int((self.monitor_geom.width - overlay_width) / 2)
        overlay_y = self.monitor_geom.y + int((self.monitor_geom.height - overlay_height) / 2)

        self.set_default_size(overlay_width, overlay_height)
        self.move(overlay_x, overlay_y)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

    def _setup_events(self):
        """Connect event handlers."""
        self.connect('draw', self._on_draw)
        self.connect('button-press-event', self._on_button_press)
        self.connect('key-press-event', self._on_key_press)
        self.connect('show', self._on_show)
        self.connect('hide', self._on_hide)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                       Gdk.EventMask.BUTTON_RELEASE_MASK |
                       Gdk.EventMask.KEY_PRESS_MASK)

    def _on_show(self, widget):
        """Grab focus when shown."""
        log.debug("Overlay shown")
        self.present()
        self.grab_focus()
        self.grab_add()  # Grab all input
        gdk_window = self.get_window()
        if gdk_window:
            gdk_window.focus(Gdk.CURRENT_TIME)

    def _on_hide(self, widget):
        """Release grabs on hide."""
        log.debug("Overlay hidden")
        self.grab_remove()  # Paired with grab_add

    def _on_draw(self, widget, cr):
        """Draw the grid and selection rectangle."""
        alloc = self.get_allocation()
        width = alloc.width
        height = alloc.height

        # Background - semi-transparent dark
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.85)
        cr.paint()

        # Draw grid lines
        cr.set_source_rgba(0.6, 0.6, 1.0, 0.8)
        cr.set_line_width(1)

        cell_width = width / self.cols
        cell_height = height / self.rows

        # Vertical lines
        for col in range(1, self.cols):
            x = col * cell_width
            cr.move_to(x, 0)
            cr.line_to(x, height)
            cr.stroke()

        # Horizontal lines
        for row in range(1, self.rows):
            y = row * cell_height
            cr.move_to(0, y)
            cr.line_to(width, y)
            cr.stroke()

        # Draw selection rectangle if active
        if self.first_corner and self.second_corner:
            x1, y1 = self.first_corner
            x2, y2 = self.second_corner

            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1

            cr.set_source_rgba(0.2, 0.6, 1.0, 0.3)
            cr.rectangle(x1, y1, x2 - x1, y2 - y1)
            cr.fill_preserve()

            cr.set_source_rgba(0.2, 0.6, 1.0, 0.8)
            cr.set_line_width(2)
            cr.stroke()

    def _on_button_press(self, widget, event):
        """Handle mouse clicks for cell selection."""
        log.debug("CLICK RECEIVED at %.1f, %.1f button=%d", event.x, event.y, event.button)

        alloc = self.get_allocation()
        cell_width = alloc.width / self.cols
        cell_height = alloc.height / self.rows

        grid_x = min(int(event.x / cell_width), self.cols - 1)
        grid_y = min(int(event.y / cell_height), self.rows - 1)

        pixel_x = grid_x * cell_width
        pixel_y = grid_y * cell_height

        log.debug("Grid cell: %d, %d -> pixel: %.1f, %.1f",
                  grid_x, grid_y, pixel_x, pixel_y)

        if self.first_corner and self.second_corner:
            # Reset and start new selection
            self.first_corner = (pixel_x, pixel_y)
            self.second_corner = None
            self.selection_active = True
            log.debug("Reset selection, first corner: %d, %d", grid_x, grid_y)
        elif not self.first_corner:
            # FIRST click - set only first corner
            self.first_corner = (pixel_x, pixel_y)
            self.second_corner = None  # <-- Don't set second corner yet!
            self.selection_active = True
            log.debug("First corner set: %d, %d", grid_x, grid_y)
        else:
            # SECOND click - set second corner
            self.second_corner = (pixel_x, pixel_y)
            log.debug("Second corner set: %d, %d", grid_x, grid_y)
            self._apply_selection()
        self.queue_draw()
        return True

    def _on_key_press(self, widget, event):
        """Handle keyboard navigation."""
        key = Gdk.keyval_name(event.keyval)
        log.debug("Key press: %s", key)

        if key == 'Escape':
            self.target_window = None  # Clear saved window
            self.hide()
            return True
        elif key == 'Return' or key == 'KP_Enter':
            if self.first_corner and self.second_corner:
                self._apply_selection()
            return True
        elif key in ('Up', 'Down', 'Left', 'Right'):
            self._handle_arrow_key(key, event.state)
            self.queue_draw()
            return True

        return False

    def _handle_arrow_key(self, key, state):
        """Move selection using arrow keys."""
        alloc = self.get_allocation()
        cell_width = alloc.width / self.cols
        cell_height = alloc.height / self.rows

        if not self.first_corner:
            self.first_corner = (0, 0)
            self.second_corner = (0, 0)
            self.selection_active = True
            return

        # Get current grid position
        if self.second_corner:
            cur_x = int(self.second_corner[0] / cell_width)
            cur_y = int(self.second_corner[1] / cell_height)
        else:
            cur_x = int(self.first_corner[0] / cell_width)
            cur_y = int(self.first_corner[1] / cell_height)

        if state & Gdk.ModifierType.SHIFT_MASK:
            # Move second corner
            if key == 'Up' and cur_y > 0:
                cur_y -= 1
            elif key == 'Down' and cur_y < self.rows - 1:
                cur_y += 1
            elif key == 'Left' and cur_x > 0:
                cur_x -= 1
            elif key == 'Right' and cur_x < self.cols - 1:
                cur_x += 1
            self.second_corner = (cur_x * cell_width, cur_y * cell_height)
        else:
            # Move first corner
            if key == 'Up' and cur_y > 0:
                cur_y -= 1
            elif key == 'Down' and cur_y < self.rows - 1:
                cur_y += 1
            elif key == 'Left' and cur_x > 0:
                cur_x -= 1
            elif key == 'Right' and cur_x < self.cols - 1:
                cur_x += 1
            self.first_corner = (cur_x * cell_width, cur_y * cell_height)
            self.second_corner = self.first_corner

    def _apply_selection(self):
        """Apply the selected grid area to the active window."""
        log.debug("APPLY_SELECTION CALLED")
        if not self.first_corner or not self.second_corner:
            log.debug("Missing corner data")
            return

        # Use the saved target window, NOT the currently active window (overlay)
        window = self.target_window
        if not window:
            log.debug("No target window saved")
            self.hide()
            return
        if not self.winman.is_relevant(window):
            log.debug("Window not relevant: %s", window.get_name())
            self.hide()
            return

        log.debug("Target window: %s", window.get_name())

        # Convert overlay pixel positions to grid cell coordinates
        alloc = self.get_allocation()
        log.debug("Overlay allocation: %s", alloc)
        cell_width = alloc.width / self.cols
        cell_height = alloc.height / self.rows
        log.debug("Cell size: %.1f x %.1f", cell_width, cell_height)

        grid_x1 = int(self.first_corner[0] / cell_width)
        grid_y1 = int(self.first_corner[1] / cell_height)
        grid_x2 = int(self.second_corner[0] / cell_width)
        grid_y2 = int(self.second_corner[1] / cell_height)
        log.debug("Grid cells: (%d,%d) to (%d,%d)", grid_x1, grid_y1, grid_x2, grid_y2)

        # Ensure correct ordering
        if grid_x1 > grid_x2:
            grid_x1, grid_x2 = grid_x2, grid_x1
        if grid_y1 > grid_y2:
            grid_y1, grid_y2 = grid_y2, grid_y1

        # Map grid cells to actual monitor pixel coordinates
        monitor_cell_width = self.monitor_geom.width / self.cols
        monitor_cell_height = self.monitor_geom.height / self.rows
        log.debug("Monitor cell size: %.1f x %.1f", monitor_cell_width, monitor_cell_height)

        x1 = grid_x1 * monitor_cell_width + self.monitor_geom.x
        y1 = grid_y1 * monitor_cell_height + self.monitor_geom.y
        x2 = (grid_x2 + 1) * monitor_cell_width + self.monitor_geom.x
        y2 = (grid_y2 + 1) * monitor_cell_height + self.monitor_geom.y

        target = Rectangle(x1, y1, x2 - x1, y2 - y1)
        log.debug("Target rectangle: %s", target)

        # Order matters: unmaximize/unminimize FIRST before reposition
        # WM will queue these requests, 50ms timeout gives time to settle
        if window.is_maximized():
            log.debug("Unmaximizing window")
            window.unmaximize()

        if window.is_minimized():
            log.debug("Unminimizing window")
            window.unminimize(Gdk.CURRENT_TIME)

        if window.is_shaded():
            log.debug("Unshading window")
            window.unshade()

        # Ensure window is focused before repositioning
        log.debug("Activating window")
        window.activate(int(time.time()))
        # activate() in _deferred_hide will re-focus after hide

        log.debug("Calling reposition()")
        self.winman.reposition(window, target)
        log.debug("reposition() complete")

        # Flush X11 buffer to ensure request is sent immediately
        dsp = Gdk.Display.get_default()
        if dsp:
            dsp.flush()

        # Defer hide so WM has time to process the async X11 resize request
        # _NET_MOVERESIZE_WINDOW is processed on next event loop iteration
        log.debug("Deferring overlay hide (50ms) to allow WM to process resize")
        GLib.timeout_add(50, self._deferred_hide, window)

    def show_overlay(self):
        """Show the overlay and grab keyboard focus."""
        log.debug("SHOW_OVERLAY CALLED")

        # Save the target window BEFORE overlay grabs focus
        self.target_window = self.winman.screen.get_active_window()
        if self.target_window:
            log.debug("Saved target window: %s", self.target_window.get_name())
        else:
            log.debug("No target window found!")

        self.first_corner = None
        self.second_corner = None
        self.selection_active = False

        log.debug("Calling show_all()")
        self.show_all()
        log.debug("Calling present()")
        self.present()
        log.debug("Calling grab_focus()")
        self.grab_focus()
        log.debug("show_overlay() complete, window visible: %s", self.get_visible())

    def _deferred_hide(self, window):
        """Hide overlay after WM has processed the resize."""
        log.debug("Deferred hide: hiding overlay")
        self.hide()
        self.target_window = None  # Clean up
        return False  # Don't repeat
