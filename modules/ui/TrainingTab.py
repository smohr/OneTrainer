from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QLabel,
    QLineEdit, QComboBox, QPushButton, QFrame, QSizePolicy, QCheckBox
)
from PySide6.QtCore import Qt
import modules.util.ui.qt_components as qt_comps # Import new shared components

# from modules.ui.OffloadingWindow import OffloadingWindow # TODO: Refactor to QDialog
from modules.ui.OptimizerParamsWindow import OptimizerParamsWindow # TODO: Refactor to QDialog
from modules.ui.SchedulerParamsWindow import SchedulerParamsWindow # Import refactored dialog
# from modules.ui.TimestepDistributionWindow import TimestepDistributionWindow # TODO: Refactor to QDialog

from modules.util.config.TrainConfig import TrainConfig
from modules.util.enum.DataType import DataType
from modules.util.enum.EMAMode import EMAMode
from modules.util.enum.GradientCheckpointingMethod import GradientCheckpointingMethod
from modules.util.enum.LearningRateScaler import LearningRateScaler
from modules.util.enum.LearningRateScheduler import LearningRateScheduler
from modules.util.enum.LossScaler import LossScaler
from modules.util.enum.LossWeight import LossWeight
from modules.util.enum.Optimizer import Optimizer
from modules.util.enum.TimestepDistribution import TimestepDistribution
from modules.util.optimizer_util import change_optimizer
from modules.util.ui.UIState import UIState


class TrainingTab(QWidget):
    def __init__(self, train_config: TrainConfig, ui_state: UIState, parent: QWidget = None):
        super().__init__(parent)

        self.train_config = train_config
        self.ui_state = ui_state

        # Main layout for the TrainingTab widget itself
        self.tab_main_layout = QVBoxLayout(self)
        self.tab_main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.tab_main_layout.addWidget(self.scroll_area)

        self.scroll_area_content_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_area_content_widget)

        # This QHBoxLayout will hold the columns
        self.columns_layout = QHBoxLayout(self.scroll_area_content_widget)

        self.lr_scheduler_comp = None # Will be QComboBox from qt_comps
        self.lr_scheduler_adv_comp = None # Will be QPushButton for "..."

        self.refresh_ui()

    # --- Temporary Helper Methods have been removed. Using qt_components now. ---

    def _create_options_adv_ui_element(self, parent_widget: QWidget, ui_state_key: str, items: list[tuple[str,Any]], tooltip: str = None, command: Callable = None, adv_command: Callable = None) -> QWidget:
        """
        Custom helper for options_adv since qt_components.create_options_kv returns a container with a label.
        This creates a QComboBox and a "..." QPushButton in a QHBoxLayout, without an external label.
        """
        widget = QWidget(parent_widget)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(5)

        # Manually create QComboBox part for options_adv, similar to qt_comps.create_options_kv but without its own label/container
        combo = QComboBox(widget)
        if tooltip: combo.setToolTip(tooltip)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        current_val = self.ui_state.get_var(ui_state_key)
        selected_idx = 0
        for idx, (text, data) in enumerate(items):
            combo.addItem(text, userData=data)
            if data == current_val: selected_idx = idx
        if combo.count() > 0 : combo.setCurrentIndex(selected_idx)

        def on_index_changed(idx): # Renamed index to idx to avoid conflict
            if idx >=0:
                data_val = combo.itemData(idx)
                self.ui_state.set_var(ui_state_key, data_val)
                if command: command(data_val)
        combo.currentIndexChanged.connect(on_index_changed)
        
        # Two-way binding for ComboBox
        def update_combo_from_state(new_data_value: Any):
            for i in range(combo.count()):
                if combo.itemData(i) == new_data_value:
                    if combo.currentIndex() != i: combo.setCurrentIndex(i)
                    return
            if combo.count() > 0 and combo.currentIndex() != 0 : pass # Defaulting logic can be tricky
        self.ui_state.track_variable(ui_state_key, update_combo_from_state)
        
        layout.addWidget(combo)

        adv_button = qt_comps.create_button(widget, "...", adv_command, fixed_width=30)
        layout.addWidget(adv_button)
        
        if ui_state_key == "learning_rate_scheduler":
            self.lr_scheduler_comp = combo
            self.lr_scheduler_adv_comp = adv_button
            # Initial state of adv_button based on loaded value
            self.__restore_scheduler_config(current_val) # current_val is the initial value for scheduler

        return widget


    def refresh_ui(self):
        # Clear existing columns from columns_layout
        while self.columns_layout.count():
            item = self.columns_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        column_0 = QFrame()
        col0_layout = QVBoxLayout(column_0)
        col0_layout.setContentsMargins(0,0,0,0)
        column_0.setLayout(col0_layout)
        
        column_1 = QFrame()
        col1_layout = QVBoxLayout(column_1)
        col1_layout.setContentsMargins(0,0,0,0)
        column_1.setLayout(col1_layout)

        column_2 = QFrame()
        col2_layout = QVBoxLayout(column_2)
        col2_layout.setContentsMargins(0,0,0,0)
        column_2.setLayout(col2_layout)

        self.columns_layout.addWidget(column_0, 1) # Weight 1 for each column
        self.columns_layout.addWidget(column_1, 1)
        self.columns_layout.addWidget(column_2, 1)

        if self.train_config.model_type.is_stable_diffusion():
            self.__setup_stable_diffusion_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_stable_diffusion_3():
            self.__setup_stable_diffusion_3_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_stable_diffusion_xl():
            self.__setup_stable_diffusion_xl_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_wuerstchen():
            self.__setup_wuerstchen_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_pixart():
            self.__setup_pixart_alpha_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_flux():
            self.__setup_flux_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_sana():
            self.__setup_sana_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_hunyuan_video():
            self.__setup_hunyuan_video_ui(column_0, column_1, column_2)
        elif self.train_config.model_type.is_hi_dream():
            self.__setup_hi_dream_ui(column_0, column_1, column_2)
        
        # Add stretch to each column layout to push frames to the top
        col0_layout.addStretch(1)
        col1_layout.addStretch(1)
        col2_layout.addStretch(1)
        
    def _add_frame_to_column(self, column_widget: QFrame, title: str = None) -> QGridLayout:
        # Creates a new QFrame, adds it to the column's QVBoxLayout, and returns a QGridLayout for content
        frame = QFrame()
        frame.setObjectName("groupFrame") # For potential styling
        frame.setFrameShape(QFrame.Shape.StyledPanel) # Gives it a border
        # frame.setFrameShadow(QFrame.Shadow.Raised)
        
        frame_layout = QVBoxLayout(frame) # Main layout for this new frame (holds title + grid)
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold;") # Basic title styling
            frame_layout.addWidget(title_label)

        content_grid_layout = QGridLayout() # Grid for the actual controls
        frame_layout.addLayout(content_grid_layout)
        
        column_widget.layout().addWidget(frame) # Add this new frame to the passed column widget
        return content_grid_layout


    def __create_base_frame(self, column: QFrame, row_idx_in_col_layout: int): # row_idx_in_col_layout not directly used with QVBoxLayout for columns
        grid = self._add_frame_to_column(column, "Base Training")
        content_widget = column # Parent for qt_comps helpers
        r = 0
        grid.addWidget(qt_comps.create_label(content_widget, "Optimizer", "The type of optimizer"), r, 0)
        grid.addWidget(self._create_options_adv_ui_element(content_widget, "optimizer.optimizer", [(str(x), x) for x in list(Optimizer)], command=self.__restore_optimizer_config, adv_command=self.__open_optimizer_params_window), r, 1)
        r+=1
        grid.addWidget(qt_comps.create_label(content_widget, "Learning Rate Scheduler", "Learning rate scheduler..."), r, 0)
        grid.addWidget(self._create_options_adv_ui_element(content_widget, "learning_rate_scheduler", [(str(x), x) for x in list(LearningRateScheduler)], command=self.__restore_scheduler_config, adv_command=self.__open_scheduler_params_window), r, 1)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "learning_rate", "Learning Rate", "The base learning rate", value_type=float), r, 0, 1, 2) # Spans 2 columns
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "learning_rate_warmup_steps", "LR Warmup Steps", "Number of steps for LR warmup...", placeholder_text="e.g. 0 or 0.1"), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "learning_rate_min_factor", "LR Min Factor", "Final LR will be initial_lr * min_factor", value_type=float), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "learning_rate_cycles", "LR Cycles", "Number of learning rate cycles...", value_type=int), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "epochs", "Epochs", "Number of epochs for a full training run", value_type=int), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "batch_size", "Batch Size", "Batch size for one training step", value_type=int), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "gradient_accumulation_steps", "Accumulation Steps", "Number of gradient accumulation steps", value_type=int), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "learning_rate_scaler", [(str(x), x) for x in list(LearningRateScaler)], "Learning Rate Scaler", "LR scaling: LR * SQRT(selection)"), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "clip_grad_norm", "Clip Grad Norm", "Clips gradient norm. Empty to disable.", value_type=float), r, 0, 1, 2)
        grid.setColumnStretch(1,1) # Ensure the entry/widget part of the container stretches


    def __create_base2_frame(self, column: QFrame, row_idx_in_col_layout: int, video_training_enabled: bool = False):
        grid = self._add_frame_to_column(column, "Advanced Base")
        content_widget = column
        r = 0
        grid.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "ema", [(str(x), x) for x in list(EMAMode)], "EMA", "EMA averages training progress..."), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "ema_decay", "EMA Decay", "EMA decay parameter...", value_type=float), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "ema_update_step_interval", "EMA Update Step Interval", "Steps between EMA updates", value_type=int), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_label(content_widget, "Gradient Checkpointing", "Enables gradient checkpointing..."), r, 0) # Label for options_adv
        grid.addWidget(self._create_options_adv_ui_element(content_widget, "gradient_checkpointing", [(str(x), x) for x in list(GradientCheckpointingMethod)], adv_command=self.__open_offloading_window), r, 1)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "layer_offload_fraction", "Layer Offload Fraction", "Offload layers to reduce VRAM... (0-1)", value_type=float), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "train_dtype", [("float32", DataType.FLOAT_32), ("float16", DataType.FLOAT_16), ("bfloat16", DataType.BFLOAT_16), ("tfloat32", DataType.TFLOAT_32)], "Train Data Type", "Mixed precision for training..."), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "fallback_train_dtype", [("float32", DataType.FLOAT_32), ("bfloat16", DataType.BFLOAT_16)], "Fallback Train Data Type", "Mixed precision for unsupported float16 stages..."), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "enable_autocast_cache", "Autocast Cache", "Enable autocast cache..."), r, 0, 1, 2)
        r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "resolution", "Resolution", "Training resolution(s)..."), r, 0, 1, 2)
        r+=1
        if video_training_enabled:
            grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "frames", "Frames", "Number of frames for video training.", value_type=int), r, 0, 1, 2)
            r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "force_circular_padding", "Force Circular Padding", "Enable circular padding for seamless images."), r, 0, 1, 2)
        grid.setColumnStretch(1,1)

    def __create_text_encoder_frame(self, column: QFrame, row_idx_in_col_layout: int):
        grid = self._add_frame_to_column(column, "Text Encoder")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "text_encoder.train", "Train Text Encoder", "Enables training the text encoder model"), r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "text_encoder.dropout_probability", "Dropout Probability", "Probability for dropping text encoder conditioning", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_time_entry(content_widget, self.ui_state, "text_encoder.stop_training_after", "text_encoder.stop_training_after_unit", "Stop Training After", "When to stop training the text encoder", default_unit="epochs", time_units=[("Epochs","epochs"),("Steps","steps")]),r,0,1,2); r+=1 # original supports_time_units=False
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "text_encoder.learning_rate", "Text Encoder LR", "LR for text encoder. Overrides base LR.", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "text_encoder_layer_skip", "Clip Skip", "Number of additional clip layers to skip. 0 = model default", value_type=int),r,0,1,2);
        grid.setColumnStretch(1,1)

    def __create_text_encoder_n_frame(self, column: QFrame, row_idx_in_col_layout: int, i: int, supports_include: bool = False, supports_layer_skip: bool = True):
        grid = self._add_frame_to_column(column, f"Text Encoder {i}")
        content_widget = column
        r=0; suffix = f"_{i}" if i > 1 else "" # Assuming key_paths are like "text_encoder_2.train"
        
        if supports_include:
            grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, f"text_encoder{suffix}.include", f"Include Text Encoder {i}", f"Includes text encoder {i} in the training run"),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, f"text_encoder{suffix}.train", f"Train Text Encoder {i}", f"Enables training the text encoder {i} model"),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, f"text_encoder{suffix}.train_embedding", f"Train Text Encoder {i} Embedding", f"Enables training embeddings for text encoder {i}"),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, f"text_encoder{suffix}.dropout_probability", "Dropout Probability", f"Probability for dropping text encoder {i} conditioning", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_time_entry(content_widget, self.ui_state, f"text_encoder{suffix}.stop_training_after",f"text_encoder{suffix}.stop_training_after_unit", "Stop Training After", f"When to stop training text encoder {i}", default_unit="epochs", time_units=[("Epochs","epochs"),("Steps","steps")]),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, f"text_encoder{suffix}.learning_rate", f"Text Encoder {i} LR", f"LR for text encoder {i}. Overrides base LR.", value_type=float),r,0,1,2); r+=1
        if supports_layer_skip:
            grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, f"text_encoder{suffix}_layer_skip", f"Text Encoder {i} Clip Skip", "Number of additional clip layers to skip. 0 = model default", value_type=int),r,0,1,2)
        grid.setColumnStretch(1,1)
        
    def __create_embedding_frame(self, column: QFrame, row_idx_in_col_layout: int):
        grid = self._add_frame_to_column(column, "Embeddings")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "embedding_learning_rate", "Embeddings LR", "LR for embeddings. Overrides base LR.", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "preserve_embedding_norm", "Preserve Embedding Norm", "Rescales each trained embedding to the median embedding norm"),r,0,1,2)
        grid.setColumnStretch(1,1)

    def __create_unet_frame(self, column: QFrame, row_idx_in_col_layout: int):
        grid = self._add_frame_to_column(column, "UNet")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "unet.train", "Train UNet", "Enables training the UNet model"),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_time_entry(content_widget, self.ui_state, "unet.stop_training_after","unet.stop_training_after_unit", "Stop Training After", "When to stop training the UNet", default_unit="epochs", time_units=[("Epochs","epochs"),("Steps","steps")]),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "unet.learning_rate", "UNet LR", "LR for UNet. Overrides base LR.", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "rescale_noise_scheduler_to_zero_terminal_snr", "Rescale Noise Scheduler to Zero Terminal SNR", "Rescales noise scheduler to zero terminal SNR and switches to v-prediction target"),r,0,1,2)
        grid.setColumnStretch(1,1)

    def __create_prior_frame(self, column: QFrame, row_idx_in_col_layout: int):
        grid = self._add_frame_to_column(column, "Prior / Transformer")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "prior.train", "Train Prior/Transformer", "Enables training the Prior/Transformer model"),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_time_entry(content_widget, self.ui_state, "prior.stop_training_after","prior.stop_training_after_unit", "Stop Training After", "When to stop training the Prior/Transformer", default_unit="epochs", time_units=[("Epochs","epochs"),("Steps","steps")]),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "prior.learning_rate", "Prior/Transformer LR", "LR for Prior/Transformer. Overrides base LR.", value_type=float),r,0,1,2)
        grid.setColumnStretch(1,1)

    def __create_transformer_frame(self, column: QFrame, row_idx_in_col_layout: int, supports_guidance_scale: bool = False):
        grid = self._add_frame_to_column(column, "Transformer")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "prior.train", "Train Transformer", "Enables training the Transformer model"),r,0,1,2); r+=1 # Uses prior.train key
        grid.addWidget(qt_comps.create_time_entry(content_widget, self.ui_state, "prior.stop_training_after","prior.stop_training_after_unit", "Stop Training After", "When to stop training the Transformer", default_unit="epochs", time_units=[("Epochs","epochs"),("Steps","steps")]),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "prior.learning_rate", "Transformer LR", "LR for Transformer. Overrides base LR.", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "prior.attention_mask", "Force Attention Mask", "Force enables passing text embedding attention mask to transformer."),r,0,1,2); r+=1
        if supports_guidance_scale:
            grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "prior.guidance_scale", "Guidance Scale", "Guidance scale for guidance distilled models.", value_type=float),r,0,1,2)
        grid.setColumnStretch(1,1)
        
    def __create_noise_frame(self, column: QFrame, row_idx_in_col_layout: int):
        grid = self._add_frame_to_column(column, "Noise & Timesteps")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "offset_noise_weight", "Offset Noise Weight", "Weight of offset noise", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "perturbation_noise_weight", "Perturbation Noise Weight", "Weight of perturbation noise", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_label(content_widget, "Timestep Distribution", "Selects function to sample timesteps"),r,0)
        grid.addWidget(self._create_options_adv_ui_element(content_widget, "timestep_distribution",[(str(x),x) for x in list(TimestepDistribution)],adv_command=self.__open_timestep_distribution_window),r,1); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "min_noising_strength", "Min Noising Strength", "Minimum noising strength", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "max_noising_strength", "Max Noising Strength", "Maximum noising strength", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "noising_weight", "Noising Weight (Gamma)", "Weight parameter of timestep distribution", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "noising_bias", "Noising Bias", "Bias parameter of timestep distribution", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "timestep_shift", "Timestep Shift", "Shift timestep distribution", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "dynamic_timestep_shifting", "Dynamic Timestep Shifting", "Dynamically shift timestep distribution based on resolution."),r,0,1,2)
        grid.setColumnStretch(1,1)

    def __create_masked_frame(self, column: QFrame, row_idx_in_col_layout: int):
        grid = self._add_frame_to_column(column, "Masked Training")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "masked_training", "Masked Training", "Masks training samples to focus on certain parts."),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "unmasked_probability", "Unmasked Probability", "Number of training steps on unmasked samples", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "unmasked_weight", "Unmasked Weight", "Loss weight of areas outside masked region", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "normalize_masked_area_loss", "Normalize Masked Area Loss", "Normalizes loss based on masked region size"),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "masked_prior_preservation_weight", "Masked Prior Preservation Weight", "Preserves regions outside mask using original model output. For LoRA.", value_type=float),r,0,1,2)
        grid.setColumnStretch(1,1)

    def __create_loss_frame(self, column: QFrame, row_idx_in_col_layout: int, supports_vb_loss: bool = False):
        grid = self._add_frame_to_column(column, "Loss Settings")
        content_widget = column
        r=0
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "mse_strength", "MSE Strength", "Mean Squared Error strength", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "mae_strength", "MAE Strength", "Mean Absolute Error strength", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "log_cosh_strength", "log-cosh Strength", "Log-Hyperbolic Cosine Error strength", value_type=float),r,0,1,2); r+=1
        if supports_vb_loss:
            grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "vb_loss_strength", "VB Strength", "Variational lower-bound strength. 1 for variational diffusion models.", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "loss_weight_fn",[(str(x),x) for x in list(LossWeight)], "Loss Weight Function", "Choice of loss weight function."),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "loss_weight_strength", "Gamma (Loss Weight Strength)", "Inverse strength of loss weighting. Range: 1-20 (Min SNR, P2).", value_type=float),r,0,1,2); r+=1
        grid.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "loss_scaler", [(str(x),x) for x in list(LossScaler)], "Loss Scaler", "Type of loss scaling: Loss * selection"),r,0,1,2)
        grid.setColumnStretch(1,1)
        
    # --- UI Setup methods based on model type (calling the frame creation methods) ---
    def __setup_stable_diffusion_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_frame(column_0, 1)
        self.__create_embedding_frame(column_0, 2)
        self.__create_base2_frame(column_1, 0)
        self.__create_unet_frame(column_1, 1)
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1) # Note: Original had this at row 1 in column 2
        self.__create_loss_frame(column_2, 2)

    def __setup_stable_diffusion_3_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_n_frame(column_0, 1, i=1, supports_include=True)
        self.__create_text_encoder_n_frame(column_0, 2, i=2, supports_include=True)
        self.__create_text_encoder_n_frame(column_0, 3, i=3, supports_include=True)
        self.__create_embedding_frame(column_0, 4)
        self.__create_base2_frame(column_1, 0)
        self.__create_transformer_frame(column_1, 1)
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1)
        self.__create_loss_frame(column_2, 2)

    def __setup_stable_diffusion_xl_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_n_frame(column_0, 1, i=1)
        self.__create_text_encoder_n_frame(column_0, 2, i=2)
        self.__create_embedding_frame(column_0, 3)
        self.__create_base2_frame(column_1, 0)
        self.__create_unet_frame(column_1, 1)
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1)
        self.__create_loss_frame(column_2, 2)

    def __setup_wuerstchen_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_frame(column_0, 1)
        self.__create_embedding_frame(column_0, 2)
        self.__create_base2_frame(column_1, 0)
        self.__create_prior_frame(column_1, 1) # Wuerstchen uses prior_frame
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 0) # Original had this at row 0
        self.__create_loss_frame(column_2, 1)

    def __setup_pixart_alpha_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_frame(column_0, 1)
        self.__create_embedding_frame(column_0, 2)
        self.__create_base2_frame(column_1, 0)
        self.__create_prior_frame(column_1, 1) # Pixart uses prior_frame
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1)
        self.__create_loss_frame(column_2, 2, supports_vb_loss=True)

    def __setup_flux_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_n_frame(column_0, 1, i=1, supports_include=True)
        self.__create_text_encoder_n_frame(column_0, 2, i=2, supports_include=True)
        self.__create_embedding_frame(column_0, 4) # Original was 3, but TE frames take 3 slots
        self.__create_base2_frame(column_1, 0)
        self.__create_transformer_frame(column_1, 1, supports_guidance_scale=True)
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1)
        self.__create_loss_frame(column_2, 2)

    def __setup_sana_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_frame(column_0, 1)
        self.__create_embedding_frame(column_0, 2)
        self.__create_base2_frame(column_1, 0)
        self.__create_prior_frame(column_1, 1) # Sana uses prior_frame
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1)
        self.__create_loss_frame(column_2, 2)

    def __setup_hunyuan_video_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_n_frame(column_0, 1, i=1, supports_include=True)
        self.__create_text_encoder_n_frame(column_0, 2, i=2, supports_include=True)
        self.__create_embedding_frame(column_0, 4) # Adjusted index
        self.__create_base2_frame(column_1, 0, video_training_enabled=True)
        self.__create_transformer_frame(column_1, 1, supports_guidance_scale=True)
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1)
        self.__create_loss_frame(column_2, 2)

    def __setup_hi_dream_ui(self, column_0, column_1, column_2):
        self.__create_base_frame(column_0, 0)
        self.__create_text_encoder_n_frame(column_0, 1, i=1, supports_include=True)
        self.__create_text_encoder_n_frame(column_0, 2, i=2, supports_include=True)
        self.__create_text_encoder_n_frame(column_0, 3, i=3, supports_include=True)
        self.__create_text_encoder_n_frame(column_0, 4, i=4, supports_include=True, supports_layer_skip=False)
        self.__create_embedding_frame(column_0, 5) # Adjusted index
        self.__create_base2_frame(column_1, 0, video_training_enabled=True)
        self.__create_transformer_frame(column_1, 1)
        self.__create_noise_frame(column_1, 2)
        self.__create_masked_frame(column_2, 1)
        self.__create_loss_frame(column_2, 2)

    # --- Dialog Opener Stubs ---
    def __open_optimizer_params_window(self):
        try:
            # Assuming OptimizerParamsWindow is already refactored and imported
            dialog = OptimizerParamsWindow(self, self.train_config, self.ui_state)
            dialog.exec()
        except Exception as e:
            print(f"Error opening OptimizerParamsWindow: {e}")
            # traceback.print_exc() # Consider if full traceback is always needed

    def __open_scheduler_params_window(self):
        try:
            dialog = SchedulerParamsWindow(self, self.train_config, self.ui_state)
            dialog.exec()
        except Exception as e:
            print(f"Error opening SchedulerParamsWindow: {e}")
            # traceback.print_exc()

    def __open_timestep_distribution_window(self): print("TODO: Open TimestepDistributionWindow") # Placeholder
    def __open_offloading_window(self): print("TODO: Open OffloadingWindow") # Placeholder

    # --- Config Restoration Callbacks ---
    def __restore_optimizer_config(self, *args):
        optimizer_config = change_optimizer(self.train_config)
        self.ui_state.get_var("optimizer").update(optimizer_config) # Assumes UIState var is a dict-like obj

    def __restore_scheduler_config(self, variable_value_str): # variable is the string value from combobox
        if not hasattr(self, 'lr_scheduler_adv_comp') or self.lr_scheduler_adv_comp is None:
            return
        if variable_value_str == LearningRateScheduler.CUSTOM.value: # Compare with enum's value
            self.lr_scheduler_adv_comp.setEnabled(True)
        else:
            self.lr_scheduler_adv_comp.setEnabled(False)
            
    # Public methods that TrainUI might call
    def refresh_ui_for_model_type(self, model_type):
        self.refresh_ui()

    def refresh_ui_for_training_method(self, training_method):
        self.refresh_ui()
