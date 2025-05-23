import webbrowser
from typing import Callable # For type hinting

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QScrollArea, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox, QCheckBox, QSizePolicy, QHBoxLayout,
    QSpacerItem, QTextEdit # Added QTextEdit
)
from PySide6.QtCore import Qt
import modules.util.ui.qt_components as qt_comps # Import new shared components

from modules.util.config.TrainConfig import TrainConfig
from modules.util.enum.CloudAction import CloudAction
from modules.util.enum.CloudFileSync import CloudFileSync
from modules.util.enum.CloudType import CloudType
from modules.util.ui.UIState import UIState
# import customtkinter as ctk # Removed
# from modules.util.ui import components # Removed

class CloudTab(QWidget):
    def __init__(self, train_config: TrainConfig, ui_state: UIState, parent_train_ui, parent_qt_widget: QWidget = None):
        super().__init__(parent_qt_widget)

        self.train_config = train_config
        self.ui_state = ui_state
        self.parent_train_ui = parent_train_ui # Reference to the main TrainUI window
        self.reattach = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.main_layout.addWidget(self.scroll_area)

        self.scroll_content_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_content_widget)

        self.grid_layout = QGridLayout(self.scroll_content_widget)
        # Column stretches based on original ctk code (0,1,0,1,0,1)
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_layout.setColumnStretch(3, 1)
        self.grid_layout.setColumnStretch(5, 1)

        self.gpu_types_combo = None # To store reference to the GPU types combobox

        self._populate_ui()

    # --- Temporary Helper Methods have been removed. Using qt_components now. ---

    def _create_options_adv_ui_element(self, parent_widget: QWidget, ui_state_key: str, items: list[tuple[str,Any]], 
                                        tooltip: str = None, command: Callable = None, adv_command: Callable = None) -> QWidget:
        """
        Custom helper for options_adv. Creates a QComboBox and a "..." QPushButton.
        Uses direct QComboBox creation and binding, similar to qt_comps.create_options_kv structure.
        """
        widget = QWidget(parent_widget)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0); layout.setSpacing(5)

        combo = QComboBox(widget)
        if tooltip: combo.setToolTip(tooltip)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        current_val = self.ui_state.get_var(ui_state_key)
        selected_idx = 0
        for idx, (text, data) in enumerate(items): # items are (display_text, data_value)
            combo.addItem(text, userData=data)
            if data == current_val: selected_idx = idx
        if combo.count() > 0 : combo.setCurrentIndex(selected_idx)

        def on_index_changed(idx):
            if idx >=0:
                data_val = combo.itemData(idx)
                self.ui_state.set_var(ui_state_key, data_val)
                if command: command(data_val)
        combo.currentIndexChanged.connect(on_index_changed)
        
        def update_combo_from_state(new_data_value: Any):
            for i in range(combo.count()):
                if combo.itemData(i) == new_data_value:
                    if combo.currentIndex() != i: combo.setCurrentIndex(i)
                    return
            if combo.count() > 0 and combo.currentIndex() != 0 : pass
        self.ui_state.track_variable(ui_state_key, update_combo_from_state)
        
        layout.addWidget(combo)

        adv_button = qt_comps.create_button(widget, "...", adv_command, fixed_width=30)
        layout.addWidget(adv_button)
        
        if ui_state_key == "cloud.gpu_type": 
            self.gpu_types_combo = combo
            if not self.gpu_types_combo.count(): # Initial placeholder if items were empty
                 self.gpu_types_combo.addItem("<Click ... to Load>")
        return widget

    def _populate_ui(self):
        layout = self.grid_layout
        content_widget = self.scroll_content_widget
        row = 0

        # Group 1 (Column 0 & 1)
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.enabled", "Enabled", "Enable cloud training"), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "cloud.type", [("RUNPOD", CloudType.RUNPOD), ("LINUX", CloudType.LINUX)], "Type", "Choose LINUX or RUNPOD."), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "cloud.file_sync", [("NATIVE_SCP", CloudFileSync.NATIVE_SCP), ("FABRIC_SFTP", CloudFileSync.FABRIC_SFTP)], "File Sync Method", "NATIVE_SCP or FABRIC_SFTP."), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "secrets.cloud.api_key", "API Key", "Cloud service API key for RUNPOD."), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "secrets.cloud.host", "Hostname", "SSH server hostname or IP."), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "secrets.cloud.port", "Port", "SSH server port.", value_type=int), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "secrets.cloud.user", "User", "SSH username (e.g., 'root' for RUNPOD)."), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "secrets.cloud.id", "Cloud ID", "RUNPOD Cloud ID."), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.tensorboard_tunnel", "Tensorboard TCP Tunnel", "Tunnel to remote tensorboard instead of local."), row, 0, 1, 2); row+=1
        
        # Group 2 (Column 2 & 3)
        row_col2 = 1 
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "cloud.remote_dir", "Remote Directory", "Directory on cloud for file exchange."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "cloud.onetrainer_dir", "OneTrainer Directory", "Directory for OneTrainer on cloud."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "cloud.huggingface_cache_dir", "Huggingface Cache Dir", "Remote Huggingface cache."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.install_onetrainer", "Install OneTrainer", "Auto install OneTrainer if not found."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "cloud.install_cmd", "Install Command", "OneTrainer install command."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.update_onetrainer", "Update OneTrainer", "Update OneTrainer if it exists."), row_col2, 2, 1, 2); row_col2+=1

        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.detach_trainer", "Detach Remote Trainer", "Trainer keeps running if connection lost."), 8, 2, 1, 2) 

        # Reattach frame
        layout.addWidget(qt_comps.create_label(content_widget, "Reattach ID", "ID of running trainer to reattach to."), 9, 2)
        reattach_frame = QFrame(content_widget); reattach_layout = QHBoxLayout(reattach_frame); reattach_layout.setContentsMargins(0,0,0,0)
        reattach_entry_container = qt_comps.create_entry(reattach_frame, self.ui_state, "cloud.run_id", label_text=None, placeholder_text="ID")
        if reattach_entry_container.layout() and isinstance(reattach_entry_container.layout().itemAt(0).widget(), QLineEdit): # Assuming label_on_left=False (default)
             reattach_entry_container.layout().itemAt(0).widget().setFixedWidth(80) # Set fixed width on QLineEdit
        reattach_layout.addWidget(reattach_entry_container)
        reattach_layout.addWidget(qt_comps.create_button(reattach_frame, "Reattach now", self.__reattach))
        reattach_layout.addStretch(1)
        layout.addWidget(reattach_frame, 9, 3)

        row_col2 = 11 
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.download_samples", "Download Samples", "Download samples to local machine."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.download_output_model", "Download Output Model", "Download final model after training."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.download_saves", "Download Saved Checkpoints", "Download automatic checkpoints."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.download_backups", "Download Backups", "Download backups."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.download_tensorboard", "Download Tensorboard Logs", "Download TensorBoard event logs."), row_col2, 2, 1, 2); row_col2+=1
        layout.addWidget(qt_comps.create_switch(content_widget, self.ui_state, "cloud.delete_workspace", "Delete Remote Workspace", "Delete cloud workspace after training."), row_col2, 2, 1, 2)

        # Group 3 (Column 4 & 5)
        row_col4 = 1
        layout.addWidget(qt_comps.create_label(content_widget, "Create cloud via API", "Auto-create RUNPOD instance if ID/Host empty."), row_col4, 4)
        create_frame = QFrame(content_widget); create_layout = QHBoxLayout(create_frame); create_layout.setContentsMargins(0,0,0,0)
        create_layout.addWidget(qt_comps.create_switch(create_frame, self.ui_state, "cloud.create", ""))
        create_layout.addWidget(qt_comps.create_button(create_frame, "Create cloud via website", self.__create_cloud))
        create_layout.addStretch(1)
        layout.addWidget(create_frame, row_col4, 5); row_col4+=1

        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "cloud.name", "Cloud Name", "Name of new cloud instance."), row_col4, 4, 1, 2); row_col4+=1
        layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "cloud.sub_type", [("", ""), ("Community", "COMMUNITY"), ("Secure", "SECURE")], "Type (RunPod)", "RunPod cloud type (Community/Secure)."), row_col4, 4, 1, 2); row_col4+=1
        
        layout.addWidget(qt_comps.create_label(content_widget, "GPU (RunPod)", "Select GPU type (needs API key)."), row_col4, 4)
        layout.addWidget(self._create_options_adv_ui_element(content_widget, "cloud.gpu_type", [("", "")], adv_command=self.__set_gpu_types), row_col4, 5); row_col4+=1
        
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "cloud.volume_size", "Volume Size (GB)", "Storage volume size (not network volume).", value_type=int), row_col4, 4, 1, 2); row_col4+=1
        layout.addWidget(qt_comps.create_entry(content_widget, self.ui_state, "cloud.min_download", "Min Download (Mbps)", "Minimum download speed of cloud.", value_type=int), row_col4, 4, 1, 2); row_col4+=1
        
        row_col4+=1 # Spacer row
        
        actions = [("None", CloudAction.NONE), ("Stop", CloudAction.STOP), ("Delete", CloudAction.DELETE)]
        layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "cloud.on_finish", actions, "Action on Finish", "Action when training finishes."), row_col4, 4, 1, 2); row_col4+=1
        layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "cloud.on_error", actions, "Action on Error", "Action if training errors."), row_col4, 4, 1, 2); row_col4+=1
        layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "cloud.on_detached_finish", actions, "Action on Detached Finish", "Action if detached and finishes."), row_col4, 4, 1, 2); row_col4+=1
        layout.addWidget(qt_comps.create_options_kv(content_widget, self.ui_state, "cloud.on_detached_error", actions, "Action on Detached Error", "Action if detached and errors."), row_col4, 4, 1, 2)

        self.grid_layout.setRowStretch(max(row, row_col2, row_col4) + 1, 1)


    def __set_gpu_types(self):
        if not self.gpu_types_combo: return
        self.gpu_types_combo.clear()
        if self.train_config.cloud.type == CloudType.RUNPOD:
            try:
                import runpod
                runpod.api_key = self.train_config.secrets.cloud.api_key
                if not runpod.api_key:
                    print("RunPod API key is missing. Cannot fetch GPU types.") # Or show in a status bar
                    self.gpu_types_combo.addItem("<API Key Missing>")
                    return
                gpus = runpod.get_gpus()
                for gpu in gpus:
                    self.gpu_types_combo.addItem(gpu['id'], userData=gpu['id'])
            except ImportError:
                print("RunPod library not installed.")
                self.gpu_types_combo.addItem("<RunPod Lib Missing>")
            except Exception as e:
                print(f"Error fetching RunPod GPUs: {e}")
                self.gpu_types_combo.addItem("<Error Fetching>")
        else:
            self.gpu_types_combo.addItem("<N/A for Linux>")


    def __reattach(self):
        self.reattach = True
        try:
            if self.parent_train_ui and hasattr(self.parent_train_ui, 'start_training'):
                self.parent_train_ui.start_training()
            else:
                print("Error: Cannot call start_training on parent_train_ui.")
        finally:
            self.reattach = False

    def __create_cloud(self):
        if self.train_config.cloud.type == CloudType.RUNPOD:
            webbrowser.open("https://www.runpod.io/console/deploy?template=1a33vbssq9&type=gpu", new=0, autoraise=False)
            
    # Public method for TrainUI to call if needed
    def refresh_ui(self): # For example, if API key changes, might need to refresh GPU list
        self._populate_ui() # Re-populating might be too much, selective update is better
        self.__set_gpu_types() # Specifically refresh GPU types if relevant state changes
