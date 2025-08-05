from kernelUpdates import installations, kernelBootChanges
from vmCreation import get_vm_config, create_vm, modify_storage_bus, update_display_to_vnc, cleanupDrives
from getISO import get_windows_iso
from hooks import setup_libvirt_hooks, update_start_sh, update_revert_sh, add_gpu_passthrough_devices
import sys
import json
import os

PROGRESS_FILE = "progress.json"

def saveProgress(choice, step):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"choice": choice, "step": step}, f)

def loadProgress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return None

def clearProgress():
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

def get_distro():
    """Get the current distribution from /etc/os-release."""
    with open("/etc/os-release", "r") as f:
        for line in f:
            if line.lower().startswith("id="):
                return line.strip().split("=")[1].strip('"').lower()

def choice_1(distro):
    progress = loadProgress()
    start_from = progress["step"] if progress and progress["choice"] == "1" else None

    if start_from is None or start_from == "installations":
        installations(distro)
        saveProgress("1", "installations")
    if start_from is None or start_from == "kernelBootChanges":
        kernelBootChanges(distro)
        saveProgress("1", "kernelBootChanges")

    clearProgress()

def choice_2(distro):
    progress = loadProgress()
    step = progress["step"] if progress and progress["choice"] == "2" else None

    if step is None or step == "get_windows_iso":
        iso_file = get_windows_iso()
        saveProgress("2", "get_vm_config")
    
    if step is None or step == "get_vm_config":
        vm_name, memory, vcpus, diskSize, sockets, cores, threads = get_vm_config()
        saveProgress("2", "create_vm")
    
    if step is None or step == "create_vm":
        create_vm(iso_file, vm_name, memory, vcpus, diskSize, sockets, cores, threads, distro)
        saveProgress("2", "modify_storage_bus")
    
    if step is None or step == "modify_storage_bus":
        modify_storage_bus(vm_name)
        saveProgress("2", "update_display_to_vnc")
    
    if step is None or step == "update_display_to_vnc":
        update_display_to_vnc(vm_name, distro)
        saveProgress("2", "setup_libvirt_hooks")
    
    if step is None or step == "setup_libvirt_hooks":
        setup_libvirt_hooks(vm_name)
        saveProgress("2", "update_start_sh")
    
    if step is None or step == "update_start_sh":
        update_start_sh(vm_name)
        saveProgress("2", "update_revert_sh")

    if step is None or step == "update_revert_sh":
        update_revert_sh(vm_name)
        saveProgress("2", "add_gpu_passthrough_devices")

    if step is None or step == "add_gpu_passthrough_devices":
        add_gpu_passthrough_devices(vm_name)
        saveProgress("2", "cleanupDrives")
    
    if step is None or step == "cleanupDrives":
        cleanupDrives(vm_name)
    
    clearProgress()
    print("---  Script has completed!   ---")
    sys.exit(0)

def main():
    print("Welcome! What would you like to do?")

    while True:
        print("1) Run Kernel Boot Changes (1st time)")
        print("2) Run remaining operations (if kernel boot changes were done already)")
        print("3) Run a specific function (Only choose this if there was an issue in the 2nd part)")
        choice = input("Enter 1, 2, or 3: ").strip()

        if choice in ("1", "2", "3"):
            break
        else:
            print("Invalid choice. Please enter either 1, 2, or 3\n")

    distro = get_distro()
    if choice == "1":
        choice_1(distro)
    elif choice == "2":
        choice_2(distro)
    else:
        progress = loadProgress()
        if not progress:
            print("No previous progress to resume.")
        elif progress["choice"] == "1":
            choice_1(distro)
        elif progress["choice"] == "2":
            choice_2(distro)
        else:
            print("Unknown progress found.")
        sys.exit(0)

if __name__ == "__main__":
    main()
