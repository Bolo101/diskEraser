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


# ── Couleurs partagées (miroir de gui_interface.THEME) ────────────────────────

_BG          = "#f0f2f5"
_HEADER_BG   = "#1e3a5f"
_HEADER_FG   = "#ffffff"
_LF_FG       = "#1e3a5f"
_BTN_ACTION  = "#2980b9"
_BTN_ACT_A   = "#2471a3"
_BTN_ACT_D   = "#aac4e0"
_BTN_DANGER  = "#e74c3c"
_BTN_DNG_A   = "#c0392b"
_BTN_DNG_D   = "#f1a9a0"
_BTN_SYS     = "#5d6d7e"
_BTN_SYS_A   = "#4d5d6e"
_BTN_SYS_D   = "#b0bec5"
_BTN_CLOSE   = "#27ae60"
_BTN_CLOSE_A = "#1e8449"
_COUNTER_FG  = "#2ecc71"


def _apply_admin_styles(root: tk.Widget) -> None:
    """
    Applique les styles ttk propres à l'admin.
    Appelé une seule fois au premier Toplevel ; inoffensif si rappelé.
    """
    style = ttk.Style(root)
    # Thème de base (identique à gui_interface)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TFrame",       background=_BG)
    style.configure("TLabel",       background=_BG, font=("Helvetica", 10))
    style.configure("TEntry",       fieldbackground="white", font=("Helvetica", 10))
    style.configure("TScrollbar",   background="#c0c7d0", troughcolor=_BG)
    style.configure("TLabelframe",
                    background=_BG, bordercolor="#c0c7d0",
                    relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label",
                    background=_BG,
                    font=("Helvetica", 10, "bold"),
                    foreground=_LF_FG)

    style.configure("AdminHeader.TFrame", background=_HEADER_BG)
    style.configure("AdminHeader.TLabel",
                    background=_HEADER_BG, foreground=_HEADER_FG,
                    font=("Helvetica", 15, "bold"))

    _abtn(style, "Action",  _BTN_ACTION,  _BTN_ACT_A,   _BTN_ACT_D)
    _abtn(style, "Danger",  _BTN_DANGER,  _BTN_DNG_A,   _BTN_DNG_D)
    _abtn(style, "Sys",     _BTN_SYS,     _BTN_SYS_A,   _BTN_SYS_D)
    _abtn(style, "Close",   _BTN_CLOSE,   _BTN_CLOSE_A, _BTN_CLOSE_A)


def _abtn(style: ttk.Style, name: str, bg: str,
          bg_a: str, bg_d: str, bold: bool = False) -> None:
    font = ("Helvetica", 10, "bold") if bold else ("Helvetica", 10)
    style.configure(f"Admin{name}.TButton",
                    foreground="white", background=bg,
                    font=font, borderwidth=0,
                    padding=(12, 7), relief="flat")
    style.map(f"Admin{name}.TButton",
              background=[("active", bg_a), ("disabled", bg_d)],
              foreground=[("disabled", "#ffffffaa")])


# ── Dialogue de saisie du mot de passe ────────────────────────────────────────

class PasswordDialog(tk.Toplevel):
    """Fenêtre modale de saisie du mot de passe admin."""

    def __init__(self, parent: tk.Widget,
                 title: str = "Authentification") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.configure(bg=_BG)

        _apply_admin_styles(self)

        self.result: str | None = None

        # En-tête
        header = ttk.Frame(self, style="AdminHeader.TFrame", padding=(20, 12))
        header.pack(fill=tk.X)
        ttk.Label(header, text="Authentification administrateur",
                  style="AdminHeader.TLabel").pack()

        # Corps
        body = ttk.Frame(self, padding=(20, 14))
        body.pack(fill=tk.X)

        ttk.Label(body, text="Mot de passe administrateur :").pack(anchor="w")
        self._entry = ttk.Entry(body, show="•", width=28, font=("Helvetica", 11))
        self._entry.pack(fill=tk.X, pady=(4, 10))
        self._entry.bind("<Return>", lambda _: self._ok())
        self._entry.focus_set()

        btn_frame = ttk.Frame(body)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Valider",  command=self._ok,
                   style="AdminClose.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Annuler", command=self._cancel,
                   style="AdminSys.TButton").pack(side=tk.LEFT)

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


# ── Dialogue de premier lancement ─────────────────────────────────────────────

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
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        win.configure(bg=_BG)

        _apply_admin_styles(win)

        # En-tête
        header = ttk.Frame(win, style="AdminHeader.TFrame", padding=(20, 12))
        header.pack(fill=tk.X)
        ttk.Label(header, text="Configuration initiale",
                  style="AdminHeader.TLabel").pack()

        # Corps
        body = ttk.Frame(win, padding=(20, 14))
        body.pack(fill=tk.X)

        ttk.Label(body, text="Définissez le mot de passe administrateur.",
                  font=("Helvetica", 11, "bold")).pack(anchor="w")
        ttk.Label(body,
                  text="Ce mot de passe protège l'interface d'administration\n"
                       "(génération de rapports, export, arrêt système…)",
                  foreground="#5d6d7e",
                  justify=tk.LEFT).pack(anchor="w", pady=(4, 12))

        fields: dict[str, ttk.Entry] = {}
        for label in ("Mot de passe :", "Confirmer :"):
            ttk.Label(body, text=label).pack(anchor="w")
            e = ttk.Entry(body, show="•", width=28, font=("Helvetica", 10))
            e.pack(fill=tk.X, pady=(2, 8))
            fields[label] = e

        err_var = tk.StringVar()
        ttk.Label(body, textvariable=err_var, foreground="#e74c3c").pack(pady=2)

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

        ttk.Button(body, text="Définir le mot de passe",
                   command=on_submit,
                   style="AdminClose.TButton").pack(pady=(6, 0))
        win.wait_window()

        if submitted[0]:
            log_info("Mot de passe administrateur défini avec succès.")
            break


# ── Interface d'administration ─────────────────────────────────────────────────

class AdminInterface(tk.Toplevel):
    """Fenêtre d'administration complète, ouverte après authentification."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self._parent = parent
        self.title("Administration – Borne de blanchiment")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.configure(bg=_BG)

        _apply_admin_styles(self)
        self._build_ui()
        self._refresh_stats()
        self._center()
        self.wait_window()

    # ── Construction UI ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # En-tête
        header = ttk.Frame(self, style="AdminHeader.TFrame", padding=(20, 12))
        header.pack(fill=tk.X)
        ttk.Label(header, text="Interface d'administration",
                  style="AdminHeader.TLabel").pack(side=tk.LEFT)

        # Corps
        body = ttk.Frame(self, padding=(14, 10))
        body.pack(fill=tk.BOTH, expand=True)

        # ── Statistiques ──
        stats_frame = ttk.LabelFrame(body, text="Statistiques", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 8))

        left_stats = ttk.Frame(stats_frame)
        left_stats.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(left_stats, text="Supports blanchis (total) :",
                  font=("Helvetica", 10)).pack(anchor="w")
        self._count_var = tk.StringVar(value="—")
        tk.Label(left_stats, textvariable=self._count_var,
                 font=("Helvetica", 28, "bold"),
                 foreground=_COUNTER_FG, bg=_BG).pack(anchor="w", pady=(2, 0))

        right_stats = ttk.Frame(stats_frame)
        right_stats.pack(side=tk.RIGHT, fill=tk.Y, anchor="center", padx=10)
        ttk.Button(right_stats, text="Voir l'historique",
                   command=self._show_history,
                   style="AdminAction.TButton").pack(fill=tk.X, pady=3)
        ttk.Button(right_stats, text="Remettre à zéro",
                   command=self._reset_counter,
                   style="AdminDanger.TButton").pack(fill=tk.X, pady=3)

        # ── Rapports PDF ──
        pdf_frame = ttk.LabelFrame(body, text="Rapports PDF", padding=10)
        pdf_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(pdf_frame, text="→  Générer rapport de session (PDF)",
                   command=self._gen_session_pdf,
                   style="AdminAction.TButton").pack(
            side=tk.LEFT, padx=(0, 8))
        ttk.Button(pdf_frame, text="→  Générer logs complets (PDF)",
                   command=self._gen_full_pdf,
                   style="AdminAction.TButton").pack(side=tk.LEFT)

        # ── Export ──
        exp_frame = ttk.LabelFrame(body, text="Export vers support amovible", padding=10)
        exp_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(exp_frame,
                   text="→  Exporter fichiers (PDF ou logs bruts) vers clé USB…",
                   command=self._open_export,
                   style="AdminAction.TButton").pack(fill=tk.X)

        # ── Maintenance ──
        maint_frame = ttk.LabelFrame(body, text="Maintenance", padding=10)
        maint_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(maint_frame, text="×  Purger tous les logs",
                   command=self._purge_logs,
                   style="AdminDanger.TButton").pack(
            side=tk.LEFT, padx=(0, 8))
        ttk.Button(maint_frame, text="◇  Changer le mot de passe admin",
                   command=self._change_password,
                   style="AdminSys.TButton").pack(side=tk.LEFT)

        # ── Système ──
        sys_frame = ttk.LabelFrame(body, text="Système", padding=10)
        sys_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(sys_frame, text="■  Éteindre",
                   command=self._shutdown,
                   style="AdminDanger.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(sys_frame, text="↺  Redémarrer",
                   command=self._reboot,
                   style="AdminSys.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(sys_frame, text="←  Quitter vers l'OS",
                   command=self._exit_to_os,
                   style="AdminSys.TButton").pack(side=tk.LEFT)

        # ── Séparateur + Fermer ──
        ttk.Separator(body).pack(fill=tk.X, pady=8)
        ttk.Button(body, text="Fermer ce panneau",
                   command=self.destroy,
                   style="AdminClose.TButton").pack(pady=(0, 4))

    # ── Centrage ──────────────────────────────────────────────────────────────
    def _center(self) -> None:
        self.update_idletasks()
        px = self._parent.winfo_rootx() + \
             (self._parent.winfo_width()  - self.winfo_width())  // 2
        py = self._parent.winfo_rooty() + \
             (self._parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    # ── Actions ───────────────────────────────────────────────────────────────
    def _refresh_stats(self) -> None:
        self._count_var.set(str(get_wipe_count()))

    def _show_history(self) -> None:
        history = get_history()
        win = tk.Toplevel(self)
        win.title("Historique des blanchiments")
        win.grab_set()
        win.configure(bg=_BG)

        _apply_admin_styles(win)

        cols = ("N°", "Date", "Disque", "FS", "Méthode")
        style = ttk.Style(win)
        style.configure("History.Treeview",
                         background="white", fieldbackground="white",
                         font=("Helvetica", 10), rowheight=24)
        style.configure("History.Treeview.Heading",
                         font=("Helvetica", 10, "bold"),
                         background="#e8edf2", foreground=_LF_FG)

        tree = ttk.Treeview(win, columns=cols, show="headings",
                             height=15, style="History.Treeview")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=130 if col != "N°" else 44, anchor="w")

        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, padx=(10, 0), pady=10, sticky="nsew")
        vsb.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ns")
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        for entry in reversed(history):
            tree.insert("", "end", values=(
                entry.get("count_at", ""),
                entry.get("date", ""),
                entry.get("disk_id", ""),
                entry.get("filesystem", ""),
                entry.get("method", ""),
            ))

        ttk.Button(win, text="Fermer", command=win.destroy,
                   style="AdminClose.TButton").grid(
            row=1, column=0, columnspan=2, pady=6)

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
            messagebox.showerror("Erreur",
                f"Impossible de créer le PDF :\n{e}", parent=self)

    def _gen_full_pdf(self) -> None:
        try:
            path = generate_log_file_pdf()
            messagebox.showinfo("PDF généré",
                f"Logs complets enregistrés :\n{path}", parent=self)
        except ValueError as e:
            messagebox.showwarning("Attention", str(e), parent=self)
        except (PermissionError, OSError) as e:
            messagebox.showerror("Erreur",
                f"Impossible de créer le PDF :\n{e}", parent=self)

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
        win.configure(bg=_BG)

        _apply_admin_styles(win)

        # En-tête
        header = ttk.Frame(win, style="AdminHeader.TFrame", padding=(20, 10))
        header.pack(fill=tk.X)
        ttk.Label(header, text="Changement de mot de passe",
                  style="AdminHeader.TLabel").pack()

        body = ttk.Frame(win, padding=(20, 14))
        body.pack(fill=tk.X)

        fields: dict[str, ttk.Entry] = {}
        for label in ("Ancien mot de passe :", "Nouveau mot de passe :", "Confirmer :"):
            ttk.Label(body, text=label).pack(anchor="w")
            e = ttk.Entry(body, show="•", width=28, font=("Helvetica", 10))
            e.pack(fill=tk.X, pady=(2, 8))
            fields[label] = e

        err_var = tk.StringVar()
        ttk.Label(body, textvariable=err_var, foreground="#e74c3c").pack(pady=2)

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

        ttk.Button(body, text="Valider", command=submit,
                   style="AdminClose.TButton").pack(pady=(4, 0))

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


# ── Point d'entrée ────────────────────────────────────────────────────────────

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