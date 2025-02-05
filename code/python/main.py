#!/usr/bin/env python3

import os
import sys
import logging
from disk_erase import erase_disk
from disk_partition import partition_disk
from disk_format import format_disk
from utils import list_disks, choose_filesystem
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def select_disks():
    list_disks()
    selected_disks = input("Enter the disks to erase (comma-separated, e.g., sda,sdb): ").strip()
    return [disk.strip() for disk in selected_disks.split(",") if disk.strip()]

def confirm_erasure(disk):
    while True:
        confirmation = input(f"Are you sure you want to securely erase {disk}? This cannot be undone. (y/n): ").strip().lower()
        if confirmation in {"y", "n"}:
            return confirmation == "y"
        logging.info("Invalid input. Please enter 'y' or 'n'.")

def get_disk_confirmations(disks):
    return [disk for disk in disks if confirm_erasure(disk)]

def process_disk(disk, fs_choice, passes):
    logging.info(f"Processing disk: {disk}")

    try:
        erase_disk(disk, passes)
        partition_disk(disk)
        format_disk(disk, fs_choice)
        logging.info(f"Completed operations on disk: {disk}")
    except (FileNotFoundError, subprocess.CalledProcessError):
        logging.info(f"Error processing disk {disk}.")
    
def main(fs_choice, passes):
    disks = select_disks()
    if not disks:
        logging.info("No disks selected. Exiting.")
        return

    confirmed_disks = get_disk_confirmations(disks)
    if not confirmed_disks:
        logging.info("No disks confirmed for erasure. Exiting.")
        return

    if not fs_choice:
        fs_choice = choose_filesystem()

    logging.info("All disks confirmed. Starting operations...\n")

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_disk, disk, fs_choice, passes) for disk in confirmed_disks]
        for future in as_completed(futures):
            future.result()

    logging.info("All operations completed successfully.")

def sudo_check(args):
    if os.geteuid() != 0:
        logging.error("This script must be run as root!")
        sys.exit(1)
    else:
        main(args.f, args.p)

def _parse_args():
    parser = ArgumentParser(description="Secure Disk Eraser Tool")
    parser.add_argument('-f', choices=['ext4', 'ntfs', 'vfat'], required=False)
    parser.add_argument('-p', type=int, default=5, required=False)
    return parser.parse_args()

def app():
    args = _parse_args()
    sudo_check(args)

if __name__ == "__main__":
    app()
