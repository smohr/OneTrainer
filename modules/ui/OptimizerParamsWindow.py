import contextlib
import traceback # For error printing
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QScrollArea, QLabel, QLineEdit,
    QComboBox, QPushButton, QWidget, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

import modules.util.ui.qt_components as qt_comps
from modules.util.ui.ui_utils import get_icon_path
from modules.util.config.TrainConfig import TrainConfig, OptimizerConfig
from modules.util.enum.Optimizer import Optimizer
from modules.util.optimizer_util import (
    OPTIMIZER_DEFAULT_PARAMETERS, # This is a dict
    change_optimizer,
    load_optimizer_defaults,
    # update_optimizer_config, # Not directly used if UIState handles updates
)
from modules.util.ui.UIState import UIState


class OptimizerParamsWindow(QDialog):
    def __init__(
            self,
            parent_widget: QWidget, # Renamed parent
            train_config: TrainConfig,
            main_ui_state: UIState, # This is the UIState for the main TrainConfig
            *args, **kwargs,
    ):
        super().__init__(parent_widget, *args, **kwargs)

        self.train_config = train_config # Reference to the main TrainConfig
        # Create a UIState specifically for the train_config.optimizer object
        # This allows qt_components to work with paths relative to optimizer_config
        self.optimizer_config_obj = train_config.optimizer 
        self.optimizer_ui_state = UIState(self.optimizer_config_obj, self) 

        self.setWindowTitle("Optimizer Settings")
        self.setMinimumSize(800, 500)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)

        # Static part (Optimizer dropdown and Load Defaults button)
        static_controls_frame = QFrame(self)
        static_controls_layout = QGridLayout(static_controls_frame)
        static_controls_layout.setColumnStretch(1, 1) # Allow dropdown to expand
        static_controls_layout.setColumnStretch(4, 1) # Allow space if needed
        self._setup_static_controls(static_controls_layout)
        main_layout.addWidget(static_controls_frame)

        # Scroll area for dynamic parameters
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area, 1) # Scroll area takes expanding space

        self.dynamic_params_widget = QWidget() # Content widget for scroll area
        self.scroll_area.setWidget(self.dynamic_params_widget)
        self.dynamic_params_layout = QGridLayout(self.dynamic_params_widget)
        self.dynamic_params_layout.setColumnStretch(1, 1)
        self.dynamic_params_layout.setColumnStretch(4, 1)
        # self.dynamic_params_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Keep items at top

        # OK Button at the bottom
        self.ok_button = qt_comps.create_button(self, "OK", command=self.accept)
        ok_button_layout = QHBoxLayout()
        ok_button_layout.addStretch(1)
        ok_button_layout.addWidget(self.ok_button)
        main_layout.addLayout(ok_button_layout)
        
        self._create_dynamic_ui_elements() # Initial population of dynamic fields

        QTimer.singleShot(100, self._late_init)
        self.setModal(True)

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        self.activateWindow()
        self.raise_()
        # Find the QComboBox for optimizer type to set focus, if needed.
        # For now, default focus behavior is fine.

    def _setup_static_controls(self, layout: QGridLayout):
        optimizer_items = [(opt.value, opt) for opt in Optimizer] # (display_name, enum_value)

        # Optimizer Dropdown
        # The key "optimizer" within self.optimizer_config_obj (which is a TrainConfig.optimizer / OptimizerConfig)
        layout.addWidget(qt_comps.create_options_kv(self, self.optimizer_ui_state, "optimizer", optimizer_items, "Optimizer", "The type of optimizer", on_change_command=self.on_optimizer_change), 0, 0, 1, 2)

        # Defaults Button
        layout.addWidget(qt_comps.create_button(self, "Load Optimizer Defaults", self.load_optimizer_defaults_action, "Load default settings for the selected optimizer"), 0, 3, 1, 2)


    def _clear_dynamic_ui_elements(self):
        while self.dynamic_params_layout.count():
            item = self.dynamic_params_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _create_dynamic_ui_elements(self):
        self._clear_dynamic_ui_elements() # Clear previous ones
        
        selected_optimizer_enum_val = self.optimizer_config_obj.optimizer # Get current optimizer enum
        
        # Ensure selected_optimizer_enum_val is an Optimizer enum instance
        if not isinstance(selected_optimizer_enum_val, Optimizer):
            try: # Try to convert from string if it's a string value from UIState init
                selected_optimizer_enum_val = Optimizer(str(selected_optimizer_enum_val))
            except ValueError:
                print(f"Warning: Invalid optimizer value '{selected_optimizer_enum_val}' encountered.")
                return # Cannot proceed without a valid optimizer

        optimizer_params = OPTIMIZER_DEFAULT_PARAMETERS.get(selected_optimizer_enum_val, {})
        
        # KEY_DETAIL_MAP from original code
        KEY_DETAIL_MAP = {
            'adam_w_mode': {'title': 'Adam W Mode', 'tooltip': 'Whether to use weight decay correction for Adam optimizer.', 'type': 'bool'},
            'alpha': {'title': 'Alpha', 'tooltip': 'Smoothing parameter for RMSprop and others.', 'type': 'float'},
            'amsgrad': {'title': 'AMSGrad', 'tooltip': 'Whether to use the AMSGrad variant for Adam.', 'type': 'bool'},
            'beta1': {'title': 'Beta1', 'tooltip': 'Momentum term (coefficient for running averages of gradient).', 'type': 'float'},
            'beta2': {'title': 'Beta2', 'tooltip': 'Coefficient for computing running averages of gradient square.', 'type': 'float'},
            'beta3': {'title': 'Beta3', 'tooltip': 'Coefficient for computing the Prodigy stepsize.', 'type': 'float'},
            'bias_correction': {'title': 'Bias Correction', 'tooltip': 'Whether to use bias correction (Adam).', 'type': 'bool'},
            'block_wise': {'title': 'Block Wise', 'tooltip': '8-bit optim: block-wise updates.', 'type': 'bool'},
            'capturable': {'title': 'Capturable', 'tooltip': 'For AdamW, Adadelta, etc. (related to CUDA graphs).', 'type': 'bool'},
            'centered': {'title': 'Centered (RMSprop)', 'tooltip': 'If True, compute centered RMSProp, gradient is normalized by an estimation of its variance.', 'type': 'bool'},
            'clip_threshold': {'title': 'Clip Threshold (Adafactor)', 'tooltip': 'Threshold for clipping parameter updates.', 'type': 'float'},
            'd0': {'title': 'Initial D (Prodigy/DAdapt)', 'tooltip': 'Initial D estimate for D-adaptation.', 'type': 'float'},
            'd_coef': {'title': 'D Coefficient (Prodigy)', 'tooltip': 'Coefficient for the estimate of d.', 'type': 'float'},
            'dampening': {'title': 'Dampening (SGD)', 'tooltip': 'Dampening for momentum.', 'type': 'float'},
            'decay_rate': {'title': 'Decay Rate (RMSprop)', 'tooltip': 'Decay rate for moment estimation.', 'type': 'float'},
            'decouple': {'title': 'Decouple WD (Prodigy/DAdapt)', 'tooltip': 'Use AdamW style decoupled weight decay.', 'type': 'bool'},
            'differentiable': {'title': 'Differentiable (Adam)', 'tooltip': 'Experimental option for Adam, makes it differentiable.', 'type': 'bool'},
            'eps': {'title': 'Epsilon (Adam, RMSProp etc.)', 'tooltip': 'Term added to the denominator to improve numerical stability.', 'type': 'float'},
            'eps2': {'title': 'Epsilon 2 (Lion)', 'tooltip': 'Term added to the denominator for Lion.', 'type': 'float'},
            'foreach': {'title': 'ForEach (Various)', 'tooltip': 'Use PyTorch foreach implementation if available (faster).', 'type': 'bool'},
            'fsdp_in_use': {'title': 'FSDP in Use (Sophia)', 'tooltip': 'Flag for using sharded parameters with FSDP.', 'type': 'bool'},
            'fused': {'title': 'Fused (Adam, SGD)', 'tooltip': 'Use a fused implementation if available (faster, less memory).', 'type': 'bool'},
            'fused_back_pass': {'title': 'Fused Back Pass', 'tooltip': 'Fuse back propagation with optimizer step (reduces VRAM, incompatible with grad accum).', 'type': 'bool'},
            'growth_rate': {'title': 'Growth Rate (Prodigy/DAdapt)', 'tooltip': 'Limit for D estimate growth rate.', 'type': 'float'},
            'initial_accumulator_value': {'title': 'Initial Accumulator (Adagrad)', 'tooltip': 'Initial value for Adagrad accumulator.', 'type': 'float'},
            'initial_accumulator': {'title': 'Initial Accumulator (Sophia)', 'tooltip': 'Starting value for moment estimates.', 'type': 'float'},
            'is_paged': {'title': 'Paged (8-bit optims)', 'tooltip': 'Whether optimizer state should be paged to CPU.', 'type': 'bool'},
            'log_every': {'title': 'Log Every (DAdapt)', 'tooltip': 'Logging interval for D-Adaptation.', 'type': 'int'},
            'lr_decay': {'title': 'LR Decay (Adagrad)', 'tooltip': 'Learning rate decay.', 'type': 'float'},
            'maximize': {'title': 'Maximize (Various)', 'tooltip': 'Maximize the objective instead of minimizing.', 'type': 'bool'},
            'min_8bit_size': {'title': 'Min 8bit Size', 'tooltip': 'Minimum tensor size for 8-bit quantization.', 'type': 'int'},
            'momentum': {'title': 'Momentum (SGD, RMSProp)', 'tooltip': 'Momentum factor.', 'type': 'float'},
            'nesterov': {'title': 'Nesterov (SGD)', 'tooltip': 'Enables Nesterov momentum.', 'type': 'bool'},
            'no_prox': {'title': 'No Prox (RMSprop)', 'tooltip': 'Whether to use proximity updates.', 'type': 'bool'},
            'optim_bits': {'title': 'Optim Bits (8-bit optims)', 'tooltip': 'Number of bits for optimizer state (e.g., 32 or 8).', 'type': 'int'},
            'percentile_clipping': {'title': 'Percentile Clipping (8-bit optims)', 'tooltip': 'Gradient clipping based on percentile (0-100).', 'type': 'int'},
            'relative_step': {'title': 'Relative Step (Adafactor)', 'tooltip': 'Use relative step size.', 'type': 'bool'},
            'safeguard_warmup': {'title': 'Safeguard Warmup (Prodigy/DAdapt)', 'tooltip': 'Avoid issues during warm-up stage.', 'type': 'bool'},
            'scale_parameter': {'title': 'Scale Parameter (Adafactor)', 'tooltip': 'Scale learning rate by parameter norm.', 'type': 'bool'},
            'stochastic_rounding': {'title': 'Stochastic Rounding (Sophia)', 'tooltip': 'Stochastic rounding for weight updates (improves bfloat16).', 'type': 'bool'},
            'use_bias_correction': {'title': 'Use Bias Correction (Prodigy)', 'tooltip': 'Turn on Adam\'s bias correction.', 'type': 'bool'},
            'use_triton': {'title': 'Use Triton', 'tooltip': 'Whether Triton optimization should be used (Sophia).', 'type': 'bool'},
            'warmup_init': {'title': 'Warmup Init (Adafactor)', 'tooltip': 'Warm-up optimizer initialization.', 'type': 'bool'},
            'weight_decay': {'title': 'Weight Decay', 'tooltip': 'L2 penalty to prevent overfitting.', 'type': 'float'},
            'weight_lr_power': {'title': 'Weight LR Power (Sophia)', 'tooltip': 'Power for LR weighting during warmup (0 for no weighting).', 'type': 'float'},
            'decoupled_decay': {'title': 'Decoupled Decay (RAdam)', 'tooltip': 'Use AdamW style decoupled weight decay.', 'type': 'bool'},
            'fixed_decay': {'title': 'Fixed Decay (RAdam)', 'tooltip': 'Applies fixed weight decay (True) or scales with LR (False).', 'type': 'bool'},
            'rectify': {'title': 'Rectify (RAdam)', 'tooltip': 'Perform rectified update similar to RAdam.', 'type': 'bool'},
            'degenerated_to_sgd': {'title': 'Degenerate to SGD (RAdam)', 'tooltip': 'Performs SGD update when gradient variance is high.', 'type': 'bool'},
            'k': {'title': 'K (AdaBound)', 'tooltip': 'Number of vector projected per iteration (AdaBound).', 'type': 'int'}, # Also Sophia
            'xi': {'title': 'Xi (Sophia)', 'tooltip': 'Term for vector projections to avoid div by zero.', 'type': 'float'},
            'n_sma_threshold': {'title': 'N SMA Threshold (RAdam)', 'tooltip': 'Threshold for Simple Moving Average.', 'type': 'int'},
            'ams_bound': {'title': 'AMSBound (AdaBound)', 'tooltip': 'Use AMSBound variant.', 'type': 'bool'}, # For AdaBound
            'r': {'title': 'R (Sophia)', 'tooltip': 'EMA factor for Sophia.', 'type': 'float'},
            'adanorm': {'title': 'AdaNorm (AdamNorm)', 'tooltip': 'Use AdaNorm variant.', 'type': 'bool'},
            'adam_debias': {'title': 'Adam Debias (AdamNorm)', 'tooltip': 'Correct denominator to avoid inflating step sizes early.', 'type': 'bool'},
            'slice_p': {'title': 'Slice Parameters (Prodigy)', 'tooltip': 'Calculate LR adaptation on every p-th entry to save memory.', 'type': 'int'},
            'cautious': {'title': 'Cautious (Sophia)', 'tooltip': 'Use Cautious variant for Sophia.', 'type': 'bool'},
            'weight_decay_by_lr': {'title': 'Weight Decay by LR (Sophia)', 'tooltip': 'Automatically adjust weight decay based on LR.', 'type': 'bool'},
            'prodigy_steps': {'title': 'Prodigy Steps', 'tooltip': 'Turn off Prodigy after N steps.', 'type': 'int'},
            'use_speed': {'title': 'Use Speed (Sophia)', 'tooltip': 'Use speed method for Sophia.', 'type': 'bool'},
            'split_groups': {'title': 'Split Groups (Sophia)', 'tooltip': 'Use split groups when training multiple params (UNet, TE).', 'type': 'bool'},
            'split_groups_mean': {'title': 'Split Groups Mean (Sophia)', 'tooltip': 'Use mean for split groups.', 'type': 'bool'},
            'factored': {'title': 'Factored (Adafactor)', 'tooltip': 'Use factored second moment estimates.', 'type': 'bool'},
            'factored_fp32': {'title': 'Factored FP32 (Sophia)', 'tooltip': 'Use factored_fp32 for Sophia.', 'type': 'bool'},
            'use_stableadamw': {'title': 'Use StableAdamW (StableAdamW)', 'tooltip': 'Use StableAdamW for gradient scaling.', 'type': 'bool'},
            'use_muon_pp': {'title': 'Use Muon_pp (Sophia)', 'tooltip': 'Use muon_pp method for Sophia.', 'type': 'bool'},
            'use_cautious': {'title': 'Use Cautious (Sophia, again)', 'tooltip': 'Use cautious method for Sophia.', 'type': 'bool'}, # Duplicate in map
            'use_grams': {'title': 'Use Grams (Sophia)', 'tooltip': 'Use grams method for Sophia.', 'type': 'bool'},
            'use_adopt': {'title': 'Use Adopt (Sophia)', 'tooltip': 'Use adopt method for Sophia.', 'type': 'bool'},
            'use_focus': {'title': 'Use Focus (Sophia)', 'tooltip': 'Use focus method for Sophia.', 'type': 'bool'},
        }
        # @formatter:on

        row_offset = 1 # Start dynamic params from row 1 in their grid
        
        for index, key in enumerate(optimizer_params.keys()):
            if key == "optimizer": continue # Skip the optimizer type itself

            param_info = KEY_DETAIL_MAP.get(key, {'title': key.replace("_", " ").title(), 'tooltip': f'Parameter: {key}', 'type': 'str'}) # Default if not in map
            
            title = param_info['title']
            tooltip = param_info['tooltip']
            param_type_str = param_info['type']

            # Determine actual data type for qt_comps.create_entry
            actual_type = str
            if param_type_str == 'float': actual_type = float
            elif param_type_str == 'int': actual_type = int
            # bool is handled by create_switch

            current_row = row_offset + (index // 2)
            current_col_label = 0 if (index % 2 == 0) else 3
            current_col_widget = 1 if (index % 2 == 0) else 4
            
            # Use self.optimizer_ui_state and the direct key
            if param_type_str == 'bool':
                self.dynamic_params_layout.addWidget(qt_comps.create_switch(self.dynamic_params_widget, self.optimizer_ui_state, key, title, tooltip), current_row, current_col_label, 1, 2) # Switch spans 2 columns
            else:
                self.dynamic_params_layout.addWidget(qt_comps.create_entry(self.dynamic_params_widget, self.optimizer_ui_state, key, title, tooltip, value_type=actual_type), current_row, current_col_label, 1, 2)
        
        self.dynamic_params_layout.setRowStretch(self.dynamic_params_layout.rowCount(), 1)


    def on_optimizer_change(self, optimizer_enum_val: Optimizer): # Receives the enum value
        # This is called when the optimizer QComboBox changes.
        # The value in self.optimizer_config_obj.optimizer is already updated by qt_comps helper.
        
        # Update the rest of the optimizer config to defaults for the NEW optimizer
        # change_optimizer updates self.train_config.optimizer based on its current .optimizer type
        # Here, self.optimizer_config_obj IS self.train_config.optimizer
        change_optimizer(self.train_config) 
        
        # Notify the UIState for the optimizer that its underlying object's content has changed significantly
        # This should make track_variable callbacks fire for all changed fields.
        self.optimizer_ui_state.update_target_object(self.optimizer_config_obj)
        
        self._create_dynamic_ui_elements() # Rebuild dynamic part of UI

    def load_optimizer_defaults_action(self):
        # load_optimizer_defaults updates self.train_config.optimizer
        load_optimizer_defaults(self.train_config)
        
        # Notify UIState and rebuild UI
        self.optimizer_ui_state.update_target_object(self.optimizer_config_obj)
        self._create_dynamic_ui_elements()

    def done(self, result: int):
        # No explicit save needed here if UIState binding is correct, as
        # self.train_config.optimizer has been updated live.
        super().done(result)

[end of modules/ui/OptimizerParamsWindow.py]
