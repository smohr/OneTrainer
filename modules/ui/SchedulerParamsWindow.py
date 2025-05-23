from typing import List, Dict, Any, Callable, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QIcon

import modules.util.ui.qt_components as qt_comps
from modules.ui.ConfigListBase import ConfigListBase # Assuming this path is correct
from modules.util.config.TrainConfig import TrainConfig # For type hinting
from modules.util.enum.LearningRateScheduler import LearningRateScheduler
from modules.util.ui.ui_utils import get_icon_path
from modules.util.ui.UIState import UIState


class KvWidget(QFrame):
    """Widget for a single Key-Value pair, used in KvParams list."""
    remove_requested = Signal(int) # Signal to request removal, providing its index

    def __init__(self, element_data_dict: Dict[str, str], index: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel) # Add a bit of styling
        self.setObjectName("KvWidgetFrame")

        self.element_data_dict = element_data_dict # This is a dict like {"key": "k", "value": "v"}
        # UIState specifically for this dict element.
        # Pass None as parent to UIState as it's managed by the widget's lifecycle.
        self.ui_state_kv_pair = UIState(self.element_data_dict, self) 
        self.index = index

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2,2,2,2) # Minimal margins
        layout.setSpacing(5)

        # Remove Button
        remove_button = qt_comps.create_button(
            parent_widget=self, text="X", command=lambda: self.remove_requested.emit(self.index),
            tooltip="Remove this parameter", fixed_width=25, fixed_height=25
        )
        remove_button.setStyleSheet("QPushButton { color: white; background-color: #C00000; }")
        layout.addWidget(remove_button)

        # Key Entry (using qt_comps.create_entry which returns a container with label+entry)
        # Since we don't want a visible label "Key" for each row, we pass label_text=None
        key_entry_container = qt_comps.create_entry(
            parent_widget=self, ui_state=self.ui_state_kv_pair, key_path="key", 
            placeholder_text="Parameter Name", label_text=None,
            tooltip="Key name for an argument in your scheduler"
        )
        layout.addWidget(key_entry_container, 1) # Stretch factor 1

        # Value Entry
        value_entry_container = qt_comps.create_entry(
            parent_widget=self, ui_state=self.ui_state_kv_pair, key_path="value",
            placeholder_text="Parameter Value", label_text=None,
            tooltip="Value for an argument. Special values: %LR%, %EPOCHS%, %STEPS_PER_EPOCH%, %TOTAL_STEPS%, %SCHEDULER_STEPS% (Note: OneTrainer calls step() per learning step, not epoch)."
        )
        layout.addWidget(value_entry_container, 1) # Stretch factor 1
        
        # Original code had save_command on FocusOut.
        # qt_comps.create_entry calls ui_state.set_var on editingFinished, which updates the dict.
        # The ConfigListBase/SchedulerParamsWindow would be responsible for saving the whole TrainConfig if needed.

class KvParams(ConfigListBase):
    """Manages a list of Key-Value parameter widgets."""
    def __init__(self, parent_widget: QWidget, train_config_instance: TrainConfig):
        super().__init__(parent_widget, add_button_text="Add Scheduler Parameter")
        
        self.train_config = train_config_instance # Reference to the main TrainConfig

        # Ensure the scheduler_params list exists on train_config
        if not hasattr(self.train_config, "scheduler_params") or \
           not isinstance(self.train_config.scheduler_params, list):
            self.train_config.scheduler_params = []

        self.items_layout = QVBoxLayout(self.scroll_content_widget)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_content_widget.setLayout(self.items_layout)

        self.refresh_list_display() # Load initial items

    def create_widget(self, element_data: Dict[str, str], index: int) -> KvWidget:
        # element_data is one of the dicts from self.train_config.scheduler_params
        widget = KvWidget(element_data, index, self.scroll_content_widget)
        widget.remove_requested.connect(self.remove_element_slot)
        return widget

    def create_new_element(self) -> Dict[str, str]:
        return {"key": "", "value": ""}

    @Slot()
    def on_add_new_element(self):
        new_kv_pair = self.create_new_element()
        self.train_config.scheduler_params.append(new_kv_pair)
        # Changes are live on self.train_config. No separate save file for this list.
        self.refresh_list_display()

    @Slot(int)
    def remove_element_slot(self, index: int):
        if 0 <= index < len(self.train_config.scheduler_params):
            del self.train_config.scheduler_params[index]
            self.refresh_list_display()
            # Changes are live on self.train_config.

    def refresh_list_display(self):
        self._clear_layout(self.items_layout)
        for i, kv_pair_dict in enumerate(self.train_config.scheduler_params):
            widget = self.create_widget(kv_pair_dict, i)
            self.items_layout.addWidget(widget)
        self.items_layout.addStretch(1) # Push items to top


class SchedulerParamsWindow(QDialog):
    def __init__(self, parent_training_tab: QWidget, train_config: TrainConfig, ui_state_train_config: UIState, *args, **kwargs):
        super().__init__(parent_training_tab, *args, **kwargs)

        self.train_config = train_config # Main TrainConfig
        self.ui_state_train_config = ui_state_train_config # UIState for the main TrainConfig

        self.setWindowTitle("Learning Rate Scheduler Settings")
        self.setMinimumSize(600, 400)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)
        main_layout.setSpacing(10)

        # Conditional UI for Custom Scheduler Class Name
        self.custom_scheduler_class_name_widget_container: Optional[QWidget] = None
        if self.train_config.learning_rate_scheduler == LearningRateScheduler.CUSTOM:
            self.custom_scheduler_class_name_widget_container = qt_comps.create_entry(
                parent_widget=self, 
                ui_state=self.ui_state_train_config, # Use main UIState
                key_path="custom_learning_rate_scheduler", # Path within TrainConfig
                label_text="Custom Scheduler Class:", 
                tooltip="Python class module and name, e.g., mymodule.MyScheduler"
            )
            main_layout.addWidget(self.custom_scheduler_class_name_widget_container)

        # Key-Value Parameters List
        params_label = qt_comps.create_label(self, "Scheduler Parameters (Key-Value Pairs):")
        params_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(params_label)
        
        self.params_list_widget = KvParams(self, self.train_config)
        main_layout.addWidget(self.params_list_widget, 1) # Make list stretch

        # OK Button
        self.ok_button = qt_comps.create_button(self, "OK", command=self.accept)
        ok_button_layout = QHBoxLayout()
        ok_button_layout.addStretch(1)
        ok_button_layout.addWidget(self.ok_button)
        main_layout.addLayout(ok_button_layout)

        QTimer.singleShot(100, self._late_init)
        self.setModal(True)

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        self.activateWindow()
        self.raise_()
        self.ok_button.setFocus()

    # No specific on_window_close needed if accept/reject is sufficient.
    # Changes to scheduler_params are live in self.train_config via UIState in KvWidget.
    # The main TrainUI is responsible for saving the overall TrainConfig.

    def done(self, result: int): # Override done to ensure cursor is restored (if ever set)
        QApplication.restoreOverrideCursor() # Just in case
        super().done(result)
