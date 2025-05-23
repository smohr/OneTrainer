import faulthandler
import traceback

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QCloseEvent

import modules.util.ui.qt_components as qt_comps
from modules.util.ui.ui_utils import get_icon_path

# Scalene might not be available in all environments, so import with a try-except
try:
    from scalene import scalene_profiler
    SCALENE_AVAILABLE = True
except ImportError:
    SCALENE_AVAILABLE = False
    print("Scalene profiler not found. Profiling features will be disabled.")


class ProfilingWindow(QWidget): # Changed from CTkToplevel to QWidget for a persistent tool window
    def __init__(self, parent_widget: QWidget, *args, **kwargs):
        super().__init__(parent_widget, *args, **kwargs)
        # self.parent = parent_widget # QWidget handles parentage

        self.setWindowTitle("Profiling Tools")
        self.setMinimumSize(300, 200) # Adjusted from original 512x512

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10,10,10,10)
        main_layout.setSpacing(10)

        # Controls
        dump_button = qt_comps.create_button(self, "Dump Current Stacks", self._dump_stack, "Writes all thread stack traces to 'stacks.txt'")
        main_layout.addWidget(dump_button)

        self._profile_button = qt_comps.create_button(self, "Start Profiling", self._toggle_profiler, "Turns on/off Scalene profiling. Requires OneTrainer to be launched with Scalene.")
        main_layout.addWidget(self._profile_button)
        
        if not SCALENE_AVAILABLE:
            self._profile_button.setToolTip("Scalene library not found. Profiling disabled.")
            self._profile_button.setEnabled(False)

        main_layout.addStretch(1) # Push controls to top

        # Status Bar
        status_bar_frame = QFrame(self) # Using QFrame for a styled bar if needed later
        status_bar_layout = QHBoxLayout(status_bar_frame)
        status_bar_layout.setContentsMargins(0,0,0,0)
        self._message_label = qt_comps.create_label(status_bar_frame, "Inactive")
        status_bar_layout.addWidget(self._message_label)
        main_layout.addWidget(status_bar_frame)
        
        self.is_profiling = False
        self._update_profiler_button_state() # Set initial button text/state

        QTimer.singleShot(100, self._late_init)
        # self.hide() # Start hidden, shown by TrainUI.open_profiling_tool()

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        # Don't grab_set or focus_set for a non-modal window that starts hidden.
        # self.activateWindow()
        # self.raise_()

    def _dump_stack(self):
        try:
            with open('stacks.txt', 'w') as f:
                faulthandler.dump_traceback(f)
            self._message_label.setText('Stack dumped to stacks.txt')
            print("Stack dumped to stacks.txt")
        except Exception as e:
            self._message_label.setText(f'Error dumping stack: {e}')
            print(f"Error dumping stack: {e}")
            traceback.print_exc()

    def _toggle_profiler(self):
        if not SCALENE_AVAILABLE:
            self._message_label.setText("Scalene profiler is not available.")
            return

        if self.is_profiling:
            self._end_profiler()
        else:
            self._start_profiler()
        self._update_profiler_button_state()

    def _start_profiler(self):
        if not SCALENE_AVAILABLE: return
        try:
            scalene_profiler.start()
            self.is_profiling = True
            print("Scalene profiling started.")
        except Exception as e: # Scalene might raise error if already started or other issues
            self.is_profiling = False # Ensure state is correct
            self._message_label.setText(f"Error starting profiler: {e}")
            print(f"Error starting Scalene profiler: {e}")
            traceback.print_exc()


    def _end_profiler(self):
        if not SCALENE_AVAILABLE or not self.is_profiling: return
        try:
            scalene_profiler.stop()
            self.is_profiling = False
            print("Scalene profiling stopped.")
        except Exception as e: # Scalene might raise error if not running
            # We still set is_profiling to False as the intent was to stop.
            self.is_profiling = False 
            self._message_label.setText(f"Error stopping profiler: {e}")
            print(f"Error stopping Scalene profiler: {e}")
            traceback.print_exc()


    def _update_profiler_button_state(self):
        if self.is_profiling:
            self._message_label.setText('Profiling active...')
            self._profile_button.setText('End Profiling')
        else:
            self._message_label.setText('Inactive')
            self._profile_button.setText('Start Profiling')
            if not SCALENE_AVAILABLE:
                 self._profile_button.setEnabled(False)


    def closeEvent(self, event: QCloseEvent):
        # Override close event to hide the window instead of destroying it
        self.hide()
        event.ignore() # Prevent the window from actually closing

    # Public method to show the window (replaces deiconify)
    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

[end of modules/ui/ProfilingWindow.py]
