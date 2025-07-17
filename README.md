# GadgetbridgeMqtt

This is a Gadgetbridge MQTT bridge for TrueNAS Scale, which allows you to connect your Gadgetbridge database to Home Assistant or other MQTT clients.

## Setup

- copy content [```compose.yaml```](./compose.yaml) your TrueNAS Scale Apps -> Discover Apps -> ⋮ -> Install via YAML
- edit
  - mount point for your Gadgetbridge database
  - your Timezone
  - environment variables for your MQTT broker
- start the app

## Editing Sensors

- add new mqtt sensor around here [main.py#L133](https://git.olli.info/Oliver/GadgetbridgeMqtt/src/branch/main/main.py#L133)
- add new function for new sensor around here [main.py#L291](https://git.olli.info/Oliver/GadgetbridgeMqtt/src/branch/main/main.py#L291)
