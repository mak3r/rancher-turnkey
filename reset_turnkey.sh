#!/bin/sh

echo {\'status\':\'disconnected\'} > /var/lib/rancher/turnkey/status.json
ifconfig wlan0 down
rm /boot/reset-turnkey