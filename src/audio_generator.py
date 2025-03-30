import os
import logging
from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings, save
from typing import List, Dict, Optional
import yaml
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global client instance (initialize later)
client: Optional[ElevenLabs] = None

def initialize_elevenlabs_client(api_key: str):
    """Initializes the ElevenLabs client."""
    global client
    if not api_key:
        logging.error("ElevenLabs API key is missing in the configuration.")
        return False
    try:
        client = ElevenLabs(api_key=api_key)
        # Test connection by listing voices (optional, but good practice)
        client.voices.get_all() 
        logging.info("ElevenLabs client initialized successfully.")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize ElevenLabs client: {e}")
        client = None
        return False

def generate_audio_for_text(text: str, voice_id: str, model_id: str, output_path: str) -> bool:
    """Generates audio for a given text using ElevenLabs API and saves it."""
    global client
    if not client:
        logging.error("ElevenLabs client is not initialized.")
        return False
        
    logging.info(f"Generating audio for text (length: {len(text)} chars) -> {output_path}")
    
    try:
        # Note: ElevenLabs Python SDK v1+ handles SSML tags like <break> automatically.
        # We might need to adjust voice settings (stability, similarity) if needed.
        audio = client.generate(
            text=text,
            voice=Voice(
                voice_id=voice_id,
                # settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True) 
                # ^ Example settings, can be customized via config if needed
            ),
            model=model_id
        )
        
        save(audio, output_path)
        logging.info(f"Audio successfully saved to {output_path}")
        return True
        
    except Exception as e:
        logging.error(f"ElevenLabs API error generating audio for {output_path}: {e}")
        # Implement retry logic if desired
        return False

def generate_all_audio(narrations: List[str], config: Dict) -> List[str]:
    """Generates audio files for all narration scripts."""
    elevenlabs_config = config.get('elevenlabs', {})
    api_key = elevenlabs_config.get('api_key')
    voice_id = elevenlabs_config.get('voice_id', 'default') # Use default if not specified
    model_id = elevenlabs_config.get('model_id', 'eleven_multilingual_v2') # Default model

    output_base_dir = config.get('output_dir', '../output')
    audio_output_dir = os.path.abspath(os.path.join(output_base_dir, 'audio'))
    os.makedirs(audio_output_dir, exist_ok=True)

    if not initialize_elevenlabs_client(api_key):
        return []

    audio_paths = []
    total_narrations = len(narrations)
    for i, narration_text in enumerate(narrations):
        slide_num = i + 1
        output_file = os.path.join(audio_output_dir, f"audio_{slide_num}.mp3") # Assuming MP3 output
        
        logging.info(f"Processing audio for slide {slide_num}/{total_narrations}")
        
        success = generate_audio_for_text(narration_text, voice_id, model_id, output_file)
        
        if success:
            audio_paths.append(output_file)
        else:
            logging.error(f"Failed to generate audio for slide {slide_num}. Stopping.")
            # Decide if we should stop or continue despite errors
            return [] # Stop on first error for now

        # Add a small delay between API calls to avoid rate limiting
        time.sleep(1) 

    logging.info(f"Successfully generated {len(audio_paths)} audio files.")
    return audio_paths


if __name__ == '__main__':
    # Example usage:
    # Needs narrations generated first
    # Use absolute imports for standalone execution demonstration if needed,
    # but relative imports are preferred for package structure.
    # For this example run, we might need to adjust sys.path or run differently.
    # Let's assume running from parent dir for this example block.
    from latex_parser import parse_latex_file 
    from narration_generator import generate_all_narrations

    try:
        with open('../config/config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        cfg = {}

    if cfg:
        cfg['output_dir'] = '../output' # Ensure output dir is relative
        os.makedirs(os.path.join(cfg['output_dir'], 'audio'), exist_ok=True)

        sample_latex_file = '../assets/presentation.tex'
        parsed_slides = parse_latex_file(sample_latex_file)
        
        if parsed_slides:
            narrations = generate_all_narrations(parsed_slides, cfg)
            if narrations:
                generated_audio = generate_all_audio(narrations, cfg)
                if generated_audio:
                    print(f"Generated {len(generated_audio)} audio files:")
                    for aud in generated_audio:
                        print(aud)
                else:
                    print("Audio generation failed.")
            else:
                 print("Narration generation failed.")
        else:
            print("Could not parse slides.")
    else:
        print("Could not load configuration.")
