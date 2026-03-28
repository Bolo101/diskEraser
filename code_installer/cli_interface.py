import sys
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from subprocess import CalledProcessError, SubprocessError
from disk_erase import get_disk_serial, is_ssd
from disk_operations import get_active_disk, process_disk
from utils import get_disk_list, choose_filesystem, get_base_disk
from log_handler import (log_info, log_error, log_erase_operation, 
                        generate_session_pdf, generate_log_file_pdf, 
                        session_start, session_end, get_current_session_logs)

def print_disk_details(disk):
    """Print detailed information about a disk."""
    try:
        disk_id = get_disk_serial(disk)
        is_disk_ssd = is_ssd(disk)
        
        # Get active disks - now returns base disk names directly
        try:
            active_base_disks = get_active_disk()  # Returns list of base disk names like ['nvme0n1', 'sda']
        except (CalledProcessError, SubprocessError) as e:
            print(f"Error detecting active disk: {str(e)}")
            log_error(f"Error detecting active disk: {str(e)}")
            active_base_disks = None
        except FileNotFoundError as e:
            print(f"Required command not found for active disk detection: {str(e)}")
            log_error(f"Required command not found for active disk detection: {str(e)}")
            active_base_disks = None
        except (IOError, OSError) as e:
            print(f"System error detecting active disk: {str(e)}")
            log_error(f"System error detecting active disk: {str(e)}")
            active_base_disks = None
        
        # Convert to set for easier lookup
        active_physical_drives = set(active_base_disks) if active_base_disks else set()
        
        # Get disk information from get_disk_list function including label
        disk_size = "Unknown"
        disk_model = "Unknown"
        disk_label = "No Label"
        available_disks = get_disk_list()
        for available_disk in available_disks:
            if available_disk["device"] == f"/dev/{disk}":
                disk_size = available_disk["size"]
                disk_model = available_disk.get("model", "Unknown")
                disk_label = available_disk.get("label", "No Label")
                break
        
        # Determine if this is the active disk - now much simpler
        try:
            base_device_name = get_base_disk(disk)
            is_active = base_device_name in active_physical_drives
        except (ValueError, TypeError) as e:
            is_active = False
            print(f"Error determining base device for {disk}: {str(e)}")
            log_error(f"Error determining base device for {disk}: {str(e)}")
        
        print(f"Disk: /dev/{disk}")
        print(f"  Serial/ID: {disk_id}")
        print(f"  Size: {disk_size}")
        print(f"  Model: {disk_model}")
        print(f"  Label: {disk_label}")
        print(f"  Type: {'Solid_state' if is_disk_ssd else 'Mechanical'}")
        print(f"  Status: {'ACTIVE SYSTEM DISK - DANGER!' if is_active else 'Safe to erase'}")
        
        if is_disk_ssd:
            print("  WARNING: This is an SSD device. Multiple-pass secure erasure:")
            print("    • May damage the SSD by causing excessive wear")
            print("    • May not securely erase all data due to SSD wear leveling")
            print("    • May not overwrite all sectors due to over-provisioning")
            print("    • For SSDs, cryptographic erasure is recommended")
        
        if is_active:
            print("  DANGER: This is the ACTIVE SYSTEM DISK! Erasing it will make your system unusable.")
            print("          The system will crash if you proceed with erasing this disk.")
            
        return disk_id, is_disk_ssd, is_active
    except (SubprocessError, FileNotFoundError) as e:
        print(f"Error getting disk details: {str(e)}")
        log_error(f"Error getting disk details for {disk}: {str(e)}")
        return f"unknown_{disk}", False, False
    except (OSError, IOError) as e:
        print(f"System error getting disk details: {str(e)}")
        log_error(f"System error getting disk details for {disk}: {str(e)}")
        return f"unknown_{disk}", False, False
    except (AttributeError, KeyError, IndexError) as e:
        print(f"Data structure error getting disk details: {str(e)}")
        log_error(f"Data structure error getting disk details for {disk}: {str(e)}")
        return f"unknown_{disk}", False, False
    except (TypeError, ValueError) as e:
        print(f"Data type error getting disk details: {str(e)}")
        log_error(f"Data type error getting disk details for {disk}: {str(e)}")
        return f"unknown_{disk}", False, False

def select_disks() -> list[str]:
    """
    Let the user select disks to erase from the command line, with detailed information.
    """
    try:
        available_disks = get_disk_list()
        disk_names = [disk["device"].replace("/dev/", "") for disk in available_disks]

        # Get active disks - now returns base disk names directly
        try:
            active_base_disks = get_active_disk()
        except (CalledProcessError, SubprocessError) as e:
            print(f"Error detecting active disk: {str(e)}")
            log_error(f"Error detecting active disk: {str(e)}")
            active_base_disks = None
        except FileNotFoundError as e:
            print(f"Required command not found for active disk detection: {str(e)}")
            log_error(f"Required command not found for active disk detection: {str(e)}")
            active_base_disks = None
        except (IOError, OSError) as e:
            print(f"System error detecting active disk: {str(e)}")
            log_error(f"System error detecting active disk: {str(e)}")
            active_base_disks = None
        
        # Convert to set for easier lookup
        active_physical_drives = set(active_base_disks) if active_base_disks else set()

        # Display summary table first
        print("\n" + "=" * 80)
        print("                          AVAILABLE DISKS SUMMARY")
        print("=" * 80)
        print(f"{'Device':<12} {'Size':<8} {'Model':<20} {'Label':<15} {'Type':<12} {'Status'}")
        print("-" * 80)
        
        for disk in disk_names:
            try:
                disk_id = get_disk_serial(disk)
                is_disk_ssd = is_ssd(disk)
                
                # Get disk information including label
                disk_size = "Unknown"
                disk_model = "Unknown"
                disk_label = "No Label"
                for available_disk in available_disks:
                    if available_disk["device"] == f"/dev/{disk}":
                        disk_size = available_disk["size"]
                        disk_model = available_disk.get("model", "Unknown")
                        disk_label = available_disk.get("label", "No Label")
                        break
                
                # Determine if this is the active disk - now much simpler
                try:
                    base_device_name = get_base_disk(disk)
                    is_active = base_device_name in active_physical_drives
                except (ValueError, TypeError) as e:
                    is_active = False
                    print(f"Error determining base device for {disk}: {str(e)}")
                    log_error(f"Error determining base device for {disk}: {str(e)}")
                
                # Truncate long names for table display
                model_display = (disk_model[:18] + "..") if len(disk_model) > 20 else disk_model
                label_display = (disk_label[:13] + "..") if len(disk_label) > 15 else disk_label
                
                disk_type = "SSD" if is_disk_ssd else "HDD"
                status = "ACTIVE!" if is_active else "Safe"
                
                print(f"{disk:<12} {disk_size:<8} {model_display:<20} {label_display:<15} {disk_type:<12} {status}")
                
            except (SubprocessError, OSError, IOError) as e:
                print(f"{disk:<12} System error retrieving disk information: {str(e)}")
            except (FileNotFoundError, PermissionError) as e:
                print(f"{disk:<12} Access error retrieving disk information: {str(e)}")
            except (AttributeError, KeyError, IndexError, TypeError, ValueError) as e:
                print(f"{disk:<12} Data error retrieving disk information: {str(e)}")
        
        print("-" * 80)

        # Then iterate over disk_names for detailed view
        print("\n" + "=" * 60)
        print("                    DETAILED DISK INFORMATION")
        print("=" * 60)
        
        for disk in disk_names:
            print("\n" + "-" * 50)
            print_disk_details(disk)
            
        print("\n" + "-" * 50)
        print("\nWARNING: This tool will COMPLETELY ERASE selected disks. ALL DATA WILL BE LOST!")
        print("WARNING: If any of these disks are SSDs, using multiple passes may damage the SSD.")
        print("For SSDs, cryptographic erasure is recommended.\n")
        
        selected_disks = input("Enter the disks to erase (comma-separated, e.g., sda,sdb): ").strip()
        disk_names = [disk.strip() for disk in selected_disks.split(",") if disk.strip()]
        
        valid_disks = []
        for disk in disk_names:
            if re.match(r'^[a-zA-Z]+[0-9]*$', disk):
                disk_path = f"/dev/{disk}"
                if os.path.exists(disk_path):
                    valid_disks.append(disk)
                else:
                    print(f"Disk {disk_path} not found. Skipping.")
            else:
                print(f"Invalid disk name format: {disk}. Skipping.")
        
        return valid_disks
        
    except KeyboardInterrupt:
        log_error("Disk selection interrupted by user (Ctrl+C)")
        sys.exit(130)
    except (IOError, OSError) as e:
        log_error(f"System error during disk selection: {str(e)}")
        return []
    except (AttributeError, TypeError) as e:
        log_error(f"Data processing error during disk selection: {str(e)}")
        return []

def get_erasure_method():
    """Get erasure method choice from user"""
    while True:
        try:
            print("\n" + "=" * 50)
            print("            ERASURE METHOD SELECTION")
            print("=" * 50)
            print("1. Standard Overwrite (multiple passes)")
            print("2. Cryptographic Erasure (recommended for SSDs)")
            print("-" * 50)
            
            choice = input("Select erasure method (1-2): ").strip()
            
            if choice == "1":
                return False, "random"  # use_crypto=False, crypto_fill doesn't matter
            elif choice == "2":
                # Get crypto fill method
                while True:
                    print("\n" + "=" * 40)
                    print("     CRYPTOGRAPHIC FILL METHOD")
                    print("=" * 40)
                    print("1. Random Data (recommended)")
                    print("2. Zero Data")
                    print("-" * 40)
                    
                    fill_choice = input("Select fill method (1-2): ").strip()
                    
                    if fill_choice == "1":
                        return True, "random"  # use_crypto=True, crypto_fill="random"
                    elif fill_choice == "2":
                        return True, "zero"   # use_crypto=True, crypto_fill="zero"
                    else:
                        print("Invalid choice. Please enter 1 or 2.")
            else:
                print("Invalid choice. Please enter 1 or 2.")
                
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(130)
        except (EOFError, IOError) as e:
            print(f"\nInput error: {str(e)}")
            print("Operation cancelled.")
            sys.exit(1)

def get_passes():
    """Get number of passes for overwrite method"""
    while True:
        try:
            passes_input = input("Enter number of passes for overwrite (default: 3): ").strip()
            if not passes_input:
                return 3
            
            passes = int(passes_input)
            if passes < 1:
                print("Number of passes must be at least 1.")
                continue
            elif passes > 20:
                print("Warning: More than 20 passes may take a very long time.")
                confirm = input("Continue? (y/n): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            return passes
            
        except ValueError:
            print("Invalid input. Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(130)
        except (EOFError, IOError) as e:
            print(f"\nInput error: {str(e)}")
            print("Operation cancelled.")
            sys.exit(1)

def confirm_erasure(disk: str, fs_choice: str, method_description: str) -> bool:
    """
    Get confirmation to erase a specific disk with detailed warnings.
    """
    while True:
        try:
            print("\n" + "-" * 50)
            disk_id, is_disk_ssd, is_active = print_disk_details(disk)
            print("-" * 50)
            
            if is_disk_ssd and "overwrite" in method_description.lower():
                print("\nWARNING: This disk is an SSD. Multiple-pass overwrite may not be effective.")
                print("         Consider using cryptographic erasure instead.")
                
            if is_active:
                print("\nDANGER: This is the ACTIVE SYSTEM DISK! Erasing it will make your system unusable.")
                print("        The system will CRASH if you proceed with erasing this disk.")
                
            print(f"\nYou are about to PERMANENTLY ERASE disk {disk_id} (/dev/{disk}).")
            print(f"Filesystem: {fs_choice}")
            print(f"Method: {method_description}")
            print("This operation CANNOT be undone and ALL DATA WILL BE LOST!")
            
            confirmation = input(f"Are you sure you want to erase disk {disk_id}? (yes/no): ").strip().lower()
            if confirmation == "yes":
                # For active system disks, require a second confirmation
                if is_active:
                    second_confirm = input("FINAL WARNING: You are about to erase the ACTIVE SYSTEM DISK. Type 'DESTROY' to confirm: ").strip()
                    return second_confirm == "DESTROY"
                return True
            elif confirmation == "no":
                return False
            print("Invalid input. Enter 'yes' or 'no'.")
        except KeyboardInterrupt:
            log_error("Erasure confirmation interrupted by user (Ctrl+C)")
            sys.exit(130)
        except (EOFError, IOError) as e:
            log_error(f"Input error during erasure confirmation: {str(e)}")
            return False

def get_disk_confirmations(disks: list[str], fs_choice: str, passes: int, use_crypto: bool, crypto_fill: str) -> list[str]:
    """Get confirmation for each disk with operation details."""
    if use_crypto:
        fill_method = "zeros" if crypto_fill == "zero" else "random data"
        method_description = f"cryptographic erasure (filling with {fill_method})"
    else:
        method_description = f"standard {passes}-pass overwrite"
    
    return [disk for disk in disks if confirm_erasure(disk, fs_choice, method_description)]

def print_log_menu() -> None:
    """Display and handle log printing options"""
    while True:
        try:
            print("\n" + "=" * 50)
            print("            LOG PRINTING OPTIONS")
            print("=" * 50)
            print("1. Print Session Log (current session only)")
            print("2. Print Complete Log File (all historical logs)")
            print("3. Return to main menu")
            print("-" * 50)
            
            choice = input("Enter your choice (1-3): ").strip()
            
            if choice == "1":
                print_session_log_cli()
            elif choice == "2":
                print_complete_log_cli()
            elif choice == "3":
                break
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\nReturning to main menu...")
            break
        except (EOFError, IOError, OSError) as e:
            print(f"Input/Output error: {str(e)}")

def print_session_log_cli() -> None:
    """Generate and save session log as PDF (CLI version)"""
    try:
        # Use the updated function from log_handler
        session_logs = get_current_session_logs()
        if not session_logs:
            print("No session logs available to print!")
            return
        
        print("Generating session log PDF...")
        pdf_path = generate_session_pdf()
        
        print(f"Session log PDF generated successfully!")
        print(f"Saved to: {pdf_path}")
        log_info(f"Session log PDF saved to: {pdf_path}")
        
    except (FileNotFoundError, PermissionError) as e:
        error_msg = f"File access error generating session log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (IOError, OSError) as e:
        error_msg = f"System error generating session log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (ImportError, AttributeError) as e:
        error_msg = f"Module/dependency error generating session log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (TypeError, ValueError) as e:
        error_msg = f"Data processing error generating session log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)

def print_complete_log_cli() -> None:
    """Generate and save complete log file as PDF (CLI version)"""
    try:
        print("Generating complete log PDF...")
        pdf_path = generate_log_file_pdf()
        
        print(f"Complete log PDF generated successfully!")
        print(f"Saved to: {pdf_path}")
        log_info(f"Complete log PDF saved to: {pdf_path}")
        
    except (FileNotFoundError, PermissionError) as e:
        error_msg = f"File access error generating complete log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (IOError, OSError) as e:
        error_msg = f"System error generating complete log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (ImportError, AttributeError) as e:
        error_msg = f"Module/dependency error generating complete log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (TypeError, ValueError) as e:
        error_msg = f"Data processing error generating complete log PDF: {str(e)}"
        print(error_msg)
        log_error(error_msg)

def cli_process_disk(disk, fs_choice, passes, use_crypto=False, crypto_fill="random"):
    """
    Process a single disk for the CLI interface with status output.
    
    This function wraps the process_disk function from disk_operations.py
    to provide CLI-specific logging and error handling.
    """
    try:
        # Get the disk identifier for better logging
        disk_id = get_disk_serial(disk)
        process_msg = f"Processing disk {disk_id} (/dev/{disk})"
        print(f"\n{process_msg}...")
        log_info(process_msg)
        
        # Define a logging function for the CLI
        def log_progress(message):
            print(f"  {message}")
        
        # Indicate if the disk is an SSD and not using crypto
        if is_ssd(disk) and not use_crypto:
            warning_msg = f"WARNING: {disk_id} is an SSD - multiple-pass erasure may not be effective"
            print(f"  {warning_msg}")
            log_info(warning_msg)
        
        # Process the disk using the imported function with crypto flag and filling method
        process_disk(disk, fs_choice, passes, use_crypto, crypto_fill, log_func=log_progress)
        
        success_msg = f"Successfully completed all operations on disk {disk_id}"
        print(success_msg)
        log_info(success_msg)
        return True
    except (CalledProcessError, SubprocessError) as e:
        error_msg = f"Command execution error processing disk /dev/{disk}: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        return False
    except (IOError, OSError) as e:
        error_msg = f"System error while processing disk /dev/{disk}: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        return False
    except (FileNotFoundError, PermissionError) as e:
        error_msg = f"Access error while processing disk /dev/{disk}: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        return False
    except (ValueError, TypeError) as e:
        error_msg = f"Data validation error while processing disk /dev/{disk}: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        return False
    except (ImportError, AttributeError) as e:
        error_msg = f"Module/dependency error while processing disk /dev/{disk}: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        return False
    except KeyboardInterrupt:
        error_msg = f"Disk processing interrupted for /dev/{disk}"
        print(error_msg)
        log_error(error_msg)
        return False

def run_disk_erasure_operation(args=None):
    """Run the disk erasure operation workflow"""
    try:
        # First, list disks and select disks to erase
        print("List of available disks: ")
        disks = select_disks()
        if not disks:
            print("No disks selected. Returning to main menu.")
            return
        
        # Get operation parameters
        if args and args.filesystem:
            fs_choice = args.filesystem
        else:
            fs_choice = choose_filesystem()
            
        # Get erasure method
        if args and hasattr(args, 'crypto') and args.crypto:
            use_crypto = True
            crypto_fill = "zero" if (hasattr(args, 'zero') and args.zero) else "random"
            passes = 1  # Not used for crypto
        else:
            use_crypto, crypto_fill = get_erasure_method()
            if use_crypto:
                passes = 1  # Not used for crypto
            else:
                if args and args.passes:
                    passes = args.passes
                else:
                    passes = get_passes()
        
        print(f"Selected filesystem: {fs_choice}")
        log_info(f"Selected filesystem: {fs_choice}")
        
        if use_crypto:
            fill_method = "zeros" if crypto_fill == "zero" else "random data"
            method_msg = f"Erasure method: Cryptographic erasure (filling with {fill_method})"
            print(method_msg)
            log_info(method_msg)
        else:
            method_msg = f"Erasure method: Standard with {passes} passes"
            print(method_msg)
            log_info(method_msg)
        
        # Then, get confirmation for each disk with detailed operation info
        confirmed_disks = get_disk_confirmations(disks, fs_choice, passes, use_crypto, crypto_fill)
        if not confirmed_disks:
            print("No disks confirmed for erasure. Returning to main menu.")
            return
        
        print("\nAll disks confirmed. Starting operations...\n")
        operation_start_msg = f"Starting disk erasure operations on {len(confirmed_disks)} disk(s)"
        log_info(operation_start_msg)
        
        with ThreadPoolExecutor() as executor:
            # Use our cli_process_disk function with the crypto flag and crypto_fill option
            futures = [executor.submit(cli_process_disk, disk, fs_choice, passes, use_crypto, crypto_fill) for disk in confirmed_disks]
            
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        completed += 1
                except (RuntimeError, ValueError, TypeError) as e:
                    error_msg = f"Thread execution error processing disk: {str(e)}"
                    log_error(error_msg)
                except (TimeoutError, InterruptedError) as e:
                    error_msg = f"Thread timeout/interrupt error processing disk: {str(e)}"
                    log_error(error_msg)
        
        completion_msg = f"Completed operations on {completed}/{len(confirmed_disks)} disks."
        print(f"\n{completion_msg}")
        log_info(completion_msg)
        
    except KeyboardInterrupt:
        interrupt_msg = "Disk erasure operation interrupted by user (Ctrl+C)"
        print(f"\n{interrupt_msg}")
        log_error(interrupt_msg)
    except (AttributeError, TypeError) as e:
        error_msg = f"Configuration/argument error during disk erasure operation: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (ImportError, ModuleNotFoundError) as e:
        error_msg = f"Module import error during disk erasure operation: {str(e)}"
        print(error_msg)
        log_error(error_msg)
    except (OSError, IOError) as e:
        error_msg = f"System error during disk erasure operation: {str(e)}"
        print(error_msg)
        log_error(error_msg)

def run_cli_mode(args):
    """
    Run the command-line interface version with detailed disk information.
    """
    try:
        # Check for root privileges
        if os.geteuid() != 0:
            print("Error: This program must be run as root!")
            sys.exit(1)
            
        print("=" * 60)
        print("         SECURE DISK ERASER - COMMAND LINE INTERFACE")
        print("=" * 60)
        
        # Start session logging
        session_start()
        
        # Initialize session log
        start_msg = "CLI session started"
        log_info(start_msg)
        print(f"Session started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        while True:
            try:
                print("\n" + "=" * 50)
                print("                MAIN MENU")
                print("=" * 50)
                print("1. Start Disk Erasure Operation")
                print("2. Print Log Options")
                print("3. Exit")
                print("-" * 50)
                
                choice = input("Enter your choice (1-3): ").strip()
                
                if choice == "1":
                    # Disk erasure operation
                    run_disk_erasure_operation(args)
                
                elif choice == "2":
                    # Print log options
                    print_log_menu()
                
                elif choice == "3":
                    # Exit
                    exit_msg = "CLI session ended by user"
                    print(f"\n{exit_msg}")
                    log_info(exit_msg)
                    break
                
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
                    
            except KeyboardInterrupt:
                interrupt_msg = "Main menu operation interrupted by user (Ctrl+C)"
                print(f"\n{interrupt_msg}")
                log_error(interrupt_msg)
                continue
            except (EOFError, IOError) as e:
                input_error_msg = f"Input error in main menu: {str(e)}"
                print(f"\n{input_error_msg}")
                log_error(input_error_msg)
                continue
                
    except KeyboardInterrupt:
        final_interrupt_msg = "Program terminated by user (Ctrl+C)"
        print(f"\n{final_interrupt_msg}")
        log_error(final_interrupt_msg)
        sys.exit(130)
    except (IOError, OSError) as e:
        error_msg = f"System error: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        sys.exit(1)
    except (ValueError, TypeError) as e:
        error_msg = f"Data validation error: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        sys.exit(1)
    except (SubprocessError, CalledProcessError) as e:
        error_msg = f"Command execution error: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        sys.exit(1)
    except (ImportError, ModuleNotFoundError) as e:
        error_msg = f"Module import error: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        sys.exit(1)
    except (AttributeError, NameError) as e:
        error_msg = f"Configuration/reference error: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        sys.exit(1)
    except (PermissionError, FileNotFoundError) as e:
        error_msg = f"Access/file error: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        sys.exit(1)
    finally:
        # Ensure session is properly ended
        session_end()