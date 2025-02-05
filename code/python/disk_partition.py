import logging
from utils import run_command
import sys
from subprocess import CalledProcessError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def partition_disk(disk: str) -> None:
    logging.info(f"Partitioning disk {disk}...")

    try:
        run_command(["parted", f"/dev/{disk}", "--script", "mklabel", "gpt"])
        run_command(["parted", f"/dev/{disk}", "--script", "mkpart", "primary", "0%", "100%"])
        logging.info(f"Disk {disk} partitioned successfully.")
    except FileNotFoundError:
        logging.error(f"Error: `parted` command not found. Ensure it is installed.")
        sys.exit(2)
    except CalledProcessError:
        logging.error(f"Error: Failed to partition {disk}.")
        sys.exit(1)
