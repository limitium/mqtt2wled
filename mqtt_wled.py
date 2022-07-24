#!/usr/bin/env python

from collections import defaultdict
import json
import requests
import logging
import argparse
import paho.mqtt.client as mqtt
import yaml
import os
import re
import operator
import time
import signal
import colorsys
import sys
from yamlreader import yaml_load

VERSION = '0.1'


def _read_config(config_path):
    """Read config file from given location, and parse properties"""

    if config_path is not None:
        if os.path.isfile(config_path):
            logging.info(f'Config file found at: {config_path}')
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f.read())
            except yaml.YAMLError:
                logging.exception('Failed to parse configuration file:')

        elif os.path.isdir(config_path):
            logging.info(
                f'Config directory found at: {config_path}')
            try:
                return yaml_load(config_path)
            except yaml.YAMLError:
                logging.exception('Failed to parse configuration directory:')

    return {}


def _parse_config_and_add_defaults(config_from_file):
    """Parse content of configfile and add default values where needed"""

    config = {}
    logging.info(f'_parse_config Config from file: {str(config_from_file)}')
    # Logging values ('logging' is optional in config
    if 'logging' in config_from_file:
        config['logging'] = _add_config_and_defaults(
            config_from_file['logging'], {'logfile': '', 'level': 'info'})
    else:
        config['logging'] = _add_config_and_defaults(
            None, {'logfile': '', 'level': 'info'})

    # MQTT values
    if 'mqtt' in config_from_file:
        config['mqtt'] = _add_config_and_defaults(
            config_from_file['mqtt'], {'host': 'localhost'})
    else:
        config['mqtt'] = _add_config_and_defaults(None, {'host': 'localhost'})

    if 'auth' in config['mqtt']:
        config['mqtt']['auth'] = _add_config_and_defaults(
            config['mqtt']['auth'], {})
        _validate_required_fields(config['mqtt']['auth'], 'auth', ['username'])

    if 'tls' in config['mqtt']:
        config['mqtt']['tls'] = _add_config_and_defaults(
            config['mqtt']['tls'], {})

    # WLED values
    if 'wled' in config_from_file:
        config['wled'] = _add_config_and_defaults(config_from_file['wled'], {'url': 'localhost'})
    return config


def _validate_required_fields(config, parent, required_fields):
    """Fail if required_fields is not present in config"""
    for field in required_fields:
        if field not in config or config[field] is None:
            if parent is None:
                error = f'\'{field}\' is a required field in configfile'
            else:
                error = f'\'{field}\' is a required parameter for field {parent} in configfile'
            raise TypeError(error)


def _add_config_and_defaults(config, defaults):
    """Return dict with values from config, if present, or values from defaults"""
    if config is not None:
        defaults.update(config)
    return defaults.copy()


def _strip_config(config, allowed_keys):
    return {k: v for k, v in config.items() if k in allowed_keys and v}


# noinspection SpellCheckingInspection
def _log_setup(logging_config):
    """Setup application logging"""

    logfile = logging_config['logfile']

    log_level = logging_config['level']

    numeric_level = logging.getLevelName(log_level.upper())
    if not isinstance(numeric_level, int):
        raise TypeError(f'Invalid log level: {log_level}')

    if logfile != '':
        logging.info('Logging redirected to: ' + logfile)
        # Need to replace the current handler on the root logger:
        file_handler = logging.FileHandler(logfile, 'a')
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        file_handler.setFormatter(formatter)

        log = logging.getLogger()  # root logger
        for handler in log.handlers:  # remove all old handlers
            log.removeHandler(handler)
        log.addHandler(file_handler)

    else:
        logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s')

    logging.getLogger().setLevel(numeric_level)
    logging.info(f'log_level set to: {log_level}')


# noinspection PyUnusedLocal
def _on_connect(client, userdata, flags, rc):
    """The callback for when the client receives a CONNACK response from the server."""
    logging.info(f'Connected to broker, result code {str(rc)}')
    topic = userdata['topic']
    client.subscribe(topic)
    logging.info(f'Subscribing to topic: {topic}')


# noinspection PyUnusedLocal
def _on_message(client, userdata, msg):
    """The callback for when a PUBLISH message is received from the server."""
    payload = msg.payload
    logging.debug(
        f'_on_message Msg received on topic: {msg.topic}, Value: {str(payload)}')
    
    try:
        json_data = json.loads(payload)
        if 'action' in json_data:
            action = json_data['action']
            if action:
                _do_action(action, json_data)                
    except json.JSONDecodeError:
        logging.info(f'No JSON payload {payload}')            



mode = 'none'
state = {}
config = {}

def _do_action(action, json):
    global mode
    logging.info(f'Action: {action}')            
    
    if action == 'shake':
        if mode == 'none':
            mode = 'color'
        elif mode == 'color':
            mode = 'bri'
        elif mode == 'bri':
            mode = 'color'
        logging.info(f'Set mode: {mode}')                     

    if action == 'tap':
        mode = 'none'
        logging.info(f'Set mode: {mode}')                     

    if action == 'rotate_left' or action == 'rotate_right':
        angle = json['angle']
        logging.info(f'Angle: {angle}')
        
        try:
            rgb = state['seg'][0]['col'][0]
                
            h, s, v = colorsys.rgb_to_hsv(rgb[0],rgb[1],rgb[2])
            
            logging.info(f'RGB {rgb} -> HSV {h},{s},{v}')

            if mode == 'bri':
                v = (int)(v + angle / (3))
                v = max(min(v, 255), 0)

            if mode == 'color':           
                h = h  + angle / (3 * 360)
                h = max(min(h,1), 0)

            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            r=int(r)
            g=int(g)
            b=int(b)
            logging.info(f'HSV {h},{s},{v} -> RGB {r},{g},{b}')

            _wled_post({'seg':{'col':[[r,g,b,0],[],[]]}, 'v':True}) 
        except Exception as e:
            logging.error(e)                        

    if action == 'flip90':
        mode = 'none'
        _wled_post({'on':True, 'v':True})                     

    if action == 'flip180':   
        _wled_post({'on':False, 'v':True})

    # if action == 'slide':   
    #     logging.info(f'Set mode: {mode}')                     


def _wled_post(data):
    global state,config
    try:
        resp = requests.post(config['wled']['url']+'/json', json=data)
        resp.raise_for_status()
        state = json.loads(resp.text)['state']
        logging.info(f'State: {state}')            
    except json.JSONDecodeError:
        logging.info(f'No JSON reponse {resp}')  
        
    except requests.exceptions.RequestException as err:
        print ("OOps: Something Else",err)
    except requests.exceptions.HTTPError as errh:
        print ("Http Error:",errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:",errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:",errt)  
    

def _mqtt_init(mqtt_config):
    """Setup mqtt connection"""
    logging.info(f'Connecting {str(mqtt_config)}')
    mqtt_client = mqtt.Client(userdata={
        'topic': mqtt_config['topic'],
        'metric_ttl': mqtt_config['metric_ttl'],
        'metrics': {
            'exporter': {},
            'users': {}
        }
    })
    mqtt_client.on_connect = _on_connect
    mqtt_client.on_message = _on_message

    if 'auth' in mqtt_config:
        auth = _strip_config(mqtt_config['auth'], ['username', 'password'])
        mqtt_client.username_pw_set(**auth)

    if 'tls' in mqtt_config:
        tls_config = _strip_config(mqtt_config['tls'], [
                                   'ca_certs', 'certfile', 'keyfile', 'cert_reqs', 'tls_version'])
        mqtt_client.tls_set(**tls_config)

    mqtt_client.connect(**_strip_config(mqtt_config,
                                        ['host', 'port', 'keepalive']))
    return mqtt_client


def _signal_handler(sig, frame):
    # pylint: disable=E1101
    logging.info('Received {0}'.format(signal.Signals(sig).name))
    sys.exit(0)


def main():
    global config
    # Setup argument parsing
    parser = argparse.ArgumentParser(
        description='Simple program to export formatted mqtt messages to wled')
    parser.add_argument('-c', '--config', action='store', dest='config', default='conf',
                        help='Set config location (file or directory), default: \'conf\'')
    options = parser.parse_args()

    # Initial logging to console
    _log_setup({'logfile': '', 'level': 'info'})
    signal.signal(signal.SIGINT, _signal_handler)

    # Read config file from disk
    from_file = _read_config(options.config)
    config = _parse_config_and_add_defaults(from_file)

    # Set up logging
    _log_setup(config['logging'])

    # Set up mqtt client and loop forever
    mqtt_client = _mqtt_init(config['mqtt'])
    mqtt_client.loop_forever()


if __name__ == '__main__':
    main()
