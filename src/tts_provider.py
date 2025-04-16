import os
import logging
from abc import ABC, abstractmethod
from typing import Optional
import re

# Import gTTS for Google Text-to-Speech
from gtts import gTTS

# Import ElevenLabs for compatibility with existing code
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import Voice, save
    ELEVENLABS_AVAILABLE = True
except (ImportError, NameError) as e:
    logging.warning(f"ElevenLabs import error: {e}. Falling back to gTTS.")
    ELEVENLABS_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    @abstractmethod
    def generate_audio(self, text: str, output_path: str) -> bool:
        """Generate audio for the given text and save to output_path."""
        pass
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess text to handle SSML tags and other provider-specific requirements."""
        return text

class GTTSProvider(TTSProvider):
    """Google Text-to-Speech provider implementation."""
    
    def __init__(self, language: str = 'pt', slow: bool = False):
        self.language = language
        self.slow = slow
        logging.info(f"Initialized gTTS provider with language: {language}")
    
    def preprocess_text(self, text: str) -> str:
        """Remove SSML tags that gTTS doesn't support."""
        # Remove <break> tags but add periods for pauses
        text = re.sub(r'<break time="([0-9\.]+)s"/>', '. ', text)
        # Remove any other XML/SSML tags
        text = re.sub(r'<[^>]+>', '', text)
        return text
    
    def generate_audio(self, text: str, output_path: str) -> bool:
        """Generate audio using Google Text-to-Speech."""
        try:
            # Preprocess text to remove SSML tags
            processed_text = self.preprocess_text(text)
            
            # Create gTTS object
            tts = gTTS(text=processed_text, lang=self.language, slow=self.slow)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Save to file
            tts.save(output_path)
            logging.info(f"Audio successfully saved to {output_path}")
            return True
        except Exception as e:
            logging.error(f"gTTS error generating audio for {output_path}: {e}")
            return False

class ElevenLabsProvider(TTSProvider):
    """ElevenLabs provider implementation."""
    
    def __init__(self, api_key: str, voice_id: str, model_id: str):
        if not ELEVENLABS_AVAILABLE:
            raise ImportError("ElevenLabs package is not installed. Install with: pip install elevenlabs")
        
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        
        try:
            self.client = ElevenLabs(api_key=api_key)
            # Test connection by listing voices (optional)
            self.client.voices.get_all()
            logging.info("ElevenLabs client initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize ElevenLabs client: {e}")
            self.client = None
            raise
    
    def generate_audio(self, text: str, output_path: str) -> bool:
        """Generate audio using ElevenLabs API."""
        if not self.client:
            logging.error("ElevenLabs client is not initialized.")
            return False
            
        logging.info(f"Generating audio with ElevenLabs for text (length: {len(text)} chars) -> {output_path}")
        
        try:
            # ElevenLabs Python SDK v1+ handles SSML tags like <break> automatically
            audio = self.client.generate(
                text=text,
                voice=Voice(voice_id=self.voice_id),
                model=self.model_id
            )
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            save(audio, output_path)
            logging.info(f"Audio successfully saved to {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"ElevenLabs API error generating audio for {output_path}: {e}")
            return False

def create_tts_provider(config: dict) -> TTSProvider:
    """Factory function to create the appropriate TTS provider based on configuration."""
    tts_config = config.get('tts', {})
    provider_name = tts_config.get('provider', 'gtts').lower()
    
    if provider_name == 'elevenlabs':
        elevenlabs_config = config.get('elevenlabs', {})
        api_key = elevenlabs_config.get('api_key')
        voice_id = elevenlabs_config.get('voice_id')
        model_id = elevenlabs_config.get('model_id', 'eleven_multilingual_v2')
        
        if not api_key:
            logging.warning("ElevenLabs API key is missing. Falling back to gTTS.")
            return GTTSProvider(language=tts_config.get('language', 'pt'))
        
        try:
            return ElevenLabsProvider(api_key, voice_id, model_id)
        except Exception as e:
            logging.error(f"Failed to initialize ElevenLabs provider: {e}. Falling back to gTTS.")
            return GTTSProvider(language=tts_config.get('language', 'pt'))
    else:
        # Default to gTTS
        return GTTSProvider(
            language=tts_config.get('language', 'pt'),
            slow=tts_config.get('slow', False)
        )
