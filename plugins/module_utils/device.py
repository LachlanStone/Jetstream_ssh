def build_device(module):
    """Build a Netmiko device dict from Ansible module params."""
    return {
        "device_type": "tplink_jetstream",
        "host": module.params["host"],
        "port": module.params["port"],
        "username": module.params["username"],
        "password": module.params["password"],
        "secret": module.params["enable_password"],
    }
