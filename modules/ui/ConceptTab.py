import os
import pathlib
from typing import List, Dict, Any # For type hinting

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QPushButton, QFrame,
    QSizePolicy, QApplication, QCheckBox # QApplication for clipboard
)
from PySide6.QtGui import QPixmap, QPainter, QMouseEvent, QBrush, QColor, QImage # QImage for PIL conversion
from PySide6.QtCore import Qt, Signal, Slot # Signal and Slot
import modules.util.ui.qt_components as qt_comps 

from modules.ui.ConceptWindow import ConceptWindow # Import refactored dialog
from modules.ui.ConfigListBase import ConfigListBase 
from modules.util import path_util
from modules.util.config.ConceptConfig import ConceptConfig
from modules.util.config.TrainConfig import TrainConfig
from modules.util.image_util import load_image
from modules.util.ui.UIState import UIState # Assuming UIState can be used as is or adapted

from PIL import Image
from PIL.ImageQt import ImageQt # For PIL to QImage conversion

class ConceptWidget(QFrame):
    # Define signals for widget interactions
    open_requested = Signal(int, tuple) # index, ui_state_tuple
    remove_requested = Signal(int)      # index
    clone_requested = Signal(int, object)       # index, callback
    save_requested = Signal()           # To notify parent to save overall config

    def __init__(self, concept_data: ConceptConfig, index: int, parent: QWidget = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("ConceptWidgetFrame")
        # self.setFixedSize(160, 200) # Adjusted size for a bit more space
        self.setFixedWidth(160)
        self.setFixedHeight(200)


        self.concept_data = concept_data
        self.index = index
        
        # UIState instances for this specific concept widget
        # These assume ConceptConfig fields are directly accessible.
        # If UIState needs a parent that is a Ctk object, this will need adaptation.
        # For now, passing None as parent to UIState, assuming it can operate for data holding.
        self.ui_state = UIState(None, self.concept_data) 
        self.image_ui_state = UIState(None, self.concept_data.image)
        self.text_ui_state = UIState(None, self.concept_data.text)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5,5,5,5)
        main_layout.setSpacing(5)

        # Image display
        self.image_label = QLabel()
        self.image_label.setFixedSize(150, 150)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;") # Simple border
        main_layout.addWidget(self.image_label)
        self.image_label.mousePressEvent = self._on_image_click

        # Name label
        self.name_label = QLabel(self._get_display_name())
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        main_layout.addWidget(self.name_label)
        
        # Controls layout (buttons, switch)
        controls_layout = QHBoxLayout()
        
        self.clone_button = QPushButton("+")
        self.clone_button.setFixedSize(25,20)
        self.clone_button.setToolTip("Clone Concept")
        self.clone_button.clicked.connect(self._on_clone_click)
        controls_layout.addWidget(self.clone_button)

        self.remove_button = QPushButton("X")
        self.remove_button.setFixedSize(25,20)
        self.remove_button.setToolTip("Remove Concept")
        self.remove_button.setStyleSheet("QPushButton { color: white; background-color: #C00000; }")
        self.remove_button.clicked.connect(self._on_remove_click)
        controls_layout.addWidget(self.remove_button)

        controls_layout.addStretch(1) # Push buttons to left, switch to right

        # Use qt_comps.create_switch for the enabled checkbox
        # It returns a QCheckBox. The label text for create_switch is the checkbox text itself.
        self.enabled_checkbox_widget = qt_comps.create_switch(
            parent_widget=self, # Parent for the checkbox itself
            ui_state=self.ui_state, 
            key_path="enabled", 
            label_text="", # Text is usually next to checkbox, here it's on the button
            tooltip="Enable/Disable this concept"
        )
        # The original UI had a QPushButton styled as a switch.
        # qt_comps.create_switch returns a QCheckBox.
        # For visual consistency with the original (button-like switch):
        # We can keep the QPushButton and manually bind it, or adapt create_switch,
        # or accept QCheckBox. For now, let's use QCheckBox and adjust if needed.
        # If we want the button style, we'd have to manually connect:
        # self.enabled_button = QPushButton(...)
        # self.enabled_button.setCheckable(True) ... then connect toggled to ui_state.set_var
        # and ui_state.track_variable to update button text/style.
        # For simplicity with qt_comps, let's use the QCheckBox it provides.
        # The "On"/"Off" text is not part of QCheckBox text directly.
        # We'll use a simple QCheckBox and its check state.
        
        # Let's simplify: Use QCheckBox from qt_comps, text appears next to it.
        # If custom text "On/Off" on a button is strictly needed, qt_comps.create_switch might need an option
        # or we do it manually here.
        # For now, using the standard QCheckBox behavior from the helper:
        self.enabled_checkbox_real = qt_comps.create_switch(
            parent_widget=self, 
            ui_state=self.ui_state,
            key_path="enabled",
            label_text="En", # Short label for the checkbox
            tooltip="Enable/Disable this concept"
        )
        # Connect the save_requested signal if the switch itself should trigger a full config save
        # self.enabled_checkbox_real.toggled.connect(self.save_requested.emit) # Already handled by create_switch calling set_var

        controls_layout.addWidget(self.enabled_checkbox_real)
        
        main_layout.addLayout(controls_layout)
        self.setLayout(main_layout)

        self.configure_element() # Load initial image and name

    def _on_image_click(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            ui_state_tuple = (self.ui_state, self.image_ui_state, self.text_ui_state)
            self.open_requested.emit(self.index, ui_state_tuple)

    def _on_remove_click(self):
        self.remove_requested.emit(self.index)

    def _on_clone_click(self):
        self.clone_requested.emit(self.index, self.__randomize_seed)

    def _on_enabled_toggle(self, checked: bool): # This is connected to the QPushButton if used
        self.ui_state.set_var("enabled", checked)
        # self._update_enabled_button_text() # If using QPushButton
        self.save_requested.emit() 

    # def _update_enabled_button_text(self): # Only needed if using QPushButton as toggle
    #     is_enabled = self.ui_state.get_var("enabled", False)
    #     self.enabled_checkbox.setText("On" if is_enabled else "Off")
    #     self.enabled_checkbox.setStyleSheet(
    #         "QPushButton { background-color: %s; color: white; }" % ('#00C000' if is_enabled else '#808080')
    #     )

    def __randomize_seed(self, concept_config: ConceptConfig) -> ConceptConfig:
        # This method is passed as a callback, so it operates on the passed config
        concept_config.seed = ConceptConfig.default_values().seed 
        return concept_config

    def _get_display_name(self) -> str:
        name = self.ui_state.get_var("name", "")
        path = self.ui_state.get_var("path", "")
        if name: return name
        if path: return os.path.basename(path)
        return "<Unnamed Concept>"

    def configure_element(self): # Called to update widget from its data
        self.name_label.setText(self._get_display_name())
        # self._update_enabled_button_text() # If using QPushButton for enabled status
        # QCheckBox updates its text/state via UIState.track_variable inside qt_comps.create_switch

        try:
            pil_image = self.__get_preview_image()
            if pil_image:
                # Convert PIL Image to QImage then to QPixmap
                q_image = ImageQt(pil_image)
                pixmap = QPixmap.fromImage(q_image)
                self.image_label.setPixmap(pixmap.scaled(
                    self.image_label.width(), self.image_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self.image_label.setText("No Preview")
        except Exception as e:
            print(f"Error loading preview for concept {self.index}: {e}")
            self.image_label.setText("Error")


    def __get_preview_image(self) -> Image.Image | None:
        preview_path_str = "resources/icons/icon.png" # Default
        concept_path_str = self.ui_state.get_var("path", "")
        include_subdirs = self.ui_state.get_var("include_subdirectories", False)

        glob_pattern = "**/*.*" if include_subdirs else "*.*"

        if concept_path_str and os.path.isdir(concept_path_str):
            try:
                concept_path = pathlib.Path(concept_path_str)
                for path_obj in concept_path.glob(glob_pattern):
                    if path_obj.is_file() and path_util.is_supported_image_extension(path_obj.suffix) \
                            and not path_obj.name.endswith("-masklabel.png"):
                        preview_path_str = str(path_obj.resolve())
                        break
            except Exception as e:
                print(f"Error searching for preview in {concept_path_str}: {e}")
        elif concept_path_str and os.path.isfile(concept_path_str) and path_util.is_supported_image_extension(pathlib.Path(concept_path_str).suffix):
             preview_path_str = concept_path_str


        if not os.path.exists(preview_path_str): # Fallback if chosen path doesn't exist
            preview_path_str = "resources/icons/icon.png" 
            if not os.path.exists(preview_path_str): return None


        try:
            image = load_image(preview_path_str, convert_mode="RGBA")
            if image:
                size = min(image.width, image.height)
                image = image.crop((
                    (image.width - size) // 2, (image.height - size) // 2,
                    (image.width - size) // 2 + size, (image.height - size) // 2 + size,
                ))
                image = image.resize((150, 150), Image.Resampling.LANCZOS)
            return image
        except Exception as e:
            print(f"Error processing image {preview_path_str}: {e}")
            return None


class ConceptTab(ConfigListBase):
    def __init__(self, train_config: TrainConfig, ui_state: UIState, parent: QWidget = None):
        # Parameters for ConfigListBase (some from original ConceptTab __init__)
        self.config_dir = "training_concepts" # Example, adjust as needed
        self.default_config_name = "concepts.json"
        self.attr_name = "concept_file_name" # Attribute in train_config for the concepts file
        
        super().__init__(parent, add_button_text="Add Concept")

        self.train_config = train_config
        self.ui_state = ui_state # Main UIState from TrainUI

        # The ConfigListBase creates self.scroll_content_widget. We set its layout here.
        self.items_layout = QGridLayout(self.scroll_content_widget)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_content_widget.setLayout(self.items_layout)
        
        # Load initial concepts
        self._load_concepts_from_config() # Or however concepts are initially loaded/stored
        self.refresh_list_display()


    def _load_concepts_from_config(self):
        # This replaces the file loading logic that was part of the original ConfigList.
        # For now, we assume concepts are directly in train_config.concepts (List[ConceptConfig])
        # If they are in an external file, that file needs to be loaded here.
        # The original ConfigList had `from_external_file=True`.
        
        # Placeholder: If concepts are in an external file defined by `train_config.concept_file_name`
        # concept_file_path = getattr(self.train_config, self.attr_name, self.default_config_name)
        # if concept_file_path and os.path.exists(concept_file_path):
        #     try:
        #         with open(concept_file_path, 'r') as f:
        #             concepts_data_list = json.load(f)
        #             self.train_config.concepts = [ConceptConfig(**data) for data in concepts_data_list]
        #     except Exception as e:
        #         print(f"Error loading concepts from {concept_file_path}: {e}")
        #         self.train_config.concepts = [] # Ensure it's a list
        # else:
        #     self.train_config.concepts = []

        # Ensure train_config.concepts is a list, even if empty
        if not hasattr(self.train_config, 'concepts') or not isinstance(self.train_config.concepts, list):
            self.train_config.concepts = []
        
        # Convert dicts to ConceptConfig instances if necessary (e.g., after JSON load)
        temp_concepts = []
        for i, concept_data in enumerate(self.train_config.concepts):
            if isinstance(concept_data, dict):
                try:
                    temp_concepts.append(ConceptConfig(**concept_data))
                except Exception as e:
                    print(f"Error converting concept data to ConceptConfig for item {i}: {e}")
            elif isinstance(concept_data, ConceptConfig):
                temp_concepts.append(concept_data)
        self.train_config.concepts = temp_concepts


    def _save_concepts_to_config(self):
        # Placeholder for saving logic if concepts are in an external file
        # concept_file_path = getattr(self.train_config, self.attr_name, self.default_config_name)
        # concepts_data_list = [c.to_dict() for c in self.train_config.concepts] # Assuming ConceptConfig has to_dict()
        # try:
        #     with open(concept_file_path, 'w') as f:
        #         json.dump(concepts_data_list, f, indent=4)
        # except Exception as e:
        #     print(f"Error saving concepts to {concept_file_path}: {e}")
        print("ConceptTab: _save_concepts_to_config called (placeholder)")
        # For now, changes are directly on self.train_config.concepts


    @Slot()
    def on_add_new_element(self):
        new_concept_data = self.create_new_element()
        self.train_config.concepts.append(ConceptConfig(**new_concept_data))
        self._save_concepts_to_config() # Save after adding
        self.refresh_list_display()

    def refresh_list_display(self):
        self._clear_layout(self.items_layout)
        
        cols = 6 # Number of columns for the grid
        for i, concept_data_obj in enumerate(self.train_config.concepts):
            widget = self.create_widget(concept_data_obj, i)
            row = i // cols
            col = i % cols
            self.items_layout.addWidget(widget, row, col)
        
        # Add stretch to fill remaining space if items don't fill the last row/column
        self.items_layout.setRowStretch(self.items_layout.rowCount(), 1)
        self.items_layout.setColumnStretch(self.items_layout.columnCount(), 1)


    def create_widget(self, element_data: ConceptConfig, index: int) -> ConceptWidget:
        widget = ConceptWidget(element_data, index)
        # Connect signals from ConceptWidget to slots in ConceptTab
        widget.open_requested.connect(self.open_element_window_slot)
        widget.remove_requested.connect(self.remove_element_slot)
        widget.clone_requested.connect(self.clone_element_slot)
        widget.save_requested.connect(self.save_config_slot) # To save the whole list if an element changes
        return widget

    def create_new_element(self) -> Dict[str, Any]: # Returns a dict that can init ConceptConfig
        return ConceptConfig.default_values().to_dict() # Assuming ConceptConfig has to_dict

    @Slot(int, tuple)
    def open_element_window_slot(self, index: int, ui_state_tuple: tuple):
        if 0 <= index < len(self.train_config.concepts):
            concept_data = self.train_config.concepts[index]
            ui_state_concept_root, ui_state_concept_image, ui_state_concept_text = ui_state_tuple
            
            try:
                dialog = ConceptWindow(
                    parent_widget=self, # self is ConceptTab (a QWidget)
                    concept=concept_data,
                    ui_state_concept_root=ui_state_concept_root,
                    ui_state_concept_image=ui_state_concept_image,
                    ui_state_concept_text=ui_state_concept_text
                )
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    # ConceptWindow directly modifies the ConceptConfig object via UIState.
                    # We need to refresh the specific widget in the list and save if external.
                    self.refresh_list_display() # Could optimize to refresh only one widget
                    self._save_items_to_file() # Save if externally managed
                else: # Rejected (Cancelled) - Re-fetch data for that item in case UIState made live changes
                    if self._is_externally_managed(): # If external, means it might have changed before cancel
                        self._load_items_from_file() # This reloads all, could be optimized
                    self.refresh_list_display()


            except Exception as e:
                print(f"Error opening ConceptWindow for element at index {index}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"Invalid index {index} for opening ConceptWindow.")


    @Slot(int)
    def remove_element_slot(self, index: int):
        if 0 <= index < len(self.train_config.concepts):
            del self.train_config.concepts[index]
            self._save_concepts_to_config()
            self.refresh_list_display() # Re-render the whole list

    @Slot(int, object)
    def clone_element_slot(self, index: int, randomize_callback: Callable):
        if 0 <= index < len(self.train_config.concepts):
            original_concept = self.train_config.concepts[index]
            cloned_data = original_concept.to_dict() # Assuming ConceptConfig has to_dict()
            
            # Create new ConceptConfig instance for the clone
            cloned_concept = ConceptConfig(**cloned_data)

            if randomize_callback:
                cloned_concept = randomize_callback(cloned_concept)
            
            self.train_config.concepts.insert(index + 1, cloned_concept)
            self._save_concepts_to_config()
            self.refresh_list_display()

    @Slot()
    def save_config_slot(self):
        # This is called when a sub-widget (ConceptWidget's enabled switch) requests a save
        self._save_concepts_to_config()
        # Optionally, could also emit a signal to TrainUI if the main config file needs saving

    # Public method for TrainUI to call if needed (e.g., after loading a preset)
    def refresh_from_train_config(self):
        self._load_concepts_from_config()
        self.refresh_list_display()
