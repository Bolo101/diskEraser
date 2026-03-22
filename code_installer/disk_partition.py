import logging
from utils import run_command
import sys
from subprocess import CalledProcessError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_partition_name(disk_name: str) -> str:
    """
    Get the correct partition name for a disk.
    Handles NVMe (nvme0n1 -> nvme0n1p1) and standard disks (sda -> sda1).
    """
    # Remove /dev/ if present
    disk_name = disk_name.replace('/dev/', '')
    
    # Check if it's an NVMe drive
    if 'nvme' in disk_name:
        # NVMe drives use 'p' before partition number
        return f"{disk_name}p1"
    else:
        # Standard drives append partition number directly
        return f"{disk_name}1"


def partition_disk(disk: str) -> None:
    """
    Partition disk with proper NVMe support.
    """
    print(f"Partitioning disk {disk}...")

    try:
        # Make sure we're working with just the device name without /dev/
        disk_name = disk.replace('/dev/', '')
        
        # Create a new GPT partition table
        run_command(["parted", f"/dev/{disk_name}", "--script", "mklabel", "gpt"])
        
        # Create a primary partition using 100% of disk space
        run_command(["parted", f"/dev/{disk_name}", "--script", "mkpart", "primary", "0%", "100%"])
        
        # Inform the kernel of partition table changes
        run_command(["partprobe", f"/dev/{disk_name}"])
        
        # Wait a moment for the partition to be recognized
        import time
        time.sleep(2)
        
        print(f"Disk {disk_name} partitioned successfully.")
        
    except FileNotFoundError:
        logging.error(f"Error: `parted` command not found. Ensure it is installed.")
        sys.exit(2)
    except CalledProcessError as e:
        logging.error(f"Error: Failed to partition {disk}: {e}")
        sys.exit(1)