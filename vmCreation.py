import subprocess
import xml.etree.ElementTree as ET
import libvirt
import getpass
import socket
import sys
from getISO import virtioDrivers

BLUE = '\033[94m'
GREEN = '\033[92m'
RED = '\033[91m'   
YELLOW = '\033[93m'
PURPLE = '\033[35m'
ORANGE = '\033[38;5;214m'
RESET = '\033[0m'

def get_sys_info():
    """Retrieve the current system's CPU info"""
    try:
        #Grabbing CPU info
        cpu_info = subprocess.check_output("lscpu", shell=True, text=True)
        
        #Parse the output to get the number of cores, threads, and sockets
        cores = None
        threads = None
        sockets = None
        for line in cpu_info.splitlines():
            if "Core(s) per socket:" in line:
                cores = int(line.split(":")[1].strip())
            elif "Thread(s) per core:" in line:
                threads = int(line.split(":")[1].strip())
            elif "Socket(s):" in line:
                sockets = int(line.split(":")[1].strip())

        #Get total memory (in MB)
        memory_info = subprocess.check_output("free -m", shell=True, text=True)
        total_memory = None
        for line in memory_info.splitlines():
            if "Mem:" in line:
                total_memory = int(line.split()[1])

        #Getting free disk space
        disk_info = subprocess.check_output("df -h", shell=True, text=True)
        free_disk_space = None
        for line in disk_info.splitlines():
            if line.endswith(" /"):  # Root mount
                parts = line.split()
                if len(parts) >= 4 and parts[3].endswith('G'):
                    free_disk_space = float(parts[3][:-1])  # Strip 'G' and convert to float

        return cores, threads, sockets, total_memory, free_disk_space
    
    except Exception as e:
        print(f"🚨 Error 🚨 fetching CPU info: {RED}{e}{RESET}")
        return None, None, None
    
def get_vm_config():
    """Prompt the user for VM configuration."""
    print("Please provide the following VM configuration:")

    cores, threads, sockets, total_memory, free_disk_space = get_sys_info()
    vcpus = sockets * cores * threads

    #Fix this conditional
    if cores and threads and sockets:
        print(f"\nCurrent system info:")
        print(f"  - Number of total logical CPUs:   {BLUE}{vcpus}{RESET}")
        print(f"  - Number of sockets:              {BLUE}{sockets}{RESET}")
        print(f"  - Cores per socket:               {BLUE}{cores}{RESET}")
        print(f"  - Threads per core:               {BLUE}{threads}{RESET}")
        print("====================================================")
        print(f"  - Free storage space:             {ORANGE}{free_disk_space}GB{RESET}")
        print("====================================================")
        print(f"  - Total memory:                   {YELLOW}{total_memory}MB{RESET}")
    else:
        print("Unable to retrieve CPU information. Please enter the values manually.")

    #Name
    vmPrompt = f"Enter the name of the VM (Default {PURPLE}Windows_VM{RESET}): "
    vm_name = input(vmPrompt) or "Windows_VM"

    #Memory
    while True:
        try:
            memoryInput = input(f"Enter the amount of memory in MB (e.g., {YELLOW}4096{RESET} for {YELLOW}4GB{RESET}): ")
            memory = int(memoryInput)
            
            if memory > total_memory:
                print(f"🚨 Error 🚨 : Memory value cannot exceed total system memory ({YELLOW}{total_memory}MB{RESET}). Try again.")
            else:
                break
        except ValueError:
            print("Invalid input! Please enter only a valid number for memory as shown below!")
            print("16GB       ❌")
            print("16384MB    ❌")
            print("16384      ✅")

    #Storage
    while True:
        try:
            diskSizePrompt = f"Enter the disk size in GB (e.g., {ORANGE}50{RESET}): "
            diskSizeInput = input(diskSizePrompt)
            diskSize = int(diskSizeInput)
            
            if diskSize > free_disk_space:
                print(f"🚨 Error 🚨 : storage value cannot exceed total system free disk space ({ORANGE}{free_disk_space}GB{RESET}). Try again")
            else:
                break
        except ValueError:
            print("Invalid input! Please enter only a valid number (in GB) for storage as shown below!")
            print("50GB     ❌")
            print("50       ✅")

    #CPU
    defaultCores = cores - 1
    promptSockets = f"Enter number of CPU sockets (default {BLUE}{sockets}{RESET}): "
    promptCores = f"Enter number of CPU cores per socket (Default {BLUE}{defaultCores}{RESET}): "
    promptThreads = f"Enter number of threads per core (Default {BLUE}{threads}{RESET}): "
    sockets = input(promptSockets) or str(sockets)
    cores = input(promptCores) or str(defaultCores)
    threads = input(promptThreads) or str(threads)
    tvcpus = int(sockets) * int(cores) * int(threads)

    return vm_name, memory, tvcpus, diskSize, sockets, cores, threads

def create_vm(iso_file, vm_name, memory, vcpus, diskSize, sockets, cores, threads, distro):
    """Use virt-install to create a VM using the provided Windows ISO."""

    if distro == "arch":
        subprocess.run(["systemctl", "enable", "libvertd"])
        subprocess.run(["systemctl", "start", "libvertd"])
        subprocess.run(["virsh", "net-start", "default"])
        subprocess.run(["virsh", "net-autostart", "default"])

    disk_path = f"/var/lib/libvirt/images/{vm_name}.qcow2"
    os_variant = "win11"

    command = [
        "virt-install",
        "--connect", "qemu:///system",
        "--name", vm_name,
        "--memory", str(memory),
        "--vcpus", f"{vcpus},sockets={sockets},cores={cores},threads={threads}",
        "--disk", f"path={iso_file},device=cdrom,boot_order=1",
        "--disk", f"size={diskSize},path={disk_path},format=qcow2,boot_order=2",
        "--cdrom", iso_file,
        "--os-variant", os_variant,
        "--network", "network=default",
        "--graphics", "spice",
        "--cpu", "host-passthrough",
        "--noautoconsole",
        "--machine", "q35",
        "--boot", "uefi",
        "--tpm", "type=emulator,model=tpm-tis,version=2.0"
    ]

    try:
        print(f"Creating VM '{vm_name}'...")
        subprocess.run(command, check=True)
        subprocess.run(["virsh", "destroy", vm_name])
        virtioDrivers(vm_name)
        print(f"VM '{vm_name}' created successfully.")
        print("======================================================================================")
        print("Open up Virt-manager and open the running VM you just created and install windows.")
        print("After, shut down your VM and come back to this terminal session to proceed!")
        print("\n⚠️  Note ⚠️ : Virt-manager sometimes fails to see the windows iso while booting up.")
        print("Just rerunning the VM until it goes to the Windows install screen.")
        print("\nWhen you boot into Windows go to the VirtIO drivers. " \
        "This is found in the CD drive that will be attached to the session.")
        print("The driver is called: virtio-win-gt-x64.msi")
        print("======================================================================================")
        while True:
            user_input = input("Do you want to proceed (Y/n)?").strip().lower()
        
            if user_input in ("yes", "y", ""):
                print("Proceeding to the next function...")
                break
            else:
                print("Waiting for confirmation...")
    except subprocess.CalledProcessError as e:
        print(f"🚨 Error 🚨 during VM creation: {RED}{e}{RESET}")

def cleanupDrives(vm_name):
    """
    Remove all storage devices from the VM except for the main Windows disk.
    """
    conn = libvirt.open('qemu:///system')
    if conn is None:
        print('Failed to connect to libvirt')
        return

    vm = conn.lookupByName(vm_name)
    xml = vm.XMLDesc()
    root = ET.fromstring(xml)

    main_disk_basename = f"{vm_name}.qcow2"
    disks_to_remove = []

    for disk in root.findall('./devices/disk'):
        source = disk.find('source')
        target = disk.find('target')

        if source is None or target is None:
            continue

        device = disk.get('device')
        if device != 'disk' and device != 'cdrom':
            continue

        file_path = source.get('file') or source.get('dev') or source.get('protocol')
        if not file_path:
            continue

        if main_disk_basename not in file_path:
            target_dev = target.get('dev')
            disks_to_remove.append((device, target_dev))

    #Detaching unused disks
    for device_type, target_dev in disks_to_remove:
        print(f"Detaching {device_type} device at {target_dev}...")
        try:
            subprocess.run([
                'virsh', 'detach-disk', vm_name, target_dev, '--persistent'
            ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to detach {target_dev}: {RED}{e}{RESET}")

    if not disks_to_remove:
        print("No additional drives found to detach.")
    else:
        print("All non-Windows drives have been detached.")

    conn.close()

def modify_storage_bus(vm_name):
    #Connecting to the local hypervisor
    conn = libvirt.open('qemu:///system')
    if conn is None:
        print('Failed to open connection to qemu:///system', file=sys.stderr)
        sys.exit(1)

    #Parse XML of the VM
    vm = conn.lookupByName(vm_name)
    xml_desc = vm.XMLDesc()
    root = ET.fromstring(xml_desc)
    modified = False

    #Find the disk elements and update if using bus='sata'
    for disk in root.findall("./devices/disk"):
        #Only modifying the main disk device, not CD-ROMs
        device = disk.get("device")
        if device != "disk":
            continue

        #Delete this?
        #driver = disk.find("driver")
        target = disk.find("target")

        #Checking if disk uses SATA
        if target is not None and target.get("bus") == "sata":
            print(f"Modifying disk {target.get('dev')} from SATA to VirtIO...")
            target.set("bus", "virtio")
            modified = True

            #Updating address type to PCI
            address = disk.find("address")
            if address is not None:
                address.set("type", "pci")

    if modified:
        #Converting the modified XML back to a string
        new_xml_desc = ET.tostring(root, encoding='unicode')

        #Redefine the domain using the updated XML
        conn.defineXML(new_xml_desc)
        print(f"Modified {vm_name} storage to use VirtIO.")
    else:
        print(f"No changes needed for {vm_name}.")

    conn.close()

def get_local_ip():
    #Ensure we can connect to VNC
    subprocess.run(["systemctl", "enable", "ssh"])

    #Creating a dummy socket connection to a non routable IP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
    #If theres an issue, go to default localhost
    except Exception:
        local_ip = '127.0.0.1'
    while True:
        print("===================================================================================")
        print("VNC Server is set up on your VM and ssh is running on your system.")
        print("We will soon attempt to disconnect the GPU from your host to the VM. The VM may")
        print("fail to show a display as it has no graphics drivers. Using VNC we can remote into")
        print("the windows VM and install the needed graphics drivers. For now lets just test it.")
        print("On another device on the same network, remote into the VM via VNC!")
        print(f"Your local IP 🛜 is: {local_ip}")
        print("===================================================================================")
        user_input = input("Are you able to connect to the VM via VNC (Y/n)?").strip().lower()
    
        if user_input in ("yes", "y", ""):
            print("Continuing script...")
            break
        else:
            print("Waiting for confirmation...")




def update_display_to_vnc(vm_name, distro):
    #Adjusting for the bug
    if distro == "fedora":
        while True:
            print("======================================================================================")
            print("There seems to be a bug with virt manager on Fedora. " \
            "For this part you will need to do things manually.")
            print("To do this open up Virt-manager, " \
            "\n      ➡️  On the left side "
            "\n      ➡️  Open the tab show virtual hardware details"
            "\n      ➡️  Right click Display Spice and remove device"
            "\n      ➡️  Preform the same with the Video QXL"
            "\n      ➡️  Click finish"
            "\n      ➡️  Run the VM and then shut it down (there will be no display output which is fine)")
            print("======================================================================================")
            user_input = input("Did you remove the devices and rerun the VM?").strip().lower()
        
            if user_input in ("yes", "y", ""):
                while True:
                    print("===================================================================================")
                    print("Readd the Graphics and change these values:")
                    "\n      ➡️  Type:      VNC Server"
                    "\n      ➡️  Address:   All Interfaces"
                    "\n      ➡️  Password:  Set a custom passoword"
                    print("===================================================================================")
                    user_input = input("Did you remove the devices?").strip().lower()
                
                    if user_input in ("yes", "y", ""):
                        return
                    else:
                        print("Waiting for confirmation...")
                break
            else:
                print("Waiting for confirmation...")

    conn = libvirt.open(None)
    if conn is None:
        print("🚨 Failed to open connection to the hypervisor 🚨")
        return

    try:
        dom = conn.lookupByName(vm_name)
    except libvirt.libvirtError:
        print(f"Domain {vm_name} not found.")
        return

    xml = dom.XMLDesc()
    tree = ET.fromstring(xml)

    # Remove ALL spice-related elements
    devices = tree.find("./devices")
    
    # Remove spice channels
    channels_to_remove = []
    for channel in tree.findall("./devices/channel"):
        channel_type = channel.get('type')
        target = channel.find('target')
        source = channel.find('source')
        
        # Check for spice-related channels
        if (channel_type == 'spicevmc' or 
            channel_type == 'spiceport' or
            (target is not None and 'spice' in target.get('name', '').lower()) or
            (source is not None and source.get('mode') == 'bind')):
            channels_to_remove.append(channel)
    
    for channel in channels_to_remove:
        print("Spice channel found. Removing...")
        devices.remove(channel)
    
    # Remove spice audio devices
    audio_devices_to_remove = []
    for audio in tree.findall("./devices/audio"):
        if audio.get('type') == 'spice':
            audio_devices_to_remove.append(audio)
    
    for audio in audio_devices_to_remove:
        print("Spice audio device found. Removing...")
        devices.remove(audio)
    
    # Remove spice USB redirection devices
    redirdev_to_remove = []
    for redirdev in tree.findall("./devices/redirdev"):
        if redirdev.get('type') == 'spicevmc':
            redirdev_to_remove.append(redirdev)
    
    for redirdev in redirdev_to_remove:
        print("Spice USB redirection device found. Removing...")
        devices.remove(redirdev)
    
    # Also remove any character devices that reference spicevmc
    chardevs_to_remove = []
    for chardev in tree.findall(".//chardev"):
        if chardev.get('type') == 'spicevmc':
            chardevs_to_remove.append(chardev)
    
    for chardev in chardevs_to_remove:
        print("Spice chardev found. Removing...")
        chardev.getparent().remove(chardev)

    #Removing existing graphic spice if present
    spice_graphics = tree.find("./devices/graphics[@type='spice']")
    if spice_graphics is not None:
        print("Found Spice graphics. Modifying to VNC...")
        
        # Modify the Spice graphics configuration to VNC
        spice_graphics.set("type", "vnc")
        spice_graphics.set("port", "-1")
        spice_graphics.set("autoport", "yes")
        spice_graphics.set("listen", "0.0.0.0")
        
        password = getpass.getpass("Enter VNC password (max 8 characters): 🔑").strip()[:8]
        spice_graphics.set("passwd", password)

        # Remove any existing listen elements and add new one
        for listen_elem in spice_graphics.findall("listen"):
            spice_graphics.remove(listen_elem)
        
        listen = ET.SubElement(spice_graphics, "listen")
        listen.set("type", "address")
        listen.set("address", "0.0.0.0")
    
    new_xml = ET.tostring(tree, encoding='unicode')
    
    # Debug: Print XML to see what's still there
    print("=== DEBUG: Checking for remaining spice references ===")
    if 'spice' in new_xml.lower():
        print("WARNING: Still found spice references in XML!")
        # Show lines containing spice
        for i, line in enumerate(new_xml.split('\n')):
            if 'spice' in line.lower():
                print(f"Line {i+1}: {line.strip()}")
    else:
        print("No spice references found in XML")
    print("=" * 55)
    
    conn.defineXML(new_xml)
    print(f"Updated display to VNC with password 🔑 for VM: {PURPLE}{vm_name}{RESET}")
    get_local_ip()