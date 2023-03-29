#!/bin/bash

#Скрипт для подключения к bgp-оболочке маршрутизатора.
router=${1:-R1}
echo "Connecting to $router shell"

sudo python run.py --node $router --cmd "telnet localhost bgpd"
