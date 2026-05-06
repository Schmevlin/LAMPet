import json
from kivy.uix.boxlayout import BoxLayout
import pigpio
from typing import Any, Optional
from random import choice, randint

from kivy.app import App
from kivy.properties import NumericProperty, AliasProperty, BooleanProperty, StringProperty, ColorProperty
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.lang import Builder
import paho.mqtt.client as mqtt
from paho.mqtt.client import Client, CallbackAPIVersion
from lampi_touch.widgets.poop import Poop
from lampi_touch.widgets.food import Food


from lamp_common import *
import lampi_touch.lampi_util
from mixpanel import Mixpanel 

from .widgets.attribute_bar import AttributeBar
from .widgets.lampet_sprite import LAMPetSprite

MQTT_CLIENT_ID = "lamp_ui"

# Throttle MQTT publishes to 20/sec max (0.05s) to prevent overwhelming
# the lamp_service with messages during rapid slider movement.
MQTT_PUBLISH_THROTTLE_SECS = 0.05


MQTT_CLIENT_ID = "lamp_ui"

try:
    from .mixpanel_settings import MIXPANEL_TOKEN
except (ModuleNotFoundError, ImportError) as e:
    MIXPANEL_TOKEN = "98678fa47e01a776dadcb74b0c41d944"

class LampiScreen(Screen):
    pass

class LampetScreen(Screen):
    def on_touch_down(self, touch):
        app = App.get_running_app()

        if app.feeding_mode:
            app.spawn_food(touch.x, touch.y)
            app.feeding_mode = False
            return True

        return super().on_touch_down(touch)


class LampiApp(App):

    def build(self):
        Builder.load_file('lampi_touch/lampi_screen.kv')
        Builder.load_file('lampi_touch/lampet.kv')
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(LampetScreen(name='lampet'))
        sm.add_widget(LampiScreen(name='lampi'))
        return sm

    _lampet_x = NumericProperty(20)
    _lampet_y = NumericProperty(40)


    def _get_lampet_x(self) -> float:
        return self._lampet_x

    def _set_lampet_x(self, value: float) -> None:
        if value > self.root.width:
            value = self.root.width
        self._lampet_x = value

    def _get_lampet_y(self) -> float:
        return self._lampet_y

    def _set_lampet_y(self, value: float) -> None:
        if value > self.root.height:
            value = self.root.height
        self._lampet_y = value

    lampet_x = AliasProperty(_get_lampet_x, _set_lampet_x, bind=['_lampet_x'])
    lampet_y = AliasProperty(_get_lampet_y, _set_lampet_y, bind=['_lampet_y'])

    _hunger = NumericProperty(50)
    _cleanliness = NumericProperty(50)
    _happiness = NumericProperty(50)
    is_dead = BooleanProperty(False)
    feeding_mode = BooleanProperty(False)

    def _get_hunger(self) -> float:
        return self._hunger

    def _set_hunger(self, value: float) -> None:
        if value > 100:
            value = 100
        self._hunger = value

    def _get_cleanliness(self) -> float:
        return self._cleanliness

    def _set_cleanliness(self, value: float) -> None:
        if value > 100:
            value = 100
        self._cleanliness = value

    def _get_happiness(self) -> float:
        return self._happiness

    def _set_happiness(self, value: float) -> None:
        if value > 100:
            value = 100
        self._happiness = value

    hunger = AliasProperty(_get_hunger, _set_hunger, bind=['_hunger'])
    cleanliness = AliasProperty(_get_cleanliness, _set_cleanliness, bind=['_cleanliness'])
    happiness = AliasProperty(_get_happiness, _set_happiness, bind=['_happiness'])

    # From here down is lampi code

    _updated: bool = False
    _updating_ui: bool = False
    _hue = NumericProperty()
    _saturation = NumericProperty()
    _brightness = NumericProperty()
    lamp_is_on = BooleanProperty()

    mp = Mixpanel(MIXPANEL_TOKEN)

    def _get_hue(self) -> float:
        return self._hue

    def _set_hue(self, value: float) -> None:
        self._hue = value

    def _get_saturation(self) -> float:
        return self._saturation

    def _set_saturation(self, value: float) -> None:
        self._saturation = value

    def _get_brightness(self) -> float:
        return self._brightness

    def _set_brightness(self, value: float) -> None:
        self._brightness = value

    hue = AliasProperty(_get_hue, _set_hue, bind=['_hue'])
    saturation = AliasProperty(_get_saturation, _set_saturation,
                               bind=['_saturation'])
    brightness = AliasProperty(_get_brightness, _set_brightness,
                               bind=['_brightness'])
    gpio17_pressed = BooleanProperty(False)
    device_associated = BooleanProperty(True)

    def on_start(self) -> None:
        self._publish_clock: Optional[Any] = None
        self.mqtt_broker_bridged: bool = False
        self._associated: bool = True
        self.association_code: Optional[str] = None
        self.mqtt: Client = Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID
        )
        self.mqtt.enable_logger()
        self.mqtt.will_set(client_state_topic(MQTT_CLIENT_ID), "0",
                           qos=2, retain=True)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.connect(MQTT_BROKER_HOST, port=MQTT_BROKER_PORT,
                          keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
        self.mqtt.loop_start()
        self.set_up_gpio_and_device_status_popup()
        self.associated_status_popup = self._build_associated_status_popup()
        self.associated_status_popup.bind(on_open=self.update_popup_associated)
        #schedules for walking
        Clock.schedule_interval(self._poll_associated, 0.1)
        Clock.schedule_interval(self._pet_walk, 0.2)
        Clock.schedule_interval(self._update_world, 0.2)
        #list of poop and food that spawned 
        self.foods = []

    def _build_associated_status_popup(self):
        return Popup(title='Associate your Lamp',
                     content=Label(text='Msg here', font_size='30sp'),
                     size_hint=(1, 1), auto_dismiss=False)
            
    def _pet_walk(self, dt):
        if self.is_dead:
            return

        # if there is food, go toward closest one
        target = None
        if self.foods:
            target = min(
                self.foods,
                key=lambda f: (f.x - self.lampet_x) ** 2 + (f.y - self.lampet_y) ** 2
            )

        if target:
            dx = target.x - self.lampet_x
            dy = target.y - self.lampet_y
            dist = max(1, (dx * dx + dy * dy) ** 0.5)

            step = 5
            self.lampet_x += step * dx / dist
            self.lampet_y += step * dy / dist
        else:
            if not hasattr(self, '_dx'):
                self._dx = randint(-2, 2)
                self._dy = randint(-2, 2)

            if randint(0, 10) > 7:
                self._dx += randint(-1, 1)
                self._dy += randint(-1, 1)
                self._dx = max(-2, min(2, self._dx))
                self._dy = max(-2, min(2, self._dy))

            new_x = self.lampet_x + self._dx
            new_y = self.lampet_y + self._dy

            if self.root:
                if new_x > self.root.width - 60:
                    new_x = self.root.width - 60
                    self._dx = -self._dx
                elif new_x < 0:
                    new_x = 0
                    self._dx = -self._dx

                if new_y < 50:
                    new_y = 50
                    self._dy = -self._dy
                elif new_y > self.root.height - 60:
                    new_y = self.root.height - 60
                    self._dy = -self._dy

            self.lampet_x = new_x
            self.lampet_y = new_y
        
    def _update_world(self, dt):
        self._check_food_collision()
        
    def spawn_poop(self):
        if not self.root:
            return
        
        poop = Poop()
        poop.pos = (randint(0, int(self.root.width - 60))),randint(60, int(self.root.height - 60))
        self.root.get_screen("lampet").add_widget(poop)
        
    def spawn_food(self, x, y):
        if self.is_dead:
            return

        screen = self.root.get_screen("lampet")

        # define bounds (same idea as your clamp logic)
        if x < 0 or x > screen.width - 10:
            return
        if y < 40 or y > screen.height - 60:
            return

        food = Food()
        food.pos = (x, y)

        screen.add_widget(food)
        self.foods.append(food)
        
    def spawn_airDrop(self):
        if not self.root:
            return
        
        screen = self.root.get_screen("lampet")
        
        food = Food(is_air_drop=True)
        food.pos = (randint(0, int(self.root.width - 60))),randint(60, int(self.root.height - 60))
        screen.add_widget(food)
        self.foods.append(food)
        
    def _check_food_collision(self):
        if not self.root:
            return

        pet_x = self.lampet_x
        pet_y = self.lampet_y

        for food in self.foods[:]:
            dx = food.x - pet_x
            dy = food.y - pet_y

            if (dx * dx + dy * dy) < 25 * 25:
                if food.parent:
                    food.parent.remove_widget(food)

                self.foods.remove(food)
                self.send_action("eat", 20)
                
    def on_hue(self, instance: Any, value: float) -> None:
        if self._updating_ui:
            return
        self._track_ui_event('Slider Change',
                             {'slider': 'hue-slider', 'value': value})
        if self._publish_clock is None:
            self._publish_clock = Clock.schedule_once(
                lambda dt: self._update_leds(), MQTT_PUBLISH_THROTTLE_SECS)

    def on_saturation(self, instance: Any, value: float) -> None:
        if self._updating_ui:
            return
        self._track_ui_event('Slider Change',
                             {'slider': 'saturation-slider', 'value': value})
        if self._publish_clock is None:
            self._publish_clock = Clock.schedule_once(
                lambda dt: self._update_leds(), MQTT_PUBLISH_THROTTLE_SECS)

    def on_brightness(self, instance: Any, value: float) -> None:
        if self._updating_ui:
            return
        self._track_ui_event('Slider Change',
                             {'slider': 'brightness-slider', 'value': value})
        if self._publish_clock is None:
            self._publish_clock = Clock.schedule_once(
                lambda dt: self._update_leds(), MQTT_PUBLISH_THROTTLE_SECS)

    def on_lamp_is_on(self, instance: Any, value: bool) -> None:
        if self._updating_ui:
            return
        self._track_ui_event('Toggle Power', {'isOn': value})
        if self._publish_clock is None:
            self._publish_clock = Clock.schedule_once(
                lambda dt: self._update_leds(), MQTT_PUBLISH_THROTTLE_SECS)
            
    def send_action(self, action: str, value: int = 10) -> None:
        self.mqtt.publish(
            TOPIC_SET_LAMPet_CONFIG,
            json.dumps({"action": action, 
                        "value": value,
                        "client": MQTT_CLIENT_ID}).encode(),
            qos=1
        )

    def _track_ui_event(self, event_name: str,
                        additional_props: dict[str, Any] = {}) -> None:
        device_id = lampi_touch.lampi_util.get_device_id()

        event_props = {'event_type': 'ui', 'interface': 'lampi',
                       'device_id': device_id}
        event_props.update(additional_props)

#self.mp.track(device_id, event_name, event_props)

    def on_connect(self, client: Client, userdata: Any,
                   flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode,
                   properties: Optional[mqtt.Properties]) -> None:
        self.mqtt.publish(client_state_topic(MQTT_CLIENT_ID), b"1",
                          qos=2, retain=True)
        self.mqtt.message_callback_add(TOPIC_LAMP_CHANGE_NOTIFICATION,
                                       self.receive_new_lamp_state)
        self.mqtt.message_callback_add(broker_bridge_connection_topic(),
                                       self.receive_bridge_connection_status)
        self.mqtt.message_callback_add(TOPIC_LAMP_ASSOCIATED,
                                       self.receive_associated)
        self.mqtt.message_callback_add(TOPIC_LAMPet_CHANGE_NOTIFICATION,
                                       self.receive_new_lampet_state)
        self.mqtt.message_callback_add(TOPIC_SET_LAMPet_CONFIG,
                                       self.receive_airDrop)
        
        self.mqtt.subscribe(broker_bridge_connection_topic(), qos=1)
        self.mqtt.subscribe(TOPIC_LAMP_CHANGE_NOTIFICATION, qos=1)
        self.mqtt.subscribe(TOPIC_LAMP_ASSOCIATED, qos=2)
        self.mqtt.subscribe(TOPIC_LAMPet_CHANGE_NOTIFICATION, qos=1)
        self.mqtt.subscribe(TOPIC_SET_LAMPet_CONFIG, qos=1)

    def _poll_associated(self, dt):
        # this polling loop allows us to synchronize changes from the
        #  MQTT callbacks (which happen in a different thread) to the
        #  Kivy UI
        self.device_associated = self._associated

    def receive_associated(self, client, userdata, message):
        # this is called in MQTT event loop thread
        new_associated = json.loads(message.payload.decode('utf-8'))
        if self._associated != new_associated['associated']:
            if not new_associated['associated']:
                self.association_code = new_associated['code']
            else:
                self.association_code = None
            self._associated = new_associated['associated']

    def on_device_associated(self, instance, value):
        if value:
            self.associated_status_popup.dismiss()
        else:
            self.associated_status_popup.open()

    def update_popup_associated(self, instance):
        code = self.association_code[0:6]
        instance.content.text = ("Please use the\n"
                                 "following code\n"
                                 "to associate\n"
                                 "your device\n"
                                 f"on the Web\n{code}")

    def receive_bridge_connection_status(self, client: Client, userdata: Any,
                                         message: mqtt.MQTTMessage) -> None:
        # monitor if the MQTT bridge to our cloud broker is up
        if message.payload == b"1":
            self.mqtt_broker_bridged = True
        else:
            self.mqtt_broker_bridged = False

    def receive_new_lamp_state(self, client: Client, userdata: Any,
                               message: mqtt.MQTTMessage) -> None:
        new_state = json.loads(message.payload.decode('utf-8'))
        Clock.schedule_once(lambda dt: self._update_ui(new_state), 0.01)
        
    def receive_new_lampet_state(self, client: Client, userdata: Any,
                               message: mqtt.MQTTMessage) -> None:
        new_state = json.loads(message.payload.decode('utf-8'))
        print("INCOMING:", new_state)
        if 'happiness' in new_state:
            self.happiness = new_state['happiness']
        if 'hunger' in new_state:
            self.hunger = new_state['hunger']
        if 'cleanliness' in new_state:
            incoming = new_state['cleanliness']
            if incoming < self.cleanliness:
                Clock.schedule_once(lambda dt: self.spawn_poop(), 0)
                
            self.cleanliness = incoming
        if 'state' in new_state:
            self.is_dead = new_state['state'] == 'dead'
            
    def receive_airDrop(self, client: Client, userdata: Any,
                               message: mqtt.MQTTMessage) -> None:
        if self.is_dead:
            return
        new_state = json.loads(message.payload.decode('utf-8'))
        if self._updated and new_state.get('client') == "web":
            if 'action' in new_state:
                if new_state['action'] == 'eat':
                    Clock.schedule_once(lambda dt: self.spawn_airDrop(), 0)

    def _update_ui(self, new_state: dict[str, Any]) -> None:
        """Update UI from MQTT state.

        Ignores updates from ourselves (except the first one for initial sync)
        to prevent MQTT feedback loops from causing UI jumpiness.
        """
        if self._updated and new_state.get('client') == MQTT_CLIENT_ID:
            # ignore updates generated by this client, except the first to
            #   make sure the UI is synchronized with the lamp_service
            # but it will update the play status wowwowowowowo
            self.send_action("play", 10) 
            return
        self._updating_ui = True
        try:
            if 'color' in new_state:
                self.hue = new_state['color']['h']
                self.saturation = new_state['color']['s']
            if 'brightness' in new_state:
                self.brightness = new_state['brightness']
            if 'on' in new_state:
                self.lamp_is_on = new_state['on']
        finally:
            self._updating_ui = False
        self.send_action("play", 10) 
        self._updated = True
        

    def _update_leds(self) -> None:
        msg = {'color': {'h': self._hue, 's': self._saturation},
               'brightness': self._brightness,
               'on': self.lamp_is_on,
               'client': MQTT_CLIENT_ID}
        self.mqtt.publish(TOPIC_SET_LAMP_CONFIG,
                          json.dumps(msg).encode('utf-8'),
                          qos=1)
        self._publish_clock = None

    def set_up_gpio_and_device_status_popup(self) -> None:
        self.pi: pigpio.pi = pigpio.pi()
        self.pi.set_mode(17, pigpio.INPUT)
        self.pi.set_pull_up_down(17, pigpio.PUD_UP)
        Clock.schedule_interval(self._poll_gpio, 0.05)
        self.network_status_popup: Popup = self._build_network_status_popup()
        self.network_status_popup.bind(on_open=self.update_popup_ip_address)

    def _build_network_status_popup(self) -> Popup:
        return Popup(title='Device Status',
                     content=Label(text='IP ADDRESS WILL GO HERE'),
                     size_hint=(1, 1), auto_dismiss=False)

    def update_popup_ip_address(self, instance: Popup) -> None:
        """Update the popup with the current IP address"""
        interface = "wlan0"
        ipaddr = lampi_touch.lampi_util.get_ip_address(interface)
        deviceid = lampi_touch.lampi_util.get_device_id()
        msg = (f"Version: {''}\n"  # Version goes in the single quotes
               f"{interface}: {ipaddr}\n"
               f"DeviceID: {deviceid}"
               f"\nBroker Bridged: {self.mqtt_broker_bridged}")
        instance.content.text = msg

    def on_gpio17_pressed(self, instance: Any, value: bool) -> None:
        """Open or close the popup depending on the provided value"""
        if value:
            self.network_status_popup.open()
        else:
            self.network_status_popup.dismiss()

    def _poll_gpio(self, _delta_time: float) -> None:
        # GPIO17 is the rightmost button when looking front of LAMPI
        self.gpio17_pressed = not self.pi.read(17)
