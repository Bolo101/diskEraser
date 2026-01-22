#!/bin/bash

# Exit on any error
set -e

# Variables
ISO_NAME="$(pwd)/diskEraser-v5.4-32bits.iso"
WORK_DIR="$(pwd)/debian-live-build"
CODE_DIR="$(pwd)/../../code"

# Install necessary tools
echo "Installing live-build and required dependencies..."
sudo apt update
sudo apt install -y live-build python3 calamares calamares-settings-debian syslinux

# Create working directory
echo "Setting up live-build workspace..."
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Clean previous build
sudo lb clean

# Configure live-build
echo "Configuring live-build for Debian Bookworm (32-bit)..."
lb config --distribution=bookworm --architectures=i386 \
    --linux-packages=linux-image \
    --debian-installer=live \
    --bootappend-live="boot=live components hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr"

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
python3-tk
dosfstools
firmware-linux-free
firmware-linux-nonfree
calamares
calamares-settings-debian
squashfs-tools
xorg
xfce4
xfce4-power-manager
network-manager
network-manager-gnome
sudo
evince
live-boot
live-config
live-tools
tasksel
tasksel-data
console-setup
keyboard-configuration
cryptsetup
dmsetup
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
cat << EOF > config/includes.chroot/etc/default/keyboard
XKBMODEL="pc105"
XKBLAYOUT="fr"
XKBVARIANT="azerty"
XKBOPTIONS=""
EOF

# Set console keymap for tty
cat << EOF > config/includes.chroot/etc/default/console-setup
ACTIVE_CONSOLES="/dev/tty[1-6]"
CHARMAP="UTF-8"
CODESET="Lat15"
XKBLAYOUT="fr"
XKBVARIANT="azerty"
EOF

# Disable all power management and suspend features
echo "Disabling power management and suspend..."
mkdir -p config/includes.chroot/etc/systemd/logind.conf.d/
cat << EOF > config/includes.chroot/etc/systemd/logind.conf.d/no-suspend.conf
[Login]
HandleSuspendKey=ignore
HandleHibernateKey=ignore
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF

# Disable systemd sleep targets
mkdir -p config/includes.chroot/etc/systemd/sleep.conf.d/
cat << EOF > config/includes.chroot/etc/systemd/sleep.conf.d/no-sleep.conf
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
EOF

# Create systemd override to mask suspend/hibernate targets
mkdir -p config/includes.chroot/etc/systemd/system/sleep.target.d/
cat << EOF > config/includes.chroot/etc/systemd/system/sleep.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

mkdir -p config/includes.chroot/etc/systemd/system/suspend.target.d/
cat << EOF > config/includes.chroot/etc/systemd/system/suspend.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

mkdir -p config/includes.chroot/etc/systemd/system/hibernate.target.d/
cat << EOF > config/includes.chroot/etc/systemd/system/hibernate.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

mkdir -p config/includes.chroot/etc/systemd/system/hybrid-sleep.target.d/
cat << EOF > config/includes.chroot/etc/systemd/system/hybrid-sleep.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

# Configure XFCE Power Manager to never suspend
mkdir -p config/includes.chroot/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/
cat << 'EOF' > config/includes.chroot/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-power-manager" version="1.0">
  <property name="xfce4-power-manager" type="empty">
    <property name="power-button-action" type="uint" value="3"/>
    <property name="show-tray-icon" type="bool" value="true"/>
    <property name="logind-handle-lid-switch" type="bool" value="false"/>
    <property name="dpms-enabled" type="bool" value="false"/>
    <property name="blank-on-ac" type="int" value="0"/>
    <property name="blank-on-battery" type="int" value="0"/>
    <property name="dpms-on-ac-sleep" type="uint" value="0"/>
    <property name="dpms-on-ac-off" type="uint" value="0"/>
    <property name="dpms-on-battery-sleep" type="uint" value="0"/>
    <property name="dpms-on-battery-off" type="uint" value="0"/>
    <property name="brightness-on-ac" type="uint" value="9"/>
    <property name="brightness-on-battery" type="uint" value="9"/>
    <property name="inactivity-on-ac" type="uint" value="0"/>
    <property name="inactivity-on-battery" type="uint" value="0"/>
    <property name="inactivity-sleep-mode-on-ac" type="uint" value="1"/>
    <property name="inactivity-sleep-mode-on-battery" type="uint" value="1"/>
    <property name="lid-action-on-ac" type="uint" value="0"/>
    <property name="lid-action-on-battery" type="uint" value="0"/>
    <property name="lock-screen-suspend-hibernate" type="bool" value="false"/>
    <property name="critical-power-action" type="uint" value="1"/>
  </property>
</channel>
EOF

# Disable screen blanking and DPMS
mkdir -p config/includes.chroot/etc/X11/xorg.conf.d/
cat << EOF > config/includes.chroot/etc/X11/xorg.conf.d/10-monitor.conf
Section "ServerFlags"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection

Section "Monitor"
    Identifier "LVDS0"
    Option "DPMS" "false"
EndSection
EOF

# Copy all files from CODE_DIR to /usr/local/bin
echo "Copying all files from $CODE_DIR to /usr/local/bin..."
mkdir -p config/includes.chroot/usr/local/bin/
cp -r "$CODE_DIR"/* config/includes.chroot/usr/local/bin/
chmod +x config/includes.chroot/usr/local/bin/*

# Create symbolic link 'de' -> main.py
ln -s /usr/local/bin/main.py config/includes.chroot/usr/local/bin/de

# Allow sudo without password
echo "Configuring sudo to be passwordless..."
mkdir -p config/includes.chroot/etc/sudoers.d/
echo "user ALL=(ALL) NOPASSWD: ALL" > config/includes.chroot/etc/sudoers.d/passwordless
chmod 0440 config/includes.chroot/etc/sudoers.d/passwordless

# Create USB flash drive udev rules
echo "Creating USB flash drive udev rules..."
mkdir -p config/includes.chroot/etc/udev/rules.d/
cat << 'EOF' > config/includes.chroot/etc/udev/rules.d/usb-flash.rules
# Try to catch USB flash drives and set them as non-rotational. Probably no impact whatsoever : /
# c.f. https://mpdesouza.com/blog/kernel-adventures-are-usb-sticks-rotational-devices/

# Device is already marked as non-rotational, skip over it
ATTR{queue/rotational}=="0", GOTO="skip"

# Device has some sort of queue support, likely to be an HDD actually
ATTRS{queue_type}!="none", GOTO="skip"

# Flip the rotational bit on this removable device and give audible signs of having caught a match
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", ATTR{queue/rotational}="0"
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", RUN+="/bin/beep -f 70 -r 2"

LABEL="skip"
EOF

# Create application launcher for the installed version
echo "Creating application launcher..."
mkdir -p config/includes.chroot/usr/share/applications/
cat << EOF > config/includes.chroot/usr/share/applications/secure_disk_eraser.desktop
[Desktop Entry]
Version=1.0
Name=Secure Disk Eraser
Comment=Securely erase disks and partitions
Exec=sudo /usr/local/bin/de
Icon=drive-harddisk
Terminal=true
Type=Application
Categories=System;Security;
Keywords=disk;erase;secure;wipe;
EOF

# Make the launcher executable
chmod +x config/includes.chroot/usr/share/applications/secure_disk_eraser.desktop

# Auto-start in live mode - Create XFCE autostart
mkdir -p config/includes.chroot/etc/xdg/autostart/
cat << EOF > config/includes.chroot/etc/xdg/autostart/disk-eraser.desktop
[Desktop Entry]
Type=Application
Name=Disk Eraser
Comment=Start Disk Eraser automatically in live mode
Exec=sudo /usr/local/bin/de
Terminal=true
Icon=drive-harddisk
Categories=System;Security;
OnlyShowIn=XFCE;
EOF

# Configure .bashrc to run main.py on login in live mode but not in installed mode
echo "Configuring .bashrc to run main.py in live mode..."
mkdir -p config/includes.chroot/etc/skel/
cat << 'EOF' > config/includes.chroot/etc/skel/.bashrc
# Source global definitions
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

# Display information about the disk eraser
echo "Secure Disk Eraser"
echo "Type 'sudo de' to use the Secure Disk Eraser program"

# Check if we're in live mode
if grep -q "boot=live" /proc/cmdline; then
    # Only auto-start in terminals when in live mode
    if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
        echo "Live mode detected. Starting disk eraser..."
        sudo /usr/local/bin/de
    fi
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
mv live-image-i386.hybrid.iso "$ISO_NAME"

# Cleanup
sudo lb clean

echo "Done. ISO created at: $ISO_NAME"