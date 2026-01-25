"""
Story generation service using Ollama LLM.

Provides streaming story generation with paragraph detection and TTS integration.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Add type hints here if needed

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

    # Story prompt templates with variable length support (legacy - animals only)
    PROMPT_TEMPLATE_ES = """Eres un cuenta cuentos para niños. Genera una historia {length_description},
divertida y educativa de {paragraph_range} sobre los siguientes animales: {animals}.
La historia debe tener aproximadamente {word_target} palabras.

La historia debe:
- Ser apropiada para niños de 4-8 años
- Tener una moraleja o enseñanza
- Usar lenguaje simple y descriptivo
- Incluir diálogos entre los personajes

Escribe solo la historia, sin introducción ni comentarios adicionales."""

    PROMPT_TEMPLATE_EN = """You are a children's storyteller. Generate a {length_description},
fun, and educational story of {paragraph_range} about the following animals: {animals}.
The story should be approximately {word_target} words.

The story should:
- Be appropriate for children ages 4-8
- Have a moral or lesson
- Use simple, descriptive language
- Include dialogue between the characters

Write only the story, without introduction or additional comments."""

    PROMPT_TEMPLATE_IT = """Sei un narratore di storie per bambini. Genera una storia {length_description},
divertente ed educativa di {paragraph_range} sui seguenti animali: {animals}.
La storia deve avere circa {word_target} parole.

La storia deve:
- Essere appropriata per bambini di 4-8 anni
- Avere una morale o un insegnamento
- Usare un linguaggio semplice e descrittivo
- Includere dialoghi tra i personaggi

Scrivi solo la storia, senza introduzione o commenti aggiuntivi."""

    # Enhanced prompt templates with characters, environment, and moral lesson
    ENHANCED_PROMPT_ES = """Eres un cuenta cuentos para niños. Genera una historia {length_description},
divertida y educativa de {paragraph_range}.
La historia debe tener aproximadamente {word_target} palabras.

PERSONAJES:
{characters_description}

AMBIENTACIÓN: La historia ocurre en {environment}.

MORALEJA: La historia debe enseñar sobre {moral_lesson}.

La historia debe:
- Ser apropiada para niños de 4-8 años
- Desarrollar la moraleja de forma natural a través de las acciones de los personajes
- Usar lenguaje simple y descriptivo
- Incluir diálogos entre los personajes
- Tener un final feliz que refuerce la enseñanza

Escribe solo la historia, sin introducción ni comentarios adicionales."""

    ENHANCED_PROMPT_EN = """You are a children's storyteller. Generate a {length_description},
fun, and educational story of {paragraph_range}.
The story should be approximately {word_target} words.

CHARACTERS:
{characters_description}

SETTING: The story takes place in {environment}.

MORAL LESSON: The story should teach about {moral_lesson}.

The story should:
- Be appropriate for children ages 4-8
- Develop the moral naturally through the characters' actions
- Use simple, descriptive language
- Include dialogue between the characters
- Have a happy ending that reinforces the lesson

Write only the story, without introduction or additional comments."""

    ENHANCED_PROMPT_IT = """Sei un narratore di storie per bambini. Genera una storia {length_description},
divertente ed educativa di {paragraph_range}.
La storia deve avere circa {word_target} parole.

PERSONAGGI:
{characters_description}

AMBIENTAZIONE: La storia si svolge in {environment}.

MORALE: La storia deve insegnare {moral_lesson}.

La storia deve:
- Essere appropriata per bambini di 4-8 anni
- Sviluppare la morale in modo naturale attraverso le azioni dei personaggi
- Usare un linguaggio semplice e descrittivo
- Includere dialoghi tra i personaggi
- Avere un finale felice che rafforzi l'insegnamento

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

    def _get_prompt(self, animals: List[str], story_minutes: int = 5) -> str:
        """
        Generate prompt for the given animals and story length (legacy).

        Args:
            animals: List of animal names.
            story_minutes: Target story duration in minutes (1-15).

        Returns:
            Formatted prompt string.
        """
        from ..hardware.length_slider import get_length_params

        animals_str = ", ".join(animals) if animals else "a cat and a dog"
        length_params = get_length_params(story_minutes)

        if self.language == "es":
            return self.PROMPT_TEMPLATE_ES.format(
                animals=animals_str,
                length_description=length_params["length_description"],
                paragraph_range=length_params["paragraph_range"],
                word_target=length_params["word_target"],
            )
        elif self.language == "it":
            return self.PROMPT_TEMPLATE_IT.format(
                animals=animals_str,
                length_description=length_params["length_description"],
                paragraph_range=length_params["paragraph_range"],
                word_target=length_params["word_target"],
            )
        else:  # English is default
            return self.PROMPT_TEMPLATE_EN.format(
                animals=animals_str,
                length_description=length_params["length_description"],
                paragraph_range=length_params["paragraph_range"],
                word_target=length_params["word_target"],
            )

    def _get_enhanced_prompt(
        self,
        characters: List[Dict[str, Any]],
        environment: str,
        moral_lesson: str,
        story_minutes: int = 5,
    ) -> str:
        """
        Generate enhanced prompt with characters, environment, and moral lesson.

        Args:
            characters: List of character dicts with name, species, and role.
            environment: The story setting.
            moral_lesson: The moral to teach.
            story_minutes: Target story duration in minutes.

        Returns:
            Formatted prompt string.
        """
        from ..hardware.length_slider import get_length_params

        length_params = get_length_params(story_minutes)

        # Build character descriptions based on language
        role_translations = {
            "es": {
                "main": "protagonista principal",
                "secondary": "personaje secundario",
                "felon": "villano menor",
                "evil": "antagonista malvado",
            },
            "en": {
                "main": "main protagonist",
                "secondary": "secondary character",
                "felon": "minor villain",
                "evil": "evil antagonist",
            },
            "it": {
                "main": "protagonista principale",
                "secondary": "personaggio secondario",
                "felon": "cattivo minore",
                "evil": "antagonista malvagio",
            },
        }

        roles = role_translations.get(self.language, role_translations["en"])
        char_lines = []
        for char in characters:
            name = char.get("name", char.get("species", "character"))
            species = char.get("species", "character")
            role = char.get("role", "secondary")
            role_desc = roles.get(role, roles["secondary"])
            char_lines.append(f"- {name} (un/una {species}): {role_desc}")

        characters_description = "\n".join(char_lines) if char_lines else "- Un personaje misterioso"

        if self.language == "es":
            return self.ENHANCED_PROMPT_ES.format(
                characters_description=characters_description,
                environment=environment,
                moral_lesson=moral_lesson,
                length_description=length_params["length_description"],
                paragraph_range=length_params["paragraph_range"],
                word_target=length_params["word_target"],
            )
        elif self.language == "it":
            return self.ENHANCED_PROMPT_IT.format(
                characters_description=characters_description,
                environment=environment,
                moral_lesson=moral_lesson,
                length_description=length_params["length_description"],
                paragraph_range=length_params["paragraph_range"],
                word_target=length_params["word_target"],
            )
        else:  # English is default
            return self.ENHANCED_PROMPT_EN.format(
                characters_description=characters_description,
                environment=environment,
                moral_lesson=moral_lesson,
                length_description=length_params["length_description"],
                paragraph_range=length_params["paragraph_range"],
                word_target=length_params["word_target"],
            )

    def _get_mock_story(self, animals: List[str], story_minutes: int = 5) -> str:
        """
        Return a mock story for testing with variable length.

        Args:
            animals: List of animal names.
            story_minutes: Target story duration (affects story length).

        Returns:
            Mock story text.
        """
        from ..hardware.length_slider import get_length_params

        animals_str = ", ".join(animals) if animals else "un gato y un perro"
        length_params = get_length_params(story_minutes)

        # Base story paragraphs for different languages
        if self.language == "es":
            base_paragraphs = [
                f"Había una vez en un bosque mágico, {animals_str} que eran los mejores amigos. Aunque eran muy diferentes, siempre jugaban juntos y se ayudaban mutuamente.",
                f"Un día, encontraron un pequeño pájaro que había caído de su nido. \"¡Tenemos que ayudarlo!\" dijo uno de ellos. Juntos, trabajaron para devolver al pájaro a su hogar.",
                f"La mamá pájaro estaba muy agradecida. \"Gracias, amables amigos,\" cantó ella. \"Su bondad será recompensada.\"",
                f"Desde ese día, todos los animales del bosque aprendieron que la amistad y la ayuda mutua son los tesoros más valiosos.",
                f"Y nuestros amigos vivieron felices, siempre dispuestos a ayudar a quien lo necesitara.",
                f"Cada mañana, {animals_str} se reunían bajo el gran roble para planear sus aventuras del día.",
                f"\"Hoy exploraremos el río,\" sugirió uno. \"¡Será una gran aventura!\" respondieron los demás con entusiasmo.",
                f"El río era cristalino y lleno de peces de colores que nadaban alegremente entre las piedras.",
                f"Mientras jugaban cerca del agua, escucharon un ruido extraño que venía de los arbustos cercanos.",
                f"Era un pequeño conejito que se había perdido y no podía encontrar el camino a casa.",
            ]
        elif self.language == "it":
            base_paragraphs = [
                f"C'era una volta in un bosco magico, {animals_str} che erano i migliori amici. Anche se erano molto diversi, giocavano sempre insieme e si aiutavano a vicenda.",
                f"Un giorno, trovarono un uccellino che era caduto dal suo nido. \"Dobbiamo aiutarlo!\" disse uno di loro. Insieme, lavorarono per riportare l'uccellino a casa.",
                f"La mamma uccello era molto grata. \"Grazie, cari amici,\" cantò lei. \"La vostra gentilezza sarà ricompensata.\"",
                f"Da quel giorno, tutti gli animali del bosco impararono che l'amicizia e l'aiuto reciproco sono i tesori più preziosi.",
                f"E i nostri amici vissero felici, sempre pronti ad aiutare chiunque ne avesse bisogno.",
                f"Ogni mattina, {animals_str} si ritrovavano sotto la grande quercia per pianificare le avventure del giorno.",
                f"\"Oggi esploreremo il fiume,\" suggerì uno. \"Sarà una grande avventura!\" risposero gli altri con entusiasmo.",
                f"Il fiume era cristallino e pieno di pesci colorati che nuotavano allegramente tra le pietre.",
                f"Mentre giocavano vicino all'acqua, sentirono uno strano rumore provenire dai cespugli vicini.",
                f"Era un piccolo coniglietto che si era perso e non riusciva a trovare la strada di casa.",
            ]
        else:  # English is default
            base_paragraphs = [
                f"Once upon a time in a magical forest, there lived {animals_str} who were the best of friends. Although they were very different, they always played together and helped each other.",
                f"One day, they found a little bird that had fallen from its nest. \"We must help it!\" said one of them. Together, they worked to return the bird to its home.",
                f"The mother bird was very grateful. \"Thank you, kind friends,\" she sang. \"Your kindness will be rewarded.\"",
                f"From that day on, all the animals in the forest learned that friendship and mutual help are the most valuable treasures.",
                f"And our friends lived happily, always ready to help anyone in need.",
                f"Every morning, {animals_str} would gather under the big oak tree to plan their adventures for the day.",
                f"\"Today we'll explore the river,\" suggested one. \"It will be a great adventure!\" the others replied with excitement.",
                f"The river was crystal clear and full of colorful fish swimming happily among the rocks.",
                f"While playing near the water, they heard a strange noise coming from the nearby bushes.",
                f"It was a little bunny who had gotten lost and couldn't find the way home.",
            ]

        # Determine number of paragraphs based on story length
        if story_minutes <= 3:
            num_paragraphs = 2
        elif story_minutes <= 6:
            num_paragraphs = 4
        elif story_minutes <= 9:
            num_paragraphs = 6
        elif story_minutes <= 12:
            num_paragraphs = 8
        else:
            num_paragraphs = 10

        # Use available paragraphs (repeat if needed for longer stories)
        selected_paragraphs = []
        for i in range(num_paragraphs):
            selected_paragraphs.append(base_paragraphs[i % len(base_paragraphs)])

        return "\n\n".join(selected_paragraphs)

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

    async def generate_story(self, animals: List[str], story_minutes: int = 5) -> str:
        """
        Generate a story text (without audio).

        Args:
            animals: List of animal names for the story.
            story_minutes: Target story duration in minutes (1-15).

        Returns:
            Generated story text.
        """
        from ..hardware.length_slider import get_length_params

        if self.mock:
            logger.info(f"[MOCK] Generating {story_minutes}-minute story for: {animals}")
            await asyncio.sleep(0.5)
            return self._get_mock_story(animals, story_minutes)

        prompt = self._get_prompt(animals, story_minutes)
        length_params = get_length_params(story_minutes)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor,
                lambda: self._generate_sync(prompt, length_params["token_limit"]),
            )
            return response
        except Exception as e:
            logger.error(f"Story generation failed: {e}")
            # Return mock story as fallback
            return self._get_mock_story(animals, story_minutes)

    def _generate_sync(self, prompt: str, num_predict: int = 500) -> str:
        """
        Synchronous story generation (runs in thread pool).

        Args:
            prompt: The prompt to send to the LLM.
            num_predict: Maximum number of tokens to generate.

        Returns:
            Generated story text.
        """
        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": 0.8, "num_predict": num_predict},
            )
            return response.get("response", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def generate_story_stream(
        self, animals: List[str], story_minutes: int = 5
    ) -> AsyncGenerator[str, None]:
        """
        Generate story with streaming output.

        Args:
            animals: List of animal names.
            story_minutes: Target story duration in minutes (1-15).

        Yields:
            Story text chunks as they're generated.
        """
        from ..hardware.length_slider import get_length_params

        if self.mock:
            story = self._get_mock_story(animals, story_minutes)
            for word in story.split():
                yield word + " "
                await asyncio.sleep(0.02)
            return

        prompt = self._get_prompt(animals, story_minutes)
        length_params = get_length_params(story_minutes)

        try:
            for chunk in self._client.generate(
                model=self.model,
                prompt=prompt,
                stream=True,
                options={"temperature": 0.8, "num_predict": length_params["token_limit"]},
            ):
                if "response" in chunk:
                    yield chunk["response"]
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            # Yield mock story as fallback
            story = self._get_mock_story(animals, story_minutes)
            yield story

    async def generate_story_with_audio(
        self,
        animals: List[str],
        tts_engine: TTSEngine,
        story_minutes: int = 5,
        story_elements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a story with parallel TTS audio synthesis.

        Args:
            animals: List of animal names (legacy, used if story_elements not provided).
            tts_engine: TTS engine instance for audio synthesis.
            story_minutes: Target story duration in minutes (1-15).
            story_elements: Optional dict with characters, environment, moral_lesson.

        Returns:
            Dictionary with story text, audio segments, and metadata.
        """
        # Extract story elements if provided
        characters = []
        environment = None
        moral_lesson = None

        if story_elements:
            characters = story_elements.get("characters", [])
            environment = story_elements.get("environment")
            moral_lesson = story_elements.get("moral_lesson")

        if characters:
            logger.info(
                f"Generating {story_minutes}-minute story with {len(characters)} characters, "
                f"environment: {environment}, moral: {moral_lesson}"
            )
        else:
            logger.info(f"Generating {story_minutes}-minute story with audio for: {animals}")

        # Generate story text using appropriate method
        if characters:
            full_text = await self.generate_story_enhanced(
                characters, environment, moral_lesson, story_minutes
            )
        else:
            full_text = await self.generate_story(animals, story_minutes)

        if not full_text:
            return {
                "full_text": "",
                "audio_segments": [],
                "animals": animals,
                "characters": characters,
                "environment": environment,
                "moral_lesson": moral_lesson,
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
            characters=characters,
            environment=environment,
            moral_lesson=moral_lesson,
            status="success" if audio_segments else "partial",
        )

        result = {
            "full_text": full_text,
            "audio_segments": [
                {"text": seg.text, "audio": seg.audio_path}
                for seg in audio_segments
            ],
            "animals": animals,
            "characters": characters,
            "environment": environment,
            "moral_lesson": moral_lesson,
            "status": story.status,
        }

        logger.info(
            f"Story generated: {len(full_text)} chars, "
            f"{len(audio_segments)} audio segments"
        )

        return result

    async def generate_story_enhanced(
        self,
        characters: List[Dict[str, Any]],
        environment: Optional[str],
        moral_lesson: Optional[str],
        story_minutes: int = 5,
    ) -> str:
        """
        Generate a story using enhanced prompt with characters, environment, and moral.

        Args:
            characters: List of character dicts with name, species, and role.
            environment: The story setting.
            moral_lesson: The moral to teach.
            story_minutes: Target story duration in minutes.

        Returns:
            Generated story text.
        """
        from ..hardware.length_slider import get_length_params

        # Use defaults if not provided
        if not environment:
            environment = "a magical forest"
        if not moral_lesson:
            moral_lesson = "friendship"

        if self.mock:
            logger.info(f"[MOCK] Generating enhanced {story_minutes}-minute story")
            await asyncio.sleep(0.5)
            return self._get_mock_story_enhanced(characters, environment, moral_lesson, story_minutes)

        prompt = self._get_enhanced_prompt(characters, environment, moral_lesson, story_minutes)
        length_params = get_length_params(story_minutes)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor,
                lambda: self._generate_sync(prompt, length_params["token_limit"]),
            )
            return response
        except Exception as e:
            logger.error(f"Enhanced story generation failed: {e}")
            return self._get_mock_story_enhanced(characters, environment, moral_lesson, story_minutes)

    def _get_mock_story_enhanced(
        self,
        characters: List[Dict[str, Any]],
        environment: str,
        moral_lesson: str,
        story_minutes: int = 5,
    ) -> str:
        """Return a mock story for testing with characters, environment, and moral."""
        # Get character names for the story
        char_names = [c.get("name", c.get("species", "friend")) for c in characters]
        chars_str = ", ".join(char_names) if char_names else "our friends"

        # Get the main character
        main_char = next(
            (c.get("name", c.get("species")) for c in characters if c.get("role") == "main"),
            char_names[0] if char_names else "the hero"
        )

        if self.language == "es":
            paragraphs = [
                f"Había una vez en {environment}, donde vivían {chars_str}. Eran muy diferentes pero compartían una gran amistad.",
                f"{main_char} era conocido por su valentía y buen corazón. Un día, mientras exploraba {environment}, encontró algo extraordinario.",
                f"\"¡Amigos, vengan a ver!\" llamó {main_char}. Todos corrieron a ver qué había descubierto.",
                f"Juntos, aprendieron una valiosa lección sobre {moral_lesson}. Desde ese día, siempre recordaron lo importante que es {moral_lesson}.",
                f"Y así, {chars_str} vivieron felices, compartiendo su sabiduría con todos los que conocían.",
            ]
        elif self.language == "it":
            paragraphs = [
                f"C'era una volta in {environment}, dove vivevano {chars_str}. Erano molto diversi ma condividevano una grande amicizia.",
                f"{main_char} era conosciuto per il suo coraggio e buon cuore. Un giorno, mentre esplorava {environment}, trovò qualcosa di straordinario.",
                f"\"Amici, venite a vedere!\" chiamò {main_char}. Tutti corsero a vedere cosa aveva scoperto.",
                f"Insieme, impararono una preziosa lezione su {moral_lesson}. Da quel giorno, ricordarono sempre quanto sia importante {moral_lesson}.",
                f"E così, {chars_str} vissero felici, condividendo la loro saggezza con tutti quelli che incontravano.",
            ]
        else:
            paragraphs = [
                f"Once upon a time in {environment}, there lived {chars_str}. They were very different but shared a great friendship.",
                f"{main_char} was known for being brave and kind-hearted. One day, while exploring {environment}, they found something extraordinary.",
                f"\"Friends, come and see!\" called {main_char}. Everyone rushed to see what had been discovered.",
                f"Together, they learned a valuable lesson about {moral_lesson}. From that day on, they always remembered how important {moral_lesson} is.",
                f"And so, {chars_str} lived happily, sharing their wisdom with everyone they met.",
            ]

        # Adjust length based on story_minutes
        if story_minutes <= 3:
            return "\n\n".join(paragraphs[:2])
        elif story_minutes <= 6:
            return "\n\n".join(paragraphs[:4])
        else:
            return "\n\n".join(paragraphs)

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
