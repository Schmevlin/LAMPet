from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.app import App
from lamp_common import *


class Food(Widget):
    size_value = NumericProperty(30)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.img = Image(
            source="images/food.png",
            size=(self.size_value, self.size_value),
            size_hint=(None, None)
        )

        self.add_widget(self.img)

        self.bind(pos=self._update_pos)
        self._update_pos()

    def _update_pos(self, *args):
        self.img.pos = self.pos

    def on_size_value(self, *args):
        self.img.size = (self.size_value, self.size_value)