#!/bin/bash

exec 2> /var/log/turnkey_ap.log      # send stderr from this script to a log file
exec 1>2                      # send stdout to the same log file
set -x                         # tell sh to display commands before execution

sleep 3

# disable wpa_supplicant
sudo systemctl stop wpa_supplicant
sudo systemctl disable wpa_supplicant
# load default (no network) wan configuration
sudo cp /var/lib/rancher/turnkey/wpa.conf /etc/wpa_supplicant/wpa_supplicant.conf

# enable the AP
sudo cp /var/lib/rancher/turnkey/config/hostapd.conf /etc/hostapd/hostapd.conf
sudo cp /var/lib/rancher/turnkey/config/dhcpcd.conf /etc/dhcpcd.conf
sudo cp /var/lib/rancher/turnkey/config/dnsmasq.conf /etc/dnsmasq.conf
sudo systemctl enable dnsmasq
sudo systemctl start dnsmasq
sudo systemctl enable dhcpcd
sudo systemctl start dhcpcd
sudo systemctl enable hostapd
sudo systemctl start hostapd

