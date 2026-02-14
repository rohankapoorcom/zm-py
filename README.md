# zm-py

[![image](https://badge.fury.io/py/zm-py.png)](https://badge.fury.io/py/zm-py)

[![Python package](https://github.com/rohankapoorcom/zm-py/actions/workflows/python-qa.yml/badge.svg)](https://github.com/rohankapoorcom/zm-py/actions/workflows/python-qa.yml)

[![image](https://img.shields.io/pypi/pyversions/zm-py.svg)](https://pypi.python.org/pypi/zm-py)

[![license](https://img.shields.io/github/license/rohankapoorcom/zm-py.svg?style=flat-square)](https://github.com/rohankapoorcom/zm-py/blob/master/LICENSE.md)

A lightweight Python API client for [ZoneMinder](https://www.zoneminder.org), built specifically for the [Home Assistant ZoneMinder integration](https://www.home-assistant.io/integrations/zoneminder/).

## Project Status

**This project is in maintenance mode.** zm-py provides the limited set of ZoneMinder API interactions that Home Assistant needs (monitors, camera streaming, events, sensors, and switches). Bug fixes and compatibility updates are accepted; new feature development is not planned.

## Not pyzm / pyzm2

zm-py is **not** a general-purpose ZoneMinder Python library. For full-featured ZoneMinder API access, see [pyzm](https://github.com/ZoneMinder/pyzm) or its fork [pyzm2](https://github.com/pliablepixels/pyzm). zm-py covers only the subset of the ZoneMinder API required by Home Assistant and carries no heavy dependencies. Replacing zm-py with pyzm or pyzm2 would require significant refactoring of the HA integration due to dependency conflicts and functional differences.

## Origins

zm-py is based on code that was originally part of [Home Assistant](https://www.home-assistant.io).
Historical sources and authorship information is available as part of the Home Assistant project:

- [ZoneMinder Platform](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/zoneminder.py)
- [ZoneMinder Camera](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/camera/zoneminder.py)
- [ZoneMinder Sensor](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/sensor/zoneminder.py)
- [ZoneMinder Switch](https://github.com/home-assistant/home-assistant/commits/dev/homeassistant/components/switch/zoneminder.py)

## Installation

### PyPI

```bash
pip install zm-py
```

## Usage

```python
from zoneminder.zm import ZoneMinder

SERVER_HOST = "{{host}}:{{port}}"
USER = "{{user}}"
PASS = "{{pass}}"
SERVER_PATH = "{{path}}"

zm_client = ZoneMinder(
    server_host=SERVER_HOST,
    server_path=SERVER_PATH,
    username=USER,
    password=PASS,
    verify_ssl=False
)

# Zoneminder authentication
zm_client.login()


# Get all monitors
monitors = zm_client.get_monitors()

for monitor in monitors:
    print(monitor)

>>> Monitor(id='monitor_id', name='monitor_name', controllable='is_controllable')


# Move camera down
controllable_monitors = [m for m in monitors if m.controllable]

for monitor in controllable_monitors:
    zm_client.move_monitor(monitor, "right")
```
