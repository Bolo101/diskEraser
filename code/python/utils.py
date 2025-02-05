import subprocess
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run_command(command_list):
    try:
        result = subprocess.run(command_list, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode('utf-8').strip()
    except FileNotFoundError:
        logging.error(f"Error: Command not found: {' '.join(command_list)}")
        sys.exit(2)
    except subprocess.CalledProcessError:
        logging.error(f"Error: Command execution failed: {' '.join(command_list)}")
        sys.exit(1)

def list_disks():
    logging.info("List of available disks:")
    try:
        output = run_command(["lsblk", "-d", "-o", "NAME,SIZE,TYPE"])
        if output:
            logging.info(output)
        else:
            logging.info("No disks detected. Ensure the program is run with appropriate permissions.")
    except FileNotFoundError:
        logging.error("Error: `lsblk` command not found. Install `util-linux` package.")
        sys.exit(2)
    except subprocess.CalledProcessError:
        logging.error("Error: Failed to retrieve disk information.")
        sys.exit(1)

def choose_filesystem():
    """
    Prompt the user to choose a filesystem.
    """
    while True:
        print("Choose a filesystem to format the disks:")
        print("1. NTFS")
        print("2. EXT4")
        print("3. VFAT")
        choice = input("Enter your choice (1, 2, or 3): ").strip()

        if choice == "1":
            return "ntfs"
        elif choice == "2":
            return "ext4"
        elif choice == "3":
            return "vfat"
        else:
            print("Invalid choice. Please select a correct option.")