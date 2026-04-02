from kivy.app import App
from kivy.uix.image import Image
from kivy.lang import Builder
import os

kv_path = os.path.join(os.path.dirname(__file__), 'lampet_sprite.kv')
Builder.load_file(kv_path)

class LAMPetSprite(Image):
    def on_touch_move(self, touch):
        # Check if the touch is actually on this specific image
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            # Update the image position to follow the touch
            app.lampet_x = touch.x - self.width/2
            app.lampet_y = touch.y - self.height/2
            return True # Consume the touch event
        return super().on_touch_move(touch)
