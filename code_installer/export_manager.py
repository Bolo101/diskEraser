"""
export_manager.py – Export de fichiers PDF/logs vers un support amovible.

Règles de sécurité :
  - Seuls les fichiers dans LOG_DIR ou PDF_DIR sont proposés.
  - L'utilisateur sélectionne les fichiers ET la destination.
  - Aucun autre répertoire n'est accessible depuis cet écran.
"""
import logging
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple

from log_handler import LOG_DIR, PDF_DIR, get_all_log_files

logger = logging.getLogger("disk_eraser")

# ── Détection des supports amovibles ──────────────────────────────────────────

def get_removable_mounts() -> List[Tuple[str, str]]:
    """
    Retourne la liste des supports amovibles montés : [(device, mountpoint), …].
    Filtre sur les périphériques USB/amovibles via lsblk.
    """
    mounts: List[Tuple[str, str]] = []
    try:
        result = subprocess.run(
            ["lsblk", "-o", "NAME,MOUNTPOINT,RM,TYPE", "-l", "-n"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True,
        )
        for line in result.stdout.decode().splitlines():
            parts = line.split()
            # NAME MOUNTPOINT RM TYPE
            if len(parts) < 4:
                continue
            name, mp, rm, typ = parts[0], parts[1] if len(parts) > 1 else "", parts[-2], parts[-1]
            # Amovible (RM=1) monté et de type 'part' ou 'disk'
            if rm == "1" and mp and mp != "" and mp != "[SWAP]" and typ in ("part", "disk"):
                mounts.append((f"/dev/{name}", mp))
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.error(f"Erreur détection supports amovibles : {e}")
    return mounts


# ── Dialogue d'export ──────────────────────────────────────────────────────────

class ExportDialog(tk.Toplevel):
    """
    Fenêtre modale d'export de fichiers.
    Affiche en deux onglets :
      - Rapports PDF  (/var/log/disk_eraser/pdf/)
      - Logs bruts    (/var/log/disk_eraser/)
    L'utilisateur coche les fichiers à exporter et choisit la destination.
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Exporter des fichiers vers un support amovible")
        self.resizable(False, False)
        self.grab_set()                 # modal
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._file_vars: dict[str, tk.BooleanVar] = {}
        self._build_ui()
        self._refresh_all()

        # Centre par rapport au parent
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    # ── Construction UI ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Titre
        ttk.Label(self, text="Sélectionner les fichiers à exporter",
                  font=("Arial", 13, "bold")).pack(padx=16, pady=(14, 4))

        # Notebook : onglet PDF / onglet Logs bruts
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        self._pdf_frame = ttk.Frame(nb)
        self._log_frame = ttk.Frame(nb)
        nb.add(self._pdf_frame, text="Rapports PDF")
        nb.add(self._log_frame, text="Logs bruts")

        self._build_file_list(self._pdf_frame, "pdf")
        self._build_file_list(self._log_frame, "log")

        # Destination
        dest_frame = ttk.LabelFrame(self, text="Support de destination")
        dest_frame.pack(fill=tk.X, padx=12, pady=4)

        inner = ttk.Frame(dest_frame)
        inner.pack(fill=tk.X, padx=6, pady=4)

        self._dest_var = tk.StringVar()
        self._dest_combo = ttk.Combobox(inner, textvariable=self._dest_var,
                                        state="readonly", width=46)
        self._dest_combo.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(inner, text="↺ Actualiser",
                   command=self._refresh_mounts).pack(side=tk.LEFT)

        # Boutons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Exporter",
                   command=self._do_export).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Fermer",
                   command=self.destroy).pack(side=tk.LEFT, padx=8)

    def _build_file_list(self, frame: ttk.Frame, kind: str) -> None:
        canvas = tk.Canvas(frame, height=200)
        vsb    = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Stocke la référence pour pouvoir reconstruire lors du rafraîchissement
        setattr(self, f"_{kind}_list_frame", inner)
        setattr(self, f"_{kind}_canvas",     canvas)

    # ── Rafraîchissement ───────────────────────────────────────────────────────
    def _refresh_all(self) -> None:
        self._refresh_file_list("pdf", PDF_DIR, [".pdf"])
        self._refresh_file_list("log", LOG_DIR,  [""])    # tous les fichiers
        self._refresh_mounts()

    def _refresh_file_list(self, kind: str, directory: str,
                           extensions: List[str]) -> None:
        frame: ttk.Frame = getattr(self, f"_{kind}_list_frame")

        for w in frame.winfo_children():
            w.destroy()

        try:
            entries = sorted(os.listdir(directory)) if os.path.isdir(directory) else []
        except OSError:
            entries = []

        # Filtre : on n'affiche que les fichiers (pas les sous-dossiers)
        # et on s'assure que le chemin absolu reste dans directory
        displayed = 0
        for name in entries:
            full = os.path.join(directory, name)
            if not os.path.isfile(full):
                continue
            if extensions != [""]:
                if not any(name.endswith(ext) for ext in extensions):
                    continue
            key = full
            if key not in self._file_vars:
                self._file_vars[key] = tk.BooleanVar(value=False)
            size_kb = os.path.getsize(full) // 1024
            label   = f"{name}  ({size_kb} Ko)"
            ttk.Checkbutton(frame, text=label,
                            variable=self._file_vars[key]).pack(anchor="w", padx=4)
            displayed += 1

        if displayed == 0:
            ttk.Label(frame, text="(aucun fichier disponible)",
                      foreground="gray").pack(padx=8, pady=4)

    def _refresh_mounts(self) -> None:
        mounts = get_removable_mounts()
        if mounts:
            options = [f"{mp}  ({dev})" for dev, mp in mounts]
            self._dest_combo["values"] = options
            self._dest_var.set(options[0])
        else:
            self._dest_combo["values"] = ["(aucun support amovible détecté)"]
            self._dest_var.set("(aucun support amovible détecté)")

    # ── Export ─────────────────────────────────────────────────────────────────
    def _do_export(self) -> None:
        # Vérifie la destination
        dest_str = self._dest_var.get()
        if dest_str.startswith("("):
            messagebox.showerror("Erreur",
                "Aucun support amovible monté.\n"
                "Insérez le support et cliquez sur ↺ Actualiser.",
                parent=self)
            return

        # Extrait le point de montage (premier token)
        mountpoint = dest_str.split("  ")[0].strip()
        if not os.path.isdir(mountpoint):
            messagebox.showerror("Erreur",
                f"Point de montage introuvable : {mountpoint}", parent=self)
            return

        # Fichiers sélectionnés
        selected = [path for path, var in self._file_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Attention",
                "Aucun fichier sélectionné.", parent=self)
            return

        # Vérification de sécurité : chaque fichier doit être dans LOG_DIR
        allowed_dirs = (
            os.path.realpath(LOG_DIR),
            os.path.realpath(PDF_DIR),
        )
        for path in selected:
            real = os.path.realpath(path)
            if not any(real.startswith(d) for d in allowed_dirs):
                messagebox.showerror("Erreur de sécurité",
                    f"Fichier non autorisé : {path}\n"
                    "Seuls les fichiers de log et PDF peuvent être exportés.",
                    parent=self)
                return

        # Copie
        errors: List[str] = []
        copied = 0
        for path in selected:
            dst = os.path.join(mountpoint, os.path.basename(path))
            try:
                shutil.copy2(path, dst)
                copied += 1
                logger.info(f"Export : {path} → {dst}")
            except (OSError, shutil.Error) as e:
                errors.append(f"{os.path.basename(path)} : {e}")
                logger.error(f"Erreur export {path} : {e}")

        # Rapport final
        if errors:
            messagebox.showwarning("Export partiel",
                f"{copied} fichier(s) copié(s).\n\nErreurs :\n" +
                "\n".join(errors), parent=self)
        else:
            messagebox.showinfo("Export réussi",
                f"{copied} fichier(s) exporté(s) vers {mountpoint}.",
                parent=self)