#!/bin/sh

cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
cat /sys/bus/usb-serial/devices/ttyUSB1/latency_timer


echo 1 > /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer

echo 1 > /sys/bus/usb-serial/devices/ttyUSB1/latency_timer
cat /sys/bus/usb-serial/devices/ttyUSB1/latency_timer

