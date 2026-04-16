#!/usr/bin/env python3
import time
import json
import pigpio
import paho.mqtt.client as mqtt
import shelve
import threading
import colorsys
from typing import Any, Optional
from datetime import datetime

from lamp_common import *

PIN_R: int = 19
PIN_G: int = 26
PIN_B: int = 13
PINS: list[int] = [PIN_R, PIN_G, PIN_B]
PWM_RANGE: int = 1000
PWM_FREQUENCY: int = 1000

LAMP_STATE_FILENAME: str = "lamp_state"
MQTT_CLIENT_ID: str = "lamp_service"

FP_DIGITS: int = 2
MAX_STARTUP_WAIT_SECS: float = 10.0

PET_DECAY_INTERVAL = 5.0
HUNGER_DECAY = 5
HAPPINESS_DECAY = 5
CLEANLINESS_DECAY = 20


class InvalidLampConfig(Exception):
    pass


class LampDriver:
    def __init__(self) -> None:
        self._gpio: pigpio.pi = pigpio.pi()
        for color_pin in PINS:
            self._gpio.set_mode(color_pin, pigpio.OUTPUT)
            self._gpio.set_PWM_dutycycle(color_pin, 0)
            self._gpio.set_PWM_frequency(color_pin, PWM_FREQUENCY)
            self._gpio.set_PWM_range(color_pin, PWM_RANGE)

    def change_color(self, r: float, g: float, b: float) -> None:
        pins_values = zip(PINS, [r, g, b])
        for pin, value in pins_values:
            self._gpio.set_PWM_dutycycle(pin, value)


class LampService:
    def __init__(self) -> None:
        self.lamp_driver: LampDriver = LampDriver()
        self._client: mqtt.Client = self._create_and_configure_broker_client()
        self.db_lock = threading.Lock()
        self.db: shelve.Shelf[Any] = shelve.open(LAMP_STATE_FILENAME)
        
        if 'color' not in self.db:
            self.db['color'] = {'h': round(1.0, FP_DIGITS),
                                's': round(1.0, FP_DIGITS)}
        if 'brightness' not in self.db:
            self.db['brightness'] = round(1.0, FP_DIGITS)
        if 'on' not in self.db:
            self.db['on'] = True
        if 'client' not in self.db:
            self.db['client'] = ''
        if 'pet_state' not in self.db:
            self.db['pet_state'] = {
                'hunger': 100,
                'happiness': 100,
                'cleanliness': 100,
                'state': 'alive',
                'state_since': None
            }
            
        self.write_current_settings_to_hardware()
        
    def db_get(self, key):
        with self.db_lock:
            return self.db[key]

    def db_set(self, key, value):
        with self.db_lock:
            self.db[key] = value

    def _create_and_configure_broker_client(self) -> mqtt.Client:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID,
            protocol=MQTT_VERSION
        )
        client.will_set(client_state_topic(MQTT_CLIENT_ID), "0",
                        qos=2, retain=True)
        client.enable_logger()
        client.on_connect = self.on_connect
        client.message_callback_add(TOPIC_SET_LAMP_CONFIG,
                                    self.on_message_set_config)
        client.message_callback_add(TOPIC_SET_LAMPet_CONFIG, 
                                    self.on_message_set_pet_status)

        return client

    def serve(self) -> None:
        while True:
            try:
                self._client.connect(
                    MQTT_BROKER_HOST,
                    port=MQTT_BROKER_PORT,
                    keepalive=MQTT_BROKER_KEEP_ALIVE_SECS
                )
                print("Connected to broker")
                break
            except Exception:
                print("Retrying connection...")
                time.sleep(1)

        last = time.time()

        while True:
            self._client.loop(timeout=1.0)  

            now = time.time()
            if now - last >= PET_DECAY_INTERVAL:
                self.apply_decay()
                last = now

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        self._client.publish(client_state_topic(MQTT_CLIENT_ID), "1", qos=2, retain=True)
        self._client.subscribe(TOPIC_SET_LAMP_CONFIG, qos=1)
        self._client.subscribe(TOPIC_SET_LAMPet_CONFIG, qos=1)
        self.publish_config_change()

    def default_on_message(self, client: mqtt.Client, userdata: Any,
                           msg: mqtt.MQTTMessage) -> None:
        print("Received unexpected message on topic " +
              msg.topic + " with payload '" + str(msg.payload) + "'")

    def on_message_set_config(self, client: mqtt.Client, userdata: Any,
                              msg: mqtt.MQTTMessage) -> None:
        try:
            new_config = json.loads(msg.payload.decode('utf-8'))
            if 'client' not in new_config:
                raise InvalidLampConfig()
            self.set_last_client(new_config['client'])
            if 'on' in new_config:
                self.set_current_onoff(new_config['on'])
            if 'color' in new_config:
                self.set_current_color(new_config['color'])
            if 'brightness' in new_config:
                self.set_current_brightness(new_config['brightness'])
            self.publish_config_change()
        except InvalidLampConfig:
            print("error applying new settings " + str(msg.payload))
            
    def on_message_set_pet_status(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())

            if 'action' in data:
                self.apply_action(data['action'], data['value'])
            else:
                print("Invalid pet message:", data)

        except Exception as e:
            print("pet message error:", e)

    def apply_action(self, action: str, value: int):
        print("ACTION:", action, "VALUE:", value, type(action), type(value))
        pet = self.db_get('pet_state')
        
        if pet['state'] != 'dead':
            if action == "eat":
                pet['hunger'] = min(100, pet['hunger'] + value)

            elif action == "play":
                pet['happiness'] = min(100, pet['happiness'] + value)

            elif action == "clean":
                pet['cleanliness'] = min(100, pet['cleanliness'] + value)

            self.db['pet_state'] = pet
            self.publish_pet_change()


    def apply_decay(self):
        pet = self.db_get('pet_state')
        
        old_pet = pet.copy()

        pet['hunger'] = max(0, pet['hunger'] - HUNGER_DECAY)
        pet['happiness'] = max(0, pet['happiness'] - HAPPINESS_DECAY)
        pet['cleanliness'] = max(0, pet['cleanliness'] - CLEANLINESS_DECAY)
        
        
        is_critical = sum([
            pet['hunger'] == 0,
            pet['happiness'] == 0,
            pet['cleanliness'] == 0
        ]) >= 2
        
        now = time.time()


        if pet['state'] == 'alive':
            if is_critical:
                pet['state'] = 'dying'
                pet['state_since'] = now

        elif pet['state'] == 'dying':
            if not is_critical:
                pet['state'] = 'alive'
                pet['state_since'] = None
            elif now - pet['state_since'] >= 60:
                pet['state'] = 'dead'
                pet['state_since'] = now

        elif pet['state'] == 'dead':
            # check next-day
            death_time = datetime.fromtimestamp(pet['state_since'])
            if datetime.now().date() > death_time.date():
                pet['state'] = 'alive'
                pet['state_since'] = None

                pet['hunger'] = 100
                pet['happiness'] = 100
                pet['cleanliness'] = 100

        if pet != old_pet:
            self.db_set('pet_state', pet)
            self.publish_pet_change()

    # ---------------- PUBLISH ----------------

    def publish_pet_change(self):
        self._client.publish(
            TOPIC_LAMPet_CHANGE_NOTIFICATION,
            json.dumps(self.db_get('pet_state')).encode(),
            qos=1,
            retain=True
        )

    def publish_config_change(self):
        config = {
            'color': self.get_current_color(),
            'brightness': self.get_current_brightness(),
            'on': self.get_current_onoff(),
            'client': self.get_last_client()
        }

        self._client.publish(
            TOPIC_LAMP_CHANGE_NOTIFICATION,
            json.dumps(config).encode(),
            qos=1,
            retain=True
        )

    # ---------------- LAMP STATE ----------------

    def get_last_client(self) -> str:
        return self.db_get('client')

    def set_last_client(self, new_client: str) -> None:
        self.db_set('client', new_client)

    def get_current_brightness(self) -> float:
        return self.db_get('brightness')

    def set_current_brightness(self, new_brightness: float) -> None:
        if new_brightness < 0 or new_brightness > 1.0:
            raise InvalidLampConfig()
        self.db_set('brightness', round(new_brightness, FP_DIGITS))
        self.write_current_settings_to_hardware()

    def get_current_onoff(self) -> bool:
        return self.db_get('on')

    def set_current_onoff(self, new_onoff: bool) -> None:
        if new_onoff not in [True, False]:
            raise InvalidLampConfig()
        self.db_set('on', new_onoff)
        self.write_current_settings_to_hardware()

    def get_current_color(self) -> dict[str, float]:
        return self.db_get('color').copy()

    def set_current_color(self, new_color: dict[str, float]) -> None:
        for ch in ['h', 's']:
            if new_color[ch] < 0 or new_color[ch] > 1.0:
                raise InvalidLampConfig()
        self.db_set('color', {'h': round(new_color['h'], FP_DIGITS),
                            's': round(new_color['s'], FP_DIGITS)})
        self.write_current_settings_to_hardware()

    def write_current_settings_to_hardware(self) -> None:
        onoff = self.get_current_onoff()
        brightness = self.get_current_brightness()
        color = self.get_current_color()

        r, g, b = self.calculate_rgb(color['h'], color['s'], brightness, onoff)
        self.lamp_driver.change_color(r, g, b)

    def calculate_rgb(self, hue: float, saturation: float, brightness: float,
                      is_on: bool) -> tuple[float, float, float]:
        pwm = float(PWM_RANGE)
        r, g, b = 0.0, 0.0, 0.0

        if is_on:
            rgb = colorsys.hsv_to_rgb(hue, saturation, 1.0)
            r, g, b = tuple(channel * pwm * brightness
                            for channel in rgb)
        return r, g, b


if __name__ == '__main__':
    LampService().serve()