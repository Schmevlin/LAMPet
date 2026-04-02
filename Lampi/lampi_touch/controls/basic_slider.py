from typing import Any

from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.properties import NumericProperty, BoundedNumericProperty
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.input import MotionEvent


class BasicSlider(Widget):
    """A simple slider widget that works on PiTFT.

    This inherits from Widget instead of Slider to work around a
    rendering bug in Kivy 2.3.x on Raspberry Pi with OpenGL 2.1 (VC4 driver).
    The standard Slider widget causes rendering issues on this platform.

    Properties match the standard Kivy Slider for compatibility:
        value: Current value (default 0)
        min: Minimum value (default 0)
        max: Maximum value (default 100)
        step: Step size for value changes (default 0 = continuous)
    """

    value = NumericProperty(0)
    min = NumericProperty(0)
    max = NumericProperty(100)
    step = NumericProperty(0)

    # Internal normalized value (0-1)
    _value_normalized = NumericProperty(0)

    # Visual properties
    padding = NumericProperty(dp(16))

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._is_touching: bool = False
        self.bind(pos=self._redraw, size=self._redraw,
                  value=self._on_value_change,
                  min=self._on_range_change, max=self._on_range_change)
        Clock.schedule_once(self._initial_setup, 0)

    def _initial_setup(self, dt: float) -> None:
        self._update_normalized()
        self._redraw()

    def _on_value_change(self, *args: Any) -> None:
        self._update_normalized()
        self._redraw()

    def _on_range_change(self, *args: Any) -> None:
        # Clamp value to new range
        self.value = max(self.min, min(self.max, self.value))
        self._update_normalized()
        self._redraw()

    def _update_normalized(self) -> None:
        """Update internal normalized value from value/min/max."""
        range_val = self.max - self.min
        if range_val > 0:
            self._value_normalized = (self.value - self.min) / range_val
        else:
            self._value_normalized = 0

    def _redraw(self, *args: Any) -> None:
        if self.width <= 0 or self.height <= 0:
            return

        self.canvas.clear()

        track_x = self.x + self.padding
        track_width = self.width - self.padding * 2
        if track_width <= 0:
            return

        track_height = dp(8)
        track_y = self.center_y - track_height / 2

        thumb_radius = dp(14)
        thumb_x = track_x + track_width * self._value_normalized

        with self.canvas:
            # Track background (dark gray)
            Color(0.3, 0.3, 0.3, 1)
            Rectangle(pos=(track_x, track_y), size=(track_width, track_height))

            # Track fill (light blue up to thumb position)
            Color(0.4, 0.6, 0.9, 1)
            fill_width = track_width * self._value_normalized
            Rectangle(pos=(track_x, track_y), size=(fill_width, track_height))

            # Thumb circle (white with border)
            Color(1, 1, 1, 1)
            Ellipse(pos=(thumb_x - thumb_radius, self.center_y - thumb_radius),
                    size=(thumb_radius * 2, thumb_radius * 2))

            # Thumb border (gray)
            Color(0.5, 0.5, 0.5, 1)
            # Draw a slightly smaller circle for border effect
            border_width = dp(2)
            Ellipse(pos=(thumb_x - thumb_radius + border_width,
                         self.center_y - thumb_radius + border_width),
                    size=(thumb_radius * 2 - border_width * 2,
                          thumb_radius * 2 - border_width * 2))

            # Thumb fill (white again, inside border)
            Color(1, 1, 1, 1)
            inner_radius = thumb_radius - border_width
            Ellipse(pos=(thumb_x - inner_radius, self.center_y - inner_radius),
                    size=(inner_radius * 2, inner_radius * 2))

    def on_touch_down(self, touch: MotionEvent) -> bool:
        if self.collide_point(*touch.pos):
            self._is_touching = True
            self._update_value_from_touch(touch.x)
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch: MotionEvent) -> bool:
        if touch.grab_current is self:
            self._update_value_from_touch(touch.x)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch: MotionEvent) -> bool:
        if touch.grab_current is self:
            self._is_touching = False
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)

    def _update_value_from_touch(self, x: float) -> None:
        track_x = self.x + self.padding
        track_width = self.width - self.padding * 2
        if track_width <= 0:
            return

        # Calculate normalized position (0-1)
        normalized = max(0.0, min(1.0, (x - track_x) / track_width))

        # Convert to actual value
        range_val = self.max - self.min
        new_value = self.min + normalized * range_val

        # Apply step if set
        if self.step > 0:
            new_value = round(new_value / self.step) * self.step
            new_value = max(self.min, min(self.max, new_value))

        self.value = new_value
