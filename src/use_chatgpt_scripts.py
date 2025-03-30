#!/usr/bin/env python3
import os
import sys
import logging
import yaml
import argparse
from typing import List, Dict

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.latex_parser import parse_latex_file, Slide
from src.image_generator import generate_slide_images
from src.audio_generator import generate_all_audio
from src.simple_video_assembler import assemble_video

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config(config_path: str) -> dict:
    """Loads configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logging.info(f"Configuration loaded from {config_path}")
        # Add absolute path for output_dir based on config location
        config_dir = os.path.dirname(os.path.abspath(config_path))
        config['output_dir'] = os.path.abspath(os.path.join(config_dir, '..', 'output'))
        return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file {config_path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"An unexpected error occurred loading config: {e}")
        return {}

def load_chatgpt_scripts(responses_dir: str) -> List[str]:
    """Load ChatGPT-4o generated scripts from response files."""
    logging.info(f"Loading ChatGPT-4o scripts from {responses_dir}")
    
    if not os.path.exists(responses_dir):
        logging.error(f"Responses directory '{responses_dir}' not found.")
        return []
    
    # Get all response files
    response_files = sorted([f for f in os.listdir(responses_dir) if f.endswith("_response.txt")])
    if not response_files:
        logging.error(f"No response files found in '{responses_dir}'.")
        return []
    
    scripts = []
    for response_file in response_files:
        response_path = os.path.join(responses_dir, response_file)
        try:
            with open(response_path, 'r', encoding='utf-8') as f:
                script = f.read().strip()
                scripts.append(script)
                logging.info(f"Loaded script from {response_file}")
        except Exception as e:
            logging.error(f"Error reading response file {response_path}: {e}")
    
    return scripts

def main():
    """Main function to generate video using ChatGPT-4o scripts."""
    parser = argparse.ArgumentParser(description="Generate a narrated video using ChatGPT-4o scripts.")
    parser.add_argument("latex_file", help="Path to the input LaTeX (.tex) file.")
    parser.add_argument("-c", "--config", default="../config/config.yaml", help="Path to the configuration YAML file.")
    parser.add_argument("-r", "--responses", default="output/chatgpt_responses", help="Path to the directory containing ChatGPT-4o responses.")
    
    args = parser.parse_args()
    
    # Handle paths
    if not os.path.isabs(args.config):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.abspath(os.path.join(project_root, args.config))
    else:
        config_path = args.config
    
    latex_path = os.path.abspath(args.latex_file)
    responses_dir = os.path.abspath(args.responses)
    
    if not os.path.exists(latex_path):
        print(f"Error: LaTeX input file not found at {latex_path}")
        return
    elif not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        return
    
    # --- 1. Load Configuration ---
    config = load_config(config_path)
    if not config:
        logging.error("Failed to load configuration. Exiting.")
        return
    
    # Ensure output directories exist
    output_dir = config.get('output_dir', 'output')
    slides_dir = os.path.join(output_dir, 'slides')
    audio_dir = os.path.join(output_dir, 'audio')
    temp_pdf_dir = os.path.join(output_dir, 'temp_pdf')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(temp_pdf_dir, exist_ok=True)
    
    # --- 2. Parse LaTeX File ---
    logging.info("Step 1: Parsing LaTeX file...")
    slides = parse_latex_file(latex_path)
    if not slides:
        logging.error("Failed to parse slides from LaTeX file. Exiting.")
        return
    
    # --- 3. Generate Slide Images ---
    logging.info("Step 2: Generating slide images...")
    abs_latex_file_path = os.path.abspath(latex_path)
    image_paths = generate_slide_images(abs_latex_file_path, config)
    if not image_paths:
        logging.error("Failed to generate slide images. Exiting.")
        return
    
    # Adjust logic if title page image exists but wasn't parsed as a content slide
    if len(image_paths) == len(slides) + 1:
        logging.info("Detected an extra image, likely the title page. Excluding it from video content.")
        content_image_paths = image_paths[1:]
    elif len(image_paths) == len(slides):
        content_image_paths = image_paths
    else:
        logging.error(f"Mismatch after image generation: {len(image_paths)} images vs {len(slides)} parsed content slides. Exiting.")
        return
    
    # --- 4. Load ChatGPT-4o Scripts ---
    logging.info("Step 3: Loading ChatGPT-4o scripts...")
    scripts = load_chatgpt_scripts(responses_dir)
    if not scripts:
        logging.error("Failed to load ChatGPT-4o scripts. Exiting.")
        return
    
    if len(scripts) != len(slides):
        logging.warning(f"Mismatch between number of scripts ({len(scripts)}) and slides ({len(slides)}).")
        logging.warning("This may cause issues with audio-slide synchronization.")
    
    # --- 5. Generate Audio Files ---
    logging.info("Step 4: Generating audio files from ChatGPT-4o scripts...")
    audio_paths = generate_all_audio(scripts, config)
    if not audio_paths:
        logging.error("Failed to generate audio files. Exiting.")
        return
    
    # --- 6. Assemble Final Video ---
    logging.info("Step 5: Assembling final video...")
    final_video_path = assemble_video(content_image_paths, audio_paths, config)
    if not final_video_path:
        logging.error("Failed to assemble the final video. Exiting.")
        return
    
    logging.info(f"--- Video Generation Complete ---")
    logging.info(f"Final video saved to: {final_video_path}")
    print(f"\nSuccess! Final video available at: {final_video_path}")

if __name__ == "__main__":
    main()
