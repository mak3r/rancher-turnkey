#!/bin/bash

exec 2> /var/log/turnkey_ap.log      # send stderr from this script to a log file
exec 1>2                      # send stdout to the same log file
set -x                         # tell sh to display commands before execution

sleep 3

sudo systemctl disable hostapd
sudo systemctl stop hostapd
sudo systemctl disable dnsmasq
sudo systemctl stop dnsmasq
sudo systemctl disable dhcpcd
sudo systemctl stop dhcpcd
# disable the AP
sudo rm /etc/hostapd/hostapd.conf
sudo cp /var/lib/rancher/turnkey/config/dhcpcd.conf.disabled /etc/dhcpcd.conf
sudo cp /var/lib/rancher/turnkey/config/dnsmasq.conf.disabled /etc/dnsmasq.conf


# load wlan configuration
sudo systemctl enable wpa_supplicant
sudo systemctl start wpa_supplicant
# wpa_supplicant configuration is written by the python script
