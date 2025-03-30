#!/usr/bin/env python3
import os
import sys
import logging
import yaml
import argparse
from typing import List, Dict
import time
from openai import OpenAI

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.latex_parser import parse_latex_file, Slide
from src.chatgpt_script_generator import format_slide_for_chatgpt
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

def initialize_openai_client(config: Dict) -> OpenAI:
    """Initialize the OpenAI client with API key from config."""
    openai_config = config.get('openai', {})
    api_key = openai_config.get('api_key')
    
    if not api_key:
        logging.error("OpenAI API key not found in config. Please add your API key to config/config.yaml")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        logging.error(f"Error initializing OpenAI client: {e}")
        return None

def generate_script_with_openai(client: OpenAI, prompt: str, config: Dict) -> str:
    """Generate a script for a slide using the OpenAI API."""
    openai_config = config.get('openai', {})
    model = openai_config.get('model', 'gpt-4o')
    temperature = openai_config.get('temperature', 0.7)
    max_tokens = openai_config.get('max_tokens', 1000)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert educational content creator who specializes in creating clear, concise narration scripts for educational videos. You explain complex concepts in an accessible way, with special attention to mathematical formulas."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        script = response.choices[0].message.content.strip()
        return script
    except Exception as e:
        logging.error(f"Error generating script with OpenAI: {e}")
        return ""

def generate_all_scripts(slides: List[Slide], client: OpenAI, config: Dict) -> List[str]:
    """Generate scripts for all slides using the OpenAI API."""
    scripts = []
    
    for i, slide in enumerate(slides):
        logging.info(f"Generating script for slide {i+1}/{len(slides)}: {slide.title}")
        
        # Format the slide content for ChatGPT
        prompt = format_slide_for_chatgpt(slide)
        
        # Generate script with OpenAI
        script = generate_script_with_openai(client, prompt, config)
        
        if script:
            scripts.append(script)
            logging.info(f"Successfully generated script for slide {i+1}")
        else:
            logging.error(f"Failed to generate script for slide {i+1}")
            # Add a placeholder script to maintain alignment with slides
            scripts.append(f"Script for slide {i+1} could not be generated.")
        
        # Add a small delay to avoid rate limiting
        time.sleep(1)
    
    return scripts

def save_scripts_to_files(scripts: List[str], output_dir: str) -> List[str]:
    """Save generated scripts to files."""
    os.makedirs(output_dir, exist_ok=True)
    
    file_paths = []
    for i, script in enumerate(scripts):
        file_name = f"slide_{i+1}_response.txt"
        file_path = os.path.join(output_dir, file_name)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(script)
        
        file_paths.append(file_path)
        logging.info(f"Saved script for slide {i+1} to {file_path}")
    
    return file_paths

def main():
    """Main function to automate the entire video generation process."""
    parser = argparse.ArgumentParser(description="Automate the entire process of generating a narrated video from a LaTeX presentation.")
    parser.add_argument("latex_file", help="Path to the input LaTeX (.tex) file.")
    parser.add_argument("-c", "--config", default="config/config.yaml", help="Path to the configuration YAML file.")
    parser.add_argument("-s", "--save-scripts", action="store_true", help="Save the generated scripts to files.")
    
    args = parser.parse_args()
    
    # Handle paths
    latex_path = os.path.abspath(args.latex_file)
    config_path = os.path.abspath(args.config)
    
    if not os.path.exists(latex_path):
        print(f"Error: LaTeX input file not found at {latex_path}")
        return
    elif not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        return
    
    # --- 1. Load Configuration ---
    logging.info("Step 1: Loading configuration...")
    config = load_config(config_path)
    if not config:
        logging.error("Failed to load configuration. Exiting.")
        return
    
    # Ensure output directories exist
    output_dir = config.get('output_dir', 'output')
    slides_dir = os.path.join(output_dir, 'slides')
    audio_dir = os.path.join(output_dir, 'audio')
    temp_pdf_dir = os.path.join(output_dir, 'temp_pdf')
    scripts_dir = os.path.join(output_dir, 'chatgpt_responses')
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(temp_pdf_dir, exist_ok=True)
    os.makedirs(scripts_dir, exist_ok=True)
    
    # --- 2. Initialize OpenAI Client ---
    logging.info("Step 2: Initializing OpenAI client...")
    client = initialize_openai_client(config)
    if not client:
        logging.error("Failed to initialize OpenAI client. Exiting.")
        return
    
    # --- 3. Parse LaTeX File ---
    logging.info("Step 3: Parsing LaTeX file...")
    slides = parse_latex_file(latex_path)
    if not slides:
        logging.error("Failed to parse slides from LaTeX file. Exiting.")
        return
    
    # --- 4. Generate Slide Images ---
    logging.info("Step 4: Generating slide images...")
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
    
    # --- 5. Generate Scripts with OpenAI ---
    logging.info("Step 5: Generating scripts with OpenAI...")
    scripts = generate_all_scripts(slides, client, config)
    
    # Save scripts if requested
    if args.save_scripts:
        logging.info(f"Saving scripts to {scripts_dir}...")
        save_scripts_to_files(scripts, scripts_dir)
    
    # --- 6. Generate Audio Files ---
    logging.info("Step 6: Generating audio files from scripts...")
    audio_paths = generate_all_audio(scripts, config)
    if not audio_paths:
        logging.error("Failed to generate audio files. Exiting.")
        return
    
    # --- 7. Assemble Final Video ---
    logging.info("Step 7: Assembling final video...")
    final_video_path = assemble_video(content_image_paths, audio_paths, config)
    if not final_video_path:
        logging.error("Failed to assemble the final video. Exiting.")
        return
    
    logging.info(f"--- Video Generation Complete ---")
    logging.info(f"Final video saved to: {final_video_path}")
    print(f"\nSuccess! Final video available at: {final_video_path}")

if __name__ == "__main__":
    main()
