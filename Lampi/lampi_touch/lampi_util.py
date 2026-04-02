import socket
import fcntl
import struct

DEVICE_ID_FILENAME = '/sys/class/net/eth0/address'


def get_ip_address(ifname: str) -> str:
    """Get the IP address associated with the given network interface.

    Parameters
    ----------
    ifname : str
        The network interface to check (e.g. "wlan0")

    Returns
    -------
    str
        The IP address of this machine on the given interface
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', bytes(ifname[:15], 'utf-8'))
        )[20:24])
    except Exception:
        return ''


def get_device_id() -> str:
    try:
        mac_addr = open(DEVICE_ID_FILENAME).read().strip()
        return mac_addr.replace(':', '')
    except Exception:
        return 'UNKNOWN'
