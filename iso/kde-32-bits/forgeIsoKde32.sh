#!/bin/bash

# Exit on any error
set -e

# ISO name and working directory
ISO_NAME="$(pwd)/diskEraser-v5.4-KDE-32bits.iso"
WORK_DIR="$(pwd)/debian-live-build"
CODE_DIR="$(pwd)/../../code"

echo "Installing live-build and required dependencies..."
sudo apt update
sudo apt install -y live-build python3 calamares calamares-settings-debian syslinux isolinux

echo "Setting up live-build workspace..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

sudo lb clean --purge || true

echo "Configuring live-build for Debian Bullseye i386..."
lb config \
  --distribution=bullseye \
  --architectures=i386 \
  --linux-packages=linux-image \
  --linux-flavours=686 \
  --debian-installer=live \
  --bootappend-live="boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr" \
  --bootloaders="syslinux" \
  --binary-images=iso-hybrid

# Repositories in chroot
mkdir -p config/archives
cat << 'EOF' > config/archives/debian.list.chroot
deb http://deb.debian.org/debian bullseye main contrib non-free
deb-src http://deb.debian.org/debian bullseye main contrib non-free
deb http://security.debian.org/debian-security bullseye-security main contrib non-free
deb-src http://security.debian.org/debian-security bullseye-security main contrib non-free
EOF

echo "Adding required packages..."
mkdir -p config/package-lists/
cat << 'EOF' > config/package-lists/custom.list.chroot
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
kde-plasma-desktop
kde-standard
plasma-nm
sddm
sudo
evince
live-boot
live-config
live-tools
console-setup
keyboard-configuration
cryptsetup
dmsetup
systemd
xserver-xorg-video-all
xserver-xorg-video-intel
xserver-xorg-video-ati
xserver-xorg-video-nouveau
xserver-xorg-video-vesa
xserver-xorg-video-fbdev
xserver-xorg-input-all
pciutils
usbutils
acpi
EOF

echo "Configuring live system for French AZERTY keyboard..."
mkdir -p config/includes.chroot/etc/default/
cat << 'EOF' > config/includes.chroot/etc/default/locale
LANG=fr_FR.UTF-8
LC_ALL=fr_FR.UTF-8
EOF

cat << 'EOF' > config/includes.chroot/etc/default/keyboard
XKBMODEL="pc105"
XKBLAYOUT="fr"
XKBVARIANT="azerty"
XKBOPTIONS=""
EOF

cat << 'EOF' > config/includes.chroot/etc/default/console-setup
ACTIVE_CONSOLES="/dev/tty[1-6]"
CHARMAP="UTF-8"
CODESET="Lat15"
XKBLAYOUT="fr"
XKBVARIANT="azerty"
EOF

echo "Disabling power management and suspend..."
mkdir -p config/includes.chroot/etc/systemd/logind.conf.d/
cat << 'EOF' > config/includes.chroot/etc/systemd/logind.conf.d/no-suspend.conf
[Login]
HandleSuspendKey=ignore
HandleHibernateKey=ignore
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF

mkdir -p config/includes.chroot/etc/systemd/sleep.conf.d/
cat << 'EOF' > config/includes.chroot/etc/systemd/sleep.conf.d/no-sleep.conf
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
EOF

mkdir -p config/includes.chroot/etc/systemd/system/sleep.target.d/
cat << 'EOF' > config/includes.chroot/etc/systemd/system/sleep.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

mkdir -p config/includes.chroot/etc/systemd/system/suspend.target.d/
cat << 'EOF' > config/includes.chroot/etc/systemd/system/suspend.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

mkdir -p config/includes.chroot/etc/systemd/system/hibernate.target.d/
cat << 'EOF' > config/includes.chroot/etc/systemd/system/hibernate.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

mkdir -p config/includes.chroot/etc/systemd/system/hybrid-sleep.target.d/
cat << 'EOF' > config/includes.chroot/etc/systemd/system/hybrid-sleep.target.d/override.conf
[Unit]
ConditionPathExists=/dev/null
EOF

echo "Disabling screen blanking..."
mkdir -p config/includes.chroot/etc/xdg
cat << 'EOF' > config/includes.chroot/etc/xdg/powerdevilrc
[General]
chargeStartThreshold=0
chargeStopThreshold=0

[AC]
BrightnessControl=0
BrightnessControlBehavior=0
DPMSControlBehavior=0
PowerButtonAction=1
SuspendSession=-1

[Battery]
BrightnessControl=0
BrightnessControlBehavior=0
DPMSControlBehavior=0
PowerButtonAction=1
SuspendSession=-1
EOF

mkdir -p config/includes.chroot/etc/X11/xorg.conf.d/
cat << 'EOF' > config/includes.chroot/etc/X11/xorg.conf.d/10-monitor.conf
Section "ServerFlags"
  Option "BlankTime" "0"
  Option "StandbyTime" "0"
  Option "SuspendTime" "0"
  Option "OffTime" "0"
EndSection
EOF

echo "Copying application files..."
mkdir -p config/includes.chroot/usr/local/bin/
cp -r "${CODE_DIR}"/* config/includes.chroot/usr/local/bin/ 2>/dev/null || true
chmod +x config/includes.chroot/usr/local/bin/* 2>/dev/null || true
ln -sf /usr/local/bin/main.py config/includes.chroot/usr/local/bin/de 2>/dev/null || true

mkdir -p config/includes.chroot/etc/sudoers.d/
echo "user ALL=(ALL) NOPASSWD: ALL" > config/includes.chroot/etc/sudoers.d/passwordless
chmod 0440 config/includes.chroot/etc/sudoers.d/passwordless

mkdir -p config/includes.chroot/etc/udev/rules.d/
cat << 'EOF' > config/includes.chroot/etc/udev/rules.d/usb-flash.rules
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", ATTR{queue/rotational}="0"
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", RUN+="/bin/beep -f 70 -r 2"
EOF

mkdir -p config/includes.chroot/usr/share/applications/
cat << 'EOF' > config/includes.chroot/usr/share/applications/secure_disk_eraser.desktop
[Desktop Entry]
Version=1.0
Name=Secure Disk Eraser
Comment=Securely erase disks and partitions
Exec=sudo /usr/local/bin/de
Icon=drive-harddisk
Terminal=false
Type=Application
Categories=System;Security;
Keywords=disk;erase;secure;wipe;
EOF

mkdir -p config/includes.chroot/etc/xdg/autostart/
cat << 'EOF' > config/includes.chroot/etc/xdg/autostart/disk-eraser.desktop
[Desktop Entry]
Type=Application
Name=Disk Eraser
Comment=Start Disk Eraser automatically in live mode
Exec=sudo /usr/local/bin/de
Terminal=false
Icon=drive-harddisk
Categories=System;Security;
OnlyShowIn=KDE;
EOF

mkdir -p config/includes.chroot/etc/skel/
cat << 'EOF' > config/includes.chroot/etc/skel/.bashrc
if [ -f /etc/bashrc ]; then
  . /etc/bashrc
fi

echo "Secure Disk Eraser"
echo "Type 'sudo de' to use the Secure Disk Eraser program"

if grep -q "boot=live" /proc/cmdline; then
  if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    echo "Live mode detected. Starting Secure Disk Eraser..."
    sudo /usr/local/bin/de &
    sleep 2
    exit 0
  fi
fi
EOF

mkdir -p config/includes.chroot/etc/kbd/
cat << 'EOF' > config/includes.chroot/etc/kbd/config
SCREEN_BLANKING=0
EOF

echo "Configuring boot menu..."
mkdir -p config/includes.binary/isolinux
cat << 'EOF' > config/includes.binary/isolinux/isolinux.cfg
UI vesamenu.c32
DEFAULT live
TIMEOUT 50

MENU TITLE Secure Disk Eraser (32-bit KDE) - Boot Menu

LABEL live
  MENU LABEL Start Live Environment
  MENU DEFAULT
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live config components

LABEL live-safe
  MENU LABEL Start Live Environment - Safe Mode (nomodeset)
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live config components nomodeset

LABEL install
  MENU LABEL Install to Disk
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live config components calamares
EOF

mkdir -p config/includes.chroot/etc/profile.d/
cat << 'EOF' > config/includes.chroot/etc/profile.d/autostart-calamares.sh
#!/bin/bash
if grep -q "calamares" /proc/cmdline; then
  calamares --debug
fi
EOF
chmod +x config/includes.chroot/etc/profile.d/autostart-calamares.sh

echo "Building the ISO..."
sudo lb build

if [ -f live-image-i386.hybrid.iso ]; then
  mv live-image-i386.hybrid.iso "$ISO_NAME"
elif [ -f live-image-i386.iso ]; then
  mv live-image-i386.iso "$ISO_NAME"
else
  echo "ERROR: Could not find generated ISO file"
  exit 1
fi

sudo lb clean
echo "Done. ISO created at: $ISO_NAME"