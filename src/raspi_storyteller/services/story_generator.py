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

    # Single Master Prompt Template
    MASTER_PROMPT = """You are a master children's storyteller.

You need to generate a story based on the following elements:

STORY ELEMENTS:
- CHARACTERS:
{characters_description}
- SETTING: {environment}
- MORAL LESSON: {moral_lesson}

INSTRUCTIONS:
1. TARGET AUDIENCE: Children ages 4-8. Use simple, descriptive language appropriate for this age.
2. PLOT STRUCTURE:
   - Do NOT return title, introduction, or "Here is the story" or any other text that is not the story suchs as **title** or **end of the story**.
   - Beginning: Introduce the protagonists ({protagonists}) in the {environment}.
   - Middle: Introduce a conflict involving the moral lesson ({moral_lesson}). If there are generic villains/felons ({antagonists}), use them to create obstacles.
   - Climax: The protagonists overcome the challenge/villain using the moral lesson.
   - Ending: A happy resolution where the lesson is clearly learned.
3. CHARACTER ROLES:
   - Main Protagonists: Drive the action and learn the lesson.
   - Secondary Characters: Help the protagonists.
   - Minor Villains/Felons: Create mischief or small obstacles.
   - Evil Antagonists: Create major challenges (but keep it kid-friendly).
4. FORMATTING:
   - Write ONLY the story text.
   - Do NOT include title, introduction, or "Here is the story".
   - Use clear paragraphs.
   - Include dialogue to bring characters to life.   

VERY IMPORTANT: 
- No harmful content.
- DO NOT use complex or abstract concepts.
- Always keep in mind taht this is a story for kids up to 8 years old.
- Use simple, descriptive language appropriate for this age.
- You MUST generate the story in {target_language}.
- DO NOT add additional characters not specified in the prompt.
- The story should be {length_description}, approximately {word_target} words, divided into {paragraph_range} paragraphs.
- Do not use symbols or special characters that cannot be pronounced.
- ALWAYS KEEP IN MIND that the story will be read by an adult for a child.
"""


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
            language: Story language code (e.g., 'es', 'en', 'it').
            mock: If True, return mock stories for testing.
        """
        self.ollama_host = ollama_host
        self.model = model
        self.timeout = timeout
        self.language = language.lower()
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

    def _get_language_name(self, code: str) -> str:
        """Map language code to full name for the prompt."""
        from ..i18n import get_language_name
        return get_language_name(code)

    def _get_prompt(self, animals: List[str], story_minutes: int = 5) -> str:
        """
        Legacy wrapper for prompt generation.
        Converts old 'animals' list into character dicts and calls _get_enhanced_prompt.
        """
        characters = [
            {"name": animal, "species": animal, "role": "main" if i == 0 else "secondary"}
            for i, animal in enumerate(animals)
        ]
        return self._get_enhanced_prompt(
            characters=characters,
            environment="a magical place",
            moral_lesson="friendship",
            story_minutes=story_minutes
        )

    def _get_enhanced_prompt(
        self,
        characters: List[Dict[str, Any]],
        environment: str,
        moral_lesson: str,
        story_minutes: int = 5,
    ) -> str:
        """
        Generate prompt using the single English Master Template.
        """
        from ..hardware.length_slider import get_length_params

        length_params = get_length_params(story_minutes)
        target_language = self._get_language_name(self.language)

        # Process characters explicitly for the prompt instruction
        char_descriptions = []
        protagonists_list = []
        antagonists_list = []

        for char in characters:
            name = char.get("name", "Unknown")
            species = char.get("species", "Creature")
            # Default to secondary if role missing
            role_raw = char.get("role", "secondary") 
            
            # Map role to descriptive text
            role_map = {
                "main": "Main Protagonist",
                "secondary": "Secondary Character",
                "felon": "Minor Villain (Mischievous)",
                "evil": "Antagonist (Opposing)",
            }
            role_desc = role_map.get(role_raw, "Character")
            
            char_descriptions.append(f"- {name} ({species}): {role_desc}")

            if role_raw in ["main", "secondary"]:
                protagonists_list.append(name)
            elif role_raw in ["felon", "evil"]:
                antagonists_list.append(name)

        # Fallbacks for empty lists
        chars_text = "\n".join(char_descriptions) if char_descriptions else "- A mysterious friend"
        protagonists_text = ", ".join(protagonists_list) if protagonists_list else "the main characters"
        antagonists_text = ", ".join(antagonists_list) if antagonists_list else "any challenges"

        return self.MASTER_PROMPT.format(
            target_language=target_language,
            length_description=length_params["length_description"],
            word_target=length_params["word_target"],
            paragraph_range=length_params["paragraph_range"],
            characters_description=chars_text,
            environment=environment,
            moral_lesson=moral_lesson,
            protagonists=protagonists_text,
            antagonists=antagonists_text,
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
        animals_str = ", ".join(animals) if animals else "un gato y un perro"

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
        self.language = language.lower()
        logger.info(f"Language changed to: {self.language}")
