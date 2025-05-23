import json
import os
import traceback
import webbrowser
from collections.abc import Callable
from contextlib import suppress
from typing import List, Tuple # For type hinting

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QComboBox, QPushButton, QInputDialog, QMessageBox,
    QSizePolicy,
    QApplication # For QInputDialog, though not used in this file directly
)
from PySide6.QtCore import Qt
import modules.util.ui.qt_components as qt_comps # Import new shared components

from modules.util import path_util
from modules.util.config.SecretsConfig import SecretsConfig
from modules.util.config.TrainConfig import TrainConfig
from modules.util.enum.ModelType import ModelType
from modules.util.enum.TrainingMethod import TrainingMethod
from modules.util.optimizer_util import change_optimizer
from modules.util.path_util import write_json_atomic
from modules.util.ui.UIState import UIState # Assuming UIState can be used as is or adapted
# from modules.util.ui import components, dialogs # Removed

class TopBar(QFrame):
    def __init__(
            self,
            master_widget: QWidget, # Renamed master to master_widget to avoid QWidget.master() conflict
            train_config: TrainConfig,
            ui_state: UIState, # This is the main UIState from TrainUI
            change_model_type_callback: Callable[[ModelType], None],
            change_training_method_callback: Callable[[TrainingMethod], None],
            load_preset_callback: Callable[[], None],
    ):
        super().__init__(master_widget)
        self.setObjectName("TopBarFrame")
        # self.setFrameShape(QFrame.Shape.StyledPanel) # Optional: add a border to see it

        self.train_config = train_config
        self.ui_state_train_config = ui_state # Main UIState for TrainConfig
        self.change_model_type_callback = change_model_type_callback
        self.change_training_method_callback = change_training_method_callback
        self.load_preset_callback = load_preset_callback

        self.presets_dir = "training_presets"
        os.makedirs(self.presets_dir, exist_ok=True)

        # Store the path to the currently selected config file.
        # UIState for this specific TopBar's state (like selected preset path)
        self.top_bar_internal_data = {"current_preset_path": path_util.canonical_join(self.presets_dir, "#.json")}
        self.ui_state_top_bar = UIState(None, self.top_bar_internal_data) # Parent None for this internal state

        self.available_presets: List[Tuple[str, str]] = [] # List of (display_name, file_path)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        layout.setSpacing(10)

        # App Title (simplified)
        app_title_label = qt_comps.create_label(self, "OneTrainer")
        app_title_label.setStyleSheet("font-weight: bold; font-size: 16pt;") # Keep custom styling
        layout.addWidget(app_title_label)

        # Configs Dropdown
        self.__load_available_config_names() # Populates self.available_presets first
        # qt_comps.create_options_kv returns a container QWidget (label + combo)
        # We need to extract the QComboBox if we want to call methods on it directly later (e.g. clear, addItem)
        # For now, assume the on_change_command is sufficient for preset loading.
        # The label "Preset:" will be part of the returned widget from create_options_kv.
        self.configs_dropdown_container = qt_comps.create_options_kv(
            parent_widget=self,
            ui_state=self.ui_state_top_bar,
            key_path="current_preset_path",
            items=self.available_presets,
            label_text="Preset:",
            on_change_command=self._on_preset_selected_by_path 
        )
        self.configs_dropdown = self.configs_dropdown_container.findChild(QComboBox) # Get the actual QComboBox
        if self.configs_dropdown: self.configs_dropdown.setMinimumWidth(150)
        layout.addWidget(self.configs_dropdown_container)
        
        # Save Button
        layout.addWidget(qt_comps.create_button(self, "Save Preset", self.__save_config_dialog, "Save the current configuration as a custom preset"))
        
        # Wiki Button
        layout.addWidget(qt_comps.create_button(self, "Wiki", self.open_wiki))

        layout.addStretch(1) # Spacer

        # Model Type Dropdown
        model_type_values = [
            ("Stable Diffusion 1.5", ModelType.STABLE_DIFFUSION_15), ("SD 1.5 Inpainting", ModelType.STABLE_DIFFUSION_15_INPAINTING),
            ("Stable Diffusion 2.0", ModelType.STABLE_DIFFUSION_20), ("SD 2.0 Inpainting", ModelType.STABLE_DIFFUSION_20_INPAINTING),
            ("Stable Diffusion 2.1", ModelType.STABLE_DIFFUSION_21),
            ("Stable Diffusion 3", ModelType.STABLE_DIFFUSION_3), ("Stable Diffusion 3.5", ModelType.STABLE_DIFFUSION_35),
            ("SD XL 1.0 Base", ModelType.STABLE_DIFFUSION_XL_10_BASE), ("SD XL 1.0 Inpainting", ModelType.STABLE_DIFFUSION_XL_10_BASE_INPAINTING),
            ("Wuerstchen v2", ModelType.WUERSTCHEN_2), ("Stable Cascade", ModelType.STABLE_CASCADE_1),
            ("PixArt Alpha", ModelType.PIXART_ALPHA), ("PixArt Sigma", ModelType.PIXART_SIGMA),
            ("Flux Dev", ModelType.FLUX_DEV_1), ("Flux Fill Dev", ModelType.FLUX_FILL_DEV_1),
            ("Sana", ModelType.SANA), ("Hunyuan Video", ModelType.HUNYUAN_VIDEO), ("HiDream Full", ModelType.HI_DREAM_FULL),
        ]
        self.model_type_dropdown_container = qt_comps.create_options_kv(
            parent_widget=self, ui_state=self.ui_state_train_config, key_path="model_type",
            items=model_type_values, label_text="Model Type:",
            on_change_command=self._on_model_type_changed_by_value
        )
        self.model_type_dropdown = self.model_type_dropdown_container.findChild(QComboBox)
        if self.model_type_dropdown: self.model_type_dropdown.setMinimumWidth(180)
        layout.addWidget(self.model_type_dropdown_container)

        # Training Method Dropdown
        # Initial items will be empty, populated by __create_training_method_dropdown_items
        self.training_method_dropdown_container = qt_comps.create_options_kv(
            parent_widget=self, ui_state=self.ui_state_train_config, key_path="training_method",
            items=[], label_text="Training Method:",
            on_change_command=self._on_training_method_changed_by_value
        )
        self.training_method_dropdown = self.training_method_dropdown_container.findChild(QComboBox)
        if self.training_method_dropdown: self.training_method_dropdown.setMinimumWidth(120)
        layout.addWidget(self.training_method_dropdown_container)
        self.__create_training_method_dropdown_items() # Initial population after creation


    def __load_available_config_names(self): # No change needed here
        self.available_presets = [("Default (Unsaved)", path_util.canonical_join(self.presets_dir, "#.json"))]
        if os.path.isdir(self.presets_dir):
            for path_str in os.listdir(self.presets_dir):
                if path_str.endswith(".json") and path_str != "#.json":
                    full_path = path_util.canonical_join(self.presets_dir, path_str)
                    name = os.path.splitext(path_str)[0]
                    self.available_presets.append((name, full_path))
            self.available_presets.sort(key=lambda x: x[0].lower() if x[0] != "Default (Unsaved)" else "")


    def __create_configs_dropdown_items(self):
        self.configs_dropdown.clear()
        current_path_to_select = self.ui_state_top_bar.get_var("current_preset_path")
        selected_idx = 0
        for idx, (name, path) in enumerate(self.available_presets):
            self.configs_dropdown.addItem(name, userData=path)
            if path == current_path_to_select:
                selected_idx = idx
        # This method is now primarily for populating self.available_presets.
        # The actual QComboBox population and selection is handled by qt_comps.create_options_kv
        # based on the ui_state_top_bar and its "current_preset_path" value.
        # However, qt_comps.create_options_kv doesn't re-fetch items if self.available_presets changes.
        # So, we need to update the items in the QComboBox if it's already created.
        if self.configs_dropdown:
            self.configs_dropdown.clear()
            current_path_to_select = self.ui_state_top_bar.get_var("current_preset_path")
            selected_idx = 0
            for idx, (name, path) in enumerate(self.available_presets):
                self.configs_dropdown.addItem(name, userData=path)
                if path == current_path_to_select:
                    selected_idx = idx
            if self.configs_dropdown.count() > 0:
                self.configs_dropdown.setCurrentIndex(selected_idx)


    def _on_preset_selected_by_path(self, selected_path: str): # Callback receives value now
        if selected_path:
            # UIState already updated by qt_comps.create_options_kv if key_path matches
            # self.ui_state_top_bar.set_var("current_preset_path", selected_path) # This is done by create_options_kv
            self.__load_current_config_file(selected_path)

    def _on_model_type_changed_by_value(self, model_type_val: ModelType): # Callback receives value
        if model_type_val:
            # UIState already updated by qt_comps.create_options_kv
            # self.ui_state_train_config.set_var("model_type", model_type_val) 
            self.change_model_type_callback(model_type_val) 
            self.__create_training_method_dropdown_items() 

    def _on_training_method_changed_by_value(self, method_val: TrainingMethod): # Callback receives value
        if method_val is not None: 
             # UIState already updated by qt_comps.create_options_kv
             # self.ui_state_train_config.set_var("training_method", method_val)
             self.change_training_method_callback(method_val)


    def __create_training_method_dropdown_items(self):
        if not self.training_method_dropdown: return # Check if widget exists
        
        # Block signals while repopulating to avoid triggering on_training_method_changed prematurely
        self.training_method_dropdown.blockSignals(True)
        self.training_method_dropdown.clear()
        current_model_type = self.ui_state_train_config.get_var("model_type")
        
        values: List[Tuple[str, TrainingMethod]] = []
        if current_model_type.is_stable_diffusion():
            values = [("Fine Tune", TrainingMethod.FINE_TUNE), ("LoRA", TrainingMethod.LORA),
                      ("Embedding", TrainingMethod.EMBEDDING), ("Fine Tune VAE", TrainingMethod.FINE_TUNE_VAE)]
        elif current_model_type.is_stable_diffusion_3() or \
             current_model_type.is_stable_diffusion_xl() or \
             current_model_type.is_wuerstchen() or \
             current_model_type.is_pixart() or \
             current_model_type.is_flux() or \
             current_model_type.is_sana() or \
             current_model_type.is_hunyuan_video() or \
             current_model_type.is_hi_dream():
            values = [("Fine Tune", TrainingMethod.FINE_TUNE), ("LoRA", TrainingMethod.LORA),
                      ("Embedding", TrainingMethod.EMBEDDING)]
        
        current_training_method = self.ui_state_train_config.get_var("training_method")
        selected_idx = -1 # Default to -1 if current method not in new list

        # If no specific training methods for this model type, or current is not compatible, reset to a default.
        if not values:
            self.ui_state_train_config.set_var("training_method", TrainingMethod.NONE) # Or some default
            self.change_training_method_callback(TrainingMethod.NONE)
            return # No items to add

        for idx, (text, val) in enumerate(values):
            self.training_method_dropdown.addItem(text, userData=val)
            if val == current_training_method:
                selected_idx = idx
        
        if selected_idx != -1:
            self.training_method_dropdown.setCurrentIndex(selected_idx)
        elif values: 
            self.training_method_dropdown.setCurrentIndex(0)
            # Update UIState directly if the first item is now selected due to no prior match
            # This will also trigger the on_change_command if not blocked, but we are setting it programmatically.
            new_method_val = values[0][1]
            self.ui_state_train_config.set_var("training_method", new_method_val) 
            # self.change_training_method_callback(new_method_val) # Let the ComboBox signal handle this if possible after unblocking
        else: 
            self.ui_state_train_config.set_var("training_method", TrainingMethod.NONE)
            # self.change_training_method_callback(TrainingMethod.NONE)
        
        self.training_method_dropdown.blockSignals(False)
        # Manually trigger callback if value changed programmatically and differed from original UIState value
        # Or rely on UIState.track_variable to update it if it changed.
        # For now, let's assume that if we set UIState above, the callback from create_options_kv will eventually fire
        # or the external UI will reflect the change. The main thing is that self.train_config is correct.
        # If setCurrentIndex doesn't trigger currentIndexChanged when signals are blocked, we might need to manually call.
        if selected_idx == -1 and values: # If we defaulted to first item
             self.change_training_method_callback(self.training_method_dropdown.itemData(0))


    def __save_to_file(self, name: str) -> str:
        safe_name = path_util.safe_filename(name)
        path = path_util.canonical_join(self.presets_dir, f"{safe_name}.json")
        write_json_atomic(path, self.train_config.to_settings_dict(secrets=False))
        return path

    def __save_secrets(self, path: str):
        write_json_atomic(path, self.train_config.secrets.to_dict())

    def open_wiki(self):
        webbrowser.open("https://github.com/Nerogar/OneTrainer/wiki", new=0, autoraise=False)

    def __save_new_config_action(self, name: str):
        if not name or name.startswith("#"):
            QMessageBox.warning(self, "Invalid Name", "Preset name cannot be empty or start with '#'.")
            return

        path = self.__save_to_file(name)
        is_new_config = name not in [item_name for item_name, item_path in self.available_presets]

        if is_new_config:
            self.available_presets.append((name, path))
            self.available_presets.sort(key=lambda x: x[0].lower() if x[0] != "Default (Unsaved)" else "")
        
        self.ui_state_top_bar.set_var("current_preset_path", path) # Update internal state
        self.__create_configs_dropdown_items() # Refresh dropdown to show new/select current

    def __save_config_dialog(self):
        current_preset_path = self.ui_state_top_bar.get_var("current_preset_path") # Path from UIState
        default_name = ""
        if current_preset_path and not current_preset_path.endswith("#.json"): # Ensure it's not the "Default (Unsaved)"
            default_name = os.path.splitext(os.path.basename(current_preset_path))[0]
        
        text, ok = QInputDialog.getText(self, "Save Preset", "Preset Name:", QLineEdit.QLineEdit.EchoMode.Normal, default_name)
        if ok and text:
            self.__save_new_config_action(text)

    def __load_current_config_file(self, filepath: str):
        try:
            basename = os.path.basename(filepath)
            is_built_in_preset = basename.startswith("#") and basename != "#.json" # Should not happen with new "Default"
            
            if not os.path.exists(filepath) and filepath.endswith("#.json"): # Handle "Default (Unsaved)"
                print("Loading default values (Unsaved preset).")
                self.train_config.from_dict(TrainConfig.default_values().to_dict()) # Reset to fresh defaults
            else:
                with open(filepath, "r") as f:
                    loaded_dict = json.load(f)
                
                default_config_instance = TrainConfig.default_values()
                if is_built_in_preset: # This case might be obsolete if "#.json" is the only special one
                    loaded_dict["__version"] = default_config_instance.config_version
                
                # Preserve secrets before loading, then re-apply if not in loaded_dict
                # This assumes secrets are global and not preset-specific unless explicitly included
                # current_secrets = self.train_config.secrets.to_dict()

                loaded_config_obj = default_config_instance.from_dict(loaded_dict) # This updates default_config_instance
                self.train_config.from_dict(loaded_config_obj.to_dict()) # Apply to main config

                # if "secrets" not in loaded_dict: # Re-apply global secrets if not in preset
                #     self.train_config.secrets.from_dict(current_secrets)


            # Try to load global secrets.json, should override anything from preset for safety
            global_secrets_path = "secrets.json"
            if os.path.exists(global_secrets_path):
                with suppress(FileNotFoundError, json.JSONDecodeError):
                    with open(global_secrets_path, "r") as f_secrets:
                        secrets_dict = json.load(f_secrets)
                        self.train_config.secrets.from_dict(secrets_dict)
            
            self.ui_state_train_config.update(self.train_config) # Update main UIState with loaded TrainConfig
            
            # Specific updates after loading
            optimizer_config = change_optimizer(self.train_config) # This might modify train_config
            self.ui_state_train_config.get_var("optimizer").update(optimizer_config)
            
            self.load_preset_callback() # Notify TrainUI to refresh tabs
            
            # Update ModelType and TrainingMethod dropdowns to reflect loaded config
            # current_model_type = self.train_config.model_type # Already set in self.train_config by from_dict
            # The qt_comps.create_options_kv should handle updating the dropdown via its track_variable
            # So, direct manipulation of self.model_type_dropdown.setCurrentIndex might not be needed here,
            # as UIState.update() should have triggered signals.
            # However, __create_training_method_dropdown_items IS needed as model_type changed.
            self.__create_training_method_dropdown_items() 
            
            # Ensure TopBar's own dropdowns reflect the new state from self.ui_state_train_config
            # This is now handled by the load_preset_callback calling self.update_from_main_config()

        except FileNotFoundError:
            # If #.json (Default) is selected and not found, it's not an error, it means load fresh defaults.
            if filepath.endswith("#.json"):
                print("Loading default values (Unsaved preset '#.json' not found, using fresh defaults).")
                self.train_config.from_dict(TrainConfig.default_values().to_dict())
                self.ui_state_train_config.update_target_object(self.train_config) # Notify UIState of new underlying object
                # Callbacks and dropdown updates
                optimizer_config = change_optimizer(self.train_config)
                self.ui_state_train_config.get_var("optimizer").update(optimizer_config) # This needs ui_state.set_var("optimizer.sub_field", val)
                self.load_preset_callback() 
                self.update_from_main_config() # Crucial to sync TopBar's own dropdowns
            else:
                QMessageBox.warning(self, "Load Error", f"Preset file not found: {filepath}")
        except Exception as e:
            print(traceback.format_exc())
            QMessageBox.critical(self, "Load Error", f"Error loading preset: {e}")


    def save_default(self):
        """Saves the current UI state as the default '#.json' preset and global 'secrets.json'."""
        default_preset_path = path_util.canonical_join(self.presets_dir, "#.json")
        self.__save_to_file("#") # Saves current train_config to '#.json'
        self.__save_secrets("secrets.json") # Saves current secrets to 'secrets.json'
        print(f"Default preset saved to {default_preset_path}")

    # Public method for TrainUI to call if UIState outside TopBar changes model_type or training_method
    def update_from_main_config(self):
        # The qt_comps helpers are now responsible for this via track_variable.
        # We just need to ensure the UIState has the correct values, and the helpers will update the widgets.
        # However, __create_training_method_dropdown_items might still be needed if model_type changes,
        # as it changes the *items* in the training_method_dropdown, not just the selected value.

        # Ensure ModelType dropdown reflects current state
        if self.model_type_dropdown: # Check if it's initialized
            current_model_type_val = self.ui_state_train_config.get_var("model_type")
            for i in range(self.model_type_dropdown.count()):
                if self.model_type_dropdown.itemData(i) == current_model_type_val:
                    if self.model_type_dropdown.currentIndex() != i:
                        self.model_type_dropdown.setCurrentIndex(i) # This will trigger its own update logic including training methods
                    else: # If model type hasn't changed, but training methods might need refresh due to other reasons (e.g. preset load)
                         self.__create_training_method_dropdown_items()
                    break
        
        # Ensure TrainingMethod dropdown reflects current state AFTER model type might have changed items
        if self.training_method_dropdown: # Check if it's initialized
            current_training_method_val = self.ui_state_train_config.get_var("training_method")
            for i in range(self.training_method_dropdown.count()):
                if self.training_method_dropdown.itemData(i) == current_training_method_val:
                    if self.training_method_dropdown.currentIndex() != i:
                        self.training_method_dropdown.setCurrentIndex(i)
                    break
        
        # Preset dropdown should be updated by its own UIState binding if current_preset_path changes
        # No need for manual update here unless self.available_presets changed and needs repopulation.
        # self.__create_configs_dropdown_items() # Call if self.available_presets could have changed
