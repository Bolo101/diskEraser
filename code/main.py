#!/usr/bin/env python3

import os
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from subprocess import CalledProcessError
from disk_erase import erase_disk, get_disk_serial, is_ssd
from disk_partition import partition_disk
from disk_format import format_disk
from utils import list_disks, choose_filesystem, run_command
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from log_handler import log_info, log_error, log_erase_operation
import threading
import logging

class DiskEraserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure Disk Eraser")
        self.root.geometry("600x500")
        self.disk_vars = {}
        self.filesystem_var = tk.StringVar(value="ext4")
        self.passes_var = tk.StringVar(value="5")
        self.disks = []
        self.disk_progress = {}
        
        # Check for root privileges
        if os.geteuid() != 0:
            messagebox.showerror("Error", "This program must be run as root!")
            root.destroy()
            sys.exit(1)
        
        self.create_widgets()
        self.refresh_disks()
    
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Secure Disk Eraser", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Left frame - Disk selection
        disk_frame = ttk.LabelFrame(main_frame, text="Select Disks to Erase")
        disk_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollable frame for disks
        self.disk_canvas = tk.Canvas(disk_frame)
        scrollbar = ttk.Scrollbar(disk_frame, orient="vertical", command=self.disk_canvas.yview)
        self.scrollable_disk_frame = ttk.Frame(self.disk_canvas)
        
        self.scrollable_disk_frame.bind(
            "<Configure>",
            lambda e: self.disk_canvas.configure(scrollregion=self.disk_canvas.bbox("all"))
        )
        
        self.disk_canvas.create_window((0, 0), window=self.scrollable_disk_frame, anchor="nw")
        self.disk_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.disk_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh button
        refresh_button = ttk.Button(disk_frame, text="Refresh Disks", command=self.refresh_disks)
        refresh_button.pack(pady=10)
        
        # Right frame - Options
        options_frame = ttk.LabelFrame(main_frame, text="Options")
        options_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5)
        
        # Filesystem options
        fs_label = ttk.Label(options_frame, text="Choose Filesystem:")
        fs_label.pack(anchor="w", pady=(10, 5))
        
        filesystems = [("ext4", "ext4"), ("NTFS", "ntfs"), ("FAT32", "vfat")]
        for text, value in filesystems:
            rb = ttk.Radiobutton(options_frame, text=text, value=value, variable=self.filesystem_var)
            rb.pack(anchor="w", padx=20)
        
        # Passes
        passes_frame = ttk.Frame(options_frame)
        passes_frame.pack(fill=tk.X, pady=10, padx=5)
        
        passes_label = ttk.Label(passes_frame, text="Number of passes:")
        passes_label.pack(side=tk.LEFT, padx=5)
        
        passes_entry = ttk.Entry(passes_frame, textvariable=self.passes_var, width=5)
        passes_entry.pack(side=tk.LEFT, padx=5)
        
        # Start button
        start_button = ttk.Button(options_frame, text="Start Erasure", command=self.start_erasure)
        start_button.pack(pady=20, padx=10, fill=tk.X)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress")
        progress_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, padx=10, pady=10)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        status_label.pack(pady=5)
        
        # Log display
        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=6, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def refresh_disks(self):
        # Clear existing disk checkboxes
        for widget in self.scrollable_disk_frame.winfo_children():
            widget.destroy()
        
        self.disk_vars = {}
        
        # Get list of disks
        self.disks = self._get_disks()
        
        if not self.disks:
            no_disk_label = ttk.Label(self.scrollable_disk_frame, text="No disks found")
            no_disk_label.pack(pady=10)
            return
            
        # Create checkboxes for each disk
        for disk in self.disks:
            frame = ttk.Frame(self.scrollable_disk_frame)
            frame.pack(fill=tk.X, pady=2)
            
            var = tk.BooleanVar()
            self.disk_vars[disk['device']] = var
            
            cb = ttk.Checkbutton(frame, variable=var)
            cb.pack(side=tk.LEFT)
            
            # Disk identifier label with size info
            device_name = disk['device'].replace('/dev/', '')
            disk_identifier = get_disk_serial(device_name)
            is_device_ssd = is_ssd(device_name)
            ssd_indicator = " (SSD)" if is_device_ssd else ""
            
            disk_label = ttk.Label(
                frame, 
                text=f"{disk_identifier}{ssd_indicator} ({disk['size']}) - {disk['model']}"
            )
            disk_label.pack(side=tk.LEFT, padx=5)
    
    def _get_disks(self):
        """
        Get list of available disks using lsblk with more robust parsing.
        """
        try:
            # Use more explicit column specification with -o option
            output = run_command(["lsblk", "-d", "-o", "NAME,SIZE,TYPE,MODEL", "-n"])
            
            # Parse the output from lsblk command
            disks = []
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                    
                # Split the line but preserve the model name which might contain spaces
                parts = line.strip().split(maxsplit=3)
                device = parts[0]
                
                # Ensure we have at least NAME, SIZE, and TYPE
                if len(parts) >= 3:
                    size = parts[1]
                    type_ = parts[2]
                    
                    # MODEL may be missing, set to "Unknown" if it is
                    model = parts[3] if len(parts) > 3 else "Unknown"
                    
                    # Only consider actual disks
                    if type_ == "disk":
                        disks.append({
                            "device": f"/dev/{device}",
                            "size": size,
                            "model": model
                        })
            
            # If no disks found, try an alternative approach
            if not disks:
                self.log("No disks found with primary method, trying alternative approach...")
                # Use simple lsblk command to get just the device names
                output = run_command(["lsblk", "-d", "-o", "NAME", "-n"])
                for line in output.strip().split('\n'):
                    if line.strip():
                        device = line.strip()
                        # Get size using a separate command
                        try:
                            size_output = run_command(["lsblk", "-d", "-o", "SIZE", "-n", f"/dev/{device}"])
                            size = size_output.strip() if size_output.strip() else "Unknown"
                        except:
                            size = "Unknown"
                        
                        disks.append({
                            "device": f"/dev/{device}",
                            "size": size,
                            "model": "Unknown"
                        })
            
            return disks
        except Exception as e:
            self.log(f"Error getting disk list: {str(e)}")
            return []

    def start_erasure(self):
        # Get selected disks
        selected_disks = [disk for disk, var in self.disk_vars.items() if var.get()]
        
        if not selected_disks:
            messagebox.showwarning("Warning", "No disks selected!")
            return
        
        # Get disk identifiers
        disk_identifiers = []
        for disk in selected_disks:
            disk_name = disk.replace('/dev/', '')
            disk_identifiers.append(get_disk_serial(disk_name))
        
        # Confirm erasure
        disk_list = "\n".join(disk_identifiers)
        if not messagebox.askyesno("Confirm Erasure", 
                                  f"WARNING: You are about to securely erase the following disks:\n\n{disk_list}\n\n"
                                  "This operation CANNOT be undone and ALL DATA WILL BE LOST!\n\n"
                                  "Are you absolutely sure you want to continue?"):
            return
        
        # Double-check confirmation with a different dialog
        if not messagebox.askyesno("FINAL WARNING", 
                                  "THIS IS YOUR FINAL WARNING!\n\n"
                                  "All selected disks will be completely erased.\n\n"
                                  "Do you want to proceed?"):
            return
        
        # Get options
        fs_choice = self.filesystem_var.get()
        
        try:
            passes = int(self.passes_var.get())
            if passes < 1:
                messagebox.showerror("Error", "Number of passes must be at least 1")
                return
        except ValueError:
            messagebox.showerror("Error", "Number of passes must be a valid integer")
            return
        
        # Start processing in a separate thread
        self.status_var.set("Starting erasure process...")
        threading.Thread(target=self.process_disks, args=(selected_disks, fs_choice, passes), daemon=True).start()
    
    def process_disks(self, disks, fs_choice, passes):
        self.log(f"Starting secure erasure of {len(disks)} disk(s) with {passes} passes")
        self.log(f"Selected filesystem: {fs_choice}")
        
        total_disks = len(disks)
        completed_disks = 0
        
        with ThreadPoolExecutor() as executor:
            # Create a dictionary to track progress for each disk
            self.disk_progress = {disk: 0 for disk in disks}
            
            # Submit all disk tasks
            futures = {executor.submit(self.process_single_disk, disk, fs_choice, passes): disk for disk in disks}
            
            # Process results as they complete
            for future in as_completed(futures):
                disk = futures[future]
                try:
                    future.result()
                    completed_disks += 1
                    self.update_progress((completed_disks / total_disks) * 100)
                    self.status_var.set(f"Completed {completed_disks}/{total_disks} disks")
                except Exception as e:
                    self.log(f"Error processing disk: {str(e)}")
        
        self.status_var.set("Erasure process completed")
        messagebox.showinfo("Complete", "Disk erasure operation has completed!")
    
    def process_single_disk(self, disk, fs_choice, passes):
        # Get the stable disk identifier before erasure
        disk_name = disk.replace('/dev/', '')
        try:
            # Get disk serial/identifier
            disk_serial = get_disk_serial(disk_name)
            self.log(f"Processing disk identifier: {disk_serial}")
        except Exception as e:
            self.log(f"Could not get disk identifier: {str(e)}")
            disk_serial = f"unknown_{disk_name}"
        
        try:
            self.status_var.set(f"Erasing {disk_serial}...")
            self.log(f"Starting secure erase with {passes} passes on disk ID: {disk_serial}")
            
            # Pass a log function for real-time progress
            erase_result = erase_disk(
                disk_name, 
                passes, 
                log_func=lambda msg: self.log(f"Shred progress: {msg}")
            )
            
            self.log(f"Erase completed on disk ID: {disk_serial}")
            
            # Partition the disk
            self.status_var.set(f"Partitioning {disk_serial}...")
            self.log(f"Creating partition on disk ID: {disk_serial}")
            partition_disk(disk_name)
            
            # Wait for the OS to recognize the new partition
            self.log("Waiting for partition to be recognized...")
            time.sleep(5)
            
            # Format the disk
            self.status_var.set(f"Formatting {disk_serial}...")
            self.log(f"Formatting disk ID: {disk_serial} with {fs_choice}")
            format_disk(disk_name, fs_choice)
            
            # Log the erase operation with the stable disk identifier and filesystem
            log_erase_operation(disk_serial, fs_choice)
            
            self.log(f"Completed operations on disk ID: {disk_serial}")
            
        except Exception as e:
            self.log(f"Error processing disk ID: {disk_serial}: {str(e)}")
            raise
    
    def update_progress(self, value):
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    def log(self, message):
        """Display messages in GUI log window, but avoid logging progress updates to file."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        # Update log in the GUI
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)

        # Avoid logging shred progress in the log file
        if "Shred progress" not in message:
            log_info(message)


def process_disk(disk: str, fs_choice: str, passes: int) -> None:
    try:
        disk_id = get_disk_serial(disk)
        log_info(f"Processing disk identifier: {disk_id}")
        
        # Erase, partition, and format the disk
        erase_disk(disk, passes)
        partition_disk(disk)
        time.sleep(5)  # Wait for the system to recognize the new partition
        format_disk(disk, fs_choice) 
        
        log_erase_operation(disk_id, fs_choice)
        
        log_info(f"Completed operations on disk ID: {disk_id}")
    except Exception as e:
        log_error(f"Error processing disk {disk}: {str(e)}")
        raise

def select_disks() -> list[str]:
    try:
        disk_list = list_disks()
        if not disk_list:
            log_info("No disks detected.")
            return []
            
    except Exception:
        pass
        
    selected_disks = input("Enter the disks to erase (comma-separated, e.g., sda,sdb): ").strip()
    return [disk.strip() for disk in selected_disks.split(",") if disk.strip()]

def confirm_erasure(disk: str) -> bool:
    while True:
        # Use disk identifier instead of device path
        disk_id = get_disk_serial(disk)
        confirmation = input(f"Are you sure you want to securely erase disk ID: {disk_id}? This cannot be undone. (y/n): ").strip().lower()
        if confirmation in {"y", "n"}:
            return confirmation == "y"
        log_info("Invalid input. Please enter 'y' or 'n'.")

def get_disk_confirmations(disks: list[str]) -> list[str]:
    return [disk for disk in disks if confirm_erasure(disk)]

def run_cli_mode(args):
    """Run the original command-line interface version"""
    try:
        fs_choice = args.filesystem
        passes = args.passes
        
        disks = select_disks()
        if not disks:
            log_info("No disks selected. Exiting.")
            return

        confirmed_disks = get_disk_confirmations(disks)
        if not confirmed_disks:
            log_info("No disks confirmed for erasure. Exiting.")
            return

        if not fs_choice:
            fs_choice = choose_filesystem()

        log_info("All disks confirmed. Starting operations...\n")

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_disk, disk, fs_choice, passes) for disk in confirmed_disks]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    log_error(f"Error processing disk: {str(e)}")

        log_info("All operations completed successfully.")
        
    except KeyboardInterrupt:
        log_error("\nTerminating program")
        sys.exit(1)

def run_gui_mode():
    """Run the GUI version"""
    root = tk.Tk()
    app = DiskEraserGUI(root)
    root.mainloop()

def main():
    # Parse command-line arguments
    parser = ArgumentParser(description="Secure Disk Eraser Tool")
    parser.add_argument('--cli', action='store_true', help="Run in command-line mode instead of GUI")
    parser.add_argument('-f', '--filesystem', choices=['ext4', 'ntfs', 'vfat'], help="Filesystem type to use")
    parser.add_argument('-p', '--passes', type=int, default=5, help="Number of passes for erasure")
    args = parser.parse_args()
    
    # Check for root privileges
    if os.geteuid() != 0:
        log_error("This program must be run as root!")
        sys.exit(1)
    
    # Choose mode based on arguments
    if args.cli:
        # Run the original CLI version
        run_cli_mode(args)
    else:
        # Run the GUI version
        run_gui_mode()

if __name__ == "__main__":
    main()