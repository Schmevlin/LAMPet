import paho.mqtt.client

DEVICE_ID_FILENAME = '/sys/class/net/eth0/address'

# MQTT Topic Names
TOPIC_SET_LAMP_CONFIG: str = "lamp/set_config"
TOPIC_LAMP_CHANGE_NOTIFICATION: str = "lamp/changed"
TOPIC_LAMP_ASSOCIATED: str = "lamp/associated"


def get_device_id() -> str:
    mac_addr = open(DEVICE_ID_FILENAME).read().strip()
    return mac_addr.replace(':', '')


def client_state_topic(client_id: str) -> str:
    return 'lamp/connection/{}/state'.format(client_id)


def broker_bridge_connection_topic() -> str:
    device_id = get_device_id()
    return '$SYS/broker/connection/{}_broker/state'.format(device_id)


# MQTT Broker Connection info
MQTT_VERSION: int = paho.mqtt.client.MQTTv311
MQTT_BROKER_HOST: str = "localhost"
MQTT_BROKER_PORT: int = 1883
MQTT_BROKER_KEEP_ALIVE_SECS: int = 60
