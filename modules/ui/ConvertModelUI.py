import traceback
from pathlib import Path
from uuid import uuid4
from typing import Callable # For type hinting

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QComboBox, QPushButton, QWidget,
    QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

from modules.util import create
from modules.util.args.ConvertModelArgs import ConvertModelArgs
from modules.util.enum.DataType import DataType
from modules.util.enum.ModelFormat import ModelFormat
from modules.util.enum.ModelType import ModelType
from modules.util.enum.TrainingMethod import TrainingMethod
from modules.util.ModelNames import EmbeddingName, ModelNames
from modules.util.torch_util import torch_gc
# from modules.util.ui import components # Removed
from modules.util.ui.ui_utils import get_icon_path # For consistency
from modules.util.ui.UIState import UIState
# import customtkinter as ctk # Removed

class ConvertModelUI(QDialog):
    def __init__(self, parent_widget: QWidget, *args, **kwargs): # parent_widget is the new name
        super().__init__(parent_widget, *args, **kwargs)
        # self.parent = parent_widget # Already stored by QDialog

        self.convert_model_args = ConvertModelArgs.default_values()
        # UIState parent is self (QDialog).
        self.ui_state = UIState(self, self.convert_model_args) 
        self.convert_button: QPushButton | None = None

        self.setWindowTitle("Convert Models")
        self.setMinimumSize(550, 350) # Replaces geometry & resizable

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)

        # self.frame in original was the main container. Here, QDialog is the main container.
        # We'll create a content_widget for the grid layout.
        content_widget = QWidget()
        main_layout.addWidget(content_widget)
        
        self.grid_layout = QGridLayout(content_widget)
        self.grid_layout.setColumnStretch(1, 1) # Allow second column to expand

        self._setup_main_ui_elements(self.grid_layout) # Pass the grid layout

        QTimer.singleShot(100, self._late_init)

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        self.activateWindow()
        self.raise_()
        if self.convert_button: self.convert_button.setFocus()


    # --- Temporary Helper Methods ---
    def _create_label(self, text: str, tooltip: str = None) -> QLabel:
        lbl = QLabel(text)
        if tooltip: lbl.setToolTip(tooltip)
        return lbl

    def _create_options_kv(self, ui_state_key: str, items: list[tuple[str, any]], tooltip: str = None, command: Callable = None) -> QComboBox:
        combo = QComboBox()
        if tooltip: combo.setToolTip(tooltip)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        current_val = self.ui_state.get_var(ui_state_key)
        selected_idx = 0
        for idx, (text, data) in enumerate(items):
            combo.addItem(text, userData=data)
            if data == current_val: selected_idx = idx
        if combo.count() > 0: combo.setCurrentIndex(selected_idx)

        def on_change(index):
            data = combo.itemData(index)
            self.ui_state.set_var(ui_state_key, data)
            if command: command(data) # Pass data to command
        combo.currentIndexChanged.connect(on_change)
        return combo

    def _create_file_entry(self, ui_state_key: str, tooltip: str = None, path_modifier: Callable[[str], str] = None, is_output:bool = False, file_filter: str = "All Files (*)") -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(5)

        line_edit = QLineEdit()
        if tooltip: line_edit.setToolTip(tooltip)
        line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        current_value = self.ui_state.get_var(ui_state_key, "")
        line_edit.setText(str(current_value))

        def update_state():
            text = line_edit.text()
            modified_text = path_modifier(text) if path_modifier else text
            self.ui_state.set_var(ui_state_key, modified_text)
        line_edit.editingFinished.connect(update_state)

        browse_button = QPushButton("Browse")
        def open_dialog():
            initial_path = line_edit.text()
            path = ""
            if is_output:
                path, _ = QFileDialog.getSaveFileName(self, "Select Output Location", initial_path, file_filter)
            else:
                path, _ = QFileDialog.getOpenFileName(self, "Select File or Directory", initial_path, file_filter) # Can select dirs if filter allows or use getExistingDirectory
            if path:
                line_edit.setText(path)
                update_state() # Ensure state is updated after path is set
        browse_button.clicked.connect(open_dialog)

        layout.addWidget(line_edit)
        layout.addWidget(browse_button)
        return widget
        
    def _create_button(self, text:str, command:callable, tooltip:str=None) -> QPushButton:
        btn = QPushButton(text)
        if command: btn.clicked.connect(command)
        if tooltip: btn.setToolTip(tooltip)
        return btn
    # --- End Helper Methods ---

    def _setup_main_ui_elements(self, layout: QGridLayout): # Changed master to layout
        row = 0
        # Model Type
        layout.addWidget(self._create_label("Model Type", "Type of the model"), row, 0)
        model_type_values = [
            ("Stable Diffusion 1.5", ModelType.STABLE_DIFFUSION_15), ("SD 1.5 Inpainting", ModelType.STABLE_DIFFUSION_15_INPAINTING),
            ("Stable Diffusion 2.0", ModelType.STABLE_DIFFUSION_20), ("SD 2.0 Inpainting", ModelType.STABLE_DIFFUSION_20_INPAINTING),
            ("Stable Diffusion 2.1", ModelType.STABLE_DIFFUSION_21),
            ("Stable Diffusion 3", ModelType.STABLE_DIFFUSION_3), ("Stable Diffusion 3.5", ModelType.STABLE_DIFFUSION_35),
            ("SD XL 1.0 Base", ModelType.STABLE_DIFFUSION_XL_10_BASE), ("SD XL 1.0 Inpainting", ModelType.STABLE_DIFFUSION_XL_10_BASE_INPAINTING),
            ("Wuerstchen v2", ModelType.WUERSTCHEN_2), ("Stable Cascade", ModelType.STABLE_CASCADE_1),
            ("PixArt Alpha", ModelType.PIXART_ALPHA), ("PixArt Sigma", ModelType.PIXART_SIGMA),
            ("Flux Dev", ModelType.FLUX_DEV_1), ("Flux Fill Dev", ModelType.FLUX_FILL_DEV_1),
            ("Hunyuan Video", ModelType.HUNYUAN_VIDEO),
        ]
        layout.addWidget(self._create_options_kv("model_type", model_type_values), row, 1); row+=1

        # Training Method
        layout.addWidget(self._create_label("Training Method", "The type of model to convert"), row, 0)
        training_method_values = [
            ("Base Model", TrainingMethod.FINE_TUNE), ("LoRA", TrainingMethod.LORA), ("Embedding", TrainingMethod.EMBEDDING),
        ]
        layout.addWidget(self._create_options_kv("training_method", training_method_values), row, 1); row+=1

        # Input Name
        layout.addWidget(self._create_label("Input name", "Filename, directory or Hugging Face repository..."), row, 0)
        layout.addWidget(self._create_file_entry("input_name", path_modifier=lambda x: Path(x).parent.absolute() if x.endswith(".json") else x), row, 1); row+=1

        # Output Data Type
        layout.addWidget(self._create_label("Output Data Type", "Precision for saving output model"), row, 0)
        output_dtype_values = [
            ("float32", DataType.FLOAT_32), ("float16", DataType.FLOAT_16), ("bfloat16", DataType.BFLOAT_16),
        ]
        layout.addWidget(self._create_options_kv("output_dtype", output_dtype_values), row, 1); row+=1

        # Output Format
        layout.addWidget(self._create_label("Output Format", "Format for saving output model"), row, 0)
        output_format_values = [
            ("Safetensors", ModelFormat.SAFETENSORS), ("Diffusers", ModelFormat.DIFFUSERS),
        ]
        layout.addWidget(self._create_options_kv("output_model_format", output_format_values), row, 1); row+=1

        # Output Model Destination
        layout.addWidget(self._create_label("Model Output Destination", "Filename or directory for output model"), row, 0)
        layout.addWidget(self._create_file_entry("output_model_destination", is_output=True), row, 1); row+=1
        
        self.convert_button = self._create_button("Convert", self.convert_model)
        layout.addWidget(self.convert_button, row, 1, alignment=Qt.AlignmentFlag.AlignRight) # Align button to right
        row+=1
        
        layout.setRowStretch(row, 1) # Push content to top

    def convert_model(self):
        if not self.convert_button: return
        try:
            self.convert_button.setEnabled(False)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor) # Indicate busy

            # Create instances (assuming these are non-UI and compatible)
            model_loader = create.create_model_loader(
                model_type=self.convert_model_args.model_type,
                training_method=self.convert_model_args.training_method
            )
            model_saver = create.create_model_saver(
                model_type=self.convert_model_args.model_type,
                training_method=self.convert_model_args.training_method
            )

            print("Loading model " + self.convert_model_args.input_name)
            model_names_instance = ModelNames( # Prepare ModelNames based on method
                base_model=self.convert_model_args.input_name if self.convert_model_args.training_method == TrainingMethod.FINE_TUNE else None,
                lora=self.convert_model_args.input_name if self.convert_model_args.training_method == TrainingMethod.LORA else None,
                embedding=EmbeddingName(str(uuid4()), self.convert_model_args.input_name) if self.convert_model_args.training_method == TrainingMethod.EMBEDDING else None,
            )
            
            model = model_loader.load(
                model_type=self.convert_model_args.model_type,
                model_names=model_names_instance,
                weight_dtypes=self.convert_model_args.weight_dtypes(), # This method on args needs to be correct
            )

            if model is None: # Check if model loading failed
                 raise Exception("Model loading returned None for: " + self.convert_model_args.input_name)


            print("Saving model " + self.convert_model_args.output_model_destination)
            model_saver.save(
                model=model,
                model_type=self.convert_model_args.model_type,
                output_model_format=self.convert_model_args.output_model_format,
                output_model_destination=self.convert_model_args.output_model_destination,
                dtype=self.convert_model_args.output_dtype.torch_dtype(), # Ensure this returns correct torch.dtype
            )
            print("Model converted successfully.")
            QMessageBox.information(self, "Success", "Model converted successfully.")

        except Exception as e:
            print(traceback.format_exc())
            QMessageBox.critical(self, "Conversion Error", f"An error occurred: {e}")
        finally:
            torch_gc()
            self.convert_button.setEnabled(True)
            QApplication.restoreOverrideCursor() # Clear busy cursor

    def done(self, result: int): # Override done to ensure torch_gc on close
        torch_gc()
        super().done(result)
