# Disk Eraser - Secure Disk Wiping and Formatting Tool

**Disk Eraser** is a powerful tool for securely erasing data from hard drives or USB keys, while also providing the option to format the disk with a chosen file system (EXT4, NTFS, or VFAT). It can erase multiple disks in parallel, while ensuring that each disk is wiped thoroughly with random data, making it impossible to recover the erased data.

The tool operates with pre-selected confirmation and formatting options, requiring no further interaction from the user once the erasure process begins. 

The project is designed to run inside a Docker container, as a bootable ISO, directly as Python code, or as a Linux command stored in `/usr/local/bin` under the name `diskeraser`.

---

## Features

- **List Available Disks**: Displays all detected disks for easy selection and allows the user to erase one or more disks.
- **Secure Erase**: Uses multiple passes of random data to overwrite existing data and a final zero pass to ensure data cannot be recovered.
- **Parallel Erasure**: Allows simultaneous erasure of multiple disks with multi-threading.
- **Automatic Partitioning**: Configures the disk with a single partition after erasure.
- **Flexible Formatting**: Format the disk with NTFS, EXT4, or VFAT file systems.
- **Non-Interactive Mode**: All confirmation prompts and filesystem format options are selected before the process starts, and no user interaction is required during the erasure.
- **Docker Support**: Can be securely run in a containerized environment.
- **Bootable ISO**: Can be converted into a bootable ISO for standalone operation.
- **Command Line Utility**: Can be installed as a Linux command (`diskeraser`) for ease of use.

---

## Prerequisites

- Docker installed on your system (for running in a container).
- Root privileges (required for disk access).
- Basic understanding of disk management and caution, as the tool will permanently erase data.

---

## Installation and Usage

### Using direct python3 code

1. **Download repo**:
```bash
git clone https://github.com/Bolo101/diskEraser.git
```
2. **Execute code**:
```bash
cd diskEraser/code
sudo python3 main.py
```

### Install as a Linux Command (`diskeraser`)

1. **Copy the scripts to `/usr/local/bin`**:
```bash
sudo mkdir -p /usr/local/bin/diskeraser
sudo cp diskEraser/code/*.py /usr/local/bin/diskeraser
sudo chmod +x /usr/local/bin/diskeraser/main.py
sudo ln -s /usr/local/bin/diskeraser/main.py /usr/local/bin/diskeraser
```
2. **Run the tool**:
```bash
sudo diskeraser
```
This allows you to execute the tool as a simple command from anywhere on your system.

### Using with Docker

You have two options for using the Docker container. The first version is `zkbolo/disk-eraser-debian:1.0`, and the newer version is `zkbolo/diskeraser-v2.1:latest`, which includes the latest features and improvements.

#### Version 1.0 (Old Version)
1. **Pull the Docker image from Docker Hub**:
```bash
docker pull zkbolo/disk-eraser-debian:1.0
```
This version can only erase one disk at a time.

2. **Run the Docker Image with Necessary Privileges**:
```bash
docker run --rm -it --privileged zkbolo/disk-eraser-debian:1.0
```

3. **Follow the interactive instructions inside the container to select and erase a disk**.

#### Version 2.2 (New Version)
1. **Pull the latest Docker image**:
```bash
docker pull zkbolo/diskeraser-v2.2:latest
```

2. **Run the Docker Image with Necessary Privileges**:
```bash
docker run --rm -it --privileged zkbolo/diskeraser-v2.2:latest
```

3. **Follow the interactive instructions inside the container to select and erase one or more disks**:
   - The tool will list all available disks, allow you to select which ones to erase, and confirm before starting the erasure process.
   - You will also be prompted to choose a file system (EXT4, NTFS, or VFAT) after erasure.

### Using the Bootable ISO

1. **Create the ISO**: Use the provided Bash script in the project to generate a bootable ISO file:

```bash
cd diskEraser/iso && chmod +x forgeIso.sh && sudo bash forgeIso.sh
```

2. **Flash the ISO to a USB key**: Use a tool like `dd` or `Rufus`:

With a terminal to forge USB using **dd** command
```bash
sudo dd if=secure_disk_eraser.iso of=/dev/sdX bs=4M status=progress
```

3. **Boot from the USB key**:
   - Configure your BIOS/UEFI to boot from the USB key.
   - Follow the on-screen instructions to use the tool, select the disks to erase, and choose a file system for formatting.

---

## ISO Download Links

If you prefer not to build the ISO yourself, you can download the pre-built ISO files for your system from the following links:

- [Download the latest version of the ISO (version 2.1)](https://archive.org/details/diskeraser-v2.1)
- [Download the previous version of the ISO (version 1)](https://archive.org/details/diskeraser)
This version can only erase one disk at a time.

These ISO files are ready to be flashed to a USB key and used for bootable operations.

---

## Command Line Options

When running the project directly in Python or via Docker, you can provide arguments to automate certain steps:

**Select file system**:
- `-f ext4`: Format the disk with the EXT4 file system.
- `-f ntfs`: Format the disk with the NTFS file system.
- `-f vfat`: Format the disk with the VFAT file system.

### Example:

```bash
python3 main.py -f ext4
```

This will erase the selected disk(s), then format it using the EXT4 file system.

---

## Project Structure

Here is the main structure of the project:

```bash
project/
├── README.md                   # Documentation for the project
├── code/                       # Main Python scripts for the tool
│   ├── disk_erase.py           # Module for secure data erasure
│   ├── disk_format.py          # Module for formatting disks
│   ├── disk_partition.py       # Module for creating partitions
│   ├── mainParse.py            # Main script with argument parsing
│   └── utils.py                # Utility functions (e.g., disk listing)
├── iso/                        # Files related to creating the bootable ISO
│   └── forgeIso.sh             # Script to generate the bootable ISO
├── setup.sh                    # Script to install dependencies and prepare the project
├── LICENSE                     # Common Creative 4 license
└── Dockerfile                  # Dockerfile to build docker image locally
```

---

## Notes

- **Disk Safety**: The tool **permanently erases** data from the selected disks. Make sure you have backups of any important data before proceeding.
- **Root Access**: Ensure you are running the program with sufficient privileges to access and modify disks (i.e., root or `sudo`).
- **Non-Interactive Operation**: Once the erasure process begins, no further user interaction is required. All confirmation prompts and formatting options are selected beforehand.
- **Small Disks**: If you are erasing very small disks, the tool may skip partitioning or formatting operations if the disk is too small to handle them.
