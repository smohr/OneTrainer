from pathlib import Path
from typing import List, Dict, Any, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox, QCheckBox, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, Slot
import modules.util.ui.qt_components as qt_comps # Import new shared components

# from modules.ui.ConfigList import ConfigList # Original base
from modules.ui.ConfigListBase import ConfigListBase # New base
from modules.util.config.TrainConfig import TrainConfig, TrainEmbeddingConfig
from modules.util.ui.UIState import UIState
# PIL import for image manipulation if needed, though not directly used in this specific tab's preview
# from PIL import Image
# from PIL.ImageQt import ImageQt

class EmbeddingWidget(QFrame):
    # Signals for widget interactions
    remove_requested = Signal(int)      # index
    clone_requested = Signal(int, object)       # index, callback for randomization
    # save_command was passed but not used for opening a window; direct changes save via UIState

    def __init__(self, element_data: TrainEmbeddingConfig, index: int, parent: QWidget = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("EmbeddingWidgetFrame")

        self.element_data = element_data
        # UIState for this specific embedding widget.
        # Pass None as parent to UIState, assuming it can operate for data holding.
        self.ui_state = UIState(None, self.element_data)
        self.index = index
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5,5,5,5)
        main_layout.setSpacing(3)

        top_frame = QFrame()
        top_layout = QGridLayout(top_frame)
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.setSpacing(5)
        main_layout.addWidget(top_frame)

        bottom_frame = QFrame()
        bottom_layout = QGridLayout(bottom_frame)
        bottom_layout.setContentsMargins(0,0,0,0)
        bottom_layout.setSpacing(5)
        main_layout.addWidget(bottom_frame)

        # --- Populate Top Frame ---
        self.clone_button = QPushButton("+")
        self.clone_button.setFixedSize(22,22)
        self.clone_button.setToolTip("Clone Embedding Config")
        self.clone_button.clicked.connect(self._on_clone_click)
        top_layout.addWidget(self.clone_button, 0, 0)

        self.remove_button = QPushButton("X")
        self.remove_button.setFixedSize(22,22)
        self.remove_button.setToolTip("Remove Embedding Config")
        self.remove_button.setStyleSheet("QPushButton { color: white; background-color: #C00000; }")
        self.remove_button.clicked.connect(self._on_remove_click)
        top_layout.addWidget(self.remove_button, 0, 1, Qt.AlignmentFlag.AlignLeft)
        
        # Spacer to push controls apart
        top_layout.addItem(QSpacerItem(10,1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum), 0, 2)

        # Base Embedding (File Entry)
        top_layout.addWidget(qt_comps.create_file_dir_entry(top_frame, self.ui_state, "model_name", "file_open", "Base Embedding:", "The base embedding to train on. Leave empty to create a new embedding", file_filter="Model Files (*.pt *.safetensors);;All Files (*)"), 0, 3, 1, 2) # Spans 2 grid cells (label is inside)
        
        # Placeholder (Entry)
        top_layout.addWidget(qt_comps.create_entry(top_frame, self.ui_state, "placeholder", "Placeholder:", "The placeholder used when using the embedding in a prompt"), 0, 5, 1, 2)
        
        # Token Count (Entry)
        top_layout.addWidget(qt_comps.create_entry(top_frame, self.ui_state, "token_count", "Token Count:", "Token count for new embedding. Empty to auto detect.", value_type=int), 0, 7, 1, 2) # Width handled by grid stretch

        top_layout.setColumnStretch(4, 3) # Give more stretch to file path container
        top_layout.setColumnStretch(6, 2) # And placeholder container
        top_layout.setColumnStretch(8, 1) # Token count container

        # --- Populate Bottom Frame ---
        # Train (Switch)
        bottom_layout.addWidget(qt_comps.create_switch(bottom_frame, self.ui_state, "train", "Train", "Enable training for this embedding"), 0, 0, 1, 2)

        # Output Embedding (Switch)
        bottom_layout.addWidget(qt_comps.create_switch(bottom_frame, self.ui_state, "is_output_embedding", "Output Embedding", "Output embeddings are calculated at the text encoder output..."), 0, 2, 1, 2)
        
        # Stop Training After (Time Entry)
        bottom_layout.addWidget(qt_comps.create_time_entry(bottom_frame, self.ui_state, "stop_training_after", "stop_training_after_unit", "Stop Training After:", "When to stop training the embedding", default_unit="epochs", time_units=[("Epochs","epochs"), ("Steps","steps")]), 0, 4, 1, 2)

        # Initial Embedding Text (Entry)
        bottom_layout.addWidget(qt_comps.create_entry(bottom_frame, self.ui_state, "initial_embedding_text", "Initial Text:", "Initial text for new embedding"), 0, 6, 1, 3) # Span more for text
        bottom_layout.setColumnStretch(7, 3) # Give more stretch to initial text container

    def _on_remove_click(self):
        self.remove_requested.emit(self.index)

    def _on_clone_click(self):
        self.clone_requested.emit(self.index, self.__randomize_uuid)

    def __randomize_uuid(self, embedding_config: TrainEmbeddingConfig) -> TrainEmbeddingConfig:
        embedding_config.uuid = TrainEmbeddingConfig.default_values().uuid
        return embedding_config

    # --- Temporary Helper Methods for UI elements within EmbeddingWidget ---
    # These are now removed as qt_components are used directly.


class AdditionalEmbeddingsTab(ConfigListBase):
    def __init__(self, train_config: TrainConfig, ui_state: UIState, parent: QWidget = None):
        super().__init__(parent, add_button_text="Add Embedding")
        self.train_config = train_config
        # self.ui_state = ui_state # Main UIState from TrainUI, not directly used by this tab itself for its own properties

        # ConfigListBase provides self.scroll_content_widget. We set its layout.
        # Each EmbeddingWidget will take full width, so QVBoxLayout.
        self.items_layout = QVBoxLayout(self.scroll_content_widget)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_content_widget.setLayout(self.items_layout)

        self._load_embeddings_from_config()
        self.refresh_list_display()

    def _load_embeddings_from_config(self):
        # `additional_embeddings` is a list directly in train_config
        if not hasattr(self.train_config, 'additional_embeddings') or \
           not isinstance(self.train_config.additional_embeddings, list):
            self.train_config.additional_embeddings = []

        # Ensure all items are TrainEmbeddingConfig instances
        temp_embeddings = []
        for i, emb_data in enumerate(self.train_config.additional_embeddings):
            if isinstance(emb_data, dict):
                try:
                    temp_embeddings.append(TrainEmbeddingConfig(**emb_data))
                except Exception as e:
                    print(f"Error converting additional embedding data to TrainEmbeddingConfig for item {i}: {e}")
            elif isinstance(emb_data, TrainEmbeddingConfig):
                temp_embeddings.append(emb_data)
        self.train_config.additional_embeddings = temp_embeddings
        
    def _save_embeddings_config(self):
        # Changes are made directly to self.train_config.additional_embeddings (list of objects).
        # The main TrainUI or app logic is responsible for saving the overall TrainConfig.
        # This method could be used if this tab's config was in a separate file.
        print("AdditionalEmbeddingsTab: _save_embeddings_config called (placeholder, usually not needed if part of main config)")

    @Slot()
    def on_add_new_element(self):
        new_embedding_data = self.create_new_element() # This returns a dict
        self.train_config.additional_embeddings.append(TrainEmbeddingConfig(**new_embedding_data))
        self._save_embeddings_config() 
        self.refresh_list_display()

    def refresh_list_display(self):
        self._clear_layout(self.items_layout)
        for i, embedding_data_obj in enumerate(self.train_config.additional_embeddings):
            widget = self.create_widget(embedding_data_obj, i)
            self.items_layout.addWidget(widget)
        self.items_layout.addStretch(1) # Push items to the top

    def create_widget(self, element_data: TrainEmbeddingConfig, index: int) -> EmbeddingWidget:
        widget = EmbeddingWidget(element_data, index)
        widget.remove_requested.connect(self.remove_element_slot)
        widget.clone_requested.connect(self.clone_element_slot)
        # No direct save_requested from EmbeddingWidget to save whole list, as changes are live on UIState
        return widget

    def create_new_element(self) -> Dict[str, Any]: # Returns dict for TrainEmbeddingConfig
        return TrainEmbeddingConfig.default_values().to_dict() # Assuming to_dict() exists

    @Slot(int)
    def remove_element_slot(self, index: int):
        if 0 <= index < len(self.train_config.additional_embeddings):
            del self.train_config.additional_embeddings[index]
            self._save_embeddings_config()
            self.refresh_list_display()

    @Slot(int, object)
    def clone_element_slot(self, index: int, randomize_callback: Callable):
        if 0 <= index < len(self.train_config.additional_embeddings):
            original_embedding = self.train_config.additional_embeddings[index]
            cloned_data = original_embedding.to_dict() # Assuming TrainEmbeddingConfig has to_dict()
            
            cloned_embedding = TrainEmbeddingConfig(**cloned_data)
            if randomize_callback:
                cloned_embedding = randomize_callback(cloned_embedding)
            
            self.train_config.additional_embeddings.insert(index + 1, cloned_embedding)
            self._save_embeddings_config()
            self.refresh_list_display()
            
    # Public method for TrainUI to call if needed (e.g., after loading a preset)
    def refresh_ui(self): # Called by TrainUI's load_preset
        self._load_embeddings_from_config() # Ensure data is in correct type
        self.refresh_list_display()

    # open_element_window was 'pass' in original, so no slot needed unless functionality is added.
    # def open_element_window_slot(self, index: int):
    #     pass
    
    # save_config_slot is not strictly necessary here as changes are live on train_config.
    # If there were an explicit "Save All Additional Embeddings" button, it would call _save_embeddings_config.
    # def save_config_slot(self):
    #     self._save_embeddings_config()
