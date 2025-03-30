import os
import re
import subprocess
import logging
from pdf2image import convert_from_path
from typing import List, Dict, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config(config_path: str = '../config/config.yaml') -> Dict:
    """Loads configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logging.info(f"Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file {config_path}: {e}")
        return {}

def compile_latex_to_pdf(latex_file_path: str, output_dir: str) -> Optional[str]:
    """Compiles a LaTeX file to PDF using pdflatex."""
    if not os.path.exists(latex_file_path):
        logging.error(f"LaTeX source file not found: {latex_file_path}")
        return None

    file_name = os.path.basename(latex_file_path)
    base_name = os.path.splitext(file_name)[0]
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    logging.info(f"Compiling {latex_file_path} to PDF in {output_dir}...")
    
    # Run pdflatex twice for references/toc etc.
    for _ in range(2):
        try:
            # Use cwd=output_dir to keep aux files etc. contained
            # Use -output-directory to specify where PDF goes
            process = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', f'-output-directory={output_dir}', latex_file_path],
                capture_output=True, text=True, check=True, timeout=60
            )
            logging.debug(f"pdflatex run stdout:\n{process.stdout}")
            logging.debug(f"pdflatex run stderr:\n{process.stderr}")
        except FileNotFoundError:
            logging.error("pdflatex command not found. Please ensure LaTeX distribution (like TeX Live) is installed and in PATH.")
            return None
        except subprocess.CalledProcessError as e:
            logging.error(f"pdflatex compilation failed. Error:\n{e.stderr}")
            # Attempt to read the log file for more details
            log_file = os.path.join(output_dir, f"{base_name}.log")
            if os.path.exists(log_file):
                with open(log_file, 'r') as lf:
                    log_content = lf.read()
                logging.error(f"pdflatex log file ({log_file}):\n{log_content[-1000:]}") # Show last 1000 chars
            return None
        except subprocess.TimeoutExpired:
             logging.error("pdflatex compilation timed out.")
             return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during pdflatex compilation: {e}")
            return None

    if os.path.exists(pdf_path):
        logging.info(f"PDF successfully generated: {pdf_path}")
        return pdf_path
    else:
        logging.error(f"PDF file was not found after compilation: {pdf_path}")
        return None

def convert_pdf_to_images(pdf_path: str, output_folder: str, dpi: int, image_format: str) -> List[str]:
    """Converts each page of a PDF to an image."""
    if not os.path.exists(pdf_path):
        logging.error(f"PDF file not found for image conversion: {pdf_path}")
        return []
        
    logging.info(f"Converting PDF {pdf_path} to images (DPI: {dpi}, Format: {image_format})...")
    os.makedirs(output_folder, exist_ok=True)
    
    try:
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            output_folder=output_folder,
            fmt=image_format.lower(),
            output_file="slide_", # Generates slide_01-1.png, slide_01-2.png etc.
            paths_only=True,
            thread_count=4 # Use multiple threads for potentially faster conversion
        )
        
        # Rename files to simple slide_1.png, slide_2.png etc.
        image_paths = []
        # Sort images based on the number extracted from the filename
        images.sort(key=lambda x: int(re.search(r'-(\d+)\.', x).group(1))) 
        
        for i, img_path in enumerate(images):
            new_name = os.path.join(output_folder, f"slide_{i + 1}.{image_format.lower()}")
            # pdf2image might create files like slide_01-1.png, need robust renaming
            if os.path.exists(img_path):
                 os.rename(img_path, new_name)
                 image_paths.append(new_name)
                 logging.debug(f"Renamed {img_path} to {new_name}")
            else:
                 logging.warning(f"Expected image file not found after conversion: {img_path}")


        if not image_paths:
             logging.error("No images were generated from the PDF.")
             return []

        logging.info(f"Successfully converted PDF to {len(image_paths)} images in {output_folder}")
        return image_paths
        
    except Exception as e:
        # Catch potential Poppler errors or other issues
        logging.error(f"Error converting PDF to images: {e}")
        logging.error("Ensure Poppler utilities are installed and in PATH (needed by pdf2image).")
        return []

def generate_slide_images(latex_file_path: str, config: Dict) -> List[str]:
    """Orchestrates LaTeX compilation and PDF to image conversion."""
    output_base_dir = config.get('output_dir', '../output') # Get base output dir
    pdf_output_dir = os.path.abspath(os.path.join(output_base_dir, 'temp_pdf')) # Temp dir for PDF and logs
    slides_output_dir = os.path.abspath(os.path.join(output_base_dir, 'slides')) # Final images dir
    
    latex_config = config.get('latex', {})
    dpi = latex_config.get('dpi', 300)
    image_format = latex_config.get('image_format', 'png')

    # 1. Compile LaTeX to PDF
    pdf_path = compile_latex_to_pdf(latex_file_path, pdf_output_dir)
    if not pdf_path:
        return []

    # 2. Convert PDF to Images
    image_paths = convert_pdf_to_images(pdf_path, slides_output_dir, dpi, image_format)
    
    # Optional: Clean up temporary PDF and LaTeX aux files
    # Consider keeping logs for debugging
    # try:
    #     if os.path.exists(pdf_path): os.remove(pdf_path)
    #     # Add cleanup for .aux, .log, .nav, .snm, .toc files if desired
    # except OSError as e:
    #     logging.warning(f"Could not clean up temporary file {pdf_path}: {e}")

    return image_paths


if __name__ == '__main__':
    # Example usage:
    cfg = load_config()
    if cfg:
        latex_file = '../assets/presentation.tex' # Adjust path
        cfg['output_dir'] = '../output' # Ensure output dir is relative to this script if run directly
        
        # Ensure the output directories exist relative to the script location for standalone run
        os.makedirs(os.path.join(cfg['output_dir'], 'slides'), exist_ok=True)
        os.makedirs(os.path.join(cfg['output_dir'], 'temp_pdf'), exist_ok=True)

        generated_images = generate_slide_images(latex_file, cfg)
        if generated_images:
            print(f"Generated {len(generated_images)} images:")
            for img in generated_images:
                print(img)
        else:
            print("Image generation failed.")
