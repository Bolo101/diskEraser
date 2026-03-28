#!/usr/bin/env python3
"""
main.py (installer) – Point d'entrée de la borne de blanchiment installée.

Lance directement l'interface graphique kiosque.
Nécessite les droits root.
"""
import os
import sys

from admin_interface import prompt_initial_password
from config_manager import is_password_set
from gui_interface import run_gui_mode


def main() -> None:
    # ── Vérification root ──
    if os.geteuid() != 0:
        print("Ce programme doit être exécuté en tant que root.", file=sys.stderr)
        sys.exit(1)

    # ── Premier lancement : définition du mot de passe admin ──
    # On utilise tkinter pour ne pas casser le flux GUI
    if not is_password_set():
        import tkinter as tk
        _bootstrap = tk.Tk()
        _bootstrap.withdraw()
        prompt_initial_password(_bootstrap)
        _bootstrap.destroy()

    # ── Lancement de l'interface kiosque ──
    run_gui_mode()


if __name__ == "__main__":
    main()