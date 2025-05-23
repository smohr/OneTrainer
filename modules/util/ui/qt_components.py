from typing import Any, Callable, List, Tuple, Optional, Union

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QHBoxLayout, QVBoxLayout, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QObject # QObject for UIState if it's passed directly
from PySide6.QtGui import QValidator # For input validation if needed

from modules.util.ui.UIState import UIState # Assuming UIState is QObject based

# --- Basic Label ---
def create_label(parent_widget: Optional[QWidget], text: str, tooltip: str = None) -> QLabel:
    """Creates a QLabel."""
    label = QLabel(text, parent_widget)
    if tooltip:
        label.setToolTip(tooltip)
    return label

# --- QLineEdit for various data types ---
def create_entry(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path: str,
    label_text: Optional[str] = None,
    tooltip: Optional[str] = None,
    default_value: Any = "",
    value_type: type = str, # str, int, float
    validator: Optional[QValidator] = None,
    label_on_left: bool = True
) -> QWidget:
    """
    Creates a QLineEdit with an optional QLabel, connected to UIState for two-way binding.
    Returns a container QWidget holding the label (if any) and the QLineEdit.
    """
    container = QWidget(parent_widget)
    if label_on_left:
        layout = QHBoxLayout(container)
    else:
        layout = QVBoxLayout(container)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(5)

    if label_text:
        label = create_label(container, label_text, tooltip if not tooltip else None) # Tooltip on label if entry doesn't have its own
        layout.addWidget(label)

    line_edit = QLineEdit(container)
    if tooltip:
        line_edit.setToolTip(tooltip)
    if validator:
        line_edit.setValidator(validator)
    
    line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # Set initial value
    current_value = ui_state.get_var(key_path, default_value)
    line_edit.setText(str(current_value if current_value is not None else ""))

    # Update UIState when QLineEdit changes
    def on_editing_finished():
        new_text = line_edit.text()
        try:
            if value_type == int:
                new_val = int(new_text) if new_text else (None if ui_state.obj.nullables.get(key_path.split('.')[-1], False) else 0)
            elif value_type == float:
                new_val = float(new_text) if new_text else (None if ui_state.obj.nullables.get(key_path.split('.')[-1], False) else 0.0)
            else: # str
                new_val = new_text
            ui_state.set_var(key_path, new_val)
        except ValueError:
            # Revert to current state value if conversion fails
            reverted_value = ui_state.get_var(key_path, default_value)
            line_edit.setText(str(reverted_value if reverted_value is not None else ""))

    line_edit.editingFinished.connect(on_editing_finished)

    # Update QLineEdit when UIState changes
    def update_widget_from_state(new_value: Any):
        current_widget_text = line_edit.text()
        new_value_str = str(new_value if new_value is not None else "")
        if current_widget_text != new_value_str:
            line_edit.setText(new_value_str)

    ui_state.track_variable(key_path, update_widget_from_state)

    layout.addWidget(line_edit)
    if label_on_left:
        layout.setStretchFactor(line_edit, 1) # Allow line_edit to take more space

    return container

# --- QCheckBox ---
def create_switch(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path: str,
    label_text: str, # Label is part of QCheckBox text
    tooltip: Optional[str] = None
) -> QCheckBox:
    """Creates a QCheckBox connected to UIState for two-way binding."""
    check_box = QCheckBox(label_text, parent_widget)
    if tooltip:
        check_box.setToolTip(tooltip)

    # Set initial value
    current_value = ui_state.get_var(key_path, False)
    check_box.setChecked(bool(current_value))

    # Update UIState when QCheckBox changes
    check_box.toggled.connect(lambda checked: ui_state.set_var(key_path, checked))

    # Update QCheckBox when UIState changes
    def update_widget_from_state(new_value: Any):
        new_bool_value = bool(new_value)
        if check_box.isChecked() != new_bool_value:
            check_box.setChecked(new_bool_value)
    
    ui_state.track_variable(key_path, update_widget_from_state)
    
    return check_box

# --- QComboBox for key-value options ---
def create_options_kv(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path: str,
    items: List[Tuple[str, Any]], # List of (display_text, data_value)
    label_text: Optional[str] = None,
    tooltip: Optional[str] = None,
    label_on_left: bool = True
) -> QWidget:
    """
    Creates a QComboBox with an optional QLabel, connected to UIState.
    Items are (display_text, data_value) tuples.
    Returns a container QWidget.
    """
    container = QWidget(parent_widget)
    if label_on_left:
        layout = QHBoxLayout(container)
    else:
        layout = QVBoxLayout(container)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(5)

    if label_text:
        label = create_label(container, label_text, tooltip if not tooltip else None)
        layout.addWidget(label)

    combo_box = QComboBox(container)
    if tooltip:
        combo_box.setToolTip(tooltip)
    combo_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # Populate items and set initial value
    current_data_value = ui_state.get_var(key_path)
    selected_idx = -1
    for idx, (text, data) in enumerate(items):
        combo_box.addItem(text, userData=data)
        if data == current_data_value:
            selected_idx = idx
    
    if selected_idx != -1:
        combo_box.setCurrentIndex(selected_idx)
    elif items: # Default to first item if current value not found and list is not empty
        combo_box.setCurrentIndex(0)
        # Optionally, update ui_state to this default if desired:
        # ui_state.set_var(key_path, items[0][1]) 

    # Update UIState when QComboBox changes
    def on_index_changed(index: int):
        if index >= 0:
            data_value = combo_box.itemData(index)
            ui_state.set_var(key_path, data_value)
    combo_box.currentIndexChanged.connect(on_index_changed)

    # Update QComboBox when UIState changes
    def update_widget_from_state(new_data_value: Any):
        for i in range(combo_box.count()):
            if combo_box.itemData(i) == new_data_value:
                if combo_box.currentIndex() != i:
                    combo_box.setCurrentIndex(i)
                return
        # If new_data_value not found, deselect or select first? For now, do nothing or select first.
        if combo_box.count() > 0:
             if combo_box.currentIndex() != 0 : combo_box.setCurrentIndex(0) # Default to first
        
    ui_state.track_variable(key_path, update_widget_from_state)

    layout.addWidget(combo_box)
    if label_on_left:
        layout.setStretchFactor(combo_box, 1)
        
    return container

# --- File/Directory Entry (QLineEdit + QPushButton) ---
def _create_file_or_dir_entry(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path: str,
    label_text: Optional[str] = None,
    tooltip: Optional[str] = None,
    get_path_dialog_fn: Callable[..., Tuple[str, str]], # e.g., QFileDialog.getOpenFileName
    dialog_title: str = "Select Path",
    file_filter: str = "All Files (*)",
    label_on_left: bool = True
) -> QWidget:
    """Internal helper for file and directory entries."""
    container = QWidget(parent_widget)
    if label_on_left:
        layout = QHBoxLayout(container)
    else:
        layout = QVBoxLayout(container)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(5)

    if label_text:
        label = create_label(container, label_text, tooltip if not tooltip else None)
        layout.addWidget(label)

    path_edit = QLineEdit(container)
    if tooltip:
        path_edit.setToolTip(tooltip)
    path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    current_value = ui_state.get_var(key_path, "")
    path_edit.setText(str(current_value if current_value is not None else ""))

    def on_editing_finished():
        ui_state.set_var(key_path, path_edit.text())
    path_edit.editingFinished.connect(on_editing_finished)

    def update_widget_from_state(new_value: Any):
        new_path_str = str(new_value if new_value is not None else "")
        if path_edit.text() != new_path_str:
            path_edit.setText(new_path_str)
    ui_state.track_variable(key_path, update_widget_from_state)

    browse_button = QPushButton("Browse", container)
    def open_dialog():
        # Use self of container or a passed parent for the dialog if needed
        # For QFileDialog, parent is often passed for modality and positioning.
        # Here, 'container' is the parent of the button.
        current_path = path_edit.text()
        if os.path.isdir(current_path): initial_dir = current_path
        elif os.path.isfile(current_path): initial_dir = os.path.dirname(current_path)
        else: initial_dir = current_path # Or os.getcwd()
        
        if get_path_dialog_fn == QFileDialog.getExistingDirectory:
            selected_path = get_path_dialog_fn(container, dialog_title, initial_dir)
        else: # For getOpenFileName, getSaveFileName
            selected_path, _ = get_path_dialog_fn(container, dialog_title, initial_dir, file_filter)

        if selected_path:
            path_edit.setText(selected_path)
            on_editing_finished() # Trigger UIState update

    browse_button.clicked.connect(open_dialog)

    sub_layout = QHBoxLayout() # Layout for path_edit and browse_button
    sub_layout.setContentsMargins(0,0,0,0)
    sub_layout.setSpacing(5)
    sub_layout.addWidget(path_edit, 1) # Line edit takes expanding space
    sub_layout.addWidget(browse_button)
    
    layout.addLayout(sub_layout)
    if label_on_left:
        layout.setStretchFactor(sub_layout_container_if_any_or_path_edit, 1) # Adjust stretch logic here

    return container

def create_file_entry(
    parent_widget: Optional[QWidget], ui_state: UIState, key_path: str,
    label_text: Optional[str] = None, tooltip: Optional[str] = None,
    dialog_title: str = "Select File", file_filter: str = "All Files (*)",
    is_save_dialog: bool = False, label_on_left: bool = True
) -> QWidget:
    dialog_fn = QFileDialog.getSaveFileName if is_save_dialog else QFileDialog.getOpenFileName
    return _create_file_or_dir_entry(
        parent_widget, ui_state, key_path, label_text, tooltip,
        dialog_fn, dialog_title, file_filter, label_on_left
    )

def create_dir_entry(
    parent_widget: Optional[QWidget], ui_state: UIState, key_path: str,
    label_text: Optional[str] = None, tooltip: Optional[str] = None,
    dialog_title: str = "Select Directory", label_on_left: bool = True
) -> QWidget:
    return _create_file_or_dir_entry(
        parent_widget, ui_state, key_path, label_text, tooltip,
        QFileDialog.getExistingDirectory, dialog_title, "", label_on_left # No filter for directory
    )

# --- Time Entry (QLineEdit for value, QComboBox for unit) ---
def create_time_entry(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path_value: str,
    key_path_unit: str,
    label_text: Optional[str] = None,
    tooltip: Optional[str] = None,
    default_value: int = 0,
    default_unit: str = "steps",
    time_units: Optional[List[Tuple[str, str]]] = None, # e.g., [("Steps", "steps"), ("Epochs", "epochs")]
    label_on_left: bool = True
) -> QWidget:
    """
    Creates a time entry widget (value + unit) with an optional QLabel.
    Returns a container QWidget.
    """
    if time_units is None:
        time_units = [("Steps", "steps"), ("Epochs", "epochs"), ("Seconds", "seconds")]

    container = QWidget(parent_widget)
    if label_on_left:
        layout = QHBoxLayout(container)
    else:
        layout = QVBoxLayout(container)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(5)

    if label_text:
        label = create_label(container, label_text, tooltip) # Tooltip on main label
        layout.addWidget(label)

    # Container for the entry and combo
    value_unit_container = QWidget(container)
    value_unit_layout = QHBoxLayout(value_unit_container)
    value_unit_layout.setContentsMargins(0,0,0,0)
    value_unit_layout.setSpacing(3)

    # Value QLineEdit
    value_edit = QLineEdit(value_unit_container)
    value_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    initial_value = ui_state.get_var(key_path_value, default_value)
    value_edit.setText(str(initial_value if initial_value is not None else ""))

    def on_value_editing_finished():
        try:
            val = int(value_edit.text()) if value_edit.text() else None
            ui_state.set_var(key_path_value, val)
        except ValueError:
            reverted_val = ui_state.get_var(key_path_value, default_value)
            value_edit.setText(str(reverted_val if reverted_val is not None else ""))
    value_edit.editingFinished.connect(on_value_editing_finished)

    def update_value_widget(new_val: Any):
        new_val_str = str(new_val if new_val is not None else "")
        if value_edit.text() != new_val_str: value_edit.setText(new_val_str)
    ui_state.track_variable(key_path_value, update_value_widget)
    value_unit_layout.addWidget(value_edit, 2) # Stretch factor for value

    # Unit QComboBox
    unit_combo = QComboBox(value_unit_container)
    unit_combo.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
    
    current_unit_data = ui_state.get_var(key_path_unit, default_unit)
    sel_idx = -1
    for idx, (text, data) in enumerate(time_units):
        unit_combo.addItem(text, userData=data)
        if data == current_unit_data: sel_idx = idx
    if sel_idx != -1: unit_combo.setCurrentIndex(sel_idx)
    elif time_units : unit_combo.setCurrentIndex(0) # Default to first

    unit_combo.currentIndexChanged.connect(
        lambda idx: ui_state.set_var(key_path_unit, unit_combo.itemData(idx)) if idx >=0 else None
    )

    def update_unit_widget(new_data_val: Any):
        for i in range(unit_combo.count()):
            if unit_combo.itemData(i) == new_data_val:
                if unit_combo.currentIndex() != i: unit_combo.setCurrentIndex(i)
                return
        if unit_combo.count() > 0 and unit_combo.currentIndex() != 0: unit_combo.setCurrentIndex(0)
    ui_state.track_variable(key_path_unit, update_unit_widget)
    value_unit_layout.addWidget(unit_combo, 1) # Stretch factor for unit

    layout.addWidget(value_unit_container)
    if label_on_left:
        layout.setStretchFactor(value_unit_container, 1)

    return container

# --- Simple QPushButton ---
def create_button(
    parent_widget: Optional[QWidget],
    text: str,
    command: Optional[Callable] = None,
    tooltip: Optional[str] = None,
    fixed_width: Optional[int] = None
) -> QPushButton:
    """Creates a QPushButton."""
    button = QPushButton(text, parent_widget)
    if command:
        button.clicked.connect(command)
    if tooltip:
        button.setToolTip(tooltip)
    if fixed_width:
        button.setFixedWidth(fixed_width)
    return button

# TODO: Add create_options_adv (ComboBox + Button) if needed as a common component.
# TODO: Add create_text_edit for multi-line text if needed.```python
from typing import Any, Callable, List, Tuple, Optional, Union

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton,
    QHBoxLayout, QVBoxLayout, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QObject # QObject for UIState if it's passed directly
from PySide6.QtGui import QValidator, QDoubleValidator, QIntValidator # For input validation if needed
import os # For path operations in file dialogs

from modules.util.ui.UIState import UIState # Assuming UIState is QObject based

# --- Basic Label ---
def create_label(parent_widget: Optional[QWidget], text: str, tooltip: str = None, alignment: Optional[Qt.AlignmentFlag] = None) -> QLabel:
    """Creates a QLabel."""
    label = QLabel(text, parent_widget)
    if tooltip:
        label.setToolTip(tooltip)
    if alignment:
        label.setAlignment(alignment)
    return label

# --- QLineEdit for various data types ---
def create_entry(
    parent_widget: Optional[QWidget], # The QWidget this component will be part of (for layout)
    ui_state: UIState,
    key_path: str,
    label_text: Optional[str] = None,
    tooltip: Optional[str] = None,
    default_value: Any = "",
    value_type: type = str, # str, int, float
    validator: Optional[QValidator] = None,
    label_on_left: bool = True,
    placeholder_text: Optional[str] = None
) -> QWidget:
    """
    Creates a QLineEdit with an optional QLabel, connected to UIState for two-way binding.
    Returns a container QWidget holding the label (if any) and the QLineEdit.
    """
    container = QWidget(parent_widget) # Parent for the container itself
    if label_on_left:
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0,0,0,0) # No margins for the inner container
        layout.setSpacing(5)
    else:
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0,0,0,0) # No margins for the inner container
        layout.setSpacing(2)


    actual_tooltip = tooltip or label_text # Use label as tooltip if no specific tooltip

    if label_text:
        label = create_label(container, label_text, actual_tooltip if not label_on_left else None)
        layout.addWidget(label)

    line_edit = QLineEdit(container)
    if actual_tooltip:
        line_edit.setToolTip(actual_tooltip)
    if placeholder_text:
        line_edit.setPlaceholderText(placeholder_text)

    if validator:
        line_edit.setValidator(validator)
    elif value_type == int:
        line_edit.setValidator(QIntValidator(line_edit))
    elif value_type == float:
        line_edit.setValidator(QDoubleValidator(line_edit))
    
    line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # Set initial value
    # Try to get nullable from BaseConfig if obj is one
    is_nullable_in_config = False
    obj_for_config = ui_state.obj
    path_parts = key_path.split('.')
    for part in path_parts[:-1]: # Navigate to parent object
        if isinstance(obj_for_config, BaseConfig) and hasattr(obj_for_config, part):
            obj_for_config = getattr(obj_for_config, part)
        elif isinstance(obj_for_config, dict) and part in obj_for_config:
            obj_for_config = obj_for_config[part]
        else: # Path broken or not a BaseConfig
            obj_for_config = None
            break
    if isinstance(obj_for_config, BaseConfig):
        is_nullable_in_config = obj_for_config.nullables.get(path_parts[-1], False)
    
    current_value = ui_state.get_var(key_path, default_value)
    line_edit.setText(str(current_value if current_value is not None else ""))

    # Update UIState when QLineEdit changes
    def on_editing_finished():
        new_text = line_edit.text()
        try:
            final_value: Any
            if not new_text.strip() and is_nullable_in_config: # Handle empty string for nullable types
                final_value = None
            elif value_type == int:
                final_value = int(new_text)
            elif value_type == float:
                final_value = float(new_text)
            else: # str
                final_value = new_text
            ui_state.set_var(key_path, final_value)
        except ValueError:
            reverted_value = ui_state.get_var(key_path, default_value)
            line_edit.setText(str(reverted_value if reverted_value is not None else ""))

    line_edit.editingFinished.connect(on_editing_finished)

    # Update QLineEdit when UIState changes
    def update_widget_from_state(new_value: Any):
        new_value_str = str(new_value if new_value is not None else "")
        if line_edit.text() != new_value_str:
            line_edit.setText(new_value_str)

    ui_state.track_variable(key_path, update_widget_from_state)

    layout.addWidget(line_edit)
    if label_on_left and label_text: # Ensure label exists for stretch factor to make sense
        layout.setStretchFactor(line_edit, 1)
    elif not label_text: # If no label, line_edit is the only main thing
        layout.setStretchFactor(line_edit,1)


    return container

# --- QCheckBox ---
def create_switch(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path: str,
    label_text: str, 
    tooltip: Optional[str] = None
) -> QCheckBox:
    """Creates a QCheckBox connected to UIState for two-way binding."""
    check_box = QCheckBox(label_text, parent_widget)
    if tooltip:
        check_box.setToolTip(tooltip)

    current_value = ui_state.get_var(key_path, False)
    check_box.setChecked(bool(current_value))

    check_box.toggled.connect(lambda checked: ui_state.set_var(key_path, checked))

    def update_widget_from_state(new_value: Any):
        new_bool_value = bool(new_value)
        if check_box.isChecked() != new_bool_value:
            check_box.setChecked(new_bool_value)
    
    ui_state.track_variable(key_path, update_widget_from_state)
    
    return check_box

# --- QComboBox for key-value options ---
def create_options_kv(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path: str,
    items: List[Tuple[str, Any]], 
    label_text: Optional[str] = None,
    tooltip: Optional[str] = None,
    on_change_command: Optional[Callable[[Any], None]] = None, # Command to call with new data_value
    label_on_left: bool = True
) -> QWidget:
    """
    Creates a QComboBox with an optional QLabel, connected to UIState.
    Items are (display_text, data_value) tuples.
    Returns a container QWidget.
    """
    container = QWidget(parent_widget)
    if label_on_left:
        layout = QHBoxLayout(container)
    else:
        layout = QVBoxLayout(container)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(5)
    
    actual_tooltip = tooltip or label_text

    if label_text:
        label = create_label(container, label_text, actual_tooltip if not label_on_left else None)
        layout.addWidget(label)

    combo_box = QComboBox(container)
    if actual_tooltip:
        combo_box.setToolTip(actual_tooltip)
    combo_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    current_data_value = ui_state.get_var(key_path)
    selected_idx = -1
    for idx, (text, data) in enumerate(items):
        combo_box.addItem(text, userData=data)
        if data == current_data_value:
            selected_idx = idx
    
    if selected_idx != -1:
        combo_box.setCurrentIndex(selected_idx)
    elif items: 
        combo_box.setCurrentIndex(0)
        # ui_state.set_var(key_path, items[0][1]) # Optionally set initial state if not found

    def on_index_changed(index: int):
        if index >= 0:
            data_value = combo_box.itemData(index)
            ui_state.set_var(key_path, data_value)
            if on_change_command:
                on_change_command(data_value)
    combo_box.currentIndexChanged.connect(on_index_changed)

    def update_widget_from_state(new_data_value: Any):
        for i in range(combo_box.count()):
            if combo_box.itemData(i) == new_data_value:
                if combo_box.currentIndex() != i:
                    combo_box.setCurrentIndex(i)
                return
        if combo_box.count() > 0 and current_data_value is None and new_data_value is not None : # if initial value was None, but now we have one
             pass # Covered by loop or default below
        elif combo_box.count() > 0 and combo_box.currentIndex() != 0 : # Default to first if value not found
            # This might be problematic if the new_data_value is legitimately not in items and shouldn't default
            # print(f"Warning: Value {new_data_value} for {key_path} not in ComboBox items. Defaulting.")
            # combo_box.setCurrentIndex(0) # Avoid this unless sure
            pass

    ui_state.track_variable(key_path, update_widget_from_state)

    layout.addWidget(combo_box)
    if label_on_left and label_text:
        layout.setStretchFactor(combo_box, 1)
    elif not label_text:
        layout.setStretchFactor(combo_box, 1)
        
    return container

# --- File/Directory Entry (QLineEdit + QPushButton) ---
def _create_file_or_dir_entry_internal(
    parent_widget_for_dialog: QWidget, # Parent for QFileDialog
    ui_state: UIState,
    key_path: str,
    get_path_dialog_fn: Callable[..., Union[str, Tuple[str, str]]], 
    dialog_title: str,
    file_filter: Optional[str] = None # Made optional
) -> QWidget:
    """Internal helper for file and directory entries; returns QLineEdit and QPushButton."""
    path_edit = QLineEdit()
    path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    current_value = ui_state.get_var(key_path, "")
    path_edit.setText(str(current_value if current_value is not None else ""))

    def on_editing_finished():
        ui_state.set_var(key_path, path_edit.text())
    path_edit.editingFinished.connect(on_editing_finished)

    def update_widget_from_state(new_value: Any):
        new_path_str = str(new_value if new_value is not None else "")
        if path_edit.text() != new_path_str:
            path_edit.setText(new_path_str)
    ui_state.track_variable(key_path, update_widget_from_state)

    browse_button = QPushButton("Browse")
    def open_dialog():
        current_path = path_edit.text()
        initial_dir = os.getcwd()
        if current_path:
            if os.path.isdir(current_path): initial_dir = current_path
            elif os.path.isfile(current_path): initial_dir = os.path.dirname(current_path)
        
        selected_path_or_tuple: Union[str, Tuple[str,str]]
        if get_path_dialog_fn == QFileDialog.getExistingDirectory:
            selected_path_or_tuple = get_path_dialog_fn(parent_widget_for_dialog, dialog_title, initial_dir)
        else: # For getOpenFileName, getSaveFileName
            selected_path_or_tuple = get_path_dialog_fn(parent_widget_for_dialog, dialog_title, initial_dir, file_filter if file_filter else "All Files (*)")

        selected_path = ""
        if isinstance(selected_path_or_tuple, tuple):
            selected_path = selected_path_or_tuple[0]
        else:
            selected_path = selected_path_or_tuple

        if selected_path:
            path_edit.setText(selected_path)
            on_editing_finished() 

    browse_button.clicked.connect(open_dialog)
    return path_edit, browse_button


def create_file_dir_entry(
    parent_widget: Optional[QWidget], ui_state: UIState, key_path: str,
    dialog_type: str, # "file_open", "file_save", "directory"
    label_text: Optional[str] = None, tooltip: Optional[str] = None,
    dialog_title: str = "Select Path", file_filter: str = "All Files (*)",
    label_on_left: bool = True
) -> QWidget:
    container = QWidget(parent_widget)
    if label_on_left:
        layout = QHBoxLayout(container)
    else:
        layout = QVBoxLayout(container)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(5)
    
    actual_tooltip = tooltip or label_text

    if label_text:
        label = create_label(container, label_text, actual_tooltip if not label_on_left else None)
        layout.addWidget(label)

    dialog_fn: Callable
    if dialog_type == "file_open": dialog_fn = QFileDialog.getOpenFileName
    elif dialog_type == "file_save": dialog_fn = QFileDialog.getSaveFileName
    elif dialog_type == "directory": dialog_fn = QFileDialog.getExistingDirectory
    else: raise ValueError("Invalid dialog_type for create_file_dir_entry")

    path_edit, browse_button = _create_file_or_dir_entry_internal(
        container, ui_state, key_path, dialog_fn, dialog_title, file_filter if dialog_type != "directory" else None
    )
    if actual_tooltip: path_edit.setToolTip(actual_tooltip)


    sub_layout = QHBoxLayout() 
    sub_layout.setContentsMargins(0,0,0,0)
    sub_layout.setSpacing(5)
    sub_layout.addWidget(path_edit, 1) 
    sub_layout.addWidget(browse_button)
    
    layout.addLayout(sub_layout)
    if label_on_left and label_text:
        layout.setStretchFactor(container.layout().itemAt(1).layout(), 1) # Stretch the sub_layout
    elif not label_text:
         layout.setStretchFactor(container.layout().itemAt(0).layout(), 1)


    return container


# --- Time Entry (QLineEdit for value, QComboBox for unit) ---
def create_time_entry(
    parent_widget: Optional[QWidget],
    ui_state: UIState,
    key_path_value: str,
    key_path_unit: str,
    label_text: Optional[str] = None,
    tooltip: Optional[str] = None,
    default_value: int = 0,
    default_unit: str = "steps", # This should be one of the data values in time_units
    time_units: Optional[List[Tuple[str, str]]] = None,
    label_on_left: bool = True
) -> QWidget:
    if time_units is None:
        time_units = [("Steps", "steps"), ("Epochs", "epochs"), ("Seconds", "seconds")]

    container = QWidget(parent_widget)
    if label_on_left: layout = QHBoxLayout(container)
    else: layout = QVBoxLayout(container)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(5)
    
    actual_tooltip = tooltip or label_text

    if label_text:
        label = create_label(container, label_text, actual_tooltip if not label_on_left else None)
        layout.addWidget(label)

    value_unit_container = QWidget(container) # Inner container for value and unit
    value_unit_layout = QHBoxLayout(value_unit_container)
    value_unit_layout.setContentsMargins(0,0,0,0)
    value_unit_layout.setSpacing(3)
    if actual_tooltip: value_unit_container.setToolTip(actual_tooltip)


    # Value QLineEdit
    value_edit = QLineEdit(value_unit_container)
    value_edit.setValidator(QIntValidator()) # Assuming time value is int
    value_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    initial_value = ui_state.get_var(key_path_value, default_value)
    value_edit.setText(str(initial_value if initial_value is not None else ""))

    def on_value_editing_finished():
        try:
            val = int(value_edit.text()) if value_edit.text().strip() else None
            ui_state.set_var(key_path_value, val)
        except ValueError:
            reverted_val = ui_state.get_var(key_path_value, default_value)
            value_edit.setText(str(reverted_val if reverted_val is not None else ""))
    value_edit.editingFinished.connect(on_value_editing_finished)

    def update_value_widget(new_val: Any):
        new_val_str = str(new_val if new_val is not None else "")
        if value_edit.text() != new_val_str: value_edit.setText(new_val_str)
    ui_state.track_variable(key_path_value, update_value_widget)
    value_unit_layout.addWidget(value_edit, 2) 

    # Unit QComboBox
    unit_combo = QComboBox(value_unit_container)
    unit_combo.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
    
    current_unit_data = ui_state.get_var(key_path_unit, default_unit)
    sel_idx = -1
    for idx, (text, data) in enumerate(time_units):
        unit_combo.addItem(text, userData=data)
        if data == current_unit_data: sel_idx = idx
    if sel_idx != -1: unit_combo.setCurrentIndex(sel_idx)
    elif time_units: unit_combo.setCurrentIndex(0) 

    unit_combo.currentIndexChanged.connect(
        lambda idx: ui_state.set_var(key_path_unit, unit_combo.itemData(idx)) if idx >=0 else None
    )

    def update_unit_widget(new_data_val: Any):
        for i in range(unit_combo.count()):
            if unit_combo.itemData(i) == new_data_val:
                if unit_combo.currentIndex() != i: unit_combo.setCurrentIndex(i)
                return
        if unit_combo.count() > 0 and current_unit_data is None and new_data_val is not None:
            pass
        elif unit_combo.count() > 0 and unit_combo.currentIndex() != 0 : 
            # print(f"Warning: Unit value {new_data_val} for {key_path_unit} not in ComboBox. Defaulting.")
            # unit_combo.setCurrentIndex(0) # Avoid this unless sure
            pass
    ui_state.track_variable(key_path_unit, update_unit_widget)
    value_unit_layout.addWidget(unit_combo, 1) 

    layout.addWidget(value_unit_container)
    if label_on_left and label_text:
        layout.setStretchFactor(value_unit_container, 1)
    elif not label_text:
        layout.setStretchFactor(value_unit_container, 1)

    return container

# --- Simple QPushButton ---
def create_button(
    parent_widget: Optional[QWidget],
    text: str,
    command: Optional[Callable] = None,
    tooltip: Optional[str] = None,
    fixed_width: Optional[int] = None,
    fixed_height: Optional[int] = None,
) -> QPushButton:
    button = QPushButton(text, parent_widget)
    if command:
        button.clicked.connect(command)
    if tooltip:
        button.setToolTip(tooltip)
    if fixed_width:
        button.setFixedWidth(fixed_width)
    if fixed_height:
        button.setFixedHeight(fixed_height)
    return button
```
