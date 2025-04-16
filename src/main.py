import os
import logging
import yaml
import argparse
from .latex_parser import parse_latex_file
from .image_generator import generate_slide_images
from .narration_generator import generate_all_narrations
from .audio_generator import generate_all_audio
from .video_assembler import assemble_video

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s] - %(message)s')

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

def main(latex_file: str, config_file: str):
    """Main function to generate video from LaTeX presentation."""
    logging.info("--- Starting LaTeX to Video Generation ---")
    
    # --- 1. Load Configuration ---
    config = load_config(config_file)
    if not config:
        logging.error("Failed to load configuration. Exiting.")
        return
    
    # Add the LaTeX file path to the configuration
    config['latex_file_path'] = os.path.abspath(latex_file)

    # Ensure output directories exist
    output_dir = config.get('output_dir', 'output') # Default to 'output' relative to project root
    slides_dir = os.path.join(output_dir, 'slides')
    audio_dir = os.path.join(output_dir, 'audio')
    temp_pdf_dir = os.path.join(output_dir, 'temp_pdf')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(slides_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(temp_pdf_dir, exist_ok=True)
    logging.info(f"Ensured output directories exist in: {output_dir}")

    # --- 2. Parse LaTeX File ---
    logging.info("Step 1: Parsing LaTeX file...")
    slides = parse_latex_file(latex_file)
    if not slides:
        logging.error("Failed to parse slides from LaTeX file. Exiting.")
        return
    logging.info(f"Successfully parsed {len(slides)} slides.")

    # --- 3. Generate Slide Images ---
    logging.info("Step 2: Generating slide images...")
    # Pass the absolute path to the latex file to the image generator
    abs_latex_file_path = os.path.abspath(latex_file)
    image_paths = generate_slide_images(abs_latex_file_path, config)
    if not image_paths:
        logging.error("Failed to generate slide images. Exiting.")
        return
    # Simple check: number of images should match number of parsed content slides
    # Note: pdf2image generates one image per PDF page. If title page wasn't skipped
    # during PDF generation (it usually isn't), there might be one extra image.
    # We need to align images with parsed slides. Let's assume the first image is title page if needed.
    
    # Check if the number of images matches the number of slides
    if len(image_paths) == len(slides):
        logging.info("Number of images matches number of slides. All slides will be included in the video.")
        content_image_paths = image_paths
    else:
        logging.warning(f"Mismatch between images ({len(image_paths)}) and slides ({len(slides)}). Attempting to adjust...")
        
        # If we have more images than slides, use only the first len(slides) images
        if len(image_paths) > len(slides):
            logging.info(f"Using only the first {len(slides)} images.")
            content_image_paths = image_paths[:len(slides)]
        # If we have more slides than images, use only the first len(image_paths) slides
        elif len(slides) > len(image_paths):
            logging.info(f"Using only the first {len(image_paths)} slides for narration.")
            slides = slides[:len(image_paths)]
            content_image_paths = image_paths
        else:
            # This should never happen, but just in case
            logging.error("Unexpected error in image-slide matching. Exiting.")
            return
         
    logging.info(f"Successfully prepared {len(content_image_paths)} slides with matching images.")


    # --- 4. Generate Narration Scripts ---
    logging.info("Step 3: Generating narration scripts...")
    narrations = generate_all_narrations(slides, config)
    if not narrations or len(narrations) != len(slides):
        logging.error("Failed to generate narration scripts or mismatch in count. Exiting.")
        return
    logging.info(f"Successfully generated {len(narrations)} narration scripts.")

    # --- 5. Generate Audio Files ---
    logging.info("Step 4: Generating audio files...")
    audio_paths = generate_all_audio(narrations, config)
    if not audio_paths or len(audio_paths) != len(narrations):
        logging.error("Failed to generate audio files or mismatch in count. Exiting.")
        return
    logging.info(f"Successfully generated {len(audio_paths)} audio files.")

    # --- 6. Assemble Final Video ---
    logging.info("Step 5: Assembling final video...")
    # Ensure we pass the content images that match the audio/narrations
    final_video_path = assemble_video(content_image_paths, audio_paths, config)
    if not final_video_path:
        logging.error("Failed to assemble the final video. Exiting.")
        return
        
    logging.info(f"--- Video Generation Complete ---")
    logging.info(f"Final video saved to: {final_video_path}")
    print(f"\nSuccess! Final video available at: {final_video_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a narrated video from a LaTeX Beamer presentation.")
    parser.add_argument("latex_file", help="Path to the input LaTeX (.tex) file.")
    parser.add_argument("-c", "--config", default="../config/config.yaml", help="Path to the configuration YAML file (default: ../config/config.yaml relative to main.py).")
    
    args = parser.parse_args()

    # Handle paths - look relative to project root if path isn't absolute
    if not os.path.isabs(args.config):
        # Get project root by going up one level from src directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.abspath(os.path.join(project_root, args.config))
    else:
        config_path = args.config
        
    latex_path = args.latex_file
    # Assume latex_file path might be relative to where the script is called from
    # Make it absolute before passing it around
    latex_path = os.path.abspath(latex_path) 

    if not os.path.exists(latex_path):
         print(f"Error: LaTeX input file not found at {latex_path}")
    elif not os.path.exists(config_path):
         print(f"Error: Config file not found at {config_path}")
    else:
         main(latex_path, config_path)
