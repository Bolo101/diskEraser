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
        sys.exit(130)


def get_disk_filesystem(device: str) -> str:
    """
    Détecte le système de fichiers de la première partition d'un disque via lsblk.
    Retourne le type (ex. 'ext4', 'ntfs', 'vfat') ou '—' si non détecté.
    """
    try:
        output = run_command(["lsblk", "-o", "FSTYPE", "-n", f"/dev/{device}"])
        if output:
            fstypes = [line.strip() for line in output.split('\n') if line.strip()]
            if fstypes:
                return fstypes[0]
        return "—"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "—"


def get_disk_partition_table(device: str) -> str:
    """
    Détecte la table de partition d'un disque via lsblk.
    Retourne 'GPT', 'MBR', 'Aucune' ou 'Inconnue'.
    """
    try:
        output = run_command(["lsblk", "-o", "PTTYPE", "-n", f"/dev/{device}"])
        if output:
            pttypes = [line.strip().lower() for line in output.split('\n') if line.strip()]
            if pttypes:
                pttype = pttypes[0]
                if pttype == "gpt":
                    return "GPT"
                if pttype in ("dos", "msdos", "mbr"):
                    return "MBR"
                return pttype.upper()
        return "Aucune"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Inconnue"


def get_disk_label(device: str) -> str:
    """
    Get the label of a disk device using lsblk.
    Returns the label or "No Label" if none exists.
    """
    try:
        output = run_command(["lsblk", "-o", "LABEL", "-n", f"/dev/{device}"])
        if output and output.strip():
            labels = [line.strip() for line in output.split('\n') if line.strip()]
            if labels:
                return labels[0]
        return "No Label"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Unknown"


def list_disks() -> str:
    """
    Get a raw string output of available disks using lsblk command.
    Returns the output of the lsblk command or an empty string if no disks found.
    """
    try:
        output = run_command(["lsblk", "-d", "-o", "NAME,SIZE,TYPE,MODEL", "-n"])
        if output:
            return output
        else:
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


def get_disk_list() -> list[dict]:
    """
    Get list of available disks as structured data.
    Returns a list of dictionaries with disk information.
    Each dictionary contains: 'device', 'size', 'model', 'label',
    'filesystem' and 'partition_table'.
    """
    try:
        output = list_disks()

        if not output:
            logging.info("No disks found.")
            return []

        disks = []
        for line in output.strip().split('\n'):
            if not line.strip():
                continue

            parts = line.strip().split(maxsplit=3)
            device = parts[0]

            if len(parts) >= 2:
                size = parts[1]
                model = parts[3] if len(parts) > 3 else "Unknown"
                label = get_disk_label(device)
                filesystem = get_disk_filesystem(device)
                partition_table = get_disk_partition_table(device)

                disks.append({
                    "device": f"/dev/{device}",
                    "size": size,
                    "model": model,
                    "label": label,
                    "filesystem": filesystem,
                    "partition_table": partition_table,
                })
        return disks
    except FileNotFoundError as e:
        logging.error(f"Error: Command not found: {str(e)}")
        return []
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing command: {str(e)}")
        return []
    except (IndexError, ValueError) as e:
        logging.error(f"Error parsing disk information: {str(e)}")
        return []
    except KeyboardInterrupt:
        logging.error("Disk listing interrupted by user")
        return []


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
        except EOFError:
            logging.error("Input stream closed unexpectedly")
            print("\nInput stream closed unexpectedly")
            sys.exit(1)


def get_physical_drives_for_logical_volumes(active_devices: list) -> set:
    """
    Map logical volumes (LVM, etc.) to their underlying physical drives.
    
    Args:
        active_devices: List of active device paths (e.g., ['/dev/mapper/rocket--vg-root'])
    
    Returns:
        Set of physical drive names (e.g., {'nvme0n1', 'sda'})
    """
    if not active_devices:
        return set()

    physical_drives = set()

    try:
        disk_list = get_disk_list()
        physical_device_names = [disk['device'].replace('/dev/', '') for disk in disk_list]

        for physical_device in physical_device_names:
            try:
                output = run_command([
                    "lsblk",
                    f"/dev/{physical_device}",
                    "-o", "NAME",
                    "-l",
                    "-n"
                ])

                device_tree = []
                for line in output.strip().split('\n'):
                    if line.strip():
                        device_name = line.strip()
                        device_tree.append(f"/dev/{device_name}")
                        device_tree.append(device_name)

                for active_device in active_devices:
                    active_variants = [
                        active_device,
                        active_device.replace('/dev/', ''),
                        active_device.replace('/dev/mapper/', '')
                    ]

                    for variant in active_variants:
                        if variant in device_tree:
                            physical_drives.add(physical_device)
                            logging.info(f"Found active device '{active_device}' on physical drive '{physical_device}'")
                            break

                    if physical_device in physical_drives:
                        break

            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logging.error(f"Could not query device tree for {physical_device}: {str(e)}")
                continue

    except (AttributeError, TypeError) as e:
        logging.error(f"Error processing device data structures: {str(e)}")
    except MemoryError:
        logging.error("Insufficient memory to process logical volume mapping")
    except OSError as e:
        logging.error(f"OS error during logical volume mapping: {str(e)}")

    return physical_drives


def get_base_disk(device_name: str) -> str:
    """
    Extract base disk name from a device name.
    Examples:
        'nvme0n1p1' -> 'nvme0n1'
        'sda1' -> 'sda'
        'nvme0n1' -> 'nvme0n1'
    """
    import re

    try:
        if 'nvme' in device_name:
            match = re.match(r'(nvme\d+n\d+)', device_name)
            if match:
                return match.group(1)

        match = re.match(r'([a-zA-Z/]+[a-zA-Z])', device_name)
        if match:
            return match.group(1)

        return device_name

    except (re.error, AttributeError) as e:
        logging.error(f"Regex error processing device name '{device_name}': {str(e)}")
        return device_name
    except TypeError:
        logging.error(f"Invalid device name type: expected string, got {type(device_name)}")
        return str(device_name) if device_name is not None else ""