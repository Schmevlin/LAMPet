import colorsys
from typing import Any

from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Ellipse, SmoothLine
from kivy.graphics.texture import Texture
from kivy.properties import NumericProperty, ListProperty, StringProperty
from kivy.properties import ObjectProperty
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.input import MotionEvent
from array import array


class GradientSlider(Widget):
    """Custom gradient slider widget.

    Note: This inherits from Widget instead of Slider to work around a
    rendering bug in Kivy 2.3.x on Raspberry Pi with OpenGL 2.1 (VC4 driver).
    The standard Slider widget causes all other widgets to not render.
    """

    value = NumericProperty(0.5)
    value_normalized = NumericProperty(0.5)
    colors = ListProperty()
    thumb_image_light = StringProperty("")
    thumb_image_dark = StringProperty("")

    _texture = ObjectProperty(None)
    _thumb_color = ListProperty([1.0, 1.0, 1.0, 1.0])
    _thumb_border_color = ListProperty([0.5, 0.5, 0.5, 1.0])
    _thumb_image = StringProperty("")
    _thumb_image_texture = ObjectProperty(None, allownone=True)
    padding = NumericProperty(dp(16))

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._is_touching: bool = False
        self._image_textures: dict[str, Any] = {}
        self.bind(pos=self._redraw, size=self._redraw,
                  value=self._on_value, colors=self._on_colors,
                  thumb_image_light=self._load_thumb_images,
                  thumb_image_dark=self._load_thumb_images)
        Clock.schedule_once(self._initial_setup, 0)

    def _initial_setup(self, dt: float) -> None:
        self._load_thumb_images()
        self._on_colors()
        self._redraw()

    def _load_thumb_images(self, *args: Any) -> None:
        """Preload thumb image textures."""
        for path in [self.thumb_image_light, self.thumb_image_dark]:
            if path and path not in self._image_textures:
                try:
                    img = CoreImage(path)
                    self._image_textures[path] = img.texture
                except Exception:
                    pass
        self._update_thumb_image()

    def _on_value(self, *args: Any) -> None:
        self.value_normalized = self.value
        self._update_thumb_color()
        self._update_thumb_image()
        self._redraw()

    def _on_colors(self, *args: Any) -> None:
        self._update_texture()
        self._update_thumb_color()
        self._update_thumb_image()
        self._redraw()

    def _update_texture(self) -> None:
        if not self.colors:
            return

        height, depth = 1, 3
        width = len(self.colors)
        size = width * height * depth

        texture = Texture.create(size=(width, height))
        texture_buffer = [0] * size
        texture_bytes = array("B", texture_buffer)

        for i, color in enumerate(self.colors):
            buffer_index = i * depth
            r = int(color[0] * 255.0)
            g = int(color[1] * 255.0)
            b = int(color[2] * 255.0)
            texture_bytes[buffer_index] = r
            texture_bytes[buffer_index + 1] = g
            texture_bytes[buffer_index + 2] = b

        texture.blit_buffer(texture_bytes, colorfmt="rgb", bufferfmt="ubyte")
        self._texture = texture

    def _update_thumb_color(self) -> None:
        if not self.colors:
            return

        position = self.value * float(len(self.colors) - 1)
        first_idx = int(position)
        second_idx = min(first_idx + 1, len(self.colors) - 1)
        pos = position - float(first_idx)

        c1, c2 = self.colors[first_idx], self.colors[second_idx]
        r = c1[0] + pos * (c2[0] - c1[0])
        g = c1[1] + pos * (c2[1] - c1[1])
        b = c1[2] + pos * (c2[2] - c1[2])

        self._thumb_color = [r, g, b, 1.0]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        border = colorsys.hsv_to_rgb(h, s, v * 0.75)
        self._thumb_border_color = [border[0], border[1], border[2], 1.0]

    def _update_thumb_image(self, *args: Any) -> None:
        if not self._thumb_color or len(self._thumb_color) < 3:
            return
        r, g, b = self._thumb_color[:3]
        # Calculate luminance to determine if we need light or dark icon
        luminance = r * 0.213 + g * 0.715 + b * 0.072

        if luminance < 0.5:
            self._thumb_image = self.thumb_image_light or ""
        else:
            self._thumb_image = self.thumb_image_dark or ""

        # Set the texture for the current thumb image
        self._thumb_image_texture = self._image_textures.get(self._thumb_image)

    def _redraw(self, *args: Any) -> None:
        if not self.colors or self.width <= 0 or self.height <= 0:
            return

        self._update_thumb_color()
        self.canvas.clear()

        track_x = self.x + self.padding
        track_width = self.width - self.padding * 2
        if track_width <= 0:
            return
        track_y = self.center_y - dp(4)

        thumb_x = track_x + track_width * self.value

        with self.canvas:
            # Outer track (gray border)
            Color(0.75, 0.75, 0.75, 1)
            Rectangle(pos=(track_x, track_y), size=(track_width, dp(8)),
                      texture=self._texture)

            # Inner track
            Color(1, 1, 1, 1)
            Rectangle(pos=(track_x + dp(1), track_y + dp(1)),
                      size=(track_width - dp(2), dp(6)),
                      texture=self._texture)

            # Thumb circle
            Color(*self._thumb_color)
            Ellipse(pos=(thumb_x - dp(16), self.center_y - dp(17)),
                    size=(dp(32), dp(32)))

            # Thumb border
            Color(*self._thumb_border_color)
            SmoothLine(circle=(thumb_x, self.center_y - dp(1), dp(16)),
                       width=dp(1))

            # Thumb icon (if available)
            if self._thumb_image_texture:
                icon_size = dp(20)
                Color(1, 1, 1, 1)
                Rectangle(
                    pos=(thumb_x - icon_size/2,
                         self.center_y - icon_size/2 - dp(1)),
                    size=(icon_size, icon_size),
                    texture=self._thumb_image_texture
                )

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
        new_value = max(0.0, min(1.0, (x - track_x) / track_width))
        self.value = new_value
