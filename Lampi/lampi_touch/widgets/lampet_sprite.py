from kivy.app import App
from kivy.uix.image import Image
from kivy.lang import Builder
import os
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.clock import Clock
from kivy.graphics import PushMatrix, PopMatrix, Scale

kv_path = os.path.join(os.path.dirname(__file__), 'lampet_sprite.kv')
Builder.load_file(kv_path)

class LAMPetSprite(Image):

    is_dead = BooleanProperty(False)
    is_flip = BooleanProperty(False)

    frames = ListProperty([])
    frame_index = NumericProperty(0)

    def on_kv_post(self, *args):

        with self.canvas.before:
            PushMatrix()
            self.flip_transform = Scale(1, 1, 1, origin=self.center)

        with self.canvas.after:
            PopMatrix()

        self.frames = [
            'images/guy/guy_0.png',
            'images/guy/guy_1.png',
            'images/guy/guy_2.png',
            'images/guy/guy_3.png',
            'images/guy/guy_4.png',
        ]

        Clock.schedule_interval(self._animate, 1 / 5)

    def _animate(self, dt):
        if self.is_dead:
            self.source = 'images/dead_guy.png'
            return

        if not self.frames:
            return

        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.source = self.frames[self.frame_index]

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            app.lampet_x = touch.x - self.width / 2
            app.lampet_y = touch.y - self.height / 2
            return True
        return super().on_touch_move(touch)

    def on_is_flip(self, instance, value):
        if hasattr(self, 'flip_transform'):
            self.flip_transform.origin = (self.center_x, self.center_y, 0)
            self.flip_transform.x = -1 if self.is_flip else 1

    def on_pos(self, *args):
        if hasattr(self, 'flip_transform'):
            self.flip_transform.origin = self.center
            self.flip_transform.x = -1 if self.is_flip else 1

    def on_size(self, *args):
        if hasattr(self, 'flip_transform'):
            self.flip_transform.origin = self.center
            self.flip_transform.x = -1 if self.is_flip else 1