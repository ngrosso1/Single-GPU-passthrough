import threading
import sys
import json
import os
import io
import time
import tty
import termios

from kernelUpdates import installations, kernelBootChanges_no_prompt, kernelBootChanges_no_prompt1
from vmCreation import get_sys_info, create_vm, modify_storage_bus, update_display_to_vnc, cleanupDrives
from getISO import ensure_libvirt_access, virtioDrivers
from hooks import setup_libvirt_hooks, update_start_sh, update_revert_sh, add_gpu_passthrough_devices

PROGRESS_FILE = "progress.json"

def saveProgress(choice, step, data=None):
    progress = {"choice": choice, "step": step}
    if data:
        progress["data"] = data
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)

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
    return None

def get_key():
    """Get a single keypress from the terminal"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = sys.stdin.read(1)
        # Handle arrow keys (they send 3 characters: \x1b[A, \x1b[B, etc.)
        if key == '\x1b':
            key += sys.stdin.read(2)
        return key
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# ANSI color codes
BLUE = "\033[94m"
RESET = "\033[0m"

def show_menu(options, title="Menu"):
    """
    Display an interactive menu with arrow key navigation
    
    Args:
        options: List of tuples (display_text, return_value)
        title: Title to display above the menu (can be None to skip)
    
    Returns:
        The return_value of the selected option
    """
    selected = 0
    
    while True:
        # Clear screen and move cursor to top
        print("\033[2J\033[H", end="")

        # Print ASCII art header
        print(f"{BLUE}")
        print(r" _    ________________  __  __")
        print(r"| |  / / ____/  _/ __ \/ / / /")
        print(r"| | / / /_   / // / / / /_/ / ")
        print(r"| |/ / __/ _/ // /_/ / __  /  ")
        print(r"|___/_/   /___/\____/_/ /_/   ")
        print(f"{RESET}")
        print("Welcome! What would you like to do?")
        print("\nUse ↑/↓ arrow keys to navigate, Enter to select:\n")
        
        # Print menu options
        for i, (text, _) in enumerate(options):
            if i == selected:
                print(f"  > \033[4m{text}\033[0m")  # Underlined for selected item
            else:
                print(f"    {text}")
        
        # Get user input
        key = get_key()
        
        # Handle arrow keys
        if key == '\x1b[A':  # Up arrow
            selected = (selected - 1) % len(options)
        elif key == '\x1b[B':  # Down arrow
            selected = (selected + 1) % len(options)
        elif key == '\r' or key == '\n':  # Enter
            return options[selected][1]
        elif key == '\x03':  # Ctrl+C
            print("\n\nExiting...")
            sys.exit(0)

class Api:
    def __init__(self):
        self.distro = get_distro()

    def _run_in_thread(self, target, args=()):
        thread = threading.Thread(target=target, args=args)
        thread.daemon = True
        thread.start()

    def _log_and_run(self, func, *args):
        # Create a string buffer to capture output
        output_buffer = io.StringIO()
        
        # Redirect stdout to our buffer
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        
        try:
            # Run the function
            func(*args)
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            
            # Get the captured output
            output = output_buffer.getvalue()
            output_buffer.close()
            
            # Send each line to the log
            for line in output.splitlines():
                self.log_message(line)
                time.sleep(0.01)  # Prevents flooding

    def log_message(self, msg):
        # Ensure we have a string
        if not isinstance(msg, str):
            msg = str(msg)
        print(msg)

    def start_choice_1(self):
        self._run_in_thread(self._execute_choice_1)

    def _execute_choice_1(self):
        saveProgress(1, 1)
        self.log_message("Starting Step 1: Preparing Host System...")
        
        # Test message to verify logging is working
        self.log_message("DEBUG: Testing log output...")
        
        self.log_message("\n--- Running Installations ---")
        kernelBootChanges_no_prompt1(self.distro)
        sys.exit(0)
        try:
            self._log_and_run(installations, self.distro)
            self.log_message("DEBUG: Installations completed")
            saveProgress(1, 2)
        except Exception as e:
            self.log_message(f"ERROR in installations: {e}")
            return
        
        self.log_message("\n--- Applying Kernel Boot Changes ---")
        try:
            self._log_and_run(kernelBootChanges_no_prompt, self.distro)
            self.log_message("DEBUG: Kernel boot changes completed")
            saveProgress(1, 3)
        except Exception as e:
            self.log_message(f"ERROR in kernelBootChanges_no_prompt: {e}")
            return
        
        self.log_message("\nHost preparation complete. A reboot is required.")
        self.log_message("You can reboot from your system menu, or run 'sudo reboot' in a terminal.")
        self.log_message("After rebooting, please run this application again and choose option 2.")
        saveProgress(1, "complete")

    def start_choice_2(self):
        self._run_in_thread(self._execute_choice_2)

    def _execute_choice_2(self):
        saveProgress(2, 1)
        self.log_message("Starting Step 2: Creating VM and Setting Up GPU Passthrough...")
        
        self.log_message("\n--- Getting System Information ---")
        try:
            sys_info = get_sys_info()
            saveProgress(2, 2, {"sys_info": sys_info})
            self.log_message(f"System info gathered: {sys_info}")
        except Exception as e:
            self.log_message(f"ERROR getting system info: {e}")
            return
        
        self.log_message("\n--- Ensuring Libvirt Access ---")
        try:
            ensure_libvirt_access()
            saveProgress(2, 3)
        except Exception as e:
            self.log_message(f"ERROR ensuring libvirt access: {e}")
            return
        
        self.log_message("\n--- Downloading VirtIO Drivers ---")
        try:
            virtioDrivers()
            saveProgress(2, 4)
        except Exception as e:
            self.log_message(f"ERROR downloading virtio drivers: {e}")
            return
        
        self.log_message("\n--- Creating VM ---")
        try:
            vm_name = create_vm()
            saveProgress(2, 5, {"vm_name": vm_name})
            self.log_message(f"VM created: {vm_name}")
        except Exception as e:
            self.log_message(f"ERROR creating VM: {e}")
            return
        
        self.log_message("\n--- Modifying Storage Bus ---")
        try:
            modify_storage_bus(vm_name)
            saveProgress(2, 6)
        except Exception as e:
            self.log_message(f"ERROR modifying storage bus: {e}")
            return
        
        self.log_message("\n--- Updating Display to VNC ---")
        try:
            update_display_to_vnc(vm_name)
            saveProgress(2, 7)
        except Exception as e:
            self.log_message(f"ERROR updating display: {e}")
            return
        
        self.log_message("\n--- Cleaning Up Drives ---")
        try:
            cleanupDrives(vm_name)
            saveProgress(2, 8)
        except Exception as e:
            self.log_message(f"ERROR cleaning up drives: {e}")
            return
        
        self.log_message("\n--- Setting Up Libvirt Hooks ---")
        try:
            setup_libvirt_hooks()
            saveProgress(2, 9)
        except Exception as e:
            self.log_message(f"ERROR setting up hooks: {e}")
            return
        
        self.log_message("\n--- Updating start.sh Script ---")
        try:
            update_start_sh(vm_name)
            saveProgress(2, 10)
        except Exception as e:
            self.log_message(f"ERROR updating start.sh: {e}")
            return
        
        self.log_message("\n--- Updating revert.sh Script ---")
        try:
            update_revert_sh(vm_name)
            saveProgress(2, 11)
        except Exception as e:
            self.log_message(f"ERROR updating revert.sh: {e}")
            return
        
        self.log_message("\n--- Adding GPU Passthrough Devices ---")
        try:
            add_gpu_passthrough_devices(vm_name)
            saveProgress(2, 12)
        except Exception as e:
            self.log_message(f"ERROR adding GPU passthrough: {e}")
            return
        
        self.log_message("\n=== VM Setup Complete! ===")
        self.log_message(f"Your VM '{vm_name}' is ready with GPU passthrough configured.")
        clearProgress()

    def start_choice_3(self):
        self._run_in_thread(self._execute_choice_3)

    def _execute_choice_3(self):
        self.log_message("Checking for saved progress...")
        progress = loadProgress()
        
        if not progress:
            self.log_message("No saved progress found. Please start from the beginning.")
            return
        
        choice = progress.get("choice")
        step = progress.get("step")
        data = progress.get("data", {})
        
        self.log_message(f"Found saved progress: Choice {choice}, Step {step}")
        
        if choice == 1:
            self.log_message("Choice 1 (Host preparation) was in progress.")
            self.log_message("Please restart Choice 1 from the beginning as kernel changes cannot be partially resumed.")
            return
        
        if choice == 2:
            self.log_message("Resuming VM creation from saved checkpoint...")
            vm_name = data.get("vm_name", "win10")
            
            # Resume from the saved step
            if step < 5:
                self.log_message("Restarting from the beginning of VM creation...")
                self._execute_choice_2()
            elif step == 5:
                self.log_message(f"Resuming with VM: {vm_name}")
                self.log_message("\n--- Modifying Storage Bus ---")
                modify_storage_bus(vm_name)
                saveProgress(2, 6)
                # Continue with remaining steps...
                self._continue_choice_2_from_step_6(vm_name)
            else:
                self.log_message(f"Resuming from step {step}...")
                self._continue_choice_2_from_step(vm_name, step)

    def _continue_choice_2_from_step_6(self, vm_name):
        """Continue choice 2 from step 6 onwards"""
        self.log_message("\n--- Updating Display to VNC ---")
        update_display_to_vnc(vm_name)
        saveProgress(2, 7)
        
        self.log_message("\n--- Cleaning Up Drives ---")
        cleanupDrives(vm_name)
        saveProgress(2, 8)
        
        self.log_message("\n--- Setting Up Libvirt Hooks ---")
        setup_libvirt_hooks()
        saveProgress(2, 9)
        
        self.log_message("\n--- Updating start.sh Script ---")
        update_start_sh(vm_name)
        saveProgress(2, 10)
        
        self.log_message("\n--- Updating revert.sh Script ---")
        update_revert_sh(vm_name)
        saveProgress(2, 11)
        
        self.log_message("\n--- Adding GPU Passthrough Devices ---")
        add_gpu_passthrough_devices(vm_name)
        saveProgress(2, 12)
        
        self.log_message("\n=== VM Setup Complete! ===")
        self.log_message(f"Your VM '{vm_name}' is ready with GPU passthrough configured.")
        clearProgress()

    def _continue_choice_2_from_step(self, vm_name, step):
        """Continue from any step in choice 2"""
        # This is a simplified version - expand as needed
        if step >= 6:
            self._continue_choice_2_from_step_6(vm_name)

def run_terminal_mode():
    """Run the application in terminal mode"""
    api = Api()
    
    # Check for root privileges
    if os.geteuid() != 0:
        print("Root privileges are required. Please run with sudo.")
        sys.exit(1)
    
    while True:
        # Define menu options as (display_text, return_value) tuples
        menu_options = [
            ("Prepare Host System (Kernel Updates & Reboot)", "1"),
            ("Create VM & Passthrough GPU", "2"),
            ("Resume Previous Setup", "3"),
            ("Exit", "4")
        ]
        
        choice = show_menu(menu_options)
        
        # Clear screen for execution
        print("\033[2J\033[H", end="")
        
        if choice == "1":
            api.start_choice_1()
            # Wait for thread to complete
            time.sleep(1)
            input("\nPress Enter to continue...")
        elif choice == "2":
            api.start_choice_2()
            # Wait for thread to complete
            time.sleep(1)
            input("\nPress Enter to continue...")
        elif choice == "3":
            api.start_choice_3()
            # Wait for thread to complete
            time.sleep(1)
            input("\nPress Enter to continue...")
        elif choice == "4":
            print("Exiting...")
            break

if __name__ == "__main__":
    run_terminal_mode()