import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

DEFAULT_VM_PATH = "/var/lib/libvirt/images"

def prompt_vm_file():
    if os.path.isdir(DEFAULT_VM_PATH):
        qcow2_files = [f for f in os.listdir(DEFAULT_VM_PATH) if f.endswith(".qcow2")]
    else:
        qcow2_files = []

    if not qcow2_files:
        print("No QCOW2 files found in default VM directory")
        manual = input("Do you want to manually enter a path? (y/n): ").strip().lower()
        if manual != 'y':
            sys.exit("Exiting...")
        vm_file = input("Enter the full path to the VM's qcow2 file: ").strip()
        if not os.path.isfile(vm_file):
            sys.exit(f"Error: {vm_file} does not exist or is not a file")
        return vm_file
    else:
        print("Available QCOW2 files:")
        for idx, file in enumerate(qcow2_files, start=1):
            print(f"{idx}. {file}")
        print(f"{len(qcow2_files)+1}. Enter manual path")

        while True:
            choice = input(f"Select a file (1-{len(qcow2_files)+1}): ").strip()
            if choice.isdigit():
                choice = int(choice)
                if 1 <= choice <= len(qcow2_files):
                    return os.path.join(DEFAULT_VM_PATH, qcow2_files[choice-1])
                elif choice == len(qcow2_files)+1:
                    vm_file = input("Enter the full path to the VM's qcow2 file: ").strip()
                    if not os.path.isfile(vm_file):
                        print(f"Error: {vm_file} does not exist or is not a file")
                        continue
                    return vm_file
            print("Invalid selection, try again")

def prompt_destination():
    dest = input("Enter the destination directory: ").strip()
    if not os.path.isdir(dest):
        sys.exit(f"Error: {dest} is not a valid directory")
    return dest

def copy_qcow2(src, dest):
    try:
        print(f"Copying {src} to {dest}...")
        shutil.copy2(src, dest)
    except Exception as e:
        sys.exit(f"Error copying file: {e}")

def remove_original(src):
    try:
        print(f"Removing original file {src}...")
        os.remove(src)
    except Exception as e:
        sys.exit(f"Error removing original file: {e}")

def update_xml(vm_name, new_path):
    xml_path = f"/etc/libvirt/qemu/{vm_name}.xml"
    if not os.path.isfile(xml_path):
        sys.exit(f"Error: XML file {xml_path} does not exist")

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for disk in root.findall("./devices/disk[@device='disk']/source"):
            disk.set("file", new_path)
        tree.write(xml_path)
        print(f"Updated XML file {xml_path} with new qcow2 path")
    except Exception as e:
        sys.exit(f"Error updating XML: {e}")

def set_permissions(file_path):
    try:
        print(f"Setting permissions for {file_path}...")
        subprocess.run(["sudo", "chown", "qemu:qemu", file_path], check=True)
        subprocess.run(["sudo", "chmod", "660", file_path], check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"Error setting permissions: {e}")

def set_external_drive_permissions(dest):
    if not os.path.abspath(dest).startswith(DEFAULT_VM_PATH):
        try:
            print(f"Setting permissions for external drive {dest}...")
            subprocess.run(["sudo", "chown", "qemu:qemu", dest], check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(f"Error setting external drive permissions: {e}")

def main_moving():
    vm_file = prompt_vm_file()
    vm_name = os.path.splitext(os.path.basename(vm_file))[0]
    dest_dir = prompt_destination()
    dest_file = os.path.join(dest_dir, os.path.basename(vm_file))

    copy_qcow2(vm_file, dest_file)
    remove_original(vm_file)
    update_xml(vm_name, dest_file)
    set_permissions(dest_file)
    set_external_drive_permissions(dest_dir)

    print("VM qcow2 file successfully moved and configured")

if __name__ == "__main__":
    main_moving()
