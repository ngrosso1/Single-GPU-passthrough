import subprocess
from tkinter import Tk, filedialog
import sys
import urllib.request
import string
import os
import stat

RED = '\033[91m'   
RESET = '\033[0m'

def ensure_libvirt_access(path):
    """
    Ensure that 'libvirt-qemu' user can access the ISO file by setting
    execute permissions on all parent directories.
    """
    current_path = path
    while True:
        current_path = os.path.dirname(current_path)
        if current_path == "/" or current_path == "":
            break

        #Geting permissions
        st = os.stat(current_path)
        #Checking if 'others' have execute permissions
        if not (st.st_mode & stat.S_IXOTH):
            print(f"Adding execute permission to {current_path} for others...")
            os.chmod(current_path, st.st_mode | stat.S_IXOTH)
        else:
            #Permissions are already ok for this directory, moving up
            pass

def virtioDrivers(vm_name):
    have_iso = input("Do you have the VirtIO Drivers ISO file? (Y/n): ").strip().lower()

    if have_iso not in ("yes", "y", ""):
        #Download driver for the user
        download = input("Would you like to download the VirtIO ISO automatically (Y/n)?").strip().lower()
        if download in ("yes", "y", ""):
            download_url = "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso"
            download_path = f"/var/lib/libvirt/images/virtio-win.iso"
            print(f"Downloading VirtIO ISO to {download_path}...")

            try:
                urllib.request.urlretrieve(download_url, download_path)
                print("Download complete.")
                virtio_driver_file = download_path
            except Exception as e:
                print(f"Download failed: {RED}{e}{RESET}")
                sys.exit(1)
        #User downloads driver themselves
        else:
            print("Please download the VirtIO Drivers manually from here:")
            print("https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/")

    #First VirtIO disk
    print("Adding VirtIO storage device (0.1GB)...")
    first_disk_path = f"/var/lib/libvirt/images/{vm_name}_virtio1.qcow2"

    subprocess.run([
        "qemu-img", "create", "-f", "qcow2", first_disk_path, "0.1G"
    ], check=True)

    subprocess.run([
        "virsh", "attach-disk", vm_name,
        first_disk_path,
        "vdb",
        "--targetbus", "virtio",
        "--type", "disk",
        "--persistent"
    ], check=True)
    print("VirtIO storage device added.")

    #Second VirtIO Driver ISO
    print("Please select the VirtIO driver ISO file... 📂")
    root = Tk()
    root.withdraw()
    virtio_driver_file = filedialog.askopenfilename(
        title="Select VirtIO Driver ISO",
        filetypes=[("ISO files", "*.iso")]
    )

    if not virtio_driver_file:
        print("🚨 No file selected. Exiting 🚨")
        sys.exit(1)

    #Find available SATA target
    result = subprocess.run(["virsh", "domblklist", vm_name],
                            capture_output=True, text=True, check=True)
    used_targets = {
        line.split()[0] for line in result.stdout.splitlines()
        if line and not line.startswith("Target")
    }

    all_possible = [f"sd{letter}" for letter in string.ascii_lowercase[2:]]
    available_target = next((dev for dev in all_possible if dev not in used_targets), None)

    if not available_target:
        print("🚨 No available SATA target found. Exiting 🚨")
        sys.exit(1)

    print(f"Attaching VirtIO driver ISO as CD-ROM to {available_target}...")
    subprocess.run([
        "virsh", "attach-disk", vm_name,
        virtio_driver_file,
        available_target,
        "--targetbus", "sata",
        "--type", "cdrom",
        "--mode", "readonly",
        "--persistent"
    ], check=True)

    print("VirtIO driver CDROM added successfully ✅")

    while True:
        print("================================================================================")
        print("Install the VirtIO drivers in the Windows VM. This is found in the CD drive " \
        "that will be attached to the session.")
        print("The driver is called: virtio-win-gt-x64.msi")
        print("================================================================================")
        user_input = input("Did you install the VirtIO Driver on Windows (Y/n)?").strip().lower()

        if user_input in ("yes", "y", ""):
            print("Proceeding to the next function...")
            break
        elif user_input in ("no", "n"):
            sys.exit("Exiting the script...")
        else:
            print("Waiting for confirmation...")


def get_windows_iso():
    have_iso = input("Do you have the Windows ISO downloaded (Y/n)?: ").strip().lower()
    
    if have_iso not in ("yes", "y", ""):
        print("Please download the Windows ISO from the official Microsoft website:")
        print("https://www.microsoft.com/en-us/software-download/windows11")
        sys.exit("Exiting the script...")

    print("Please select the Windows ISO file... 📂")

    root = Tk()
    root.withdraw()
    iso_file = filedialog.askopenfilename(
        title="Select Windows ISO",
        filetypes=[("ISO files", "*.iso")]
    )

    if not iso_file:
        print("No file selected. Exiting.")
        sys.exit(1)
        
    ensure_libvirt_access(iso_file)
        
    try:
        current_permissions = os.stat(iso_file).st_mode
        os.chmod(iso_file, current_permissions | stat.S_IROTH)
        print(f"Permissions for {iso_file} updated to be world-readable.")
    except Exception as e:
        print(f"Failed to change permissions on ISO: {RED}{e}{RESET}")

    print(f"Selected ISO file: {iso_file}")
    return iso_file