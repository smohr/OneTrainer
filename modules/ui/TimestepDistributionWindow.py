import random
import traceback # For error printing

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QWidget, QPushButton, QScrollArea,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPalette

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib.pyplot as plt # Keep for plt.subplots() if used that way

from modules.modelSetup.mixin.ModelSetupNoiseMixin import ModelSetupNoiseMixin
from modules.util.config.TrainConfig import TrainConfig
from modules.util.enum.TimestepDistribution import TimestepDistribution
import modules.util.ui.qt_components as qt_comps
from modules.util.ui.ui_utils import get_icon_path
from modules.util.ui.UIState import UIState

import torch
from torch import Tensor


class TimestepGenerator(ModelSetupNoiseMixin):
    # This class is non-UI and its logic should remain the same.
    def __init__(
            self,
            timestep_distribution: TimestepDistribution,
            min_noising_strength: float,
            max_noising_strength: float,
            noising_weight: float,
            noising_bias: float,
            timestep_shift: float,
            dynamic_timestep_shifting: bool,
            latent_width: int,
            latent_height: int,
    ):
        super().__init__()
        self.timestep_distribution = timestep_distribution
        self.min_noising_strength = min_noising_strength
        self.max_noising_strength = max_noising_strength
        self.noising_weight = noising_weight
        self.noising_bias = noising_bias
        self.timestep_shift = timestep_shift
        self.dynamic_timestep_shifting = dynamic_timestep_shifting
        self.latent_width = latent_width
        self.latent_height = latent_height

    def generate(self) -> Tensor:
        generator = torch.Generator()
        generator.seed() # Use a new random seed each time for representative distribution

        # Create a temporary config for generation based on current UI settings
        # This assumes the main config passed to the window is the one being modified by UIState
        temp_config_for_generation = TrainConfig() # Create a blank or default one
        temp_config_for_generation.timestep_distribution = self.timestep_distribution
        temp_config_for_generation.min_noising_strength = self.min_noising_strength
        temp_config_for_generation.max_noising_strength = self.max_noising_strength
        temp_config_for_generation.noising_weight = self.noising_weight
        temp_config_for_generation.noising_bias = self.noising_bias
        temp_config_for_generation.timestep_shift = self.timestep_shift
        temp_config_for_generation.dynamic_timestep_shifting = self.dynamic_timestep_shifting
        
        return self._get_timestep_discrete(
            num_train_timesteps=1000, # Standard number of timesteps for preview
            deterministic=False,
            generator=generator,
            batch_size=100000, # Generate a large batch for a good histogram
            config=temp_config_for_generation, # Use the temp config
            latent_width=self.latent_width,
            latent_height=self.latent_height,
        )


class TimestepDistributionWindow(QDialog):
    def __init__(
            self,
            parent_widget: QWidget, # parent is QWidget
            config: TrainConfig,    # Main TrainConfig from TrainingTab/TrainUI
            ui_state: UIState,      # UIState for the main TrainConfig
            *args, **kwargs,
    ):
        super().__init__(parent_widget, *args, **kwargs)

        self.setWindowTitle("Timestep Distribution Preview")
        self.setMinimumSize(900, 650) # Adjusted for potentially larger plot labels

        self.config = config # This is train_config
        self.ui_state = ui_state # This is main_ui_state for train_config

        self.ax = None
        self.canvas = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)

        # UI Elements Frame (Scrollable)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        controls_and_plot_layout = QHBoxLayout(content_widget) # Horizontal: Controls | Plot

        # Left side: Controls
        controls_container = QWidget()
        controls_layout = QGridLayout(controls_container)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._setup_controls(controls_container, controls_layout) # Pass container for qt_comps parent
        controls_and_plot_layout.addWidget(controls_container, 1) # Stretch factor 1 for controls side

        # Right side: Plot
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container) # Use QVBoxLayout for the canvas
        self._setup_plot_area(plot_container, plot_layout)
        controls_and_plot_layout.addWidget(plot_container, 2) # Stretch factor 2 for plot side
        
        main_layout.addWidget(scroll_area, 1) # Scroll area takes most space

        # Bottom Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.update_preview_button = qt_comps.create_button(self, "Update Preview", command=self.__update_preview)
        button_layout.addWidget(self.update_preview_button)
        self.ok_button = qt_comps.create_button(self, "OK", command=self.accept)
        button_layout.addWidget(self.ok_button)
        main_layout.addLayout(button_layout)

        QTimer.singleShot(100, self._late_init)
        self.setModal(True)
        self.__update_preview() # Initial plot

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        self.activateWindow()
        self.raise_()
        self.update_preview_button.setFocus()


    def _setup_controls(self, parent_for_helpers: QWidget, layout: QGridLayout):
        row = 0
        # Key paths are relative to self.config (TrainConfig) which is managed by self.ui_state
        layout.addWidget(qt_comps.create_options_kv(parent_for_helpers, self.ui_state, "timestep_distribution", [(str(x), x) for x in list(TimestepDistribution)], "Timestep Distribution", "Selects the function to sample timesteps during training"), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(parent_for_helpers, self.ui_state, "min_noising_strength", "Min Noising Strength", "Specifies the minimum noising strength...", value_type=float), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(parent_for_helpers, self.ui_state, "max_noising_strength", "Max Noising Strength", "Specifies the maximum noising strength...", value_type=float), row, 0, 1, 2); row+=1
        layout.addWidget(qt_comps.create_entry(parent_for_helpers, self.ui_state, "noising_weight", "Noising Weight (Gamma)", "Controls the weight parameter of the timestep distribution function."), row, 0, 1, 2, value_type=float); row+=1
        layout.addWidget(qt_comps.create_entry(parent_for_helpers, self.ui_state, "noising_bias", "Noising Bias", "Controls the bias parameter of the timestep distribution function."), row, 0, 1, 2, value_type=float); row+=1
        layout.addWidget(qt_comps.create_entry(parent_for_helpers, self.ui_state, "timestep_shift", "Timestep Shift", "Shift the timestep distribution."), row, 0, 1, 2, value_type=float); row+=1
        layout.addWidget(qt_comps.create_switch(parent_for_helpers, self.ui_state, "dynamic_timestep_shifting", "Dynamic Timestep Shifting", "Dynamically shift based on resolution. Preview uses random 512-1024 (VAE scale 8)."), row, 0, 1, 2); row+=1
        layout.setRowStretch(row, 1) # Push controls to top of their column


    def _setup_plot_area(self, parent_container: QWidget, layout: QVBoxLayout):
        # Determine theme colors for plot
        palette = QApplication.instance().palette()
        bg_color_q = palette.color(QPalette.ColorRole.Window)
        text_color_q = palette.color(QPalette.ColorRole.WindowText)

        bg_color_hex = bg_color_q.name()
        text_color_hex = text_color_q.name()

        self.fig = Figure(figsize=(6, 5), dpi=100) # Adjust size as needed
        self.fig.set_facecolor(bg_color_hex)
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(bg_color_hex)
        self.ax.spines['bottom'].set_color(text_color_hex)
        self.ax.spines['left'].set_color(text_color_hex)
        self.ax.spines['top'].set_color(text_color_hex)
        self.ax.spines['right'].set_color(text_color_hex)
        self.ax.tick_params(axis='x', colors=text_color_hex, which="both")
        self.ax.tick_params(axis='y', colors=text_color_hex, which="both")
        self.ax.xaxis.label.set_color(text_color_hex)
        self.ax.yaxis.label.set_color(text_color_hex)
        self.ax.title.set_color(text_color_hex)


        self.canvas = FigureCanvasQTAgg(self.fig)
        layout.addWidget(self.canvas)

    def __update_preview(self):
        if not self.ax or not self.canvas:
            return
            
        # Values are taken directly from self.config, which should be updated by UIState
        resolution = random.randint(512, 1024)
        try:
            generator = TimestepGenerator(
                timestep_distribution=self.config.timestep_distribution,
                min_noising_strength=self.config.min_noising_strength,
                max_noising_strength=self.config.max_noising_strength,
                noising_weight=self.config.noising_weight,
                noising_bias=self.config.noising_bias,
                timestep_shift=self.config.timestep_shift,
                dynamic_timestep_shifting=self.config.dynamic_timestep_shifting,
                latent_width=resolution // 8,
                latent_height=resolution // 8,
            )
            data_to_plot = generator.generate()
            self.ax.cla() # Clear previous plot
            self.ax.hist(data_to_plot.numpy(), bins=100, range=(0, 999)) # .numpy() if it's a torch tensor
            self.ax.set_title("Timestep Distribution Preview", color=self.ax.title.get_color())
            self.ax.set_xlabel("Timestep", color=self.ax.xaxis.label.get_color())
            self.ax.set_ylabel("Frequency", color=self.ax.yaxis.label.get_color())
            self.canvas.draw()
        except Exception as e:
            print(f"Error updating timestep distribution preview: {e}")
            traceback.print_exc()
            if self.ax and self.canvas:
                self.ax.cla()
                self.ax.text(0.5, 0.5, "Error generating preview", horizontalalignment='center', verticalalignment='center', color='red')
                self.canvas.draw()

    # def __ok(self): # Original method, now handled by self.accept()
    #     self.destroy()

    def done(self, result: int):
        # Clean up Matplotlib figure if necessary, though QDialog closing should handle canvas
        if self.fig:
            plt.close(self.fig) # Important to close the figure to free memory
        super().done(result)

[end of modules/ui/TimestepDistributionWindow.py]
