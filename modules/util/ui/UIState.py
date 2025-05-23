import contextlib
from collections.abc import Callable
from enum import Enum
from typing import Any, Dict, Optional, Union

from PySide6.QtCore import QObject, Signal, Slot

from modules.util.config.BaseConfig import BaseConfig

class UIState(QObject):
    """
    Manages the state of UI elements and synchronizes it with underlying configuration objects.
    Emits signals when values change, allowing UI components to react.
    """
    
    # Signal: emitted when a variable is changed via set_var
    # Args: key_path (str), new_value (Any)
    valueChanged = Signal(str, object)

    # Signal: emitted when a specific variable (identified by key_path) needs a UI refresh
    # This is for cases where the value might not have changed but UI needs to re-read it.
    # For example, after a batch update or loading a preset.
    refreshNeeded = Signal(str)

    def __init__(self, target_object: Union[BaseConfig, Dict[str, Any]], parent: Optional[QObject] = None):
        super().__init__(parent)
        self.obj = target_object
        
        # __tracked_slots is used to keep references to the wrapper slots created by track_variable,
        # so they don't get garbage collected if the caller doesn't store them.
        # The key is the original slot, value is the list of generated wrapper slots.
        self.__tracked_slots_map: Dict[Callable, List[Callable]] = {}


    def update_target_object(self, new_target_object: Union[BaseConfig, Dict[str, Any]]):
        """
        Updates the underlying data object that UIState is managing.
        This will trigger a refresh of all tracked variables.
        """
        is_config_before = isinstance(self.obj, BaseConfig)
        is_dict_before = isinstance(self.obj, dict)
        
        self.obj = new_target_object

        is_config_after = isinstance(self.obj, BaseConfig)
        is_dict_after = isinstance(self.obj, dict)

        # Determine keys to refresh. If structure type changes, refresh all.
        # Otherwise, refresh common keys and new keys.
        # For simplicity now, let's assume we should try to refresh all existing tracked paths.
        # A more robust way would be to iterate through all previously known keys.
        # However, refreshNeeded signal takes a key_path.
        # Perhaps it's better if the component that calls update_target_object
        # is responsible for explicitly refreshing its UI elements.
        # Or UIState could iterate its internal list of what is being tracked.
        # For now, let's emit a generic signal that components can connect to for full refresh.
        
        # This is a bit of a sledgehammer. A more granular approach would be better.
        # Iterate over all *previously* known keys (if we stored them) and emit refreshNeeded.
        # For now, the UI components will need to manage their own full refresh on a higher-level signal
        # or after calling this.

        # Let's try to emit refreshNeeded for existing paths if the object type is compatible.
        # This is complex because the structure of self.obj might have completely changed.
        # The simplest is that after calling update_target_object, the UI explicitly re-binds/re-reads values.
        # print(f"UIState target object updated. UI components may need to re-query values or re-track variables.")
        # For now, no automatic signal emission on full object update, caller should manage UI refresh.


    def _get_value_from_path(self, obj: Any, path_parts: List[str]) -> Any:
        current = obj
        for part in path_parts:
            if isinstance(current, BaseConfig):
                if hasattr(current, part):
                    current = getattr(current, part)
                else: # Try to get from 'extras' if it's a BaseConfig with extras
                    current = current.extras.get(part, None) if hasattr(current, 'extras') and isinstance(current.extras, dict) else None
            elif isinstance(current, dict):
                current = current.get(part, None)
            elif hasattr(current, part): # Generic object access
                 current = getattr(current, part)
            else:
                return None # Path not found
            if current is None and part != path_parts[-1]: # Path broken midway
                return None
        return current

    def _set_value_at_path(self, obj: Any, path_parts: List[str], value: Any) -> bool:
        current = obj
        for i, part in enumerate(path_parts[:-1]): # Navigate to the parent of the target
            if isinstance(current, BaseConfig):
                if hasattr(current, part):
                    current = getattr(current, part)
                else: # Try to set in 'extras' if it's a BaseConfig with extras
                    if not hasattr(current, 'extras') or not isinstance(current.extras, dict):
                        return False # Cannot set path
                    if part not in current.extras: # Create intermediate dict if needed
                        current.extras[part] = {}
                    current = current.extras[part]

            elif isinstance(current, dict):
                if part not in current: # Create intermediate dict if needed
                    current[part] = {}
                current = current.get(part)
            elif hasattr(current, part):
                 current = getattr(current, part)
            else:
                return False # Path not found or not settable

            if not isinstance(current, (BaseConfig, dict)) and i < len(path_parts) - 2 : # Path broken with non-dict/config object
                 return False


        target_key = path_parts[-1]
        target_type = None
        is_nullable = False

        if isinstance(current, BaseConfig):
            if target_key in current.types:
                target_type = current.types[target_key]
                is_nullable = current.nullables.get(target_key, False)
                
                # Type conversion for BaseConfig based on defined types
                try:
                    if value is None and is_nullable:
                        setattr(current, target_key, None)
                    elif target_type is bool:
                        setattr(current, target_key, bool(value))
                    elif target_type is int:
                        setattr(current, target_key, int(value) if value is not None else (None if is_nullable else 0) )
                    elif target_type is float:
                        setattr(current, target_key, float(value) if value is not None else (None if is_nullable else 0.0) )
                    elif issubclass(target_type, Enum):
                        setattr(current, target_key, target_type(value) if value is not None else (None if is_nullable else list(target_type)[0]))
                    elif target_type is str:
                         setattr(current, target_key, str(value) if value is not None else (None if is_nullable else ""))
                    else: # For complex types like lists, dicts, or other BaseConfigs, assign directly
                        setattr(current, target_key, value)
                    return True
                except (ValueError, TypeError) as e:
                    print(f"UIState: Type conversion error for {target_key}: {e}")
                    return False
            elif hasattr(current, 'extras') and isinstance(current.extras, dict): # Fallback to extras
                current.extras[target_key] = value
                return True
            else: # Not a defined field and no extras
                return False
        elif isinstance(current, dict):
            current[target_key] = value
            return True
        elif hasattr(current, target_key): # Generic object attribute
            try:
                # Attempt basic type conversion if possible, based on existing attribute type
                # This is less robust than BaseConfig's explicit types
                existing_attr_type = type(getattr(current, target_key, None))
                if existing_attr_type is bool: value = bool(value)
                elif existing_attr_type is int: value = int(value)
                elif existing_attr_type is float: value = float(value)
                # Enum conversion is tricky here without knowing the enum type
                setattr(current, target_key, value)
                return True
            except (ValueError, TypeError) as e:
                print(f"UIState: Type conversion error for attribute {target_key}: {e}")
                return False
        return False


    def get_var(self, key_path: str, default: Any = None) -> Any:
        path_parts = key_path.split('.')
        value = self._get_value_from_path(self.obj, path_parts)
        return value if value is not None else default

    def set_var(self, key_path: str, value: Any):
        path_parts = key_path.split('.')
        
        # Store old value for comparison if needed, though signal emits new value
        # old_value = self._get_value_from_path(self.obj, path_parts)

        if self._set_value_at_path(self.obj, path_parts, value):
            # print(f"UIState: Emitting valueChanged for {key_path} = {value}")
            self.valueChanged.emit(key_path, value)
        else:
            print(f"UIState: Failed to set value for {key_path}")


    def track_variable(self, key_path: str, slot_callback: Callable[[Any], None]):
        """
        Connects a slot/lambda to be called when the variable at key_path changes.
        The slot_callback will receive the new value of the variable.
        """
        # Wrapper to filter signals by key_path
        # @Slot(str, object) # This decorator is for QObject methods, not inner functions
        def specific_value_changed_handler(emitted_key_path: str, new_value: Any):
            if emitted_key_path == key_path:
                try:
                    slot_callback(new_value)
                except Exception as e:
                    print(f"Error in UIState tracked slot for key '{key_path}': {e}")
                    traceback.print_exc()
        
        self.valueChanged.connect(specific_value_changed_handler)
        
        # Store the wrapper to prevent it from being garbage collected if slot_callback is a lambda
        # This is a simplified way; a more robust solution might involve a custom Connection class
        # or ensuring the QObject making the connection (the widget) keeps a reference.
        if slot_callback not in self.__tracked_slots_map:
            self.__tracked_slots_map[slot_callback] = []
        self.__tracked_slots_map[slot_callback].append(specific_value_changed_handler)


    def refresh_ui_for_key(self, key_path: str):
        """Emits a signal indicating that UI elements bound to this key should refresh."""
        self.refreshNeeded.emit(key_path)

    # The old trace methods are removed.
    # The old __create_vars and __set_vars logic for Tkinter variables is removed.
    # Type conversion logic from __set_xxx_var methods is partially moved to _set_value_at_path
    # when dealing with BaseConfig instances. For generic dicts/objects, type conversion
    # responsibility is more on the caller of set_var or the widget updating the value.
    # UIState is now primarily a signal emitter based on changes to a Python object.
    
    # Example of how a widget would use this:
    # Assume my_line_edit = QLineEdit()
    # Assume ui_state = UIState(my_config_object)
    #
    # To set initial value:
    # my_line_edit.setText(str(ui_state.get_var("some.text.property", "")))
    #
    # To update UIState when QLineEdit changes:
    # my_line_edit.editingFinished.connect(
    #     lambda: ui_state.set_var("some.text.property", my_line_edit.text())
    # )
    #
    # To update QLineEdit when UIState changes (e.g. from preset load):
    # def update_my_line_edit(new_text_value):
    #    if my_line_edit.text() != str(new_text_value): # Avoid loops if setText also triggers editingFinished
    #        my_line_edit.setText(str(new_text_value))
    # ui_state.track_variable("some.text.property", update_my_line_edit)

    # If UIState's target object is updated (e.g. TrainConfig reloaded):
    # ui_state.update_target_object(new_config_object)
    # # Then, explicitly update UI elements:
    # my_line_edit.setText(str(ui_state.get_var("some.text.property", ""))) 
    # # Or connect to a global refresh signal from UIState if that's implemented.
    # This is why the helper methods in TrainUI and other classes are important,
    # as they encapsulate this get, set, and track logic.
