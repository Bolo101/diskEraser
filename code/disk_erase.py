import os


def write_random_data(device, passes, update_progress_callback=None):
    block_size = 4096
    try:
        with open(f"/dev/{device}", "wb") as disk:
            disk_size = os.lseek(disk.fileno(), 0, os.SEEK_END)
            os.lseek(disk.fileno(), 0, os.SEEK_SET)

            for pass_num in range(1, passes + 1):
                written = 0
                while written < disk_size:
                    remaining = disk_size - written
                    to_write = min(block_size, remaining)
                    disk.write(os.urandom(to_write))
                    written += to_write

                    if update_progress_callback:
                        progress = (written / disk_size) * 100 / passes + (pass_num - 1) * (100 / passes)
                        update_progress_callback(progress)

                disk.flush()
                os.lseek(disk.fileno(), 0, os.SEEK_SET)
    except Exception as e:
        raise Exception(f"Error while writing random data to {device}: {e}")


def write_zero_data(device, update_progress_callback=None):
    block_size = 4096
    try:
        with open(f"/dev/{device}", "wb") as disk:
            disk_size = os.lseek(disk.fileno(), 0, os.SEEK_END)
            os.lseek(disk.fileno(), 0, os.SEEK_SET)

            written = 0
            while written < disk_size:
                remaining = disk_size - written
                to_write = min(block_size, remaining)
                disk.write(b"\x00" * to_write)
                written += to_write

                if update_progress_callback:
                    progress = (written / disk_size) * 100
                    update_progress_callback(progress)

            disk.flush()
    except Exception as e:
        raise Exception(f"Error while writing zero data to {device}: {e}")


def erase_disk(disk, passes, update_progress_callback=None):
    """
    Securely erase the entire disk by overwriting it with random data and zeros.
    """
    print(f"Erasing {disk} with multiple random data passes and a final zero pass for security...")
    write_random_data(disk, passes, update_progress_callback)
    write_zero_data(disk, update_progress_callback)
    print(f"Disk {disk} successfully erased.")
