#!/usr/bin/env python3
import os
import sys
import logging
import argparse
from src.chatgpt_script_generator import clean_chatgpt_response

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_chatgpt_scripts(responses_dir: str, use_cleaned: bool = False):
    """Load ChatGPT-4o generated scripts from response files and clean them."""
    logging.info(f"Loading ChatGPT-4o scripts from {responses_dir}")
    
    # Check if we have cleaned responses available
    cleaned_dir = os.path.join(os.path.dirname(responses_dir), "cleaned_responses")
    if use_cleaned and os.path.exists(cleaned_dir) and os.listdir(cleaned_dir):
        logging.info(f"Using pre-cleaned responses from {cleaned_dir}")
        responses_dir = cleaned_dir
    
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
                
                # If we're not using pre-cleaned responses, clean them now
                if not use_cleaned:
                    script = clean_chatgpt_response(script)
                    logging.info(f"Cleaned script from {response_file}")
                
                if script:
                    scripts.append((response_file, script))
                    logging.info(f"Loaded script from {response_file}")
                else:
                    logging.warning(f"Script from {response_file} was empty after cleaning. Using placeholder.")
                    scripts.append((response_file, f"Script for slide could not be generated properly."))
        except Exception as e:
            logging.error(f"Error reading response file {response_path}: {e}")
    
    return scripts

def save_cleaned_scripts(scripts, output_dir: str):
    """Save cleaned scripts to files."""
    cleaned_dir = os.path.join(output_dir, "cleaned_responses")
    os.makedirs(cleaned_dir, exist_ok=True)
    
    for filename, script in scripts:
        # Create a new filename for the cleaned script
        cleaned_filename = filename.replace("_response.txt", "_cleaned.txt")
        cleaned_path = os.path.join(cleaned_dir, cleaned_filename)
        
        try:
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                f.write(script)
            logging.info(f"Saved cleaned script to {cleaned_path}")
        except Exception as e:
            logging.error(f"Error saving cleaned script to {cleaned_path}: {e}")
    
    return cleaned_dir

def main():
    """Main function to display ChatGPT-4o scripts."""
    parser = argparse.ArgumentParser(description="Display ChatGPT-4o scripts.")
    parser.add_argument("-r", "--responses", default="output/chatgpt_responses", help="Path to the directory containing ChatGPT-4o responses.")
    parser.add_argument("-c", "--cleaned", action="store_true", help="Use pre-cleaned responses if available.")
    parser.add_argument("-s", "--save", action="store_true", help="Save cleaned scripts to files.")
    
    args = parser.parse_args()
    
    # Load scripts
    scripts = load_chatgpt_scripts(args.responses, args.cleaned)
    
    # Save cleaned scripts if requested
    if args.save and scripts:
        output_dir = os.path.dirname(args.responses)
        cleaned_dir = save_cleaned_scripts(scripts, output_dir)
        print(f"\nSaved cleaned scripts to {cleaned_dir}")
    
    # Print scripts
    if scripts:
        print(f"\nLoaded {len(scripts)} scripts:")
        for i, (filename, script) in enumerate(scripts):
            print(f"\n--- Script {i+1}/{len(scripts)} ({filename}) ---")
            print(f"{script[:200]}...")  # Print first 200 chars
    else:
        print("No scripts loaded.")

if __name__ == "__main__":
    main()
