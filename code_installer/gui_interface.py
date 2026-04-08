import os
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from subprocess import CalledProcessError, SubprocessError
from disk_erase import get_disk_serial, is_ssd
from utils import get_disk_list, get_base_disk
from disk_partition import partition_disk
from disk_format import format_disk
from concurrent.futures import ThreadPoolExecutor, as_completed
from log_handler import (log_info, log_error, log_erase_operation,
                         session_start, session_end,
                         generate_session_pdf, generate_log_file_pdf)
from disk_operations import get_active_disk, process_disk
import threading
from typing import Dict, List


class DiskEraserInstallerGUI:

    # Intervalle de rafraîchissement automatique de la liste des disques (ms)
    _REFRESH_INTERVAL_MS = 3000

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Secure Disk Eraser")
        self.root.geometry("600x500")
        self.root.attributes("-fullscreen", True)

        self.disk_vars: Dict[str, tk.BooleanVar] = {}
        self.filesystem_var  = tk.StringVar(value="ext4")
        self.passes_var      = tk.StringVar(value="5")
        self.erase_method_var = tk.StringVar(value="overwrite")
        self.crypto_fill_var  = tk.StringVar(value="random")
        self.disks: List[Dict[str, str]] = []
        self.disk_progress: Dict[str, float] = {}
        self.active_disk = get_active_disk()

        self.active_drive_logged = False

        # Ensemble des disques actuellement en cours d'effacement
        self._erasing_devs: set = set()

        # Cache de la dernière liste de disques connue, utilisé pour le diff
        # {dev: {"label_text": str, "text_color": str}}
        self._disk_row_cache: Dict[str, dict] = {}

        # Widgets par disque : {dev: {"frame": Frame, "cb": Checkbutton, "var": BooleanVar}}
        self._disk_rows: Dict[str, dict] = {}

        session_start()

        if os.geteuid() != 0:
            messagebox.showerror("Error", "This program must be run as root!")
            root.destroy()
            sys.exit(1)

        self._build_ui()
        self._refresh_disks()
        # Lance la boucle de rafraîchissement automatique
        self.root.after(self._REFRESH_INTERVAL_MS, self._auto_refresh_disks)

    # ── Construction UI ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="Secure Disk Eraser", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # Left frame - Disk selection
        disk_frame = ttk.LabelFrame(main_frame, text="Select Disks to Erase")
        disk_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.disk_canvas = tk.Canvas(disk_frame)
        scrollbar = ttk.Scrollbar(disk_frame, orient="vertical", command=self.disk_canvas.yview)
        self.scrollable_disk_frame = ttk.Frame(self.disk_canvas)

        self.scrollable_disk_frame.bind(
            "<Configure>",
            lambda e: self.disk_canvas.configure(scrollregion=self.disk_canvas.bbox("all"))
        )
        self.disk_canvas.create_window((0, 0), window=self.scrollable_disk_frame, anchor="nw")
        self.disk_canvas.configure(yscrollcommand=scrollbar.set)
        self.disk_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.disclaimer_var = tk.StringVar(value="")
        self.disclaimer_label = ttk.Label(disk_frame, textvariable=self.disclaimer_var,
                                          foreground="red", wraplength=250)
        self.disclaimer_label.pack(side=tk.BOTTOM, pady=5)

        self.ssd_disclaimer_var = tk.StringVar(value="")
        self.ssd_disclaimer_label = ttk.Label(disk_frame, textvariable=self.ssd_disclaimer_var,
                                              foreground="blue", wraplength=250)
        self.ssd_disclaimer_label.pack(side=tk.BOTTOM, pady=5)

        # NOTE : le bouton "Refresh Disks" a été supprimé.
        # Le rafraîchissement est désormais automatique (cf. _auto_refresh_disks).

        # Right frame - Options
        options_frame = ttk.LabelFrame(main_frame, text="Options")
        options_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5)

        method_label = ttk.Label(options_frame, text="Erasure Method:")
        method_label.pack(anchor="w", pady=(10, 5))

        for text, value in [("Standard Overwrite", "overwrite"),
                             ("Cryptographic Erasure", "crypto")]:
            ttk.Radiobutton(options_frame, text=text, value=value,
                            variable=self.erase_method_var,
                            command=self.update_method_options).pack(anchor="w", padx=20)

        self.passes_frame = ttk.Frame(options_frame)
        self.passes_frame.pack(fill=tk.X, pady=10, padx=5)
        ttk.Label(self.passes_frame, text="Number of passes:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(self.passes_frame, textvariable=self.passes_var, width=5).pack(side=tk.LEFT, padx=5)

        self.crypto_fill_frame = ttk.LabelFrame(options_frame, text="Fill Method (Crypto)")
        for text, value in [("Random Data", "random"), ("Zero Data", "zero")]:
            ttk.Radiobutton(self.crypto_fill_frame, text=text, value=value,
                            variable=self.crypto_fill_var).pack(anchor="w", padx=20, pady=2)

        ttk.Label(options_frame, text="Choose Filesystem:").pack(anchor="w", pady=(10, 5))
        for text, value in [("ext4", "ext4"), ("NTFS", "ntfs"), ("FAT32", "vfat")]:
            ttk.Radiobutton(options_frame, text=text, value=value,
                            variable=self.filesystem_var).pack(anchor="w", padx=20)

        ttk.Button(options_frame, text="Exit Fullscreen",
                   command=self.toggle_fullscreen).pack(pady=5, padx=10, fill=tk.X)
        ttk.Button(options_frame, text="Start Erasure",
                   command=self._start_erasure).pack(pady=10, padx=10, fill=tk.X)
        ttk.Button(options_frame, text="Format Only (No Erase)",
                   command=self.format_only).pack(pady=5, padx=10, fill=tk.X)

        log_buttons_frame = ttk.Frame(options_frame)
        log_buttons_frame.pack(pady=5, padx=10, fill=tk.X)
        ttk.Button(log_buttons_frame, text="Print Session Log",
                   command=self.print_session_log).pack(side=tk.TOP, pady=5, padx=10,
                                                        fill=tk.X, expand=True)
        ttk.Button(log_buttons_frame, text="Print Complete Log",
                   command=self.print_complete_log).pack(side=tk.BOTTOM, pady=5, padx=10,
                                                         fill=tk.X, expand=True)

        ttk.Button(options_frame, text="Power Off System",
                   command=self.power_off_system).pack(pady=5, padx=10, fill=tk.X)
        ttk.Button(options_frame, text="Exit",
                   command=self.exit_application).pack(pady=5, padx=10, fill=tk.X)

        progress_frame = ttk.LabelFrame(main_frame, text="Progress")
        progress_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, padx=10, pady=10)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(pady=5)

        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text = tk.Text(log_frame, height=6, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        self.update_method_options()

    # ── Rafraîchissement automatique des disques ───────────────────────────────
    def _auto_refresh_disks(self) -> None:
        """
        Boucle de rafraîchissement périodique lancée au démarrage.
        Ne rafraîchit pas si un effacement est actif afin d'éviter
        de modifier la liste pendant le traitement.
        """
        if not self._erasing_devs:
            self._refresh_disks()
        self.root.after(self._REFRESH_INTERVAL_MS, self._auto_refresh_disks)

    # ── Helpers : construction d'une ligne de disque ──────────────────────────
    @staticmethod
    def _build_disk_label(disk: dict, active_physical_drives: set) -> tuple:
        """
        Calcule le texte et la couleur d'affichage pour un disque.
        Retourne (id_text, details_text, text_color, is_active).
        """
        device_name = disk['device'].replace('/dev/', '')

        try:
            disk_identifier = get_disk_serial(device_name)
        except Exception:
            disk_identifier = device_name

        try:
            ssd_indicator = " (Solid_state)" if is_ssd(device_name) else " (Mechanical)"
        except Exception:
            ssd_indicator = " (Type unknown)"

        try:
            is_active = get_base_disk(device_name) in active_physical_drives
        except Exception:
            is_active = False

        active_indicator = " (ACTIVE SYSTEM DISK)" if is_active else ""
        disk_label_str   = disk.get('label', 'Unknown')
        label_indicator  = (f" [Label: {disk_label_str}]"
                            if disk_label_str and disk_label_str != "No Label"
                            else " [No Label]")

        id_text      = f"{disk_identifier}{ssd_indicator}{active_indicator}{label_indicator}"
        details_text = f"Size: {disk['size']} - Model: {disk['model']}"
        text_color   = "red" if is_active else ("blue" if "(Solid_state)" in ssd_indicator else "black")

        return id_text, details_text, text_color, is_active

    def _create_disk_row(self, disk: dict, active_physical_drives: set) -> None:
        """Crée et pack les widgets pour un disque donné. Ne doit être appelé qu'une fois par disque."""
        dev = disk['device']
        id_text, details_text, text_color, _ = self._build_disk_label(disk, active_physical_drives)
        is_erasing = dev in self._erasing_devs

        var = tk.BooleanVar(value=is_erasing)
        self.disk_vars[dev] = var

        disk_entry_frame = ttk.Frame(self.scrollable_disk_frame)
        disk_entry_frame.pack(fill=tk.X, pady=5, padx=2)

        checkbox_row = ttk.Frame(disk_entry_frame)
        checkbox_row.pack(fill=tk.X)

        cb = ttk.Checkbutton(checkbox_row, variable=var)
        if is_erasing:
            cb.configure(state="disabled")
        cb.pack(side=tk.LEFT)

        id_label = ttk.Label(checkbox_row, text=id_text, foreground=text_color, wraplength=300)
        id_label.pack(side=tk.LEFT, padx=5, fill=tk.X)

        details_row = ttk.Frame(disk_entry_frame)
        details_row.pack(fill=tk.X, padx=25)
        details_label = ttk.Label(details_row, text=details_text,
                                  foreground=text_color, wraplength=300)
        details_label.pack(side=tk.LEFT, fill=tk.X)

        sep = ttk.Separator(self.scrollable_disk_frame, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=2)

        # Mémorise tous les widgets de cette ligne pour les mises à jour futures
        self._disk_rows[dev] = {
            "frame":         disk_entry_frame,
            "sep":           sep,
            "cb":            cb,
            "var":           var,
            "id_label":      id_label,
            "details_label": details_label,
        }
        self._disk_row_cache[dev] = {"id_text": id_text, "details_text": details_text,
                                     "text_color": text_color}

    def _update_disk_row(self, dev: str, disk: dict, active_physical_drives: set) -> None:
        """
        Met à jour uniquement les attributs qui ont changé pour un disque existant.
        Aucune destruction/recréation de widget → pas de clignotement.
        """
        id_text, details_text, text_color, _ = self._build_disk_label(disk, active_physical_drives)
        is_erasing = dev in self._erasing_devs
        row = self._disk_rows[dev]

        # Mise à jour du texte et de la couleur si changement
        cache = self._disk_row_cache.get(dev, {})
        if cache.get("id_text") != id_text:
            row["id_label"].configure(text=id_text, foreground=text_color)
        if cache.get("details_text") != details_text:
            row["details_label"].configure(text=details_text, foreground=text_color)
        if cache.get("text_color") != text_color:
            row["id_label"].configure(foreground=text_color)
            row["details_label"].configure(foreground=text_color)

        # Mise à jour état checkbox
        var = row["var"]
        cb  = row["cb"]
        if is_erasing:
            var.set(True)
            cb.configure(state="disabled")
        else:
            # Si le disque n'est plus en cours d'effacement on remet normal
            # mais on ne touche pas à la sélection de l'utilisateur
            cb.configure(state="normal")

        self._disk_row_cache[dev] = {"id_text": id_text, "details_text": details_text,
                                     "text_color": text_color}
        self.disk_vars[dev] = var

    def _remove_disk_row(self, dev: str) -> None:
        """Détruit les widgets d'un disque qui a disparu."""
        row = self._disk_rows.pop(dev, None)
        if row:
            row["sep"].destroy()
            row["frame"].destroy()
        self._disk_row_cache.pop(dev, None)
        self.disk_vars.pop(dev, None)

    # ── Rafraîchissement principal (diff, sans clignotement) ───────────────────
    def _refresh_disks(self) -> None:
        """
        Met à jour la liste des disques de façon incrémentale :
          - Crée uniquement les lignes des disques nouvellement détectés.
          - Supprime uniquement les lignes des disques disparus.
          - Met à jour en place les lignes des disques déjà affichés.
        Cette approche évite tout clignotement visuel.
        """
        # ── 1. Récupération de la liste système ──
        try:
            new_disks = get_disk_list()
        except (CalledProcessError, SubprocessError, FileNotFoundError, IOError, OSError) as e:
            error_msg = f"Error getting disk list: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            new_disks = []

        # ── 2. Détection du disque actif ──
        try:
            active_base_disks = get_active_disk()
        except Exception as e:
            self.update_gui_log(f"Error detecting active disk: {str(e)}")
            active_base_disks = None
        active_physical_drives = set(active_base_disks) if active_base_disks else set()

        if active_base_disks and not self.active_drive_logged and active_physical_drives:
            log_info(f"Active physical devices: {active_physical_drives}")
            self.active_drive_logged = True

        # Mise à jour des disclaimers (StringVar → pas de clignotement)
        if active_physical_drives:
            self.disclaimer_var.set(
                "WARNING: Disk marked in red contains the active filesystem. "
                "Erasing this disk will cause system failure and data loss!"
            )
        else:
            self.disclaimer_var.set("")

        # ── 3. Calcul du diff ──
        new_dev_set = {d['device'] for d in new_disks}
        old_dev_set = set(self._disk_rows.keys())

        added   = new_dev_set - old_dev_set
        removed = old_dev_set - new_dev_set
        kept    = new_dev_set & old_dev_set

        # ── 4. Suppressions : disques débranchés ──
        for dev in removed:
            self._remove_disk_row(dev)

        # ── 5. Mises à jour : disques déjà présents ──
        new_disk_map = {d['device']: d for d in new_disks}
        for dev in kept:
            self._update_disk_row(dev, new_disk_map[dev], active_physical_drives)

        # ── 6. Ajouts : nouveaux disques ──
        for dev in added:
            self._create_disk_row(new_disk_map[dev], active_physical_drives)

        # Cas liste vide
        if not new_disks:
            if not self._disk_rows:
                if not self.scrollable_disk_frame.winfo_children():
                    ttk.Label(self.scrollable_disk_frame, text="No disks found").pack(pady=10)
            self.disclaimer_var.set("")
            self.ssd_disclaimer_var.set("")
            return

        # ── 7. Disclaimer SSD ──
        has_ssd = False
        for disk in new_disks:
            try:
                if is_ssd(disk['device'].replace('/dev/', '')):
                    has_ssd = True
                    break
            except Exception:
                pass
        self.ssd_disclaimer_var.set(
            "WARNING: SSD devices detected. Multiple-pass erasure may damage SSDs "
            "and NOT achieve secure data deletion due to SSD wear leveling. "
            "For SSDs, use cryptographic erase mode instead."
            if has_ssd else ""
        )

        self.disks = new_disks

    # ── Méthode d'effacement ───────────────────────────────────────────────────
    def update_method_options(self) -> None:
        """Update UI based on the selected erasure method"""
        method = self.erase_method_var.get()
        self.crypto_fill_frame.pack(fill=tk.X, pady=10, padx=5, after=self.passes_frame)
        for child in self.crypto_fill_frame.winfo_children():
            try:
                child.configure(state="normal" if method == "crypto" else "disabled")
            except tk.TclError:
                pass
        for child in self.passes_frame.winfo_children():
            if isinstance(child, ttk.Entry):
                try:
                    child.configure(state="disabled" if method == "crypto" else "normal")
                except tk.TclError:
                    pass

    # ── Format only ───────────────────────────────────────────────────────────
    def format_only(self) -> None:
        """Format selected disks without erasing them first."""
        selected_disks = [disk for disk, var in self.disk_vars.items() if var.get()]
        if not selected_disks:
            messagebox.showwarning("Warning", "No disks selected!")
            return

        disk_identifiers = []
        for disk in selected_disks:
            disk_name = disk.replace('/dev/', '')
            try:
                disk_identifier = get_disk_serial(disk_name)
            except (CalledProcessError, SubprocessError) as e:
                disk_identifier = f"{disk_name} (Serial unavailable)"
                self.update_gui_log(f"Error getting serial for {disk_name}: {str(e)}")
                log_error(f"Error getting serial for {disk_name}: {str(e)}")
            except FileNotFoundError as e:
                disk_identifier = f"{disk_name} (Serial command not found)"
                self.update_gui_log(f"Required command not found for getting serial of {disk_name}: {str(e)}")
                log_error(f"Required command not found for getting serial of {disk_name}: {str(e)}")
            except PermissionError as e:
                disk_identifier = f"{disk_name} (Permission denied)"
                self.update_gui_log(f"Permission denied getting serial for {disk_name}: {str(e)}")
                log_error(f"Permission denied getting serial for {disk_name}: {str(e)}")
            except (IOError, OSError) as e:
                disk_identifier = f"{disk_name} (IO error)"
                self.update_gui_log(f"IO error getting serial for {disk_name}: {str(e)}")
                log_error(f"IO error getting serial for {disk_name}: {str(e)}")
            disk_identifiers.append(disk_identifier)

        disk_list = "\n".join(disk_identifiers)
        fs_choice = self.filesystem_var.get()
        if not messagebox.askyesno("Confirm Format",
                                   f"WARNING: You are about to format the following disks as {fs_choice}:\n\n{disk_list}\n\n"
                                   "All existing data will be lost!\n\n"
                                   "Do you want to continue?"):
            return

        self.status_var.set("Starting format process...")
        try:
            threading.Thread(target=self.format_disks_thread,
                             args=(selected_disks, fs_choice), daemon=True).start()
        except (RuntimeError, OSError) as e:
            error_msg = f"Error starting format thread: {str(e)}"
            messagebox.showerror("Thread Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")

    def format_disks_thread(self, disks, fs_choice):
        """Thread function to format disks."""
        start_msg = f"Starting format of {len(disks)} disk(s) as {fs_choice}"
        self.update_gui_log(start_msg)
        log_info(start_msg)
        total_disks = len(disks)
        completed_disks = 0
        try:
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(self.format_single_disk, disk, fs_choice): disk
                           for disk in disks}
                for future in as_completed(futures):
                    disk = futures[future]
                    try:
                        future.result()
                        completed_disks += 1
                        self.update_progress((completed_disks / total_disks) * 100)
                        self.status_var.set(f"Formatted {completed_disks}/{total_disks} disks")
                    except Exception as e:
                        error_msg = f"Error formatting disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
        except Exception as e:
            error_msg = f"Error with thread pool executor during format: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        self.status_var.set("Format process completed")
        log_info("Format process completed")
        try:
            messagebox.showinfo("Complete", "Disk formatting operation has completed!")
        except tk.TclError as e:
            self.update_gui_log(f"Error showing completion dialog: {str(e)}")

    def format_single_disk(self, disk, fs_choice):
        """Format a single disk."""
        disk_name = disk.replace('/dev/', '')
        try:
            disk_id = get_disk_serial(disk_name)
            self.status_var.set(f"Formatting {disk_id}...")
            log_info(f"Formatting {disk_id} as {fs_choice}")
        except Exception as e:
            self.update_gui_log(f"Error getting disk serial: {str(e)}")
            self.status_var.set(f"Formatting {disk_name}...")
            log_info(f"Formatting {disk_name} as {fs_choice}")
        try:
            partition_disk(disk_name)
            self.update_gui_log(f"Partitioned {disk_name}")
            format_disk(disk_name, fs_choice)
            self.update_gui_log(f"Successfully formatted {disk_name} as {fs_choice}")
            log_info(f"Successfully formatted {disk_name} as {fs_choice}")
        except (CalledProcessError, FileNotFoundError, PermissionError, IOError, OSError,
                MemoryError, ValueError, TypeError, RuntimeError) as e:
            error_msg = f"Error formatting {disk_name}: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
            raise

    # ── Power off ─────────────────────────────────────────────────────────────
    def power_off_system(self) -> None:
        """Power off the system after confirmation."""
        import subprocess
        if not messagebox.askyesno("Confirm Power Off",
                                   "Are you sure you want to power off the system?\n\n"
                                   "All unsaved work will be lost!"):
            return
        if not messagebox.askyesno("FINAL WARNING",
                                   "This will shut down the computer immediately.\n\n"
                                   "Do you want to proceed?"):
            return
        try:
            log_info("System power off initiated by user")
            self.update_gui_log("Powering off system...")
            session_end()
            time.sleep(1)
            subprocess.run(["poweroff"], check=True)
        except subprocess.CalledProcessError as e:
            error_msg = f"Error executing poweroff command: {str(e)}"
            messagebox.showerror("Power Off Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except FileNotFoundError:
            error_msg = "Poweroff command not found. Try 'shutdown -h now' manually."
            messagebox.showerror("Command Not Found", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
        except (PermissionError, IOError, OSError, MemoryError, ValueError, TypeError) as e:
            error_msg = f"System error during poweroff: {str(e)}"
            messagebox.showerror("System Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)

    # ── External storage helpers ───────────────────────────────────────────────
    def _get_external_disks(self) -> list:
        """
        Return a list of dicts describing block devices that are NOT the
        active system disk and NOT a pure virtual/loop device.

        Each dict has:
          device       – base device name, e.g. 'sdb'
          path         – full path, e.g. '/dev/sdb'
          size         – human-readable size from lsblk
          model        – model string (may be empty)
          partitions   – list of partition names, e.g. ['sdb1', 'sdb2']
          mount_points – dict {partition_name: mount_point or None}
        """
        import subprocess as _sp, json as _json
        active_disks = set(self.active_disk or [])
        result = []
        try:
            raw = _sp.run(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MODEL,MOUNTPOINT"],
                          stdout=_sp.PIPE, stderr=_sp.PIPE).stdout.decode()
            data = _json.loads(raw)
        except Exception as e:
            log_error(f"lsblk JSON failed: {e}")
            return result
        for dev in data.get("blockdevices", []):
            dev_name = dev.get("name", "")
            if dev.get("type") != "disk":
                continue
            if dev_name in active_disks or dev_name.startswith("loop"):
                continue
            partitions, mount_map = [], {}
            children = dev.get("children") or []
            if children:
                for child in children:
                    if child.get("type") == "part":
                        p = child["name"]
                        partitions.append(p)
                        mount_map[p] = child.get("mountpoint") or None
            else:
                partitions.append(dev_name)
                mount_map[dev_name] = dev.get("mountpoint") or None
            result.append({
                "device": dev_name, "path": f"/dev/{dev_name}",
                "size": dev.get("size", "?"),
                "model": (dev.get("model") or "").strip(),
                "partitions": partitions, "mount_points": mount_map,
            })
        return result

    def _mount_partition(self, partition: str) -> "str | None":
        """
        Mount /dev/<partition> to a unique temp directory.
        Returns the mount point on success, None on failure.
        """
        import subprocess as _sp, tempfile as _tf
        mount_dir = _tf.mkdtemp(prefix="disk_eraser_export_")
        try:
            r = _sp.run(["mount", f"/dev/{partition}", mount_dir],
                        stdout=_sp.PIPE, stderr=_sp.PIPE)
            if r.returncode != 0:
                log_error(f"mount /dev/{partition} -> {mount_dir} failed: {r.stderr.decode().strip()}")
                try:
                    import os as _os; _os.rmdir(mount_dir)
                except OSError:
                    pass
                return None
            log_info(f"Mounted /dev/{partition} at {mount_dir}")
            return mount_dir
        except FileNotFoundError:
            log_error("mount command not found")
            return None
        except Exception as e:
            log_error(f"Unexpected error mounting /dev/{partition}: {e}")
            return None

    def _unmount_partition(self, mount_dir: str) -> None:
        """Unmount and remove the temporary mount directory."""
        import subprocess as _sp, os as _os
        try:
            r = _sp.run(["umount", mount_dir], stdout=_sp.PIPE, stderr=_sp.PIPE)
            if r.returncode != 0:
                log_error(f"umount {mount_dir} failed: {r.stderr.decode().strip()}")
            else:
                log_info(f"Unmounted {mount_dir}")
        except Exception as e:
            log_error(f"Error during umount {mount_dir}: {e}")
        finally:
            try:
                _os.rmdir(mount_dir)
            except OSError:
                pass

    def _show_disk_picker(self, external_disks: list):
        """
        Modal dialog that lets the user pick one partition from the list of
        external disks. Returns (partition_name, was_already_mounted,
        existing_mount_point) or (None, False, None) if cancelled.
        """
        import tkinter as _tk
        from tkinter import ttk as _ttk
        result = {"partition": None, "already_mounted": False, "mount_point": None}
        dlg = _tk.Toplevel(self.root)
        dlg.title("Sélectionner le support externe")
        dlg.grab_set()
        dlg.resizable(False, False)
        _ttk.Label(dlg, text="Choisissez le support externe pour l'export PDF",
                   font=("Arial", 11, "bold"), padding=(10, 10)).pack(fill=_tk.X)
        _ttk.Label(dlg, text="Seuls les disques hors système sont listés.\n"
                   "Le support sera monté automatiquement si nécessaire.",
                   foreground="#555555", padding=(10, 0, 10, 6)).pack(fill=_tk.X)
        frame = _ttk.Frame(dlg, padding=(10, 0, 10, 6))
        frame.pack(fill=_tk.BOTH, expand=True)
        lb = _tk.Listbox(frame, width=68, height=12, font=("Courier", 9),
                         selectmode=_tk.SINGLE, activestyle="dotbox")
        sb = _ttk.Scrollbar(frame, orient=_tk.VERTICAL, command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True)
        sb.pack(side=_tk.RIGHT, fill=_tk.Y)
        entries = []
        for disk in external_disks:
            model_str = f" [{disk['model']}]" if disk['model'] else ""
            lb.insert(_tk.END, f"── {disk['path']} {disk['size']}{model_str}")
            lb.itemconfig(_tk.END, foreground="#333388", background="#eeeeff")
            entries.append(None)
            for part in disk["partitions"]:
                mp = disk["mount_points"].get(part)
                lb.insert(_tk.END, f"   /dev/{part:<14} {'monté sur ' + mp if mp else 'non monté'}")
                entries.append((part, mp is not None, mp))
        btn_frame = _ttk.Frame(dlg, padding=(10, 6))
        btn_frame.pack(fill=_tk.X)
        def on_select():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Aucune sélection", "Veuillez sélectionner une partition.", parent=dlg)
                return
            entry = entries[sel[0]]
            if entry is None:
                messagebox.showwarning("Sélection invalide",
                                       "Veuillez sélectionner une partition,\npas un en-tête de disque.",
                                       parent=dlg)
                return
            result["partition"], result["already_mounted"], result["mount_point"] = entry
            dlg.destroy()
        def on_cancel():
            dlg.destroy()
        _ttk.Button(btn_frame, text="Sélectionner", command=on_select).pack(side=_tk.LEFT, padx=4)
        _ttk.Button(btn_frame, text="Annuler", command=on_cancel).pack(side=_tk.LEFT, padx=4)
        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        dlg.geometry(f"+{self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2}"
                     f"+{self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2}")
        self.root.wait_window(dlg)
        return result["partition"], result["already_mounted"], result["mount_point"]

    def _request_external_export_path(self, default_filename: str):
        """
        Full workflow:
        1. Detect external disks (mounted or not).
        2. Show the disk picker dialog.
        3. If the chosen partition is not mounted, mount it to a temp dir.
        4. Open the standard Tk save-as dialog on that mount point.
        5. Validate the destination is still on the external mount.
        6. Return the chosen path (caller is responsible for unmounting via
           self._pending_unmount_dir after PDF is written).

        Returns:
            str | None: Chosen absolute file path, or None if cancelled.
        """
        external_disks = self._get_external_disks()
        if not external_disks:
            messagebox.showerror("Aucun support externe détecté",
                                 "Aucun disque externe n'a été détecté.\n\n"
                                 "Branchez une clé USB, un disque dur externe ou tout autre "
                                 "support amovible, puis réessayez.")
            return None
        partition, already_mounted, existing_mp = self._show_disk_picker(external_disks)
        if not partition:
            return None
        self._pending_unmount_dir = None
        if already_mounted and existing_mp:
            mount_point = existing_mp
        else:
            self.status_var.set(f"Montage de /dev/{partition}…")
            self.root.update_idletasks()
            mount_point = self._mount_partition(partition)
            if not mount_point:
                messagebox.showerror("Erreur de montage",
                                     f"Impossible de monter /dev/{partition}.\n\n"
                                     "Vérifiez que le support est correctement branché et "
                                     "que le système de fichiers est supporté (ext4, NTFS, FAT32…).")
                self.status_var.set("Prêt")
                return None
            self._pending_unmount_dir = mount_point
        chosen_path = filedialog.asksaveasfilename(
            title="Exporter le PDF — support externe",
            initialdir=mount_point,
            initialfile=default_filename,
            defaultextension=".pdf",
            filetypes=[("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")],
        )
        if not chosen_path:
            if self._pending_unmount_dir:
                self.status_var.set(f"Démontage de /dev/{partition}…")
                self.root.update_idletasks()
                self._unmount_partition(self._pending_unmount_dir)
                self._pending_unmount_dir = None
            self.status_var.set("Prêt")
            return None
        import os as _os
        mp_norm   = mount_point.rstrip('/') + '/'
        path_norm = _os.path.abspath(chosen_path).rstrip('/') + '/'
        if not path_norm.startswith(mp_norm):
            messagebox.showwarning("Destination invalide",
                                   "Le chemin choisi n'est pas sur le support externe monté.\n"
                                   f"Veuillez choisir un emplacement sous : {mount_point}")
            if self._pending_unmount_dir:
                self._unmount_partition(self._pending_unmount_dir)
                self._pending_unmount_dir = None
            return None
        return chosen_path

    def _finalize_export(self, partition_label: str = "") -> None:
        """
        Unmount the temporary mount directory that was created during an export
        (if any). Called after the PDF has been successfully written.
        """
        if getattr(self, '_pending_unmount_dir', None):
            self.status_var.set("Démontage du support externe…")
            self.root.update_idletasks()
            self._unmount_partition(self._pending_unmount_dir)
            self._pending_unmount_dir = None
            self.status_var.set("Support externe démonté.")
            self.update_gui_log("Support externe démonté avec succès.")

    def print_session_log(self) -> None:
        """Generate and save session log as PDF to an external storage device."""
        from datetime import datetime as _dt
        default_name = f"session_log_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        export_path = self._request_external_export_path(default_name)
        if not export_path:
            self.update_gui_log("Export PDF session annulé.")
            self.status_var.set("Prêt")
            return
        try:
            self.status_var.set("Génération du PDF de session…")
            pdf_path = generate_session_pdf(output_path=export_path)
            self._finalize_export()
            messagebox.showinfo("PDF Exporté",
                                f"PDF de session exporté avec succès !\nEnregistré : {pdf_path}")
            self.update_gui_log(f"PDF de session enregistré : {pdf_path}")
            self.status_var.set("PDF de session exporté")
        except Exception as e:
            error_msg = f"Error generating session log PDF: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")

    def print_complete_log(self) -> None:
        """Generate and save complete log file as PDF to an external storage device."""
        from datetime import datetime as _dt
        default_name = f"complete_log_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        export_path = self._request_external_export_path(default_name)
        if not export_path:
            self.update_gui_log("Export PDF journal complet annulé.")
            self.status_var.set("Prêt")
            return
        try:
            self.status_var.set("Génération du PDF journal complet…")
            pdf_path = generate_log_file_pdf(output_path=export_path)
            self._finalize_export()
            messagebox.showinfo("PDF Exporté",
                                f"PDF journal complet exporté avec succès !\nEnregistré : {pdf_path}")
            self.update_gui_log(f"PDF journal complet enregistré : {pdf_path}")
            self.status_var.set("PDF journal complet exporté")
        except Exception as e:
            error_msg = f"Error generating complete log PDF: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self.status_var.set("Ready")

    # ── Contrôles généraux ────────────────────────────────────────────────────
    def exit_application(self) -> None:
        """Log and close the application when Exit is clicked"""
        exit_message = "Application closed by user via Exit button"
        log_info(exit_message)
        self.update_gui_log(exit_message)
        session_end()
        self.root.destroy()

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode"""
        try:
            self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))
        except tk.TclError as e:
            self.update_gui_log(f"Error toggling fullscreen mode: {str(e)}")
            log_error(f"Error toggling fullscreen mode: {str(e)}")

    # ── Effacement ────────────────────────────────────────────────────────────
    def _start_erasure(self) -> None:
        selected_disks = [disk for disk, var in self.disk_vars.items() if var.get()]
        if not selected_disks:
            messagebox.showwarning("Warning", "No disks selected!")
            return

        active_disk_selected = any(
            self.active_disk and any(ad in d.replace('/dev/', '') for ad in self.active_disk)
            for d in selected_disks
        )
        if active_disk_selected:
            if not messagebox.askyesno("DANGER - SYSTEM DISK SELECTED",
                                       "WARNING: You have selected the ACTIVE SYSTEM DISK!\n\n"
                                       "Erasing this disk will CRASH your system and cause PERMANENT DATA LOSS!\n\n"
                                       "Are you absolutely sure you want to continue?",
                                       icon="warning"):
                return

        erase_method = self.erase_method_var.get()

        ssd_selected = False
        if erase_method == "overwrite":
            for disk in selected_disks:
                try:
                    if is_ssd(disk.replace('/dev/', '')):
                        ssd_selected = True
                        break
                except Exception:
                    pass
        if ssd_selected:
            if not messagebox.askyesno("WARNING - SSD DEVICE SELECTED",
                                       "WARNING: You have selected one or more SSD devices!\n\n"
                                       "Using multiple-pass erasure on SSDs can:\n"
                                       "• Damage the SSD by causing excessive wear\n"
                                       "• Fail to securely erase data due to SSD wear leveling\n"
                                       "• Not overwrite all sectors due to over-provisioning\n\n"
                                       "For SSDs, use cryptographic erasure\n\n"
                                       "Do you still want to continue?",
                                       icon="warning"):
                return

        disk_identifiers = []
        for disk in selected_disks:
            disk_name = disk.replace('/dev/', '')
            try:
                disk_identifier = get_disk_serial(disk_name)
            except Exception:
                disk_identifier = disk_name
            disk_identifiers.append(disk_identifier)
            fs_choice = self.filesystem_var.get()
            if erase_method == "crypto":
                method_description = f"cryptographic erasure with {self.crypto_fill_var.get()} fill"
            else:
                method_description = f"standard {self.passes_var.get()}-pass overwrite"
            try:
                log_erase_operation(disk_identifier, fs_choice, method_description)
            except Exception as e:
                self.update_gui_log(f"Error logging erasure operation for {disk_identifier}: {str(e)}")
                log_error(f"Error logging erasure operation for {disk_identifier}: {str(e)}")

        disk_list  = "\n".join(disk_identifiers)
        method_info = (f"using cryptographic erasure with {self.crypto_fill_var.get()} fill"
                       if erase_method == "crypto"
                       else f"with {self.passes_var.get()} pass overwrite")
        if not messagebox.askyesno("Confirm Erasure",
                                   f"WARNING: You are about to securely erase the following disks {method_info}:\n\n{disk_list}\n\n"
                                   "This operation CANNOT be undone and ALL DATA WILL BE LOST!\n\n"
                                   "Are you absolutely sure you want to continue?"):
            return
        if not messagebox.askyesno("FINAL WARNING",
                                   "THIS IS YOUR FINAL WARNING!\n\n"
                                   "All selected disks will be completely erased.\n\n"
                                   "Do you want to proceed?"):
            return

        passes = 1
        if erase_method == "overwrite":
            try:
                passes = int(self.passes_var.get())
                if passes < 1:
                    messagebox.showerror("Error", "Number of passes must be at least 1")
                    return
            except (ValueError, OverflowError):
                messagebox.showerror("Error", "Number of passes must be a valid integer")
                return

        # Mémorise les disques en cours d'effacement pour le refresh automatique
        self._erasing_devs = set(selected_disks)

        self.status_var.set("Starting erasure process...")
        try:
            threading.Thread(target=self._run_erasure,
                             args=(selected_disks, self.filesystem_var.get(), passes, erase_method),
                             daemon=True).start()
        except (RuntimeError, OSError) as e:
            error_msg = f"Error starting erasure thread: {str(e)}"
            messagebox.showerror("Thread Error", error_msg)
            self.update_gui_log(error_msg)
            log_error(error_msg)
            self._erasing_devs.clear()
            self.status_var.set("Ready")

    def _run_erasure(self, disks: List[str], fs_choice: str,
                      passes: int, erase_method: str) -> None:
        if erase_method == "crypto":
            fill_method = self.crypto_fill_var.get()
            method_str = f"cryptographic erasure with {fill_method} fill"
        else:
            method_str = f"standard {passes}-pass overwrite"

        start_msg = f"Starting secure erasure of {len(disks)} disk(s) using {method_str}"
        self.update_gui_log(start_msg)
        log_info(start_msg)
        self.update_gui_log(f"Selected filesystem: {fs_choice}")
        log_info(f"Selected filesystem: {fs_choice}")

        total_disks = len(disks)
        completed_disks = 0

        try:
            with ThreadPoolExecutor() as executor:
                self.disk_progress = {disk: 0 for disk in disks}
                futures = {
                    executor.submit(self.process_disk_wrapper, disk, fs_choice, passes, erase_method): disk
                    for disk in disks
                }
                for future in as_completed(futures):
                    disk = futures[future]
                    try:
                        future.result()
                        completed_disks += 1
                        # Retire le disque terminé de l'ensemble des disques en cours
                        self._erasing_devs.discard(disk)
                        self.update_progress((completed_disks / total_disks) * 100)
                        self.status_var.set(f"Completed {completed_disks}/{total_disks} disks")
                    except Exception as e:
                        self._erasing_devs.discard(disk)
                        error_msg = f"Error processing disk {disk}: {str(e)}"
                        self.update_gui_log(error_msg)
                        log_error(error_msg)
        except Exception as e:
            error_msg = f"Error with thread pool executor: {str(e)}"
            self.update_gui_log(error_msg)
            log_error(error_msg)
        finally:
            # Garantit le nettoyage de l'ensemble même en cas d'exception non anticipée
            self._erasing_devs.clear()

        self._on_erasure_done()
        self.status_var.set("Erasure process completed")
        log_info("Erasure process completed")
        try:
            messagebox.showinfo("Complete", "Disk erasure operation has completed!")
        except tk.TclError as e:
            self.update_gui_log(f"Error showing completion dialog: {str(e)}")


    def _on_erasure_done(self) -> None:
        """Nettoyage d'état après la fin globale d'un effacement."""
        self._erasing_devs.clear()
        self.root.after(0, self._refresh_disks)

    def process_disk_wrapper(self, disk: str, fs_choice: str,
                              passes: int, erase_method: str) -> None:
        """Wrapper for process_disk that updates GUI status."""
        disk_name = disk.replace('/dev/', '')
        try:
            disk_id = get_disk_serial(disk_name)
            self.status_var.set(f"Erasing {disk_id}...")
        except Exception as e:
            self.update_gui_log(f"Error getting disk serial: {str(e)}")
            self.status_var.set(f"Erasing {disk_name}...")

        try:
            use_crypto  = (erase_method == "crypto")
            crypto_fill = self.crypto_fill_var.get() if use_crypto else "random"
            process_disk(disk_name, fs_choice, passes, use_crypto, crypto_fill,
                         log_func=self.update_gui_log)
        except Exception as e:
            self.update_gui_log(f"Error processing {disk_name}: {str(e)}")
            raise

    # ── Helpers ───────────────────────────────────────────────────────────────
    def update_progress(self, value: float) -> None:
        try:
            self.progress_var.set(value)
            self.root.update_idletasks()
        except (tk.TclError, ValueError, TypeError) as e:
            self.update_gui_log(f"Error updating progress bar: {str(e)}")
            log_error(f"Error updating progress bar: {str(e)}")

    def update_gui_log(self, message: str) -> None:
        """Update the GUI log window with a message (for display only)."""
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
        except (tk.TclError, ValueError, TypeError, OSError) as e:
            try:
                log_error(f"Error updating GUI log: {str(e)}")
            except (IOError, OSError):
                pass


# ── Point d'entrée ─────────────────────────────────────────────────────────────
def run_gui_mode() -> None:
    """Run the GUI version"""
    try:
        root = tk.Tk()
        DiskEraserInstallerGUI(root)
        root.mainloop()
    except tk.TclError as e:
        print(f"GUI initialization error: {str(e)}")
        log_error(f"GUI initialization error: {str(e)}")
        sys.exit(1)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"Required GUI library not available: {str(e)}")
        log_error(f"Required GUI library not available: {str(e)}")
        sys.exit(1)
    except MemoryError:
        print("Insufficient memory to start GUI")
        log_error("Insufficient memory to start GUI")
        sys.exit(1)
    except OSError as e:
        print(f"System error starting GUI: {str(e)}")
        log_error(f"System error starting GUI: {str(e)}")
        sys.exit(1)
