"""
Story generation service using Ollama LLM.

Provides streaming story generation with paragraph detection and TTS integration.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..state import AudioSegment, Story
from ..utils.logger import get_logger
from .tts_engine import TTSEngine

logger = get_logger(__name__)

# Thread pool for sync operations
_executor = ThreadPoolExecutor(max_workers=2)


class StoryGenerator:
    """
    Generates stories using Ollama LLM with TTS integration.

    Features:
    - Streaming story generation
    - Paragraph-by-paragraph TTS processing
    - Parallel audio synthesis
    - Story caching
    """

    # Story prompt templates
    PROMPT_TEMPLATE_ES = """Eres un cuenta cuentos para niños. Genera una historia corta,
divertida y educativa de 3-4 párrafos sobre los siguientes animales: {animals}.

La historia debe:
- Ser apropiada para niños de 4-8 años
- Tener una moraleja o enseñanza
- Usar lenguaje simple y descriptivo
- Incluir diálogos entre los personajes

Escribe solo la historia, sin introducción ni comentarios adicionales."""

    PROMPT_TEMPLATE_EN = """You are a children's storyteller. Generate a short,
fun, and educational story of 3-4 paragraphs about the following animals: {animals}.

The story should:
- Be appropriate for children ages 4-8
- Have a moral or lesson
- Use simple, descriptive language
- Include dialogue between the characters

Write only the story, without introduction or additional comments."""

    PROMPT_TEMPLATE_IT = """Sei un narratore di storie per bambini. Genera una storia breve,
divertente ed educativa di 3-4 paragrafi sui seguenti animali: {animals}.

La storia deve:
- Essere appropriata per bambini di 4-8 anni
- Avere una morale o un insegnamento
- Usare un linguaggio semplice e descrittivo
- Includere dialoghi tra i personaggi

Scrivi solo la storia, senza introduzione o commenti aggiuntivi."""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "gemma3:1b",
        timeout: int = 120,
        language: str = "es",
        mock: bool = False,
    ):
        """
        Initialize the story generator.

        Args:
            ollama_host: Ollama server URL.
            model: LLM model to use.
            timeout: Request timeout in seconds.
            language: Story language ('es' or 'en').
            mock: If True, return mock stories for testing.
        """
        self.ollama_host = ollama_host
        self.model = model
        self.timeout = timeout
        self.language = language
        self.mock = mock
        self._client = None

        if not mock:
            self._init_client()

        logger.info(
            f"StoryGenerator initialized (model={model}, lang={language})"
        )

    def _init_client(self) -> None:
        """Initialize Ollama client."""
        try:
            import ollama

            self._client = ollama.Client(host=self.ollama_host)
            logger.debug(f"Ollama client initialized: {self.ollama_host}")
        except ImportError:
            logger.warning("ollama not installed, using mock mode")
            self.mock = True
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}")
            self.mock = True

    def _get_prompt(self, animals: List[str]) -> str:
        """Generate prompt for the given animals."""
        animals_str = ", ".join(animals) if animals else "a cat and a dog"

        if self.language == "es":
            return self.PROMPT_TEMPLATE_ES.format(animals=animals_str)
        elif self.language == "it":
            return self.PROMPT_TEMPLATE_IT.format(animals=animals_str)
        else:  # English is default
            return self.PROMPT_TEMPLATE_EN.format(animals=animals_str)

    def _get_mock_story(self, animals: List[str]) -> str:
        """Return a mock story for testing."""
        animals_str = ", ".join(animals) if animals else "un gato y un perro"

        if self.language == "es":
            return f"""Había una vez en un bosque mágico, {animals_str} que eran los mejores amigos. Aunque eran muy diferentes, siempre jugaban juntos y se ayudaban mutuamente.

Un día, encontraron un pequeño pájaro que había caído de su nido. "¡Tenemos que ayudarlo!" dijo uno de ellos. Juntos, trabajaron para devolver al pájaro a su hogar.

La mamá pájaro estaba muy agradecida. "Gracias, amables amigos," cantó ella. "Su bondad será recompensada."

Desde ese día, todos los animales del bosque aprendieron que la amistad y la ayuda mutua son los tesoros más valiosos. Y nuestros amigos vivieron felices, siempre dispuestos a ayudar a quien lo necesitara."""
        elif self.language == "it":
            return f"""C'era una volta in un bosco magico, {animals_str} che erano i migliori amici. Anche se erano molto diversi, giocavano sempre insieme e si aiutavano a vicenda.

Un giorno, trovarono un uccellino che era caduto dal suo nido. "Dobbiamo aiutarlo!" disse uno di loro. Insieme, lavorarono per riportare l'uccellino a casa.

La mamma uccello era molto grata. "Grazie, cari amici," cantò lei. "La vostra gentilezza sarà ricompensata."

Da quel giorno, tutti gli animali del bosco impararono che l'amicizia e l'aiuto reciproco sono i tesori più preziosi. E i nostri amici vissero felici, sempre pronti ad aiutare chiunque ne avesse bisogno."""
        else:  # English is default
            return f"""Once upon a time in a magical forest, there lived {animals_str} who were the best of friends. Although they were very different, they always played together and helped each other.

One day, they found a little bird that had fallen from its nest. "We must help it!" said one of them. Together, they worked to return the bird to its home.

The mother bird was very grateful. "Thank you, kind friends," she sang. "Your kindness will be rewarded."

From that day on, all the animals in the forest learned that friendship and mutual help are the most valuable treasures. And our friends lived happily, always ready to help anyone in need."""

    def detect_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs.

        Args:
            text: Full story text.

        Returns:
            List of paragraph strings.
        """
        # Split on double newlines or paragraph markers
        paragraphs = re.split(r"\n\s*\n", text.strip())

        # Filter empty paragraphs and strip whitespace
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # If no paragraph breaks found, split by sentences (groups of 2-3)
        if len(paragraphs) == 1 and len(text) > 200:
            sentences = re.split(r"(?<=[.!?])\s+", text)
            paragraphs = []
            current = []
            for sentence in sentences:
                current.append(sentence)
                if len(current) >= 2:
                    paragraphs.append(" ".join(current))
                    current = []
            if current:
                paragraphs.append(" ".join(current))

        return paragraphs

    async def generate_story(self, animals: List[str]) -> str:
        """
        Generate a story text (without audio).

        Args:
            animals: List of animal names for the story.

        Returns:
            Generated story text.
        """
        if self.mock:
            logger.info(f"[MOCK] Generating story for: {animals}")
            await asyncio.sleep(0.5)
            return self._get_mock_story(animals)

        prompt = self._get_prompt(animals)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor, self._generate_sync, prompt
            )
            return response
        except Exception as e:
            logger.error(f"Story generation failed: {e}")
            # Return mock story as fallback
            return self._get_mock_story(animals)

    def _generate_sync(self, prompt: str) -> str:
        """Synchronous story generation (runs in thread pool)."""
        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": 0.8, "num_predict": 500},
            )
            return response.get("response", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def generate_story_stream(
        self, animals: List[str]
    ) -> AsyncGenerator[str, None]:
        """
        Generate story with streaming output.

        Args:
            animals: List of animal names.

        Yields:
            Story text chunks as they're generated.
        """
        if self.mock:
            story = self._get_mock_story(animals)
            for word in story.split():
                yield word + " "
                await asyncio.sleep(0.02)
            return

        prompt = self._get_prompt(animals)

        try:
            for chunk in self._client.generate(
                model=self.model,
                prompt=prompt,
                stream=True,
                options={"temperature": 0.8, "num_predict": 500},
            ):
                if "response" in chunk:
                    yield chunk["response"]
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            # Yield mock story as fallback
            story = self._get_mock_story(animals)
            yield story

    async def generate_story_with_audio(
        self,
        animals: List[str],
        tts_engine: TTSEngine,
    ) -> Dict[str, Any]:
        """
        Generate a story with parallel TTS audio synthesis.

        Args:
            animals: List of animal names.
            tts_engine: TTS engine instance for audio synthesis.

        Returns:
            Dictionary with story text, audio segments, and metadata.
        """
        logger.info(f"Generating story with audio for: {animals}")

        # Generate story text
        full_text = await self.generate_story(animals)

        if not full_text:
            return {
                "full_text": "",
                "audio_segments": [],
                "animals": animals,
                "status": "error",
                "error": "Failed to generate story",
            }

        # Split into paragraphs
        paragraphs = self.detect_paragraphs(full_text)
        logger.info(f"Story has {len(paragraphs)} paragraphs")

        # Generate audio for each paragraph in parallel
        audio_segments = []
        tasks = [
            tts_engine.synthesize_async(para) for para in paragraphs
        ]

        audio_paths = await asyncio.gather(*tasks)

        for i, (para, audio_path) in enumerate(zip(paragraphs, audio_paths)):
            if audio_path:
                segment = AudioSegment(text=para, audio_path=audio_path)
                audio_segments.append(segment)
                logger.debug(f"Segment {i + 1}: {audio_path}")
            else:
                logger.warning(f"Failed to generate audio for paragraph {i + 1}")

        # Create Story object
        story = Story(
            full_text=full_text,
            audio_segments=audio_segments,
            animals=animals,
            status="success" if audio_segments else "partial",
        )

        result = {
            "full_text": full_text,
            "audio_segments": [
                {"text": seg.text, "audio": seg.audio_path}
                for seg in audio_segments
            ],
            "animals": animals,
            "status": story.status,
        }

        logger.info(
            f"Story generated: {len(full_text)} chars, "
            f"{len(audio_segments)} audio segments"
        )

        return result

    def set_language(self, language: str) -> None:
        """
        Change the story generation language.

        Args:
            language: Language code ('es' or 'en').
        """
        self.language = language
        logger.info(f"Language changed to: {language}")

    def set_model(self, model: str) -> None:
        """
        Change the LLM model.

        Args:
            model: Model name (e.g., 'gemma3:1b', 'llama2').
        """
        self.model = model
        logger.info(f"Model changed to: {model}")
