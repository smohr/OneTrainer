import os
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QCheckBox, QProgressBar,
    QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QApplication

import modules.util.ui.qt_components as qt_comps
from modules.util.ui.ui_utils import get_icon_path
from modules.util.ui.UIState import UIState
import traceback # For error printing

class GenerateCaptionsArgs:
    """A simple class to hold the arguments for this dialog."""
    def __init__(self, initial_path: str, initial_include_subdirs: bool):
        self.model: str = "Blip" # Default model
        self.path: str = initial_path
        self.initial_caption: str = ""
        self.prefix: str = ""
        self.postfix: str = ""
        self.mode: str = "Create if absent" # Default mode
        self.include_subdirectories: bool = initial_include_subdirs
        
        self.types = {
            "model": str, "path": str, "initial_caption": str, "prefix": str,
            "postfix": str, "mode": str, "include_subdirectories": bool
        }
        self.nullables = {k: False for k in self.types}


class GenerateCaptionsWindow(QDialog):
    def __init__(self, parent_caption_ui, initial_path: str, initial_include_subdirectories: bool, *args, **kwargs):
        super().__init__(parent_caption_ui, *args, **kwargs)

        self.parent_caption_ui = parent_caption_ui
        
        self.args = GenerateCaptionsArgs(initial_path or "", initial_include_subdirectories)
        self.ui_state = UIState(self.args, self)

        self.modes = ["Replace all captions", "Create if absent", "Add as new line"]
        self.models = ["Blip", "Blip2", "WD14 VIT v2"]

        self.setWindowTitle("Batch Generate Captions")
        self.setMinimumSize(380, 400) # Adjusted for content

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)

        grid = QGridLayout()
        main_layout.addLayout(grid)

        row = 0
        grid.addWidget(qt_comps.create_options_kv(self, self.ui_state, "model", list(zip(self.models, self.models)), "Model"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_file_dir_entry(self, self.ui_state, "path", "directory", "Folder", "Path to the folder with images"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "initial_caption", "Initial Caption"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "prefix", "Caption Prefix"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "postfix", "Caption Postfix"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_options_kv(self, self.ui_state, "mode", list(zip(self.modes, self.modes)), "Mode"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_switch(self, self.ui_state, "include_subdirectories", "Include subfolders"), row, 0, 1, 2); row+=1

        self.progress_label = qt_comps.create_label(self, "Progress: 0/0")
        grid.addWidget(self.progress_label, row, 0)
        self.progressbar = QProgressBar(self)
        self.progressbar.setValue(0)
        self.progressbar.setTextVisible(False)
        grid.addWidget(self.progressbar, row, 1); row+=1
        
        self.create_captions_button = qt_comps.create_button(self, "Create Captions", self.create_captions_action)
        grid.addWidget(self.create_captions_button, row, 0, 1, 2)
        row+=1

        main_layout.addStretch(1)

        QTimer.singleShot(100, self._late_init)
        self.setModal(True)

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        self.activateWindow()
        self.raise_()
        if self.create_captions_button: self.create_captions_button.setFocus()

    def set_progress(self, current_value: int, max_value: int):
        if max_value > 0:
            progress_percent = int((current_value / max_value) * 100)
            self.progressbar.setValue(progress_percent)
        else:
            self.progressbar.setValue(0)
        self.progress_label.setText(f"Progress: {current_value}/{max_value}")
        QApplication.processEvents()

    def create_captions_action(self):
        if hasattr(self.parent_caption_ui, 'load_captioning_model') and \
           hasattr(self.parent_caption_ui, 'captioning_model') and \
           hasattr(self.parent_caption_ui.captioning_model, 'caption_folder'):

            self.parent_caption_ui.load_captioning_model(self.args.model)

            if self.parent_caption_ui.captioning_model is None:
                print("Error: Captioning model not loaded in parent (CaptionUI). Cannot generate captions.")
                return

            mode_map = {
                "Replace all captions": "replace", "Create if absent": "fill", "Add as new line": "add",
            }
            mapped_mode = mode_map.get(self.args.mode, "fill")

            self.create_captions_button.setEnabled(False)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.parent_caption_ui.captioning_model.caption_folder(
                    sample_dir=self.args.path,
                    initial_caption=self.args.initial_caption,
                    caption_prefix=self.args.prefix,
                    caption_postfix=self.args.postfix,
                    mode=mapped_mode,
                    progress_callback=self.set_progress,
                    include_subdirectories=self.args.include_subdirectories,
                )
                if hasattr(self.parent_caption_ui, 'switch_image'):
                    self.parent_caption_ui.switch_image(self.parent_caption_ui.current_image_index)
            except Exception as e:
                print(f"Error during caption generation: {e}")
                traceback.print_exc()
            finally:
                QApplication.restoreOverrideCursor()
                self.create_captions_button.setEnabled(True)
                self.set_progress(0,1)
        else:
            print("Error: Parent CaptionUI does not have required captioning methods or model.")

    def done(self, result: int):
        QApplication.restoreOverrideCursor()
        super().done(result)
