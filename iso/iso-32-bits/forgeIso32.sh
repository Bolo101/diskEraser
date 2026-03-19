#!/bin/bash

# Exit on any error
set -e

# Variables
ISO_NAME="$(pwd)/diskEraser-v6.0-32bits.iso"
WORK_DIR="$(pwd)/debian-live-build"
CODE_DIR="$(pwd)/../../code"

echo "Installing live-build and required dependencies..."
sudo apt update
sudo apt install -y live-build python3 syslinux isolinux

echo "Setting up live-build workspace..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

sudo lb clean --purge || true

echo "Configuring live-build for Debian bullseye i386..."
lb config \
  --distribution=bullseye \
  --architectures=i386 \
  --linux-packages=linux-image \
  --linux-flavours=686 \$\n  --debian-installer=none \
  --bootappend-live="boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr" \
  --bootloaders="syslinux" \
  --binary-images=iso-hybrid
# NOTE: --debian-installer=none avoids the live-build bug on i386/bullseye:
#   "flAbsPath on localArchive/aptdir/.../dpkg/status failed (realpath: ...)"
# Our custom install-to-disk.sh replaces the Debian installer entirely.

# Repositories
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
squashfs-tools
xorg
xserver-xorg-video-all
xserver-xorg-video-intel
xserver-xorg-video-ati
xserver-xorg-video-nouveau
xserver-xorg-video-vesa
xserver-xorg-video-fbdev
xserver-xorg-input-all
openbox
lightdm
xterm
rsync
grub-common
grub-pc-bin
grub-efi-ia32-bin
os-prober
network-manager
sudo
evince
live-boot
live-config
live-tools
console-setup
keyboard-configuration
systemd
pciutils
usbutils
acpi
EOF

echo "Configuring French AZERTY keyboard..."
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

for target in sleep suspend hibernate hybrid-sleep; do
  mkdir -p "config/includes.chroot/etc/systemd/system/${target}.target.d/"
  cat << EOF > "config/includes.chroot/etc/systemd/system/${target}.target.d/override.conf"
[Unit]
ConditionPathExists=/dev/null
EOF
done

echo "Disabling screen blanking..."
mkdir -p config/includes.chroot/etc/X11/xorg.conf.d/
cat << 'EOF' > config/includes.chroot/etc/X11/xorg.conf.d/10-monitor.conf
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

echo "Copying application files..."
mkdir -p config/includes.chroot/usr/local/bin/
cp -r "${CODE_DIR}"/* config/includes.chroot/usr/local/bin/ 2>/dev/null || true
chmod +x config/includes.chroot/usr/local/bin/* 2>/dev/null || true
cat << 'WRAPPER' > config/includes.chroot/usr/local/bin/de
#!/bin/bash
exec python3 /usr/local/bin/main.py "$@"
WRAPPER
chmod +x config/includes.chroot/usr/local/bin/de
mkdir -p config/includes.chroot/etc/sudoers.d/
echo "user ALL=(ALL) NOPASSWD: ALL" > config/includes.chroot/etc/sudoers.d/passwordless
chmod 0440 config/includes.chroot/etc/sudoers.d/passwordless

mkdir -p config/includes.chroot/etc/udev/rules.d/
cat << 'EOF' > config/includes.chroot/etc/udev/rules.d/usb-flash.rules
ATTR{queue/rotational}=="0", GOTO="skip"
ATTRS{queue_type}!="none", GOTO="skip"
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", ATTR{queue/rotational}="0"
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", RUN+="/bin/beep -f 70 -r 2"
LABEL="skip"
EOF

# ── KIOSK SESSION ──────────────────────────────────────────────────────────
echo "Configuring openbox kiosk session..."
mkdir -p config/includes.chroot/etc/xdg/openbox/
cat << 'EOF' > config/includes.chroot/etc/xdg/openbox/rc.xml
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc"
                xmlns:xi="http://www.w3.org/2001/XInclude">
  <applications>
    <application class="*">
      <fullscreen>yes</fullscreen>
      <decor>no</decor>
      <maximized>yes</maximized>
      <layer>above</layer>
    </application>
  </applications>
</openbox_config>
EOF
cat << 'EOF' > config/includes.chroot/usr/local/bin/de-session.sh
#!/bin/bash
xset s off -dpms 2>/dev/null || true
xset s noblank   2>/dev/null || true
openbox &
WM_PID=$!
sleep 1
if grep -q "installer=1" /proc/cmdline; then
    xterm -title "Disk Eraser Installer" -fa "Monospace" -fs 12 \n          -e "sudo /usr/local/bin/install-to-disk.sh"
else
    sudo /usr/local/bin/de
fi
kill "$WM_PID" 2>/dev/null || true
EOF
chmod +x config/includes.chroot/usr/local/bin/de-session.sh

mkdir -p config/includes.chroot/usr/share/xsessions/
cat << 'EOF' > config/includes.chroot/usr/share/xsessions/disk-eraser-kiosk.desktop
[Desktop Entry]
Name=Disk Eraser (Kiosk)
Comment=Launch Disk Eraser fullscreen, no desktop
Exec=/usr/local/bin/de-session.sh
Type=Application
EOF

mkdir -p config/includes.chroot/etc/lightdm/lightdm.conf.d/
cat << 'EOF' > config/includes.chroot/etc/lightdm/lightdm.conf.d/50-autologin.conf
[Seat:*]
autologin-user=user
autologin-session=disk-eraser-kiosk
autologin-user-timeout=0
EOF

mkdir -p config/includes.chroot/etc/skel/
cat << 'EOF' > config/includes.chroot/etc/skel/.dmrc
[Desktop]
Session=disk-eraser-kiosk
EOF

cat << 'EOF' > config/includes.chroot/etc/skel/.bashrc
if [ -f /etc/bashrc ]; then
  . /etc/bashrc
fi
echo "Disk Eraser (32-bit)"
echo "Type 'sudo de' to use the program"
EOF

# ── DISK INSTALLER ─────────────────────────────────────────────────────────
echo "Writing disk installer..."
cat << 'INSTALLER' > config/includes.chroot/usr/local/bin/install-to-disk.sh
#!/bin/bash
set -e
TITLE="Disk Eraser — Installer (32-bit)"
TARGET_MNT="/mnt/install-target"

if [ "$(id -u)" -ne 0 ]; then exec sudo "$0" "$@"; fi

whiptail --title "$TITLE" --msgbox \
"Welcome to the installer.

This will copy the live system to a disk of your choice.
The installed system will boot directly into the application,
exactly like this live environment.

WARNING: all data on the selected disk will be erased." \
14 64

LIVE_DEV=$(lsblk -no PKNAME "$(findmnt -n -o SOURCE /run/live/medium 2>/dev/null)" 2>/dev/null || true)

DISK_MENU=()
while read -r name size model; do
    [ "$name" = "$LIVE_DEV" ] && continue
    [[ "$name" == loop* ]] && continue
    [[ "$name" == sr*   ]] && continue
    DISK_MENU+=("/dev/$name" "$(printf '%-8s %s' "$size" "$model")")
done < <(lsblk -dn -o NAME,SIZE,MODEL 2>/dev/null)

if [ "${#DISK_MENU[@]}" -eq 0 ]; then
    whiptail --title "$TITLE" --msgbox \
"No suitable target disk found.
Please connect a target disk and restart the installer." 8 60
    exit 1
fi

TARGET=$(whiptail --title "$TITLE" \
    --menu "Select the disk to install to:" \
    20 64 10 "${DISK_MENU[@]}" \
    3>&1 1>&2 2>&3) || { echo "Installer cancelled."; exit 0; }

whiptail --title "$TITLE" --yesno \
"FINAL WARNING

All data on $TARGET will be permanently erased.

Proceed with installation?" \
10 60 || { echo "Installer cancelled."; exit 0; }

UEFI=0
[ -d /sys/firmware/efi ] && UEFI=1

whiptail --title "$TITLE" --infobox "Partitioning $TARGET..." 5 50
wipefs -a "$TARGET"
if [ "$UEFI" -eq 1 ]; then
    parted -s "$TARGET" mklabel gpt
    parted -s "$TARGET" mkpart ESP  fat32  1MiB 513MiB
    parted -s "$TARGET" set 1 esp on
    parted -s "$TARGET" mkpart root ext4  513MiB 100%
    EFI_PART="${TARGET}1"
    ROOT_PART="${TARGET}2"
else
    parted -s "$TARGET" mklabel msdos
    parted -s "$TARGET" mkpart primary ext4 1MiB 100%
    parted -s "$TARGET" set 1 boot on
    ROOT_PART="${TARGET}1"
fi

whiptail --title "$TITLE" --infobox "Formatting partitions..." 5 50
mkfs.ext4 -F "$ROOT_PART"
[ "$UEFI" -eq 1 ] && mkfs.fat -F32 "$EFI_PART"

whiptail --title "$TITLE" --infobox "Mounting target filesystem..." 5 50
mkdir -p "$TARGET_MNT"
mount "$ROOT_PART" "$TARGET_MNT"
[ "$UEFI" -eq 1 ] && { mkdir -p "$TARGET_MNT/boot/efi"; mount "$EFI_PART" "$TARGET_MNT/boot/efi"; }

whiptail --title "$TITLE" --infobox "Copying system (this may take several minutes)..." 5 56
rsync -aHAX \
    --exclude=/proc --exclude=/sys --exclude=/dev --exclude=/run \
    --exclude=/mnt  --exclude=/media --exclude=/tmp --exclude=/live \
    / "$TARGET_MNT"/

mkdir -p "$TARGET_MNT"/{proc,sys,dev,run,mnt,media,tmp}
chmod 1777 "$TARGET_MNT/tmp"

ROOT_UUID=$(blkid -s UUID -o value "$ROOT_PART")
{
    echo "UUID=$ROOT_UUID  /          ext4  errors=remount-ro  0  1"
    if [ "$UEFI" -eq 1 ]; then
        EFI_UUID=$(blkid -s UUID -o value "$EFI_PART")
        echo "UUID=$EFI_UUID  /boot/efi  vfat  umask=0077         0  1"
    fi
    echo "tmpfs  /tmp  tmpfs  defaults,nosuid,nodev  0  0"
} > "$TARGET_MNT/etc/fstab"

whiptail --title "$TITLE" --infobox "Installing bootloader..." 5 50
mount --bind /dev  "$TARGET_MNT/dev"
mount --bind /proc "$TARGET_MNT/proc"
mount --bind /sys  "$TARGET_MNT/sys"
if [ "$UEFI" -eq 1 ]; then
    mount --bind /sys/firmware/efi/efivars "$TARGET_MNT/sys/firmware/efi/efivars" 2>/dev/null || true
    chroot "$TARGET_MNT" grub-install \
        --target=i386-efi \
        --efi-directory=/boot/efi \
        --bootloader-id=DiskEraser \
        --recheck
else
    chroot "$TARGET_MNT" grub-install --target=i386-pc --recheck "$TARGET"
fi

cat > "$TARGET_MNT/etc/default/grub" << 'GRUBCFG'
GRUB_DEFAULT=0
GRUB_TIMEOUT=3
GRUB_DISTRIBUTOR="Kiosk System"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
GRUB_CMDLINE_LINUX=""
GRUBCFG

chroot "$TARGET_MNT" update-grub

umount "$TARGET_MNT/sys/firmware/efi/efivars" 2>/dev/null || true
umount "$TARGET_MNT/dev"
umount "$TARGET_MNT/proc"
umount "$TARGET_MNT/sys"
[ "$UEFI" -eq 1 ] && umount "$TARGET_MNT/boot/efi"
umount "$TARGET_MNT"

whiptail --title "$TITLE" --msgbox \
"Installation complete!

The system has been installed to $TARGET.
Remove the live USB/CD and press OK to reboot." \
10 60

reboot
INSTALLER
chmod +x config/includes.chroot/usr/local/bin/install-to-disk.sh

# ── BOOT MENU ──────────────────────────────────────────────────────────────
echo "Configuring boot menu..."
mkdir -p config/includes.binary/isolinux
cat << 'EOF' > config/includes.binary/isolinux/isolinux.cfg
UI vesamenu.c32
DEFAULT live
TIMEOUT 100

MENU TITLE Disk Eraser (32-bit) - Boot Menu

LABEL live
  MENU LABEL Start (Live)
  MENU DEFAULT
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live config components

LABEL install
  MENU LABEL Install to Disk
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live config components installer=1

LABEL live-safe
  MENU LABEL Start Live - Safe Mode (nomodeset)
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live config components nomodeset
EOF

echo "Building the ISO..."
sudo lb build

if [ -f live-image-i386.hybrid.iso ]; then
  mv live-image-i386.hybrid.iso "$ISO_NAME"
elif [ -f live-image-i386.iso ]; then
  mv live-image-i386.iso "$ISO_NAME"
else
  echo "ERROR: Could not find generated ISO file"; exit 1
fi

sudo lb clean
echo "Done. ISO created at: $ISO_NAME"