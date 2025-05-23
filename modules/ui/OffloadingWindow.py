from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QWidget, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

import modules.util.ui.qt_components as qt_comps
from modules.util.ui.ui_utils import get_icon_path
from modules.util.config.TrainConfig import TrainConfig
from modules.util.enum.GradientCheckpointingMethod import GradientCheckpointingMethod
from modules.util.ui.UIState import UIState
import traceback


class OffloadingWindow(QDialog):
    def __init__(
            self,
            parent_widget: QWidget, # parent is QWidget
            config: TrainConfig,    # Main TrainConfig
            ui_state: UIState,      # UIState for the main TrainConfig
            *args, **kwargs,
    ):
        super().__init__(parent_widget, *args, **kwargs)

        self.config = config # This is train_config, accessed via self.ui_state
        self.ui_state = ui_state # This is main_ui_state for train_config

        self.setWindowTitle("Gradient Checkpointing & Offloading Settings")
        self.setMinimumSize(500, 250) # Adjusted size

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)
        main_layout.setSpacing(10)

        # Content Frame
        content_frame = QWidget(self) # No need for QScrollArea if content is fixed and small
        grid_layout = QGridLayout(content_frame)
        grid_layout.setColumnStretch(1, 1) # Allow widgets in column 1 to expand
        self._setup_controls(content_frame, grid_layout)
        main_layout.addWidget(content_frame)

        # OK Button at the bottom
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

    def _setup_controls(self, parent_for_helpers: QWidget, layout: QGridLayout):
        row = 0
        
        # Gradient Checkpointing Method
        gcm_items = [(str(x), x) for x in list(GradientCheckpointingMethod)]
        layout.addWidget(qt_comps.create_options_kv(parent_for_helpers, self.ui_state, "gradient_checkpointing", gcm_items, "Gradient Checkpointing", "Enables gradient checkpointing. Reduces memory, increases training time."), row, 0, 1, 2); row+=1
        
        # Async Offloading Switch
        layout.addWidget(qt_comps.create_switch(parent_for_helpers, self.ui_state, "enable_async_offloading", "Async Offloading", "Enables Asynchronous offloading."), row, 0, 1, 2); row+=1
        
        # Offload Activations Switch
        layout.addWidget(qt_comps.create_switch(parent_for_helpers, self.ui_state, "enable_activation_offloading", "Offload Activations", "Enables Activation Offloading."), row, 0, 1, 2); row+=1

        # Layer Offload Fraction Entry
        layout.addWidget(qt_comps.create_entry(parent_for_helpers, self.ui_state, "layer_offload_fraction", "Layer Offload Fraction", "Offloading of individual layers (0-1). 0=disabled. Requires CPU_OFFLOADED checkpointing.", value_type=float), row, 0, 1, 2); row+=1

        layout.setRowStretch(row, 1) # Push controls to top

    def done(self, result: int):
        # No specific save logic needed here as qt_components update UIState,
        # which updates the underlying TrainConfig object directly.
        super().done(result)

[end of modules/ui/OffloadingWindow.py]
