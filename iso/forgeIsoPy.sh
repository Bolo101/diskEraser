#!/bin/bash

# Exit on any error
set -e

# Variables
ISO_NAME="secure_disk_eraser.iso"
WORK_DIR="$HOME/debian-live-build"
CODE_DIR="$HOME/diskEraser/code/python"  # Path to your Python code directory

# Install necessary tools
echo "Installing live-build and required dependencies..."
sudo apt update
sudo apt install -y live-build python3 python3-pip calamares calamares-settings-debian syslinux

# Create working directory
echo "Setting up live-build workspace..."
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Clean previous build
sudo lb clean

# Configure live-build
echo "Configuring live-build for Debian Bookworm..."
lb config --distribution=bookworm --architectures amd64 \
    --linux-packages linux-image \
    --debian-installer live \
    --bootappend-live "boot=live components hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr"

# Add Debian repositories for firmware
mkdir -p config/archives
cat << EOF > config/archives/debian.list.chroot
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
EOF

# Add required packages
echo "Adding required packages..."
mkdir -p config/package-lists/
cat << EOF > config/package-lists/custom.list.chroot
coreutils
parted
ntfs-3g
python3
python3-pip
dosfstools
firmware-linux-free
firmware-linux-nonfree
calamares
calamares-settings-debian
squashfs-tools
xorg
xfce4
network-manager
network-manager-gnome
sudo
live-boot
live-config
live-tools
tasksel
tasksel-data
console-setup
keyboard-configuration
EOF

# Set system locale and keyboard layout to French AZERTY
echo "Configuring live system for French AZERTY keyboard..."
mkdir -p config/includes.chroot/etc/default/

# Set default locale to French
cat << EOF > config/includes.chroot/etc/default/locale
LANG=fr_FR.UTF-8
LC_ALL=fr_FR.UTF-8
EOF

# Set keyboard layout to AZERTY
mkdir -p config/includes.chroot/etc/default/
cat << EOF > config/includes.chroot/etc/default/keyboard
XKBMODEL="pc105"
XKBLAYOUT="fr"
XKBVARIANT="azerty"
XKBOPTIONS=""
EOF

# Set console keymap for tty
mkdir -p config/includes.chroot/etc/default/
cat << EOF > config/includes.chroot/etc/default/console-setup
ACTIVE_CONSOLES="/dev/tty[1-6]"
CHARMAP="UTF-8"
CODESET="Lat15"
XKBLAYOUT="fr"
XKBVARIANT="azerty"
EOF

# Copy all files from CODE_DIR to /usr/local/bin
echo "Copying all files from $CODE_DIR to /usr/local/bin..."
mkdir -p config/includes.chroot/usr/local/bin/

# Copy all files recursively
cp -r "$CODE_DIR"/* config/includes.chroot/usr/local/bin/

# Make sure all copied files are executable
chmod +x config/includes.chroot/usr/local/bin/*

# Create symbolic link 'de' -> main.py
ln -s /usr/local/bin/main.py config/includes.chroot/usr/local/bin/de

# Configure .bashrc to run main.py on login
echo "Configuring .bashrc to run main.py as root..."
mkdir -p config/includes.chroot/etc/skel/
cat << 'EOF' > config/includes.chroot/etc/skel/.bashrc
if [ "$(id -u)" -ne 0 ]; then
    echo "Running main.py as root..."
    sudo python3 /usr/local/bin/main.py
else
    python3 /usr/local/bin/main.py
fi
EOF

# Configure Boot Menu (Syslinux)
mkdir -p config/includes.binary/isolinux
cat << 'EOF' > config/includes.binary/isolinux/menu.cfg
UI vesamenu.c32
DEFAULT live
TIMEOUT 50

MENU TITLE Secure Disk Eraser - Boot Menu

LABEL live
    MENU LABEL Start Live Environment
    KERNEL /live/vmlinuz
    APPEND initrd=/live/initrd.img boot=live components

LABEL install
    MENU LABEL Install Secure Eraser (Copy Live System)
    KERNEL /live/vmlinuz
    APPEND initrd=/live/initrd.img boot=live components automatic calamares
EOF

# Configure GRUB Boot Menu
mkdir -p config/bootloaders
cat << 'EOF' > config/bootloaders/grub.cfg
set default=0
set timeout=5

menuentry "Start Live Environment" {
    linux /live/vmlinuz boot=live components
    initrd /live/initrd.img
}

menuentry "Install Secure Eraser (Copy Live System)" {
    linux /live/vmlinuz boot=live components automatic calamares
    initrd /live/initrd.img
}
EOF

# Auto-start Calamares if in installer mode
mkdir -p config/includes.chroot/etc/profile.d/
cat << 'EOF' > config/includes.chroot/etc/profile.d/autostart-calamares.sh
#!/bin/bash
if [[ "$(cat /proc/cmdline)" == *"calamares"* ]]; then
    echo "Starting Calamares Installer..."
    calamares --debug
fi
EOF
chmod +x config/includes.chroot/etc/profile.d/autostart-calamares.sh

# Build the ISO
echo "Building the ISO..."
sudo lb build

# Move the ISO
mv live-image-amd64.hybrid.iso "$HOME/$ISO_NAME"

# Cleanup
sudo lb clean

echo "Done."
