from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QScrollArea, QLabel, QLineEdit, 
    QComboBox, QPushButton, QHBoxLayout, QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt
import modules.util.ui.qt_components as qt_comps # Import new shared components

from modules.util.config.TrainConfig import TrainConfig
from modules.util.enum.ConfigPart import ConfigPart
from modules.util.enum.DataType import DataType
from modules.util.enum.ModelFormat import ModelFormat
from modules.util.enum.TrainingMethod import TrainingMethod
from modules.util.ui.UIState import UIState
# We will re-implement necessary component creators temporarily
# from modules.util.ui import components # Removed
# import customtkinter as ctk # Removed


class ModelTab(QWidget):
    def __init__(self, train_config: TrainConfig, ui_state: UIState, parent: QWidget = None):
        super().__init__(parent)

        self.train_config = train_config
        self.ui_state = ui_state

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.main_layout.addWidget(self.scroll_area)

        self.scroll_area_content_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_area_content_widget)
        
        self.grid_layout = QGridLayout(self.scroll_area_content_widget)
        # self.scroll_area_content_widget.setLayout(self.grid_layout) # Set layout on the widget

        self.refresh_ui()

    # --- Temporary Helper Methods have been removed. Using qt_components now. ---

    def refresh_ui(self):
        # Clear existing content in the grid layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Reset column stretches, may need adjustment based on content
        for i in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnStretch(i, 0)

        self.grid_layout.setColumnStretch(1, 10) # As per ctk code (column 1, weight 10)
        self.grid_layout.setColumnMinimumWidth(2, 50) # As per ctk code (column 2, minsize 50)
        self.grid_layout.setColumnStretch(4, 1)  # As per ctk code (column 4, weight 1)
        # Column 0 and 3 had weight 0 (default for stretch factor)


        # Determine which UI setup to call based on model_type
        # This logic remains the same
        if self.train_config.model_type.is_stable_diffusion():
            self.__setup_stable_diffusion_ui()
        elif self.train_config.model_type.is_stable_diffusion_3():
            self.__setup_stable_diffusion_3_ui()
        elif self.train_config.model_type.is_stable_diffusion_xl():
            self.__setup_stable_diffusion_xl_ui()
        elif self.train_config.model_type.is_wuerstchen():
            self.__setup_wuerstchen_ui()
        elif self.train_config.model_type.is_pixart():
            self.__setup_pixart_alpha_ui()
        elif self.train_config.model_type.is_flux():
            self.__setup_flux_ui()
        elif self.train_config.model_type.is_sana():
            self.__setup_sana_ui()
        elif self.train_config.model_type.is_hunyuan_video():
            self.__setup_hunyuan_video_ui()
        elif self.train_config.model_type.is_hi_dream():
            self.__setup_hi_dream_ui()
        
        # Add a stretch at the bottom to push content up
        self.grid_layout.setRowStretch(self.grid_layout.rowCount(), 1)


    def __create_dtype_options(self, include_none:bool=True) -> list[tuple[str, DataType]]:
        # This method remains largely the same as it's data generation
        options = [
            ("float32", DataType.FLOAT_32),
            ("bfloat16", DataType.BFLOAT_16),
            ("float16", DataType.FLOAT_16),
            ("float8", DataType.FLOAT_8),
            ("nfloat4", DataType.NFLOAT_4),
        ]
        if include_none:
            options.insert(0, ("<Default>", DataType.NONE)) # Changed "" to "<Default>" for clarity
        return options

    def __create_base_dtype_components(self, row: int) -> int:
        self.grid_layout.addWidget(qt_comps.create_entry(self.scroll_area_content_widget, self.ui_state, "secrets.huggingface_token", "Hugging Face Token", "Enter your Hugging Face access token..."), row, 0, 1, 2)
        row += 1
        
        # Base Model (File Entry) - Spans 2 columns for label+widget, placed in grid column 0
        # path_modifier logic is complex for a generic helper. UIState or caller should handle if needed.
        self.grid_layout.addWidget(qt_comps.create_file_dir_entry(self.scroll_area_content_widget, self.ui_state, "base_model_name", "file_open", "Base Model", "Filename, directory or Hugging Face repository...", file_filter="Model Files (*.json *.safetensors *.ckpt);;All Files (*)"), row, 0, 1, 2)
        
        # Weight Data Type (Options KV) - Spans 2 columns for label+widget, placed in grid column 3
        self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "weight_dtype", self.__create_dtype_options(False), "Weight Data Type", "The base model weight data type..."), row, 3, 1, 2)
        row += 1
        return row

    def __create_base_components(
            self, row: int, has_unet: bool = False, has_prior: bool = False, allow_override_prior: bool = False,
            allow_override_text_encoder_4: bool = False, has_text_encoder: bool = False, has_text_encoder_1: bool = False,
            has_text_encoder_2: bool = False, has_text_encoder_3: bool = False, has_text_encoder_4: bool = False,
            has_vae: bool = False,
    ) -> int:
        # Each call to qt_comps helper creates a container with label+widget, so they take 2 grid columns.
        # We place them in column 0 (for left-side items) or column 3 (for right-side items).
        if has_unet:
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "unet.weight_dtype", self.__create_dtype_options(), "Override UNet Data Type", "Overrides the unet weight data type"), row, 3, 1, 2)
            row += 1
        if has_prior:
            if allow_override_prior:
                self.grid_layout.addWidget(qt_comps.create_file_dir_entry(self.scroll_area_content_widget, self.ui_state, "prior.model_name", "file_open", "Prior Model", "Filename, directory or Hugging Face repository...", file_filter="Model Files (*.json *.safetensors *.ckpt);;All Files (*)"), row, 0, 1, 2)
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "prior.weight_dtype", self.__create_dtype_options(), "Override Prior Data Type", "Overrides the prior weight data type"), row, 3, 1, 2)
            row += 1
        if has_text_encoder: # SD1.5, Wuerstchen, PixArt, Sana
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "text_encoder.weight_dtype", self.__create_dtype_options(), "Override Text Encoder Data Type", "Overrides the text encoder weight data type"), row, 3, 1, 2)
            row += 1
        if has_text_encoder_1: # SDXL, SD3, Flux, Hunyuan, HiDream
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "text_encoder.weight_dtype", self.__create_dtype_options(), "Override Text Encoder 1 Data Type", "Overrides text encoder 1 data type"), row, 3, 1, 2)
            row += 1
        if has_text_encoder_2: # SDXL, SD3, Flux, Hunyuan, HiDream
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "text_encoder_2.weight_dtype", self.__create_dtype_options(), "Override Text Encoder 2 Data Type", "Overrides text encoder 2 data type"), row, 3, 1, 2)
            row += 1
        if has_text_encoder_3: # SD3, HiDream
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "text_encoder_3.weight_dtype", self.__create_dtype_options(), "Override Text Encoder 3 Data Type", "Overrides text encoder 3 data type"), row, 3, 1, 2)
            row += 1
        if has_text_encoder_4: # HiDream
            if allow_override_text_encoder_4:
                 self.grid_layout.addWidget(qt_comps.create_file_dir_entry(self.scroll_area_content_widget, self.ui_state, "text_encoder_4.model_name", "file_open", "Text Encoder 4 Override", "Filename, directory or Hugging Face repository...", file_filter="Model Files (*.json *.safetensors *.ckpt);;All Files (*)"), row, 0, 1, 2)
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "text_encoder_4.weight_dtype", self.__create_dtype_options(), "Override Text Encoder 4 Data Type", "Overrides text encoder 4 data type"), row, 3, 1, 2)
            row += 1
        if has_vae:
            self.grid_layout.addWidget(qt_comps.create_file_dir_entry(self.scroll_area_content_widget, self.ui_state, "vae.model_name", "file_open", "VAE Override", "Directory or Hugging Face repository of a VAE model...", file_filter="Model Files (*.json *.safetensors *.ckpt);;All Files (*)"), row, 0, 1, 2)
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "vae.weight_dtype", self.__create_dtype_options(), "Override VAE Data Type", "Overrides the vae weight data type"), row, 3, 1, 2)
            row += 1
        return row

    def __create_effnet_encoder_components(self, row: int) -> int:
        self.grid_layout.addWidget(qt_comps.create_file_dir_entry(self.scroll_area_content_widget, self.ui_state, "effnet_encoder.model_name", "file_open", "Effnet Encoder Model", "Filename, directory or Hugging Face repository...", file_filter="Model Files (*.json *.safetensors *.ckpt);;All Files (*)"), row, 0, 1, 2)
        self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "effnet_encoder.weight_dtype", self.__create_dtype_options(), "Override Effnet Encoder Data Type", "Overrides the effnet encoder weight data type"), row, 3, 1, 2)
        row += 1
        return row

    def __create_decoder_components(self, row: int, has_text_encoder: bool) -> int:
        self.grid_layout.addWidget(qt_comps.create_file_dir_entry(self.scroll_area_content_widget, self.ui_state, "decoder.model_name", "file_open", "Decoder Model", "Filename, directory or Hugging Face repository...", file_filter="Model Files (*.json *.safetensors *.ckpt);;All Files (*)"), row, 0, 1, 2)
        self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "decoder.weight_dtype", self.__create_dtype_options(), "Override Decoder Data Type", "Overrides the decoder weight data type"), row, 3, 1, 2)
        row += 1
        if has_text_encoder:
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "decoder_text_encoder.weight_dtype", self.__create_dtype_options(), "Override Decoder Text Encoder Data Type", "Overrides the decoder text encoder weight data type"), row, 3, 1, 2) # Should this be on a new row or different column? Assuming new row for now if it's a separate field.
            row += 1
        self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "decoder_vqgan.weight_dtype", self.__create_dtype_options(), "Override Decoder VQGAN Data Type", "Overrides the decoder vqgan weight data type"), row, 3, 1, 2) # Same row as above if space, or new. Assuming new.
        row += 1
        return row

    def __create_output_components(self, row: int, allow_safetensors: bool = False, allow_diffusers: bool = False, allow_legacy_safetensors: bool = False) -> int:
        self.grid_layout.addWidget(qt_comps.create_file_dir_entry(self.scroll_area_content_widget, self.ui_state, "output_model_destination", "file_save", "Model Output Destination", "Filename or directory where the output model is saved", file_filter="Model Files (*.safetensors *.ckpt);;All Files (*)"), row, 0, 1, 2)
        
        output_dtype_items = [("float16", DataType.FLOAT_16), ("float32", DataType.FLOAT_32), ("bfloat16", DataType.BFLOAT_16), ("float8", DataType.FLOAT_8), ("nfloat4", DataType.NFLOAT_4)]
        self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "output_dtype", output_dtype_items, "Output Data Type", "Precision to use when saving the output model"), row, 3, 1, 2)
        row += 1

        formats = []
        if allow_safetensors: formats.append(("Safetensors", ModelFormat.SAFETENSORS))
        if allow_diffusers: formats.append(("Diffusers", ModelFormat.DIFFUSERS))
        
        if formats: # Only add if there are formats to choose from
            self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "output_model_format", formats, "Output Format", "Format to use when saving the output model"), row, 0, 1, 2)
        
        include_config_items = [("None", ConfigPart.NONE), ("Settings", ConfigPart.SETTINGS), ("All", ConfigPart.ALL)]
        self.grid_layout.addWidget(qt_comps.create_options_kv(self.scroll_area_content_widget, self.ui_state, "include_train_config", include_config_items, "Include Config", "Include the training configuration in the final model..."), row, 3, 1, 2)
        row += 1
        return row

    # --- UI Setup methods based on model type ---
    # These methods call the component creation methods above.
    # Their internal logic (which components to create based on conditions) remains the same.
    def __setup_stable_diffusion_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_unet=True, has_text_encoder=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=True, allow_diffusers=self.train_config.training_method in [TrainingMethod.FINE_TUNE, TrainingMethod.FINE_TUNE_VAE], allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    def __setup_stable_diffusion_3_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_prior=True, has_text_encoder_1=True, has_text_encoder_2=True, has_text_encoder_3=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=True, allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    def __setup_flux_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_prior=True, allow_override_prior=True, has_text_encoder_1=True, has_text_encoder_2=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=True, allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    def __setup_stable_diffusion_xl_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_unet=True, has_text_encoder_1=True, has_text_encoder_2=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=True, allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    def __setup_wuerstchen_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_prior=True, allow_override_prior=self.train_config.model_type.is_stable_cascade(), has_text_encoder=True)
        row = self.__create_effnet_encoder_components(row)
        row = self.__create_decoder_components(row, self.train_config.model_type.is_wuerstchen_v2())
        row = self.__create_output_components(row, allow_safetensors=self.train_config.training_method != TrainingMethod.FINE_TUNE or self.train_config.model_type.is_stable_cascade(), allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    def __setup_pixart_alpha_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_prior=True, has_text_encoder=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=True, allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    def __setup_sana_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_prior=True, has_text_encoder=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=self.train_config.training_method != TrainingMethod.FINE_TUNE, allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)
    
    def __setup_hunyuan_video_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_prior=True, has_text_encoder_1=True, has_text_encoder_2=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=True, allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    def __setup_hi_dream_ui(self):
        row = 0
        row = self.__create_base_dtype_components(row)
        row = self.__create_base_components(row, has_prior=True, has_text_encoder_1=True, has_text_encoder_2=True, has_text_encoder_3=True, has_text_encoder_4=True, allow_override_text_encoder_4=True, has_vae=True)
        row = self.__create_output_components(row, allow_safetensors=True, allow_diffusers=self.train_config.training_method == TrainingMethod.FINE_TUNE, allow_legacy_safetensors=self.train_config.training_method == TrainingMethod.LORA)

    # Public methods that TrainUI might call
    def refresh_ui_for_model_type(self, model_type): # model_type is already in self.train_config
        self.refresh_ui()

    def refresh_ui_for_training_method(self, training_method): # training_method is already in self.train_config
        self.refresh_ui()
