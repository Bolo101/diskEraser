"""
export_manager.py – Export PDF/log files to an external removable device.

Security rules:
- Only files under LOG_DIR or PDF_DIR are offered.
- The user selects both the files and the destination.
"""

import json
import logging
import os
import shutil
import subprocess
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import List, Optional

from log_handler import LOG_DIR, PDF_DIR

logger = logging.getLogger("disk_eraser")


# ──────────────────────────────────────────────────────────────────────────────
# USB device model (partition)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class UsbDevice:
    device: str          # e.g. "/dev/sdb1"
    name: str            # e.g. "sdb1"
    mountpoint: str = "" # current mount point (if any)
    fstype: str = ""     # filesystem type (optional)
    rm: bool = False     # kept for compatibility, not used for filtering
    size: str = ""       # human-readable size from lsblk
    model: str = ""      # disk model string

    @property
    def mounted(self) -> bool:
        return bool(self.mountpoint)

    @property
    def display(self) -> str:
        """Human‑readable label used in the combobox."""
        state = self.mountpoint if self.mounted else "not mounted"
        model = f" - {self.model}" if self.model else ""
        size = f" ({self.size})" if self.size else ""
        return f"{self.device}{size}{model} [{state}]"


def _run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Small wrapper around subprocess.run with text output."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Device detection – mirror admin_interface external-disk logic
# ──────────────────────────────────────────────────────────────────────────────

def get_usb_devices() -> List[UsbDevice]:
    """
    Return partitions belonging to non-system, non-loop disks.

    Behaviour is aligned with admin_interface._get_external_disks():

    - Use lsblk JSON output.
    - Keep blockdevices where:
        * type == "disk"
        * name does not start with "loop"
        * not identified as system disk by utils.is_system_disk (if available)
    - For each such disk, expose all child partitions (type == "part").
    """
    devices: List[UsbDevice] = []

    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MODEL,MOUNTPOINT"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        logger.error("Failed to execute lsblk for export manager: %s", e)
        return devices

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse lsblk JSON output in export manager: %s", e)
        return devices

    # Optional: same "system disk" detection as used by the admin panel
    is_system_disk_fn = None
    try:
        from utils import is_system_disk as _isd  # type: ignore
        is_system_disk_fn = _isd
    except ImportError:
        is_system_disk_fn = None

    for dev in data.get("blockdevices", []):
        dev_name = dev.get("name", "")
        dev_type = dev.get("type", "")
        if dev_type != "disk":
            continue
        if dev_name.startswith("loop"):
            continue
        if is_system_disk_fn and is_system_disk_fn(f"/dev/{dev_name}"):
            # Skip the main system disk, just like the admin interface
            continue

        disk_model = (dev.get("model") or "").strip()
        disk_size = dev.get("size", "?")

        # Enumerate partitions for this disk
        for child in dev.get("children") or []:
            if child.get("type") != "part":
                continue
            part_name = child.get("name", "")
            if not part_name:
                continue

            part_path = f"/dev/{part_name}"
            mountpoint = child.get("mountpoint") or ""

            devices.append(
                UsbDevice(
                    device=part_path,
                    name=part_name,
                    mountpoint=mountpoint,
                    fstype="",      # FSTYPE is not included in this lsblk call
                    rm=True,        # considered exportable; RM is not used here
                    size=disk_size,
                    model=disk_model,
                )
            )

    return devices


def _is_path_allowed(path: str) -> bool:
    """
    Security check: only allow files that live under LOG_DIR or PDF_DIR.
    """
    rp = os.path.realpath(path)
    allowed = [os.path.realpath(LOG_DIR), os.path.realpath(PDF_DIR)]
    return any(rp == d or rp.startswith(d + os.sep) for d in allowed)


# ──────────────────────────────────────────────────────────────────────────────
# Export dialog window
# ──────────────────────────────────────────────────────────────────────────────

class ExportDialog(tk.Toplevel):
    """
    Modal window used to export log/PDF files to an external device.

    - Shows PDF reports (PDF_DIR) and raw logs (LOG_DIR) in two tabs.
    - Lists partitions from non-system, non-loop disks (mounted or not).
    - Can automatically mount the selected partition.
    - Copies the selected files to the chosen mountpoint.
    - Unmounts the partition when done if it was mounted by the dialog.
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Export manager")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._file_vars: dict[str, tk.BooleanVar] = {}
        self._device_map: dict[str, UsbDevice] = {}
        self._mounted_by_app: Optional[str] = None  # device path if mounted by this dialog
        self._mountpoint: Optional[str] = None
        self._mount_root = "/mnt/export_manager"

        self._build_ui()
        self._refresh_all()

        # Center relative to parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(px, 0)}+{max(py, 0)}")

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        ttk.Label(
            self,
            text="Choose files to export",
            font=("Arial", 13, "bold"),
        ).pack(padx=16, pady=(14, 4))

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        self._pdf_frame = ttk.Frame(nb)
        self._log_frame = ttk.Frame(nb)
        nb.add(self._pdf_frame, text="PDF reports")
        nb.add(self._log_frame, text="Raw logs")

        self._build_file_list(self._pdf_frame, "pdf")
        self._build_file_list(self._log_frame, "log")

        # USB device selection
        dest_frame = ttk.LabelFrame(self, text="USB key / removable device")
        dest_frame.pack(fill=tk.X, padx=12, pady=4)
        inner = ttk.Frame(dest_frame)
        inner.pack(fill=tk.X, padx=6, pady=4)

        self._device_var = tk.StringVar()
        self._device_combo = ttk.Combobox(
            inner,
            textvariable=self._device_var,
            state="readonly",
            width=58,
        )
        self._device_combo.pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)

        ttk.Button(
            inner,
            text="↺ Refresh",
            command=self._refresh_devices,
        ).pack(side=tk.LEFT)

        # Export path (mountpoint)
        path_frame = ttk.LabelFrame(self, text="Export path")
        path_frame.pack(fill=tk.X, padx=12, pady=4)
        path_inner = ttk.Frame(path_frame)
        path_inner.pack(fill=tk.X, padx=6, pady=4)

        self._export_var = tk.StringVar(value="")
        self._export_entry = ttk.Entry(
            path_inner,
            textvariable=self._export_var,
            width=64,
        )
        self._export_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        ttk.Button(
            path_inner,
            text="Mount / select",
            command=self._prepare_mount,
        ).pack(side=tk.LEFT)

        # Bottom buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Export",
                   command=self._do_export).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Close",
                   command=self._close).pack(side=tk.LEFT, padx=8)

    def _build_file_list(self, frame: ttk.Frame, kind: str) -> None:
        """Create a scrollable area listing selectable files."""
        canvas = tk.Canvas(frame, height=200)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )

        setattr(self, f"_{kind}_list_frame", inner)

    # ── Refresh helpers ──────────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._refresh_file_list("pdf", PDF_DIR, [".pdf"])
        self._refresh_file_list("log", LOG_DIR, [])
        self._refresh_devices()

    def _refresh_file_list(
        self,
        kind: str,
        directory: str,
        extensions: List[str],
    ) -> None:
        """Rebuild the file list for the given tab."""
        frame: ttk.Frame = getattr(self, f"_{kind}_list_frame")
        for w in frame.winfo_children():
            w.destroy()

        entries: List[str] = []
        try:
            if os.path.isdir(directory):
                entries = sorted(os.listdir(directory))
        except OSError as e:
            logger.error("Unable to list directory %s: %s", directory, e)
            entries = []

        displayed = 0
        for name in entries:
            full = os.path.join(directory, name)
            if not os.path.isfile(full):
                continue
            if extensions and not any(name.lower().endswith(ext) for ext in extensions):
                continue

            if full not in self._file_vars:
                self._file_vars[full] = tk.BooleanVar(value=False)

            size_kb = os.path.getsize(full) // 1024
            ttk.Checkbutton(
                frame,
                text=f"{name} ({size_kb} KiB)",
                variable=self._file_vars[full],
            ).pack(anchor="w", padx=4)
            displayed += 1

        if displayed == 0:
            ttk.Label(
                frame,
                text="(no file available)",
                foreground="gray",
            ).pack(padx=8, pady=4)

    def _refresh_devices(self) -> None:
        """Refresh the list of removable partitions."""
        devices = get_usb_devices()
        self._device_map = {d.display: d for d in devices}
        values = list(self._device_map.keys())
        self._device_combo["values"] = values if values else ["(no removable device detected)"]

        if values:
            current = self._device_var.get()
            self._device_var.set(current if current in self._device_map else values[0])
        else:
            self._device_var.set("(no removable device detected)")

        self._sync_export_path()

    def _selected_device(self) -> Optional[UsbDevice]:
        """Return the UsbDevice corresponding to the current combobox selection."""
        return self._device_map.get(self._device_var.get())

    # ── Mount / umount helpers ───────────────────────────────────────────────

    def _mount_device(self, device: UsbDevice) -> str:
        """
        Ensure the partition is mounted and return its mountpoint.

        If the device is already mounted, just return its current mountpoint.
        Otherwise, mount it under self._mount_root.
        """
        if device.mounted:
            return device.mountpoint

        os.makedirs(self._mount_root, exist_ok=True)
        mountpoint = os.path.join(
            self._mount_root,
            os.path.basename(device.device).replace("/", "_"),
        )
        os.makedirs(mountpoint, exist_ok=True)

        try:
            _run(["mount", device.device, mountpoint])
        except subprocess.CalledProcessError as e:
            logger.error("Mount failed for %s: %s", device.device, e.stderr or e)
            raise
        except OSError as e:
            logger.error("OS error while mounting %s: %s", device.device, e)
            raise

        return mountpoint

    def _umount_device(self, mountpoint: str) -> None:
        """Try to unmount the given mountpoint."""
        try:
            _run(["umount", mountpoint])
        except subprocess.CalledProcessError as e:
            logger.error("Umount failed for %s: %s", mountpoint, e.stderr or e)
        except OSError as e:
            logger.error("OS error while unmounting %s: %s", mountpoint, e)

    def _prepare_mount(self) -> None:
        """
        Handler for the 'Mount / select' button.

        If the selected device is not mounted, mount it and update the export
        path field with the mountpoint.
        """
        dev = self._selected_device()
        if not dev:
            messagebox.showerror("Error", "No USB device selected.", parent=self)
            return

        try:
            mountpoint = self._mount_device(dev)
        except subprocess.CalledProcessError as e:
            messagebox.showerror(
                "Error",
                f"Unable to mount {dev.device}\n{e.stderr or e}",
                parent=self,
            )
            return
        except OSError as e:
            messagebox.showerror(
                "Error",
                f"OS error while mounting {dev.device}: {e}",
                parent=self,
            )
            return

        # Remember that this dialog mounted the device (so we can unmount it)
        self._mounted_by_app = dev.device if not dev.mounted else None
        self._mountpoint = mountpoint
        self._export_var.set(mountpoint)
        self._refresh_devices()

    def _sync_export_path(self) -> None:
        """
        Keep the export path field in sync with the selected device state.
        """
        dev = self._selected_device()
        if dev and dev.mounted:
            self._export_var.set(dev.mountpoint)
            self._mountpoint = dev.mountpoint
        elif self._mounted_by_app and self._mountpoint:
            self._export_var.set(self._mountpoint)
        else:
            self._export_var.set("")

    # ── File selection and export ────────────────────────────────────────────

    def _selected_files(self) -> List[str]:
        """Return the list of user‑selected files."""
        return [path for path, var in self._file_vars.items() if var.get()]

    def _do_export(self) -> None:
        """Main export logic: security checks, copy, optional unmount."""
        selected = self._selected_files()
        if not selected:
            messagebox.showwarning(
                "Warning",
                "No file selected.",
                parent=self,
            )
            return

        # Security: all files must live under LOG_DIR or PDF_DIR
        for path in selected:
            if not _is_path_allowed(path):
                messagebox.showerror(
                    "Security error",
                    f"Unauthorized file: {path}\n"
                    "Only log and PDF files can be exported.",
                    parent=self,
                )
                return

        dev = self._selected_device()
        if not dev:
            messagebox.showerror("Error", "No removable device selected.", parent=self)
            return

        mountpoint = self._export_var.get().strip()
        mounted_here = False

        try:
            if not mountpoint or not os.path.isdir(mountpoint):
                # Either no path or invalid path: mount the device ourselves.
                mountpoint = self._mount_device(dev)
                mounted_here = not dev.mounted

            os.makedirs(mountpoint, exist_ok=True)

            copied = 0
            errors: List[str] = []

            for src in selected:
                dst = os.path.join(mountpoint, os.path.basename(src))
                try:
                    shutil.copy2(src, dst)
                    copied += 1
                    logger.info("Export %s -> %s", src, dst)
                except (OSError, shutil.Error) as e:
                    errors.append(f"{os.path.basename(src)} : {e}")
                    logger.error("Error while exporting %s: %s", src, e)

            if errors:
                messagebox.showwarning(
                    "Partial export",
                    f"{copied} file(s) copied.\n\n" + "\n".join(errors),
                    parent=self,
                )
            else:
                messagebox.showinfo(
                    "Export successful",
                    f"{copied} file(s) exported to {mountpoint}.",
                    parent=self,
                )

        finally:
            # Only unmount if we mounted the device in this method
            if mounted_here and mountpoint:
                self._umount_device(mountpoint)
                if self._mounted_by_app:
                    self._mounted_by_app = None
                self._mountpoint = None
                self._refresh_devices()

    # ── Close / cleanup ──────────────────────────────────────────────────────

    def _close(self) -> None:
        """
        Close the dialog. If we mounted a device earlier and it is still
        mounted, try to unmount it cleanly.
        """
        if self._mounted_by_app and self._mountpoint:
            self._umount_device(self._mountpoint)
        self.destroy()