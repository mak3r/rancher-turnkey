#!/bin/bash

# update and upgrade the current system
apt update && apt upgrade -y
# install required tools
apt install -y dnsmasq hostapd python3-flask python3-requests

# make sure wlan0 is not connected
ifconfig wlan0 down

# stop dnsmasq and hostapd while we reconfigure them
systemctl stop dnsmasq
systemctl stop hostapd

## copy disabled dhcpcd configuration
cp /etc/dhcpcd.conf /var/lib/rancher/turnkey/config/dhcpcd.conf.disabled

# configure dhcpcd
cat <<EOF >> /etc/dhcpcd.conf

interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

## Copy dhcpcd configuration to config directory
cp /etc/dhcpcd.conf /var/lib/rancher/turnkey/config/dhcpcd.conf

# configuration done, restart dhcpcd
service dhcpcd restart

# backup the original dnsmasq configuration
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig

# Create a new dnsmasq configuration for this device
cat <<EOF >> /etc/dnsmasq.conf
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
EOF

## copy the dnsmasq config to config directory
cp /etc/dnsmasq.conf /var/lib/rancher/turnkey/config/dnsmasq.conf
## Create the disabled version
sed 's/^.*$/#&/g' /var/lib/rancher/turnkey/config/dnsmasq.conf > /var/lib/rancher/turnkey/config/dnsmasq.conf.disabled 

# startup the dnsmasq service
systemctl start dnsmasq

# setup hostapd configuration
cat <<EOF > /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=ConfigureK3s
hw_mode=a
channel=44
ieee80211d=1
country_code=US
ieee80211n=1
ieee80211ac=1
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=rancher-k3s
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

## Copy hostapd.conf to the config directory
cp /etc/hostapd/hostapd.conf /var/lib/rancher/turnkey/config/hostapd.conf

# fire up hostapd
systemctl unmask hostapd
systemctl enable hostapd
systemctl start hostapd

# Waypoint to insure all is good
echo "Check if things started up properly"
echo '  sudo systemctl status hostapd'
echo '  sudo systemctl status dnsmasq'


echo "Did everything startup ok? [Y/n]"
read ok

if [[ "n" == "$ok" || "N" == "$ok" ]]; then
  echo Aborting..
  echo "Check if the content of the configuration files is correct"
  echo '  /etc/dhcpcd.conf'
  echo '  /etc/dnsmasq.conf'
  echo '  /etc/hostapd/hostapd.conf'
  echo '  /etc/default/hostapd'
  echo 'Also check journactl -xe'
  exit 1;
fi

# ok, looks like we passed the waypoint checks - continue

# Make sure wpa supplicant is off 
systemctl stop wpa_supplicant
systemctl disable wpa_supplicant

# configure wpa_supplicant service
cp /var/lib/rancher/turnkey/image-prep/setup/wpa_supplicant.service /etc/systemd/system/multi-user.target.wants

# configure network interfaces
cp /var/lib/rancher/turnkey/image-prep/setup/wlan0 /etc/network/interfaces.d/.
cp /var/lib/rancher/turnkey/image-prep/setup/eth0 /etc/network/interfaces.d/.

# enable ip forwarding 
sed -i.bak 's/\(#\)\(net\.ipv4\.ip_forward\)/\2/' /etc/sysctl.conf 

# setup a MASQUERADE for traffic talking to this gateway
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
# save the rule
iptables-save > /etc/iptables.ipv4.nat

# make sure the iptables rule sticks on boot
cp /etc/rc.local /etc/rc.local.orig
sed -i.bak '0,/^exit 0/s/^exit 0/iptables-restore < \/etc\/iptables\.ipv4\.nat\n&/'  /etc/rc.local
sed -i.bak '0,/^exit 0/s/^exit 0/\/usr\/bin\/python3 \/var\/lib\/rancher\/turnkey\/startup.py\n&/'  /etc/rc.local

# setup a tmp log for rc.local just in case the prior commands need debugging
sed -i.bak '0,/^$/s/^$/exec 2> \/tmp\/rc.local.log      # send stderr from rc.local to a log file\n&/' /etc/rc.local
sed -i.bak '0,/^$/s/^$/exec 1>&2                      # send stdout to the same log file\n&/' /etc/rc.local
sed -i.bak '0,/^$/s/^$/set -x                         # tell sh to display commands before execution\n&/' /etc/rc.local


# copy the hostapd service (default service was not always coming up)
cp /var/lib/rancher/turnkey/image-prep/setup/hostapd.service /etc/systemd/system/multi-user.target.wants/hostapd.service

# copy the reset service and link it
cp /var/lib/rancher/turnkey/image-prep/setup/reset-turnkey.service /etc/systemd/system/reset-turnkey.service
# create a softlink as a multi-user target
if [ ! -f "/etc/systemd/system/multi-user.target.wants/reset-turnkey.service" ]; then
  ln -s /etc/systemd/system/reset-turnkey.service /etc/systemd/system/multi-user.target.wants/reset-turnkey.service
fi

# copy the lograte configuration and enable it
cp /var/lib/rancher/turnkey/image-prep/setup/turnkey.logrotate.conf /etc/logrotate.d/99-turnkey.conf

# pre-install k3s components
/var/lib/rancher/turnkey/image-prep/setup/k3s-prep.sh

# pre-install Rancher components
