#!/bin/bash

sleep 3

# enable the AP
systemctl enable dnsmasq
systemctl start dnsmasq
systemctl enable dhcpcd
systemctl start dhcpcd
systemctl unmask hostapd
systemctl enable hostapd
systemctl start hostapd

# load wan configuration
systemctl stop wpa_supplicant.service 
systemctl disable wpa_supplicant.service
cat << EOF > /etc/wpa_supplicant/wpa_supplicant.conf
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
EOF

reboot now
