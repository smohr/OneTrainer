import json
import threading
import traceback
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

from modules.trainer.CloudTrainer import CloudTrainer
from modules.trainer.GenericTrainer import GenericTrainer
from modules.ui.AdditionalEmbeddingsTab import AdditionalEmbeddingsTab
from modules.ui.CaptionUI import CaptionUI
from modules.ui.CloudTab import CloudTab
from modules.ui.ConceptTab import ConceptTab
from modules.ui.ConvertModelUI import ConvertModelUI
from modules.ui.LoraTab import LoraTab
from modules.ui.ModelTab import ModelTab
from modules.ui.ProfilingWindow import ProfilingWindow
from modules.ui.SampleWindow import SampleWindow
from modules.ui.SamplingTab import SamplingTab
# from modules.ui.TopBar import TopBar # Will be refactored later
from modules.ui.TrainingTab import TrainingTab
from modules.ui.VideoToolUI import VideoToolUI # Needs refactor to QDialog/QWidget
from modules.util.callbacks.TrainCallbacks import TrainCallbacks
from modules.util.commands.TrainCommands import TrainCommands
from modules.util.config.TrainConfig import TrainConfig
from modules.util.enum.DataType import DataType
from modules.util.enum.ImageFormat import ImageFormat
from modules.util.enum.ModelType import ModelType
from modules.util.enum.TrainingMethod import TrainingMethod
from modules.util.torch_util import torch_gc
from modules.util.TrainProgress import TrainProgress
# import components  # This will need to be refactored or replaced
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon # Assuming set_window_icon will be adapted for QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.util.ui.ui_utils import get_icon_path # Assuming set_window_icon is replaced by a function that gives path
from modules.util.ui.UIState import UIState
from modules.zluda import ZLUDA
import modules.util.ui.qt_components as qt_comps # Import new shared components

import torch


# Placeholder for AppearanceModeTracker logic if needed
# from customtkinter import AppearanceModeTracker


class TrainUI(QMainWindow): # Changed from ctk.CTk to QMainWindow
    set_step_progress: Callable[[int, int], None] # This will need to be a QProgressBar
    set_epoch_progress: Callable[[int, int], None] # This will need to be a QProgressBar

    status_label: QLabel | None # Changed from ctk.CTkLabel
    training_button: QPushButton | None # Changed from ctk.CTkButton
    training_callbacks: TrainCallbacks | None
    training_commands: TrainCommands | None

    def __init__(self):
        super().__init__()

        self.setWindowTitle("OneTrainer")
        self.resize(1100, 740) # Changed from geometry

        QTimer.singleShot(100, lambda: self._set_icon()) # Changed from after

        # Appearance mode setting needs to be handled differently in Qt, possibly with stylesheets or system theme detection
        # ctk.set_appearance_mode("Light" if AppearanceModeTracker.detect_appearance_mode() == 0 else "Dark")
        # ctk.set_default_color_theme("blue") # Qt themes are handled via stylesheets or QPalette

        self.train_config = TrainConfig.default_values()
        self.train_config = TrainConfig.default_values()
        # UIState is initialized here. Passing 'self' (QMainWindow) as parent.
        # If UIState needs to connect signals for bi-directional updates, it can do so with 'parent'.
        self.ui_state = UIState(self, self.train_config)


        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.status_label = None
        self.training_button = None
        self.export_button = None
        self.tabview = None # Will be QTabWidget

        self.model_tab = None
        self.training_tab = None
        self.lora_tab = None
        self.cloud_tab = None
        self.additional_embeddings_tab = None

        # Placeholder for top_bar, content_frame, and bottom_bar
        # These will be QWidgets or QFrames added to main_layout
        self.top_bar_component = self._create_top_bar() # Renamed for clarity
        main_layout.addWidget(self.top_bar_component)

        self._create_content_frame(main_layout) # Pass layout to add tab widget

        self._create_bottom_bar(main_layout) # Pass layout to add bottom bar

        self.training_thread = None
        self.training_callbacks = None
        self.training_commands = None

        # Persistent profiling window.
        # self.profiling_window = ProfilingWindow(self) # ProfilingWindow will need to be a QWidget/QDialog

        # WM_DELETE_WINDOW is handled by overriding closeEvent in QMainWindow

    def closeEvent(self, event): # Replaces protocol("WM_DELETE_WINDOW", self.__close)
        if self.top_bar_component: # Ensure top_bar_component is initialized
             self.top_bar_component.save_default() # Assuming TopBar has save_default
        QApplication.instance().quit() # Changed from self.quit()
        event.accept()

    def _create_top_bar(self): # Renamed from top_bar and master is self
        # TopBar will need to be a QWidget subclass
        # For now, return a placeholder QFrame
        # return TopBar(
        #     self, # parent
        #     self.train_config,
        #     self.ui_state,
        #     self.change_model_type,
        #     self.change_training_method,
        #     self.load_preset,
        # )
        frame = QFrame(self)
        frame.setFixedHeight(50) # Example height
        frame.setStyleSheet("background-color: lightgray;")
        # self.top_bar_component will be this frame, or the TopBar instance
        return frame


    def _set_icon(self):
        """Set the window icon."""
        icon_path = get_icon_path() # Assumes this function returns the path to the icon
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

    def _create_bottom_bar(self, main_layout: QVBoxLayout): # Renamed from bottom_bar
        frame = QFrame()
        frame.setFixedHeight(50) # Example height
        # frame.setStyleSheet("background-color: lightgray;") # Optional styling
        bottom_layout = QHBoxLayout(frame)
        bottom_layout.setContentsMargins(5,5,5,5)
        bottom_layout.setSpacing(10)

        # self.set_step_progress, self.set_epoch_progress = components.double_progress(frame, 0, 0, "step", "epoch")
        # Replace components.double_progress with QProgressBars
        self.step_progress_bar = QProgressBar()
        self.step_progress_bar.setFormat("Step: %v/%m")
        bottom_layout.addWidget(self.step_progress_bar)
        self.set_step_progress = lambda current, total: self.step_progress_bar.setValue(current) if self.step_progress_bar.maximum() != total else self.step_progress_bar.setMaximum(total)


        self.epoch_progress_bar = QProgressBar()
        self.epoch_progress_bar.setFormat("Epoch: %v/%m")
        bottom_layout.addWidget(self.epoch_progress_bar)
        self.set_epoch_progress = lambda current, total: self.epoch_progress_bar.setValue(current) if self.epoch_progress_bar.maximum() != total else self.epoch_progress_bar.setMaximum(total)


        self.status_label = QLabel("Ready") # Changed from components.label
        self.status_label.setToolTip("Current status of the training run")
        bottom_layout.addWidget(self.status_label)

        # padding/spacer
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        bottom_layout.addItem(spacer)

        # tensorboard button
        tensorboard_button = QPushButton("Tensorboard") # Changed from components.button
        tensorboard_button.clicked.connect(self.open_tensorboard)
        bottom_layout.addWidget(tensorboard_button)

        # training button
        self.training_button = QPushButton("Start Training") # Changed from components.button
        self.training_button.clicked.connect(self.start_training)
        bottom_layout.addWidget(self.training_button)

        # export button
        self.export_button = QPushButton("Export") # Changed from components.button
        self.export_button.setToolTip("Export the current configuration as a script to run without a UI")
        self.export_button.clicked.connect(self.export_training)
        bottom_layout.addWidget(self.export_button)

        main_layout.addWidget(frame)
        # return frame # Not needed as it's added to main_layout

    def _create_content_frame(self, main_layout: QVBoxLayout): # Renamed from content_frame
        # The main content area will be a QTabWidget
        self.tabview = QTabWidget()
        main_layout.addWidget(self.tabview) # Add tab widget to the main layout, it will expand

        # self.general_tab = self.create_general_tab(self.tabview.add("general"))
        # self.model_tab = self.create_model_tab(self.tabview.add("model"))
        # self.data_tab = self.create_data_tab(self.tabview.add("data"))
        # self.create_concepts_tab(self.tabview.add("concepts"))
        # self.training_tab = self.create_training_tab(self.tabview.add("training"))
        # self.create_sampling_tab(self.tabview.add("sampling"))
        # self.backup_tab = self.create_backup_tab(self.tabview.add("backup"))
        # self.tools_tab = self.create_tools_tab(self.tabview.add("tools"))
        # self.additional_embeddings_tab = self.create_additional_embeddings_tab(self.tabview.add("additional embeddings"))
        # self.cloud_tab = self.create_cloud_tab(self.tabview.add("cloud"))

        # Placeholder: Add dummy tabs
        self.general_tab = QWidget()
        self.tabview.addTab(self.general_tab, "General")
        # Create and add tabs. Note that master is self.tabview (QTabWidget)
        self.general_tab = self.create_general_tab(self.tabview)
        self.model_tab_instance = self.create_model_tab(self.tabview) # Renamed to avoid conflict with property
        self.data_tab = self.create_data_tab(self.tabview)
        self.concepts_tab_instance = self.create_concepts_tab(self.tabview) # Placeholder
        self.training_tab_instance = self.create_training_tab(self.tabview) # Placeholder
        self.create_sampling_tab(self.tabview)
        self.backup_tab_instance = self.create_backup_tab(self.tabview)
        self.tools_tab_instance = self.create_tools_tab(self.tabview)
        self.additional_embeddings_tab_instance = self.create_additional_embeddings_tab(self.tabview) # Placeholder
        self.cloud_tab_instance = self.create_cloud_tab(self.tabview) # Placeholder


        self.change_training_method(self.train_config.training_method) # Call this after ALL tabs are potentially created

        # return frame # Not needed as tabview is added to main_layout

    # --- Helper methods have been moved to qt_components.py ---

    # --- Tab Creation Methods ---

    def create_general_tab(self, master_tab_widget: QTabWidget):
        page = QWidget(master_tab_widget) # Set parent for the page
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid_layout = QGridLayout(content_widget)
        grid_layout.setColumnStretch(1, 1) # Give more space to input fields column (index 1)
        grid_layout.setColumnStretch(3, 1) # And for the second set of input fields (index 3)

        row = 0
        # Workspace Directory
        grid_layout.addWidget(qt_comps.create_dir_entry(content_widget, self.ui_state, "workspace_dir", "Workspace Directory", "The directory where all files of this training run are saved"), row, 0, 1, 4) # Span 4 columns
        row += 1
        # Cache Directory
        grid_layout.addWidget(qt_comps.create_dir_entry(content_widget, self.ui_state, "cache_dir", "Cache Directory", "The directory where cached data is saved"), row, 0, 1, 4)
        row += 1
        
        # Two-column layout for switches and smaller entries
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "continue_last_backup", "Continue from last backup", "Automatically continues training from the last backup saved in <workspace>/backup"), row, 0, 1, 2)
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "only_cache", "Only Cache", "Only populate the cache, without any training"), row, 2, 1, 2)
        row += 1

        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "debug_mode", "Debug mode", "Save debug information during the training into the debug directory"), row, 0, 1, 2)
        # Debug Directory (only shown if debug_mode is true, or always visible?) - Assuming always visible for now
        grid_layout.addWidget(qt_comps.create_dir_entry(content_widget, self.ui_state, "debug_dir", "Debug Directory", "The directory where debug data is saved"), row, 2, 1, 2)
        row += 1
        
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "tensorboard", "Tensorboard", "Starts the Tensorboard Web UI during training"), row, 0, 1, 2)
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "tensorboard_expose", "Expose Tensorboard", "Exposes Tensorboard Web UI to all network interfaces"), row, 2, 1, 2)
        row += 1

        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "tensorboard_port", "Tensorboard Port", "Port to use for Tensorboard link", value_type=int), row, 0, 1, 2)
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "validation", "Validation", "Enable validation steps and add new graph in tensorboard"), row, 2, 1, 2)
        row += 1

        grid_layout.addWidget(qt_comps.create_time_entry(content_widget, self.ui_state, "validate_after", "validate_after_unit", "Validate after", "The interval used when validate training"), row, 0, 1, 4)
        row += 1
        
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "dataloader_threads", "Dataloader Threads", "Number of threads used for the data loader...", value_type=int), row, 0, 1, 2)
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "train_device", "Train Device", "The device used for training... Default:\"cuda\""), row, 2, 1, 2)
        row += 1
        
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "temp_device", "Temp Device", "The device used to temporarily offload models... Default:\"cpu\""), row, 0, 1, 2)
        row += 1

        grid_layout.setRowStretch(row, 1) # Add spacer at the bottom
        master_tab_widget.addTab(page, "General")
        return page

    def create_model_tab(self, master_tab_widget: QTabWidget):
        # This will eventually be an instance of the refactored ModelTab class
        # Import ModelTab
        from modules.ui.ModelTab import ModelTab
from modules.ui.ModelTab import ModelTab
from modules.ui.ModelTab import ModelTab
from modules.ui.ModelTab import ModelTab
from modules.ui.TrainingTab import TrainingTab
from modules.ui.ConceptTab import ConceptTab
from modules.ui.AdditionalEmbeddingsTab import AdditionalEmbeddingsTab
from modules.ui.CloudTab import CloudTab
from modules.ui.SamplingTab import SamplingTab # Import SamplingTab

        model_page_widget = ModelTab(self.train_config, self.ui_state, self) # Pass self as parent
        master_tab_widget.addTab(model_page_widget, "Model")
        return model_page_widget

    def create_data_tab(self, master_tab_widget: QTabWidget):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid_layout = QGridLayout(content_widget)
        grid_layout.setColumnStretch(1, 1) # Column for switches

        row = 0
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "aspect_ratio_bucketing", "Aspect Ratio Bucketing", "Aspect ratio bucketing enables training on images with different aspect ratios"), row, 0, 1, 2) # Span label + switch
        row += 1
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "latent_caching", "Latent Caching", "Caching of intermediate training data that can be re-used between epochs"), row, 0, 1, 2)
        row += 1
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "clear_cache_before_training", "Clear cache before training", "Clears the cache directory before starting to train..."), row, 0, 1, 2)
        
        grid_layout.setRowStretch(row + 1, 1) # Push content to top
        master_tab_widget.addTab(page, "Data")
        return page

    def create_concepts_tab(self, master_tab_widget: QTabWidget):
        concepts_page_widget = ConceptTab(self.train_config, self.ui_state, self) # Instantiate refactored ConceptTab
        master_tab_widget.addTab(concepts_page_widget, "Concepts")
        return concepts_page_widget

    def create_training_tab(self, master_tab_widget: QTabWidget) -> QWidget:
        training_page_widget = TrainingTab(self.train_config, self.ui_state, self) # Instantiate refactored TrainingTab
        master_tab_widget.addTab(training_page_widget, "Training")
        return training_page_widget

    def create_additional_embeddings_tab(self, master_tab_widget: QTabWidget): # Method name from original TrainUI
        additional_embeddings_page_widget = AdditionalEmbeddingsTab(self.train_config, self.ui_state, self)
        master_tab_widget.addTab(additional_embeddings_page_widget, "Additional Embeddings")
        return additional_embeddings_page_widget

    def create_cloud_tab(self, master_tab_widget: QTabWidget) -> QWidget:
        # parent_train_ui is self (the TrainUI instance), parent_qt_widget is also self (as it's a QWidget)
        cloud_page_widget = CloudTab(self.train_config, self.ui_state, self, self) 
        master_tab_widget.addTab(cloud_page_widget, "Cloud")
        return cloud_page_widget


    def create_sampling_tab(self, master_tab_widget: QTabWidget): 
        page = QWidget()
        page_layout = QVBoxLayout(page) 

        top_frame = QFrame()
        top_layout = QGridLayout(top_frame)
        page_layout.addWidget(top_frame)

        row = 0
        # Sample After (Time Entry) - Spans 2 columns in grid for its internal layout
        top_layout.addWidget(qt_comps.create_time_entry(top_frame, self.ui_state, "sample_after", "sample_after_unit", "Sample After", "The interval used when automatically sampling..."), row, 0, 1, 2)
        
        # Skip First (Entry) - Spans 2 columns
        top_layout.addWidget(qt_comps.create_entry(top_frame, self.ui_state, "sample_skip_first", "Skip First", "Start sampling automatically after this interval has elapsed.", value_type=int, placeholder_text="e.g. 0"), row, 2, 1, 2)

        # Format (Options KV) - Spans 2 columns
        top_layout.addWidget(qt_comps.create_options_kv(top_frame, self.ui_state, "sample_image_format", [("PNG", ImageFormat.PNG), ("JPG", ImageFormat.JPG)], "Format", "File Format used when saving samples"), row, 4, 1, 2)
        row +=1 

        # Buttons
        sample_now_btn_container = QWidget(top_frame) # Container for button to allow specific alignment/sizing if needed
        sample_now_btn_layout = QHBoxLayout(sample_now_btn_container)
        sample_now_btn_layout.setContentsMargins(0,0,0,0)
        sample_now_btn_layout.addWidget(qt_comps.create_button(top_frame, "Sample Now", self.sample_now))
        top_layout.addWidget(sample_now_btn_container, row, 0)

        manual_sample_btn_container = QWidget(top_frame)
        manual_sample_btn_layout = QHBoxLayout(manual_sample_btn_container)
        manual_sample_btn_layout.setContentsMargins(0,0,0,0)
        manual_sample_btn_layout.addWidget(qt_comps.create_button(top_frame, "Manual Sample", self.open_sample_ui))
        top_layout.addWidget(manual_sample_btn_container, row, 1)
        row +=1

        # Switches (can take full row span or be placed side-by-side)
        top_layout.addWidget(qt_comps.create_switch(top_frame, self.ui_state, "non_ema_sampling", "Non-EMA Sampling", "Whether to include non-ema sampling when using ema."), row, 0, 1, 3)
        top_layout.addWidget(qt_comps.create_switch(top_frame, self.ui_state, "samples_to_tensorboard", "Samples to Tensorboard", "Whether to include sample images in the Tensorboard output."), row, 3, 1, 3)
        
        # top_layout.setColumnStretch(6, 1) # Ensure last column with content can stretch if needed, or add a final stretch

        # Instantiate the refactored SamplingTab for the list part
        self.sampling_tab_list_instance = SamplingTab(self.train_config, self.ui_state, self)
        page_layout.addWidget(self.sampling_tab_list_instance)
        page_layout.setStretchFactor(self.sampling_tab_list_instance, 1) # Make it expand

        master_tab_widget.addTab(page, "Sampling")
        return page # Return the main page widget for the tab

    def create_backup_tab(self, master_tab_widget: QTabWidget): 
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid_layout = QGridLayout(content_widget)
        # Let column 1 (entries/compound widgets) take most of the space
        grid_layout.setColumnStretch(1, 1)
        # Column 3 for second set of entries/widgets if used
        grid_layout.setColumnStretch(3, 1)


        row = 0
        # Backup After & Backup Now button
        time_entry_backup = qt_comps.create_time_entry(content_widget, self.ui_state, "backup_after", "backup_after_unit", "Backup After", "The interval used when automatically creating model backups...")
        grid_layout.addWidget(time_entry_backup, row, 0, 1, 2) # Span 2 columns for label+widget
        grid_layout.addWidget(qt_comps.create_button(content_widget, "Backup Now", self.backup_now), row, 2)
        row += 1

        # Rolling Backup & Count
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "rolling_backup", "Rolling Backup", "If rolling backups are enabled, older backups are deleted automatically"), row, 0, 1, 2)
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "rolling_backup_count", "Rolling Backup Count", "Defines the number of backups to keep...", value_type=int), row, 2, 1, 2)
        row += 1

        # Backup Before Save
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "backup_before_save", "Backup Before Save", "Create a full backup before saving the final model"), row, 0, 1, 4) # Span all
        row += 1
        
        # Save Every & Save Now button
        time_entry_save = qt_comps.create_time_entry(content_widget, self.ui_state, "save_every", "save_every_unit", "Save Every", "The interval used when automatically saving the model during training")
        grid_layout.addWidget(time_entry_save, row, 0, 1, 2)
        grid_layout.addWidget(qt_comps.create_button(content_widget, "Save Now", self.save_now), row, 2)
        row += 1

        # Skip First (for saving)
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "save_skip_first", "Skip First Save", "Start saving automatically after this interval has elapsed", value_type=int), row, 0, 1, 2)
        row += 1
        
        # Save Filename Prefix
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "save_filename_prefix", "Save Filename Prefix", "The prefix for filenames used when saving the model..."), row, 0, 1, 4) # Span all
        row += 1

        grid_layout.setRowStretch(row, 1) # Push content to top
        master_tab_widget.addTab(page, "Backup")
        return page

    def lora_tab(self, master_tab_widget: QTabWidget) -> QWidget: 
        page = QWidget()
        # ScrollArea for LoRA tab as its content might grow
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        lora_layout = QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)

        main_page_layout = QVBoxLayout(page)
        main_page_layout.addWidget(scroll_area)
        main_page_layout.setContentsMargins(0,0,0,0) # No margins for the page itself, scroll area handles it
        
        row = 0
        lora_layout.addWidget(qt_comps.create_file_dir_entry(content_widget, self.ui_state, "lora_model_name", "file_open", "LoRA Base Model", "The base LoRA to train on. Leave empty to create a new LoRA", file_filter="Model Files (*.safetensors *.bin *.pt);;All Files (*)"), row, 0, 1, 2) # Span 2 for label+widget
        # path_modifier lambda x: Path(x).parent.absolute() if x.endswith(".json") else x -> This logic is complex for a generic helper if it depends on other state. UIState's set_var or a wrapper around it should handle this if possible.
        row += 1
        
        lora_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "lora_rank", "LoRA Rank", "The rank parameter used when creating a new LoRA", value_type=int), row, 0, 1, 2)
        row += 1
        
        lora_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "lora_alpha", "LoRA Alpha", "The alpha parameter used when creating a new LoRA", value_type=float), row, 0, 1, 2)
        row += 1
        
        lora_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "dropout_probability", "Dropout Probability", "Dropout probability... 0 disables, 1 maximum.", value_type=float), row, 0, 1, 2)
        row += 1
        
        lora_layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "lora_weight_dtype", [("float32", DataType.FLOAT_32), ("bfloat16", DataType.BFLOAT_16)], "LoRA Weight Data Type", "The LoRA weight data type used for training..."), row, 0, 1, 2)
        row += 1
        
        lora_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "bundle_additional_embeddings", "Bundle Embeddings", "Bundles any additional embeddings into the LoRA output file..."), row, 0, 1, 2)
        row += 1
        
        lora_layout.setColumnStretch(1, 1) # Ensure second column in grid (if helpers created 2) stretches
        lora_layout.setRowStretch(row, 1) # Push all content to the top
        return page


    def embedding_tab(self, master_tab_widget: QTabWidget) -> QWidget: 
        page = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)

        main_page_layout = QVBoxLayout(page)
        main_page_layout.addWidget(scroll_area)
        main_page_layout.setContentsMargins(0,0,0,0)

        row = 0
        grid_layout.addWidget(qt_comps.create_file_dir_entry(content_widget, self.ui_state, "embedding.model_name", "file_open", "Base Embedding", "The base embedding to train on...", file_filter="Model Files (*.pt *.safetensors);;All Files (*)"), row, 0, 1, 2)
        # path_modifier for embedding.model_name
        row += 1
        
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "embedding.token_count", "Token Count", "The token count used when creating a new embedding...", value_type=int), row, 0, 1, 2)
        row += 1
        
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "embedding.initial_embedding_text", "Initial Embedding Text", "The initial embedding text used when creating a new embedding"), row, 0, 1, 2)
        row += 1
        
        grid_layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "embedding_weight_dtype", [("float32", DataType.FLOAT_32), ("bfloat16", DataType.BFLOAT_16)], "Embedding Weight Data Type", "The Embedding weight data type used for training..."), row, 0, 1, 2)
        row += 1
        
        grid_layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "embedding.placeholder", "Placeholder", "The placeholder used when using the embedding in a prompt"), row, 0, 1, 2)
        row += 1
        
        grid_layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "embedding.is_output_embedding", "Output Embedding", "Output embeddings are calculated at the output of the text encoder..."), row, 0, 1, 2)
        row += 1
        
        grid_layout.setColumnStretch(1, 1) # Assuming helpers create label in col 0, widget in col 1 effectively
        grid_layout.setRowStretch(row, 1)
        return page


    def create_additional_embeddings_tab(self, master_tab_widget: QTabWidget):
        additional_embed_page = QWidget() 
        layout = QVBoxLayout(additional_embed_page)
        layout.addWidget(QLabel("Additional Embeddings Tab Content (To be implemented by AdditionalEmbeddingsTab class)"))
        master_tab_widget.addTab(additional_embed_page, "Additional Embeddings")
        return additional_embed_page


    def create_tools_tab(self, master_tab_widget: QTabWidget): 
        page = QWidget()
        layout = QVBoxLayout(page)
        # No scroll area needed if content is fixed and small
        
        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        layout.addWidget(content_widget) # Add content_widget to page's main layout

        row = 0
        grid_layout.addWidget(qt_comps.create_label(content_widget, "Dataset Tools", "Open the captioning tool"), row, 0)
        grid_layout.addWidget(qt_comps.create_button(content_widget, "Open", self.open_dataset_tool), row, 1)
        row += 1

        grid_layout.addWidget(qt_comps.create_label(content_widget, "Video Tools", "Open the video tools"), row, 0)
        grid_layout.addWidget(qt_comps.create_button(content_widget, "Open", self.open_video_tool), row, 1)
        row += 1

        grid_layout.addWidget(qt_comps.create_label(content_widget, "Convert Model Tools", "Open the model conversion tool"), row, 0)
        grid_layout.addWidget(qt_comps.create_button(content_widget, "Open", self.open_convert_model_tool), row, 1)
        row += 1

        grid_layout.addWidget(qt_comps.create_label(content_widget, "Sampling Tool", "Open the model sampling tool"), row, 0)
        grid_layout.addWidget(qt_comps.create_button(content_widget, "Open", self.open_sampling_tool), row, 1)
        row += 1

        grid_layout.addWidget(qt_comps.create_label(content_widget, "Profiling Tool", "Open the profiling tools."), row, 0)
        grid_layout.addWidget(qt_comps.create_button(content_widget, "Open", self.open_profiling_tool), row, 1)
        row += 1
        
        grid_layout.setRowStretch(row, 1) 
        grid_layout.setColumnStretch(2, 1) # Allow space to the right to stretch

        master_tab_widget.addTab(page, "Tools")
        return page

    def change_model_type(self, model_type: ModelType):
        # Placeholder for logic that might need to refresh UI elements in specific tabs
        # For example, if ModelTab content changes based on ModelType
        if self.model_tab_instance and hasattr(self.model_tab_instance, 'refresh_ui_for_model_type'):
            self.model_tab_instance.refresh_ui_for_model_type(model_type) # model_type is already in self.train_config

        if self.training_tab_instance and hasattr(self.training_tab_instance, 'refresh_ui_for_model_type'):
            self.training_tab_instance.refresh_ui_for_model_type(model_type) # model_type is already in self.train_config

        # LoraTab might be affected if LoRA options change per model type
        # self.lora_tab is the QWidget page itself. If LoraTab was a class, it would be self.lora_tab_instance
        if self.lora_tab and hasattr(self.lora_tab, 'refresh_ui_for_model_type'): 
             # This assumes the QWidget page returned by self.lora_tab() has this method.
             # More likely, if LoraTab becomes its own class, this logic moves there or is called on an instance.
            pass # self.lora_tab.refresh_ui_for_model_type(model_type)


    def change_training_method(self, training_method: TrainingMethod):
        if not self.tabview: 
            return

        # Refresh ModelTab as its content might depend on training method (e.g. output formats)
        if self.model_tab_instance and hasattr(self.model_tab_instance, 'refresh_ui_for_training_method'):
            self.model_tab_instance.refresh_ui_for_training_method(training_method) # training_method is already in self.train_config
        
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'refresh_ui_for_training_method'):
            self.training_tab_instance.refresh_ui_for_training_method(training_method)


        lora_tab_index = -1
        for i in range(self.tabview.count()):
            if self.tabview.tabText(i) == "LoRA":
                lora_tab_index = i
                break
        
        embedding_tab_index = -1
        for i in range(self.tabview.count()):
            if self.tabview.tabText(i) == "Embedding": 
                embedding_tab_index = i
                break

        # Remove LoRA tab if method is not LoRA and tab exists
        if training_method != TrainingMethod.LORA and lora_tab_index != -1:
            widget_to_remove = self.tabview.widget(lora_tab_index)
            self.tabview.removeTab(lora_tab_index)
            if widget_to_remove:
                widget_to_remove.deleteLater() 
            self.lora_tab = None 
        
        # Remove Embedding tab if method is not Embedding and tab exists
        if training_method != TrainingMethod.EMBEDDING and embedding_tab_index != -1:
            widget_to_remove = self.tabview.widget(embedding_tab_index)
            self.tabview.removeTab(embedding_tab_index)
            if widget_to_remove:
                widget_to_remove.deleteLater()
            # self.embedding_tab should also be cleared if you track it
            # For now, lora_tab was the main one tracked as a property for dynamic add/remove.

        # Add LoRA tab if method is LoRA and tab doesn't exist
        if training_method == TrainingMethod.LORA and lora_tab_index == -1:
            # lora_tab() method now returns a fully populated QWidget page
            self.lora_tab_page = self.lora_tab(self.tabview) # Pass tabview as master (though not strictly used by lora_tab itself)
            self.tabview.addTab(self.lora_tab_page, "LoRA")
            self.lora_tab = self.lora_tab_page # Keep track of the page widget

        # Add Embedding tab if method is Embedding and tab doesn't exist
        if training_method == TrainingMethod.EMBEDDING and embedding_tab_index == -1:
            self.embedding_tab_page = self.embedding_tab(self.tabview) 
            self.tabview.addTab(self.embedding_tab_page, "Embedding")
            # self.embedding_tab = self.embedding_tab_page # If you need to track it

    def load_preset(self):
        # frame.grid_columnconfigure(0, weight=0) # Label column
        # frame.grid_columnconfigure(1, weight=1) # Entry column (spans 1-3 if 4 columns total)
        # frame.grid_columnconfigure(2, weight=0) # Label column (for second pair)
        # frame.grid_columnconfigure(3, weight=1) # Entry column (for second pair)
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid_layout = QGridLayout(content_widget) # Using QGridLayout for form-like structure
        # grid_layout.setColumnStretch(1, 1) # Make column 1 stretchable
        # grid_layout.setColumnStretch(3, 1) # Make column 3 stretchable

        # workspace dir
        # components.label(frame, 0, 0, "Workspace Directory",
        #                  tooltip="The directory where all files of this training run are saved")
        ws_dir_label = QLabel("Workspace Directory")
        ws_dir_label.setToolTip("The directory where all files of this training run are saved")
        grid_layout.addWidget(ws_dir_label, 0, 0)
        # components.dir_entry(frame, 0, 1, self.ui_state, "workspace_dir")
        # -> This will be handled by create_general_tab directly using helpers.
        # cache dir
        # components.label(frame, 1, 0, "Cache Directory", ...)
        # components.dir_entry(frame, 1, 1, self.ui_state, "cache_dir")
        # -> etc. for all components in general tab

        # frame.pack(fill="both", expand=1) # Not needed with QScrollArea and QVBoxLayout for page
        master_tab_widget.addTab(page, "General")
        return page

    def create_model_tab(self, master_tab_widget: QTabWidget):
        # This will eventually be an instance of the refactored ModelTab class
        model_page = QWidget() 
        layout = QVBoxLayout(model_page)
        layout.addWidget(QLabel("Model Tab Content (To be implemented by ModelTab class)"))
        master_tab_widget.addTab(model_page, "Model")
        return model_page 

    def create_data_tab(self, master_tab_widget: QTabWidget):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid_layout = QGridLayout(content_widget)
        grid_layout.setColumnStretch(1, 1) 

        row = 0
        grid_layout.addWidget(self._create_label("Aspect Ratio Bucketing", "Aspect ratio bucketing enables training on images with different aspect ratios"), row, 0)
        grid_layout.addWidget(self._create_switch("aspect_ratio_bucketing"), row, 1)
        row += 1
        grid_layout.addWidget(self._create_label("Latent Caching", "Caching of intermediate training data that can be re-used between epochs"), row, 0)
        grid_layout.addWidget(self._create_switch("latent_caching"), row, 1)
        row += 1
        grid_layout.addWidget(self._create_label("Clear cache before training", "Clears the cache directory before starting to train..."), row, 0)
        grid_layout.addWidget(self._create_switch("clear_cache_before_training"), row, 1)
        
        grid_layout.setRowStretch(row + 1, 1)
        master_tab_widget.addTab(page, "Data")
        return page

    def create_concepts_tab(self, master_tab_widget: QTabWidget):
        concept_page = QWidget() 
        layout = QVBoxLayout(concept_page)
        layout.addWidget(QLabel("Concepts Tab Content (To be implemented by ConceptTab class)"))
        master_tab_widget.addTab(concept_page, "Concepts")
        # return concept_page 

    def create_training_tab(self, master_tab_widget: QTabWidget) -> QWidget: 
        training_page = QWidget()
        layout = QVBoxLayout(training_page)
        layout.addWidget(QLabel("Training Tab Content (To be implemented by TrainingTab class)"))
        master_tab_widget.addTab(training_page, "Training")
        return training_page


    def create_cloud_tab(self, master_tab_widget: QTabWidget) -> QWidget: 
        cloud_page = QWidget()
        layout = QVBoxLayout(cloud_page)
        layout.addWidget(QLabel("Cloud Tab Content (To be implemented by CloudTab class)"))
        master_tab_widget.addTab(cloud_page, "Cloud")
        return cloud_page


    def create_sampling_tab(self, master_tab_widget: QTabWidget): 
        page = QWidget()
        page_layout = QVBoxLayout(page) 

        top_frame = QFrame()
        top_layout = QGridLayout(top_frame) 
        page_layout.addWidget(top_frame)

        row = 0
        top_layout.addWidget(self._create_label("Sample After", "The interval used when automatically sampling..."), row, 0)
        top_layout.addWidget(self._create_time_entry("sample_after", "sample_after_unit"), row, 1)
        
        top_layout.addWidget(self._create_label("Skip First", "Start sampling automatically after this interval has elapsed."), row, 2)
        top_layout.addWidget(self._create_entry("sample_skip_first", type=int, width=75), row, 3) 

        top_layout.addWidget(self._create_label("Format", "File Format used when saving samples"), row, 4)
        top_layout.addWidget(self._create_options_kv("sample_image_format", [
            ("PNG", ImageFormat.PNG),
            ("JPG", ImageFormat.JPG),
        ]), row, 5)
        row +=1 # Next row for buttons

        sample_now_button = QPushButton("Sample Now")
        sample_now_button.clicked.connect(self.sample_now)
        top_layout.addWidget(sample_now_button, row, 0) # Place buttons as needed

        manual_sample_button = QPushButton("Manual Sample")
        manual_sample_button.clicked.connect(self.open_sample_ui)
        top_layout.addWidget(manual_sample_button, row, 1)
        row +=1

        top_layout.addWidget(self._create_label("Non-EMA Sampling", "Whether to include non-ema sampling when using ema."), row, 0)
        top_layout.addWidget(self._create_switch("non_ema_sampling"), row, 1)
        
        top_layout.addWidget(self._create_label("Samples to Tensorboard", "Whether to include sample images in the Tensorboard output."), row, 2)
        top_layout.addWidget(self._create_switch("samples_to_tensorboard"), row, 3)
        
        top_layout.setColumnStretch(6, 1) # Add stretch at the end of grid

        sampling_table_placeholder = QWidget() 
        sampling_table_layout = QVBoxLayout(sampling_table_placeholder)
        sampling_table_layout.addWidget(QLabel("Sampling Tab Table Content (To be implemented by SamplingTab class)"))
        page_layout.addWidget(sampling_table_placeholder)
        page_layout.setStretchFactor(sampling_table_placeholder, 1) 

        master_tab_widget.addTab(page, "Sampling")
        # return page

    def create_backup_tab(self, master_tab_widget: QTabWidget): 
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid_layout = QGridLayout(content_widget)
        grid_layout.setColumnStretch(1, 1) 
        grid_layout.setColumnStretch(4, 1)

        row = 0
        grid_layout.addWidget(self._create_label("Backup After", "The interval used when automatically creating model backups..."), row, 0)
        grid_layout.addWidget(self._create_time_entry("backup_after", "backup_after_unit"), row, 1, 1, 2) 

        backup_now_button = QPushButton("Backup Now")
        backup_now_button.clicked.connect(self.backup_now)
        grid_layout.addWidget(backup_now_button, row, 3)
        row += 1

        grid_layout.addWidget(self._create_label("Rolling Backup", "If rolling backups are enabled, older backups are deleted automatically"), row, 0)
        grid_layout.addWidget(self._create_switch("rolling_backup"), row, 1)

        grid_layout.addWidget(self._create_label("Rolling Backup Count", "Defines the number of backups to keep if rolling backups are enabled"), row, 3, Qt.AlignmentFlag.AlignRight)
        grid_layout.addWidget(self._create_entry("rolling_backup_count", type=int), row, 4)
        row += 1

        grid_layout.addWidget(self._create_label("Backup Before Save", "Create a full backup before saving the final model"), row, 0)
        grid_layout.addWidget(self._create_switch("backup_before_save"), row, 1)
        row += 1

        grid_layout.addWidget(self._create_label("Save Every", "The interval used when automatically saving the model during training"), row, 0)
        grid_layout.addWidget(self._create_time_entry("save_every", "save_every_unit"), row, 1, 1, 2)

        save_now_button = QPushButton("Save Now")
        save_now_button.clicked.connect(self.save_now)
        grid_layout.addWidget(save_now_button, row, 3)
        row += 1

        grid_layout.addWidget(self._create_label("Skip First", "Start saving automatically after this interval has elapsed"), row, 0)
        grid_layout.addWidget(self._create_entry("save_skip_first", type=int, width=75), row, 1) 

        row += 1
        grid_layout.addWidget(self._create_label("Save Filename Prefix", "The prefix for filenames used when saving the model during training"), row, 0)
        grid_layout.addWidget(self._create_entry("save_filename_prefix"), row, 1, 1, 4) # Span across remaining columns

        grid_layout.setRowStretch(row + 1, 1)
        master_tab_widget.addTab(page, "Backup")
        return page

    def lora_tab(self, master_tab_widget: QTabWidget) -> QWidget: 
        page = QWidget()
        # ScrollArea for LoRA tab as its content might grow
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        lora_layout = QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)

        main_page_layout = QVBoxLayout(page)
        main_page_layout.addWidget(scroll_area)
        main_page_layout.setContentsMargins(0,0,0,0)
        
        row = 0
        lora_layout.addWidget(self._create_label("LoRA base model", "The base LoRA to train on. Leave empty to create a new LoRA"), row, 0)
        lora_layout.addWidget(self._create_file_entry("lora_model_name", 
                                                   file_filter="Safetensors (*.safetensors);;PyTorch Binaries (*.bin *.pt);;All Files (*)",
                                                   path_modifier=lambda x: Path(x).parent.absolute() if x.endswith(".json") else x), row, 1)
        row += 1
        lora_layout.addWidget(self._create_label("LoRA rank", "The rank parameter used when creating a new LoRA"), row, 0)
        lora_layout.addWidget(self._create_entry("lora_rank", type=int), row, 1)
        row += 1
        lora_layout.addWidget(self._create_label("LoRA alpha", "The alpha parameter used when creating a new LoRA"), row, 0)
        lora_layout.addWidget(self._create_entry("lora_alpha", type=float), row, 1) # Alpha can be float
        row += 1
        lora_layout.addWidget(self._create_label("Dropout Probability", "Dropout probability... 0 disables, 1 maximum."), row, 0)
        lora_layout.addWidget(self._create_entry("dropout_probability", type=float), row, 1)
        row += 1
        lora_layout.addWidget(self._create_label("LoRA Weight Data Type", "The LoRA weight data type used for training..."), row, 0)
        lora_layout.addWidget(self._create_options_kv("lora_weight_dtype", [
            ("float32", DataType.FLOAT_32),
            ("bfloat16", DataType.BFLOAT_16),
        ]), row, 1)
        row += 1
        lora_layout.addWidget(self._create_label("Bundle Embeddings", "Bundles any additional embeddings into the LoRA output file..."), row, 0)
        lora_layout.addWidget(self._create_switch("bundle_additional_embeddings"), row, 1)
        
        lora_layout.setColumnStretch(1, 1) 
        lora_layout.setRowStretch(row + 1, 1)
        return page


    def embedding_tab(self, master_tab_widget: QTabWidget) -> QWidget: 
        page = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)

        main_page_layout = QVBoxLayout(page)
        main_page_layout.addWidget(scroll_area)
        main_page_layout.setContentsMargins(0,0,0,0)

        row = 0
        grid_layout.addWidget(self._create_label("Base embedding", "The base embedding to train on..."), row, 0)
        grid_layout.addWidget(self._create_file_entry("embedding.model_name", 
                                                  file_filter="PyTorch Binaries (*.bin *.pt);;Safetensors (*.safetensors);;All Files (*)",
                                                  path_modifier=lambda x: Path(x).parent.absolute() if x.endswith(".json") else x), row, 1)
        row += 1
        grid_layout.addWidget(self._create_label("Token count", "The token count used when creating a new embedding..."), row, 0)
        grid_layout.addWidget(self._create_entry("embedding.token_count", type=int), row, 1)
        row += 1
        grid_layout.addWidget(self._create_label("Initial embedding text", "The initial embedding text used when creating a new embedding"), row, 0)
        grid_layout.addWidget(self._create_entry("embedding.initial_embedding_text"), row, 1) 
        row += 1
        grid_layout.addWidget(self._create_label("Embedding Weight Data Type", "The Embedding weight data type used for training..."), row, 0)
        grid_layout.addWidget(self._create_options_kv("embedding_weight_dtype", [
            ("float32", DataType.FLOAT_32),
            ("bfloat16", DataType.BFLOAT_16),
        ]), row, 1)
        row += 1
        grid_layout.addWidget(self._create_label("Placeholder", "The placeholder used when using the embedding in a prompt"), row, 0)
        grid_layout.addWidget(self._create_entry("embedding.placeholder"), row, 1)
        row += 1
        grid_layout.addWidget(self._create_label("Output embedding", "Output embeddings are calculated at the output of the text encoder..."), row, 0)
        grid_layout.addWidget(self._create_switch("embedding.is_output_embedding"), row, 1)
        
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setRowStretch(row + 1, 1)
        return page


    def create_additional_embeddings_tab(self, master_tab_widget: QTabWidget):
        additional_embed_page = QWidget() 
        layout = QVBoxLayout(additional_embed_page)
        layout.addWidget(QLabel("Additional Embeddings Tab Content (To be implemented by AdditionalEmbeddingsTab class)"))
        master_tab_widget.addTab(additional_embed_page, "Additional Embeddings")
        return additional_embed_page


    def create_tools_tab(self, master_tab_widget: QTabWidget): 
        page = QWidget()
        layout = QVBoxLayout(page)
        # No scroll area needed if content is fixed and small
        
        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        layout.addWidget(content_widget)

        row = 0
        dataset_tools_button = QPushButton("Open")
        dataset_tools_button.clicked.connect(self.open_dataset_tool)
        grid_layout.addWidget(self._create_label("Dataset Tools", "Open the captioning tool"), row, 0)
        grid_layout.addWidget(dataset_tools_button, row, 1)
        row += 1

        video_tools_button = QPushButton("Open")
        video_tools_button.clicked.connect(self.open_video_tool)
        grid_layout.addWidget(self._create_label("Video Tools", "Open the video tools"), row, 0)
        grid_layout.addWidget(video_tools_button, row, 1)
        row += 1

        convert_model_button = QPushButton("Open")
        convert_model_button.clicked.connect(self.open_convert_model_tool)
        grid_layout.addWidget(self._create_label("Convert Model Tools", "Open the model conversion tool"), row, 0)
        grid_layout.addWidget(convert_model_button, row, 1)
        row += 1

        sampling_tool_button = QPushButton("Open")
        sampling_tool_button.clicked.connect(self.open_sampling_tool)
        grid_layout.addWidget(self._create_label("Sampling Tool", "Open the model sampling tool"), row, 0)
        grid_layout.addWidget(sampling_tool_button, row, 1)
        row += 1

        profiling_tool_button = QPushButton("Open")
        profiling_tool_button.clicked.connect(self.open_profiling_tool)
        grid_layout.addWidget(self._create_label("Profiling Tool", "Open the profiling tools."), row, 0)
        grid_layout.addWidget(profiling_tool_button, row, 1)
        
        grid_layout.setRowStretch(row + 1, 1) 
        grid_layout.setColumnStretch(2, 1)


        master_tab_widget.addTab(page, "Tools")
        return page

    def change_model_type(self, model_type: ModelType):
        # Placeholder for logic that might need to refresh UI elements in specific tabs
        # For example, if ModelTab content changes based on ModelType
        if self.model_tab and hasattr(self.model_tab, 'refresh_ui_for_model_type'): 
            self.model_tab.refresh_ui_for_model_type(model_type) 

        if self.training_tab and hasattr(self.training_tab, 'refresh_ui_for_model_type'):
            self.training_tab.refresh_ui_for_model_type(model_type)

        # LoraTab might be affected if LoRA options change per model type
        if self.lora_tab and hasattr(self.lora_tab, 'refresh_ui_for_model_type'): 
            self.lora_tab.refresh_ui_for_model_type(model_type)


    def change_training_method(self, training_method: TrainingMethod):
        if not self.tabview: 
            return

        # Refresh ModelTab as its content might depend on training method (e.g. output formats)
        if self.model_tab and hasattr(self.model_tab, 'refresh_ui_for_training_method'):
            self.model_tab.refresh_ui_for_training_method(training_method)

        lora_tab_index = -1
        for i in range(self.tabview.count()):
            if self.tabview.tabText(i) == "LoRA":
                lora_tab_index = i
                break
        
        embedding_tab_index = -1
        for i in range(self.tabview.count()):
            if self.tabview.tabText(i) == "Embedding": # Assuming "embedding" was the key
                embedding_tab_index = i
                break

        if training_method != TrainingMethod.LORA and lora_tab_index != -1:
            self.tabview.removeTab(lora_tab_index)
            self.lora_tab = None # This was the ctk frame, now it's the QWidget page
        
        if training_method != TrainingMethod.EMBEDDING and embedding_tab_index != -1:
            self.tabview.removeTab(embedding_tab_index)
            # self.embedding_tab_widget = None # Assuming you have a similar variable for embedding tab page

        if training_method == TrainingMethod.LORA and lora_tab_index == -1:
            # self.lora_tab = LoraTab(self.tabview.add("LoRA"), self.train_config, self.ui_state)
            # LoraTab needs to be a QWidget subclass that populates itself
            # For now, create a placeholder and add it
            # self.lora_tab_page = LoraTab(self.train_config, self.ui_state) # LoraTab returns a QWidget
            # self.tabview.addTab(self.lora_tab_page, "LoRA")
            # self.lora_tab = self.lora_tab_page # Keep track of the page widget
            pass # Placeholder: LoraTab creation will be handled by its own adapted class

        if training_method == TrainingMethod.EMBEDDING and embedding_tab_index == -1:
            # self.embedding_tab_page = self.embedding_tab(self.tabview) # embedding_tab now returns a QWidget page
            # self.tabview.addTab(self.embedding_tab_page, "Embedding")
            pass # Placeholder

    def load_preset(self):
        if not self.tabview:
            return

        # When a preset is loaded, various parts of train_config are updated.
        # We need to ensure that tabs reflecting this config also update their UI.
        
        # Example for ModelTab (if it has such a method)
        if self.model_tab_instance and hasattr(self.model_tab_instance, 'refresh_ui'):
            self.model_tab_instance.refresh_ui()

        # Example for TrainingTab (if it has such a method)
        if self.training_tab_instance and hasattr(self.training_tab_instance, 'refresh_ui'):
            self.training_tab_instance.refresh_ui()
            
        # For ConceptTab
        if self.concepts_tab_instance and hasattr(self.concepts_tab_instance, 'refresh_from_train_config'):
            self.concepts_tab_instance.refresh_from_train_config()
            
        if self.additional_embeddings_tab_instance and hasattr(self.additional_embeddings_tab_instance, 'refresh_ui'):
            self.additional_embeddings_tab_instance.refresh_ui()

        if self.cloud_tab_instance and hasattr(self.cloud_tab_instance, 'refresh_ui'):
            self.cloud_tab_instance.refresh_ui()
            
        if self.sampling_tab_list_instance and hasattr(self.sampling_tab_list_instance, 'refresh_ui'):
            self.sampling_tab_list_instance.refresh_ui()


        # After loading a preset, the training method might change, so refresh dynamic tabs
        self.change_training_method(self.train_config.training_method)


    def open_tensorboard(self):
        webbrowser.open("http://localhost:" + str(self.train_config.tensorboard_port), new=0, autoraise=False)

    def on_update_train_progress(self, train_progress: TrainProgress, max_sample: int, max_epoch: int):
        if self.step_progress_bar:
            if self.step_progress_bar.maximum() != max_sample:
                self.step_progress_bar.setMaximum(max_sample)
            self.step_progress_bar.setValue(train_progress.epoch_step)
        
        if self.epoch_progress_bar:
            if self.epoch_progress_bar.maximum() != max_epoch:
                self.epoch_progress_bar.setMaximum(max_epoch)
            self.epoch_progress_bar.setValue(train_progress.epoch)


    def on_update_status(self, status: str):
        if self.status_label:
            self.status_label.setText(status) # Changed from configure(text=status)

    def open_dataset_tool(self):
        # window = CaptionUI(self, None, False) # CaptionUI needs to be QDialog or QWidget
        # self.wait_window(window) # Replaced by dialog.exec() or showing a new window
        # caption_dialog = CaptionUI(self, None, False) # Assuming CaptionUI is now a QDialog
        # caption_dialog.exec() # For modal dialog
        try:
            # Assuming initial_dir and include_subdirectories might come from train_config or a default
            initial_dir = self.ui_state.get_var("workspace_dir", os.getcwd()) # Example: use workspace_dir
            # Assuming 'include_subdirectories' isn't a direct config, pass False or get from a relevant place
            # For now, let's assume it's not a readily available config for this generic call.
            # If CaptionUI itself has its own state for this, it will manage it.
            # The original CaptionUI took these as arguments.

            # Import CaptionUI here to avoid circular dependencies at module load time if CaptionUI also imports things from TrainUI's module space
            from modules.ui.CaptionUI import CaptionUI
            caption_dialog = CaptionUI(
                parent_widget=self, 
                initial_dir=initial_dir, 
                initial_include_subdirectories=False # Defaulting this, adjust if stored elsewhere
            )
            caption_dialog.exec() # Show as modal dialog
        except Exception as e:
            print(f"Error opening CaptionUI: {e}")
            traceback.print_exc()
            # Optionally, show a QMessageBox to the user about the error

    def open_video_tool(self):
        # window = VideoToolUI(self) # VideoToolUI needs to be QDialog or QWidget
        # self.wait_window(window)
        # video_dialog = VideoToolUI(self)
        # video_dialog.exec()
        try:
            from modules.ui.VideoToolUI import VideoToolUI # Dynamic import
            video_dialog = VideoToolUI(parent_widget=self)
            video_dialog.exec()
        except Exception as e:
            print(f"Error opening VideoToolUI: {e}")
            traceback.print_exc()

    def open_convert_model_tool(self):
        try:
            from modules.ui.ConvertModelUI import ConvertModelUI # Dynamic import
            convert_dialog = ConvertModelUI(parent_widget=self)
            convert_dialog.exec()
        except Exception as e:
            print(f"Error opening ConvertModelUI: {e}")
            traceback.print_exc()

    def open_sampling_tool(self):
        if not self.training_callbacks and not self.training_commands:
            # window = SampleWindow(self, train_config=self.train_config) # SampleWindow needs to be QDialog/QWidget
            # self.wait_window(window)
            # sample_dialog = SampleWindow(self, train_config=self.train_config)
            # sample_dialog.exec()
            torch_gc()
            pass # Placeholder

    def open_profiling_tool(self):
        # self.profiling_window.deiconify() # This is Tkinter specific
        # Assuming self.profiling_window is a QWidget (e.g. QDialog or another QMainWindow)
        # if self.profiling_window:
        #     self.profiling_window.show()
        #     self.profiling_window.raise_() # Bring to front
        #     self.profiling_window.activateWindow() # Ensure it has focus
        pass # Placeholder


    def open_sample_ui(self):
        training_callbacks = self.training_callbacks
        training_commands = self.training_commands

        if training_callbacks and training_commands:
            # window = SampleWindow(self, callbacks=training_callbacks, commands=training_commands)
            # self.wait_window(window)
            # sample_dialog = SampleWindow(self, callbacks=training_callbacks, commands=training_commands)
            # sample_dialog.exec()
            # training_callbacks.set_on_sample_custom() # Ensure this is still valid
            pass # Placeholder


    def __training_thread_function(self):
        error_caught = False

        self.training_callbacks = TrainCallbacks(
            on_update_train_progress=self.on_update_train_progress,
            on_update_status=self.on_update_status,
        )

        if self.train_config.cloud.enabled:
            trainer = CloudTrainer(self.train_config, self.training_callbacks, self.training_commands, reattach=self.cloud_tab.reattach if self.cloud_tab else None) # Ensure cloud_tab has reattach
        else:
            ZLUDA.initialize_devices(self.train_config)
            trainer = GenericTrainer(self.train_config, self.training_callbacks, self.training_commands)

        try:
            trainer.start()
            if self.train_config.cloud.enabled:
                # Ensure ui_state and its methods are adapted if they interact with UI directly
                # self.ui_state.get_var("secrets.cloud").update(self.train_config.secrets.cloud)
                pass # Placeholder: ui_state interaction needs review
            trainer.train()
        except Exception:
            if self.train_config.cloud.enabled:
                # self.ui_state.get_var("secrets.cloud").update(self.train_config.secrets.cloud)
                pass # Placeholder
            error_caught = True
            traceback.print_exc()

        trainer.end()

        del trainer

        self.training_thread = None
        self.training_commands = None
        torch.clear_autocast_cache()
        torch_gc()

        if error_caught:
            self.on_update_status("error: check the console for more information")
        else:
            self.on_update_status("stopped")
        
        if self.training_button:
            self.training_button.setText("Start Training") # Changed from configure
            self.training_button.setEnabled(True)


    def start_training(self):
        if self.training_thread is None:
            if self.top_bar_component and hasattr(self.top_bar_component, 'save_default'):
                 self.top_bar_component.save_default()

            if self.training_button:
                self.training_button.setText("Stop Training") # Changed from configure
                self.training_button.setEnabled(True)


            self.training_commands = TrainCommands()

            self.training_thread = threading.Thread(target=self.__training_thread_function)
            self.training_thread.start()
        else:
            if self.training_button:
                self.training_button.setEnabled(False) # Changed from configure
            self.on_update_status("stopping")
            if self.training_commands:
                self.training_commands.stop()

    def export_training(self):
        # file_path = filedialog.asksaveasfilename(...) # Tkinter dialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Configuration", ".", "JSON Files (*.json);;All Files (*.*)")

        if file_path:
            with open(file_path, "w") as f:
                json.dump(self.train_config.to_pack_dict(secrets=False), f, indent=4)

    def sample_now(self):
        train_commands = self.training_commands
        if train_commands:
            train_commands.sample_default()

    def backup_now(self):
        train_commands = self.training_commands
        if train_commands:
            train_commands.backup()

    def save_now(self):
        train_commands = self.training_commands
        if train_commands:
            train_commands.save()

# The following is needed to run a PySide6 application
# if __name__ == '__main__':
#     import sys
#     app = QApplication(sys.argv)
#     # You might need to initialize other things here like UIState if it's not passed to TrainUI or created inside
#     # For example, if UIState needs the app instance or some global config before UI is shown.
#     main_window = TrainUI()
#     main_window.show()
#     sys.exit(app.exec())
