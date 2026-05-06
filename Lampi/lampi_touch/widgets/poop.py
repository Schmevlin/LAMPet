from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.app import App
from lamp_common import *


class Poop(ButtonBehavior, Widget):
    size_value = NumericProperty(50)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.img = Image(
            source="images/poop.png",
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
        
    def on_press(self):
        app = App.get_running_app()
        app.send_action("clean", 30)

        screen = app.root.get_screen("lampet")

        # if self in app.poops:
        #     app.poops.remove(self)
        
        screen.remove_widget(self)
