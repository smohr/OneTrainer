from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QPushButton, QFrame, QHBoxLayout, QLabel,
    QFileDialog # For file dialogs if needed directly here, though subclasses might handle path selection
)
from PySide6.QtCore import Qt, Slot
import json
import os
from typing import List, Dict, Any, Callable, Optional, Type, TypeVar
from modules.util.config.BaseConfig import BaseConfig # For type hinting item creation

# Define a type variable for the config items, assuming they inherit from BaseConfig or are dicts
TConfigItem = TypeVar("TConfigItem")


class ConfigListBase(QWidget):
    def __init__(self, 
                 parent_widget: Optional[QWidget],
                 add_button_text: str = "Add New",
                 # For managing the list within train_config
                 train_config_main: Optional[Any] = None, # Main TrainConfig (or similar) instance
                 ui_state_main: Optional[Any] = None, # UIState for train_config_main
                 list_attr_name: Optional[str] = None, # e.g., "concepts", "sample_configs"
                 # For external file management
                 from_external_file_key_path: Optional[str] = None, # e.g., "concepts_use_external_file"
                 external_file_path_key_path: Optional[str] = None, # e.g., "concept_file_name"
                 default_external_filename: str = "list_config.json",
                 config_item_class: Optional[Type[TConfigItem]] = None # e.g., ConceptConfig, SampleConfig
                ):
        super().__init__(parent_widget)

        self.train_config_main = train_config_main
        self.ui_state_main = ui_state_main
        self.list_attr_name = list_attr_name
        self.from_external_file_key_path = from_external_file_key_path
        self.external_file_path_key_path = external_file_path_key_path
        self.default_external_filename = default_external_filename
        self.config_item_class = config_item_class # Used to recreate class instances from dicts

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1,1,1,1) # Small margins
        self.main_layout.setSpacing(5)

        # Optional: Header/Toolbar area
        self.toolbar_frame = QFrame()
        self.toolbar_layout = QHBoxLayout(self.toolbar_frame)
        self.toolbar_layout.setContentsMargins(0,0,0,0)
        self.main_layout.addWidget(self.toolbar_frame)

        self.add_button = QPushButton(add_button_text)
        self.add_button.clicked.connect(self.on_add_new_element) # To be implemented by subclass
        self.toolbar_layout.addWidget(self.add_button)
        self.toolbar_layout.addStretch(1) # Push button to the left

        # Scroll Area for list items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: 0px; }") # No border for scroll area itself
        self.main_layout.addWidget(self.scroll_area)

        self.scroll_content_widget = QWidget() # This widget will contain the actual list layout
        self.scroll_area.setWidget(self.scroll_content_widget)

        # This layout will hold the items (e.g., a QVBoxLayout for vertical list, QGridLayout for grid)
        # Subclasses must set this layout on self.scroll_content_widget
        self.items_layout = QVBoxLayout() # Default to QVBoxLayout, subclasses can change
        self.scroll_content_widget.setLayout(self.items_layout)
        
        # Ensure the target list attribute exists on train_config_main
        if self.train_config_main and self.list_attr_name and \
           not hasattr(self.train_config_main, self.list_attr_name):
            setattr(self.train_config_main, self.list_attr_name, [])

        if self._is_externally_managed():
            self._load_items_from_file()
        # refresh_list_display is usually called by subclass after data is ready

    def _get_managed_list(self) -> Optional[List[Any]]:
        if self.train_config_main and self.list_attr_name:
            return getattr(self.train_config_main, self.list_attr_name, None)
        return None

    def _set_managed_list(self, new_list: List[Any]):
        if self.train_config_main and self.list_attr_name:
            setattr(self.train_config_main, self.list_attr_name, new_list)
            # TODO: How to notify UIState that this part of train_config_main has changed?
            # If ui_state_main tracks the list object itself, it won't know its content changed.
            # If ui_state_main has a key path to this list, we could emit a signal for that key path.
            if self.ui_state_main and hasattr(self.ui_state_main, 'refresh_ui_for_key'):
                 self.ui_state_main.refresh_ui_for_key(self.list_attr_name)


    def _is_externally_managed(self) -> bool:
        if self.ui_state_main and self.from_external_file_key_path:
            return bool(self.ui_state_main.get_var(self.from_external_file_key_path, False))
        return False # Default to not externally managed if keys are not provided

    def _get_external_file_path(self) -> Optional[str]:
        if self.ui_state_main and self.external_file_path_key_path:
            filename = self.ui_state_main.get_var(self.external_file_path_key_path, self.default_external_filename)
            # Assuming filename might be relative to a config directory (e.g., self.config_dir from subclass)
            # For now, let's assume it's a full path or relative to cwd if not absolute.
            # Subclasses might need to override this to prepend their specific config_dir.
            if hasattr(self, 'config_dir') and not os.path.isabs(filename):
                 return os.path.join(getattr(self, 'config_dir'), filename)
            return filename
        return None

    def _load_items_from_file(self):
        if not self._is_externally_managed():
            return

        file_path = self._get_external_file_path()
        if not file_path or not os.path.exists(file_path):
            print(f"ConfigListBase: External file not found: {file_path}. Initializing empty list.")
            self._set_managed_list([])
            self.refresh_list_display() # Show empty list
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
            
            loaded_items = []
            if self.config_item_class:
                for item_data in data_list:
                    if isinstance(item_data, dict):
                        try:
                            # If config_item_class is a BaseConfig, it should handle **item_data
                            if issubclass(self.config_item_class, BaseConfig):
                                item = self.config_item_class() # Create instance
                                item.from_dict(item_data) # Populate from dict
                                loaded_items.append(item)
                            else: # If it's just a class that takes **kwargs
                                loaded_items.append(self.config_item_class(**item_data))
                        except Exception as e:
                            print(f"Error creating item of type {self.config_item_class.__name__} from data: {item_data}. Error: {e}")
                    else: # If data is not a dict, cannot create class instance
                        print(f"Skipping item, expected dict for {self.config_item_class.__name__}, got {type(item_data)}")
            else: # No class specified, load as dicts
                loaded_items = [item_data for item_data in data_list if isinstance(item_data, dict)]
            
            self._set_managed_list(loaded_items)
            print(f"ConfigListBase: Loaded {len(loaded_items)} items from {file_path}")

        except json.JSONDecodeError:
            print(f"ConfigListBase: Error decoding JSON from {file_path}. Initializing empty list.")
            self._set_managed_list([])
        except Exception as e:
            print(f"ConfigListBase: Error loading from {file_path}: {e}")
            self._set_managed_list([])
        
        self.refresh_list_display()


    def _save_items_to_file(self):
        if not self._is_externally_managed():
            return

        file_path = self._get_external_file_path()
        if not file_path:
            print("ConfigListBase: No external file path specified for saving.")
            return
        
        managed_list = self._get_managed_list()
        if managed_list is None:
            print("ConfigListBase: No list to save.")
            return

        # Convert items to dicts if they have a to_dict method
        data_list_to_save = []
        for item in managed_list:
            if hasattr(item, 'to_dict') and callable(getattr(item, 'to_dict')):
                data_list_to_save.append(item.to_dict())
            elif isinstance(item, dict): # Already a dict
                data_list_to_save.append(item)
            else:
                print(f"ConfigListBase: Cannot serialize item for saving (no to_dict method): {item}")
                # Optionally, skip or raise error

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_list_to_save, f, indent=4)
            print(f"ConfigListBase: Saved {len(data_list_to_save)} items to {file_path}")
        except Exception as e:
            print(f"ConfigListBase: Error saving to {file_path}: {e}")


    @Slot()
    def on_add_new_element(self):
        new_element_data = self.create_new_element() # Subclass provides dict or BaseConfig instance
        
        # Ensure new_element is of the correct type for the list
        if self.config_item_class and not isinstance(new_element_data, self.config_item_class):
            if isinstance(new_element_data, dict):
                try:
                    if issubclass(self.config_item_class, BaseConfig):
                        item = self.config_item_class()
                        item.from_dict(new_element_data)
                        new_element = item
                    else:
                        new_element = self.config_item_class(**new_element_data)
                except Exception as e:
                    print(f"Error converting new element data to {self.config_item_class.__name__}: {e}")
                    return
            else: # Cannot convert
                 print(f"New element type {type(new_element_data)} does not match expected {self.config_item_class.__name__}")
                 return

        managed_list = self._get_managed_list()
        if managed_list is not None:
            managed_list.append(new_element)
            self.refresh_list_display()
            self._save_items_to_file() 
        else:
            print("ConfigListBase: Cannot add element, list attribute not found on train_config.")


    def refresh_list_display(self): # Abstract method, to be implemented by subclass
        raise NotImplementedError("Subclasses must implement refresh_list_display")

    def create_widget(self, element_data: TConfigItem, index: int) -> QWidget: # Abstract
        raise NotImplementedError("Subclasses must implement create_widget")
    
    def create_new_element(self) -> Union[Dict[str, Any], TConfigItem]: # Abstract
        # Should return a dictionary or an instance of config_item_class for a new item
        raise NotImplementedError("Subclasses must implement create_new_element")


    @Slot(int) # Ensure slots are decorated if connected by name or for type safety
    def open_element_window_slot(self, index: int): 
        # Default implementation, subclasses can override if they have element windows
        print(f"ConfigListBase: open_element_window_slot called for index {index}, but not implemented.")
        pass

    @Slot(int)
    def remove_element_slot(self, index: int):
        managed_list = self._get_managed_list()
        if managed_list is not None and 0 <= index < len(managed_list):
            del managed_list[index]
            self.refresh_list_display()
            self._save_items_to_file()
        else:
            print(f"ConfigListBase: Invalid index {index} for remove_element_slot.")


    @Slot(int, object) # 'object' for optional callback
    def clone_element_slot(self, index: int, randomize_callback: Optional[Callable[[TConfigItem], TConfigItem]] = None):
        managed_list = self._get_managed_list()
        if managed_list is not None and 0 <= index < len(managed_list):
            original_item = managed_list[index]
            
            cloned_item_data: Dict[str,Any]
            if hasattr(original_item, 'to_dict') and callable(getattr(original_item, 'to_dict')):
                cloned_item_data = original_item.to_dict()
            elif isinstance(original_item, dict):
                cloned_item_data = original_item.copy() # Shallow copy for dicts
            else:
                print(f"ConfigListBase: Cannot clone item of type {type(original_item)}. Needs to_dict or be a dict.")
                return

            cloned_item: TConfigItem
            if self.config_item_class:
                if issubclass(self.config_item_class, BaseConfig):
                    item = self.config_item_class()
                    item.from_dict(cloned_item_data)
                    cloned_item = item
                else:
                    cloned_item = self.config_item_class(**cloned_item_data)
            else: # Assume it's a list of dicts
                cloned_item = cloned_item_data # type: ignore
            
            if randomize_callback:
                cloned_item = randomize_callback(cloned_item)
            
            managed_list.insert(index + 1, cloned_item)
            self.refresh_list_display()
            self._save_items_to_file()
        else:
            print(f"ConfigListBase: Invalid index {index} for clone_element_slot.")
        
    @Slot()
    def save_config_slot(self): 
        # This slot can be connected by child widgets if they want to trigger a save of the external file.
        self._save_items_to_file()

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    child_layout = item.layout()
                    if child_layout is not None:
                        self._clear_layout(child_layout)
