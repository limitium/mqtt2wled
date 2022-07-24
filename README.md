# Mqtt 2 wled bridge
![Build&push docker image](https://github.com/limitium/mqtt2wled/workflows/Build&push%20docker%20image/badge.svg)

## Description:

Converts zigbee2mqtt xiaomi magic cube to wled

## Usage:

- Create a folder to hold the config (default: "conf/")
- Add config in yaml format to the folder. (See exampleconf/conf.yaml for details)
- Run  ./mqtt_exporter.py or Docker `docker run -v /Users/limi/projects/mqtt_wled/conf:/usr/src/app/conf mqtt2wled`
- Profit!

## Config:

Yaml files in the folder config/ is combined and read as config.
See exampleconf/ for examples.

## Python dependencies:

 - paho-mqtt
 - PyYAML
 - yamlreader

## Todo:

- Add persistence of metrics on restart
- Add TTL for metrics
