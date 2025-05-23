from typing import List, Dict, Any, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot
import modules.util.ui.qt_components as qt_comps # Import shared components

# from modules.ui.ConfigList import ConfigList # Original base
from modules.ui.ConfigListBase import ConfigListBase # New base
# from modules.ui.SampleParamsWindow import SampleParamsWindow # TODO: Refactor to QDialog
from modules.util.config.SampleConfig import SampleConfig
from modules.util.config.TrainConfig import TrainConfig
from modules.util.ui.UIState import UIState
# import customtkinter as ctk # Removed
# from modules.util.ui import components # Removed

class SampleWidget(QFrame):
    # Signals
    open_requested = Signal(int, object)  # index, ui_state_for_element
    remove_requested = Signal(int)
    clone_requested = Signal(int) # No randomize callback in original for SampleWidget clone
    save_requested = Signal() # To trigger save of the main config file

    def __init__(self, element_data: SampleConfig, index: int, parent: QWidget = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("SampleWidgetFrame")

        self.element_data = element_data
        # UIState for this specific sample widget.
        self.ui_state = UIState(None, self.element_data) # Parent None for now
        self.index = index

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5,5,5,5)
        main_layout.setSpacing(5)

        self.remove_button = QPushButton("X")
        self.remove_button.setFixedSize(22,22)
        self.remove_button.setToolTip("Remove Sample")
        self.remove_button.setStyleSheet("QPushButton { color: white; background-color: #C00000; }")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.index))
        main_layout.addWidget(self.remove_button)

        self.clone_button = QPushButton("+")
        self.clone_button.setFixedSize(22,22)
        self.clone_button.setToolTip("Clone Sample")
        self.clone_button.setStyleSheet("QPushButton { color: white; background-color: #00C000; }")
        self.clone_button.clicked.connect(lambda: self.clone_requested.emit(self.index))
        main_layout.addWidget(self.clone_button)

        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(self.ui_state.get_var("enabled", False))
        self.enabled_checkbox.toggled.connect(self.__switch_enabled)
        main_layout.addWidget(self.enabled_checkbox)
        
        # Use qt_comps.create_entry, which returns a container.
        # For this horizontal layout, we want label then entry.
        # qt_comps.create_entry with label_on_left=True by default creates label-entry HBox.
        # So, we add these containers directly.
        self.width_entry_container = qt_comps.create_entry(self, self.ui_state, "width", "Width:", value_type=int)
        self.width_entry = self.width_entry_container.findChild(QLineEdit)
        if self.width_entry: self.width_entry.setFixedWidth(50) # Apply fixed width to internal QLineEdit
        main_layout.addWidget(self.width_entry_container)

        self.height_entry_container = qt_comps.create_entry(self, self.ui_state, "height", "Height:", value_type=int)
        self.height_entry = self.height_entry_container.findChild(QLineEdit)
        if self.height_entry: self.height_entry.setFixedWidth(50)
        main_layout.addWidget(self.height_entry_container)

        self.seed_entry_container = qt_comps.create_entry(self, self.ui_state, "seed", "Seed:", value_type=int)
        self.seed_entry = self.seed_entry_container.findChild(QLineEdit)
        if self.seed_entry: self.seed_entry.setFixedWidth(80)
        main_layout.addWidget(self.seed_entry_container)

        self.prompt_entry_container = qt_comps.create_entry(self, self.ui_state, "prompt", "Prompt:")
        self.prompt_entry = self.prompt_entry_container.findChild(QLineEdit)
        main_layout.addWidget(self.prompt_entry_container, 1) # Give prompt entry stretch factor

        self.params_button = qt_comps.create_button(self, "...", command=lambda: self.open_requested.emit(self.index, self.ui_state), tooltip="Edit Sample Parameters", fixed_width=30, fixed_height=22)
        main_layout.addWidget(self.params_button)
        
        self.__set_enabled_state(self.enabled_checkbox.isChecked())

    # --- Temporary Helper Methods for UI elements within SampleWidget ---
    # These are now removed.
    # --- End Helper Methods ---

    def __switch_enabled(self, checked: bool):
        # 'enabled' state is already set by QCheckBox through UIState binding if it were from qt_comps.
        # However, this QCheckBox is created manually. So, we set UIState here.
        self.ui_state.set_var("enabled", checked) 
        self.save_requested.emit()
        self.__set_enabled_state(checked)

    def __set_enabled_state(self, is_enabled: bool):
        self.width_entry.setEnabled(is_enabled)
        self.height_entry.setEnabled(is_enabled)
        self.prompt_entry.setEnabled(is_enabled)
        self.seed_entry.setEnabled(is_enabled)
        self.params_button.setEnabled(is_enabled)


class SamplingTab(ConfigListBase):
    def __init__(self, train_config: TrainConfig, ui_state: UIState, parent: QWidget = None):
        # Note: Original SamplingTab was also a ConfigList that handled samples.json
        # The top part of sampling tab (sample_after, skip_first, etc.) is in TrainUI.py
        # This class now represents the list of individual sample configurations.
        super().__init__(parent, add_button_text="Add Sample Prompt") # "Add Sample" was for the whole file

        self.train_config = train_config
        # This specific UIState is for the list itself, not directly used for list properties here.
        # self.list_ui_state = ui_state_main # If SamplingTab needed its own UIState for its properties

        super().__init__(
            parent_widget=parent,
            add_button_text="Add Sample Prompt",
            train_config_main=train_config,
            ui_state_main=ui_state, # This is the main UIState for TrainConfig
            list_attr_name="sample_configs", # Attribute in TrainConfig holding the list
            from_external_file_key_path="samples_from_external_file", # Key in TrainConfig to check if list is external
            external_file_path_key_path="sample_definition_file_name", # Key in TrainConfig for the external file path
            default_external_filename="samples.json", # Default filename if path is empty
            config_item_class=SampleConfig # Class to instantiate for items from file
        )
        
        # ConfigListBase now initializes self.items_layout and self.scroll_content_widget
        # We ensure items_layout is QVBoxLayout if not already set by base or if we want to override.
        if not isinstance(self.items_layout, QVBoxLayout):
            self._clear_layout(self.items_layout) # Clear if it was, e.g. QGridLayout
            self.items_layout = QVBoxLayout()
            self.scroll_content_widget.setLayout(self.items_layout)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Data source: train_config.sample_configs (List[SampleConfig])
        # Loading is now handled by ConfigListBase's __init__ if external.
        # self._load_samples_from_config() # This logic is now in ConfigListBase
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_content_widget.setLayout(self.items_layout)
        
        # Data source: train_config.sample_configs (List[SampleConfig])
        # This matches how other ConfigList-derived tabs might work if their data is part of TrainConfig
        self._load_samples_from_config()
        self.refresh_list_display()

    def _load_samples_from_config(self):
        if not hasattr(self.train_config, 'sample_configs') or \
           not isinstance(self.train_config.sample_configs, list):
            self.train_config.sample_configs = []

        temp_samples = []
        for i, sample_data in enumerate(self.train_config.sample_configs):
            if isinstance(sample_data, dict):
                try:
                    temp_samples.append(SampleConfig(**sample_data))
                except Exception as e:
                    print(f"Error converting sample data to SampleConfig for item {i}: {e}")
            elif isinstance(sample_data, SampleConfig):
                temp_samples.append(sample_data)
        self.train_config.sample_configs = temp_samples

    # _save_samples_config is effectively replaced by ConfigListBase._save_items_to_file
    # def _save_samples_config(self):
    #     print("SamplingTab: _save_samples_config called (placeholder)")

    # on_add_new_element is inherited from ConfigListBase and calls create_new_element,
    # appends to the list, calls refresh_list_display, and _save_items_to_file.

    def refresh_list_display(self): # This is called by ConfigListBase methods
        self._clear_layout(self.items_layout)
        managed_list = self._get_managed_list() # Get from ConfigListBase
        if managed_list:
            for i, sample_data_obj in enumerate(managed_list):
                if isinstance(sample_data_obj, SampleConfig): # Ensure it's the correct type
                    widget = self.create_widget(sample_data_obj, i)
                    self.items_layout.addWidget(widget)
        self.items_layout.addStretch(1) 

    def create_widget(self, element_data: SampleConfig, index: int) -> SampleWidget:
        # element_data is already a SampleConfig instance due to ConfigListBase._load_items_from_file
        widget = SampleWidget(element_data, index, self.scroll_content_widget)
        widget.open_requested.connect(self.open_element_window_slot)
        widget.remove_requested.connect(self.remove_element_slot)
        widget.clone_requested.connect(self.clone_element_slot)
        widget.save_requested.connect(self.save_config_slot) # Connect to save the main config
        return widget

    def create_new_element(self) -> Dict[str, Any]:
        return SampleConfig.default_values().to_dict()

    @Slot(int, object)
    def open_element_window_slot(self, index: int, element_ui_state: UIState):
        # sample_data = self.train_config.sample_configs[index]
        # TODO: Refactor SampleParamsWindow to QDialog and show it
        # window = SampleParamsWindow(self, sample_data, element_ui_state) # self is QWidget parent
        # window.exec()
        print(f"TODO: Open SampleParamsWindow for element at index {index}")
        # After dialog:
        # self.refresh_list_display() # Or update specific widget
        # self._save_samples_config()

    @Slot(int)
    def remove_element_slot(self, index: int):
        # remove_element_slot is inherited from ConfigListBase and calls _save_items_to_file
        super().remove_element_slot(index)

    @Slot(int) # Overriding to ensure no randomize_callback is passed, as SampleWidget doesn't use one
    def clone_element_slot(self, index: int): 
        super().clone_element_slot(index, randomize_callback=None) # Call base with None callback

    # save_config_slot is inherited from ConfigListBase and calls _save_items_to_file

    def refresh_ui(self): # Called by TrainUI's load_preset
        # If externally managed, loading happens in __init__ or if file path changes.
        # For preset loads, we need to ensure the internal list (train_config.sample_configs)
        # is up-to-date from the main train_config, then refresh display.
        if self._is_externally_managed():
            self._load_items_from_file() # This reloads from file and refreshes display
        else:
            # If not external, assume train_config.sample_configs was updated by preset load
            # and just refresh the display from it.
            self._load_samples_from_config() # Ensure items are SampleConfig instances
            self.refresh_list_display()
