from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.app import App
from lamp_common import *


class Food(Widget):
    size_value = NumericProperty(30)
    is_air_drop = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.img = Image(
            source="images/food.png",
            size_hint=(None, None)
        )

        self.add_widget(self.img)

        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(size_value=self._update)

        self._update()

    def _update(self, *args):
        # keep widget size synced
        self.size = (self.size_value, self.size_value)

        # center image inside widget
        self.img.size = (self.size_value, self.size_value)
        self.img.pos = (
            self.x + (self.width - self.img.width) / 2,
            self.y + (self.height - self.img.height) / 2
        )