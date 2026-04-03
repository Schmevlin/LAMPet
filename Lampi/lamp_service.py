#!/usr/bin/env python3
import time
import json
import pigpio
import paho.mqtt.client as mqtt
import shelve
import colorsys
from typing import Any, Optional

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
                'cleanliness': 100
            }
        self.write_current_settings_to_hardware()

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
        client.message_callback_add(TOPIC_SET_LAMPet_CONFIG, self.on_message_set_pet_status)
        client.on_message = self.default_on_message
        return client

    def serve(self) -> None:
        start_time = time.time()
        while True:
            try:
                self._client.connect(MQTT_BROKER_HOST,
                                     port=MQTT_BROKER_PORT,
                                     keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
                print("Connected to broker")
                break
            except ConnectionRefusedError as e:
                current_time = time.time()
                delay = current_time - start_time
                if (delay) < MAX_STARTUP_WAIT_SECS:
                    print("Error connecting to broker; delaying and "
                          "will retry; delay={:.0f}".format(delay))
                    time.sleep(1)
                else:
                    raise e
        try:
            self._client.loop_forever()
        finally:
            self.db.close()

    def on_connect(self, client: mqtt.Client, userdata: Any,
                   flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode,
                   properties: Optional[mqtt.Properties]) -> None:
        print(f"Connected with reason code: {reason_code}")
        self._client.publish(client_state_topic(MQTT_CLIENT_ID), "1",
                             qos=2, retain=True)
        self._client.subscribe(TOPIC_SET_LAMP_CONFIG, qos=1)
        self._client.subscribe(TOPIC_SET_LAMPet_CONFIG, qos=1)
        # publish current lamp state at startup
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
            new_status = json.loads(msg.payload.decode('utf-8'))
            # Validate keys
            for key in ['hunger', 'happiness', 'cleanliness']:
                if key not in new_status:
                    print(f"Invalid pet payload, missing {key}")
                    return
            self.db['pet_state'] = new_status
            self.publish_pet_change()
        except Exception as e:
            print("Error processing pet message:", e)

    def publish_config_change(self) -> None:
        config = {'color': self.get_current_color(),
                  'brightness': self.get_current_brightness(),
                  'on': self.get_current_onoff(),
                  'client': self.get_last_client()}
        self._client.publish(TOPIC_LAMP_CHANGE_NOTIFICATION,
                             json.dumps(config).encode('utf-8'), qos=1,
                             retain=True)
    
    def publish_pet_change(self):
        pet_status = self.db['pet_state']
        self._client.publish(TOPIC_LAMPet_CHANGE_NOTIFICATION, 
                            json.dumps(pet_status).encode('utf-8'),
                            qos=1, retain=True)

    def get_last_client(self) -> str:
        return self.db['client']

    def set_last_client(self, new_client: str) -> None:
        self.db['client'] = new_client

    def get_current_brightness(self) -> float:
        return self.db['brightness']

    def set_current_brightness(self, new_brightness: float) -> None:
        if new_brightness < 0 or new_brightness > 1.0:
            raise InvalidLampConfig()
        self.db['brightness'] = round(new_brightness, FP_DIGITS)
        self.write_current_settings_to_hardware()

    def get_current_onoff(self) -> bool:
        return self.db['on']

    def set_current_onoff(self, new_onoff: bool) -> None:
        if new_onoff not in [True, False]:
            raise InvalidLampConfig()
        self.db['on'] = new_onoff
        self.write_current_settings_to_hardware()

    def get_current_color(self) -> dict[str, float]:
        return self.db['color'].copy()

    def set_current_color(self, new_color: dict[str, float]) -> None:
        for ch in ['h', 's']:
            if new_color[ch] < 0 or new_color[ch] > 1.0:
                raise InvalidLampConfig()
        self.db['color'] = {'h': round(new_color['h'], FP_DIGITS),
                            's': round(new_color['s'], FP_DIGITS)}
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
