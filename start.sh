#!/bin/bash
# Helpful to read output when debugging
set -x

# Stop display manager
systemctl stop display-manager.service
## Uncomment the following line if you use GDM
#killall gdm-x-session

for i in {1..5}; do
    modprobe -r nvidia_drm && break
    sleep 1
done

sudo rmmod nvidia_drm
sudo rmmod nvidia_uvm
sudo rmmod nvidia_modeset
sudo rmmod nvidia

# Unbind VTconsoles
echo 0 > /sys/class/vtconsole/vtcon0/bind
echo 0 > /sys/class/vtconsole/vtcon1/bind

# Unbind EFI-Framebuffer
echo efi-framebuffer.0 > /sys/bus/platform/drivers/efi-framebuffer/unbind

# Avoid a Race condition by waiting 2 seconds. This can be calibrated to be shorter or longer if required for your system
sleep 2

# Load VFIO Kernel Module  
modprobe vfio-pci  
