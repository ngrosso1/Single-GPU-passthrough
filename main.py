import threading
import sys
import json
import os
import io
import time
import tty
import termios

from kernelUpdates import installations, failed2find, kernelBootChanges, reboot_system
from vmCreation import get_sys_info, create_vm, modify_storage_bus, update_display_to_vnc, cleanupDrives
from getISO import ensure_libvirt_access, virtioDrivers
from hooks import setup_libvirt_hooks, update_start_sh, update_revert_sh, add_gpu_passthrough_devices

PROGRESS_FILE = "progress.json"

def saveProgress(choice, step, data=None):
    progress = {"choice": choice, "step": step}
    if data:
        progress["data"] = data
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
        print(r" __  __  ____    ______   _____   __  __     ")
        print(r"/\ \/\ \/\  _`\ /\__  _\ /\  __`\/\ \/\ \    ")
        print(r"\ \ \ \ \ \ \L\_\/_/\ \/ \ \ \/\ \ \ \_\ \   ")
        print(r" \ \ \ \ \ \  _\/  \ \ \  \ \ \ \ \ \  _  \  ")
        print(r"  \ \ \_/ \ \ \/    \_\ \__\ \ \_\ \ \ \ \ \ ")
        print(r"   \ `\___/\ \_\    /\_____\\ \_____\ \_\ \_\ ")
        print(r"    `\/__/  \/_/    \/_____/ \/_____/\/_/\/_/")
        print(f"{RESET}")
        print("Welcome! What would you like to do?")
        print("\nUse ↑/↓ arrow keys to navigate, Enter to select:\n")
        
        # Print menu options
        for i, (text, _) in enumerate(options):
            if i == selected:
                print(f"  > {text}")
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

    def _execute_choice_1(self):
        self.log_message("Starting Step 1: Preparing Host System...")
        
        # Test message to verify logging is working
        self.log_message("DEBUG: Testing log output...")
        
        self.log_message("\n--- Running Installations ---")
        try:
            self._log_and_run(installations, self.distro)
            self.log_message("DEBUG: Installations completed")
        except Exception as e:
            self.log_message(f"ERROR in installations: {e}")
        
        self.log_message("\n--- Applying Kernel Boot Changes ---")
        try:
            self._log_and_run(kernelBootChanges, self.distro)
            self.log_message("DEBUG: Kernel boot changes completed")
        except Exception as e:
            self.log_message(f"ERROR in kernelBootChanges: {e}")
        
        self.log_message("\nHost preparation complete. A reboot is required.")
        self.log_message("You can reboot from your system menu, or run 'sudo reboot' in a terminal.")
        self.log_message("After rebooting, please run this application again and choose option 2.")

    def prepare_choice_2(self):
        """Placeholder for choice 2 implementation"""
        self.log_message("Executing Choice 2: Create VM & Passthrough GPU")
        # Add your implementation here
        pass

    def start_choice_3(self):
        """Placeholder for choice 3 implementation"""
        self.log_message("Executing Choice 3: Resume Previous Setup")
        progress = loadProgress()
        if progress:
            self.log_message(f"Found saved progress: {progress}")
        else:
            self.log_message("No saved progress found.")
        # Add your implementation here
        pass

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
            api._execute_choice_1()
            input("\nPress Enter to continue...")
        elif choice == "2":
            api.prepare_choice_2()
            input("\nPress Enter to continue...")
        elif choice == "3":
            api.start_choice_3()
            input("\nPress Enter to continue...")
        elif choice == "4":
            print("Exiting...")
            break

if __name__ == "__main__":
    #run_terminal_mode()
    failed2find()