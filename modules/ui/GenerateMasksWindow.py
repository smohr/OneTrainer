import os
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QCheckBox, QProgressBar,
    QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

import modules.util.ui.qt_components as qt_comps
from modules.util.ui.ui_utils import get_icon_path
from modules.util.ui.UIState import UIState

# Keep non-UI imports
# from modules.module.Blip2Model import Blip2Model etc. (if this dialog directly loads models)
# For now, assuming model loading is handled by the parent (CaptionUI) as per original.

class GenerateMasksArgs:
    """A simple class to hold the arguments for this dialog."""
    def __init__(self, initial_path: str, initial_include_subdirs: bool):
        self.model: str = "ClipSeg" # Default model
        self.path: str = initial_path
        self.prompt: str = ""
        self.mode: str = "Create if absent" # Default mode
        self.threshold: float = 0.3
        self.smooth: int = 5
        self.expand: int = 10
        self.alpha: float = 1.0
        self.include_subdirectories: bool = initial_include_subdirs
        
        # For UIState type/nullable tracking, mirror BaseConfig structure if complex
        self.types = {
            "model": str, "path": str, "prompt": str, "mode": str,
            "threshold": float, "smooth": int, "expand": int, "alpha": float,
            "include_subdirectories": bool
        }
        self.nullables = {k: False for k in self.types} # Assuming no fields are nullable by default here


class GenerateMasksWindow(QDialog):
    def __init__(self, parent_caption_ui, initial_path: str, initial_include_subdirectories: bool, *args, **kwargs):
        super().__init__(parent_caption_ui, *args, **kwargs) # parent_caption_ui is QWidget

        self.parent_caption_ui = parent_caption_ui # Store reference to CaptionUI
        
        self.args = GenerateMasksArgs(initial_path or "", initial_include_subdirectories)
        self.ui_state = UIState(self.args, self) # self.args is the target_object

        self.modes = ["Replace all masks", "Create if absent", "Add to existing", "Subtract from existing", "Blend with existing"]
        self.models = ["ClipSeg", "Rembg", "Rembg-Human", "Hex Color"]

        self.setWindowTitle("Batch Generate Masks")
        self.setMinimumSize(380, 450) # Adjusted for potentially different widget sizes

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)

        grid = QGridLayout()
        main_layout.addLayout(grid) # Add grid to main layout

        row = 0
        grid.addWidget(qt_comps.create_options_kv(self, self.ui_state, "model", list(zip(self.models, self.models)), "Model"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_file_dir_entry(self, self.ui_state, "path", "directory", "Folder", "Path to the folder with images"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "prompt", "Prompt"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_options_kv(self, self.ui_state, "mode", list(zip(self.modes, self.modes)), "Mode"), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "threshold", "Threshold", "0.0 - 1.0", default_value=0.3, value_type=float), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "smooth", "Smooth", "e.g., 5", default_value=5, value_type=int), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "expand", "Expand", "e.g., 10", default_value=10, value_type=int), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_entry(self, self.ui_state, "alpha", "Alpha", "e.g., 1.0", default_value=1.0, value_type=float), row, 0, 1, 2); row+=1
        grid.addWidget(qt_comps.create_switch(self, self.ui_state, "include_subdirectories", "Include subfolders"), row, 0, 1, 2); row+=1

        self.progress_label = qt_comps.create_label(self, "Progress: 0/0")
        grid.addWidget(self.progress_label, row, 0)
        self.progressbar = QProgressBar(self)
        self.progressbar.setValue(0)
        self.progressbar.setTextVisible(False)
        grid.addWidget(self.progressbar, row, 1); row+=1
        
        self.create_masks_button = qt_comps.create_button(self, "Create Masks", self.create_masks_action)
        grid.addWidget(self.create_masks_button, row, 0, 1, 2)
        row+=1

        main_layout.addStretch(1) # Push content to top

        QTimer.singleShot(100, self._late_init)
        self.setModal(True) # Make it a modal dialog explicitly

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        self.activateWindow()
        self.raise_()
        if self.create_masks_button: self.create_masks_button.setFocus()


    def set_progress(self, current_value: int, max_value: int):
        if max_value > 0:
            progress_percent = int((current_value / max_value) * 100)
            self.progressbar.setValue(progress_percent)
        else:
            self.progressbar.setValue(0)
        self.progress_label.setText(f"Progress: {current_value}/{max_value}")
        QApplication.processEvents() # Allow UI to update, but use with caution

    def create_masks_action(self):
        # Ensure parent_caption_ui has the method load_masking_model
        if hasattr(self.parent_caption_ui, 'load_masking_model') and \
           hasattr(self.parent_caption_ui, 'masking_model') and \
           hasattr(self.parent_caption_ui.masking_model, 'mask_folder'):

            self.parent_caption_ui.load_masking_model(self.args.model)
            
            if self.parent_caption_ui.masking_model is None:
                print("Error: Masking model not loaded in parent (CaptionUI). Cannot generate masks.")
                # Optionally show a QMessageBox to the user
                return

            mode_map = {
                "Replace all masks": "replace", "Create if absent": "fill",
                "Add to existing": "add", "Subtract from existing": "subtract",
                "Blend with existing": "blend",
            }
            mapped_mode = mode_map.get(self.args.mode, "fill") # Default to "fill"

            # Disable button during processing
            self.create_masks_button.setEnabled(False)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            try:
                # Run in a separate thread if mask_folder is long-running
                # For now, direct call for simplicity of refactor
                self.parent_caption_ui.masking_model.mask_folder(
                    sample_dir=self.args.path,
                    prompts=[self.args.prompt],
                    mode=mapped_mode,
                    alpha=self.args.alpha,
                    threshold=self.args.threshold,
                    smooth_pixels=self.args.smooth,
                    expand_pixels=self.args.expand,
                    progress_callback=self.set_progress,
                    include_subdirectories=self.args.include_subdirectories,
                )
                # Assuming parent_caption_ui has a method to refresh its current image/mask
                if hasattr(self.parent_caption_ui, 'switch_image'): # Or a more specific refresh_current_mask
                    self.parent_caption_ui.switch_image(self.parent_caption_ui.current_image_index) 
            except Exception as e:
                print(f"Error during mask generation: {e}")
                traceback.print_exc()
                # Show QMessageBox error
            finally:
                QApplication.restoreOverrideCursor()
                self.create_masks_button.setEnabled(True)
                self.set_progress(0,1) # Reset progress
        else:
            print("Error: Parent CaptionUI does not have required masking methods or model.")
            # Show QMessageBox error to user

    def done(self, result: int): # Override done to ensure cursor is restored
        QApplication.restoreOverrideCursor()
        super().done(result)
