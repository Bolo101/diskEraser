"""
admin_interface.py – Interface d'administration sécurisée par mot de passe.

Fonctionnalités :
  • Compteur de supports blanchis (total cumulé)
  • Génération PDF : rapport de session / logs complets
  • Export de fichiers vers support amovible
  • Purge des logs
  • Changement du mot de passe admin
  • Quitter (ferme l'application → retour à l'OS)
  • Redémarrer / Éteindre
"""
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config_manager import (change_password, is_password_set,
                             set_password, verify_password)
from export_manager import ExportDialog
from log_handler import (generate_log_file_pdf, generate_session_pdf,
                          log_info, log_error, log_application_exit, purge_logs)
from stats_manager import get_history, get_wipe_count, reset_counter


# ── Dialogue de saisie du mot de passe ────────────────────────────────────────

class PasswordDialog(tk.Toplevel):
    """Fenêtre modale de saisie du mot de passe admin."""

    def __init__(self, parent: tk.Widget, title: str = "Authentification") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.result: str | None = None

        ttk.Label(self, text="Mot de passe administrateur :",
                  font=("Arial", 11)).pack(padx=20, pady=(16, 4))
        self._entry = ttk.Entry(self, show="•", width=28, font=("Arial", 11))
        self._entry.pack(padx=20, pady=4)
        self._entry.bind("<Return>", lambda _: self._ok())
        self._entry.focus_set()

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK",     command=self._ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Annuler", command=self._cancel).pack(side=tk.LEFT, padx=6)

        self._center(parent)
        self.wait_window()

    def _center(self, parent: tk.Widget) -> None:
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _ok(self) -> None:
        self.result = self._entry.get()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


# ── Dialogue de premier lancement (définition du mot de passe) ────────────────

def prompt_initial_password(parent: tk.Widget) -> None:
    """
    Affiché au premier démarrage : force la création du mot de passe admin.
    Boucle jusqu'à ce qu'un mot de passe valide soit défini.
    """
    while True:
        win = tk.Toplevel(parent)
        win.title("Configuration initiale – Mot de passe administrateur")
        win.resizable(False, False)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)   # non fermable

        ttk.Label(win,
                  text="Définissez le mot de passe administrateur.",
                  font=("Arial", 11, "bold")).pack(padx=20, pady=(14, 6))
        ttk.Label(win,
                  text="Ce mot de passe protège l'interface d'administration\n"
                       "(génération de rapports, export, arrêt système…)",
                  justify=tk.LEFT).pack(padx=20)

        fields: dict[str, ttk.Entry] = {}
        for label in ("Mot de passe :", "Confirmer :"):
            ttk.Label(win, text=label).pack(anchor="w", padx=20, pady=(6, 0))
            e = ttk.Entry(win, show="•", width=28)
            e.pack(padx=20, pady=2)
            fields[label] = e

        err_var = tk.StringVar()
        ttk.Label(win, textvariable=err_var, foreground="red").pack(pady=2)

        submitted: list[bool] = [False]

        def on_submit() -> None:
            pw  = fields["Mot de passe :"].get()
            pw2 = fields["Confirmer :"].get()
            if len(pw) < 8:
                err_var.set("Le mot de passe doit comporter au moins 8 caractères.")
                return
            if pw != pw2:
                err_var.set("Les mots de passe ne correspondent pas.")
                return
            try:
                set_password(pw)
                submitted[0] = True
                win.destroy()
            except Exception as exc:
                err_var.set(f"Erreur : {exc}")

        ttk.Button(win, text="Définir le mot de passe", command=on_submit).pack(pady=10)
        win.wait_window()

        if submitted[0]:
            log_info("Mot de passe administrateur défini avec succès.")
            break
        # Si la fenêtre est détruite sans soumission (ne devrait pas arriver)


# ── Interface d'administration ─────────────────────────────────────────────────

class AdminInterface(tk.Toplevel):
    """
    Fenêtre d'administration complète, ouverte après authentification réussie.
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self._parent = parent
        self.title("Administration – Borne de blanchiment")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build_ui()
        self._refresh_stats()
        self._center()

    # ── Construction UI ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # ── En-tête ──
        header = ttk.Frame(self, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Interface d'administration",
                  font=("Arial", 15, "bold")).pack()

        # ── Statistiques ──
        stats_frame = ttk.LabelFrame(self, text="Statistiques", padding=10)
        stats_frame.pack(fill=tk.X, padx=14, pady=6)

        self._count_var = tk.StringVar(value="—")
        ttk.Label(stats_frame, text="Supports blanchis (total) :").grid(
            row=0, column=0, sticky="w")
        ttk.Label(stats_frame, textvariable=self._count_var,
                  font=("Arial", 22, "bold"), foreground="#1a6e1a").grid(
            row=0, column=1, padx=12)

        ttk.Button(stats_frame, text="Voir l'historique",
                   command=self._show_history).grid(row=0, column=2, padx=6)
        ttk.Button(stats_frame, text="Remettre à zéro",
                   command=self._reset_counter).grid(row=0, column=3, padx=6)

        # ── Rapports PDF ──
        pdf_frame = ttk.LabelFrame(self, text="Rapports PDF", padding=10)
        pdf_frame.pack(fill=tk.X, padx=14, pady=4)

        ttk.Button(pdf_frame, text="📄 Générer rapport session (PDF)",
                   command=self._gen_session_pdf, width=38).pack(
            side=tk.LEFT, padx=6)
        ttk.Button(pdf_frame, text="📚 Générer logs complets (PDF)",
                   command=self._gen_full_pdf, width=38).pack(
            side=tk.LEFT, padx=6)

        # ── Export ──
        exp_frame = ttk.LabelFrame(self, text="Export vers support amovible", padding=10)
        exp_frame.pack(fill=tk.X, padx=14, pady=4)

        ttk.Button(exp_frame,
                   text="💾 Exporter fichiers (PDF ou logs bruts) vers clé USB…",
                   command=self._open_export, width=55).pack()

        # ── Maintenance ──
        maint_frame = ttk.LabelFrame(self, text="Maintenance", padding=10)
        maint_frame.pack(fill=tk.X, padx=14, pady=4)

        ttk.Button(maint_frame, text="🗑  Purger tous les logs",
                   command=self._purge_logs, width=28).grid(
            row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Button(maint_frame, text="🔑 Changer le mot de passe admin",
                   command=self._change_password, width=32).grid(
            row=0, column=1, padx=6, pady=4, sticky="w")

        # ── Système ──
        sys_frame = ttk.LabelFrame(self, text="Système", padding=10)
        sys_frame.pack(fill=tk.X, padx=14, pady=4)

        ttk.Button(sys_frame, text="⏻  Éteindre",
                   command=self._shutdown, width=18).grid(
            row=0, column=0, padx=8, pady=4)
        ttk.Button(sys_frame, text="↺  Redémarrer",
                   command=self._reboot, width=18).grid(
            row=0, column=1, padx=8, pady=4)
        ttk.Button(sys_frame, text="🖥  Quitter vers l'OS",
                   command=self._exit_to_os, width=20).grid(
            row=0, column=2, padx=8, pady=4)

        # ── Fermer panneau admin ──
        ttk.Separator(self).pack(fill=tk.X, padx=14, pady=6)
        ttk.Button(self, text="Fermer ce panneau",
                   command=self.destroy, width=24).pack(pady=(0, 12))

    # ── Centrage ──────────────────────────────────────────────────────────────
    def _center(self) -> None:
        self.update_idletasks()
        px = self._parent.winfo_rootx() + (self._parent.winfo_width()  - self.winfo_width())  // 2
        py = self._parent.winfo_rooty() + (self._parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    # ── Actions ───────────────────────────────────────────────────────────────
    def _refresh_stats(self) -> None:
        self._count_var.set(str(get_wipe_count()))

    def _show_history(self) -> None:
        history = get_history()
        win = tk.Toplevel(self)
        win.title("Historique des blanchiments")
        win.grab_set()

        cols = ("N°", "Date", "Disque", "FS", "Méthode")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=130 if col != "N°" else 40)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for entry in reversed(history):
            tree.insert("", "end", values=(
                entry.get("count_at", ""),
                entry.get("date", ""),
                entry.get("disk_id", ""),
                entry.get("filesystem", ""),
                entry.get("method", ""),
            ))

        ttk.Button(win, text="Fermer", command=win.destroy).pack(pady=6)

    def _reset_counter(self) -> None:
        if not messagebox.askyesno(
            "Confirmer",
            "Remettre le compteur de supports blanchis à zéro ?\n\n"
            "L'historique complet sera effacé.",
            parent=self,
        ):
            return
        reset_counter()
        self._refresh_stats()
        log_info("Compteur remis à zéro par l'administrateur.")
        messagebox.showinfo("Succès", "Compteur remis à zéro.", parent=self)

    def _gen_session_pdf(self) -> None:
        try:
            path = generate_session_pdf()
            messagebox.showinfo("PDF généré",
                f"Rapport de session enregistré :\n{path}", parent=self)
        except ValueError as e:
            messagebox.showwarning("Attention", str(e), parent=self)
        except (PermissionError, OSError) as e:
            messagebox.showerror("Erreur", f"Impossible de créer le PDF :\n{e}", parent=self)

    def _gen_full_pdf(self) -> None:
        try:
            path = generate_log_file_pdf()
            messagebox.showinfo("PDF généré",
                f"Logs complets enregistrés :\n{path}", parent=self)
        except ValueError as e:
            messagebox.showwarning("Attention", str(e), parent=self)
        except (PermissionError, OSError) as e:
            messagebox.showerror("Erreur", f"Impossible de créer le PDF :\n{e}", parent=self)

    def _open_export(self) -> None:
        ExportDialog(self)

    def _purge_logs(self) -> None:
        if not messagebox.askyesno(
            "Confirmer la purge",
            "Supprimer TOUS les fichiers de log ?\n\n"
            "Cette action est irréversible.\n"
            "Les rapports PDF existants ne seront PAS supprimés.",
            parent=self,
        ):
            return
        purge_logs()
        messagebox.showinfo("Logs purgés",
            "Tous les fichiers de log ont été supprimés.", parent=self)

    def _change_password(self) -> None:
        win = tk.Toplevel(self)
        win.title("Changer le mot de passe")
        win.resizable(False, False)
        win.grab_set()

        fields: dict[str, ttk.Entry] = {}
        for label in ("Ancien mot de passe :", "Nouveau mot de passe :", "Confirmer :"):
            ttk.Label(win, text=label).pack(anchor="w", padx=20, pady=(8, 0))
            e = ttk.Entry(win, show="•", width=26)
            e.pack(padx=20, pady=2)
            fields[label] = e

        err_var = tk.StringVar()
        ttk.Label(win, textvariable=err_var, foreground="red").pack(pady=2)

        def submit() -> None:
            old = fields["Ancien mot de passe :"].get()
            new = fields["Nouveau mot de passe :"].get()
            cnf = fields["Confirmer :"].get()
            if len(new) < 8:
                err_var.set("Le nouveau mot de passe doit faire au moins 8 caractères.")
                return
            if new != cnf:
                err_var.set("Les nouveaux mots de passe ne correspondent pas.")
                return
            try:
                change_password(old, new)
                win.destroy()
                messagebox.showinfo("Succès", "Mot de passe modifié.", parent=self)
                log_info("Mot de passe admin modifié.")
            except ValueError as exc:
                err_var.set(str(exc))

        ttk.Button(win, text="Valider", command=submit).pack(pady=10)

    def _shutdown(self) -> None:
        if messagebox.askyesno("Éteindre",
            "Éteindre le système maintenant ?", parent=self):
            log_application_exit("Arrêt système via admin")
            try:
                subprocess.run(["shutdown", "-h", "now"], check=False)
            except FileNotFoundError:
                subprocess.run(["poweroff"], check=False)

    def _reboot(self) -> None:
        if messagebox.askyesno("Redémarrer",
            "Redémarrer le système maintenant ?", parent=self):
            log_application_exit("Redémarrage via admin")
            try:
                subprocess.run(["reboot"], check=False)
            except FileNotFoundError:
                subprocess.run(["shutdown", "-r", "now"], check=False)

    def _exit_to_os(self) -> None:
        if messagebox.askyesno(
            "Quitter vers l'OS",
            "Fermer l'application et retourner au système d'exploitation ?",
            parent=self,
        ):
            log_application_exit("Sortie vers l'OS via admin")
            self._parent.destroy()


# ── Point d'entrée : ouvre l'admin après authentification ─────────────────────

def open_admin_panel(parent: tk.Widget) -> None:
    """
    Vérifie l'authentification puis ouvre le panneau admin.
    Gère aussi le premier lancement (définition du mot de passe).
    """
    if not is_password_set():
        prompt_initial_password(parent)

    dlg = PasswordDialog(parent, title="Accès administration")
    if dlg.result is None:
        return   # annulé

    if not verify_password(dlg.result):
        messagebox.showerror("Accès refusé",
            "Mot de passe incorrect.", parent=parent)
        log_error("Tentative d'accès admin avec un mot de passe incorrect.")
        return

    log_info("Accès au panneau d'administration accordé.")
    AdminInterface(parent)