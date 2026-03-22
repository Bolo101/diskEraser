import logging
from utils import run_command
from subprocess import CalledProcessError
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def format_disk(disk: str, fs_choice: str) -> None:
    """
    Format a disk partition with the specified filesystem.
    Handles both NVMe and standard disk partition naming.
    """
    # Make sure we're working with just the device name without /dev/
    disk_name = disk.replace('/dev/', '')
    
    # Get the correct partition name (handles NVMe vs standard disks)
    from disk_partition import get_partition_name
    partition_name = get_partition_name(disk_name)
    partition = f"/dev/{partition_name}"
    
    # Wait briefly for the partition to be recognized by the system
    logging.info(f"Waiting for partition {partition} to be recognized...")
    time.sleep(2)
    
    try:
        if fs_choice == "ntfs":
            logging.info(f"Formatting {partition} as NTFS...")
            run_command(["mkfs.ntfs", "-f", partition])
        elif fs_choice == "ext4":
            logging.info(f"Formatting {partition} as EXT4...")
            run_command(["mkfs.ext4", "-F", partition])
        elif fs_choice == "vfat":
            logging.info(f"Formatting {partition} as VFAT...")
            run_command(["mkfs.vfat", "-F", "32", partition])
        else:
            logging.error(f"Unsupported filesystem: {fs_choice}")
            sys.exit(1)

        logging.info(f"Partition {partition} formatted successfully.")
    except FileNotFoundError:
        logging.error(f"Error: Filesystem utility not found for {fs_choice}. Ensure necessary tools are installed.")
        sys.exit(2)
    except CalledProcessError as e:
        logging.error(f"Error: Failed to format {partition}: {e}")
        sys.exit(1)