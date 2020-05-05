#!/bin/bash

# install k3s
curl -sfL https://get.k3s.io | sh -
# stop and disable k3s from running
sudo systemctl stop k3s
sudo systemctl disable k3s
# remove the k3s runtime directory (binaries are still in place)
sudo rm -rf /var/lib/rancher/k3s