"""
log_handler.py (installer) – Journalisation avec rotation par volumétrie.

Rotation : dès que disk_erase.log dépasse MAX_LOG_SIZE, il est renommé
           disk_erase.log.YYYYMMDD_HHMMSS et un nouveau fichier démarre.
           Les MAX_ROTATED_FILES plus anciens rotated sont supprimés.

Structure :
  /var/log/disk_eraser/disk_erase.log          ← journal courant
  /var/log/disk_eraser/disk_erase.log.*        ← journaux tournés
  /var/log/disk_eraser/pdf/                    ← rapports PDF
"""
import glob
import logging
import os
import sys
import textwrap
from datetime import datetime
from typing import List

# ── Constantes ─────────────────────────────────────────────────────────────────
LOG_DIR          = "/var/log/disk_eraser"
LOG_FILE         = os.path.join(LOG_DIR, "disk_erase.log")
PDF_DIR          = os.path.join(LOG_DIR, "pdf")
MAX_LOG_SIZE     = 10 * 1024 * 1024   # 10 Mo
MAX_ROTATED_FILES = 10

# ── État de session ─────────────────────────────────────────────────────────────
_session_logs: List[str] = []
_session_active: bool    = False


# ── Handler de capture de session ─────────────────────────────────────────────
class SessionCapturingHandler(logging.Handler):
    """Capture tous les messages de log pendant la session courante."""
    def emit(self, record: logging.LogRecord) -> None:
        global _session_logs, _session_active
        if _session_active:
            ts  = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            msg = f"[{ts}] {record.levelname}: {record.getMessage()}"
            _session_logs.append(msg)


# ── Rotation des logs ──────────────────────────────────────────────────────────
def _rotate_if_needed() -> None:
    """Rotate le fichier de log courant si sa taille dépasse MAX_LOG_SIZE."""
    if not os.path.isfile(LOG_FILE):
        return
    if os.path.getsize(LOG_FILE) < MAX_LOG_SIZE:
        return

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    rotated = f"{LOG_FILE}.{ts}"
    try:
        os.rename(LOG_FILE, rotated)
    except OSError as e:
        print(f"[log_handler] Impossible de pivoter le log : {e}", file=sys.stderr)
        return

    # Suppression des plus anciens si dépassement du quota
    pattern  = f"{LOG_FILE}.*"
    existing = sorted(glob.glob(pattern))
    while len(existing) > MAX_ROTATED_FILES:
        oldest = existing.pop(0)
        try:
            os.remove(oldest)
        except OSError:
            pass


def _setup_file_handler() -> None:
    """(Re)crée le FileHandler après rotation ou au démarrage."""
    global _file_handler
    
    # Supprime l'ancien handler s'il existe
    try:
        if _file_handler:
            _logger.removeHandler(_file_handler)
            _file_handler.close()
    except NameError:
        pass

    try:
        handler = logging.FileHandler(LOG_FILE)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        _logger.addHandler(handler)
        _file_handler = handler
    except (PermissionError, OSError) as e:
        print(f"[log_handler] Impossible d'ouvrir le fichier de log : {e}", file=sys.stderr)


# ── Initialisation du logger ───────────────────────────────────────────────────
os.makedirs(LOG_DIR, mode=0o750, exist_ok=True)
os.makedirs(PDF_DIR, mode=0o750, exist_ok=True)

_logger = logging.getLogger("disk_eraser")
_logger.setLevel(logging.INFO)
_logger.propagate = False

# Handler console
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
_logger.addHandler(_console_handler)

# Handler session
_session_handler = SessionCapturingHandler()
_logger.addHandler(_session_handler)

# Handler fichier (après rotation éventuelle)
_file_handler = None
_rotate_if_needed()
_setup_file_handler()


# ── API de journalisation ──────────────────────────────────────────────────────
def log_info(message: str) -> None:
    _logger.info(message)


def log_error(message: str) -> None:
    _logger.error(message)


def log_warning(message: str) -> None:
    _logger.warning(message)


def log_erase_operation(disk_id: str, filesystem: str, method: str) -> None:
    msg = (f"Effacement – disque: {disk_id} | "
           f"système de fichiers: {filesystem} | méthode: {method}")
    _logger.info(msg)


def log_disk_completed(disk_id: str) -> None:
    _logger.info(f"Opérations terminées sur le disque : {disk_id}")


def session_start() -> None:
    global _session_logs, _session_active
    _session_logs   = []
    _session_active = True

    # Rotation avant démarrage si nécessaire
    _rotate_if_needed()
    _setup_file_handler()

    sep = "=" * 80
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n{sep}\nSESSION START: {ts}\n{sep}\n")
    except OSError as e:
        _logger.error(f"Impossible d'écrire le début de session : {e}")

    log_info(f"Nouvelle session démarrée à {ts}")


def session_end() -> None:
    global _session_active
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_info(f"Session terminée à {ts}")
    _session_active = False

    sep = "=" * 80
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n{sep}\nSESSION END: {ts}\n{sep}\n\n")
    except OSError as e:
        _logger.error(f"Impossible d'écrire la fin de session : {e}")


def log_application_exit(exit_method: str = "Bouton Quitter") -> None:
    log_info(f"Application fermée via : {exit_method}")
    session_end()


def log_erasure_process_completed() -> None:
    log_info("Processus d'effacement terminé.")


def log_erasure_process_stopped() -> None:
    log_info("Processus d'effacement arrêté par l'utilisateur.")


def get_current_session_logs() -> List[str]:
    return _session_logs.copy()


def is_session_active() -> bool:
    return _session_active


def get_all_log_files() -> List[str]:
    """Retourne la liste de tous les fichiers de log (courant + tournés), triés du plus récent au plus ancien."""
    files = []
    if os.path.isfile(LOG_FILE):
        files.append(LOG_FILE)
    rotated = sorted(glob.glob(f"{LOG_FILE}.*"), reverse=True)
    files.extend(rotated)
    return files


def purge_logs() -> None:
    """Supprime tous les fichiers de log (courant + tournés). Réservé à l'admin."""
    for f in get_all_log_files():
        try:
            os.remove(f)
        except OSError as e:
            _logger.error(f"Impossible de supprimer {f} : {e}")
    # Recrée un fichier vide
    _setup_file_handler()
    log_info("Logs purgés par l'administrateur.")


# ── Génération PDF ─────────────────────────────────────────────────────────────
def generate_session_pdf(output_path: str = None) -> str:
    """Génère un PDF du rapport de session courante. Retourne le chemin du PDF."""
    session_logs = get_current_session_logs()
    if not session_logs:
        raise ValueError("Aucun log de session disponible.")

    if output_path is None:
        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"session_{ts}.pdf"
        output_path  = os.path.join(PDF_DIR, pdf_filename)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    _create_simple_pdf(
        output_path,
        "Rapport de session – Blanchiment de disques",
        session_logs,
        f"Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Entrées de log : {len(session_logs)}",
    )
    log_info(f"PDF de session généré : {output_path}")
    return output_path


def generate_log_file_pdf(output_path: str = None) -> str:
    """Génère un PDF consolidé de tous les logs (courant + tournés). Retourne le chemin du PDF."""
    all_lines: List[str] = []
    for log_file in get_all_log_files():
        try:
            with open(log_file, "r", errors="replace") as f:
                all_lines.append(f"{'='*60}")
                all_lines.append(f"Fichier : {os.path.basename(log_file)}")
                all_lines.append(f"{'='*60}")
                all_lines.extend(f.read().splitlines())
        except OSError as e:
            all_lines.append(f"[Erreur lecture {log_file} : {e}]")

    if not all_lines:
        raise ValueError("Aucun log disponible.")

    if output_path is None:
        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"logs_complets_{ts}.pdf"
        output_path  = os.path.join(PDF_DIR, pdf_filename)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    _create_simple_pdf(
        output_path,
        "Logs complets – Blanchiment de disques",
        all_lines,
        f"Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Fichiers sources : {len(get_all_log_files())}",
        f"Lignes totales : {len(all_lines)}",
    )
    log_info(f"PDF logs complets généré : {output_path}")
    return output_path


# ── Construction PDF bas niveau (stdlib uniquement) ─────────────────────────────
def _escape_pdf_string(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\\", "\\\\")
    text = text.replace("(", "\\(")
    text = text.replace(")", "\\)")
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return "".join(c if 32 <= ord(c) <= 126 else " " for c in text)


def _create_simple_pdf(pdf_path: str, title: str, lines: List[str], *info_lines: str) -> None:
    LINES_PER_PAGE = 55
    wrapped: List[str] = []
    for i, line in enumerate(lines, 1):
        prefix = f"{i:4d}: "
        avail  = 90 - len(prefix)
        for j, part in enumerate(textwrap.wrap(line or " ", avail, break_long_words=True) or [" "]):
            wrapped.append(f"{prefix if j == 0 else '      '}{part}")

    pages = [wrapped[i: i + LINES_PER_PAGE] for i in range(0, max(1, len(wrapped)), LINES_PER_PAGE)]

    objects: List[str] = []

    def add(obj: str) -> int:
        objects.append(obj)
        return len(objects)   # 1-based

    # Catalog + Pages placeholder (will patch offsets later)
    catalog_id  = add("")   # 1 – catalog
    pages_id    = add("")   # 2 – pages dict
    font_id     = add(      # 3 – font
        "3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj"
    )

    page_ids: List[int] = []
    stream_ids: List[int] = []

    for p_idx, page_lines in enumerate(pages):
        is_first = (p_idx == 0)
        page_num = p_idx + 1

        # Build content stream
        content_lines: List[str] = ["BT", "/F1 8 Tf"]
        if is_first:
            content_lines += [
                "50 750 Td", "/F1 14 Tf",
                f"({_escape_pdf_string(title)}) Tj",
                "/F1 9 Tf",
            ]
            for il in info_lines:
                content_lines += ["0 -14 Td", f"({_escape_pdf_string(il)}) Tj"]
            content_lines += ["0 -18 Td", "/F1 8 Tf"]
        else:
            content_lines += [
                "50 750 Td", "/F1 11 Tf",
                f"({_escape_pdf_string(f'{title} – page {page_num}')}) Tj",
                "0 -20 Td", "/F1 8 Tf",
            ]

        for cl in page_lines:
            content_lines += ["0 -11 Td", f"({_escape_pdf_string(cl)}) Tj"]

        content_lines += ["50 25 Td", "/F1 7 Tf",
                          f"(Page {page_num}/{len(pages)}) Tj", "ET"]
        stream_body = "\n".join(content_lines)

        sid = add(
            f"{len(objects)+1} 0 obj\n<< /Length {len(stream_body)} >>\n"
            f"stream\n{stream_body}\nendstream\nendobj"
        )
        stream_ids.append(sid)

        pid = add(
            f"{len(objects)+1} 0 obj\n"
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Contents {sid} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>\n"
            f"endobj"
        )
        page_ids.append(pid)

    # Fix catalog and pages objects
    objects[catalog_id - 1] = (
        f"1 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj"
    )
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[pages_id - 1] = (
        f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>\nendobj"
    )

    # Renumber all objects
    numbered: List[str] = []
    for i, obj in enumerate(objects, 1):
        if not obj.startswith(f"{i} 0 obj"):
            obj = f"{i} 0 obj\n" + obj.split(" 0 obj\n", 1)[-1]
        numbered.append(obj)

    # Write PDF
    body  = "%PDF-1.4\n"
    offsets: List[int] = []
    for obj in numbered:
        offsets.append(len(body))
        body += obj + "\n"

    xref_offset = len(body)
    xref  = f"xref\n0 {len(numbered)+1}\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n"

    trailer = (
        f"trailer\n<< /Size {len(numbered)+1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )

    with open(pdf_path, "w", errors="replace") as f:
        f.write(body + xref + trailer)