import os
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from subprocess import CalledProcessError, SubprocessError
from disk_erase import get_disk_serial, is_ssd
from utils import get_disk_list, get_base_disk
from disk_partition import partition_disk
from disk_format import format_disk
from concurrent.futures import ThreadPoolExecutor, as_completed
from log_handler import log_info, log_error, log_erase_operation, session_start, session_end, generate_session_pdf, generate_log_file_pdf
from disk_operations import get_active_disk, process_disk
import threading
from typing import Dict, List

class DiskEraserGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Secure Disk Eraser")
        self.root.geometry("600x500")
        # Set fullscreen mode to True
        self.root.attributes("-fullscreen", True)
        self.disk_vars: Dict[str, tk.BooleanVar] = {}
        self.filesystem_var = tk.StringVar(value="ext4")
        self.passes_var = tk.StringVar(value="5")
        self.erase_method_var = tk.StringVar(value="overwrite")  # Default to overwrite method
        self.crypto_fill_var = tk.StringVar(value="random")  # Default fill method for crypto erasure
        self.disks: List[Dict[str, str]] = []
        self.disk_progress: Dict[str, float] = {}
        self.active_disk = get_active_disk()
        
        # Track if active drive message was logged
        self.active_drive_logged = False
        
        # Start session logging - this will now automatically capture all log messages
        session_start()
        
        # Check for root privileges
        if os.geteuid() != 0:
            messagebox.showerror("Error", "This program must be run as root!")
            root.destroy()
            sys.exit(1)
        
        self.create_widgets()
        self.refresh_disks()
    
    def create_widgets(self) -> None:
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
        
        # Add disclaimer label at the bottom of disk frame
        self.disclaimer_var = tk.StringVar(value="")
        self.disclaimer_label = ttk.Label(disk_frame, textvariable=self.disclaimer_var, foreground="red", wraplength=250)
        self.disclaimer_label.pack(side=tk.BOTTOM, pady=5)
        
        # Add SSD warning disclaimer at the bottom of disk frame
        self.ssd_disclaimer_var = tk.StringVar(value="")
        self.ssd_disclaimer_label = ttk.Label(disk_frame, textvariable=self.ssd_disclaimer_var, foreground="blue", wraplength=250)
        self.ssd_disclaimer_label.pack(side=tk.BOTTOM, pady=5)
        
        # Refresh button
        refresh_button = ttk.Button(disk_frame, text="Refresh Disks", command=self.refresh_disks)
        refresh_button.pack(pady=10)
        
        # Right frame - Options
        options_frame = ttk.LabelFrame(main_frame, text="Options")
        options_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5)
        
        # Erasure method options
        method_label = ttk.Label(options_frame, text="Erasure Method:")
        method_label.pack(anchor="w", pady=(10, 5))
        
        methods = [("Standard Overwrite", "overwrite"), ("Cryptographic Erasure", "crypto")]
        for text, value in methods:
            rb = ttk.Radiobutton(options_frame, text=text, value=value, variable=self.erase_method_var, 
                                command=self.update_method_options)
            rb.pack(anchor="w", padx=20)
        
        # Passes (for overwrite method)
        self.passes_frame = ttk.Frame(options_frame)
        self.passes_frame.pack(fill=tk.X, pady=10, padx=5)
        
        passes_label = ttk.Label(self.passes_frame, text="Number of passes:")
        passes_label.pack(side=tk.LEFT, padx=5)
        
        passes_entry = ttk.Entry(self.passes_frame, textvariable=self.passes_var, width=5)
        passes_entry.pack(side=tk.LEFT, padx=5)
        
        # Crypto fill method options (for crypto method)
        self.crypto_fill_frame = ttk.LabelFrame(options_frame, text="Fill Method (Crypto)")
        
        fill_methods = [("Random Data", "random"), ("Zero Data", "zero")]
        for text, value in fill_methods:
            rb = ttk.Radiobutton(self.crypto_fill_frame, text=text, value=value, variable=self.crypto_fill_var)
            rb.pack(anchor="w", padx=20, pady=2)
        
        # Filesystem options
        fs_label = ttk.Label(options_frame, text="Choose Filesystem:")
        fs_label.pack(anchor="w", pady=(10, 5))
        
        filesystems = [("ext4", "ext4"), ("NTFS", "ntfs"), ("FAT32", "vfat")]
        for text, value in filesystems:
            rb = ttk.Radiobutton(options_frame, text=text, value=value, variable=self.filesystem_var)
            rb.pack(anchor="w", padx=20)
        
        # Exit fullscreen button
        exit_button = ttk.Button(options_frame, text="Exit Fullscreen", command=self.toggle_fullscreen)
        exit_button.pack(pady=5, padx=10, fill=tk.X)
        
        # Start button
        start_button = ttk.Button(options_frame, text="Start Erasure", command=self.start_erasure)
        start_button.pack(pady=10, padx=10, fill=tk.X)
        
        # Format only button
        format_button = ttk.Button(options_frame, text="Format Only (No Erase)", command=self.format_only)
        format_button.pack(pady=5, padx=10, fill=tk.X)

        # Print log buttons frame
        log_buttons_frame = ttk.Frame(options_frame)
        log_buttons_frame.pack(pady=5, padx=10, fill=tk.X)
        
        # Print session log button
        print_session_button = ttk.Button(log_buttons_frame, text="Print Session Log", 
                                        command=self.print_session_log)
        print_session_button.pack(side=tk.TOP, pady=5, padx=10, fill=tk.X, expand=True)
        
        # Print complete log button
        print_log_button = ttk.Button(log_buttons_frame, text="Print Complete Log", 
                                    command=self.print_complete_log)
        print_log_button.pack(side=tk.BOTTOM, pady=5, padx=10, fill=tk.X, expand=True)

        # Power off button
        poweroff_button = ttk.Button(options_frame, text="Power Off System", command=self.power_off_system)
        poweroff_button.pack(pady=5, padx=10, fill=tk.X)

        # Exit program button
        close_button = ttk.Button(options_frame, text="Exit", command=self.exit_application)
        close_button.pack(pady=5, padx=10, fill=tk.X)
        
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
        
        # Protocol for window close event
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        
        # Initial method options update
        self.update_method_options()

    def format_only(self) -> None:
        """Format selected disks without erasing them first."""
        # Get selected disks
        selected_disks = [disk for disk, var in self.disk_vars.items() if var.get()]
        
        if not selected_disks:
            messagebox.showwarning("Warning", "No disks selected!")
            return
        
        # Get disk identifiers
        disk_identifiers = []
        for disk in selected_disks:
            disk_name = disk.replace('/dev/', '')
            try:
                disk_identifier = get_disk_serial(disk_name)
            except (CalledProcessError, SubprocessError) as e:
                disk_identifier = f"{disk_name} (Serial unavailable)"
                error_msg = f"Error getting serial for {disk_name}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
            except FileNotFoundError as e:
                disk_identifier = f"{disk_name} (Serial command not found)"
                error_msg = f"Required command not found for getting serial of {disk_name}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
            except PermissionError as e:
                disk_identifier = f"{disk_name} (Permission denied)"
                error_msg = f"Permission denied getting serial for {disk_name}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
            except (IOError, OSError) as e:
                disk_identifier = f"{disk_name} (IO error)"
                error_msg = f"IO error getting serial for {disk_name}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
                
            disk_identifiers.append(disk_identifier)
        
        # Confirm formatting
        disk_list = "\n".join(disk_identifiers)
        fs_choice = self.filesystem_var.get()
        
        if not messagebox.askyesno("Confirm Format", 
                                f"WARNING: You are about to format the following disks as {fs_choice}:\n\n{disk_list}\n\n"
                                "All existing data will be lost!\n\n"
                                "Do you want to continue?"):
            return
        
        # Start formatting in a separate thread
        self.status_var.set("Starting format process...")
        try:
            threading.Thread(target=self.format_disks_thread, args=(selected_disks, fs_choice), daemon=True).start()
        except RuntimeError as e:
            error_msg = f"Error starting format thread: {str(e)}"
            messagebox.showerror("Thread Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except OSError as e:
            error_msg = f"System error starting format process: {str(e)}"
            messagebox.showerror("System Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")


    def format_disks_thread(self, disks, fs_choice):
        """Thread function to format disks."""
        start_msg = f"Starting format of {len(disks)} disk(s) as {fs_choice}"
        self.update_gui_log(start_msg)
        log_info(start_msg)
        
        total_disks = len(disks)
        completed_disks = 0
        
        try:
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(self.format_single_disk, disk, fs_choice): disk for disk in disks}
                
                for future in as_completed(futures):
                    disk = futures[future]
                    try:
                        future.result()
                        completed_disks += 1
                        self.update_progress((completed_disks / total_disks) * 100)
                        self.status_var.set(f"Formatted {completed_disks}/{total_disks} disks")
                    except (CalledProcessError, FileNotFoundError, PermissionError, OSError) as e:
                        error_msg = f"Error formatting disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except KeyboardInterrupt:
                        error_msg = "Format operation interrupted by user"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except MemoryError:
                        error_msg = f"Insufficient memory while formatting disk {disk}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except RuntimeError as e:
                        error_msg = f"Runtime error formatting disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except (ValueError, TypeError) as e:
                        error_msg = f"Invalid data error formatting disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
        
        except RuntimeError as e:
            error_msg = f"Error with thread pool executor during format: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except OSError as e:
            error_msg = f"System error during disk formatting: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except MemoryError:
            error_msg = "Insufficient memory for format thread pool operations"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        
        complete_msg = "Format process completed"
        self.status_var.set(complete_msg)
        log_info(complete_msg)
        try:
            messagebox.showinfo("Complete", "Disk formatting operation has completed!")
        except tk.TclError as e:
            error_msg = f"Error showing completion dialog: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)


    def format_single_disk(self, disk, fs_choice):
        """Format a single disk."""
        disk_name = disk.replace('/dev/', '')
        
        try:
            disk_id = get_disk_serial(disk_name)
            self.status_var.set(f"Formatting {disk_id}...")
            log_info(f"Formatting {disk_id} as {fs_choice}")
        except (CalledProcessError, SubprocessError) as e:
            self.update_gui_log(f"Error getting disk serial: {str(e)}")
            self.status_var.set(f"Formatting {disk_name}...")
            log_info(f"Formatting {disk_name} as {fs_choice}")
        except FileNotFoundError as e:
            self.update_gui_log(f"Required command not found: {str(e)}")
            self.status_var.set(f"Formatting {disk_name}...")
            log_info(f"Formatting {disk_name} as {fs_choice}")
        except PermissionError as e:
            self.update_gui_log(f"Permission error: {str(e)}")
            self.status_var.set(f"Formatting {disk_name}...")
            log_info(f"Formatting {disk_name} as {fs_choice}")
        except (IOError, OSError) as e:
            self.update_gui_log(f"OS/IO error: {str(e)}")
            self.status_var.set(f"Formatting {disk_name}...")
            log_info(f"Formatting {disk_name} as {fs_choice}")
        
        try:
            # Partition the disk first
            partition_disk(disk_name)
            self.update_gui_log(f"Partitioned {disk_name}")
            
            # Format the partition using the existing format_disk function
            format_disk(disk_name, fs_choice)
            self.update_gui_log(f"Successfully formatted {disk_name} as {fs_choice}")
            log_info(f"Successfully formatted {disk_name} as {fs_choice}")
            
        except CalledProcessError as e:
            error_msg = f"Command execution error formatting {disk_name}: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise
        except FileNotFoundError as e:
            error_msg = f"Required command not found for formatting {disk_name}: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise
        except PermissionError as e:
            error_msg = f"Permission denied formatting {disk_name}: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise
        except (IOError, OSError) as e:
            error_msg = f"IO/System error formatting {disk_name}: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise
        except MemoryError:
            error_msg = f"Insufficient memory while formatting {disk_name}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid parameter for formatting {disk_name}: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise
        except RuntimeError as e:
            error_msg = f"Runtime error formatting {disk_name}: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise


    def power_off_system(self) -> None:
        """Power off the system after confirmation."""
        import subprocess
        
        if not messagebox.askyesno("Confirm Power Off", 
                                "Are you sure you want to power off the system?\n\n"
                                "All unsaved work will be lost!"):
            return
        
        # Double confirmation
        if not messagebox.askyesno("FINAL WARNING", 
                                "This will shut down the computer immediately.\n\n"
                                "Do you want to proceed?"):
            return
        
        try:
            log_info("System power off initiated by user")
            self.update_gui_log("Powering off system...")
            session_end()
            
            # Give a moment for logs to be written
            import time
            time.sleep(1)
            
            # Execute poweroff command
            subprocess.run(["poweroff"], check=True)
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Error executing poweroff command: {str(e)}"
            messagebox.showerror("Power Off Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except FileNotFoundError:
            error_msg = "Poweroff command not found. Try 'shutdown -h now' manually."
            messagebox.showerror("Command Not Found", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except PermissionError:
            error_msg = "Permission denied. Root privileges required for poweroff."
            messagebox.showerror("Permission Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except (IOError, OSError) as e:
            error_msg = f"System error during poweroff: {str(e)}"
            messagebox.showerror("System Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except MemoryError:
            error_msg = "Insufficient memory to execute poweroff"
            messagebox.showerror("Memory Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid data during poweroff: {str(e)}"
            messagebox.showerror("Data Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
    
    def print_session_log(self) -> None:
        """Generate and save session log as PDF"""
        try:
            self.status_var.set("Generating session log PDF...")
            pdf_path = generate_session_pdf()
            
            success_msg = f"Session log PDF generated successfully!\nSaved to: {pdf_path}"
            messagebox.showinfo("PDF Generated", success_msg)
            self.update_gui_log(f"Session log PDF saved to: {pdf_path}")
            self.status_var.set("Session log PDF generated")
            
        except (ImportError, ModuleNotFoundError) as e:
            error_msg = f"PDF library not available: {str(e)}"
            messagebox.showerror("Library Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except (IOError, OSError) as e:
            error_msg = f"File system error generating session log PDF: {str(e)}"
            messagebox.showerror("File Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except PermissionError as e:
            error_msg = f"Permission denied when generating session log PDF: {str(e)}"
            messagebox.showerror("Permission Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except MemoryError:
            error_msg = "Insufficient memory to generate session log PDF"
            messagebox.showerror("Memory Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except (ValueError, TypeError) as e:
            error_msg = f"Data format error generating session log PDF: {str(e)}"
            messagebox.showerror("Data Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
    
    def print_complete_log(self) -> None:
        """Generate and save complete log file as PDF"""
        try:
            self.status_var.set("Generating complete log PDF...")
            pdf_path = generate_log_file_pdf()
            
            success_msg = f"Complete log PDF generated successfully!\nSaved to: {pdf_path}"
            messagebox.showinfo("PDF Generated", success_msg)
            self.update_gui_log(f"Complete log PDF saved to: {pdf_path}")
            self.status_var.set("Complete log PDF generated")
            
        except (ImportError, ModuleNotFoundError) as e:
            error_msg = f"PDF library not available: {str(e)}"
            messagebox.showerror("Library Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except (IOError, OSError) as e:
            error_msg = f"File system error generating complete log PDF: {str(e)}"
            messagebox.showerror("File Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except PermissionError as e:
            error_msg = f"Permission denied when generating complete log PDF: {str(e)}"
            messagebox.showerror("Permission Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except FileNotFoundError as e:
            error_msg = f"Log file not found when generating complete log PDF: {str(e)}"
            messagebox.showerror("File Not Found", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except MemoryError:
            error_msg = "Insufficient memory to generate complete log PDF"
            messagebox.showerror("Memory Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except (ValueError, TypeError) as e:
            error_msg = f"Data format error generating complete log PDF: {str(e)}"
            messagebox.showerror("Data Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
    
    def update_method_options(self) -> None:
        """Update UI based on the selected erasure method"""
        method = self.erase_method_var.get()

        # Always show the crypto fill options frame
        self.crypto_fill_frame.pack(fill=tk.X, pady=10, padx=5, after=self.passes_frame)

        # Enable or disable widgets inside crypto_fill_frame
        for child in self.crypto_fill_frame.winfo_children():
            try:
                if method == "crypto":
                    child.configure(state="normal")
                else:
                    child.configure(state="disabled")
            except tk.TclError as e:
                # Some widgets (like labels) may not support 'state'
                # Log the specific widget type that doesn't support state configuration
                widget_type = type(child).__name__
                self.update_gui_log(f"Widget {widget_type} does not support state configuration: {str(e)}")

        # Enable or disable passes entry
        for child in self.passes_frame.winfo_children():
            if isinstance(child, ttk.Entry):
                try:
                    if method == "crypto":
                        child.configure(state="disabled")
                    else:
                        child.configure(state="normal")
                except tk.TclError as e:
                    error_msg = f"Error configuring entry widget state: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)

    def exit_application(self) -> None:
        """Log and close the application when Exit is clicked"""
        exit_message = "Application closed by user via Exit button"
        log_info(exit_message)
        self.update_gui_log(exit_message)
        session_end()
        self.root.destroy()
    
    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode"""
        try:
            is_fullscreen = self.root.attributes("-fullscreen")
            self.root.attributes("-fullscreen", not is_fullscreen)
        except tk.TclError as e:
            error_msg = f"Error toggling fullscreen mode: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)

    def refresh_disks(self) -> None:
            # Clear existing disk checkboxes
            for widget in self.scrollable_disk_frame.winfo_children():
                widget.destroy()
            
            self.disk_vars = {}
            
            # Get list of disks using the common function
            try:
                self.disks = get_disk_list()
            except (CalledProcessError, SubprocessError) as e:
                error_msg = f"Error getting disk list: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
                self.disks = []
            except FileNotFoundError as e:
                error_msg = f"Required disk utility command not found: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
                self.disks = []
            except (IOError, OSError) as e:
                error_msg = f"System error accessing disk information: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
                self.disks = []
            
            if not self.disks:
                no_disk_label = ttk.Label(self.scrollable_disk_frame, text="No disks found")
                no_disk_label.pack(pady=10)
                self.disclaimer_var.set("")
                self.ssd_disclaimer_var.set("")
                self.update_gui_log("No disks found.")
                log_info("No disks found during disk refresh")
                return
            
            # Get active device(s) - now returns base disk names directly
            try:
                active_base_disks = get_active_disk()  # Returns list of base disk names like ['nvme0n1', 'sda']
            except (CalledProcessError, SubprocessError) as e:
                error_msg = f"Error detecting active disk: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
                active_base_disks = None
            except FileNotFoundError as e:
                error_msg = f"Required command not found for active disk detection: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
                active_base_disks = None
            except (IOError, OSError) as e:
                error_msg = f"System error detecting active disk: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
                active_base_disks = None
            
            # Convert to set for easier lookup
            active_physical_drives = set(active_base_disks) if active_base_disks else set()
            
            if active_base_disks:
                # Only log once per session
                if not self.active_drive_logged and active_physical_drives:
                    log_info(f"Active physical devices: {active_physical_drives}")
                    self.active_drive_logged = True
                
                # Set disclaimer if we found an active disk
                if active_physical_drives:
                    self.disclaimer_var.set(
                        "WARNING: Disk marked in red contains the active filesystem. "
                        "Erasing this disk will cause system failure and data loss!"
                    )
                else:
                    self.disclaimer_var.set("")
            else:
                self.disclaimer_var.set("")
            
            # Check if any SSDs are present and set the SSD disclaimer
            has_ssd = False
            for disk in self.disks:
                device_name = disk['device'].replace('/dev/', '')
                try:
                    if is_ssd(device_name):
                        has_ssd = True
                        break
                except (CalledProcessError, SubprocessError) as e:
                    error_msg = f"Error checking if {device_name} is SSD: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                except FileNotFoundError as e:
                    error_msg = f"Required command not found for SSD detection: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                    
            if has_ssd:
                self.ssd_disclaimer_var.set(
                    "WARNING: SSD devices detected. Multiple-pass erasure may damage SSDs "
                    "and NOT achieve secure data deletion due to SSD wear leveling. "
                    "For SSDs, use cryptographic erase mode instead."
                )
            else:
                self.ssd_disclaimer_var.set("")
            
            # Create checkboxes for each disk
            for disk in self.disks:
                # Create a container frame for each disk entry
                disk_entry_frame = ttk.Frame(self.scrollable_disk_frame)
                disk_entry_frame.pack(fill=tk.X, pady=5, padx=2)
                
                # Top row with checkbox
                checkbox_row = ttk.Frame(disk_entry_frame)
                checkbox_row.pack(fill=tk.X)
                
                var = tk.BooleanVar()
                self.disk_vars[disk['device']] = var
                
                cb = ttk.Checkbutton(checkbox_row, variable=var)
                cb.pack(side=tk.LEFT)
                
                # Get disk information
                device_name = disk['device'].replace('/dev/', '')
                
                # Get disk identifier with error handling
                try:
                    disk_identifier = get_disk_serial(device_name)
                except (CalledProcessError, SubprocessError) as e:
                    disk_identifier = f"{device_name} (Serial unavailable)"
                    error_msg = f"Error getting serial for {device_name}: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                except FileNotFoundError as e:
                    disk_identifier = f"{device_name} (Serial command not found)"
                    error_msg = f"Required command not found for getting serial of {device_name}: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                
                # Check if SSD with error handling
                try:
                    is_device_ssd = is_ssd(device_name)
                    ssd_indicator = " (Solid_state)" if is_device_ssd else " (Mechanical)"
                except (CalledProcessError, SubprocessError) as e:
                    ssd_indicator = " (Type unknown)"
                    error_msg = f"Error determining drive type for {device_name}: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                except FileNotFoundError as e:
                    ssd_indicator = " (Type detection unavailable)"
                    error_msg = f"Required command not found for drive type detection of {device_name}: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                
                # Determine if this is the active disk - now much simpler
                try:
                    base_device_name = get_base_disk(device_name)
                    is_active = base_device_name in active_physical_drives
                except (ValueError, TypeError) as e:
                    is_active = False
                    error_msg = f"Error determining base device for {device_name}: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                
                active_indicator = " (ACTIVE SYSTEM DISK)" if is_active else ""
                
                # Get disk label from the updated utils
                disk_label = disk.get('label', 'Unknown')
                label_indicator = f" [Label: {disk_label}]" if disk_label and disk_label != "No Label" else " [No Label]"
                
                # Set text color
                text_color = "red" if is_active else "blue" if 'is_device_ssd' in locals() and is_device_ssd else "black"
                
                # Create disk identifier label with wrapping
                disk_id_label = ttk.Label(
                    checkbox_row, 
                    text=f"{disk_identifier}{ssd_indicator}{active_indicator}{label_indicator}",
                    foreground=text_color,
                    wraplength=300
                )
                disk_id_label.pack(side=tk.LEFT, padx=5, fill=tk.X)
                
                # Create a second row for disk details that will wrap if needed
                details_row = ttk.Frame(disk_entry_frame)
                details_row.pack(fill=tk.X, padx=25)
                
                # Create disk details label
                disk_details_label = ttk.Label(
                    details_row,
                    text=f"Size: {disk['size']} - Model: {disk['model']}",
                    wraplength=300,
                    foreground=text_color
                )
                disk_details_label.pack(side=tk.LEFT, fill=tk.X)
                
                # Add a separator between disk entries for better visual separation
                ttk.Separator(self.scrollable_disk_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)  
        
    def start_erasure(self) -> None:
        # Get selected disks
        selected_disks = [disk for disk, var in self.disk_vars.items() if var.get()]
        
        if not selected_disks:
            messagebox.showwarning("Warning", "No disks selected!")
            return
        
        # Check if active disk is selected
        active_disk_selected = False
        for disk in selected_disks:
            disk_name = disk.replace('/dev/', '')
            if self.active_disk and any(active_disk in disk_name for active_disk in self.active_disk):
                active_disk_selected = True
                break

        # Additional warning for active disk
        if active_disk_selected:
            if not messagebox.askyesno("DANGER - SYSTEM DISK SELECTED", 
                                      "WARNING: You have selected the ACTIVE SYSTEM DISK!\n\n"
                                      "Erasing this disk will CRASH your system and cause PERMANENT DATA LOSS!\n\n"
                                      "Are you absolutely sure you want to continue?",
                                      icon="warning"):
                return
        
        # Get erasure method
        erase_method = self.erase_method_var.get()
        
        # Check if any SSDs are selected and show a warning for overwrite method
        ssd_selected = False
        if erase_method == "overwrite":
            for disk in selected_disks:
                disk_name = disk.replace('/dev/', '')
                try:
                    if is_ssd(disk_name):
                        ssd_selected = True
                        break
                except (CalledProcessError, SubprocessError) as e:
                    error_msg = f"Error checking SSD status for {disk_name}: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                except FileNotFoundError as e:
                    error_msg = f"SSD detection command not found for {disk_name}: {str(e)}"
                    self.update_gui_log(error_msg)
                    log_error(error_msg)
                    
            if ssd_selected:
                if not messagebox.askyesno("WARNING - SSD DEVICE SELECTED", 
                                          "WARNING: You have selected one or more SSD devices!\n\n"
                                          "Using multiple-pass erasure on SSDs can:\n"
                                          "• Damage the SSD by causing excessive wear\n"
                                          "• Fail to securely erase data due to SSD wear leveling\n"
                                          "• Not overwrite all sectors due to over-provisioning\n\n"
                                          "For SSDs, use cryptographic erasure \n\n"
                                          "Do you still want to continue?",
                                          icon="warning"):
                    return
        
        # Get disk identifiers and log each erasure operation
        disk_identifiers = []
        for disk in selected_disks:
            disk_name = disk.replace('/dev/', '')
            try:
                disk_identifier = get_disk_serial(disk_name)
            except (CalledProcessError, SubprocessError) as e:
                disk_identifier = f"{disk_name} (Serial unavailable)"
                error_msg = f"Error getting serial for logging: {disk_name}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
            except FileNotFoundError as e:
                disk_identifier = f"{disk_name} (Serial command not found)"
                error_msg = f"Serial detection command not found for logging: {disk_name}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
            
            disk_identifiers.append(disk_identifier)
            
            # Log detailed erasure operation for each disk
            fs_choice = self.filesystem_var.get()
            if erase_method == "crypto":
                fill_method = self.crypto_fill_var.get()
                method_description = f"cryptographic erasure with {fill_method} fill"
            else:
                method_description = f"standard {self.passes_var.get()}-pass overwrite"
            
            try:
                log_erase_operation(disk_identifier, fs_choice, method_description)
            except (IOError, OSError) as e:
                error_msg = f"Error logging erasure operation for {disk_identifier}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid data for logging erasure operation for {disk_identifier}: {str(e)}"
                self.update_gui_log(error_msg)
                log_error(error_msg)
        
        # Confirm erasure
        disk_list = "\n".join(disk_identifiers)
        
        # Add method-specific information to confirmation dialog
        if erase_method == "crypto":
            fill_method = self.crypto_fill_var.get()
            method_info = f"using cryptographic erasure with {fill_method} fill"
        else:
            method_info = f"with {self.passes_var.get()} pass overwrite"
        
        if not messagebox.askyesno("Confirm Erasure", 
                                  f"WARNING: You are about to securely erase the following disks {method_info}:\n\n{disk_list}\n\n"
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
        
        # For overwrite method, validate passes
        passes = 1  # Default value
        if erase_method == "overwrite":
            try:
                passes = int(self.passes_var.get())
                if passes < 1:
                    messagebox.showerror("Error", "Number of passes must be at least 1")
                    return
            except ValueError:
                messagebox.showerror("Error", "Number of passes must be a valid integer")
                return
            except OverflowError:
                messagebox.showerror("Error", "Number of passes is too large")
                return
        
        # Start processing in a separate thread
        self.status_var.set("Starting erasure process...")
        try:
            threading.Thread(target=self.progress_state, args=(selected_disks, fs_choice, passes, erase_method), daemon=True).start()
        except RuntimeError as e:
            error_msg = f"Error starting erasure thread: {str(e)}"
            messagebox.showerror("Thread Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
        except OSError as e:
            error_msg = f"System error starting erasure process: {str(e)}"
            messagebox.showerror("System Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")
    
    def progress_state(self, disks: List[str], fs_choice: str, passes: int, erase_method: str) -> None:
        if erase_method == "crypto":
            fill_method = self.crypto_fill_var.get()
            method_str = f"cryptographic erasure with {fill_method} fill"
        else:
            method_str = f"standard {passes}-pass overwrite"
        
        start_msg = f"Starting secure erasure of {len(disks)} disk(s) using {method_str}"
        fs_msg = f"Selected filesystem: {fs_choice}"
        
        self.update_gui_log(start_msg)
        log_info(start_msg)
        
        self.update_gui_log(fs_msg)
        log_info(fs_msg)
        
        total_disks = len(disks)
        completed_disks = 0
        
        try:
            with ThreadPoolExecutor() as executor:
                # Create a dictionary to track progress for each disk
                self.disk_progress = {disk: 0 for disk in disks}
                
                # Submit all disk tasks
                futures = {executor.submit(self.process_disk_wrapper, disk, fs_choice, passes, erase_method): disk for disk in disks}
                
                # Process results as they complete
                for future in as_completed(futures):
                    disk = futures[future]
                    try:
                        future.result()
                        completed_disks += 1
                        self.update_progress((completed_disks / total_disks) * 100)
                        self.status_var.set(f"Completed {completed_disks}/{total_disks} disks")
                    except (CalledProcessError, FileNotFoundError, PermissionError, OSError) as e:
                        error_msg = f"Error processing disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except KeyboardInterrupt:
                        error_msg = "Operation interrupted by user"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except MemoryError:
                        error_msg = f"Insufficient memory while processing disk {disk}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except RuntimeError as e:
                        error_msg = f"Runtime error processing disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
                    except (ValueError, TypeError) as e:
                        error_msg = f"Invalid data error processing disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
        
        except RuntimeError as e:
            error_msg = f"Error with thread pool executor: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except OSError as e:
            error_msg = f"System error during disk processing: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except MemoryError:
            error_msg = "Insufficient memory for thread pool operations"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        
        complete_msg = "Erasure process completed"
        self.status_var.set(complete_msg)
        log_info(complete_msg)
        try:
            messagebox.showinfo("Complete", "Disk erasure operation has completed!")
        except tk.TclError as e:
            error_msg = f"Error showing completion dialog: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
    
    def process_disk_wrapper(self, disk: str, fs_choice: str, passes: int, erase_method: str) -> None:
        """
        Wrapper for process_disk from disk_operations.py that updates GUI status
        """
        # Extract disk name (remove /dev/)
        disk_name = disk.replace('/dev/', '')
        
        # Get the disk ID for status updates
        try:
            disk_id = get_disk_serial(disk_name)
            self.status_var.set(f"Erasing {disk_id}...")
        except (CalledProcessError, SubprocessError) as e:
            self.update_gui_log(f"Error getting disk serial: {str(e)}")
            self.status_var.set(f"Erasing {disk_name}...")
        except FileNotFoundError as e:
            self.update_gui_log(f"Required command not found: {str(e)}")
            self.status_var.set(f"Erasing {disk_name}...")
        except PermissionError as e:
            self.update_gui_log(f"Permission error: {str(e)}")
            self.status_var.set(f"Erasing {disk_name}...")
        except OSError as e:
            self.update_gui_log(f"OS error: {str(e)}")
            self.status_var.set(f"Erasing {disk_name}...")
        
        # Define GUI log callback for process_disk (only for display, not session logs)
        def gui_log_callback(message: str) -> None:
            self.update_gui_log(message)
        
        try:
            # Call process_disk from disk_operations
            use_crypto = (erase_method == "crypto")
            crypto_fill = self.crypto_fill_var.get() if use_crypto else "random"
            process_disk(disk_name, fs_choice, passes, use_crypto, crypto_fill, log_func=gui_log_callback)
            
        except CalledProcessError as e:
            self.update_gui_log(f"Process error: {str(e)}")
            raise
        except FileNotFoundError as e:
            self.update_gui_log(f"Required command not found: {str(e)}")
            raise
        except PermissionError as e:
            self.update_gui_log(f"Permission error: {str(e)}")
            raise
        except OSError as e:
            self.update_gui_log(f"OS error: {str(e)}")
            raise
        except KeyboardInterrupt:
            self.update_gui_log("Operation interrupted by user")
            raise
        except MemoryError:
            self.update_gui_log(f"Insufficient memory while processing {disk_name}")
            raise
        except (ValueError, TypeError) as e:
            self.update_gui_log(f"Invalid parameter error for {disk_name}: {str(e)}")
            raise
        except RuntimeError as e:
            self.update_gui_log(f"Runtime error processing {disk_name}: {str(e)}")
            raise
    
    def update_progress(self, value: float) -> None:
        try:
            self.progress_var.set(value)
            self.root.update_idletasks()
        except tk.TclError as e:
            error_msg = f"Error updating progress bar: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid progress value: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
    
    def update_gui_log(self, message: str) -> None:
        """Update the GUI log window with a message (for display only)."""
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] {message}\n"

            # Update log in the GUI
            self.log_text.insert(tk.END, log_message)
            self.log_text.see(tk.END)
        except tk.TclError as e:
            # If GUI log fails, at least try to log the error
            error_msg = f"Error updating GUI log: {str(e)}"
            try:
                log_error(error_msg)
            except (IOError, OSError):
                # If even logging fails, we can't do much more
                pass
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid data for GUI log update: {str(e)}"
            try:
                log_error(error_msg)
            except (IOError, OSError):
                pass
        except OSError as e:
            error_msg = f"System error updating GUI log: {str(e)}"
            try:
                log_error(error_msg)
            except (IOError, OSError):
                pass

def run_gui_mode() -> None:
    """Run the GUI version"""
    try:
        root = tk.Tk()
        app = DiskEraserGUI(root)
        root.mainloop()
    except tk.TclError as e:
        print(f"GUI initialization error: {str(e)}")
        log_error(f"GUI initialization error: {str(e)}")
        sys.exit(1)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"Required GUI library not available: {str(e)}")
        log_error(f"Required GUI library not available: {str(e)}")
        sys.exit(1)
    except MemoryError:
        print("Insufficient memory to start GUI")
        log_error("Insufficient memory to start GUI")
        sys.exit(1)
    except OSError as e:
        print(f"System error starting GUI: {str(e)}")
        log_error(f"System error starting GUI: {str(e)}")
        sys.exit(1)