import os
import platform
import subprocess
import traceback
# from tkinter import filedialog # Replaced by QFileDialog

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QCheckBox, QFileDialog, QWidget, QApplication,
    QSizePolicy, QSpacerItem
)
from PySide6.QtGui import QPixmap, QMouseEvent, QWheelEvent, QPainter, QColor, QBrush, QKeySequence, QShortcut, QIcon, QImage
from PySide6.QtCore import Qt, QTimer, QEvent, QPoint

from modules.module.Blip2Model import Blip2Model
from modules.module.BlipModel import BlipModel
from modules.module.ClipSegModel import ClipSegModel
from modules.module.MaskByColor import MaskByColor
from modules.module.RembgHumanModel import RembgHumanModel
from modules.module.RembgModel import RembgModel
from modules.module.WDModel import WDModel
# from modules.ui.GenerateCaptionsWindow import GenerateCaptionsWindow # TODO: Refactor to QDialog
# from modules.ui.GenerateMasksWindow import GenerateMasksWindow # TODO: Refactor to QDialog
from modules.util import path_util
from modules.util.image_util import load_image
from modules.util.torch_util import default_device
# from modules.util.ui import components # Replaced by direct PySide6 widgets or helpers
from modules.util.ui.ui_utils import get_icon_path # Using get_icon_path for consistency
from modules.util.ui.UIState import UIState

import torch
import cv2 # Still used for floodFill
import numpy as np
from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt


class CaptionUI(QDialog):
    def __init__(
            self,
            parent_widget: QWidget, # parent is QWidget for QDialog
            initial_dir: str | None,
            initial_include_subdirectories: bool,
    ) -> None:
        super().__init__(parent_widget)

        self.dir = initial_dir if initial_dir else os.getcwd()
        self.config_ui_data = {"include_subdirectories": initial_include_subdirectories}
        # UIState parent is self (QDialog), though direct widget manipulation is preferred in Qt
        self.config_ui_state = UIState(self, self.config_ui_data) 
        
        self.image_size = 850 # Max dimension for image display area
        self.help_text = """Keyboard shortcuts:
Up arrow: previous image
Down arrow: next image
Return (in prompt): save
Ctrl+M: toggle mask display
Ctrl+D: draw mask mode
Ctrl+F: fill mask mode

Mask Editing:
Left click: add mask
Right click: remove mask
Mouse wheel: change brush size"""

        self.masking_model = None
        self.captioning_model = None
        self.image_rel_paths = []
        self.current_image_index = -1
        
        self.file_list_scroll_area = None # QScrollArea for file list
        self.file_list_content_widget = None # QWidget inside scroll_area
        self.image_labels_in_list = [] # List of QLabels for file names
        
        self.pil_image: Image.Image | None = None
        self.image_width = 0
        self.image_height = 0
        self.pil_mask: Image.Image | None = None
        self.mask_draw_x = 0
        self.mask_draw_y = 0
        self.mask_draw_radius = 0.01 # Percentage of max image dimension
        self.display_only_mask = False
        
        self.image_display_label: QLabel | None = None # QLabel to show image/mask
        self.mask_editing_mode = 'draw' # 'draw' or 'fill'
        self.enable_mask_editing_checkbox: QCheckBox | None = None
        self.mask_editing_alpha_input: QLineEdit | None = None
        self.prompt_input: QLineEdit | None = None

        self.setWindowTitle("OneTrainer - Caption/Mask Editor")
        self.setMinimumSize(1280, 980) # Replaces geometry and resizable(False,False)
        # self.setFixedSize(1280, 980) # If truly not resizable

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5,5,5,5)

        self._setup_top_bar(main_layout)
        
        self.bottom_frame = QFrame()
        main_layout.addWidget(self.bottom_frame, 1) # Give stretch factor for expansion
        
        bottom_layout = QHBoxLayout(self.bottom_frame)
        bottom_layout.setContentsMargins(0,0,0,0)

        self._setup_file_list_column(bottom_layout)
        self._setup_content_column(bottom_layout)
        
        self.load_directory(self.dir, self.config_ui_state.get_var("include_subdirectories"))

        QTimer.singleShot(100, self._late_init)


    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        if self.prompt_input: self.prompt_input.setFocus()
        self.activateWindow()
        self.raise_()

    def _setup_top_bar(self, main_layout: QVBoxLayout):
        top_frame = QFrame()
        top_bar_layout = QHBoxLayout(top_frame)
        top_bar_layout.setContentsMargins(0,0,0,0)

        open_btn = QPushButton("Open Directory")
        open_btn.setToolTip("Open a new directory")
        open_btn.clicked.connect(self.open_directory_dialog)
        top_bar_layout.addWidget(open_btn)

        masks_btn = QPushButton("Generate Masks")
        masks_btn.setToolTip("Automatically generate masks")
        masks_btn.clicked.connect(self.open_mask_window)
        top_bar_layout.addWidget(masks_btn)

        captions_btn = QPushButton("Generate Captions")
        captions_btn.setToolTip("Automatically generate captions")
        captions_btn.clicked.connect(self.open_caption_window)
        top_bar_layout.addWidget(captions_btn)

        if platform.system() == "Windows":
            explorer_btn = QPushButton("Open in Explorer")
            explorer_btn.setToolTip("Open the current image in Explorer")
            explorer_btn.clicked.connect(self.open_in_explorer)
            top_bar_layout.addWidget(explorer_btn)

        self.include_subdirs_checkbox = QCheckBox("Include Subdirectories")
        self.include_subdirs_checkbox.setChecked(self.config_ui_state.get_var("include_subdirectories"))
        self.include_subdirs_checkbox.toggled.connect(self._on_include_subdirs_changed)
        top_bar_layout.addWidget(self.include_subdirs_checkbox)
        
        top_bar_layout.addStretch(1)

        help_btn = QPushButton("Help")
        help_btn.setToolTip(self.help_text)
        help_btn.clicked.connect(self.print_help_to_console)
        top_bar_layout.addWidget(help_btn)
        
        main_layout.addWidget(top_frame)

    def _on_include_subdirs_changed(self, checked: bool):
        self.config_ui_state.set_var("include_subdirectories", checked)
        self.load_directory(self.dir, checked)


    def _setup_file_list_column(self, bottom_layout: QHBoxLayout):
        self.file_list_scroll_area = QScrollArea()
        self.file_list_scroll_area.setWidgetResizable(True)
        self.file_list_scroll_area.setFixedWidth(300) # Original width
        
        self.file_list_content_widget = QWidget() # This widget goes inside scroll area
        self.file_list_layout = QVBoxLayout(self.file_list_content_widget) # Layout for this widget
        self.file_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.file_list_scroll_area.setWidget(self.file_list_content_widget)
        
        bottom_layout.addWidget(self.file_list_scroll_area)

    def _populate_file_list_ui(self):
        if not self.file_list_layout: return
        
        # Clear previous labels
        while self.file_list_layout.count():
            item = self.file_list_layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()
        self.image_labels_in_list.clear()

        for i, filename in enumerate(self.image_rel_paths):
            label = QLabel(filename)
            label.setToolTip(filename)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            # Make label clickable by installing event filter
            label.setProperty("file_index", i) # Store index on the label
            label.mousePressEvent = lambda event, index=i: self._on_file_label_clicked(index)
            self.image_labels_in_list.append(label)
            self.file_list_layout.addWidget(label)
            
    def _on_file_label_clicked(self, index: int):
        self.switch_image(index)

    def _setup_content_column(self, bottom_layout: QHBoxLayout):
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame) # Main layout for content: VBox
        right_layout.setContentsMargins(5,0,0,0) # Add some left margin

        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame) # HBox for top controls
        controls_layout.setContentsMargins(0,0,0,0)

        draw_mode_btn = QPushButton("Draw Mode")
        draw_mode_btn.setToolTip("Draw mask using a brush (Ctrl+D)")
        draw_mode_btn.setCheckable(True); draw_mode_btn.setChecked(True)
        draw_mode_btn.clicked.connect(lambda: self.set_mask_editing_mode('draw', draw_mode_btn))
        controls_layout.addWidget(draw_mode_btn)
        self.draw_mode_button = draw_mode_btn # Store for mutual exclusivity

        fill_mode_btn = QPushButton("Fill Mode")
        fill_mode_btn.setToolTip("Fill mask area (Ctrl+F)")
        fill_mode_btn.setCheckable(True)
        fill_mode_btn.clicked.connect(lambda: self.set_mask_editing_mode('fill', fill_mode_btn))
        controls_layout.addWidget(fill_mode_btn)
        self.fill_mode_button = fill_mode_btn # Store

        self.enable_mask_editing_checkbox = QCheckBox("Enable Mask Editing")
        controls_layout.addWidget(self.enable_mask_editing_checkbox)
        
        controls_layout.addSpacerItem(QSpacerItem(20, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        controls_layout.addWidget(QLabel("Brush Alpha:"))
        self.mask_editing_alpha_input = QLineEdit("1.0")
        self.mask_editing_alpha_input.setFixedWidth(50)
        self.mask_editing_alpha_input.setToolTip("Alpha for mask brush (0.0 to 1.0)")
        controls_layout.addWidget(self.mask_editing_alpha_input)
        controls_layout.addStretch(1)
        right_layout.addWidget(controls_frame)

        self.image_display_label = QLabel("No image loaded")
        self.image_display_label.setMinimumSize(self.image_size, self.image_size) # Ensure it takes space
        self.image_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_display_label.setStyleSheet("border: 1px solid #555555; background-color: #333333;")
        # Event handling for mask editing
        self.image_display_label.mouseMoveEvent = self._on_image_mouse_move
        self.image_display_label.mousePressEvent = self._on_image_mouse_press
        self.image_display_label.wheelEvent = self._on_image_mouse_wheel # For brush size
        self.image_display_label.setMouseTracking(True) # Needed for mouseMoveEvent without button press
        right_layout.addWidget(self.image_display_label, 1) # Give stretch

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter prompt here...")
        self.prompt_input.returnPressed.connect(self.save_current_changes) # Save on Enter
        right_layout.addWidget(self.prompt_input)
        
        bottom_layout.addWidget(right_frame, 1) # Give stretch factor

        # Setup shortcuts for this dialog
        self._setup_shortcuts()


    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, self.previous_image_shortcut)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, self.next_image_shortcut)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_M), self, self.toggle_mask_display_shortcut)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_D), self, lambda: self.set_mask_editing_mode('draw', self.draw_mode_button))
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F), self, lambda: self.set_mask_editing_mode('fill', self.fill_mode_button))

    # --- Actual methods from original, adapted ---
    # load_directory, scan_directory, load_image, load_mask, load_prompt: mostly file I/O, should be fine
    # switch_image, refresh_image: need to update QPixmap on self.image_display_label
    # edit_mask, draw_mask, fill_mask: core logic on PIL images, then refresh_image
    # save: file I/O for prompt and mask
    # open_..._window: Will instantiate QDialogs (TODO)
    # model loading: fine
    
    # Placeholder for methods that need more detailed PySide6 implementation or event handling
    def load_directory(self, directory: str | None, include_subdirectories: bool = False):
        self.dir = directory if directory else os.getcwd()
        self.config_ui_state.set_var("include_subdirectories", include_subdirectories)
        self.scan_directory(include_subdirectories)
        self._populate_file_list_ui()

        if len(self.image_rel_paths) > 0:
            self.switch_image(0)
        else:
            self.switch_image(-1) # To clear display
        if self.prompt_input: self.prompt_input.setFocus()

    def scan_directory(self, include_subdirectories: bool):
        # ... (original scan_directory logic is fine, uses os and path_util) ...
        def __is_supported_image_extension(filename):
            name, ext = os.path.splitext(filename)
            return path_util.is_supported_image_extension(ext) and not name.endswith("-masklabel")
        self.image_rel_paths = []
        if not self.dir or not os.path.isdir(self.dir): return

        if include_subdirectories:
            for root, _, files in os.walk(self.dir):
                for filename in files:
                    if __is_supported_image_extension(filename):
                        self.image_rel_paths.append(os.path.relpath(os.path.join(root, filename), self.dir))
        else:
            for filename in os.listdir(self.dir):
                if __is_supported_image_extension(filename) and os.path.isfile(os.path.join(self.dir, filename)):
                    self.image_rel_paths.append(filename) # Already relative if not walking
        self.image_rel_paths.sort()


    def switch_image(self, index: int):
        if not self.image_labels_in_list: # No files loaded
            self.pil_image = None; self.pil_mask = None; self.prompt_input.clear()
            self.image_display_label.setText("No images in directory.")
            self.image_display_label.setPixmap(QPixmap()) # Clear pixmap
            self.current_image_index = -1
            return

        if self.current_image_index >= 0 and self.current_image_index < len(self.image_labels_in_list):
            self.image_labels_in_list[self.current_image_index].setStyleSheet("") # Reset style
        
        self.current_image_index = index
        
        if index >= 0 and index < len(self.image_labels_in_list):
            self.image_labels_in_list[index].setStyleSheet("color: red;") # Highlight selected

            try:
                self.pil_image = self._load_pil_image_for_current_index()
                self.pil_mask = self._load_pil_mask_for_current_index()
                prompt_text = self._load_prompt_for_current_index()
                if self.prompt_input: self.prompt_input.setText(prompt_text)

                if self.pil_image:
                    self.image_width = self.pil_image.width
                    self.image_height = self.pil_image.height
                    self.refresh_image_display()
                else:
                    self.image_display_label.setText(f"Error loading image: {self.image_rel_paths[index]}")
                    self.image_display_label.setPixmap(QPixmap())


            except Exception as e:
                print(f"Error switching image to index {index}: {e}")
                if self.image_display_label: self.image_display_label.setText("Error loading image.")
                if self.prompt_input: self.prompt_input.clear()
        else: # index is -1 (no image)
            if self.image_display_label:
                self.image_display_label.setText("No image selected.")
                self.image_display_label.setPixmap(QPixmap())
            if self.prompt_input: self.prompt_input.clear()
            self.pil_image = None
            self.pil_mask = None
            
    def _load_pil_image_for_current_index(self) -> Image.Image | None:
        # ... (original load_image logic, returns PIL.Image or None) ...
        if 0 <= self.current_image_index < len(self.image_rel_paths):
            try:
                path = os.path.join(self.dir, self.image_rel_paths[self.current_image_index])
                return load_image(path, convert_mode="RGB")
            except Exception as e: print(f"Failed to load image: {e}"); return None
        return None

    def _load_pil_mask_for_current_index(self) -> Image.Image | None:
        # ... (original load_mask logic, returns PIL.Image or None) ...
        if 0 <= self.current_image_index < len(self.image_rel_paths):
            try:
                base, _ = os.path.splitext(self.image_rel_paths[self.current_image_index])
                mask_path = os.path.join(self.dir, base + "-masklabel.png")
                if os.path.exists(mask_path): return load_image(mask_path, convert_mode='RGB')
            except Exception as e: print(f"Failed to load mask: {e}"); return None
        return None

    def _load_prompt_for_current_index(self) -> str:
        # ... (original load_prompt logic, returns str) ...
        if 0 <= self.current_image_index < len(self.image_rel_paths):
            try:
                base, _ = os.path.splitext(self.image_rel_paths[self.current_image_index])
                prompt_path = os.path.join(self.dir, base + ".txt")
                if os.path.exists(prompt_path):
                    with open(prompt_path, "r", encoding='utf-8') as f: return f.read().strip()
            except Exception as e: print(f"Failed to load prompt: {e}"); return ""
        return ""


    def refresh_image_display(self):
        if not self.pil_image or not self.image_display_label:
            if self.image_display_label: self.image_display_label.setPixmap(QPixmap()) # Clear
            return

        display_image = self.pil_image.copy()

        if self.pil_mask:
            # Ensure mask is same size as display_image for overlay
            # Original code resized mask to pil_image (which was already scaled for display)
            mask_for_display = self.pil_mask.resize(display_image.size, Image.Resampling.NEAREST)
            
            if self.display_only_mask:
                display_image = mask_for_display
            else: # Blend image and mask
                try:
                    # Convert to RGBA for alpha blending if not already
                    display_image = display_image.convert("RGBA")
                    mask_for_blend = mask_for_display.convert("L") # Grayscale for alpha
                    
                    # Create an RGBA version of the mask color (e.g., red with some transparency)
                    # Or use the mask's intensity to control blending
                    # For simplicity, let's make the mask red and semi-transparent
                    red_overlay = Image.new("RGBA", display_image.size, (255,0,0,0)) # Transparent red
                    
                    # Use mask_for_blend as alpha for the red_overlay
                    # This is a common way: make parts of overlay visible based on mask
                    display_image = Image.alpha_composite(display_image, Image.composite(red_overlay, display_image, mask_for_blend.point(lambda i: i * (128/255.0) ) ))

                except Exception as e:
                    print(f"Error blending mask: {e}")


        # Scale final image to fit label while preserving aspect ratio
        q_image = ImageQt(display_image.convert("RGBA")) # Ensure RGBA for QImage
        pixmap = QPixmap.fromImage(q_image)
        
        scaled_pixmap = pixmap.scaled(self.image_display_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_display_label.setPixmap(scaled_pixmap)

    # ... (Event handlers like _on_image_mouse_move, _on_image_mouse_press, _on_image_mouse_wheel) ...
    # ... (Mask editing logic: edit_mask, draw_mask, fill_mask) ...
    # ... (Save, open_directory_dialog, open_..._window, model loading) ...

    def save_current_changes(self, event=None): # event is None if called directly
        # ... (original save logic) ...
        if 0 <= self.current_image_index < len(self.image_rel_paths):
            image_rel_path = self.image_rel_paths[self.current_image_index]
            base, _ = os.path.splitext(image_rel_path)
            prompt_path = os.path.join(self.dir, base + ".txt")
            mask_path = os.path.join(self.dir, base + "-masklabel.png")

            try:
                if self.prompt_input:
                    with open(prompt_path, "w", encoding='utf-8') as f:
                        f.write(self.prompt_input.text())
                if self.pil_mask:
                    self.pil_mask.save(mask_path)
                print(f"Saved changes for {image_rel_path}")
            except Exception as e:
                print(f"Error saving changes: {e}")
                # QMessageBox.warning(self, "Save Error", f"Could not save changes: {e}")


    def open_directory_dialog(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Open Directory", self.dir)
        if new_dir:
            self.load_directory(new_dir, self.include_subdirs_checkbox.isChecked())

    def print_help_to_console(self): print(self.help_text)

    # --- Shortcut Handlers ---
    def previous_image_shortcut(self):
        if len(self.image_rel_paths) > 0 and (self.current_image_index - 1) >= 0:
            self.switch_image(self.current_image_index - 1)
    def next_image_shortcut(self):
        if len(self.image_rel_paths) > 0 and (self.current_image_index + 1) < len(self.image_rel_paths):
            self.switch_image(self.current_image_index + 1)
    def toggle_mask_display_shortcut(self):
        self.display_only_mask = not self.display_only_mask
        self.refresh_image_display()
        
    def set_mask_editing_mode(self, mode:str, button_pressed: QPushButton):
        self.mask_editing_mode = mode
        if mode == 'draw':
            self.draw_mode_button.setChecked(True)
            self.fill_mode_button.setChecked(False)
        elif mode == 'fill':
            self.draw_mode_button.setChecked(False)
            self.fill_mode_button.setChecked(True)


    # --- Stubs for dialogs and complex event handling ---
    def open_mask_window(self): print("TODO: Open GenerateMasksWindow")
    def open_caption_window(self): print("TODO: Open GenerateCaptionsWindow")
    def open_in_explorer(self):
        if 0 <= self.current_image_index < len(self.image_rel_paths):
            try:
                image_path = os.path.realpath(os.path.join(self.dir, self.image_rel_paths[self.current_image_index]))
                if platform.system() == "Windows":
                    subprocess.Popen(f'explorer /select,"{image_path}"')
                elif platform.system() == "Darwin": # macOS
                    subprocess.Popen(['open', '-R', image_path])
                else: # Linux
                    subprocess.Popen(['xdg-open', os.path.dirname(image_path)])
            except Exception as e: print(f"Error opening in explorer: {e}")

    # --- Mask Editing (Simplified stubs, needs full port of original logic) ---
    def _on_image_mouse_move(self, event: QMouseEvent):
        if self.enable_mask_editing_checkbox and self.enable_mask_editing_checkbox.isChecked():
            self.mask_draw_x = event.position().x() 
            self.mask_draw_y = event.position().y()
            # If mouse button is held, continue drawing line (original code implies this)
            if event.buttons() & Qt.MouseButton.LeftButton or event.buttons() & Qt.MouseButton.RightButton:
                 self._process_mask_interaction(event, is_move=True)


    def _on_image_mouse_press(self, event: QMouseEvent):
        if self.enable_mask_editing_checkbox and self.enable_mask_editing_checkbox.isChecked():
            self.mask_draw_x = event.position().x()
            self.mask_draw_y = event.position().y()
            self._process_mask_interaction(event, is_move=False)

    def _on_image_mouse_wheel(self, event: QWheelEvent):
        if self.enable_mask_editing_checkbox and self.enable_mask_editing_checkbox.isChecked():
            delta = event.angleDelta().y()
            multiplier = 1.0 + (delta / 120 * 0.1) # Adjust sensitivity
            self.mask_draw_radius = max(0.0025, min(self.mask_draw_radius * multiplier, 0.5))
            # print(f"New brush radius: {self.mask_draw_radius:.4f}") # For debugging

    def _process_mask_interaction(self, event: QMouseEvent, is_move: bool):
        if not self.pil_image: return

        # Convert QPointF to image coordinates
        # This needs to account for the scaled pixmap vs original image size
        # and the position of the pixmap within the QLabel
        
        pixmap = self.image_display_label.pixmap()
        if not pixmap or pixmap.isNull(): return

        # Calculate the actual display rect of the pixmap within the QLabel (due to KeepAspectRatio)
        label_size = self.image_display_label.size()
        pixmap_size = pixmap.size()
        
        scaled_pixmap_size = pixmap_size.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio)

        offset_x = (label_size.width() - scaled_pixmap_size.width()) / 2
        offset_y = (label_size.height() - scaled_pixmap_size.height()) / 2

        # Mouse position relative to the scaled pixmap
        img_coord_x_f = event.position().x() - offset_x
        img_coord_y_f = event.position().y() - offset_y

        # Convert to original image coordinates
        if scaled_pixmap_size.width() == 0 or scaled_pixmap_size.height() == 0: return # Avoid division by zero
        
        orig_x = int((img_coord_x_f / scaled_pixmap_size.width()) * self.image_width)
        orig_y = int((img_coord_y_f / scaled_pixmap_size.height()) * self.image_height)

        # For line drawing, we need previous point in original image coordinates
        # This part is tricky because self.mask_draw_x/y were in display label coords
        # Let's assume for now self.prev_orig_x, self.prev_orig_y are stored from last event
        
        prev_orig_x = getattr(self, 'prev_orig_x', orig_x)
        prev_orig_y = getattr(self, 'prev_orig_y', orig_y)

        is_left = bool(event.buttons() & Qt.MouseButton.LeftButton)
        is_right = bool(event.buttons() & Qt.MouseButton.RightButton)

        if self.mask_editing_mode == 'draw':
            self.draw_mask_on_pil(prev_orig_x if is_move else orig_x, 
                                  prev_orig_y if is_move else orig_y, 
                                  orig_x, orig_y, is_left, is_right)
        elif self.mask_editing_mode == 'fill' and not is_move: # Fill only on press
            self.fill_mask_on_pil(orig_x, orig_y, is_left, is_right)
            
        self.prev_orig_x = orig_x
        self.prev_orig_y = orig_y


    def draw_mask_on_pil(self, start_x, start_y, end_x, end_y, is_left, is_right):
        # ... (Ported logic from original draw_mask, operating on self.pil_mask) ...
        color_tuple = None; adding_to_mask = True
        if is_left:
            try: alpha = float(self.mask_editing_alpha_input.text())
            except ValueError: alpha = 1.0
            rgb_val = int(max(0.0, min(alpha, 1.0)) * 255)
            color_tuple = (rgb_val, rgb_val, rgb_val)
        elif is_right:
            color_tuple = (0,0,0); adding_to_mask = False
        
        if color_tuple:
            if self.pil_mask is None:
                self.pil_mask = Image.new('RGB', (self.image_width, self.image_height), (0,0,0) if adding_to_mask else (255,255,255))
            
            radius = int(self.mask_draw_radius * max(self.pil_mask.width, self.pil_mask.height))
            draw = ImageDraw.Draw(self.pil_mask)
            if start_x == end_x and start_y == end_y: # Single click
                 draw.ellipse((start_x - radius, start_y - radius, start_x + radius, start_y + radius), fill=color_tuple, outline=None)
            else: # Drag
                draw.line(((start_x, start_y), (end_x, end_y)), fill=color_tuple, width=radius * 2 + 1)
                # Ellipses at ends for rounded strokes
                draw.ellipse((start_x - radius, start_y - radius, start_x + radius, start_y + radius), fill=color_tuple, outline=None)
                draw.ellipse((end_x - radius, end_y - radius, end_x + radius, end_y + radius), fill=color_tuple, outline=None)
            del draw
            self.refresh_image_display()


    def fill_mask_on_pil(self, x, y, is_left, is_right):
        # ... (Ported logic from original fill_mask, operating on self.pil_mask) ...
        if not (0 <= x < self.image_width and 0 <= y < self.image_height): return

        color_tuple = None; adding_to_mask = True
        if is_left:
            try: alpha = float(self.mask_editing_alpha_input.text())
            except ValueError: alpha = 1.0
            rgb_val = int(max(0.0, min(alpha, 1.0)) * 255)
            color_tuple = (rgb_val, rgb_val, rgb_val)
        elif is_right:
            color_tuple = (0,0,0); adding_to_mask = False

        if color_tuple:
            if self.pil_mask is None:
                self.pil_mask = Image.new('RGB', (self.image_width, self.image_height), (0,0,0) if adding_to_mask else (255,255,255))
            
            # QImage conversion for floodFill is complex with PIL. Using OpenCV for floodFill.
            # Ensure pil_mask is 8-bit single channel or 3-channel for cv2.floodFill
            cv_mask = np.array(self.pil_mask.convert('RGB')) 
            # Get current color at seed point to define tolerance or target for replacement
            # seed_color = tuple(cv_mask[y,x]) # For specific color replacement
            # Floodfill in OpenCV often needs a mask for the operation itself if not filling the source.
            # For simplicity, let's assume we are filling based on connectivity from seed point.
            h, w = cv_mask.shape[:2]
            flood_mask = np.zeros((h + 2, w + 2), np.uint8) # Mask for floodFill needs to be 2px larger
            
            # Heuristic for lo/hi diff for floodfill. Can be made adjustable.
            # If filling a black area with white, seed_color is (0,0,0), target is (255,255,255)
            # If color_tuple is (0,0,0), we are erasing, so seed point might be non-black.
            # This part needs careful thought on how flood fill should behave.
            # Let's assume a simple fill: if it's very different from target, fill.
            # Or, fill if it's similar to what's under the seed.
            # For now, a generic approach:
            diff = (10,10,10) # Tolerance for color difference
            cv2.floodFill(cv_mask, flood_mask, (x,y), color_tuple, loDiff=diff, upDiff=diff)
            self.pil_mask = Image.fromarray(cv_mask, 'RGB')
            self.refresh_image_display()

    # Model loading stubs (original logic is mostly non-UI)
    def load_masking_model(self, model_name_str: str): print(f"TODO: Load masking model {model_name_str}")
    def load_captioning_model(self, model_name_str: str): print(f"TODO: Load captioning model {model_name_str}")

    def keyPressEvent(self, event: QKeyEvent):
        # This is a basic way to handle global key presses for the dialog
        # More specific handling might be needed if focus is on certain widgets
        if event.key() == Qt.Key.Key_Up and self.prompt_input and not self.prompt_input.hasFocus():
            self.previous_image_shortcut()
        elif event.key() == Qt.Key.Key_Down and self.prompt_input and not self.prompt_input.hasFocus():
            self.next_image_shortcut()
        else:
            super().keyPressEvent(event) # Important for other default processing

    def accept(self): # Override if custom close/save logic is needed on OK
        self.save_current_changes() # Save current before closing
        super().accept()

    def reject(self): # Override if custom logic is needed on Cancel/Esc
        super().reject()

[end of modules/ui/CaptionUI.py]
