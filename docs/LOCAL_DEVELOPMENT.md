# Local Development Guide

## Prerequisites

- Python 3.8 or higher
- Git
- pip and virtualenv
- (Optional) Ollama for LLM inference

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-username/once-upon-a-time.git
cd once-upon-a-time
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (includes testing tools)
pip install -r requirements-dev.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env as needed
```

For local development, the defaults work well:

```bash
FLASK_ENV=development
MOCK_HARDWARE=True
TTS_PROVIDER=pyttsx3
```

### 5. Install Ollama (Optional)

For local LLM inference:

```bash
# Download from https://ollama.com
# Follow platform-specific instructions

# Start Ollama
ollama serve

# Pull a model
ollama pull gemma3:1b
```

If Ollama is not available, set `MOCK_OLLAMA=True` for mock responses.

## Running the Application

### Development Server

```bash
python -m raspi_storyteller.app
```

Access at:
- http://localhost:5000 - Main interface
- http://localhost:5000/manage - Card management
- http://localhost:5000/voice_test - Voice testing

### With Hot Reload

```bash
FLASK_DEBUG=True python -m raspi_storyteller.app
```

## Running Tests

### All Tests

```bash
pytest tests/ -v
```

### Specific Test File

```bash
pytest tests/test_state.py -v
```

### With Coverage

```bash
pytest tests/ --cov=raspi_storyteller --cov-report=html
open htmlcov/index.html
```

### Continuous Testing

```bash
# Run tests on file changes
pytest-watch tests/
```

## Code Quality

### Format Code

```bash
black src/ tests/
isort src/ tests/
```

### Check Style

```bash
flake8 src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Debugging

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG python -m raspi_storyteller.app
```

### Test Individual Components

```python
# In Python REPL
from raspi_storyteller.services.tts_engine import TTSEngine

engine = TTSEngine(provider="pyttsx3")
result = engine.synthesize_sync("Hello world")
print(result)
```

### Test API Endpoints

```bash
# Generate story
curl -X POST http://localhost:5000/api/story/generate \
  -H "Content-Type: application/json" \
  -d '{"animals": ["cat", "dog"]}'

# Get status
curl http://localhost:5000/api/status
```

## Common Issues

### "Module not found" Error

```bash
# Make sure you're in the project root
cd once-upon-a-time

# Ensure venv is activated
source venv/bin/activate

# Reinstall in editable mode
pip install -e .
```

### TTS Not Working

```bash
# Test pyttsx3 directly
python -c "import pyttsx3; e = pyttsx3.init(); print('OK')"

# If edge-tts issues
pip install --upgrade edge-tts
```

### Ollama Connection Error

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve
```

## Project Layout

```
once-upon-a-time/
├── src/raspi_storyteller/   # Main package
├── tests/                    # Test suite
├── templates/                # HTML templates
├── static/                   # CSS/JS files
├── docs/                     # Documentation
├── audio_cache/              # Generated audio (gitignored)
├── logs/                     # Application logs
├── requirements.txt          # Production deps
├── requirements-dev.txt      # Dev deps
├── pytest.ini                # Pytest config
└── .env                      # Local config (gitignored)
```
