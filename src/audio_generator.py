import os
import logging
import time
from typing import List, Dict
import yaml

# Import the TTS provider interface and factory
from .tts_provider import create_tts_provider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_all_audio(narrations: List[str], config: Dict) -> List[str]:
    """Generates audio files for all narration scripts using the configured TTS provider."""
    logging.info("========== INICIANDO GERAÇÃO DE ÁUDIOS ==========")
    output_base_dir = config.get('output_dir', '../output')
    audio_output_dir = os.path.abspath(os.path.join(output_base_dir, 'audio'))
    os.makedirs(audio_output_dir, exist_ok=True)

    # Log config TTS
    tts_config = config.get('tts', {})
    logging.info(f"[AUDIO] Configuração TTS: {tts_config}")
    logging.info(f"[AUDIO] Configuração ElevenLabs: {config.get('elevenlabs', {})}")

    # Create the appropriate TTS provider based on configuration
    try:
        tts_provider = create_tts_provider(config)
        logging.info(f"[AUDIO] Provider TTS selecionado: {tts_provider.__class__.__name__}")
    except Exception as e:
        logging.error(f"[AUDIO] Falha ao inicializar provider TTS: {e}")
        return []

    audio_paths = []
    total_narrations = len(narrations)
    logging.info(f"[AUDIO] Total de narrações: {total_narrations}")
    
    for i, narration_text in enumerate(narrations):
        slide_num = i + 1
        output_file = os.path.join(audio_output_dir, f"audio_{slide_num}.mp3")
        
        logging.info(f"[AUDIO] --- Slide {slide_num}/{total_narrations} ---")
        logging.info(f"[AUDIO] Caminho de saída: {output_file}")
        logging.info(f"[AUDIO] Texto da narração (preview): {narration_text[:120].replace(chr(10), ' ')}")
        
        success = tts_provider.generate_audio(narration_text, output_file)
        
        if success:
            logging.info(f"[AUDIO] Áudio gerado com sucesso: {output_file}")
            audio_paths.append(output_file)
        else:
            logging.error(f"[AUDIO] Falha ao gerar áudio para o slide {slide_num}. Interrompendo o processo.")
            return [] # Stop on first error for now

        # Add a small delay between API calls to avoid rate limiting if using online services
        time.sleep(1)

    logging.info(f"[AUDIO] Geração de áudios finalizada. Total gerado: {len(audio_paths)}")
    return audio_paths


if __name__ == '__main__':
    # Example usage:
    # Needs narrations generated first
    from .latex_parser import parse_latex_file 
    from .narration_generator import generate_all_narrations

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
