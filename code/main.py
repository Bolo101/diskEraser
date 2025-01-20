import os
from disk_erase import erase_disk
from disk_partition import partition_disk
from disk_format import format_disk
from utils import list_disks
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from time import sleep
import threading

class DiskProgress:
    def __init__(self, disk):
        self.disk = disk
        self.progress = 0
        self.lock = threading.Lock()

    def update_progress(self, value):
        with self.lock:
            self.progress = value

    def display(self):
        while self.progress < 100:
            sleep(0.5)
            with self.lock:
                print(f"{self.disk}: {self.progress:.2f}% complete", end='\r')

def select_disks():
    """
    Display a list of disks and allow the user to select multiple disks for processing.
    """
    list_disks()
    selected_disks = input(
        "Enter the disks to erase (comma-separated, e.g., sda,sdb): "
    ).strip()
    return [disk.strip() for disk in selected_disks.split(",") if disk.strip()]

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

def confirm_erasure(disk):
    """
    Display a confirmation prompt before erasing the disk.
    """
    while True:
        confirmation = input(
            f"Are you sure you want to securely erase {disk}? This cannot be undone. (y/n): "
        ).strip().lower()
        if confirmation in {"y", "n"}:
            return confirmation == "y"
        print("Invalid input. Please enter 'y' or 'n'.")

def get_disk_confirmations(disks):
    """
    Collect confirmations for all disks before proceeding with erasure.
    """
    confirmed_disks = []
    for disk in disks:
        if confirm_erasure(disk):
            confirmed_disks.append(disk)
        else:
            print(f"Skipping disk: {disk}")
    return confirmed_disks

def process_disk(disk, fs_choice, passes):
    """
    Erase, partition, and format a disk sequentially.
    """
    print(f"Starting operations on disk: {disk}")
    disk_progress = DiskProgress(disk)
    progress_thread = Thread(target=disk_progress.display)
    progress_thread.start()

    try:
        erase_disk(disk, passes, disk_progress.update_progress)
    except Exception as e:
        print(f"\nError erasing disk {disk}: {e}")
        return

    try:
        partition_disk(disk)
    except Exception as e:
        print(f"\nError partitioning disk {disk}: {e}")
        return

    try:
        format_disk(disk, fs_choice)
    except Exception as e:
        print(f"\nError formatting disk {disk}: {e}")
        return

    with disk_progress.lock:
        disk_progress.progress = 100

    progress_thread.join()
    print(f"\nCompleted operations on disk: {disk}")

def main(fs_choice=None, passes=7):
    disks = select_disks()
    if not disks:
        print("No disks selected. Exiting.")
        return

    confirmed_disks = get_disk_confirmations(disks)
    if not confirmed_disks:
        print("No disks were confirmed for erasure. Exiting.")
        return

    if not fs_choice:
        fs_choice = choose_filesystem()

    print("All disks confirmed for erasure. Starting the operation...\n")

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_disk, disk, fs_choice, passes) for disk in confirmed_disks]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing disk: {e}")

    print("All operations completed successfully.")

def sudo_check(args):
    if os.geteuid() != 0:
        print("This script must be run as root!")
    else:
        main(args.f, args.p)

def _parse_args():
    parser = ArgumentParser(description="Secure Disk Eraser Tool")
    parser.add_argument(
        '-f', 
        help="Filesystem type (ext4, ntfs, vfat)",
        choices=['ext4', 'ntfs', 'vfat'], 
        required=False
    )
    parser.add_argument(
        '-p',
        help="Number of random data passes",
        type=int,
        default=7,
        required=False
    )
    return parser.parse_args()

def app():
    args = _parse_args()
    sudo_check(args)

if __name__ == "__main__":
    app()
