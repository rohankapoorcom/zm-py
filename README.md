# Zm-py

[![image](https://badge.fury.io/py/zm-py.svg)](https://badge.fury.io/py/zm-py/)

[![image](https://travis-ci.org/rohankapoorcom/zm-py.svg?branch=master)](https://travis-ci.org/rohankapoorcom/zm-py)

[![image](https://img.shields.io/pypi/pyversions/zm-py.svg)](https://pypi.python.org/pypi/zm-py)

[![license](https://img.shields.io/github/license/rohankapoorcom/zm-py.svg?style=flat-square)](https://github.com/rohankapoorcom/zm-py/blob/master/LICENSE.md)

A loose python wrapper around the [ZoneMinder](https://www.zoneminder.org) API. As time goes on additional functionality will be added to this API client.

zm-py is based on code that was originally part of [Home Assistant](https://www.home-assistant.io). Historical sources and authorship information is available as part of the Home Assistant project:

- [ZoneMinder Platform](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/zoneminder.py)
- [ZoneMinder Camera](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/camera/zoneminder.py)
- [ZoneMinder Sensor](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/sensor/zoneminder.py)
- [ZoneMinder Switch](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/switch/zoneminder.py)

## Installation

### PyPI

```bash
$ pip install zm-py
```

## Usage

```python
from zoneminder.zm import ZoneMinder

SERVER_HOST = "{{host}}:{{port}}"
USER = "{{user}}"
PASS = "{{pass}}"
SERVER_PATH = "{{path}}"

zm_client = ZoneMinder(
    server_host=SERVER_HOST, server_path=SERVER_PATH, username=USER, password=PASS, verify_ssl=False
)

#Zoneminder authentication
zm_client.login()


#Get all monitors
monitors = zm_client.get_monitors()

for monitor in monitors:
    print(monitor)

>>> Monitor(id='monitor_id', name='monitor_name', controllable='is_controllable')


#Move camera down
controllable_monitors = [m for m in monitors if m.controllable]

for monitor in controllable_monitors:
    zm_client.move_monitor(monitor, "right")
```
