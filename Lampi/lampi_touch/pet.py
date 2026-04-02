from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.progressbar import ProgressBar
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.core.window import Window

# Set window background color
Window.clearcolor = (0.85, 0.85, 0.85, 1)


class StatBar(BoxLayout):
    """Custom widget for displaying a stat with icon and progress bar"""
    def __init__(self, icon_text, initial_value=0.5, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 40
        self.padding = [10, 5]
        self.spacing = 10
        
        # Icon label
        icon = Label(
            text=icon_text,
            size_hint_x=None,
            width=40,
            font_size='24sp',
            color=(0, 0, 0, 1)
        )
        self.add_widget(icon)
        
        # Progress bar
        self.progress = ProgressBar(
            max=100,
            value=initial_value * 100,
            size_hint_x=1
        )
        
        # Style the progress bar
        with self.progress.canvas.before:
            Color(0.7, 0.7, 0.7, 1)
            self.progress.bg_rect = RoundedRectangle(
                pos=self.progress.pos,
                size=self.progress.size,
                radius=[15]
            )
        
        with self.progress.canvas:
            Color(0, 0, 0, 1)
            self.progress.fg_rect = RoundedRectangle(
                pos=self.progress.pos,
                size=(self.progress.value / self.progress.max * self.progress.width, self.progress.height),
                radius=[15]
            )
        
        self.progress.bind(pos=self.update_progress_graphics, size=self.update_progress_graphics, value=self.update_progress_graphics)
        
        self.add_widget(self.progress)
    
    def update_progress_graphics(self, *args):
        """Update progress bar graphics when value changes"""
        self.progress.bg_rect.pos = self.progress.pos
        self.progress.bg_rect.size = self.progress.size
        self.progress.fg_rect.pos = self.progress.pos
        self.progress.fg_rect.size = (self.progress.value / self.progress.max * self.progress.width, self.progress.height)


class PetDisplayArea(FloatLayout):
    """Central area where the pet is displayed"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Background
        with self.canvas.before:
            Color(0.75, 0.75, 0.75, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)
        
        # Pet character (placeholder oval)
        pet_container = FloatLayout(
            size_hint=(None, None),
            size=(150, 150),
            pos_hint={'center_x': 0.3, 'center_y': 0.6}
        )
        
        with pet_container.canvas:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=(0, 0), size=(150, 150), radius=[20])
            Color(0, 0, 0, 1)
            # Pet face - simple oval shape with eyes
        
        pet_label = Label(
            text='😊',
            font_size='80sp',
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        pet_container.add_widget(pet_label)
        
        self.add_widget(pet_container)
        
        # Poop items (decorative)
        poop1 = Label(
            text='💩',
            font_size='40sp',
            size_hint=(None, None),
            size=(50, 50),
            pos_hint={'x': 0.6, 'y': 0.4}
        )
        self.add_widget(poop1)
        
        poop2 = Label(
            text='💩',
            font_size='40sp',
            size_hint=(None, None),
            size=(50, 50),
            pos_hint={'x': 0.75, 'y': 0.25}
        )
        self.add_widget(poop2)
    
    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class NavigationButton(Button):
    """Custom styled navigation button"""
    def __init__(self, icon_text, **kwargs):
        super().__init__(**kwargs)
        self.text = icon_text
        self.font_size = '36sp'
        self.background_color = (1, 1, 1, 0)
        self.color = (0, 0, 0, 1)
        
        with self.canvas.before:
            Color(1, 1, 1, 0)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self.update_bg, size=self.update_bg)
    
    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class PetAppLayout(BoxLayout):
    """Main application layout"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 0
        self.spacing = 0
        
        # Stats panel at top
        stats_panel = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=150,
            padding=[20, 10],
            spacing=5
        )
        
        with stats_panel.canvas.before:
            Color(0.85, 0.85, 0.85, 1)
            stats_panel.rect = Rectangle(pos=stats_panel.pos, size=stats_panel.size)
        stats_panel.bind(pos=lambda obj, val: setattr(obj.rect, 'pos', val),
                        size=lambda obj, val: setattr(obj.rect, 'size', val))
        
        # Add stat bars
        stats_panel.add_widget(StatBar('🍴', 0.7))
        stats_panel.add_widget(StatBar('🏠', 0.3))
        stats_panel.add_widget(StatBar('😊', 0.8))
        
        self.add_widget(stats_panel)
        
        # Pet display area (takes up remaining space)
        pet_area = PetDisplayArea()
        self.add_widget(pet_area)
        
        # Bottom navigation bar
        nav_bar = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=100,
            spacing=0
        )
        
        with nav_bar.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            nav_bar.rect = Rectangle(pos=nav_bar.pos, size=nav_bar.size)
        nav_bar.bind(pos=lambda obj, val: setattr(obj.rect, 'pos', val),
                    size=lambda obj, val: setattr(obj.rect, 'size', val))
        
        # Navigation buttons
        nav_bar.add_widget(NavigationButton('✋'))
        nav_bar.add_widget(NavigationButton('🍴'))
        nav_bar.add_widget(NavigationButton('🚿'))
        
        self.add_widget(nav_bar)


class PetApp(App):
    def build(self):
        return PetAppLayout()


if __name__ == '__main__':
    PetApp().run()
