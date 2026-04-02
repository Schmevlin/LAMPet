from kivy.properties import NumericProperty, AliasProperty, BooleanProperty, StringProperty, ColorProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
import os

kv_path = os.path.join(os.path.dirname(__file__), 'attribute_bar.kv')
Builder.load_file(kv_path)

class AttributeBar(BoxLayout):
    # These properties are "observable" by the KV file
    label_text = StringProperty("Stat")
    value = NumericProperty(50)
    max_value = NumericProperty(100)
    bar_color = ColorProperty([0.7, 0.7, 0.7, 1])
    inner_padding = NumericProperty(2)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # You could add logic here to animate the bar 
        # or change color based on value

