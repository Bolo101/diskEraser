#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  forgeIso64.sh – Construction de l'ISO dual-boot Disk Eraser               ║
# ║                                                                             ║
# ║  Entrée 1 : Live       → OpenBox kiosque  (code/)                          ║
# ║  Entrée 2 : Installer  → installe sur disque avec XFCE kiosque             ║
# ║             Le système installé utilise code_installer/ et XFCE            ║
# ║  Entrée 3 : Live Safe  → Live + nomodeset                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

set -e

# ── Variables ──────────────────────────────────────────────────────────────────
ISO_NAME="$(pwd)/diskEraser-v6.0-64bits.iso"
WORK_DIR="$(pwd)/debian-live-build"
CODE_DIR="$(pwd)/../../code"
CODE_INSTALLER_DIR="$(pwd)/../../code_installer"

echo "=== Installation des dépendances ==="
sudo apt update
sudo apt install -y live-build python3 syslinux isolinux xorriso rsync

echo "=== Mise en place du workspace live-build ==="
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

sudo lb clean --purge || true

echo "=== Configuration live-build (Debian bookworm amd64) ==="
lb config \
  --distribution=bookworm \
  --architectures=amd64 \
  --linux-packages=linux-image \
  --debian-installer=none \
  --bootappend-live="boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr" \
  --bootloaders="syslinux" \
  --binary-images=iso-hybrid

# ── Dépôts ─────────────────────────────────────────────────────────────────────
mkdir -p config/archives
cat << 'EOF' > config/archives/debian.list.chroot
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
deb-src http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
EOF

# ── Paquets ────────────────────────────────────────────────────────────────────
echo "=== Déclaration des paquets ==="
mkdir -p config/package-lists/
cat << 'EOF' > config/package-lists/custom.list.chroot
# ── Système de base ──
coreutils
parted
ntfs-3g
python3
python3-tk
dosfstools
cryptsetup
util-linux
udev
pciutils
usbutils
acpi
sudo
rsync
grub-common
grub-pc-bin
grub-efi-amd64-bin
grub-pc
os-prober
whiptail
# ── Firmware ──
firmware-linux-free
firmware-linux-nonfree
# ── Affichage ──
xorg
xserver-xorg-video-all
xserver-xorg-video-intel
xserver-xorg-video-ati
xserver-xorg-video-nouveau
xserver-xorg-video-vesa
xserver-xorg-video-fbdev
xserver-xorg-input-all
# ── Live mode : OpenBox ──
openbox
lightdm
xterm
# ── Installed mode : XFCE minimal ──
xfce4-session
xfwm4
xfce4-terminal
# ── Live system ──
live-boot
live-config
live-tools
squashfs-tools
# ── Locale ──
console-setup
keyboard-configuration
systemd
# ── Visionneuse PDF (admin) ──
evince
# ── Réseau ──
network-manager
EOF

# ── Locale française ───────────────────────────────────────────────────────────
echo "=== Configuration AZERTY fr_FR ==="
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

# ── Anti-veille / anti-écran noir ─────────────────────────────────────────────
echo "=== Désactivation de la mise en veille ==="
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

# ── Code Live (mode live → /usr/local/bin/) ───────────────────────────────────
echo "=== Copie du code live ==="
mkdir -p config/includes.chroot/usr/local/bin/
cp -r "${CODE_DIR}"/* config/includes.chroot/usr/local/bin/ 2>/dev/null || true
chmod +x config/includes.chroot/usr/local/bin/*.py 2>/dev/null || true

cat << 'WRAPPER' > config/includes.chroot/usr/local/bin/de
#!/bin/bash
exec python3 /usr/local/bin/main.py "$@"
WRAPPER
chmod +x config/includes.chroot/usr/local/bin/de

# ── Code Installer (mode installé → /usr/local/bin_installer/) ───────────────
echo "=== Copie du code installer ==="
mkdir -p config/includes.chroot/usr/local/bin_installer/
cp -r "${CODE_INSTALLER_DIR}"/* config/includes.chroot/usr/local/bin_installer/ 2>/dev/null || true
chmod +x config/includes.chroot/usr/local/bin_installer/*.py 2>/dev/null || true

cat << 'WRAPPER' > config/includes.chroot/usr/local/bin_installer/de-installer
#!/bin/bash
exec python3 /usr/local/bin_installer/main.py "$@"
WRAPPER
chmod +x config/includes.chroot/usr/local/bin_installer/de-installer

# Crée les répertoires nécessaires (seront recréés au boot, mais utile en live)
mkdir -p config/includes.chroot/var/log/disk_eraser/pdf/
mkdir -p config/includes.chroot/var/lib/disk_eraser/
mkdir -p config/includes.chroot/etc/disk_eraser/

# ── Sudo sans mot de passe pour l'utilisateur live ───────────────────────────
mkdir -p config/includes.chroot/etc/sudoers.d/
echo "user ALL=(ALL) NOPASSWD: ALL" > config/includes.chroot/etc/sudoers.d/passwordless
chmod 0440 config/includes.chroot/etc/sudoers.d/passwordless

# ── Règle udev USB ────────────────────────────────────────────────────────────
mkdir -p config/includes.chroot/etc/udev/rules.d/
cat << 'EOF' > config/includes.chroot/etc/udev/rules.d/usb-flash.rules
ATTR{queue/rotational}=="0", GOTO="skip"
ATTRS{queue_type}!="none", GOTO="skip"
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", ATTR{queue/rotational}="0"
LABEL="skip"
EOF

# ════════════════════════════════════════════════════════════════════════════════
# LIVE MODE – Session OpenBox kiosque
# ════════════════════════════════════════════════════════════════════════════════
echo "=== Configuration OpenBox kiosque (live) ==="

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
  <keyboard>
    <!-- Désactive Alt+F4 et autres raccourcis de gestion de fenêtre -->
    <keybind key="A-F4"><action name="Close"/></keybind>
  </keyboard>
</openbox_config>
EOF

# Script de session – dispatcher live / installer.
# LightDM appelle toujours CE script (session disk-eraser-live).
# Il lit /proc/cmdline pour brancher sur le bon mode.
cat << 'EOF' > config/includes.chroot/usr/local/bin/de-session-live.sh
#!/bin/bash
xset s off -dpms 2>/dev/null || true
xset s noblank   2>/dev/null || true
openbox &
WM_PID=$!
sleep 1

if grep -q "installer=1" /proc/cmdline; then
    # ── Mode installateur : script whiptail dans un xterm ──────────────────────
    xterm -title "Disk Eraser - Installateur" -fa "Monospace" -fs 12 \
          -e "sudo /usr/local/bin/install-to-disk.sh"
else
    # ── Mode live : borne de blanchiment standard ───────────────────────────────
    sudo /usr/local/bin/de
fi

kill "$WM_PID" 2>/dev/null || true
EOF
chmod +x config/includes.chroot/usr/local/bin/de-session-live.sh

# Session .desktop pour LightDM (live)
mkdir -p config/includes.chroot/usr/share/xsessions/
cat << 'EOF' > config/includes.chroot/usr/share/xsessions/disk-eraser-live.desktop
[Desktop Entry]
Name=Disk Eraser – Live
Comment=Borne de blanchiment (mode live)
Exec=/usr/local/bin/de-session-live.sh
Type=Application
EOF

# ════════════════════════════════════════════════════════════════════════════════
# INSTALLER MODE – Session XFCE kiosque (système installé)
# ════════════════════════════════════════════════════════════════════════════════
echo "=== Configuration XFCE kiosque (installer) ==="

# Script de session installé (XFCE minimal + app installeur)
cat << 'EOF' > config/includes.chroot/usr/local/bin/de-session-installer.sh
#!/bin/bash
# Désactive économiseur écran
xset s off -dpms 2>/dev/null || true
xset s noblank   2>/dev/null || true

# Démarre xfwm4 uniquement (pas de panel, pas de bureau)
xfwm4 --compositor=off &
WM_PID=$!
sleep 1

# Lance la borne de blanchiment installée
sudo /usr/local/bin_installer/de-installer

# Après fermeture de l'app (via admin), retour à un xterm root
xterm -title "Session administrateur" -fa "Monospace" -fs 12 &
kill "$WM_PID" 2>/dev/null || true
EOF
chmod +x config/includes.chroot/usr/local/bin/de-session-installer.sh

# Session .desktop pour LightDM (installé)
cat << 'EOF' > config/includes.chroot/usr/share/xsessions/disk-eraser-installer.desktop
[Desktop Entry]
Name=Disk Eraser – Borne installée
Comment=Borne de blanchiment (mode installé, kiosque XFCE)
Exec=/usr/local/bin/de-session-installer.sh
Type=Application
EOF

# ── LightDM : autologin sur la session live ───────────────────────────────────
mkdir -p config/includes.chroot/etc/lightdm/lightdm.conf.d/
cat << 'EOF' > config/includes.chroot/etc/lightdm/lightdm.conf.d/50-autologin.conf
[Seat:*]
autologin-user=user
autologin-session=disk-eraser-live
autologin-user-timeout=0
EOF

mkdir -p config/includes.chroot/etc/skel/
cat << 'EOF' > config/includes.chroot/etc/skel/.dmrc
[Desktop]
Session=disk-eraser-live
EOF

cat << 'EOF' > config/includes.chroot/etc/skel/.bashrc
if [ -f /etc/bashrc ]; then . /etc/bashrc; fi
echo "Borne de blanchiment Disk Eraser (64-bit)"
echo "  sudo de                     → mode live"
echo "  sudo de-installer           → mode installé (test)"
EOF

# ════════════════════════════════════════════════════════════════════════════════
# SCRIPT D'INSTALLATION SUR DISQUE
# Copie le système live sur le disque cible et configure la session XFCE kiosque.
# ════════════════════════════════════════════════════════════════════════════════
echo "=== Écriture du script d'installation ==="
cat << 'INSTALLER' > config/includes.chroot/usr/local/bin/install-to-disk.sh
#!/bin/bash
set -e

TITLE="Disk Eraser – Installation"
TARGET_MNT="/mnt/target"

# Fonction utilitaire : nom de partition selon le type de disque
part() {
    case "$1" in
        *nvme*|*mmcblk*) echo "${1}p${2}" ;;
        *)               echo "${1}${2}"  ;;
    esac
}

# ── Sélection du disque cible ──────────────────────────────────────────────────
DISKS=$(lsblk -d -o NAME,SIZE,MODEL -n | grep -v "^loop" || true)
if [ -z "$DISKS" ]; then
    whiptail --title "$TITLE" --msgbox "Aucun disque détecté." 8 50
    exit 1
fi

MENU_ARGS=()
while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    rest=$(echo "$line" | awk '{$1=""; print $0}' | xargs)
    MENU_ARGS+=("/dev/$name" "$rest")
done <<< "$DISKS"

TARGET=$(whiptail --title "$TITLE" --menu \
    "Choisir le disque d'installation :\n⚠  TOUTES LES DONNÉES SERONT EFFACÉES" \
    20 70 10 \
    "${MENU_ARGS[@]}" \
    3>&1 1>&2 2>&3) || { echo "Installation annulée."; exit 0; }

whiptail --title "$TITLE" --yesno \
"AVERTISSEMENT FINAL

Toutes les données sur $TARGET seront définitivement effacées.
Le système sera configuré en borne de blanchiment (kiosque XFCE).

Confirmer l'installation ?" \
12 60 || { echo "Installation annulée."; exit 0; }

# ── Détection UEFI / BIOS ──────────────────────────────────────────────────────
UEFI=0
[ -d /sys/firmware/efi ] && UEFI=1

# ── Partitionnement ───────────────────────────────────────────────────────────
whiptail --title "$TITLE" --infobox "Partitionnement de $TARGET..." 5 56
wipefs -a "$TARGET"

if [ "$UEFI" -eq 1 ]; then
    parted -s "$TARGET" mklabel gpt
    parted -s "$TARGET" mkpart ESP  fat32 1MiB 513MiB
    parted -s "$TARGET" set 1 esp on
    parted -s "$TARGET" mkpart root ext4 513MiB 100%
    EFI_PART="$(part "$TARGET" 1)"
    ROOT_PART="$(part "$TARGET" 2)"
else
    parted -s "$TARGET" mklabel msdos
    parted -s "$TARGET" mkpart primary ext4 1MiB 100%
    parted -s "$TARGET" set 1 boot on
    ROOT_PART="$(part "$TARGET" 1)"
fi

# ── Formatage ─────────────────────────────────────────────────────────────────
whiptail --title "$TITLE" --infobox "Formatage des partitions..." 5 50
mkfs.ext4 -F "$ROOT_PART"
[ "$UEFI" -eq 1 ] && mkfs.fat -F32 "$EFI_PART"

# ── Montage ───────────────────────────────────────────────────────────────────
whiptail --title "$TITLE" --infobox "Montage du système de fichiers cible..." 5 56
mkdir -p "$TARGET_MNT"
mount "$ROOT_PART" "$TARGET_MNT"
[ "$UEFI" -eq 1 ] && { mkdir -p "$TARGET_MNT/boot/efi"; mount "$EFI_PART" "$TARGET_MNT/boot/efi"; }

# ── Copie du système ──────────────────────────────────────────────────────────
whiptail --title "$TITLE" --infobox \
    "Copie du système (quelques minutes)..." 5 60
rsync -aHAX \
    --exclude=/proc   --exclude=/sys    --exclude=/dev  \
    --exclude=/run    --exclude=/mnt    --exclude=/media \
    --exclude=/tmp    --exclude=/live   \
    / "$TARGET_MNT"/

mkdir -p "$TARGET_MNT"/{proc,sys,dev,run,mnt,media,tmp}
chmod 1777 "$TARGET_MNT/tmp"

# ── fstab ─────────────────────────────────────────────────────────────────────
ROOT_UUID=$(blkid -s UUID -o value "$ROOT_PART")
{
    echo "UUID=$ROOT_UUID  /          ext4  errors=remount-ro  0  1"
    if [ "$UEFI" -eq 1 ]; then
        EFI_UUID=$(blkid -s UUID -o value "$EFI_PART")
        echo "UUID=$EFI_UUID  /boot/efi  vfat  umask=0077         0  1"
    fi
    echo "tmpfs  /tmp  tmpfs  defaults,nosuid,nodev  0  0"
} > "$TARGET_MNT/etc/fstab"

# ── Masquage des services live ────────────────────────────────────────────────
for svc in live-boot live-config live-tools; do
    chroot "$TARGET_MNT" systemctl mask "$svc" 2>/dev/null || true
done
rm -f "$TARGET_MNT/etc/live/boot.conf" 2>/dev/null || true

# ── Configuration LightDM : session XFCE kiosque installé ────────────────────
cat > "$TARGET_MNT/etc/lightdm/lightdm.conf.d/50-autologin.conf" << 'LIGHTDM_EOF'
[Seat:*]
autologin-user=user
autologin-session=disk-eraser-installer
autologin-user-timeout=0
LIGHTDM_EOF

# Le .dmrc pointe sur la session installée
cat > "$TARGET_MNT/etc/skel/.dmrc" << 'DMRC_EOF'
[Desktop]
Session=disk-eraser-installer
DMRC_EOF

# S'assure que le .dmrc de l'utilisateur existant est aussi à jour
[ -f "$TARGET_MNT/home/user/.dmrc" ] && \
cat > "$TARGET_MNT/home/user/.dmrc" << 'DMRC_EOF'
[Desktop]
Session=disk-eraser-installer
DMRC_EOF

# ── Création des répertoires persistants pour l'installé ─────────────────────
mkdir -p "$TARGET_MNT/var/log/disk_eraser/pdf/"
mkdir -p "$TARGET_MNT/var/lib/disk_eraser/"
mkdir -p "$TARGET_MNT/etc/disk_eraser/"
chmod 750 "$TARGET_MNT/var/log/disk_eraser/" \
          "$TARGET_MNT/var/lib/disk_eraser/" \
          "$TARGET_MNT/etc/disk_eraser/"

# ── GRUB ──────────────────────────────────────────────────────────────────────
cat > "$TARGET_MNT/etc/default/grub" << 'GRUBCFG'
GRUB_DEFAULT=0
GRUB_TIMEOUT=3
GRUB_DISTRIBUTOR="Disk Eraser – Borne de blanchiment"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
GRUB_CMDLINE_LINUX=""
GRUBCFG

whiptail --title "$TITLE" --infobox "Installation du chargeur d'amorçage..." 5 54
mount --bind /dev  "$TARGET_MNT/dev"
mount --bind /proc "$TARGET_MNT/proc"
mount --bind /sys  "$TARGET_MNT/sys"
[ "$UEFI" -eq 1 ] && \
    mount --bind /sys/firmware/efi/efivars \
                 "$TARGET_MNT/sys/firmware/efi/efivars" 2>/dev/null || true

if [ "$UEFI" -eq 1 ]; then
    chroot "$TARGET_MNT" grub-install \
        --target=x86_64-efi \
        --efi-directory=/boot/efi \
        --bootloader-id=DiskEraser \
        --recheck
else
    chroot "$TARGET_MNT" grub-install --target=i386-pc --recheck "$TARGET"
fi
chroot "$TARGET_MNT" update-grub

# ── Démontage ─────────────────────────────────────────────────────────────────
umount "$TARGET_MNT/sys/firmware/efi/efivars" 2>/dev/null || true
umount "$TARGET_MNT/sys"
umount "$TARGET_MNT/proc"
umount "$TARGET_MNT/dev"
[ "$UEFI" -eq 1 ] && umount "$TARGET_MNT/boot/efi"
umount "$TARGET_MNT"

whiptail --title "$TITLE" --msgbox \
"Installation terminée !

Le système Disk Eraser a été installé sur $TARGET
en mode kiosque XFCE.

Au démarrage :
  • L'interface de blanchiment se lance automatiquement.
  • Le panneau Administration (🔒) donne accès
    aux rapports, à l'export, et aux contrôles système.

Retirez la clé USB / le CD et appuyez sur OK pour redémarrer." \
16 65

reboot
INSTALLER
chmod +x config/includes.chroot/usr/local/bin/install-to-disk.sh

# ── Script de session pour le mode installer (depuis le live ISO) ─────────────
# (Le boot avec installer=1 lance le script whiptail d'installation)
cat << 'EOF' > config/includes.chroot/usr/local/bin/de-session.sh
#!/bin/bash
xset s off -dpms 2>/dev/null || true
xset s noblank   2>/dev/null || true
openbox &
WM_PID=$!
sleep 1

if grep -q "installer=1" /proc/cmdline; then
    xterm -title "Disk Eraser – Installateur" -fa "Monospace" -fs 12 \
          -e "sudo /usr/local/bin/install-to-disk.sh"
else
    sudo /usr/local/bin/de
fi

kill "$WM_PID" 2>/dev/null || true
EOF
chmod +x config/includes.chroot/usr/local/bin/de-session.sh

# ════════════════════════════════════════════════════════════════════════════════
# MENU DE DÉMARRAGE – injection AVANT lb build via config/includes.binary/
#
# POURQUOI includes.binary ET PAS seulement xorriso :
#   lb build empaquète config/includes.binary/ directement dans l'ISO.
#   C'est la méthode garantie : le fichier est présent à la fermeture de l'ISO.
#   xorriso est conservé en renfort pour s'assurer que live.cfg ne prend pas
#   le dessus via un éventuel INCLUDE dans d'autres fichiers syslinux.
# ════════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Injection du menu de démarrage (avant lb build) ==="
mkdir -p config/includes.binary/isolinux/

cat > config/includes.binary/isolinux/isolinux.cfg << 'MENU'
UI vesamenu.c32
DEFAULT live
TIMEOUT 150
PROMPT 0

MENU TITLE Disk Eraser v7.0 (64-bit) - Menu de demarrage

LABEL live
  MENU LABEL > Demarrer en mode Live (OpenBox kiosque)
  MENU DEFAULT
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr

LABEL install
  MENU LABEL > Installer la borne sur le disque dur
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr installer=1

LABEL live-safe
  MENU LABEL > Demarrer en mode Live - Sans echec (nomodeset)
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr nomodeset
MENU

# Neutralise live.cfg pour qu'il ne prenne pas le dessus via INCLUDE
echo "# replaced by custom boot menu" > config/includes.binary/isolinux/live.cfg

echo "  → isolinux.cfg et live.cfg injectés dans config/includes.binary/isolinux/"

# ════════════════════════════════════════════════════════════════════════════════
# BUILD ISO
# ════════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Construction de l'ISO (plusieurs minutes)… ==="
sudo lb build

# ════════════════════════════════════════════════════════════════════════════════
# PATCH DU MENU DE DÉMARRAGE VIA XORRISO
#
# L'ISO produite par lb build contient un menu syslinux par défaut.
# On le remplace par notre menu à 3 entrées :
#   1. Live (OpenBox kiosque)
#   2. Installer sur disque  [installer=1]
#   3. Live – sans échec     [nomodeset]
# ════════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Patch du menu de démarrage via xorriso ==="

# Localise l'ISO
BUILT_ISO=""
if   [ -f "live-image-amd64.hybrid.iso" ]; then BUILT_ISO="live-image-amd64.hybrid.iso"
elif [ -f "live-image-amd64.iso" ];        then BUILT_ISO="live-image-amd64.iso"
else
    echo "ERREUR : ISO introuvable après lb build"
    ls -lh ./*.iso 2>/dev/null || true
    exit 1
fi
echo "ISO source : $BUILT_ISO ($(du -h "$BUILT_ISO" | cut -f1))"

PATCH_DIR=$(mktemp -d)
trap 'rm -rf "$PATCH_DIR"' EXIT

# Inspecte les chemins réels dans l'ISO
echo "Inspection des chemins syslinux dans l'ISO…"
ISO_FILES=$(xorriso -indev "$BUILT_ISO" -find / -type f 2>/dev/null | grep '^/' || true)

ISO_ISOL_CFG=$(echo "$ISO_FILES" | grep -i 'isolinux\.cfg$' | head -1)
ISO_LIVE_CFG=$(echo "$ISO_FILES" | grep -i 'live\.cfg$'     | head -1)

[ -z "$ISO_ISOL_CFG" ] && ISO_ISOL_CFG="/isolinux/isolinux.cfg"
[ -z "$ISO_LIVE_CFG" ] && ISO_LIVE_CFG="/isolinux/live.cfg"

echo "  isolinux.cfg : $ISO_ISOL_CFG"
echo "  live.cfg     : $ISO_LIVE_CFG"

# Nouveau menu syslinux
cat > "$PATCH_DIR/isolinux.cfg" << 'MENU'
UI vesamenu.c32
DEFAULT live
TIMEOUT 150
PROMPT 0

MENU TITLE Disk Eraser v7.0 (64-bit) – Menu de démarrage

LABEL live
  MENU LABEL > Demarrer en mode Live (OpenBox kiosque)
  MENU DEFAULT
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr

LABEL install
  MENU LABEL > Installer la borne sur le disque dur
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr installer=1

LABEL live-safe
  MENU LABEL > Demarrer en mode Live – Sans echec (nomodeset)
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components config hostname=secure-eraser username=user locales=fr_FR.UTF-8 keyboard-layouts=fr nomodeset
MENU

echo "# replaced by custom boot menu" > "$PATCH_DIR/live.cfg"

# Application du patch
PATCHED_ISO="$PATCH_DIR/patched.iso"
echo "Application du patch xorriso…"
xorriso \
    -indev  "$BUILT_ISO" \
    -outdev "$PATCHED_ISO" \
    -boot_image any replay \
    -map "$PATCH_DIR/isolinux.cfg" "$ISO_ISOL_CFG" \
    -map "$PATCH_DIR/live.cfg"     "$ISO_LIVE_CFG"

# Vérification
ORIG_SIZE=$(stat -c%s "$BUILT_ISO")
PATCH_SIZE=$(stat -c%s "$PATCHED_ISO" 2>/dev/null || echo 0)

if [ "$PATCH_SIZE" -lt $(( ORIG_SIZE / 2 )) ]; then
    echo "ERREUR : L'ISO patchée est anormalement petite ($PATCH_SIZE vs $ORIG_SIZE octets)"
    echo "         L'ISO originale est conservée."
    exit 1
fi
echo "Patch OK : $ORIG_SIZE → $PATCH_SIZE octets"

# Vérification entrée installer
# NOTE : xorriso -extract vers /dev/stdout ne fonctionne pas (crée un fichier
#        littéralement nommé /dev/stdout). On extrait vers un fichier temporaire.
VERIFY_FILE="$PATCH_DIR/verify_isolinux.cfg"
xorriso -indev "$PATCHED_ISO" \
    -osirrox on \
    -extract "$ISO_ISOL_CFG" "$VERIFY_FILE" 2>/dev/null || true

if [ -f "$VERIFY_FILE" ] && grep -q "installer=1" "$VERIFY_FILE"; then
    echo "✓ Entrée 'Installer la borne sur le disque dur' confirmée dans l'ISO."
else
    echo "ATTENTION : L'entrée installer=1 n'a pas été trouvée dans l'ISO patchée."
    echo "Contenu extrait de $ISO_ISOL_CFG :"
    cat "$VERIFY_FILE" 2>/dev/null || echo "  (fichier vide ou non extrait)"
    echo ""
    echo "→ La méthode includes.binary garantit quand même la présence du menu."
    echo "  Vérifiez visuellement le menu au boot."
fi

mv "$PATCHED_ISO" "$BUILT_ISO"
echo "=== Patch du menu appliqué avec succès ==="
echo ""

# ── Finalisation ───────────────────────────────────────────────────────────────
if   [ -f "live-image-amd64.hybrid.iso" ]; then mv "live-image-amd64.hybrid.iso" "$ISO_NAME"
elif [ -f "live-image-amd64.iso" ];        then mv "live-image-amd64.iso"        "$ISO_NAME"
else echo "ERREUR : ISO introuvable pour le renommage final"; exit 1
fi

sudo lb clean
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ISO créée : $ISO_NAME"
echo "║"
echo "║  Menu de démarrage :"
echo "║    1. Live        → OpenBox kiosque  (code/)"
echo "║    2. Installer   → Copie sur disque + XFCE kiosque"
echo "║    3. Live Safe   → Live + nomodeset"
echo "╚══════════════════════════════════════════════════════════╝"