#!/usr/bin/env python3
"""
PyQt5 version of the LaTeX2Video GUI.
This version avoids the XCB issues that occur with Tkinter.
"""

import os
import sys
import logging
import re
import yaml
import threading
import queue
import time
import shutil
from typing import List, Dict, Optional
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("[MARKER] pyqt_latex2video.py loaded and running from: " + os.path.abspath(__file__))
print("[PRINT-MARKER] pyqt_latex2video.py loaded and running from:", os.path.abspath(__file__))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLineEdit, QTextEdit, QFileDialog, QMessageBox, QSplitter, QGridLayout,
    QFrame, QStatusBar, QAction, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSettings, QTimer
from PyQt5.QtGui import QIcon, QPixmap

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.latex_parser import parse_latex_file, Slide
from src.chatgpt_script_generator import format_slide_for_chatgpt, clean_chatgpt_response
from src.openai_script_generator import initialize_openai_client, generate_script_with_openai
from src.image_generator import generate_slide_images
from src.audio_generator import generate_all_audio
from src.simple_video_assembler import assemble_video

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'latex2video_gui.log'))
    ]
)

class Worker(QObject):
    """Worker thread for background tasks"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        print("[PRINT-DEBUG] Worker.__init__ called")
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Run the worker function"""
        print("[PRINT-DEBUG] Worker.run called")
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.result.emit(result)
        except Exception as e:
            print("[PRINT-DEBUG] Exception in Worker.run:", e)
            self.error.emit(str(e))
            logging.error(f"Error in worker thread: {e}")
        finally:
            self.finished.emit()

    def _generate_images_worker(self, latex_file):
        """Worker function for generating images"""
        try:
            print("[PRINT-DEBUG] ENTERED _generate_images_worker")
            # Add the LaTeX file path to the configuration
            config_copy = self.config.copy()
            config_copy['latex_file_path'] = os.path.abspath(latex_file)
            print("[PRINT-DEBUG] About to call generate_slide_images in src.image_generator.py")
            # Generate slide images
            return generate_slide_images(latex_file, config_copy)
        except Exception as e:
            print("[PRINT-DEBUG] Exception in _generate_images_worker:", e)
            raise

class RedirectText:
    """Class to redirect stdout/stderr to a QTextEdit widget"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, string):
        self.buffer += string
        self.text_widget.append(string)
        self.text_widget.ensureCursorVisible()

    def flush(self):
        pass

# Define stylesheets for light and dark modes
LIGHT_STYLE = """
QMainWindow, QWidget {
    background-color: #f0f0f0;
    color: #202020;
}
QTextEdit, QLineEdit {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #c0c0c0;
}
QPushButton {
    background-color: #e0e0e0;
    color: #202020;
    border: 1px solid #c0c0c0;
    padding: 5px;
}
QPushButton:hover {
    background-color: #d0d0d0;
}
QTabWidget::pane {
    border: 1px solid #c0c0c0;
    background-color: #f0f0f0;
}
QTabBar::tab {
    background-color: #e0e0e0;
    color: #202020;
    padding: 5px 10px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #f0f0f0;
    border-bottom: 2px solid #505050;
}
QSplitter::handle {
    background-color: #c0c0c0;
}
QStatusBar {
    background-color: #e0e0e0;
    color: #202020;
}
"""

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #2d2d2d;
    color: #e0e0e0;
}
QTextEdit, QLineEdit {
    background-color: #3d3d3d;
    color: #e0e0e0;
    border: 1px solid #505050;
}
QPushButton {
    background-color: #3d3d3d;
    color: #e0e0e0;
    border: 1px solid #505050;
    padding: 5px;
}
QPushButton:hover {
    background-color: #4d4d4d;
}
QTabWidget::pane {
    border: 1px solid #505050;
    background-color: #2d2d2d;
}
QTabBar::tab {
    background-color: #3d3d3d;
    color: #e0e0e0;
    padding: 5px 10px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #2d2d2d;
    border-bottom: 2px solid #a0a0a0;
}
QSplitter::handle {
    background-color: #505050;
}
QStatusBar {
    background-color: #3d3d3d;
    color: #e0e0e0;
}
"""

class LaTeX2VideoGUI(QMainWindow):
    """Main GUI application for LaTeX2Video using PyQt5"""
    def __init__(self):
        super().__init__()
        
        # Initialize variables
        self.latex_file_path = ""
        self.config_file_path = ""
        self.output_dir = ""
        self.current_slide_index = 0
        self.slides = []
        self.narrations = []
        self.prompts = []
        self.config = {}
        self.threads = []
        self.dark_mode = False
        
        # Set default paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file_path = os.path.join(script_dir, "config", "config.yaml")
        self.output_dir = os.path.join(script_dir, "output")
        
        # Load settings
        self.settings = QSettings("LaTeX2Video", "PyQt5GUI")
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)
        
        # Set up the UI
        self.init_ui()
        
        # Apply the appropriate theme
        self.apply_theme()
        
        # Load config if exists
        self.load_config()
        
        # Initialize status
        self.update_status("Ready")

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("LaTeX2Video (PyQt5)")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)
        
        # Create menu bar
        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")
        
        # Add dark mode toggle action
        self.dark_mode_action = QAction("Dark Mode", self, checkable=True)
        self.dark_mode_action.setChecked(self.dark_mode)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(self.dark_mode_action)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create top frame for file selection
        top_frame = QFrame()
        top_layout = QGridLayout(top_frame)
        
        # LaTeX file selection
        top_layout.addWidget(QLabel("LaTeX File:"), 0, 0)
        self.latex_file_edit = QLineEdit()
        top_layout.addWidget(self.latex_file_edit, 0, 1)
        latex_browse_button = QPushButton("Browse...")
        latex_browse_button.clicked.connect(self.browse_latex_file)
        top_layout.addWidget(latex_browse_button, 0, 2)
        
        # Config file selection
        top_layout.addWidget(QLabel("Config File:"), 1, 0)
        self.config_file_edit = QLineEdit()
        self.config_file_edit.setText(self.config_file_path)
        top_layout.addWidget(self.config_file_edit, 1, 1)
        config_browse_button = QPushButton("Browse...")
        config_browse_button.clicked.connect(self.browse_config_file)
        top_layout.addWidget(config_browse_button, 1, 2)
        
        # Output directory selection
        top_layout.addWidget(QLabel("Output Directory:"), 2, 0)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setText(self.output_dir)
        top_layout.addWidget(self.output_dir_edit, 2, 1)
        output_browse_button = QPushButton("Browse...")
        output_browse_button.clicked.connect(self.browse_output_dir)
        top_layout.addWidget(output_browse_button, 2, 2)
        
        # Set column stretch
        top_layout.setColumnStretch(1, 1)
        
        # Add top frame to main layout
        main_layout.addWidget(top_frame)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create editor tab
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        
        # Create editor controls
        editor_controls = QWidget()
        editor_controls_layout = QHBoxLayout(editor_controls)
        editor_controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add buttons
        parse_button = QPushButton("Parse LaTeX")
        parse_button.clicked.connect(self.parse_latex)
        editor_controls_layout.addWidget(parse_button)
        
        generate_scripts_button = QPushButton("Generate Scripts")
        generate_scripts_button.clicked.connect(self.generate_scripts)
        editor_controls_layout.addWidget(generate_scripts_button)
        
        save_scripts_button = QPushButton("Save Scripts")
        save_scripts_button.clicked.connect(self.save_scripts)
        editor_controls_layout.addWidget(save_scripts_button)
        
        load_scripts_button = QPushButton("Load Scripts")
        load_scripts_button.clicked.connect(self.load_scripts)
        editor_controls_layout.addWidget(load_scripts_button)
        
        # Add spacer
        editor_controls_layout.addStretch()
        
        # Add navigation controls
        prev_button = QPushButton("< Prev")
        prev_button.clicked.connect(self.prev_slide)
        editor_controls_layout.addWidget(prev_button)
        
        self.slide_label = QLabel("Slide: 0/0")
        editor_controls_layout.addWidget(self.slide_label)
        
        next_button = QPushButton("Next >")
        next_button.clicked.connect(self.next_slide)
        editor_controls_layout.addWidget(next_button)
        
        # Add editor controls to editor layout
        editor_layout.addWidget(editor_controls)
        
        # Create editor panes
        editor_splitter = QSplitter(Qt.Vertical)
        
        # Top pane - slide image and content
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Slide image panel
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.addWidget(QLabel("Slide Image:"))
        
        # Create a scroll area for the image
        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setMinimumHeight(300)
        
        # Create a label to display the image
        self.slide_image_label = QLabel()
        self.slide_image_label.setAlignment(Qt.AlignCenter)
        self.slide_image_label.setMinimumSize(400, 300)
        self.slide_image_label.setStyleSheet("background-color: #ffffff;")
        self.slide_image_label.setText("No image available")
        
        # Add the label to the scroll area
        self.image_scroll_area.setWidget(self.slide_image_label)
        image_layout.addWidget(self.image_scroll_area)
        
        top_splitter.addWidget(image_widget)
        
        # ChatGPT response panel
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(QLabel("ChatGPT Response:"))
        self.slide_content_text = QTextEdit()
        self.slide_content_text.setReadOnly(True)
        content_layout.addWidget(self.slide_content_text)
        
        top_splitter.addWidget(content_widget)
        
        # Add the top splitter to the main editor splitter
        editor_splitter.addWidget(top_splitter)
        
        # Bottom pane - ChatGPT prompt
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.addWidget(QLabel("ChatGPT Prompt:"))
        self.narration_text = QTextEdit()
        bottom_layout.addWidget(self.narration_text)
        
        editor_splitter.addWidget(bottom_widget)
        
        # Add editor panes to editor layout
        editor_layout.addWidget(editor_splitter)
        
        # Add editor tab to tab widget
        self.tab_widget.addTab(editor_widget, "ChatGPT Editor")
        
        # Create generation tab
        generation_widget = QWidget()
        generation_layout = QVBoxLayout(generation_widget)
        
        # Create generation controls
        gen_controls = QWidget()
        gen_controls_layout = QHBoxLayout(gen_controls)
        gen_controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add buttons
        gen_images_button = QPushButton("Generate Images")
        gen_images_button.clicked.connect(self.generate_images)
        gen_controls_layout.addWidget(gen_images_button)
        
        gen_audio_button = QPushButton("Generate Audio")
        gen_audio_button.clicked.connect(self.generate_audio)
        gen_controls_layout.addWidget(gen_audio_button)
        
        assemble_button = QPushButton("Assemble Video")
        assemble_button.clicked.connect(self.assemble_video)
        gen_controls_layout.addWidget(assemble_button)
        
        gen_all_button = QPushButton("Generate All")
        gen_all_button.clicked.connect(self.generate_all)
        gen_controls_layout.addWidget(gen_all_button)
        
        # Add spacer
        gen_controls_layout.addStretch()
        
        # Add generation controls to generation layout
        generation_layout.addWidget(gen_controls)
        
        # Create log output
        generation_layout.addWidget(QLabel("Log Output:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        generation_layout.addWidget(self.log_text)
        
        # Add generation tab to tab widget
        self.tab_widget.addTab(generation_widget, "Video Generation")
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Redirect stdout and stderr to the log text widget
        self.stdout_redirect = RedirectText(self.log_text)
        self.stderr_redirect = RedirectText(self.log_text)
        sys.stdout = self.stdout_redirect
        sys.stderr = self.stderr_redirect
        
        # Show the window
        self.show()

    def apply_theme(self):
        """Apply the current theme (light or dark)"""
        if self.dark_mode:
            self.setStyleSheet(DARK_STYLE)
        else:
            self.setStyleSheet(LIGHT_STYLE)
        
        # Save the setting
        self.settings.setValue("dark_mode", self.dark_mode)
    
    def toggle_dark_mode(self):
        """Toggle between light and dark mode"""
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        
        # Update the status
        mode_name = "dark" if self.dark_mode else "light"
        self.update_status(f"Switched to {mode_name} mode")

    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_bar.showMessage(message)
        logging.info(message)

    def resizeEvent(self, event):
        """Handle window resize event"""
        super().resizeEvent(event)
        
        # If we have a current image, reload it to fit the new size
        if hasattr(self, 'current_image_path') and self.current_image_path:
            try:
                # Load the image
                pixmap = QPixmap(self.current_image_path)
                if not pixmap.isNull():
                    # Scale the image to fit the label while maintaining aspect ratio
                    pixmap = pixmap.scaled(
                        self.slide_image_label.width(), 
                        self.slide_image_label.height(),
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    
                    # Display the image
                    self.slide_image_label.setPixmap(pixmap)
            except Exception as e:
                logging.error(f"Error resizing image: {e}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Restore stdout and stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        
        # Accept the close event
        event.accept()

    def browse_latex_file(self):
        """Open file dialog to select LaTeX file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select LaTeX File",
            "",
            "LaTeX Files (*.tex);;All Files (*.*)"
        )
        if file_path:
            # Clean output directories when a new LaTeX file is loaded
            for outdir in ["output", "output-lagrange", "output-test"]:
                abs_outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), outdir)
                if os.path.exists(abs_outdir):
                    shutil.rmtree(abs_outdir)
                os.makedirs(abs_outdir, exist_ok=True)
            self.latex_file_path = file_path
            self.latex_file_edit.setText(file_path)
            self.update_status(f"LaTeX file selected: {file_path}")
            # Automatically parse LaTeX and generate slides after loading
            self.parse_latex()
            # Automatically generate images after parsing LaTeX
            self.generate_images()

    def browse_config_file(self):
        """Open file dialog to select config file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Config File",
            "",
            "YAML Files (*.yaml);;All Files (*.*)"
        )
        if file_path:
            self.config_file_path = file_path
            self.config_file_edit.setText(file_path)
            self.load_config()
            self.update_status(f"Config file selected: {file_path}")

    def browse_output_dir(self):
        """Open directory dialog to select output directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ""
        )
        if dir_path:
            self.output_dir = dir_path
            self.output_dir_edit.setText(dir_path)
            self.config['output_dir'] = dir_path
            
            # Ensure output directories exist
            os.makedirs(dir_path, exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'slides'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'audio'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'temp_pdf'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'chatgpt_prompts'), exist_ok=True)
            os.makedirs(os.path.join(dir_path, 'chatgpt_responses'), exist_ok=True)
            
            self.update_status(f"Output directory selected: {dir_path}")

    def load_config(self):
        """Load configuration from YAML file"""
        config_path = self.config_file_path
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
                logging.info(f"Configuration loaded from {config_path}")
                
                # Add output_dir to config
                self.config['output_dir'] = self.output_dir
                
                # Ensure output directories exist
                os.makedirs(self.output_dir, exist_ok=True)
                os.makedirs(os.path.join(self.output_dir, 'slides'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir, 'audio'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir, 'temp_pdf'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir, 'chatgpt_prompts'), exist_ok=True)
                os.makedirs(os.path.join(self.output_dir, 'chatgpt_responses'), exist_ok=True)
                
                return True
            except Exception as e:
                logging.error(f"Error loading config: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")
                return False
        else:
            logging.warning(f"Config file not found: {config_path}")
            return False

    def parse_latex(self):
        """Parse the LaTeX file and extract slides"""
        latex_file = self.latex_file_path
        if not latex_file:
            QMessageBox.critical(self, "Error", "Please select a LaTeX file first.")
            return
        
        if not os.path.exists(latex_file):
            QMessageBox.critical(self, "Error", f"LaTeX file not found: {latex_file}")
            return
        
        self.update_status("Parsing LaTeX file...")
        
        try:
            # Parse LaTeX file
            self.slides = parse_latex_file(latex_file)
            
            if not self.slides:
                QMessageBox.critical(self, "Error", "Failed to parse slides from LaTeX file.")
                self.update_status("Failed to parse LaTeX file.")
                return
            
            # Initialize narrations list with empty strings
            self.narrations = [""] * len(self.slides)
            
            # Update UI
            self.current_slide_index = 0
            self.update_slide_display()
            
            self.update_status(f"Successfully parsed {len(self.slides)} slides.")
            QMessageBox.information(self, "Success", f"Successfully parsed {len(self.slides)} slides.")

            # Copy generated PDF to output/temp_pdf
            try:
                base_name = os.path.splitext(os.path.basename(self.latex_file_path))[0]
                src_pdf = os.path.join(os.path.dirname(self.latex_file_path), f"{base_name}.pdf")
                dest_dir = os.path.join(self.output_dir, "temp_pdf")
                dest_pdf = os.path.join(dest_dir, f"{base_name}.pdf")
                if os.path.exists(src_pdf):
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(src_pdf, dest_pdf)
                    logging.info(f"[PARSE_LATEX] Copied PDF from {src_pdf} to {dest_pdf}")
                else:
                    logging.warning(f"[PARSE_LATEX] PDF not found to copy: {src_pdf}")
            except Exception as e:
                logging.error(f"[PARSE_LATEX] Error copying PDF after parse: {e}")

        except Exception as e:
            logging.error(f"Error parsing LaTeX file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to parse LaTeX file: {e}")

    def _generate_scripts_worker(self, client):
        """Worker function for generating scripts with OpenAI API"""
        try:
            logging.info("========== SCRIPT GENERATION STARTED ==========")
            logging.info(f"Worker thread ID: {threading.get_ident()}")
            narrations = []
            prompts = []
            
            # Add more detailed logging
            logging.info(f"Starting to generate scripts for {len(self.slides)} slides")
            logging.info(f"OpenAI client initialized: {client is not None}")
            logging.info(f"OpenAI client type: {type(client)}")
            logging.info(f"Using model: {self.config.get('openai', {}).get('model', 'gpt-4o')}")
            logging.info(f"Config contents: {self.config}")
            
            for i, slide in enumerate(self.slides):
                try:
                    # Format slide for script generation
                    formatted_content = format_slide_for_chatgpt(slide, self.slides, i)
                    
                    # Store the prompt
                    prompts.append(formatted_content)
                    
                    # Log the prompt being sent (first 100 chars)
                    prompt_preview = formatted_content[:100] + "..." if len(formatted_content) > 100 else formatted_content
                    logging.info(f"Sending prompt for slide {i+1}: {prompt_preview}")
                    
                    # Generate script with OpenAI
                    status_msg = f"Generating script for slide {i+1}/{len(self.slides)}: {slide.title}"
                    logging.info(status_msg)
                    
                    # More detailed logging before API call
                    logging.info(f"Calling OpenAI API for slide {i+1}")
                    logging.info(f"OpenAI client: {client}")
                    logging.info(f"OpenAI config: {self.config.get('openai', {})}")
                    
                    try:
                        logging.info("About to call generate_script_with_openai")
                        script = generate_script_with_openai(client, formatted_content, self.config)
                        logging.info(f"OpenAI API call completed. Response received: {bool(script)}")
                    except Exception as api_error:
                        logging.error(f"Error calling OpenAI API: {api_error}")
                        logging.error(f"Error details: {str(api_error)}")
                        script = None
                    
                    if script:
                        # Clean the response
                        cleaned_script = clean_chatgpt_response(script)
                        narrations.append(cleaned_script)
                        logging.info(f"Successfully generated script for slide {i+1}")
                    else:
                        logging.info(f"Failed to generate script for slide {i+1}, using placeholder")
                        # Add a placeholder script
                        narrations.append(f"Script for slide {i+1} could not be generated.")
                    
                    # Save the prompt to a file
                    prompts_dir = os.path.join(self.output_dir, 'chatgpt_prompts')
                    os.makedirs(prompts_dir, exist_ok=True)
                    prompt_path = os.path.join(prompts_dir, f"slide_{i+1}_prompt.txt")
                    
                    with open(prompt_path, 'w', encoding='utf-8') as f:
                        f.write(formatted_content)
                        
                except Exception as slide_error:
                    # Catch errors for individual slides but continue processing
                    error_msg = f"Error processing slide {i+1}: {str(slide_error)}"
                    logging.error(error_msg)
                    narrations.append(f"Error generating script for slide {i+1}: {str(slide_error)}")
            
            return {"narrations": narrations, "prompts": prompts}
            
        except Exception as e:
            logging.error(f"Error in generate_scripts_worker: {e}")
            import traceback
            logging.error(traceback.format_exc())
            raise
    
    def _on_scripts_generated(self, result):
        """Handle the result of script generation"""
        narrations = result.get("narrations", [])
        prompts = result.get("prompts", [])
        
        if not narrations:
            QMessageBox.critical(self, "Error", "Failed to generate narration scripts.")
            self.update_status("Failed to generate narration scripts.")
            return
        
        # Store the narrations and prompts
        self.narrations = narrations
        self.prompts = prompts
        
        # Update the display
        self.update_slide_display()
        
        self.update_status(f"Generated {len(narrations)} narration scripts.")
        QMessageBox.information(self, "Success", f"Generated {len(narrations)} narration scripts.")

    def _on_error(self, error_msg):
        """Handle errors from worker threads"""
        QMessageBox.critical(self, 'Error', f'An error occurred: {error_msg}')
        self.update_status(f'Error: {error_msg}')

    def save_scripts(self):
        """Save the current narration scripts"""
        if not self.slides or not self.narrations:
            QMessageBox.critical(self, "Error", "No narration scripts to save.")
            return
        
        # Update the current narration from the text widget
        current_narration = self.narration_text.toPlainText().strip()
        if self.current_slide_index < len(self.narrations):
            self.narrations[self.current_slide_index] = current_narration
        
        # Save all narrations to files
        output_dir = os.path.join(self.output_dir, 'chatgpt_responses')
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            for i, narration in enumerate(self.narrations):
                file_path = os.path.join(output_dir, f"slide_{i+1}_response.txt")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(narration)
            
            self.update_status("Narration scripts saved.")
            QMessageBox.information(self, "Success", f"Narration scripts saved to {output_dir}")
            
        except Exception as e:
            logging.error(f"Error saving scripts: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save scripts: {e}")
            self.update_status("Error saving scripts.")

    def load_scripts(self):
        """Load narration scripts and prompts from files"""
        if not self.slides:
            QMessageBox.critical(self, "Error", "No slides available. Please parse a LaTeX file first.")
            return
        
        responses_dir = os.path.join(self.output_dir, 'chatgpt_responses')
        prompts_dir = os.path.join(self.output_dir, 'chatgpt_prompts')
        
        if not os.path.exists(responses_dir):
            QMessageBox.critical(self, "Error", f"Responses directory not found: {responses_dir}")
            return
        
        try:
            # Initialize narrations list if needed
            if len(self.narrations) != len(self.slides):
                self.narrations = [""] * len(self.slides)
            
            # Initialize prompts list if needed
            if len(self.prompts) != len(self.slides):
                self.prompts = [""] * len(self.slides)
            
            # Load responses for all slides
            for i in range(len(self.slides)):
                response_path = os.path.join(responses_dir, f'slide_{i+1}_response.txt')
                if os.path.exists(response_path):
                    with open(response_path, 'r', encoding='utf-8') as f:
                        self.narrations[i] = f.read().strip()
            
            # Load prompts for all slides if they exist
            if os.path.exists(prompts_dir):
                for i in range(len(self.slides)):
                    prompt_path = os.path.join(prompts_dir, f'slide_{i+1}_prompt.txt')
                    if os.path.exists(prompt_path):
                        with open(prompt_path, 'r', encoding='utf-8') as f:
                            self.prompts[i] = f.read().strip()
            
            # Update the display
            self.update_slide_display()
            
            self.update_status('Scripts loaded.')
            QMessageBox.information(self, 'Success', 'Scripts and prompts loaded.')
            
        except Exception as e:
            logging.error(f'Error loading scripts: {e}')
            QMessageBox.critical(self, 'Error', f'Failed to load scripts: {e}')
            self.update_status('Error loading scripts.')

    def prev_slide(self):
        """Navigate to the previous slide"""
        if not self.slides:
            return
        
        # Save current narration
        current_narration = self.narration_text.toPlainText().strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Move to previous slide
        if self.current_slide_index > 0:
            self.current_slide_index -= 1
            self.update_slide_display()

    def next_slide(self):
        """Navigate to the next slide"""
        if not self.slides:
            return
        
        # Save current narration
        current_narration = self.narration_text.toPlainText().strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Move to next slide
        if self.current_slide_index < len(self.slides) - 1:
            self.current_slide_index += 1
            self.update_slide_display()

    def update_slide_display(self):
        """Update the display with the current slide"""
        if not self.slides or self.current_slide_index >= len(self.slides):
            return
        
        # Get current slide, narration, and prompt
        slide = self.slides[self.current_slide_index]
        narration = self.narrations[self.current_slide_index] if self.current_slide_index < len(self.narrations) else ""
        
        # Get prompt if available, otherwise use an empty string
        prompt = ""
        if len(self.prompts) > self.current_slide_index:
            prompt = self.prompts[self.current_slide_index]
        
        # If no prompt is available, try to load it from file
        if not prompt:
            prompt_path = os.path.join(self.output_dir, 'chatgpt_prompts', f'slide_{self.current_slide_index + 1}_prompt.txt')
            if os.path.exists(prompt_path):
                try:
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        prompt = f.read().strip()
                        # Store the prompt for future use
                        if len(self.prompts) <= self.current_slide_index:
                            self.prompts.extend([''] * (self.current_slide_index + 1 - len(self.prompts)))
                        self.prompts[self.current_slide_index] = prompt
                except Exception as e:
                    logging.error(f'Error loading prompt: {e}')
        
        # Update ChatGPT response panel with the narration
        self.slide_content_text.clear()
        self.slide_content_text.append(narration)
        
        # Update ChatGPT prompt panel with the prompt
        self.narration_text.clear()
        self.narration_text.append(prompt)
        
        # Update slide label
        self.slide_label.setText(f'Slide: {self.current_slide_index + 1}/{len(self.slides)}')
        
        # Try to load and display the slide image
        self.load_slide_image()

    def load_slide_image(self):
        """Load and display the current slide image if it exists"""
        # Clear current image
        self.slide_image_label.clear()
        self.slide_image_label.setText('No image available')
        
        # Check if the slides directory exists
        slides_dir = os.path.join(self.output_dir, 'slides')
        if not os.path.exists(slides_dir):
            return
        
        # Try to find the image for the current slide
        slide_number = self.current_slide_index + 1
        
        # Store the image path for potential resizing
        self.current_image_path = None
        
        # Check for common image formats, with and without leading zeros
        for ext in ['png', 'jpg', 'jpeg']:
            # Try with leading zeros (slide_001.png)
            image_path_zeros = os.path.join(slides_dir, f'slide_{slide_number:03d}.{ext}')
            if os.path.exists(image_path_zeros):
                try:
                    pixmap = QPixmap(image_path_zeros)
                    if not pixmap.isNull():
                        self.current_image_path = image_path_zeros
                        pixmap = pixmap.scaled(
                            self.slide_image_label.width(),
                            self.slide_image_label.height(),
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        self.slide_image_label.setPixmap(pixmap)
                        self.slide_image_label.setText('')
                        self.update_status(f'Loaded slide image: {image_path_zeros}')
                        return
                except Exception as e:
                    logging.error(f'Error loading image {image_path_zeros}: {e}')
            # Try without leading zeros (slide_1.png)
            image_path = os.path.join(slides_dir, f'slide_{slide_number}.{ext}')
            if os.path.exists(image_path):
                try:
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        self.current_image_path = image_path
                        pixmap = pixmap.scaled(
                            self.slide_image_label.width(),
                            self.slide_image_label.height(),
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        self.slide_image_label.setPixmap(pixmap)
                        self.slide_image_label.setText('')
                        self.update_status(f'Loaded slide image: {image_path}')
                        return
                except Exception as e:
                    logging.error(f'Error loading image {image_path}: {e}')

    def generate_scripts(self):
        """Generate narration scripts for all slides using OpenAI API"""
        if not self.slides:
            QMessageBox.critical(self, "Error", "No slides available. Please parse a LaTeX file first.")
            return

        # Check if config is loaded
        if not self.load_config():
            QMessageBox.critical(self, "Error", "Failed to load configuration. Please check your config file.")
            return

        # Initialize OpenAI client
        try:
            from src.openai_script_generator import initialize_openai_client
            client = initialize_openai_client(self.config)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initialize OpenAI client: {e}")
            return

        if not client:
            QMessageBox.critical(self, "Error", "Failed to initialize OpenAI client. Please check your API key in the config file.")
            return

        self.update_status("Generating narration scripts with OpenAI API...")

        # Create a worker thread
        thread = QThread()
        worker = Worker(self._generate_scripts_worker, client)
        worker.moveToThread(thread)

        # Keep explicit references to prevent garbage collection
        self._current_scripts_thread = thread
        self._current_scripts_worker = worker

        # Connect signals
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        worker.result.connect(self._on_scripts_generated)
        worker.error.connect(self._on_error)
        worker.progress.connect(self.update_status)

        # Start the thread
        thread.start()
        print("[PRINT-DEBUG] QThread started for script generation")

        # Keep a reference to the thread
        self.threads.append(thread)

    def generate_images(self):
        """Generate images from the LaTeX file"""
        print("[PRINT-DEBUG] ENTERED generate_images(self)")
        if not self.load_config():
            return

        latex_file = self.latex_file_path
        output_dir = self.output_dir
        logging.info(f"[DEBUG] generate_images: latex_file={latex_file}")
        logging.info(f"[DEBUG] generate_images: output_dir={output_dir}")
        if not latex_file or not os.path.exists(latex_file):
            QMessageBox.critical(self, 'Error', 'Please select a valid LaTeX file first.')
            return

        # Check if PDF exists before conversion
        pdf_path = os.path.join(output_dir, "temp_pdf", os.path.splitext(os.path.basename(latex_file))[0] + ".pdf")
        logging.info(f"[DEBUG] generate_images: expected PDF path={pdf_path}, exists={os.path.exists(pdf_path)}")

        self.update_status('Generating slide images...')

        # Create a worker thread
        thread = QThread()
        worker = Worker(self._generate_images_worker, latex_file)
        worker.moveToThread(thread)

        # Keep explicit references to prevent garbage collection
        self._current_image_thread = thread
        self._current_image_worker = worker

        # Connect signals
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        worker.result.connect(self._on_images_generated)
        worker.error.connect(self._on_error)

        # Start the thread
        thread.start()
        print("[PRINT-DEBUG] QThread started for image generation")

        # Keep a reference to the thread
        self.threads.append(thread)

    def _generate_images_worker(self, latex_file):
        """Worker function for generating images"""
        print("[PRINT-DEBUG] ENTERED _generate_images_worker")
        # Add the LaTeX file path to the configuration
        config_copy = self.config.copy()
        config_copy['latex_file_path'] = os.path.abspath(latex_file)
        
        print("[PRINT-DEBUG] About to call generate_slide_images in src.image_generator.py")
        # Generate slide images
        return generate_slide_images(latex_file, config_copy)

    def _on_images_generated(self, image_paths):
        """Handle the result of image generation"""
        if not image_paths:
            QMessageBox.critical(self, 'Error', 'Failed to generate slide images.')
            self.update_status('Failed to generate slide images.')
            return
        
        self.update_status(f'Generated {len(image_paths)} slide images.')
        
        # Update the slide display to show the current slide image
        self.load_slide_image()
        
        QMessageBox.information(self, 'Success', f'Generated {len(image_paths)} slide images.')

    def generate_audio(self):
        """Generate audio files from narration scripts"""
        if not self.load_config():
            return
        
        if not self.slides or not self.narrations:
            QMessageBox.critical(self, 'Error', 'No narration scripts available. Please generate scripts first.')
            return
        
        # Save current narration
        current_narration = self.narration_text.toPlainText().strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Save all narrations to files first
        self.save_scripts()
        
        self.update_status('Generating audio files...')
        
        # Create a worker thread
        thread = QThread()
        worker = Worker(self._generate_audio_worker)
        worker.moveToThread(thread)
        
        # Connect signals
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        worker.result.connect(self._on_audio_generated)
        worker.error.connect(self._on_error)
        
        # Start the thread
        thread.start()
        
        # Keep a reference to the thread
        self.threads.append(thread)

    def _generate_audio_worker(self):
        """Worker function for generating audio"""
        # Make a copy of the data to avoid thread issues
        narrations_copy = self.narrations.copy()
        config_copy = self.config.copy()
        
        # Generate audio files
        return generate_all_audio(narrations_copy, config_copy)

    def _on_audio_generated(self, audio_paths):
        """Handle the result of audio generation"""
        if not audio_paths:
            QMessageBox.critical(self, 'Error', 'Failed to generate audio files.')
            self.update_status('Failed to generate audio files.')
            return
        
        self.update_status(f'Generated {len(audio_paths)} audio files.')
        QMessageBox.information(self, 'Success', f'Generated {len(audio_paths)} audio files.')

    def assemble_video(self):
        """Assemble the final video from images and audio"""
        if not self.load_config():
            return
        
        # Check if images and audio files exist
        slides_dir = os.path.join(self.output_dir, 'slides')
        audio_dir = os.path.join(self.output_dir, 'audio')
        
        if not os.path.exists(slides_dir) or not os.listdir(slides_dir):
            QMessageBox.critical(self, 'Error', 'No slide images found. Please generate images first.')
            return
        
        if not os.path.exists(audio_dir) or not os.listdir(audio_dir):
            QMessageBox.critical(self, 'Error', 'No audio files found. Please generate audio first.')
            return
        
        self.update_status('Assembling video...')
        
        # Create a worker thread
        thread = QThread()
        worker = Worker(self._assemble_video_worker, slides_dir, audio_dir)
        worker.moveToThread(thread)
        
        # Connect signals
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        worker.result.connect(self._on_video_assembled)
        worker.error.connect(self._on_error)
        
        # Start the thread
        thread.start()
        
        # Keep a reference to the thread
        self.threads.append(thread)

    def _assemble_video_worker(self, slides_dir, audio_dir):
        """Worker function for assembling video"""
        # Get image and audio files
        image_files = sorted([os.path.join(slides_dir, f) for f in os.listdir(slides_dir) if f.endswith(('.png', '.jpg', '.jpeg'))])
        audio_files = sorted([os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith('.mp3')])
        
        if len(image_files) != len(audio_files):
            raise ValueError(f'Mismatch between number of images ({len(image_files)}) and audio files ({len(audio_files)}).')
        
        # Make a copy of the config to avoid thread issues
        config_copy = self.config.copy()
        
        # Assemble video
        return assemble_video(image_files, audio_files, config_copy)

    def _on_video_assembled(self, output_path):
        """Handle the result of video assembly"""
        if not output_path:
            QMessageBox.critical(self, 'Error', 'Failed to assemble video.')
            self.update_status('Failed to assemble video.')
            return
        
        self.update_status(f'Video assembled: {output_path}')
        QMessageBox.information(self, 'Success', f'Video assembled: {output_path}')

    def generate_all(self):
        """Generate everything: images, audio, and video"""
        if not self.load_config():
            return
        
        latex_file = self.latex_file_path
        if not latex_file or not os.path.exists(latex_file):
            QMessageBox.critical(self, 'Error', 'Please select a valid LaTeX file first.')
            return
        
        if not self.slides or not self.narrations:
            QMessageBox.critical(self, 'Error', 'No slides or narrations available. Please parse LaTeX and generate scripts first.')
            return
        
        # Save current narration
        current_narration = self.narration_text.toPlainText().strip()
        self.narrations[self.current_slide_index] = current_narration
        
        # Save all narrations to files
        self.save_scripts()
        
        self.update_status('Generating everything...')
        
        # Step 1: Generate images
        self.update_status('Step 1: Generating slide images...')
        
        # Create a worker thread for image generation
        thread1 = QThread()
        worker1 = Worker(self._generate_images_worker, latex_file)
        worker1.moveToThread(thread1)
        
        # Connect signals
        thread1.started.connect(worker1.run)
        worker1.finished.connect(thread1.quit)
        worker1.finished.connect(worker1.deleteLater)
        thread1.finished.connect(thread1.deleteLater)
        worker1.result.connect(lambda image_paths: self._continue_with_audio(image_paths))
        worker1.error.connect(self._on_error)
        
        # Start the thread
        thread1.start()
        
        # Keep a reference to the thread
        self.threads.append(thread1)
    
    def _continue_with_audio(self, image_paths):
        """Continue with audio generation after images are generated"""
        if not image_paths:
            QMessageBox.critical(self, 'Error', 'Failed to generate slide images.')
            self.update_status('Failed to generate slide images.')
            return
        
        self.update_status(f'Generated {len(image_paths)} slide images.')
        
        # Step 2: Generate audio
        self.update_status('Step 2: Generating audio files...')
        
        # Create a worker thread for audio generation
        thread2 = QThread()
        worker2 = Worker(self._generate_audio_worker)
        worker2.moveToThread(thread2)
        
        # Connect signals
        thread2.started.connect(worker2.run)
        worker2.finished.connect(thread2.quit)
        worker2.finished.connect(worker2.deleteLater)
        thread2.finished.connect(thread2.deleteLater)
        worker2.result.connect(lambda audio_paths: self._continue_with_video(image_paths, audio_paths))
        worker2.error.connect(self._on_error)
        
        # Start the thread
        thread2.start()
        
        # Keep a reference to the thread
        self.threads.append(thread2)
    
    def _continue_with_video(self, image_paths, audio_paths):
        """Continue with video assembly after audio is generated"""
        if not audio_paths:
            QMessageBox.critical(self, 'Error', 'Failed to generate audio files.')
            self.update_status('Failed to generate audio files.')
            return
        
        self.update_status(f'Generated {len(audio_paths)} audio files.')
        
        # Step 3: Assemble video
        self.update_status('Step 3: Assembling final video...')
        
        # Check if the number of images matches the number of audio files
        if len(image_paths) != len(audio_paths):
            QMessageBox.warning(self, 'Warning', 
                f'Mismatch between number of images ({len(image_paths)}) and audio files ({len(audio_paths)}). Using the minimum number.')
            # Use the minimum number of files
            count = min(len(image_paths), len(audio_paths))
            image_paths = image_paths[:count]
            audio_paths = audio_paths[:count]
        
        # Get the directories
        slides_dir = os.path.join(self.output_dir, 'slides')
        audio_dir = os.path.join(self.output_dir, 'audio')
        
        # Create a worker thread for video assembly
        thread3 = QThread()
        worker3 = Worker(self._assemble_video_worker, slides_dir, audio_dir)
        worker3.moveToThread(thread3)
        
        # Connect signals
        thread3.started.connect(worker3.run)
        worker3.finished.connect(thread3.quit)
        worker3.finished.connect(worker3.deleteLater)
        thread3.finished.connect(thread3.deleteLater)
        worker3.result.connect(self._on_video_assembled)
        worker3.error.connect(self._on_error)
        
        # Start the thread
        thread3.start()
        
        # Keep a reference to the thread
        self.threads.append(thread3)


def main():
    """Main function to run the PyQt5 GUI"""
    app = QApplication(sys.argv)
    window = LaTeX2VideoGUI()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
