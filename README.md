# AI-powered Storyteller with Audio Integration

An interactive storytelling system that combines RFID card detection with AI-generated stories and text-to-speech audio playback. Designed for children's education and entertainment.

## Features

- **RFID Card Detection**: Tap RFID cards to select animals for story generation
- **AI Story Generation**: Uses Ollama LLM to create unique, child-friendly stories
- **Text-to-Speech**: Three TTS provider options (Edge TTS, pyttsx3, Google TTS)
- **Voice Commands**: Say "Tell me a story about a cat and a dog"
- **Web Interface**: Responsive UI with audio playback controls
- **LED Feedback**: Visual status indicators via NeoPixel LED ring
- **Offline Support**: Works without internet using pyttsx3 TTS

## Quick Start

### Prerequisites

- Python 3.8+
- Git
- (Optional) Ollama for local LLM inference

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/once-upon-a-time.git
cd once-upon-a-time

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install package and dependencies
pip install -e .

# Or for development with all tools:
# pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env

# Run the application
# Option 1: Using installed command (recommended)
raspi-storyteller

# Option 2: Using Python module
# python -m raspi_storyteller
```

### Access the Web Interface

- Main UI: http://localhost:5000
- Card Management: http://localhost:5000/manage
- Voice Test: http://localhost:5000/voice_test
- System Status: http://localhost:5000/status

### Verify Installation

```bash
# Check package is installed
pip show raspi_storyteller

# Check command is available
which raspi-storyteller
```

## Project Structure

```
once-upon-a-time/
├── src/
│   └── raspi_storyteller/
│       ├── app.py              # Main Flask application
│       ├── config.py           # Configuration management
│       ├── state.py            # State management
│       ├── hardware/           # Hardware abstraction layer
│       │   ├── rfid_handler.py
│       │   ├── led_controller.py
│       │   └── audio_device.py
│       ├── services/           # Business logic services
│       │   ├── tts_engine.py
│       │   ├── audio_manager.py
│       │   ├── speech_recognizer.py
│       │   └── story_generator.py
│       ├── routes/             # Flask routes
│       │   ├── api.py
│       │   └── web.py
│       └── utils/              # Utility modules
│           ├── logger.py
│           └── cache.py
├── templates/                  # HTML templates
├── static/                     # CSS and JavaScript
├── tests/                      # Test suite
├── docs/                       # Documentation
├── requirements.txt            # Production dependencies
└── requirements-dev.txt        # Development dependencies
```

## Configuration

Configuration is managed through environment variables. See `.env.example` for all options.

Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `TTS_PROVIDER` | TTS engine (edge, pyttsx3, google) | pyttsx3 |
| `OLLAMA_HOST` | Ollama server URL | http://localhost:11434 |
| `OLLAMA_MODEL` | LLM model name | gemma3:1b |
| `MOCK_HARDWARE` | Simulate hardware for dev | True |
| `SPEECH_LANGUAGE` | Voice recognition language | es-ES |

## API Endpoints

### Story Generation

- `POST /api/story/generate` - Generate a new story
- `GET /api/story/current` - Get current story state

### Card Management

- `GET /api/cards` - List all registered cards
- `POST /api/cards/save` - Register a new card
- `DELETE /api/cards/delete/<uid>` - Remove a card

### Voice Commands

- `POST /api/voice/listen` - Listen for voice command
- `GET /api/voice/languages` - Available languages

See [docs/API.md](docs/API.md) for full API documentation.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=raspi_storyteller --cov-report=html
```

### Code Style

```bash
# Format code
black src/ tests/

# Check style
flake8 src/ tests/

# Type checking
mypy src/
```

## Raspberry Pi Deployment

For deployment on Raspberry Pi 5, see [docs/RASPBERRY_PI_DEPLOYMENT.md](docs/RASPBERRY_PI_DEPLOYMENT.md).

### Hardware Requirements

- Raspberry Pi 5 (16GB RAM recommended)
- RC522 RFID reader module
- NeoPixel/WS2812 LED ring (12 LEDs)
- Speaker (3.5mm or USB)
- (Optional) HAT microphone for voice commands

### Quick Deploy

```bash
# On Raspberry Pi
git clone https://github.com/your-username/once-upon-a-time.git
cd once-upon-a-time
./scripts/install_raspberry_pi.sh
```

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Web Interface (HTML/CSS/JS)                              │
├──────────────────────────────────────────────────────────┤
│ Flask Routes (api.py, web.py)                            │
├──────────────────────────────────────────────────────────┤
│ Services Layer                                           │
│ • TTSEngine (Edge/pyttsx3/Google)                        │
│ • AudioManager (pygame playback)                         │
│ • StoryGenerator (Ollama LLM)                            │
│ • SpeechRecognizer (Google STT)                          │
├──────────────────────────────────────────────────────────┤
│ Hardware Abstraction Layer                               │
│ • RFIDHandler (RC522/Mock)                               │
│ • LEDController (NeoPixel/Mock)                          │
│ • AudioDevice (speaker/mic detection)                    │
└──────────────────────────────────────────────────────────┘
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests: `pytest tests/ -v`
5. Commit: `git commit -m "Add amazing feature"`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Hackster's AI-powered Storyteller](https://www.hackster.io/) - Original inspiration
- [Fably](https://github.com/stefanom/fably) - Audio pipeline reference
- [Ollama](https://ollama.com/) - Local LLM inference
- [Edge TTS](https://github.com/rany2/edge-tts) - High-quality TTS
