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

def write_random_data(device, passes):
    """
    Overwrite the entire device with random data for the specified number of passes.
    """
    block_size = 4096  # Write in 4 KB blocks
    try:
        with open(f"/dev/{device}", "wb") as disk:
            disk_size = os.lseek(disk.fileno(), 0, os.SEEK_END)  # Get the disk size in bytes
            os.lseek(disk.fileno(), 0, os.SEEK_SET)  # Reset position to the start of the disk
            for pass_num in range(1, passes + 1):
                print(f"\nWriting random data pass {pass_num} to {device}...")
                written = 0
                while written < disk_size:
                    remaining = disk_size - written
                    to_write = min(block_size, remaining)
                    disk.write(os.urandom(to_write))
                    written += to_write
                    display_progress_bar(written, disk_size, pass_num, device)
                disk.flush()
                os.lseek(disk.fileno(), 0, os.SEEK_SET)  # Reset position after each pass
            print()  # Move to the next line after progress bar
    except Exception as e:
        print(f"\nError while writing random data to {device}: {e}")
        raise

def write_zero_data(device):
    """
    Overwrite the entire device with zeros.
    """
    block_size = 4096  # Write in 4 KB blocks
    try:
        with open(f"/dev/{device}", "wb") as disk:
            disk_size = os.lseek(disk.fileno(), 0, os.SEEK_END)  # Get the disk size in bytes
            os.lseek(disk.fileno(), 0, os.SEEK_SET)  # Reset position to the start of the disk

            print("\nWriting final zero pass to {device}...")
            written = 0
            while written < disk_size:
                remaining = disk_size - written
                to_write = min(block_size, remaining)
                disk.write(b"\x00" * to_write)
                written += to_write
                display_progress_bar(written, disk_size, "Final Zero", device)
            disk.flush()
            print()  # Move to the next line after progress bar
    except Exception as e:
        print(f"\nError while writing zero data to {device}: {e}")
        raise

def erase_disk(disk, passes):
    """
    Securely erase the entire disk by overwriting it with random data and zeros.
    """
    try:
        print(f"Erasing {disk} with multiple random data passes and a final zero pass for security...")

        write_random_data(disk, passes)

        write_zero_data(disk)

        print(f"Disk {disk} successfully erased with random data and zeros.")
    except Exception as e:
        print(f"Failed to erase disk {disk}: {e}")
