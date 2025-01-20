import os
import sys

def display_progress_bar(progress, total, pass_num, device):
    """
    Display a bash-style progress bar.
    """
    bar_length = 50  # Number of characters in the progress bar
    percent = (progress / total) * 100
    filled_length = int(bar_length * progress // total)
    bar = '=' * filled_length + '-' * (bar_length - filled_length)
    sys.stdout.write(f"\rPass {pass_num}: [{bar}] {percent:.2f}% {device}")
    sys.stdout.flush()

def write_random_data(device, passes, update_progress_callback=None):
    """
    Overwrite the entire device with random data for the specified number of passes.
    """
    block_size = 4096  # Write in 4 KB blocks
    try:
        with open(f"/dev/{device}", "wb") as disk:
            disk_size = os.lseek(disk.fileno(), 0, os.SEEK_END)  # Get the disk size in bytes
            os.lseek(disk.fileno(), 0, os.SEEK_SET)  # Reset position to the start of the disk

            for pass_num in range(1, passes + 1):
                written = 0
                while written < disk_size:
                    remaining = disk_size - written
                    to_write = min(block_size, remaining)
                    disk.write(os.urandom(to_write))
                    written += to_write
                    if update_progress_callback:
                        update_progress_callback((written / disk_size) * 100 / passes + (pass_num - 1) * (100 / passes))
                disk.flush()
                os.lseek(disk.fileno(), 0, os.SEEK_SET)  # Reset position after each pass
    except Exception as e:
        print(f"\nError while writing random data to {device}: {e}")
        raise

def write_zero_data(device, update_progress_callback=None):
    """
    Overwrite the entire device with zeros.
    """
    block_size = 4096  # Write in 4 KB blocks
    try:
        with open(f"/dev/{device}", "wb") as disk:
            disk_size = os.lseek(disk.fileno(), 0, os.SEEK_END)  # Get the disk size in bytes
            os.lseek(disk.fileno(), 0, os.SEEK_SET)  # Reset position to the start of the disk

            written = 0
            while written < disk_size:
                remaining = disk_size - written
                to_write = min(block_size, remaining)
                disk.write(b"\x00" * to_write)
                written += to_write
                if update_progress_callback:
                    update_progress_callback((written / disk_size) * 100)
            disk.flush()
    except Exception as e:
        print(f"\nError while writing zero data to {device}: {e}")
        raise

def erase_disk(disk, passes, update_progress_callback=None):
    """
    Securely erase the entire disk by overwriting it with random data and zeros.
    """
    try:
        write_random_data(disk, passes, update_progress_callback)
        write_zero_data(disk, update_progress_callback)
    except Exception as e:
        print(f"Failed to erase disk {disk}: {e}")
