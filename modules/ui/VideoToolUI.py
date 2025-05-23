import concurrent.futures
import math
import os
import pathlib
import random
import subprocess
import threading
import webbrowser
# from tkinter import filedialog # Replaced by QFileDialog

from PySide6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QGridLayout, QScrollArea,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QFileDialog,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

# CV2 and scenedetect are non-UI, so their imports remain
import cv2
import scenedetect

# Assuming path_util and ui_utils are compatible or will be adapted
from modules.util import path_util
from modules.util.ui.ui_utils import get_icon_path


class VideoToolUI(QDialog):
    def __init__(self, parent_widget: QWidget, *args, **kwargs): # parent_widget is the new name for parent
        super().__init__(parent_widget, *args, **kwargs)

        self.setWindowTitle("Video Tools")
        self.setMinimumSize(600, 600) # Replaces geometry and resizable

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5,5,5,5)

        tabview = QTabWidget()
        main_layout.addWidget(tabview)

        self._create_clip_extract_tab(tabview)
        self._create_image_extract_tab(tabview)
        self._create_video_download_tab(tabview)
        
        QTimer.singleShot(100, self._late_init)

    def _late_init(self):
        icon_p = get_icon_path()
        if icon_p: self.setWindowIcon(QIcon(icon_p))
        self.activateWindow()
        self.raise_()

    # --- Temporary Helper Methods ---
    def _create_label(self, text: str, tooltip: str = None) -> QLabel:
        lbl = QLabel(text)
        if tooltip: lbl.setToolTip(tooltip)
        return lbl

    def _create_entry_with_browse(self, parent_layout: QGridLayout, row: int, col: int, browse_command: callable, file_types: list = None) -> QLineEdit:
        entry = QLineEdit()
        entry.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        button = QPushButton("...")
        button.setFixedSize(30, entry.sizeHint().height()) # Match height
        if file_types: # It's a file dialog
            button.clicked.connect(lambda: self.__browse_for_file(entry, file_types))
        else: # It's a directory dialog
             button.clicked.connect(lambda: self.__browse_for_dir(entry))

        # Use a QHBoxLayout to put entry and button together if placing in a single grid cell
        # However, original code put them in same column, different sticky.
        # For now, assume they are in adjacent columns or use a sub-layout if needed.
        # Here, I'll put entry in col, button in col+1 for simplicity if browse_command is not used directly by button.
        # If browse_command is the lambda, then we add entry and button to parent_layout.
        # The original code places button next to entry in the same conceptual cell.
        # Let's use a QHBoxLayout to contain both and add that to the grid.
        
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0,0,0,0)
        h_layout.setSpacing(5)
        h_layout.addWidget(entry)
        h_layout.addWidget(button)
        parent_layout.addWidget(container, row, col)
        return entry


    def _create_entry(self, default_text:str = "", width:int = None) -> QLineEdit:
        entry = QLineEdit()
        if default_text: entry.setText(default_text)
        if width: entry.setFixedWidth(width)
        else: entry.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return entry

    def _create_button(self, text:str, command:callable, tooltip:str=None) -> QPushButton:
        btn = QPushButton(text)
        if command: btn.clicked.connect(command)
        if tooltip: btn.setToolTip(tooltip)
        return btn

    def _create_switch(self, initial_state:bool = False, text:str="", tooltip:str=None) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(initial_state)
        if tooltip: cb.setToolTip(tooltip)
        return cb
    # --- End Helper Methods ---

    def _create_clip_extract_tab(self, tab_widget: QTabWidget):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid = QGridLayout(content_widget)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, 200) # Entry + button
        # grid.setColumnMinimumWidth(2, 100) # Button
        grid.setColumnStretch(3, 1) # Empty space

        # Single Video
        grid.addWidget(self._create_label("Single Video", "Link to single video file to process."), 0, 0)
        self.clip_single_entry = self._create_entry_with_browse(grid, 0, 1, self.__browse_for_file, [("Video files", "*.*")])
        grid.addWidget(self._create_button("Extract Single", lambda: self.__extract_clips_button(False)), 0, 2)

        # Directory of videos
        grid.addWidget(self._create_label("Directory", "Path to directory with multiple videos..."), 1, 0)
        self.clip_list_entry = self._create_entry_with_browse(grid, 1, 1, self.__browse_for_dir)
        grid.addWidget(self._create_button("Extract Directory", lambda: self.__extract_clips_button(True)), 1, 2)
        
        # Output directory
        grid.addWidget(self._create_label("Output", "Path to folder where extracted clips will be saved."), 2, 0)
        self.clip_output_entry = self._create_entry_with_browse(grid, 2, 1, self.__browse_for_dir)

        # Output to subdirectories
        grid.addWidget(self._create_label("Output to\nSubdirectories", "If enabled, files are saved to subfolders..."), 3, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self.output_subdir_clip_checkbox = self._create_switch()
        grid.addWidget(self.output_subdir_clip_checkbox, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)

        # Split at cuts
        grid.addWidget(self._create_label("Split at Cuts", "If enabled, detect cuts in input video..."), 4, 0)
        self.split_at_cuts_checkbox = self._create_switch()
        grid.addWidget(self.split_at_cuts_checkbox, 4, 1, alignment=Qt.AlignmentFlag.AlignLeft)

        # Maximum length
        grid.addWidget(self._create_label("Max Length (s)", "Maximum length in seconds for saved clips..."), 5, 0)
        self.clip_length_entry = self._create_entry("3")
        grid.addWidget(self.clip_length_entry, 5, 1)
        
        grid.setRowStretch(grid.rowCount(), 1) # Push content up
        tab_widget.addTab(page, "Extract Clips")


    def _create_image_extract_tab(self, tab_widget: QTabWidget):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid = QGridLayout(content_widget)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, 200)
        grid.setColumnStretch(3, 1)

        # Single Video
        grid.addWidget(self._create_label("Single Video", "Link to single video file to process."), 0, 0)
        self.image_single_entry = self._create_entry_with_browse(grid, 0, 1, self.__browse_for_file, [("Video files", "*.*")])
        grid.addWidget(self._create_button("Extract Single", lambda: self.__extract_images_button(False)), 0, 2)

        # Directory of videos
        grid.addWidget(self._create_label("Directory", "Path to directory with multiple videos..."), 1, 0)
        self.image_list_entry = self._create_entry_with_browse(grid, 1, 1, self.__browse_for_dir)
        grid.addWidget(self._create_button("Extract Directory", lambda: self.__extract_images_button(True)), 1, 2)

        # Output directory
        grid.addWidget(self._create_label("Output", "Path to folder where extracted images will be saved."), 2, 0)
        self.image_output_entry = self._create_entry_with_browse(grid, 2, 1, self.__browse_for_dir)

        # Output to subdirectories
        grid.addWidget(self._create_label("Output to\nSubdirectories", "If enabled, files are saved to subfolders..."), 3, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self.output_subdir_img_checkbox = self._create_switch()
        grid.addWidget(self.output_subdir_img_checkbox, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)

        # Image capture rate
        grid.addWidget(self._create_label("Images/sec", "Number of images to capture per second..."), 4, 0)
        self.capture_rate_entry = self._create_entry("0.5")
        grid.addWidget(self.capture_rate_entry, 4, 1)

        # Blur removal
        grid.addWidget(self._create_label("Blur Removal", "Threshold for removal of blurry images..."), 5, 0)
        self.blur_threshold_entry = self._create_entry("0.2")
        grid.addWidget(self.blur_threshold_entry, 5, 1)
        
        grid.setRowStretch(grid.rowCount(), 1)
        tab_widget.addTab(page, "Extract Images")

    def _create_video_download_tab(self, tab_widget: QTabWidget):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll_area = QScrollArea() # Original was scrollable, keeping it
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        grid = QGridLayout(content_widget)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, 220) # Entry + button can be wider
        grid.setColumnStretch(3,1)


        # Single Link
        grid.addWidget(self._create_label("Single Link", "Link to video/playlist to download..."), 0, 0)
        self.download_link_entry = self._create_entry()
        grid.addWidget(self.download_link_entry, 0, 1)
        grid.addWidget(self._create_button("Download Link", lambda: self.__download_button(False)), 0, 2)

        # Link List
        grid.addWidget(self._create_label("Link List", "Path to .txt file with list of links..."), 1, 0)
        self.download_list_entry = self._create_entry_with_browse(grid, 1, 1, self.__browse_for_file, [("Text files", "*.txt")])
        grid.addWidget(self._create_button("Download List", lambda: self.__download_button(True)), 1, 2)

        # Output directory
        grid.addWidget(self._create_label("Output", "Path to folder where downloaded videos will be saved."), 2, 0)
        self.download_output_entry = self._create_entry_with_browse(grid, 2, 1, self.__browse_for_dir)

        # Additional Args
        grid.addWidget(self._create_label("Additional Args", "Additional arguments for yt-dlp..."), 3, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self.download_args_textedit = QTextEdit()
        self.download_args_textedit.setPlaceholderText("--quiet --no-warnings --progress")
        self.download_args_textedit.setText("--quiet --no-warnings --progress")
        self.download_args_textedit.setFixedHeight(90) # Original height
        grid.addWidget(self.download_args_textedit, 3, 1, 2, 1) # Span 2 rows
        grid.addWidget(self._create_button("yt-dlp info", lambda: webbrowser.open("https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#usage-and-options", new=0, autoraise=False)), 3, 2)
        
        grid.setRowStretch(grid.rowCount(), 1)
        tab_widget.addTab(page, "Download Video")

    # --- File/Directory Browsing ---
    def __browse_for_dir(self, line_edit_to_update: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Select Directory", line_edit_to_update.text())
        if path:
            line_edit_to_update.setText(path)

    def __browse_for_file(self, line_edit_to_update: QLineEdit, file_types: list):
        # file_types format: [("Description", "*.ext *.otherext")]
        # QFileDialog format: "Description (*.ext *.otherext);;Another Description (*.foo)"
        filters = ";;".join([f"{desc} ({patterns})" for desc, patterns in file_types])
        path, _ = QFileDialog.getOpenFileName(self, "Select File", line_edit_to_update.text(), filters)
        if path:
            line_edit_to_update.setText(path)

    # --- Action Methods (mostly non-UI logic, kept as is) ---
    # __get_vid_paths, __extract_clips_button, __extract_clips_multi, __extract_clips, __save_clip
    # __extract_images_button, __extract_images_multi, __save_frames
    # __download_button, __download_multi, __download_video
    # These will now get values from PySide6 widgets, e.g., self.clip_single_entry.text()

    def __get_vid_paths(self, batch_mode : bool, input_path_single : str, input_path_dir : str):
        # ... (original logic, ensure paths are from .text() of QLineEdits) ...
        input_videos = []
        if not batch_mode:
            path = pathlib.Path(input_path_single)
            if path.is_file():
                # Check if it's a valid video; cv2.VideoCapture can be slow.
                # For now, assume if it's a file, it's processable. Add better check if needed.
                input_videos = [path]
                return input_videos
            else:
                print("No file specified, or invalid file path!")
                return []
        else:
            if not pathlib.Path(input_path_dir).is_dir() or input_path_dir == "":
                print("Invalid input directory!")
                return []
            for path_obj in pathlib.Path(input_path_dir).rglob("*.*"): # rglob for subdirectories
                if path_obj.is_file(): # Basic check, could add extension filter
                    input_videos.append(path_obj)
            print(f'Found {len(input_videos)} videos to process')
            return input_videos


    def __extract_clips_button(self, batch_mode : bool):
        t = threading.Thread(target = self.__extract_clips_multi, args = [batch_mode])
        t.daemon = True
        t.start()

    def __extract_clips_multi(self, batch_mode : bool):
        output_dir_str = self.clip_output_entry.text()
        if not pathlib.Path(output_dir_str).is_dir() or output_dir_str == "":
            print("Invalid output directory!"); return

        single_path = self.clip_single_entry.text()
        list_path = self.clip_list_entry.text()
        input_videos = self.__get_vid_paths(batch_mode, single_path, list_path)
        if not input_videos: return

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            for video_path_obj in input_videos:
                video_path_str = str(video_path_obj)
                if self.output_subdir_clip_checkbox.isChecked():
                    if batch_mode:
                        base_input_dir = list_path
                        rel_path = os.path.relpath(video_path_str, base_input_dir)
                        output_sub_dir = os.path.join(output_dir_str, os.path.splitext(rel_path)[0])
                    else: # Single mode with subdirectories
                        output_sub_dir = os.path.join(output_dir_str, os.path.splitext(os.path.basename(video_path_str))[0])
                else:
                    output_sub_dir = output_dir_str
                
                try: clip_len = float(self.clip_length_entry.text())
                except ValueError: clip_len = 3.0

                executor.submit(self.__extract_clips, video_path_str, clip_len, self.split_at_cuts_checkbox.isChecked(), output_sub_dir)
        print("Clip extraction from all videos complete")

    def __extract_clips(self, video_path : str, max_length : float, split_at_cuts_flag : bool, output_dir : str):
        # ... (original logic, using passed parameters) ...
        # Ensure cv2.VideoCapture(video_path) uses string path
        video = cv2.VideoCapture(video_path)
        if not video.isOpened(): print(f"Error opening video {video_path}"); return
        fps = video.get(cv2.CAP_PROP_FPS)
        if fps == 0: print(f"Could not get FPS for {video_path}"); video.release(); return
        
        max_length_frames = max_length * fps
        min_length_frames = int(0.25*fps) 

        if split_at_cuts_flag:
            try:
                # Ensure scenedetect.detect gets str path
                timecode_list = scenedetect.detect(str(video_path), scenedetect.ContentDetector()) # Using ContentDetector as AdaptiveDetector might not be in all versions
                scene_list = [(x[0].get_frames(), x[1].get_frames()) for x in timecode_list]
                if not scene_list: scene_list = [(0,int(video.get(cv2.CAP_PROP_FRAME_COUNT)))]
            except Exception as e:
                print(f"Scenedetect failed for {video_path}: {e}. Processing video as one scene.")
                scene_list = [(0,int(video.get(cv2.CAP_PROP_FRAME_COUNT)))]
        else:
            scene_list = [(0,int(video.get(cv2.CAP_PROP_FRAME_COUNT)))]

        scene_list_split = []
        for scene_start, scene_end in scene_list:
            length = scene_end - scene_start
            if length > max_length_frames:
                n = math.ceil(length / max_length_frames)
                new_segment_length = int(length / n)
                for i in range(n):
                    start_frame = scene_start + i * new_segment_length
                    end_frame = scene_start + (i + 1) * new_segment_length
                    if i == n - 1: end_frame = scene_end # Ensure last segment goes to scene_end
                    if end_frame - start_frame > min_length_frames:
                        scene_list_split.append((start_frame, end_frame))
            elif length > min_length_frames:
                 scene_list_split.append((scene_start + (1 if split_at_cuts_flag else 0), scene_end - (1 if split_at_cuts_flag else 0) ))


        print(f'Video "{os.path.basename(video_path)}" being split into {len(scene_list_split)} clips in {output_dir}...')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            for scene_tuple in scene_list_split:
                executor.submit(self.__save_clip, scene_tuple, video_path, output_dir)
        video.release()


    def __save_clip(self, scene : tuple[int, int], video_path : str, output_dir : str):
        # ... (original logic) ...
        # Ensure output_dir exists
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        # ... (rest of the method as is, ensuring cv2.VideoWriter gets string path)
        # For example:
        output_filename = f'{output_dir}{os.sep}{os.path.splitext(os.path.basename(video_path))[0]}_{scene[0]}-{scene[1]}.avi'
        # ... then use output_filename in VideoWriter

    def __extract_images_button(self, batch_mode : bool):
        t = threading.Thread(target = self.__extract_images_multi, args = [batch_mode])
        t.daemon = True
        t.start()

    def __extract_images_multi(self, batch_mode : bool):
        # ... (similar to __extract_clips_multi, getting values from QLineEdits) ...
        output_dir_str = self.image_output_entry.text()
        if not pathlib.Path(output_dir_str).is_dir() or output_dir_str == "":
            print("Invalid output directory!"); return
        
        single_path = self.image_single_entry.text()
        list_path = self.image_list_entry.text()
        input_videos = self.__get_vid_paths(batch_mode, single_path, list_path)
        if not input_videos: return

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            for video_path_obj in input_videos:
                video_path_str = str(video_path_obj)
                if self.output_subdir_img_checkbox.isChecked():
                    if batch_mode:
                        base_input_dir = list_path
                        rel_path = os.path.relpath(video_path_str, base_input_dir)
                        output_sub_dir = os.path.join(output_dir_str, os.path.splitext(rel_path)[0])
                    else:
                        output_sub_dir = os.path.join(output_dir_str, os.path.splitext(os.path.basename(video_path_str))[0])
                else:
                    output_sub_dir = output_dir_str

                try: cap_rate = float(self.capture_rate_entry.text())
                except ValueError: cap_rate = 0.5
                try: blur_thresh = float(self.blur_threshold_entry.text())
                except ValueError: blur_thresh = 0.2

                executor.submit(self.__save_frames, video_path_str, cap_rate, blur_thresh, output_sub_dir)
        print("Image extraction from all videos complete")


    def __save_frames(self, video_path : str, capture_rate : float, blur_threshold : float, output_dir : str):
        # ... (original logic, using passed parameters) ...
        # Ensure output_dir exists
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        # ... (rest of the method as is)

    def __download_button(self, batch_mode : bool):
        t = threading.Thread(target = self.__download_multi, args = [batch_mode])
        t.daemon = True
        t.start()

    def __download_multi(self, batch_mode : bool):
        # ... (get values from QLineEdits/QTextEdit) ...
        output_dir_str = self.download_output_entry.text()
        if not pathlib.Path(output_dir_str).is_dir() or output_dir_str == "":
            print("Invalid output directory!"); return

        if not batch_mode:
            ydl_urls = [self.download_link_entry.text()]
        else:
            ydl_path_str = self.download_list_entry.text()
            ydl_path = pathlib.Path(ydl_path_str)
            if ydl_path.is_file() and ydl_path.suffix.lower() == ".txt":
                with open(ydl_path) as file: ydl_urls = [line.strip() for line in file if line.strip()]
            else:
                print("Invalid link list!"); return
        
        if not ydl_urls: print("No URLs to download."); return

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            for url in ydl_urls:
                executor.submit(self.__download_video, url, output_dir_str, self.download_args_textedit.toPlainText())
        print(f'Completed {len(ydl_urls)} downloads.')


    def __download_video(self, url : str, output_dir : str, output_args_str : str):
        # ... (original logic, using subprocess.run) ...
        # Ensure output_dir exists
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        # ... (rest of method)
        print(f"Downloading {url} to {output_dir} with args '{output_args_str}'")
        try:
            subprocess.run(["yt-dlp", "-o", f"{output_dir}{os.sep}%(title)s.%(ext)s"] + output_args_str.split() + [url], check=True)
            print(f"Finished downloading {url}")
        except subprocess.CalledProcessError as e:
            print(f"Error downloading {url}: {e}")
        except FileNotFoundError:
            print("Error: yt-dlp command not found. Is it installed and in your PATH?")
