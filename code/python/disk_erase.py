import subprocess
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def is_ssd(device: str) -> bool:
    try:
        output = subprocess.run(
            ["cat", f"/sys/block/{device}/queue/rotational"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return output.stdout.decode().strip() == "0"
    except FileNotFoundError:
        logging.error(f"SSD check failed: {device} not found.")
        sys.exit(2)
    except subprocess.SubprocessError:
        logging.error(f"Error executing subprocess for SSD check on {device}.")
        sys.exit(1)
    return False

def erase_disk(device: str, passes: int) -> None:
    try:
        # Type-casting arguments to ensure correct types
        device = str(device)
        passes = int(passes)

        if is_ssd(device):
            logging.info(f"Warning: {device} appears to be an SSD. Use `hdparm` for secure erase.")
            return

        logging.info(f"Erasing {device} using shred with {passes} passes...")

        for i in range(1, passes + 1):
            logging.info(f"Pass {i} of {passes} is being processed...")
            subprocess.run(["shred", "-n", "1", "-z", f"/dev/{device}"], check=True)

        logging.info(f"Wiping partition table of {device} using dd...")
        subprocess.run(["dd", "if=/dev/zero", f"of=/dev/{device}", "bs=1M", "count=10"], check=True)

        logging.info(f"Disk {device} successfully erased.")
    except FileNotFoundError:
        logging.error(f"Error: Required command not found.")
        sys.exit(2)
    except subprocess.CalledProcessError:
        logging.error(f"Error: Failed to erase {device} using shred or dd.")
        sys.exit(1)
