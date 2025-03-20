import subprocess
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run_command(command_list: list[str]) -> str:
    try:
        result = subprocess.run(command_list, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode('utf-8').strip()
    except FileNotFoundError:
        logging.error(f"Error: Command not found: {' '.join(command_list)}")
        sys.exit(2)
    except subprocess.CalledProcessError:
        logging.error(f"Error: Command execution failed: {' '.join(command_list)}")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.error("Operation interrupted by user (Ctrl+C)")
        print("\nOperation interrupted by user (Ctrl+C)")
        sys.exit(130)  # Standard exit code for SIGINT

def list_disks() -> str:
    print("List of available disks:")
    try:
        # Use more explicit column specification with -o option and -n to skip header
        output = run_command(["lsblk", "-d", "-o", "NAME,SIZE,TYPE,MODEL", "-n"])
        if output:
            return output
        else:
            # Fallback to a simpler command if the first one returned no results
            output = run_command(["lsblk", "-d", "-o", "NAME", "-n"])
            if output:
                logging.info(output)
                return output
            else:
                logging.info("No disks detected. Ensure the program is run with appropriate permissions.")
                return ""
    except FileNotFoundError:
        logging.error("Error: `lsblk` command not found. Install `util-linux` package.")
        sys.exit(2)
    except subprocess.CalledProcessError:
        logging.error("Error: Failed to retrieve disk information.")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.error("Disk listing interrupted by user (Ctrl+C)")
        print("\nDisk listing interrupted by user (Ctrl+C)")
        sys.exit(130)

def choose_filesystem() -> str:
    """
    Prompt the user to choose a filesystem.
    """
    while True:
        try:
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
                logging.error("Invalid choice. Please select a correct option.")
        except KeyboardInterrupt:
            logging.error("Filesystem selection interrupted by user (Ctrl+C)")
            print("\nFilesystem selection interrupted by user (Ctrl+C)")
            sys.exit(130)