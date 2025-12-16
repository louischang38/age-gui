import sys
import os
import subprocess
import threading
import time
import ctypes
import configparser
import re 
import secrets
import string 
import tempfile 

# Cross-platform theme detection library (install: pip install darkdetect)
import darkdetect 
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QMessageBox, QFrame,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QSettings, QPoint
)
from PySide6.QtGui import QDropEvent, QColor, QFont, QIcon

# ==========================================
# Windows API 
# ==========================================
if os.name == 'nt':
    # Windows-specific flags for subprocess
    CREATE_NO_WINDOW = 0x08000000
    def bring_pid_to_front(pid):
        pass
else:
    CREATE_NO_WINDOW = 0
    def bring_pid_to_front(pid):
        pass


# ==========================================
#  Colors & Styling (Modernized)
# ==========================================
LIGHT_THEME_COLORS = {
    "TEXT_PRIMARY": "#212529", "TEXT_SECONDARY": "#6c757d", "BACKGROUND": "#F8F9FA",
    "CARD_BG": "#FFFFFF", "BORDER": "#CED4DA", "DANGER": "#dc3545", "DANGER_BG": "#f8d7da",
    "ACCENT": "#007bff", "SUCCESS_ACCENT": "#28a745",
    "SUCCESS_BG": "#d4edda",
}

DARK_THEME_COLORS = {
    "TEXT_PRIMARY": "#f8f9fa", "TEXT_SECONDARY": "#adb5bd", "BACKGROUND": "#212529",
    "CARD_BG": "#343a40", "BORDER": "#495057", "DANGER": "#fd7e14", "DANGER_BG": "#4e2c2f",
    "ACCENT": "#0099ff", "SUCCESS_ACCENT": "#20c997",
    "SUCCESS_BG": "#1f392f",
}

def get_base_stylesheet(colors):
    # Determine colors for specific UI elements
    border_radius = "8px"
    progress_text_color = "transparent" if colors == LIGHT_THEME_COLORS else colors["TEXT_PRIMARY"]
    
    return f"""
        QMainWindow {{ background-color: {colors["BACKGROUND"]}; }}
        QLabel {{ color: {colors["TEXT_PRIMARY"]}; }}
        
        /* General Button Styling */
        QPushButton {{
            border-radius: {border_radius}; font-weight: 500; font-size: 13px; 
            padding: 8px 15px;
            background-color: {colors["CARD_BG"]}; 
            border: 1px solid {colors["BORDER"]};
            color: {colors["TEXT_PRIMARY"]};
        }}
        QPushButton:hover {{
            background-color: {colors["BORDER"]};
            border: 1px solid {colors["BORDER"]};
        }}
        
        /* Clear Keys Button */
        QPushButton#ClearKeysBtn {{
            color: {colors["TEXT_SECONDARY"]}; 
            background-color: {colors["CARD_BG"]};
            border: 1px solid {colors["BORDER"]};
        }}
        QPushButton#ClearKeysBtn:hover {{
            color: {colors["TEXT_PRIMARY"]}; 
            background-color: {colors["BORDER"]};
        }}
        
        
        /* Clear File/State Button */
        QPushButton#ClearBtn {{
            color: {colors["DANGER"]}; 
            background-color: {colors["CARD_BG"]};
            border: 1px solid {colors["DANGER"]};
        }}
        QPushButton#ClearBtn:hover {{
            background-color: {colors["DANGER_BG"]};
            color: {colors["DANGER"]};
            border: 1px solid {colors["DANGER"]};
        }}
        
        /* Status Bar Label */
        QLabel#StatusLabel {{ 
            color: {colors['TEXT_SECONDARY']}; 
            font-size: 10px;
            padding: 0 5px;
        }}
        
        /* Progress Bar Styling */
        QProgressBar {{
            border: 1px solid {colors["BORDER"]};
            background-color: {colors["CARD_BG"]};
            border-radius: {border_radius};
            height: 12px;
            text-align: center;
            color: {progress_text_color};
            margin-top: 5px;
        }}
        QProgressBar::chunk {{
            background-color: {colors["ACCENT"]};
            border-radius: {border_radius};
            margin: 0px;
        }}
    """

# ==========================================
#  AgeWorker 
# ==========================================
class AgeWorker(QThread):
    finished = Signal(int, int, bool)
    error = Signal(str, str) # file_name, error_message
    progress_update = Signal(float)
    process_starting = Signal(str)

    def __init__(self, mode, files_to_process, keys_to_use, age_path, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.files_to_process = files_to_process
        self.keys_to_use = keys_to_use 
        self.age_path = age_path  # Path to the age executable
        self._process = None

    def _find_unique_filename(self, path):
        # Finds a unique filename if the output path already exists
        if not os.path.exists(path):
            return path
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        name, ext = os.path.splitext(filename)
        match = re.search(r' \((\d+)\)$', name)
        if match:
            base_name_without_suffix = name[:match.start()]
            start_num = int(match.group(1)) + 1
        else:
            base_name_without_suffix = name
            start_num = 1
        while True:
            new_name = f"{base_name_without_suffix} ({start_num}){ext}"
            new_path = os.path.join(directory, new_name)
            if not os.path.exists(new_path):
                return new_path
            start_num += 1

    def run(self):
        success_count = 0
        processed_files = self.files_to_process[:]
        total_files = len(processed_files) 
        needs_clear = self.mode == "encrypt"

        creation_flags = CREATE_NO_WINDOW
        
        temp_recipients_file = None 
        env = os.environ.copy()
        
        try:
            for i, input_path in enumerate(processed_files):
                current_file_name = os.path.basename(input_path)
                output_path_base = ""
                
                self.process_starting.emit(current_file_name)

                try:
                    # Use the internal age absolute path
                    cmd = [self.age_path]
                    
                    if self.mode == "encrypt":
                        temp_output_path = f"{input_path}.age" 
                        cmd.append("-a") 
                        cmd.extend(["-o", temp_output_path])
                        
                        # Encryption: Use Recipient Keys
                        if not self.keys_to_use:
                            raise Exception("Encryption requires at least one recipient public key.")
                            
                        # Write public keys to temp recipients file (-R)
                        temp_recipients_file = os.path.join(os.path.dirname(input_path) or os.getcwd(), f".temp_recipients_{os.getpid()}_{i}.txt")
                        with open(temp_recipients_file, 'w', encoding='utf-8') as f:
                            for key_path in self.keys_to_use:
                                if not os.path.exists(key_path): continue
                                with open(key_path, 'r', encoding='utf-8') as key_f:
                                    # Strip comments again for safety before passing to age
                                    content = "".join([line for line in key_f if not line.strip().startswith('#')]).strip()
                                    if content: f.write(content + '\n')
                        
                        if os.path.exists(temp_recipients_file) and os.path.getsize(temp_recipients_file):
                            cmd.extend(["-R", temp_recipients_file])
                        else:
                            raise Exception("No valid recipient public keys provided.")
                        
                        cmd.append(input_path)

                    else: # decrypt mode
                        cmd.append("-d")
                        output_path_base = input_path.removesuffix(".age") if input_path.lower().endswith(".age") else f"{input_path}.decrypted"
                        temp_decrypt_path = f"{output_path_base}.temp_decrypted_{os.getpid()}"
                        cmd.extend(["-o", temp_decrypt_path])
                        
                        # Decryption: Use Identity Keys
                        if not self.keys_to_use:
                             raise Exception("Decryption requires at least one identity key.")

                        # Pass private keys to age (-i)
                        for key_path in self.keys_to_use:
                            cmd.extend(["-i", key_path])
                        
                        cmd.append(input_path)
                    
                    # Use binary mode, manual decoding to avoid deadlock
                    self._process = subprocess.Popen(
                        cmd,
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=creation_flags
                    )
                    
                    stdout_output = ""
                    stderr_output = ""

                    try:
                        # Timeout set to 300 seconds (5 minutes) per file
                        stdout_bytes, stderr_bytes = self._process.communicate(timeout=300) 
                        stdout_output = stdout_bytes.decode('utf-8', errors='ignore')
                        stderr_output = stderr_bytes.decode('utf-8', errors='ignore')

                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        stdout_bytes, stderr_bytes = self._process.communicate() 
                        stdout_output = stdout_bytes.decode('utf-8', errors='ignore')
                        stderr_output = stderr_bytes.decode('utf-8', errors='ignore')
                        
                        return_code = 1 
                        raise Exception("Process timeout (5 minutes limit). Possible age binary hang or pipe issue.")
                        
                    return_code = self._process.returncode

                    if return_code == 0:
                        if self.mode == "encrypt":
                            pass
                        else: # decrypt mode
                            if os.path.exists(temp_decrypt_path):
                                expected_output_path = output_path_base 
                                final_output_path = self._find_unique_filename(expected_output_path)
                                os.rename(temp_decrypt_path, final_output_path)
                            else:
                                raise IOError(f"Age returned success, but output file not found: {temp_decrypt_path}")
                        success_count += 1
                    else:
                        error_msg = stderr_output.strip()
                        detail_msg = error_msg if error_msg else f"Failed, exit code: {return_code}"
                        
                        # Friendly error message hints
                        if "missing recipients" in error_msg.lower():
                            detail_msg = "Encryption failed: Missing public recipient key."
                        elif "no matching keys" in error_msg.lower():
                            detail_msg = "Decryption failed. Please check the identity keys."
                        elif "encrypted identity" in error_msg.lower():
                            detail_msg = "Decryption failed: Identity key is encrypted. Please use an unencrypted key."
                        elif "error: no secrets provided to decrypt the file" in error_msg.lower():
                            detail_msg = "Decryption failed: No identity key provided that matches the file."


                        raise Exception(detail_msg)

                except Exception as e:
                    self.error.emit(current_file_name, str(e))
                finally:
                    progress = (i + 1) / total_files
                    self.progress_update.emit(progress)
                    # Clean up temporary files
                    if temp_recipients_file and os.path.exists(temp_recipients_file):
                        try: os.remove(temp_recipients_file)
                        except: pass 
                    if self.mode == "decrypt" and 'temp_decrypt_path' in locals() and os.path.exists(temp_decrypt_path):
                        try: os.remove(temp_decrypt_path)
                        except: pass

        except Exception as e:
            self.error.emit("Pre-process", f"Pre-process Error: {e}")
            total_files = 0
        finally:
            self.finished.emit(success_count, total_files, needs_clear)


# ==========================================
#  Widget: Drop Target
# ==========================================
class SingleDropTarget(QFrame):
    files_dropped = Signal(list)
    keys_dropped = Signal(list)

    def __init__(self, main_window, colors, strings, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.colors = colors
        self.strings = strings
        self.setAcceptDrops(True)
        self.mode = "file"

        self._apply_style()
        self.setMinimumSize(320, 180)

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        self.layout.setSpacing(6)
      
        self.label = QLabel(
            self.strings["DROP_FILE_ENCRYPT"],
            objectName="DropText",
            alignment=Qt.AlignCenter
        )
        self.label.setFont(QFont("Arial", 12))
        self.layout.addWidget(self.label)
     
        self.count_label = QLabel("", alignment=Qt.AlignCenter)
        self.count_label.setFont(QFont("Arial", 10))
        self.count_label.setStyleSheet(f"""
            QLabel {{
                border: none;
                background: transparent;
                color: {self.colors["TEXT_SECONDARY"]};
                margin-top: 4px;
            }}
        """)
        self.count_label.hide()
        self.layout.addWidget(self.count_label)

       
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow_color = QColor(0, 0, 0, 50) if self.colors == LIGHT_THEME_COLORS else QColor(0, 0, 0, 80)
        shadow.setColor(shadow_color)
        shadow.setOffset(QPoint(0, 5))
        self.setGraphicsEffect(shadow)

    def _apply_style(self, style_override=""):
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {self.colors["BORDER"]};
                border-radius: 12px;
                background-color: {self.colors["CARD_BG"]};
                padding: 20px;
            }}
            QLabel#DropText {{
                border: none;
                background-color: transparent;
                color: {self.colors["TEXT_SECONDARY"]};
                font-weight: 500;
            }}
            {style_override}
        """)

    def reset_extra_labels(self):
        self.count_label.hide()
        self.count_label.setText("")

    def set_mode(self, mode, message=None, file_count=None):
        self.mode = mode
        style_override = ""
        new_text = ""
        text_color = self.colors["TEXT_SECONDARY"]

   
        self.reset_extra_labels()

        if mode == "file":
            if self.main_window.current_action_mode == "decrypt":
                new_text = self.strings["DROP_FILE_DECRYPT"]
            else:
                new_text = self.strings["DROP_FILE_ENCRYPT"]

        elif mode == "key":
            if self.main_window.current_action_mode == "encrypt":
                new_text = self.strings["DROP_KEY_PUBLIC"]
                count_key = "STR_FILE_COUNT_READY_ENCRYPT"
            else:
                new_text = self.strings["DROP_KEY_PRIVATE"]
                count_key = "STR_FILE_COUNT_READY_DECRYPT"

           
            if file_count is not None:
                self.count_label.setText(
                    self.strings.get(count_key, "%d file(s) ready") % file_count
                )
                self.count_label.show()
            else:
                self.count_label.hide()


        elif mode == "finished":
            accent = self.colors["SUCCESS_ACCENT"]
            bg = self.colors["SUCCESS_BG"]
            new_text = self.strings["DROP_FINISHED"] % message
            style_override = f"border: 2px solid {accent}; background-color: {bg};"
            text_color = accent

        elif mode == "error":
            accent = self.colors["DANGER"]
            bg = self.colors["DANGER_BG"]
            new_text = self.strings["DROP_ERROR"] % message
            style_override = f"border: 2px solid {accent}; background-color: {bg};"
            text_color = accent

        self._apply_style(style_override)
        self.label.setText(new_text)
        self.label.setStyleSheet(f"color: {text_color}; font-weight: 500;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        mime = event.mimeData()
        if mime.hasUrls():
            paths = [
                u.toLocalFile()
                for u in mime.urls()
                if u.isLocalFile() and os.path.exists(u.toLocalFile())
            ]
            if not paths:
                event.ignore()
                return

            if self.mode in ("finished", "error"):
                self.main_window._reset_state_ui(clear_keys=False)

            if self.mode == "file":
                self.files_dropped.emit(paths)
            elif self.mode == "key":
                self.keys_dropped.emit(paths)

            event.acceptProposedAction()
        else:
            event.ignore()




class AgeGUI(QMainWindow):
    SETTINGS_FILE = "settings.ini"

    STRINGS = {
        "TITLE": "Age Encrypt/Decrypt GUI v0.1.0",
        "MSGBOX_TITLE": "Age Notification",
        "STATUS_READY": "Ready. Recipient Keys: %s.",
        "STATUS_LOADED_KEYS": "Loaded %d keys.",
        "STATUS_ENCRYPT_MODE": "Encryption Ready",
        "STATUS_DECRYPT_MODE": "Decryption Ready",
        "STATUS_START_PROCESS": "Executing %s on %d files...",
        "STATUS_PROCESSING_FILE": "Processing file: %s",
        "STATUS_FINISHED_KEYS": "Finished. Keys Used: %d.",
        "STATUS_TERMINATED": "Operation terminated.",
        "STATUS_KEY_LOAD_FAIL": "Key load failed.",
        "BTN_CLEAR": "Clear",
        "BTN_CLEAR_KEYS": "Clear Keys", 
        "CONFIRM_CLEAR_KEYS": "Are you sure you want to clear ALL saved public recipient key paths?",
        "ERROR_MIXED_FILES": "Cannot mix .age and non-.age files.",
        "ERROR_INVALID_KEY_PATH": "Invalid key path or file not found.",
        "ERROR_AGE_WORKER": "Age command failed: %s",
        "ERROR_FILES_FAIL": "Failed! %d files failed.",
        "ERROR_DECRYPT_MULTI": "No valid .age files found.",
        "MODE_ENCRYPT_DISPLAY": "Encryption",
        "MODE_DECRYPT_DISPLAY": "Decryption",
        "DROP_FILE_ENCRYPT": "Drop Files or Folders for Encryption", 
        "DROP_FILE_DECRYPT": "Drop .age Files or Folders for Decryption", 
        "DROP_KEY_PUBLIC": "Drop Recipient Public Key(s)",
        "DROP_KEY_PRIVATE": "Drop Identity Private Key(s)",
        "DROP_FINISHED": "%s Complete!",
        "DROP_ERROR": "Error: %s",
        "ERROR_KEY_FORMAT_PUBLIC": "Invalid Age PUBLIC key format",
        "ERROR_KEY_FORMAT_PRIVATE": "Invalid Age PRIVATE key format",
        "ERROR_AGE_NOT_FOUND": "Error: Age executable not found. Please ensure 'age' is packaged or in system PATH.",
        "STR_FILE_COUNT_READY": "%d file(s) ready for encryption",
        "STR_FILE_COUNT_READY_DECRYPT": "%d file(s) ready for decryption",
   
   }

    def __init__(self):
        super().__init__()
        self.is_dark_mode = darkdetect.isDark()
        self.colors = DARK_THEME_COLORS if self.is_dark_mode else LIGHT_THEME_COLORS
        self.strings = self.STRINGS
        self.setWindowTitle(self.strings["TITLE"])
        self.setFixedSize(400, 320) 

        # State management variables
        self.keys = []                  # Temp list for Identity/Recipient keys for current operation
        self.recipients_keys = []       # Persistent list for Recipient Public Keys (Encrypt only)
        self.files_to_process = []
        self.current_action_mode = None 
        self._key_pending = False
        self.worker = None
        
        # 1. Get Age executable path
        self.age_exe_path = self._get_age_executable_path()
        if not self.age_exe_path:
             QMessageBox.critical(self, "Fatal Error", self.strings["ERROR_AGE_NOT_FOUND"])
             sys.exit(1)

        self.setStyleSheet(get_base_stylesheet(self.colors))
        self._set_qmessagebox_style()
        self._init_ui()
        self._load_key_settings()

    def _get_age_executable_path(self):
        import os, sys, shutil

        exe_name = "age.exe" if os.name == "nt" else "age"

        search_paths = []

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            search_paths.append(sys._MEIPASS)

        if getattr(sys, 'frozen', False):
            search_paths.append(os.path.dirname(sys.executable))
        else:
            search_paths.append(os.path.dirname(os.path.abspath(__file__)))

        for path in search_paths:
            candidate = os.path.join(path, exe_name)
            if os.path.exists(candidate):
                return candidate

        path_check = shutil.which(exe_name)
        if path_check:
            return path_check

        return None 

    def _set_qmessagebox_style(self):
        # Applies themed styling to QMessageBox
        text_color = self.colors["TEXT_PRIMARY"]
        bg_color = self.colors["CARD_BG"]
        btn_bg = self.colors["CARD_BG"]
        btn_text = self.colors["TEXT_PRIMARY"]
        style = f"""
            QMessageBox {{ background-color: {bg_color}; }}
            QMessageBox QLabel {{ color: {text_color}; }}
            QMessageBox QPushButton {{
                border-radius: 6px; font-weight: 500; padding: 6px 12px;
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {self.colors['BORDER']};
            }}
            QMessageBox QPushButton:hover {{ background-color: {self.colors['BORDER']}; }}
        """
        app = QApplication.instance()
        current_style = app.styleSheet()
        new_style = current_style.split("QMessageBox {")[0] + style
        app.setStyleSheet(new_style)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # Drop Target
        self.drop_target = SingleDropTarget(
            main_window=self, 
            colors=self.colors, 
            strings=self.STRINGS, 
            parent=central
        )
        self.drop_target.files_dropped.connect(self._on_files_dropped)
        self.drop_target.keys_dropped.connect(self._on_keys_dropped_in_key_mode)
        self.main_layout.addWidget(self.drop_target, 1)

        # Footer
        self.progress = QProgressBar(value=0)
        self.main_layout.addWidget(self.progress)

        footer_layout = QHBoxLayout()
        
        self.btn_clear_keys = QPushButton(self.strings["BTN_CLEAR_KEYS"], objectName="ClearKeysBtn")
        self.btn_clear_keys.clicked.connect(self._clear_keys_action)
        self.btn_clear_keys.setFixedSize(100, 32)
        footer_layout.addWidget(self.btn_clear_keys) 

        self.status_label = QLabel(self.strings["STATUS_READY"] % "0", objectName="StatusLabel", alignment=Qt.AlignVCenter)
        self.status_label.setFont(QFont("Arial", 10))
        footer_layout.addWidget(self.status_label, 1) 
        
        self.btn_clear = QPushButton(self.strings["BTN_CLEAR"], objectName="ClearBtn")
        self.btn_clear.clicked.connect(lambda: self._reset_state_ui(clear_keys=False))
        self.btn_clear.setFixedSize(90, 32)
        footer_layout.addWidget(self.btn_clear)

        self.main_layout.addLayout(footer_layout)
        
        self._update_ui_state()

    # Key Validation Function
    def _validate_key_file(self, file_path, key_type):
        """Validates key file content, ignoring # comments."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read all lines, filter out lines starting with # and empty lines
                content_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                
                if not content_lines:
                    return False
                
                first_line = content_lines[0]
                
                if key_type == 'public':
                    return first_line.startswith("age1")
                elif key_type == 'private':
                    return first_line.startswith("AGE-SECRET-KEY-")
                else:
                    return False
        except Exception:
            return False

    # State Management and Persistence
    def _update_ui_state(self, _=None):
        is_running = self.worker is not None and self.worker.isRunning()        
        self.btn_clear_keys.setDisabled(is_running)
        
    def _reset_state_ui(self, clear_keys=False):
        self.files_to_process = []
        self._key_pending = False
        self.current_action_mode = None
        self.keys = [] 
        self.progress.setValue(0)
        self.drop_target.setDisabled(False)
        self.btn_clear.setDisabled(False)
        self.drop_target.set_mode("file") 
        if clear_keys:
            self.recipients_keys = [] 
            self._save_key_settings([], False)
        
        key_status = str(len(self.recipients_keys))
        self.status_label.setText(self.strings["STATUS_READY"] % key_status)
        self._update_ui_state()

    def _clear_keys_action(self):
        if not self.recipients_keys:
            self.status_label.setText(self.strings["STATUS_READY"] % "0")
            return

        reply = QMessageBox.question(
            self, 
            self.strings["BTN_CLEAR_KEYS"], 
            self.strings["CONFIRM_CLEAR_KEYS"], 
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No 
        )

        if reply == QMessageBox.Yes:
            self._reset_state_ui(clear_keys=True)

    def _load_key_settings(self):
        settings = QSettings(self._get_settings_path(), QSettings.IniFormat)
        is_remembered = settings.value("Keys/RememberKeys", "false") == "true"
        self.recipients_keys = []
        if is_remembered:
            key_paths_str = settings.value("Keys/Paths", "")
            # Validate existence and public key format upon loading
            key_paths = [p for p in key_paths_str.split(';') if os.path.exists(p) and p and self._validate_key_file(p, 'public')]
            if key_paths:
                self.recipients_keys = key_paths 
                self.status_label.setText(self.strings["STATUS_LOADED_KEYS"] % len(self.recipients_keys))
            else:
                 self.status_label.setText(self.strings["STATUS_READY"] % "0")
                 # Clear remembered settings if loading failed
                 self._save_key_settings([], False)

    def _save_key_settings(self, keys_to_save: list, remember: bool):
        settings = QSettings(self._get_settings_path(), QSettings.IniFormat)
        settings.setValue("Keys/RememberKeys", "true" if remember else "false")
        if remember:
            settings.setValue("Keys/Paths", ";".join(keys_to_save))
        else:
            settings.setValue("Keys/Paths", "")
        settings.sync()
        
    def _get_settings_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), self.SETTINGS_FILE)
        else:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.SETTINGS_FILE)
            
    def _get_files_recursive(self, paths):
        # Recursively collects files from paths, ignoring hidden files/folders
        file_list = []
        for path in paths:
            if os.path.basename(path).startswith('.'):
                continue
            if os.path.isfile(path):
                file_list.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file_name in files:
                        if not file_name.startswith('.'):
                            file_list.append(os.path.join(root, file_name))
        return file_list

    # Drop Handlers
    def _on_files_dropped(self, paths):
        if self._key_pending: return

        # 1. Determine mode
        collected_files = self._get_files_recursive(paths)
        has_age_files = any(p.lower().endswith(".age") for p in collected_files)
        
        if not collected_files:
            self.drop_target.set_mode("error", self.strings["ERROR_DECRYPT_MULTI"])
            self.status_label.setText(self.strings["STATUS_TERMINATED"])
            return

        if has_age_files and not all(p.lower().endswith(".age") for p in collected_files):
            self.drop_target.set_mode("error", self.strings["ERROR_MIXED_FILES"])
            self.status_label.setText(self.strings["STATUS_TERMINATED"])
            return

        if has_age_files:
            self.files_to_process = collected_files
            self.current_action_mode = "decrypt"
        else:
            self.files_to_process = collected_files
            self.current_action_mode = "encrypt"

        # 2. Key Check and Start Process
        total_files = len(self.files_to_process)
        
        if self.current_action_mode == "decrypt":
            # Decryption: Require temporary Identity Keys (self.keys)
            if not self.keys:
                self._key_pending = True
                total_files = len(self.files_to_process)  
                self.drop_target.set_mode(
                    mode="key",
                    file_count=total_files  
                )
                self.status_label.setText(self.strings["STATUS_DECRYPT_MODE"])
            else:
                self.status_label.setText(self.strings['STATUS_START_PROCESS'] % ('Decryption', total_files))
                self._start_process()

        else: # Encrypt Mode
            # Encryption: Use persistent Recipient Keys (self.recipients_keys)
            if not self.recipients_keys: 
                self._key_pending = True
                self.drop_target.set_mode(
                    mode="key",
                    file_count=total_files
                )
                self.status_label.setText(self.strings["STATUS_ENCRYPT_MODE"])
            
            else:
                self.keys = list(self.recipients_keys) # Use persistent keys for worker
                self.status_label.setText(self.strings['STATUS_START_PROCESS'] % ('Encryption', total_files))
                self._start_process()

    def _on_keys_dropped_in_key_mode(self, paths):
        if not self._key_pending: return
        
        key_type = 'public' if self.current_action_mode == 'encrypt' else 'private'
        
        # 1. Validate all dropped keys
        valid_keys = []
        invalid_keys = []
        for p in paths:
            if os.path.exists(p) and os.path.isfile(p):
                if self._validate_key_file(p, key_type):
                    valid_keys.append(p)
                else:
                    invalid_keys.append(os.path.basename(p))

        if invalid_keys:
            # Show critical error and maintain pending state
            error_key_msg = self.strings["ERROR_KEY_FORMAT_PUBLIC"] if key_type == 'public' else self.strings["ERROR_KEY_FORMAT_PRIVATE"]
            QMessageBox.critical(
                self, 
                self.strings["MSGBOX_TITLE"], 
                f"{error_key_msg}\n\nInvalid files: {', '.join(invalid_keys)}"
            )
            self.drop_target.set_mode("key", self.drop_target.label.text()) 
            self.status_label.setText(self.strings["STATUS_KEY_LOAD_FAIL"])
            return

        if not valid_keys:
            self.drop_target.set_mode("error", self.strings["ERROR_INVALID_KEY_PATH"])
            self.status_label.setText(self.strings["STATUS_KEY_LOAD_FAIL"])
            self.drop_target.setDisabled(False)
            return

        # 2. Process valid keys
        self.keys = valid_keys
        self._key_pending = False
        total_files = len(self.files_to_process)

        if self.current_action_mode == "encrypt":
            # Save public keys to persistent list and settings
            self.recipients_keys = valid_keys 
            self._save_key_settings(self.recipients_keys, True)
            self.status_label.setText(self.strings['STATUS_START_PROCESS'] % ('Encryption', total_files))
        elif self.current_action_mode == "decrypt":
            # Keys are only stored temporarily in self.keys
            self.status_label.setText(self.strings['STATUS_START_PROCESS'] % ('Decryption', total_files))

        self._start_process()

    # Worker Thread Management
    def _start_process(self):
        self.drop_target.setDisabled(True)
        self.btn_clear.setDisabled(True)
        self.btn_clear_keys.setDisabled(True)
        self._update_ui_state()

        mode_text = 'Encryption' if self.current_action_mode == 'encrypt' else 'Decryption'
        
        self.progress.setRange(0, 0) # Indeterminate progress bar
        
        # Start Worker
        self.worker = AgeWorker(
            mode=self.current_action_mode, 
            files_to_process=self.files_to_process, 
            keys_to_use=self.keys,
            age_path=self.age_exe_path
        )
        self.worker.finished.connect(self._on_finished)
        self.worker.process_starting.connect(self._on_process_starting)

        def report_error(file_name, error_msg):
            # Detailed error reporting
            if "timeout (5 minutes limit)" in error_msg:
                user_msg = "Process timeout (5 minutes limit). Check if 'age' executable is functioning correctly or if the file is too large."
            else:
                 user_msg = self.strings["ERROR_AGE_WORKER"] % error_msg
                 
            QMessageBox.critical(self, self.strings["MSGBOX_TITLE"], f"File: {file_name}\n\n{user_msg}")
            
        self.worker.error.connect(report_error)
        self.worker.progress_update.connect(self._update_progress)
        self.worker.start()

    def _on_process_starting(self, file_name):
        self.status_label.setText(self.strings["STATUS_PROCESSING_FILE"] % file_name)

    def _update_progress(self, val):
        self.progress.setRange(0, 100)
        self.progress.setValue(int(val * 100))

    def _on_finished(self, success, total, needs_clear):
        self.progress.setValue(100)
        self.drop_target.setDisabled(False)
        self.btn_clear.setDisabled(False)
        self.btn_clear_keys.setDisabled(False)
        self._update_ui_state()

        if total == 0:
            self.drop_target.set_mode("error", self.strings["STATUS_TERMINATED"])
            self.status_label.setText(self.strings["STATUS_TERMINATED"])
            self._reset_state_ui(clear_keys=False) 
            
        elif success == total:
            if self.current_action_mode == 'encrypt':
                mode_text_display = self.strings["MODE_ENCRYPT_DISPLAY"]
                key_count = len(self.recipients_keys)
            else:
                mode_text_display = self.strings["MODE_DECRYPT_DISPLAY"]
                key_count = len(self.keys)

            self.drop_target.set_mode("finished", mode_text_display)
            self.status_label.setText(self.strings["STATUS_FINISHED_KEYS"] % key_count)
            # Clear temporary lists
            self.files_to_process = []
            self.keys = []
        else:
            error_count = total - success
            self.drop_target.set_mode("error", self.strings["ERROR_FILES_FAIL"] % error_count)
            self.status_label.setText(self.strings["STATUS_TERMINATED"])
            self._reset_state_ui(clear_keys=False) 

if __name__ == "__main__":
    if os.name == 'nt':
        # Disable Page Table Extension on Windows for stability
        os.environ["AGE_DISABLE_PTE"] = "1" 

    try:
        app = QApplication(sys.argv)
    except RuntimeError:
        app = QApplication.instance()

    font = QFont("Arial", 10)
    if sys.platform == "darwin": font = QFont("Helvetica", 10)
    app.setFont(font)

    window = AgeGUI()

    # Icon handling for packaged app
    icon_path = "icon.ico"
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        icon_path = os.path.join(base_path, "icon.ico")

    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))

    window.show()
    sys.exit(app.exec())