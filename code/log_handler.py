import logging
import sys
import os
from datetime import datetime
from typing import List
import textwrap

# Define the log file path
log_file = "/var/log/disk_erase.log"

# Session tracking - capture all logs during current session
_session_logs = []
_session_active = False

class SessionCapturingHandler(logging.Handler):
    """Custom handler to capture session logs"""
    def emit(self, record):
        global _session_logs, _session_active
        if _session_active:
            # Format the message the same way as the file handler
            timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
            formatted_message = f"[{timestamp}] {record.levelname}: {record.getMessage()}"
            _session_logs.append(formatted_message)

# Configure logging with basic format
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Add session capturing handler
session_handler = SessionCapturingHandler()
logger.addHandler(session_handler)

try:
    log_handler = logging.FileHandler(log_file)
    log_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)
except PermissionError:
    print("Error: Permission denied. Please run the script with sudo.", file=sys.stderr)
    sys.exit(1)  # Exit the script to enforce sudo usage
except FileNotFoundError:
    print(f"Error: Log directory does not exist: {os.path.dirname(log_file)}", file=sys.stderr)
    sys.exit(1)
except OSError as e:
    print(f"Error: Unable to create log handler: {e}", file=sys.stderr)
    sys.exit(1)


def log_info(message: str) -> None:
    """Log general information to both the console and log file."""
    logger.info(message)

def log_error(message: str) -> None:
    """Log error message to both the console and log file."""
    logger.error(message)

def log_warning(message: str) -> None:
    """Log warning message to both the console and log file."""
    logger.warning(message)

def log_erase_operation(disk_id: str, filesystem: str, method: str) -> None:
    """Log detailed erasure operation with stable disk identifier."""
    message = f"Erasure operation for disk ID: {disk_id}. Filesystem: {filesystem}. Erase method: {method}"
    logger.info(message)

def log_disk_completed(disk_id: str) -> None:
    """Log completion of operations on a single disk without ending session."""
    message = f"Completed operations on disk ID: {disk_id}"
    logger.info(message)

def session_start() -> None:
    """Log session start with clear separator and begin session log capture"""
    global _session_logs, _session_active
    
    # Clear previous session logs and start capturing
    _session_logs = []
    _session_active = True
    
    separator = "=" * 80
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        with open(log_file, "a") as f:
            f.write(f"\n{separator}\n")
            f.write(f"SESSION START: {timestamp}\n")
            f.write(f"{separator}\n")
    except PermissionError:
        log_error("Permission denied when writing session start to log file")
        return
    except OSError as e:
        log_error(f"OS error when writing session start: {e}")
        return
    except IOError as e:
        log_error(f"IO error when writing session start: {e}")
        return
    
    # This will be captured in session logs too
    log_info(f"New session started at {timestamp}")

def session_end() -> None:
    """Log session end with clear separator and stop session log capture"""
    global _session_active
    
    separator = "=" * 80
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Log session end (this will be captured before we stop)
    log_info(f"Session ended at {timestamp}")
    
    # Stop capturing session logs
    _session_active = False
    
    try:
        with open(log_file, "a") as f:
            f.write(f"\n{separator}\n")
            f.write(f"SESSION END: {timestamp}\n")
            f.write(f"{separator}\n\n")
    except PermissionError:
        log_error("Permission denied when writing session end to log file")
    except OSError as e:
        log_error(f"OS error when writing session end: {e}")
    except IOError as e:
        log_error(f"IO error when writing session end: {e}")

def log_application_exit(exit_method: str = "Exit button") -> None:
    """Log application exit and end session properly."""
    log_info(f"Application closed by user via {exit_method}")
    session_end()

def log_erasure_process_completed() -> None:
    """Log that the erasure process is completed but don't end session."""
    log_info("Erasure process completed")

def log_erasure_process_stopped() -> None:
    """Log that the erasure process was stopped by user but don't end session."""
    log_info("Erasure process stopped by user")

def get_current_session_logs() -> List[str]:
    """Get all logs from the current session"""
    global _session_logs
    return _session_logs.copy()

def is_session_active() -> bool:
    """Check if a logging session is currently active"""
    global _session_active
    return _session_active

def generate_session_pdf(output_path: str = None) -> str:
    """
    Generate a PDF from current session logs using built-in libraries only.
    
    Args:
        output_path (str, optional): Full path for the output PDF file.
                                     If None, a default path in /tmp is used.
    
    Returns:
        str: Path to the generated PDF file
    
    Raises:
        ValueError: If no session logs are available
        PermissionError: If unable to write to output directory
        OSError: If filesystem operations fail
    """
    # Get current session logs
    session_logs = get_current_session_logs()
    
    if not session_logs:
        raise ValueError("No session logs available to generate PDF")
    
    if output_path:
        # Use the provided output path directly
        pdf_path = output_path
        # Ensure the parent directory exists
        output_dir = os.path.dirname(pdf_path)
        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
            except PermissionError:
                error_msg = f"Permission denied creating directory: {output_dir}"
                log_error(error_msg)
                raise PermissionError(error_msg)
            except OSError as e:
                error_msg = f"OS error creating directory {output_dir}: {str(e)}"
                log_error(error_msg)
                raise OSError(error_msg)
    else:
        # Default: create output directory in /tmp
        output_dir = "/tmp/disk_cloner_logs"
        try:
            os.makedirs(output_dir, exist_ok=True)
        except PermissionError:
            error_msg = f"Permission denied creating directory: {output_dir}"
            log_error(error_msg)
            raise PermissionError(error_msg)
        except OSError as e:
            error_msg = f"OS error creating directory {output_dir}: {str(e)}"
            log_error(error_msg)
            raise OSError(error_msg)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"disk_cloner_session_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
    
    try:
        # Create PDF using basic PDF structure
        _create_simple_pdf(
            pdf_path,
            "Disk Cloner - Session Log Report",
            session_logs,
            f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Log Entries: {len(session_logs)}"
        )
        
        log_info(f"Session log PDF generated successfully: {pdf_path}")
        return pdf_path
        
    except PermissionError:
        error_msg = f"Permission denied writing PDF to {pdf_path}"
        log_error(error_msg)
        raise
    except OSError as e:
        error_msg = f"OS error during PDF generation: {str(e)}"
        log_error(error_msg)
        raise
    except IOError as e:
        error_msg = f"IO error during PDF generation: {str(e)}"
        log_error(error_msg)
        raise IOError(error_msg)

def generate_log_file_pdf(output_path: str = None) -> str:
    """
    Generate a PDF from the complete log file using built-in libraries only.

    Args:
        output_path (str, optional): Full path for the output PDF file.
                                     If None, a default path in /tmp is used.

    Returns:
        str: Path to the generated PDF file

    Raises:
        FileNotFoundError: If log file doesn't exist
        PermissionError: If unable to read log file or write PDF
        UnicodeDecodeError: If log file has encoding issues
        OSError: If filesystem operations fail
    """
    if output_path:
        # Use the provided output path directly
        pdf_path = output_path
        output_dir = os.path.dirname(pdf_path)
        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
            except PermissionError:
                error_msg = f"Permission denied creating directory: {output_dir}"
                log_error(error_msg)
                raise PermissionError(error_msg)
            except OSError as e:
                error_msg = f"OS error creating directory {output_dir}: {str(e)}"
                log_error(error_msg)
                raise OSError(error_msg)
    else:
        # Default: create output directory in /tmp
        output_dir = "/tmp/disk_cloner_logs"
        try:
            os.makedirs(output_dir, exist_ok=True)
        except PermissionError:
            error_msg = f"Permission denied creating directory: {output_dir}"
            log_error(error_msg)
            raise PermissionError(error_msg)
        except OSError as e:
            error_msg = f"OS error creating directory {output_dir}: {str(e)}"
            log_error(error_msg)
            raise OSError(error_msg)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"disk_cloner_complete_log_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
    
    # Read log file
    if not os.path.exists(log_file):
        error_msg = f"Log file not found: {log_file}"
        log_error(error_msg)
        raise FileNotFoundError(error_msg)
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_lines = [line.strip() for line in f.readlines() if line.strip()]
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        try:
            with open(log_file, 'r', encoding='latin-1') as f:
                log_lines = [line.strip() for line in f.readlines() if line.strip()]
        except UnicodeDecodeError as e:
            error_msg = f"Unable to decode log file with UTF-8 or latin-1: {str(e)}"
            log_error(error_msg)
            raise UnicodeDecodeError(e.encoding, e.object, e.start, e.end, error_msg)
    except PermissionError:
        error_msg = f"Permission denied reading log file: {log_file}"
        log_error(error_msg)
        raise
    except OSError as e:
        error_msg = f"OS error reading log file: {str(e)}"
        log_error(error_msg)
        raise
    except IOError as e:
        error_msg = f"IO error reading log file: {str(e)}"
        log_error(error_msg)
        raise IOError(error_msg)
    
    try:
        # Create PDF using basic PDF structure
        _create_simple_pdf(
            pdf_path,
            "Disk Cloner - Complete Log File Report",
            log_lines,
            f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Log File: {log_file}",
            f"Total Log Lines: {len(log_lines)}"
        )
        
        log_info(f"Complete log file PDF generated successfully: {pdf_path}")
        return pdf_path
        
    except PermissionError:
        error_msg = f"Permission denied writing PDF to {pdf_path}"
        log_error(error_msg)
        raise
    except OSError as e:
        error_msg = f"OS error during PDF generation: {str(e)}"
        log_error(error_msg)
        raise
    except IOError as e:
        error_msg = f"IO error during PDF generation: {str(e)}"
        log_error(error_msg)
        raise IOError(error_msg)

def _create_simple_pdf(file_path: str, title: str, content_lines: List[str], *info_lines: str) -> None:
    """
    Create a simple PDF file using basic PDF structure without external libraries.
    Supports multiple pages automatically.
    
    Args:
        file_path: Path where to save the PDF
        title: Title of the document
        content_lines: List of content lines to include
        *info_lines: Additional info lines to include in header
        
    Raises:
        PermissionError: If unable to write to file
        OSError: If filesystem operations fail
        ValueError: If invalid parameters provided
    """
    if not file_path:
        raise ValueError("File path cannot be empty")
    if not title:
        raise ValueError("Title cannot be empty")
    if not isinstance(content_lines, list):
        raise ValueError("Content lines must be a list")
    
    try:
        with open(file_path, 'wb') as f:
            # PDF Header
            f.write(b'%PDF-1.4\n')
            
            # Prepare content and calculate pages needed
            try:
                pages_content = _prepare_pdf_pages(title, content_lines, *info_lines)
                num_pages = len(pages_content)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Error preparing PDF pages: {str(e)}")
            
            # Track object positions for xref table
            object_positions = {}
            
            # Object 1: Catalog
            object_positions[1] = f.tell()
            catalog_obj = b'''1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
'''
            f.write(catalog_obj)
            
            # Object 2: Pages (parent) - build page references dynamically
            object_positions[2] = f.tell()
            page_object_nums = [3 + i * 2 for i in range(num_pages)]  # Page objects: 3, 5, 7, 9, etc.
            page_refs = " ".join([f"{num} 0 R" for num in page_object_nums])
            
            pages_obj = f'''2 0 obj
<<
/Type /Pages
/Kids [{page_refs}]
/Count {num_pages}
>>
endobj
'''.encode('utf-8')
            f.write(pages_obj)
            
            # Create page objects and content streams
            obj_counter = 3
            for page_idx, page_content in enumerate(pages_content):
                content_bytes = page_content.encode('utf-8')
                content_length = len(content_bytes)
                
                # Page object (odd numbered: 3, 5, 7, etc.)
                object_positions[obj_counter] = f.tell()
                page_obj = f'''{obj_counter} 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents {obj_counter + 1} 0 R
/Resources <<
/Font <<
/F1 {3 + num_pages * 2} 0 R
>>
>>
>>
endobj
'''.encode('utf-8')
                f.write(page_obj)
                obj_counter += 1
                
                # Content stream object (even numbered: 4, 6, 8, etc.)
                object_positions[obj_counter] = f.tell()
                content_obj = f'''{obj_counter} 0 obj
<<
/Length {content_length}
>>
stream
{page_content}
endstream
endobj
'''.encode('utf-8')
                f.write(content_obj)
                obj_counter += 1
            
            # Font object (last object)
            font_obj_num = obj_counter
            object_positions[font_obj_num] = f.tell()
            font_obj = f'''{font_obj_num} 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Courier
>>
endobj
'''.encode('utf-8')
            f.write(font_obj)
            
            # Cross-reference table
            xref_start = f.tell()
            total_objects = font_obj_num + 1
            
            f.write(b'xref\n')
            f.write(f'0 {total_objects}\n'.encode())
            f.write(b'0000000000 65535 f \n')  # Object 0 (always free)
            
            # Write xref entries for all objects
            for i in range(1, total_objects):
                if i in object_positions:
                    f.write(f'{object_positions[i]:010d} 00000 n \n'.encode())
                else:
                    f.write(b'0000000000 00000 f \n')  # Mark as free if missing
            
            # Trailer
            trailer = f'''trailer
<<
/Size {total_objects}
/Root 1 0 R
>>
startxref
{xref_start}
%%EOF
'''.encode('utf-8')
            f.write(trailer)
            
    except PermissionError:
        raise PermissionError(f"Permission denied writing to file: {file_path}")
    except OSError as e:
        raise OSError(f"OS error writing PDF file: {str(e)}")
    except IOError as e:
        raise IOError(f"IO error writing PDF file: {str(e)}")
    except UnicodeEncodeError as e:
        raise ValueError(f"Unicode encoding error in PDF content: {str(e)}")

def _prepare_pdf_pages(title: str, content_lines: List[str], *info_lines: str) -> List[str]:
    """
    Prepare PDF content split into multiple pages.
    
    Args:
        title: Document title
        content_lines: List of content lines
        *info_lines: Additional info lines
    
    Returns:
        List[str]: List of page contents (PDF content streams)
        
    Raises:
        ValueError: If invalid parameters provided
        TypeError: If parameters are wrong type
    """
    if not isinstance(title, str):
        raise TypeError("Title must be a string")
    if not isinstance(content_lines, list):
        raise TypeError("Content lines must be a list")
    
    try:
        pages = []
        lines_per_page = 55  # Conservative lines that fit on a page
        first_page_content_lines = lines_per_page - 10  # Account for title and info
        other_page_content_lines = lines_per_page - 4   # Account for page header
        
        # Wrap all content lines first
        wrapped_lines = []
        display_line_number = 1
        
        if not content_lines:
            wrapped_lines = ["No content available."]
        else:
            for content_line in content_lines:
                try:
                    wrapped_content = _wrap_log_line(content_line, display_line_number)
                    wrapped_lines.extend(wrapped_content)
                    display_line_number += 1
                except (TypeError, ValueError) as e:
                    # Handle problematic lines gracefully
                    wrapped_lines.append(f"{display_line_number:4d}: [Error processing line: {str(e)}]")
                    display_line_number += 1
        
        # Split wrapped lines into pages
        processed_lines = 0
        page_num = 1
        
        while processed_lines < len(wrapped_lines):
            is_first_page = (page_num == 1)
            max_lines_this_page = first_page_content_lines if is_first_page else other_page_content_lines
            
            # Get lines for this page
            end_line = min(processed_lines + max_lines_this_page, len(wrapped_lines))
            lines_for_this_page = wrapped_lines[processed_lines:end_line]
            
            if lines_for_this_page:
                try:
                    page_content = _create_page_content(title, lines_for_this_page, page_num, is_first_page, *info_lines)
                    pages.append(page_content)
                except (ValueError, TypeError) as e:
                    # Create a fallback page if content creation fails
                    fallback_content = f"BT\n/F1 12 Tf\n50 400 Td\n(Error creating page {page_num}: {_escape_pdf_string(str(e))}) Tj\nET"
                    pages.append(fallback_content)
                
                processed_lines = end_line
                page_num += 1
                
                # Safety check to prevent infinite loops
                if page_num > 100:  # Reasonable maximum
                    break
            else:
                break
        
        # Ensure at least one page
        if not pages:
            try:
                fallback_page = _create_page_content(title, ["No content available."], 1, True, *info_lines)
                pages.append(fallback_page)
            except (ValueError, TypeError):
                # Ultimate fallback
                pages.append("BT\n/F1 12 Tf\n50 400 Td\n(Error: Unable to create page content) Tj\nET")
        
        return pages
        
    except MemoryError:
        raise ValueError("Content too large to process - out of memory")
    except RecursionError:
        raise ValueError("Content structure too complex - recursion limit exceeded")

def _create_page_content(title: str, content_lines: List[str], page_number: int, is_first_page: bool, *info_lines: str) -> str:
    """
    Create PDF content stream for a single page.
    
    Args:
        title: Document title
        content_lines: List of content lines for this page
        page_number: Current page number
        is_first_page: Whether this is the first page
        *info_lines: Additional info lines
    
    Returns:
        str: PDF content stream for this page
        
    Raises:
        ValueError: If invalid parameters provided
        TypeError: If parameters are wrong type
    """
    if not isinstance(title, str):
        raise TypeError("Title must be a string")
    if not isinstance(content_lines, list):
        raise TypeError("Content lines must be a list")
    if not isinstance(page_number, int) or page_number < 1:
        raise ValueError("Page number must be a positive integer")
    if not isinstance(is_first_page, bool):
        raise TypeError("is_first_page must be a boolean")
    
    try:
        lines = []
        
        # Start content stream
        lines.append("BT")  # Begin text
        lines.append("/F1 8 Tf")  # Set font early
        
        if is_first_page:
            # First page: full header with title and info
            lines.append("50 750 Td")  # Move to top position
            lines.append("/F1 16 Tf")  # Larger font for title
            lines.append(f"({_escape_pdf_string(title)}) Tj")
            
            # Add info lines
            lines.append("/F1 10 Tf")  # Smaller font for info
            for info_line in info_lines:
                lines.append("0 -15 Td")  # Move down 15 points
                lines.append(f"({_escape_pdf_string(info_line)}) Tj")
            
            lines.append("0 -20 Td")  # Extra space before content
            lines.append("/F1 8 Tf")   # Set content font
        else:
            # Subsequent pages: simple page header
            lines.append("50 750 Td")  # Move to top position
            lines.append("/F1 12 Tf")  # Medium font for page header
            lines.append(f"({_escape_pdf_string(f'{title} - Page {page_number}')}) Tj")
            lines.append("0 -25 Td")   # Move down before content
            lines.append("/F1 8 Tf")   # Set content font
        
        # Add content lines
        for i, content_line in enumerate(content_lines):
            lines.append("0 -12 Td")  # Move down 12 points
            try:
                escaped_line = _escape_pdf_string(content_line)
                lines.append(f"({escaped_line}) Tj")
            except (TypeError, ValueError):
                # Handle problematic content gracefully
                lines.append(f"([Line {i+1}: Error processing content]) Tj")
        
        # Add page number at bottom (move to absolute position)
        lines.append("50 30 Td")  # Move to bottom left (absolute position)
        lines.append("/F1 8 Tf")  # Ensure font is set
        lines.append(f"({_escape_pdf_string(f'Page {page_number}')}) Tj")
        
        lines.append("ET")  # End text
        
        return "\n".join(lines)
        
    except MemoryError:
        # Return a minimal error page if we run out of memory
        return f"BT\n/F1 12 Tf\n50 400 Td\n(Error: Page {page_number} - Out of memory) Tj\nET"

def _wrap_log_line(content_line: str, line_number: int, max_width: int = 75) -> List[str]:
    """
    Wrap a single log line into multiple lines if it's too long.
    
    Args:
        content_line: The original log line
        line_number: The line number to display
        max_width: Maximum characters per line (accounting for line number prefix)
    
    Returns:
        List[str]: List of wrapped lines with proper formatting
        
    Raises:
        TypeError: If parameters are wrong type
        ValueError: If parameters are invalid
    """
    if not isinstance(content_line, str):
        raise TypeError("Content line must be a string")
    if not isinstance(line_number, int) or line_number < 1:
        raise ValueError("Line number must be a positive integer")
    if not isinstance(max_width, int) or max_width < 10:
        raise ValueError("Max width must be an integer >= 10")
    
    try:
        # Calculate available width after line number prefix
        line_prefix = f"{line_number:4d}: "
        continuation_prefix = "      "  # 6 spaces to align with content
        available_width = max_width - len(line_prefix)
        
        if available_width < 10:
            # Fallback for very narrow widths
            return [f"{line_number:4d}: {content_line[:10]}..."]
        
        try:
            # Use textwrap to break long lines at word boundaries
            wrapped_content = textwrap.fill(
                content_line,
                width=available_width,
                break_long_words=True,
                break_on_hyphens=True,
                expand_tabs=True,
                replace_whitespace=False
            )
        except (TypeError, ValueError):
            # Fallback to simple truncation if textwrap fails
            if len(content_line) > available_width:
                wrapped_content = content_line[:available_width-3] + "..."
            else:
                wrapped_content = content_line
        
        wrapped_lines = wrapped_content.split('\n')
        
        # Format the lines with proper prefixes
        formatted_lines = []
        for i, line in enumerate(wrapped_lines):
            if i == 0:
                # First line gets the line number
                formatted_lines.append(f"{line_prefix}{line}")
            else:
                # Continuation lines get indented to align with content
                formatted_lines.append(f"{continuation_prefix}{line}")
        
        return formatted_lines
        
    except MemoryError:
        # Fallback for memory issues
        return [f"{line_number:4d}: [Memory error processing line]"]
    except RecursionError:
        # Fallback for recursion issues
        return [f"{line_number:4d}: [Recursion error processing line]"]

def _escape_pdf_string(text: str) -> str:
    """
    Escape special characters in PDF strings.
    
    Args:
        text: Text to escape
    
    Returns:
        str: Escaped text safe for PDF
        
    Raises:
        TypeError: If text is not a string
    """
    if text is None:
        return ""
    
    try:
        # Convert to string if not already
        text = str(text)
        
        # Replace special PDF string characters
        text = text.replace('\\', '\\\\')  # Backslash must be first
        text = text.replace('(', '\\(')
        text = text.replace(')', '\\)')
        text = text.replace('\r', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\t', ' ')
        
        # Remove or replace non-printable characters
        cleaned_text = ""
        for char in text:
            try:
                char_ord = ord(char)
                if 32 <= char_ord <= 126:
                    cleaned_text += char
                else:
                    cleaned_text += " "  # Replace with space
            except (TypeError, ValueError):
                cleaned_text += " "  # Replace problematic characters with space
        
        return cleaned_text
        
    except (TypeError, ValueError, AttributeError):
        return f"[Error processing text: {type(text).__name__}]"
    except MemoryError:
        return "[Memory error processing text]"