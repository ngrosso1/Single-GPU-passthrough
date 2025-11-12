# Single-GPU-Passthrough

This script will help install, configure, and run a single GPU passthrough for a VFIO VM. So far this script only works for nvidia cards. 

## 🐍 Dependencies

❗ Be sure to have a windows iso and virtio drivers downloaded before running the script ❗

* https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso
* https://www.microsoft.com/en-us/software-download/windows11

### Arch-based

```
    sudo pacman -S python3 tk libvirt-python
```

### Debian, PopOS, Ubuntu

```
    sudo apt-get install python3 python3-tk python3-libvirt
```

### Fedora

```
    sudo dnf install python3 python3-tkinter python3-libvirt
```

## Usage:

```
    sudo python3 main.py
```

## ⚠️ Troubleshooting:

* If you are running Fedora there seems to be a bug with virt-manager. You will need to remove the display spice manually. The script should tell you when this should take place but keep this in mind
* If you passed the GPU through the VM and the screen has been black for a long time then there may have been an issue. To troubleshoot this ssh into your PC and run the following below. 
    * lsmod | grep nvidia

    There should be a nvidia driver or service in use as shown by the output. Add them to the hooks scripts below (replace {vm_name} with the name of your vm)
    * /etc/libvirt/hooks/qemu.d/{vm_name}/prepare/begin/start.sh
    * /etc/libvirt/hooks/qemu.d/{vm_name}/release/end/revert.sh
* If you are having issues trying to move your VM to an external drive:
    * Ensure you have said drive mounted
    * exFat (and any others that do not have file permissions) can cause issues with qemu
    * If the external drive has a different file system that you have the proper package installed on your system. For NTFS it usually is ntfs-3g, exFat (not recomended) is exfat-utils, etc.


