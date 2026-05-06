from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.properties import NumericProperty, BooleanProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.app import App
from lamp_common import *


class Food(Widget):
    size_value = NumericProperty(30)

    def __init__(self, is_air_drop=False, **kwargs):
        super().__init__(**kwargs)
        self.size = (self.size_value, self.size_value)  # set once
        self.size_hint = (None, None)
        self.img = Image(
            source="images/airdrop_food.png" if is_air_drop else "images/food.png",
            size_hint=(None, None)
        )
        self.add_widget(self.img)
        self.bind(pos=self._update)
        self.bind(size_value=self._update)  # NO size bind
        self._update()

    def _update(self, *args):
        self.size = (self.size_value, self.size_value)
        self.img.size = self.size
        self.img.pos = (
            self.x + (self.width - self.img.width) / 2,
            self.y + (self.height - self.img.height) / 2
        )
