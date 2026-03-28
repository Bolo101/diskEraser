import subprocess
import tempfile
import os
import logging
import sys
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_disk_serial(device: str) -> str:
    """
    Get a stable disk identifier using udevadm to extract WWN or serial number from an unmounted device.
    """
    try:
        # Try getting the WWN (World Wide Name) directly from udevadm
        output = subprocess.run(
            ["udevadm", "info", "--query=property", f"--name=/dev/{device}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        ).stdout.decode()

        # Look for WWN in the udevadm output
        wwn_match = re.search(r'ID_WWN=(\S+)', output)
        if wwn_match:
            return wwn_match.group(1)

        # If WWN not found, fall back to the serial number
        serial_match = re.search(r'ID_SERIAL_SHORT=(\S+)', output)
        if serial_match:
            return serial_match.group(1)
        
        # Get the model as a fallback if serial is not available
        model_match = re.search(r'ID_MODEL=(\S+)', output)
        if model_match:
            return f"{model_match.group(1)}_{device}"
            
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logging.error(f"Error occurred while querying {device}: {e}")
    except KeyboardInterrupt:
        logging.error("Disk identification interrupted by user (Ctrl+C)")
        print("\nDisk identification interrupted by user (Ctrl+C)")
        sys.exit(130)

    # If all else fails, return a default identifier
    return f"UNKNOWN_{device}"

def is_ssd(device: str) -> bool:
    try:
        output = subprocess.run(
            ["cat", f"/sys/block/{device}/queue/rotational"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return output.stdout.decode().strip() == "0"
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        logging.warning(f"SSD check failed for {device}: {e}")
        # Don't exit, just return False as fallback
        return False
    except KeyboardInterrupt:
        logging.error("SSD check interrupted by user (Ctrl+C)")
        print("\nSSD check interrupted by user (Ctrl+C)")
        sys.exit(130)

def erase_disk_hdd(device: str, passes: int, log_func=None) -> str:
    try:
        # Type-casting arguments to ensure correct types
        device = str(device)
        passes = int(passes)

        # Get stable disk identifier before erasure
        disk_serial = get_disk_serial(device)

        if is_ssd(device):
            logging.warning(f"Warning: {device} appears to be an SSD. Multiple passes may not be effective.")
            # Continue with erasure instead of returning

        logging.info(f"Erasing {device} using shred with {passes} passes...")
        # Also log to GUI if log_func is provided
        if log_func:
            log_func(f"Erasing {device} using shred with {passes} passes...")
        
        # Create a subprocess with stdout piped to capture shred output
        shred_process = subprocess.Popen(
            ["shred", "-n", f"{passes}", "-v", f"/dev/{device}"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True
        )

        # Read output in real-time
        while True:
            try:
                output = shred_process.stdout.readline()
                if output == '' and shred_process.poll() is not None:
                    break
                if output:
                    # If a log function is provided (like in GUI), use it
                    # Otherwise, print to stdout
                    if log_func:
                        log_func(output.strip())
                    else:
                        print(output.strip())
            except KeyboardInterrupt:
                # Terminate the shred process if user interrupts
                shred_process.terminate()
                logging.error("Disk erasure interrupted by user (Ctrl+C)")
                print("\nDisk erasure interrupted by user (Ctrl+C)")
                sys.exit(130)

        # Check return code
        if shred_process.returncode != 0:
            raise subprocess.CalledProcessError(shred_process.returncode, "shred")

        # Log partition table wiping to both log file and GUI
        wipe_message = f"Wiping partition table of {device} using dd..."
        logging.info(wipe_message)
        if log_func:
            log_func(wipe_message)
            
        # Run dd command
        subprocess.run(["dd", "if=/dev/zero", f"of=/dev/{device}", "bs=1M", "count=10"], check=True)

        # Log success message to both log file and GUI
        success_message = f"Disk {device} successfully erased."
        logging.info(success_message)
        if log_func:
            log_func(success_message)
            
        return disk_serial
    except FileNotFoundError:
        error_message = "Error: Required command not found."
        logging.error(error_message)
        if log_func:
            log_func(error_message)
        sys.exit(2)
    except subprocess.CalledProcessError as e:
        error_message = f"Error: Failed to erase {device}: {e}"
        logging.error(error_message)
        if log_func:
            log_func(error_message)
        sys.exit(1)
    except KeyboardInterrupt:
        error_message = "Disk erasure interrupted by user (Ctrl+C)"
        logging.error(error_message)
        if log_func:
            log_func(error_message)
        print(f"\n{error_message}")
        sys.exit(130)

def erase_disk_crypto(device: str, filling_method: str = "random", log_func=None) -> bool:
    """
    Securely erase a disk using cryptographic erasure: encrypt the entire drive
    with a random key, then discard the key making data unrecoverable.
    
    Args:
        device (str): Device name (without /dev/ prefix, e.g. 'sda')
        filling_method (str): Fill method - "random" or "zero"
        log_func (callable, optional): Function for logging output in real-time (e.g., for GUI)
        
    Returns:
        str: Disk serial number or identifier
        
    Raises:
        Various exceptions if the erasure process fails
    """
    # Create unique temporary keyfile for this device to avoid conflicts
    keyfile_fd, keyfile_path = tempfile.mkstemp(prefix=f"keyfile_{device}_", suffix=".key")
    
    try:
        # Close the file descriptor since we'll use the path with dd
        os.close(keyfile_fd)
        
        # Get stable disk identifier before erasure
        disk_serial = get_disk_serial(device)
        
        # Log start message
        start_message = f"Starting cryptographic erasure of {device}..."
        logging.info(start_message)
        if log_func:
            log_func(start_message)
        
        # Step 1: Create a random encryption key and store temporarily
        key_creation_msg = "Generating random encryption key..."
        logging.info(key_creation_msg)
        if log_func:
            log_func(key_creation_msg)
            
        # Create a temporary keyfile with random data using unique path
        subprocess.run(
            ["dd", "if=/dev/urandom", f"of={keyfile_path}", "bs=512", "count=8"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Step 2: Use cryptsetup to encrypt the entire drive with LUKS
        encrypt_msg = f"Encrypting {device} with LUKS using random key..."
        logging.info(encrypt_msg)
        if log_func:
            log_func(encrypt_msg)
            
        # Create LUKS container (this will destroy all data on the device)
        cryptsetup_process = subprocess.Popen(
            ["cryptsetup", "-q", "--batch-mode", "luksFormat", 
             f"/dev/{device}", keyfile_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Read output in real-time
        while True:
            try:
                output = cryptsetup_process.stdout.readline()
                if output == '' and cryptsetup_process.poll() is not None:
                    break
                if output:
                    if log_func:
                        log_func(output.strip())
                    else:
                        print(output.strip())
            except KeyboardInterrupt:
                cryptsetup_process.terminate()
                logging.error("Encryption interrupted by user (Ctrl+C)")
                print("\nEncryption interrupted by user (Ctrl+C)")
                sys.exit(130)
        
        # Check return code
        if cryptsetup_process.returncode != 0:
            raise subprocess.CalledProcessError(cryptsetup_process.returncode, "cryptsetup")
        
        # Step 3: Fill the encrypted volume with zeroes or random data for added security
        fill_msg = "Opening encrypted device to fill with data..."
        logging.info(fill_msg)
        if log_func:
            log_func(fill_msg)
            
        # Create unique mapper name for this device to avoid conflicts
        mapper_name = f"temp_{device}_{os.getpid()}"
        
        # Open the encrypted device
        subprocess.run(
            ["cryptsetup", "open", "--key-file", keyfile_path, 
             f"/dev/{device}", mapper_name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # FIXED: Properly handle the filling method selection
        if filling_method == "random":
            fill_data_msg = "Filling encrypted device with random data (this may take a while)..."
            logging.info(fill_data_msg)
            if log_func:
                log_func(fill_data_msg)
                
            fill_process = subprocess.Popen(
                ["dd", "if=/dev/urandom", f"of=/dev/mapper/{mapper_name}", 
                "bs=4M", "status=progress"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
        else:  # "zero" filling method
            fill_data_msg = "Filling encrypted device with zeros (this may take a while)..."
            logging.info(fill_data_msg)
            if log_func:
                log_func(fill_data_msg)
                
            fill_process = subprocess.Popen(
                ["dd", "if=/dev/zero", f"of=/dev/mapper/{mapper_name}", 
                "bs=4M", "status=progress"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
        # Read output in real-time to show progress
        while True:
            try:
                output = fill_process.stdout.readline()
                if output == '' and fill_process.poll() is not None:
                    break
                if output:
                    if log_func:
                        log_func(output.strip())
                    else:
                        print(output.strip())
            except KeyboardInterrupt:
                fill_process.terminate()
                logging.error("Fill operation interrupted by user (Ctrl+C)")
                print("\nFill operation interrupted by user (Ctrl+C)")
                # Make sure to close the mapper device before exiting
                subprocess.run(["cryptsetup", "close", mapper_name], 
                               check=False)
                sys.exit(130)
        
        # Step 4: Close the encrypted device
        close_msg = "Closing encrypted device..."
        logging.info(close_msg)
        if log_func:
            log_func(close_msg)
            
        subprocess.run(
            ["cryptsetup", "close", mapper_name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Step 5: Securely delete the key file
        key_delete_msg = "Securely erasing the encryption key..."
        logging.info(key_delete_msg)
        if log_func:
            log_func(key_delete_msg)
            
        subprocess.run(
            ["shred", "-u", "-z", "-n", "3", keyfile_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Step 6: Optionally, overwrite the LUKS header to prevent any chance of recovery
        header_msg = "Overwriting LUKS header to prevent any possibility of key recovery..."
        logging.info(header_msg)
        if log_func:
            log_func(header_msg)
            
        subprocess.run(
            ["dd", "if=/dev/urandom", f"of=/dev/{device}", "bs=1M", "count=10"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Log success message with correct fill method
        fill_method_str = "random data" if filling_method == "random" else "zero data"
        success_message = f"Disk {device} successfully erased using cryptographic method with {fill_method_str} filling."
        logging.info(success_message)
        if log_func:
            log_func(success_message)
            
        return disk_serial
        
    except FileNotFoundError as e:
        error_message = f"Error: Required command not found: {e}"
        logging.error(error_message)
        if log_func:
            log_func(error_message)
        sys.exit(2)
    except subprocess.CalledProcessError as e:
        error_message = f"Error: Failed to cryptographically erase {device}: {e}"
        logging.error(error_message)
        if log_func:
            log_func(error_message)
        sys.exit(1)
    except KeyboardInterrupt:
        error_message = "Cryptographic erasure interrupted by user (Ctrl+C)"
        logging.error(error_message)
        if log_func:
            log_func(error_message)
        print(f"\n{error_message}")
        sys.exit(130)
    finally:
        # Cleanup in case of any errors
        try:
            # Create mapper name for cleanup (same as above)
            mapper_name = f"temp_{device}_{os.getpid()}"
            
            # Check if the mapper device exists and close it if it does
            result = subprocess.run(
                ["dmsetup", "info", mapper_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                subprocess.run(["cryptsetup", "close", mapper_name], check=False)
                
            # Remove the key file if it still exists
            if Path(keyfile_path).exists():
                subprocess.run(["shred", "-u", "-z", "-n", "3", keyfile_path], check=False)
        except subprocess.SubprocessError as e:
            logging.error(f"Subprocess error during cleanup: {e}")
        except FileNotFoundError as e:
            logging.error(f"Required command not found during cleanup: {e}")
        except PermissionError as e:
            logging.error(f"Permission error during cleanup: {e}")
        except OSError as e:
            logging.error(f"OS error during cleanup: {e}")