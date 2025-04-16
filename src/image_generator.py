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
    
    # Get the directory where the source file is located
    source_dir = os.path.dirname(os.path.abspath(latex_file_path))
    
    # First try to compile in the source directory
    pdf_path_source = os.path.join(source_dir, f"{base_name}.pdf")
    
    # Also define the output path in the output directory
    pdf_path_output = os.path.join(output_dir, f"{base_name}.pdf")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    logging.info(f"Compiling {latex_file_path} to PDF in source directory: {source_dir}...")
    
    # Run pdflatex twice for references/toc etc.
    for i in range(2):
        try:
            # First try to compile in the source directory (without specifying output directory)
            process = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', latex_file_path],
                cwd=source_dir,  # Run in the source directory
                capture_output=True, text=True, timeout=60
            )
            
            # Log stdout/stderr for debugging
            if process.stdout:
                logging.debug(f"pdflatex run stdout:\n{process.stdout}")
            if process.stderr:
                logging.debug(f"pdflatex run stderr:\n{process.stderr}")
            
            # Check if the process was successful
            if process.returncode != 0:
                logging.warning(f"pdflatex returned non-zero exit code: {process.returncode}")
                # Continue anyway, as pdflatex might still have generated a usable PDF
                # despite warnings or non-fatal errors
        
        except FileNotFoundError:
            logging.error("pdflatex command not found. Please ensure LaTeX distribution (like TeX Live) is installed and in PATH.")
            return None
        except subprocess.TimeoutExpired:
            logging.error("pdflatex compilation timed out.")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during pdflatex compilation: {e}")
            # Continue to check if PDF was generated despite the error
    
    # Check if the PDF was generated in the source directory, regardless of pdflatex exit code
    if os.path.exists(pdf_path_source):
        # Check if the PDF file is valid (not empty)
        if os.path.getsize(pdf_path_source) > 0:
            logging.info(f"PDF successfully generated in source directory: {pdf_path_source}")
            
            # Copy the PDF to the output directory for further processing
            try:
                import shutil
                shutil.copy2(pdf_path_source, pdf_path_output)
                logging.info(f"PDF copied to output directory: {pdf_path_output}")
                return pdf_path_output
            except Exception as e:
                logging.error(f"Error copying PDF to output directory: {e}")
                # If we can't copy, still return the source PDF path
                return pdf_path_source
        else:
            logging.error(f"PDF file was generated but is empty: {pdf_path_source}")
            return None
    else:
        # If PDF doesn't exist in source directory, try to read the log file for more details
        log_file = os.path.join(source_dir, f"{base_name}.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as lf:
                    log_content = lf.read()
                logging.error(f"pdflatex log file ({log_file}):\n{log_content[-1000:]}") # Show last 1000 chars
            except Exception as e:
                logging.error(f"Error reading log file: {e}")
        
        logging.error(f"PDF file was not found after compilation. Tried: {pdf_path_source} and {pdf_path_output}")
        return None

def convert_pdf_to_images(pdf_path: str, output_folder: str, dpi: int, image_format: str) -> List[str]:
    """Converts each page of a PDF to an image."""
    if not os.path.exists(pdf_path):
        logging.error(f"PDF file not found for image conversion: {pdf_path}")
        return []
        
    logging.info(f"Converting PDF {pdf_path} to images (DPI: {dpi}, Format: {image_format})...")
    os.makedirs(output_folder, exist_ok=True)
    
    # List existing files in the output folder before conversion
    existing_files = set(os.listdir(output_folder))
    logging.debug(f"Existing files in output folder before conversion: {existing_files}")
    
    # Try multiple approaches to convert PDF to images
    image_paths = []
    
    # Approach 1: Default settings
    try:
        logging.info("Attempting conversion with default settings...")
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            output_folder=output_folder,
            fmt=image_format.lower(),
            paths_only=True
        )
        
        if images:
            logging.info(f"Successfully converted PDF to {len(images)} images with default settings")
            
            # Rename files to simple slide_1.png, slide_2.png etc.
            for i, img_path in enumerate(images):
                new_name = os.path.join(output_folder, f"slide_{i + 1}.{image_format.lower()}")
                try:
                    os.rename(img_path, new_name)
                    image_paths.append(new_name)
                    logging.debug(f"Renamed {img_path} to {new_name}")
                except Exception as rename_error:
                    logging.error(f"Error renaming {img_path} to {new_name}: {rename_error}")
                    # If renaming fails, still add the original path to the list
                    image_paths.append(img_path)
            
            return image_paths
        else:
            logging.warning("No images returned with default settings")
    except Exception as e:
        logging.error(f"Error with default settings: {e}")
    
    # Approach 2: Alternative settings
    try:
        logging.info("Attempting conversion with alternative settings (single thread, no pdftocairo)...")
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            output_folder=output_folder,
            fmt=image_format.lower(),
            paths_only=True,
            thread_count=1,
            use_pdftocairo=False
        )
        
        if images:
            logging.info(f"Successfully converted PDF to {len(images)} images with alternative settings")
            
            # Rename files to simple slide_1.png, slide_2.png etc.
            for i, img_path in enumerate(images):
                new_name = os.path.join(output_folder, f"slide_{i + 1}.{image_format.lower()}")
                try:
                    os.rename(img_path, new_name)
                    image_paths.append(new_name)
                    logging.debug(f"Renamed {img_path} to {new_name}")
                except Exception as rename_error:
                    logging.error(f"Error renaming {img_path} to {new_name}: {rename_error}")
                    # If renaming fails, still add the original path to the list
                    image_paths.append(img_path)
            
            return image_paths
        else:
            logging.warning("No images returned with alternative settings")
    except Exception as e:
        logging.error(f"Error with alternative settings: {e}")
    
    # Approach 3: Check if any images were created despite errors
    try:
        new_files = set(os.listdir(output_folder)) - existing_files
        image_files = [f for f in new_files if f.endswith(f'.{image_format.lower()}')]
        
        if image_files:
            logging.info(f"Found {len(image_files)} image files in output directory despite errors:")
            
            # Sort the image files by name
            image_files.sort()
            
            # Rename files to simple slide_1.png, slide_2.png etc.
            for i, img_file in enumerate(image_files):
                img_path = os.path.join(output_folder, img_file)
                new_name = os.path.join(output_folder, f"slide_{i + 1}.{image_format.lower()}")
                
                try:
                    os.rename(img_path, new_name)
                    image_paths.append(new_name)
                    logging.debug(f"Renamed {img_path} to {new_name}")
                except Exception as rename_error:
                    logging.error(f"Error renaming {img_path} to {new_name}: {rename_error}")
                    # If renaming fails, still add the original path to the list
                    image_paths.append(img_path)
            
            return image_paths
    except Exception as e:
        logging.error(f"Error checking for created images: {e}")
    
    logging.error("Failed to convert PDF to images with all methods")
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
