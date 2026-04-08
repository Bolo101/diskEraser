import os
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from subprocess import CalledProcessError, SubprocessError
from tkinter import messagebox, ttk
from typing import Dict, List
from subprocess import CalledProcessError, SubprocessError
from admin_interface import open_admin_panel
from disk_erase import get_disk_serial, is_ssd
from disk_format import format_disk
from disk_operations import get_active_disk, process_disk
from disk_partition import partition_disk
from log_handler import (log_error, log_info, log_erasure_process_completed,
                          log_erasure_process_stopped, session_start)
from stats_manager import get_wipe_count
from utils import get_base_disk, get_disk_list



class DiskEraserInstallerGUI:
    """Fenêtre principale de la borne de blanchiment (mode installé)."""

    _REFRESH_INTERVAL_MS = 1000

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Borne de blanchiment – Secure Disk Eraser")
        self.root.geometry("800x600")
        self.root.attributes("-fullscreen", True)

        # Intercepte toutes les tentatives de fermeture
        self.root.protocol("WM_DELETE_WINDOW", self._block_close)

        self.disk_vars: Dict[str, tk.BooleanVar]   = {}
        self.filesystem_var  = tk.StringVar(value="ntfs")
        self.passes_var      = tk.StringVar(value="5")
        self.erase_method_var = tk.StringVar(value="overwrite")
        self.crypto_fill_var  = tk.StringVar(value="random")
        self.disks: List[Dict[str, str]] = []
        self.active_disk  = get_active_disk()
        self._erasure_running = False

        # Ensemble des disques actuellement en cours d'effacement
        # (utilisé pour conserver leur état coché pendant le refresh automatique)
        self._erasing_devs: set = set()

        # Vérification root
        if os.geteuid() != 0:
            messagebox.showerror("Erreur", "Ce programme doit être lancé en root !")
            root.destroy()
            sys.exit(1)

        session_start()
        self._build_ui()
        self._refresh_disks()
        # Lance la boucle de rafraîchissement automatique
        self.root.after(self._REFRESH_INTERVAL_MS, self._auto_refresh_disks)
        self._update_wipe_counter()

    # ── Construction UI ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Barre de titre avec compteur
        title_bar = ttk.Frame(self.root, padding=6)
        title_bar.pack(fill=tk.X)

        ttk.Label(title_bar, text="Borne de blanchiment de disques",
                  font=("Arial", 16, "bold")).pack(side=tk.LEFT)

        counter_frame = ttk.Frame(title_bar)
        counter_frame.pack(side=tk.RIGHT, padx=12)
        ttk.Label(counter_frame, text="Supports blanchis :").pack(side=tk.LEFT)
        self._counter_var = tk.StringVar(value="0")
        ttk.Label(counter_frame, textvariable=self._counter_var,
                  font=("Arial", 14, "bold"), foreground="#1a6e1a").pack(side=tk.LEFT, padx=6)

        ttk.Separator(self.root).pack(fill=tk.X)

        # Contenu principal
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── Colonne gauche : sélection des disques ──
        disk_frame = ttk.LabelFrame(main_frame, text="Disques à effacer", padding=6)
        disk_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self.disk_canvas = tk.Canvas(disk_frame)
        vsb = ttk.Scrollbar(disk_frame, orient="vertical", command=self.disk_canvas.yview)
        self.scrollable_disk_frame = ttk.Frame(self.disk_canvas)

        self.scrollable_disk_frame.bind(
            "<Configure>",
            lambda e: self.disk_canvas.configure(scrollregion=self.disk_canvas.bbox("all")),
        )
        self.disk_canvas.create_window((0, 0), window=self.scrollable_disk_frame, anchor="nw")
        self.disk_canvas.configure(yscrollcommand=vsb.set)
        self.disk_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._disclaimer_var    = tk.StringVar()
        self._ssd_disclaimer_var = tk.StringVar()
        ttk.Label(disk_frame, textvariable=self._disclaimer_var,
                  foreground="red",  wraplength=260).pack(side=tk.BOTTOM, pady=2)
        ttk.Label(disk_frame, textvariable=self._ssd_disclaimer_var,
                  foreground="blue", wraplength=260).pack(side=tk.BOTTOM, pady=2)

        # ── Colonne droite : options + actions ──
        right = ttk.Frame(main_frame)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))

        # Méthode d'effacement
        method_frame = ttk.LabelFrame(right, text="Méthode d'effacement", padding=8)
        method_frame.pack(fill=tk.X, pady=4)

        for text, val in [("Écrasement standard", "overwrite"),
                          ("Effacement cryptographique", "crypto")]:
            ttk.Radiobutton(method_frame, text=text, value=val,
                            variable=self.erase_method_var,
                            command=self._update_method_options).pack(anchor="w")

        # Nombre de passes (toujours visible)
        self._passes_frame = ttk.LabelFrame(right, text="Nombre de passes", padding=4)
        self._passes_frame.pack(fill=tk.X, pady=2)
        ttk.Label(self._passes_frame, text="Passes :").pack(side=tk.LEFT, padx=4)
        self.passes_entry = ttk.Entry(self._passes_frame, textvariable=self.passes_var, width=5)
        self.passes_entry.pack(side=tk.LEFT, padx=4)
        self.passes_label = ttk.Label(self._passes_frame, text="(actif en mode écrasement)")
        self.passes_label.pack(side=tk.LEFT)

        # Remplissage crypto (toujours visible)
        self._crypto_fill_frame = ttk.LabelFrame(right, text="Remplissage crypto", padding=4)
        self._crypto_fill_frame.pack(fill=tk.X, pady=2)
        for text, val in [("Données aléatoires", "random"), ("Zéros", "zero")]:
            ttk.Radiobutton(self._crypto_fill_frame, text=text, value=val,
                            variable=self.crypto_fill_var).pack(anchor="w")
        self.crypto_label = ttk.Label(self._crypto_fill_frame, text="(actif en mode crypto)")
        self.crypto_label.pack(side=tk.BOTTOM, pady=2)

        # Système de fichiers
        fs_frame = ttk.LabelFrame(right, text="Système de fichiers", padding=8)
        fs_frame.pack(fill=tk.X, pady=4)

        for text, val in [("NTFS", "ntfs"), ("ext4", "ext4"), ("FAT32", "vfat")]:
            ttk.Radiobutton(fs_frame, text=text, value=val,
                            variable=self.filesystem_var).pack(anchor="w")

        # Actions principales
        actions_frame = ttk.LabelFrame(right, text="Actions", padding=8)
        actions_frame.pack(fill=tk.X, pady=4)

        self._start_btn = ttk.Button(actions_frame, text="▶  Lancer l'effacement",
                                     command=self._start_erasure)
        self._start_btn.pack(fill=tk.X, pady=3)

        self._stop_btn = ttk.Button(actions_frame, text="■  Arrêter",
                                    command=self._stop_erasure, state="disabled")
        self._stop_btn.pack(fill=tk.X, pady=3)

        ttk.Button(actions_frame, text="≡  Formater uniquement (sans effacer)",
                   command=self._format_only).pack(fill=tk.X, pady=3)

        ttk.Separator(actions_frame).pack(fill=tk.X, pady=6)

        ttk.Button(actions_frame, text="◆  Administration",
                   command=self._open_admin).pack(fill=tk.X, pady=3)

        # Barre de progression + statut
        prog_frame = ttk.LabelFrame(self.root, text="Progression", padding=6)
        prog_frame.pack(fill=tk.X, padx=10, pady=4)

        self._progress_var = tk.DoubleVar()
        ttk.Progressbar(prog_frame, variable=self._progress_var,
                        maximum=100).pack(fill=tk.X, padx=6, pady=4)
        self._status_var = tk.StringVar(value="Prêt")
        ttk.Label(prog_frame, textvariable=self._status_var).pack()

        # Journal d'activité (lecture seule)
        log_frame = ttk.LabelFrame(self.root, text="Journal d'activité", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        self._log_text = tk.Text(log_frame, height=8, state="disabled",
                                  font=("Courier", 9), wrap="word")
        log_vsb = ttk.Scrollbar(log_frame, orient="vertical",
                                 command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_vsb.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._update_method_options()

    # ── Méthode d'effacement ───────────────────────────────────────────────────
    def _update_method_options(self) -> None:
        """Met à jour l'état visuel des options selon le mode sélectionné."""
        method = self.erase_method_var.get()

        crypto_children = self._crypto_fill_frame.winfo_children()

        if method == "overwrite":
            self.passes_entry.configure(state="normal")
            self.passes_label.configure(foreground="black")

            for child in crypto_children:
                if isinstance(child, ttk.Radiobutton):
                    child.configure(state="disabled")
            self.crypto_label.configure(foreground="gray")

        else:
            self.passes_entry.configure(state="disabled")
            self.passes_label.configure(foreground="gray")

            for child in crypto_children:
                if isinstance(child, ttk.Radiobutton):
                    child.configure(state="normal")
            self.crypto_label.configure(foreground="black")

    # ── Rafraîchissement automatique des disques ───────────────────────────────
    def _auto_refresh_disks(self) -> None:
        if not self._erasure_running:
            self._refresh_disks()
        self.root.after(self._REFRESH_INTERVAL_MS, self._auto_refresh_disks)

    def _refresh_disks(self) -> None:
        for w in self.scrollable_disk_frame.winfo_children():
            w.destroy()

        previous_selection: Dict[str, bool] = {
            dev: var.get() for dev, var in self.disk_vars.items()
        }
        self.disk_vars.clear()

        self.disks = get_disk_list()
        active_set = set(self.active_disk or [])
        has_ssd = False

        self._disclaimer_var.set("")
        self._ssd_disclaimer_var.set("")

        for disk in self.disks:
            dev  = disk["device"]
            name = dev.replace("/dev/", "")
            is_active = name in active_set or get_base_disk(name) in active_set

            if is_active:
                if not self._get_active_drive_logged():
                    log_info(f"Disque système détecté (exclu) : {name}")
                    self._set_active_drive_logged(True)
                self._disclaimer_var.set(
                    f"⚠ {name} est le disque système et ne peut pas être effacé.")
                continue

            label = f"{name}  {disk.get('size', '')}  {disk.get('model', '')}  [{disk.get('label', '')}]"

            was_checked = previous_selection.get(dev, False)
            is_erasing  = dev in self._erasing_devs
            var = tk.BooleanVar(value=was_checked or is_erasing)
            self.disk_vars[dev] = var

            cb = ttk.Checkbutton(
                self.scrollable_disk_frame,
                text=label,
                variable=var,
                command=lambda d=name: self._on_disk_toggle(d),
            )
            if is_erasing:
                cb.configure(state="disabled")
            cb.pack(anchor="w", padx=6, pady=2)

            if is_ssd(name):
                has_ssd = True

        if has_ssd:
            self._ssd_disclaimer_var.set(
                "ℹ Un ou plusieurs SSD détectés. L'effacement cryptographique est recommandé.")

    def _get_active_drive_logged(self) -> bool:
        return getattr(self, "_active_drive_logged", False)

    def _set_active_drive_logged(self, v: bool) -> None:
        self._active_drive_logged = v

    def _on_disk_toggle(self, disk_name: str) -> None:
        if is_ssd(disk_name):
            self._ssd_disclaimer_var.set(
                f"ℹ {disk_name} est un SSD : l'effacement cryptographique est conseillé.")

    # ── Effacement ────────────────────────────────────────────────────────────
    def _start_erasure(self) -> None:
        selected = [dev for dev, var in self.disk_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Attention", "Aucun disque sélectionné.", parent=self.root)
            return

        names = "\n".join(f"  • {d}" for d in selected)
        if not messagebox.askyesno(
            "Confirmation",
            f"AVERTISSEMENT : Effacement irréversible de :\n{names}\n\n"
            "Confirmer l'opération ?",
            parent=self.root,
        ):
            return

        try:
            passes = int(self.passes_var.get())
            if passes < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erreur", "Nombre de passes invalide.", parent=self.root)
            return

        self._erasure_running = True
        self._erasing_devs = set(selected)
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._progress_var.set(0)

        threading.Thread(target=self._run_erasure,
                         args=(selected, self.filesystem_var.get(),
                               passes, self.erase_method_var.get()),
                         daemon=True).start()

    def _stop_erasure(self) -> None:
        self._erasure_running = False
        self._erasing_devs.clear()
        self._status_var.set("Arrêt demandé…")
        log_erasure_process_stopped()
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")

    def _run_erasure(self, disks: List[str], fs: str, passes: int, method: str) -> None:
        total = len(disks)
        done  = 0

        try:
            with ThreadPoolExecutor(max_workers=max(1, total)) as pool:
                futures = {
                    pool.submit(self._erase_one, dev, fs, passes, method): dev
                    for dev in disks
                }
                for future in as_completed(futures):
                    dev = futures[future]
                    try:
                        future.result()
                        done += 1
                        self._erasing_devs.discard(dev)
                        self._update_progress(done / total * 100)
                        self._status_var.set(f"Terminé : {done}/{total} disques")
                    except Exception as exc:
                        self._erasing_devs.discard(dev)
                        self._gui_log(f"Erreur sur {dev} : {exc}")
                        log_error(f"Erreur sur {dev} : {exc}")
        except Exception as exc:
            self._gui_log(f"Erreur générale : {exc}")
            log_error(f"Erreur générale : {exc}")

        log_erasure_process_completed()
        self._update_wipe_counter()
        self.root.after(0, self._on_erasure_done)

    def _erase_one(self, dev: str, fs: str, passes: int, method: str) -> None:
        name = dev.replace("/dev/", "")
        use_crypto  = (method == "crypto")
        crypto_fill = self.crypto_fill_var.get() if use_crypto else "random"

        process_disk(name, fs, passes, use_crypto, crypto_fill,
                     log_func=self._gui_log)

    def _format_only(self) -> None:
        """Partitionne et formate les disques sélectionnés sans effacement préalable."""
        selected = [dev for dev, var in self.disk_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Attention", "Aucun disque sélectionné.", parent=self.root)
            return

        fs_choice = self.filesystem_var.get()
        names = "\n".join(f"  • {d}" for d in selected)
        if not messagebox.askyesno(
            "Confirmation – Formatage uniquement",
            f"AVERTISSEMENT : Les disques suivants seront partitionnés\n"
            f"et formatés en {fs_choice} SANS effacement sécurisé préalable :\n\n"
            f"{names}\n\n"
            "Toutes les données seront perdues.\n\n"
            "Confirmer ?",
            parent=self.root,
        ):
            return

        self._start_btn.configure(state="disabled")
        self._progress_var.set(0)
        self._status_var.set("Formatage en cours…")

        threading.Thread(
            target=self._format_disks_thread,
            args=(selected, fs_choice),
            daemon=True,
        ).start()

    def _format_disks_thread(self, disks: list, fs_choice: str) -> None:
        """Thread d'exécution du formatage en parallèle."""
        total = len(disks)
        done  = 0
        log_info(f"Formatage uniquement – {total} disque(s) en {fs_choice}")

        try:
            with ThreadPoolExecutor(max_workers=max(1, total)) as pool:
                futures = {
                    pool.submit(self._format_single_disk, dev, fs_choice): dev
                    for dev in disks
                }
                for future in as_completed(futures):
                    dev = futures[future]
                    try:
                        future.result()
                        done += 1
                        self._update_progress(done / total * 100)
                        self._status_var.set(f"Formaté : {done}/{total} disques")
                    except Exception as exc:
                        msg = f"Erreur formatage {dev} : {exc}"
                        self._gui_log(msg)
                        log_error(msg)
        except Exception as exc:
            msg = f"Erreur générale formatage : {exc}"
            self._gui_log(msg)
            log_error(msg)

        log_info("Formatage uniquement terminé.")
        self.root.after(0, self._on_format_done)

    def _format_single_disk(self, dev: str, fs_choice: str) -> None:
        """Partitionne puis formate un seul disque."""
        name = dev.replace("/dev/", "")
        try:
            disk_id = get_disk_serial(name)
        except (CalledProcessError, SubprocessError, FileNotFoundError, OSError):
            disk_id = name

        self._gui_log(f"Partitionnement de {disk_id}…")
        log_info(f"Partitionnement (format only) : {disk_id}")
        try:
            partition_disk(name)
        except (CalledProcessError, FileNotFoundError, PermissionError, OSError) as exc:
            msg = f"Erreur partitionnement {disk_id} : {exc}"
            self._gui_log(msg)
            log_error(msg)
            raise

        self._gui_log(f"Formatage de {disk_id} en {fs_choice}…")
        log_info(f"Formatage (format only) : {disk_id} → {fs_choice}")
        try:
            format_disk(name, fs_choice)
            self._gui_log(f"✓ {disk_id} formaté en {fs_choice}")
            log_info(f"Formatage terminé : {disk_id}")
        except (CalledProcessError, FileNotFoundError, PermissionError, OSError) as exc:
            msg = f"Erreur formatage {disk_id} : {exc}"
            self._gui_log(msg)
            log_error(msg)
            raise

    def _on_format_done(self) -> None:
        self._start_btn.configure(state="normal")
        messagebox.showinfo("Terminé", "Formatage terminé.", parent=self.root)

    def _on_erasure_done(self) -> None:
        self._erasure_running = False
        self._erasing_devs.clear()
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        messagebox.showinfo("Terminé",
            "L'effacement est terminé.\n," \
            "Vous pouvez maintenant retirer les supports.",
            parent=self.root)

    # ── Compteur ──────────────────────────────────────────────────────────────
    def _update_wipe_counter(self) -> None:
        count = get_wipe_count()
        if hasattr(self, "_counter_var"):
            self.root.after(0, lambda: self._counter_var.set(str(count)))

    # ── Admin ─────────────────────────────────────────────────────────────────
    def _open_admin(self) -> None:
        open_admin_panel(self.root)
        # Actualise le compteur après fermeture du panneau admin
        self._update_wipe_counter()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _block_close(self) -> None:
        """Empêche la fermeture de la fenêtre sans passer par l'admin."""
        messagebox.showinfo("Accès restreint",
            "Pour quitter l'application, utilisez le bouton Administration.",
            parent=self.root)

    def _update_progress(self, value: float) -> None:
        self.root.after(0, lambda: self._progress_var.set(value))

    def _gui_log(self, message: str) -> None:
        """Ajoute un message dans le journal d'activité (thread-safe)."""
        def _insert():
            try:
                ts  = time.strftime("%H:%M:%S")
                self._log_text.configure(state="normal")
                self._log_text.insert(tk.END, f"[{ts}] {message}\n")
                self._log_text.see(tk.END)
                self._log_text.configure(state="disabled")
            except tk.TclError:
                pass
        self.root.after(0, _insert)


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def run_gui_mode() -> None:
    try:
        root = tk.Tk()
        DiskEraserInstallerGUI(root)
        root.mainloop()
    except tk.TclError as e:
        print(f"Erreur GUI : {e}", file=sys.stderr)
        sys.exit(1)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"Module manquant : {e}", file=sys.stderr)
        sys.exit(1)
    except MemoryError:
        print("Mémoire insuffisante.", file=sys.stderr)
        sys.exit(1)