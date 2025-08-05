import subprocess
import os
import sys

RED = '\033[91m'   
RESET = '\033[0m'

def installations(distro):
    commands = {
        "pop": "apt install qemu-kvm libvirt-clients libvirt-daemon-system bridge-utils virt-manager ovmf openssh-server -y",
        "manjaro": "pacman -S virt-manager qemu vde2 ebtables iptables-nft nftables dnsmasq bridge-utils ovmf -y",
        "debian": "apt install qemu-kvm libvirt-clients libvirt-daemon-system bridge-utils virt-manager ovmf openssh-server -y",
        "opensuse" "zypper in libvirt libvirt-client libvirt-daemon virt-manager virt-install virt-viewer qemu qemu-kvm qemu-ovmf-x86_64 qemu-tools -y"
        "linuxmint": "apt install qemu-kvm libvirt-clients libvirt-daemon-system bridge-utils virt-manager ovmf openssh-server -y",
        "arch": "pacman -S virt-manager qemu vde2 ebtables iptables-nft nftables dnsmasq bridge-utils ovmf swtpm qemu-full -y",
        "ubuntu": "apt install qemu-kvm libvirt-clients libvirt-daemon-system bridge-utils virt-manager ovmf openssh-server -y",
        "fedora": "dnf5 install @virtualization",
        "endeavouros": "pacman -S virt-manager qemu vde2 ebtables iptables-nft nftables dnsmasq bridge-utils ovmf -y"
    }

    if distro in commands:
        print(f"Installing packages for {distro.capitalize()}...")
        try:
            subprocess.run(commands[distro], shell=True, check=True)
            print(f"Installation for {distro.capitalize()} completed.")
        except subprocess.CalledProcessError as e:
            print(f"🚨 Error 🚨 during installation: {RED}{e}{RESET}")
    else:
        print(f"No installation command found for {distro.capitalize()}.")

def checkCPU():
    #Checking if AMD or Intel
    isAMD = False
    isIntel = False
    with open("/proc/cpuinfo", "r") as f:
        cpuinfo = f.read()
        if "AuthenticAMD" in cpuinfo:
            isAMD = True
        elif "GenuineIntel" in cpuinfo:
            isIntel = True
    return isAMD, isIntel

def initramfsKernelBootChanges():
    #Appending VFIO modules to initramfs config
    vfio_modules = [
        "vfio",
        "vfio_iommu_type1",
        "vfio_pci",
        "vfio_virtqfd"
    ]
    modules_path = "/etc/initramfs-tools/modules"

    try:
        with open(modules_path, "a+") as f:
            f.seek(0)
            existing_lines = set(line.strip() for line in f)
            for module in vfio_modules:
                if module not in existing_lines:
                    f.write(f"{module}\n")
        print("VFIO modules added to /etc/initramfs-tools/modules.")
    except Exception as e:
        print(f"Failed to modify {modules_path}: {RED}{e}{RESET}")

    print("Regenerating initramfs...")
    subprocess.run(["update-initramfs", "-u"])
    print("Initramfs regeneration complete.")

def grubChanges():
    isAMD, isIntel = checkCPU()

    if isAMD:
        print("AMD CPU detected. Setting kernel options...")
        command = [
            "sed", "-i", 
            '/^GRUB_CMDLINE_LINUX="/ s/"$/ amd_iommu=on iommu=pt"/', 
            "/etc/sysconfig/grub"
        ]
        subprocess.run(command, check=True)
    elif isIntel:
        print("Intel CPU detected. Setting kernel options...")
        command = [
            "sed", "-i", 
            '/^GRUB_CMDLINE_LINUX="/ s/"$/ intel_iommu=on iommu=pt"/', 
            "/etc/sysconfig/grub"
        ]
        subprocess.run(command, check=True)
    else:
        print("Unknown CPU vendor. Skipping kernel options.")
    subprocess.run(["grub2-mkconfig", "-o", "/etc/grub2.cfg"])

def popChanges():
    isAMD, isIntel = checkCPU()
    if isAMD:
        print("AMD CPU detected. Setting kernel options...")
        subprocess.run(["kernelstub", "--add-options", "amd_iommu=on iommu=pt"])
    elif isIntel:
        print("Intel CPU detected. Setting kernel options...")
        subprocess.run(["kernelstub", "--add-options", "intel_iommu=on iommu=pt"])
    else:
        print("Unknown CPU vendor. Skipping kernel options.")

def dracutKernelBootChanges():
    command = [
        "bash", "-c", 
        'echo "add_driver+=\' vfio vfio_iommu_type1 vfio_pci vfio_virqfd \'" >> /etc/dracut.conf.d/local.conf'
    ]
    subprocess.run(command, check=True)
    
    command = [
        "sudo", "dracut", "-f", "--kver", subprocess.check_output(["uname", "-r"]).decode().strip()
    ]
    subprocess.run(command, check=True)

def sysChanges():
    isAMD, isIntel = checkCPU()
    iommu_option = None
    if isAMD:
        iommu_option = "amd_iommu=on iommu=pt"
    elif isIntel:
        iommu_option = "intel_iommu=on iommu=pt"

    if not iommu_option:
        print("Unknown CPU vendor. Skipping kernel option modification.")
        return

    # Get current kernel
    current_kernel = subprocess.check_output(["uname", "-r"], text=True).strip()

    # Determine current kernel flavor (e.g., linux-zen, linux)
    kernel_flavor = "linux"
    if "zen" in current_kernel:
        kernel_flavor = "linux-zen"
    elif "hardened" in current_kernel:
        kernel_flavor = "linux-hardened"
    elif "lts" in current_kernel:
        kernel_flavor = "linux-lts"

    # Look through entries to find correct non-fallback entry
    entries_dir = "/boot/loader/entries"
    matched_entry = None
    for entry in os.listdir(entries_dir):
        if entry.endswith(".conf") and kernel_flavor in entry and "fallback" not in entry:
            matched_entry = os.path.join(entries_dir, entry)
            break

    if not matched_entry:
        print(f"No matching boot entry found for kernel flavor: {kernel_flavor}")
        return

    print(f"Modifying kernel options in: {matched_entry}")

    # Read the entry and modify options line
    with open(matched_entry, "r") as f:
        lines = f.readlines()

    new_lines = []
    modified = False
    for line in lines:
        if line.startswith("options"):
            if iommu_option not in line:
                line = line.strip() + f" {iommu_option}\n"
                modified = True
        new_lines.append(line)

    if modified:
        with open(matched_entry, "w") as f:
            f.writelines(new_lines)
        print("IOMMU kernel options added successfully.")
    else:
        print("IOMMU options already present. No changes made.")

def kernelBootChanges(distro):
    if distro == "pop":
        print("Pop!_OS detected!")
        popChanges()
        initramfsKernelBootChanges()
    elif distro == "fedora":
        print("Fedora detected!")
        grubChanges()
        dracutKernelBootChanges()
    elif distro == "debian":
        print("Debian detected!")
        grubChanges()
        initramfsKernelBootChanges()
    elif distro == "linuxmint":
        print("Linux Mint detected!")
        grubChanges()
        initramfsKernelBootChanges()
    elif distro == "opensuse":
        print("openSUSE detected!")
        grubChanges()
        dracutKernelBootChanges()
    elif distro == "ubuntu":
        print("Ubuntu detected!")
        grubChanges()
        initramfsKernelBootChanges()
    elif distro == "arch":
        sysChanges()
        #initramfsKernelBootChanges()
    else:
        print("🚨 Distro not supported 🚨")
        sys.exit(1)

    print("================================================================================")
    print("REMINDER: After you have rebooted, open virt-manager, and then rerun this script as part 2")
    print("================================================================================")
    reboot_choice = input("Do you want to reboot now (Y/n)? ").strip().lower()
    if reboot_choice in ("yes", "y", ""):
        print("Rebooting system...")
        subprocess.run(["reboot"])
    else:
        print("System will not reboot now.")