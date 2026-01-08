# Raspberry Pi Deployment Guide

## Hardware Requirements

- Raspberry Pi 5 (16GB RAM recommended)
- MicroSD card (32GB+)
- RC522 RFID reader module
- NeoPixel/WS2812 LED ring (12 LEDs)
- Speaker (3.5mm jack or USB)
- (Optional) HAT microphone for voice commands
- RFID cards/tags

## Wiring Diagram

### RC522 RFID Reader

| RC522 Pin | Raspberry Pi Pin |
|-----------|-----------------|
| SDA | GPIO 8 (CE0) |
| SCK | GPIO 11 (SCLK) |
| MOSI | GPIO 10 (MOSI) |
| MISO | GPIO 9 (MISO) |
| GND | Ground |
| RST | GPIO 25 |
| 3.3V | 3.3V |

### NeoPixel LED Ring

| LED Pin | Raspberry Pi Pin |
|---------|-----------------|
| DIN | GPIO 18 (PWM0) |
| VCC | 5V |
| GND | Ground |

## Software Installation

### 1. Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    libportaudio2 \
    libsndfile1 \
    alsa-utils \
    mpg123 \
    portaudio19-dev
```

### 2. Enable Interfaces

```bash
sudo raspi-config
# Interface Options → SPI → Enable
# Reboot when prompted
```

### 3. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama
ollama pull gemma3:1b
```

### 4. Clone and Install Project

```bash
cd ~
git clone https://github.com/your-username/once-upon-a-time.git
cd once-upon-a-time

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure for Production

```bash
cp .env.example .env
nano .env
```

Set these values:

```bash
FLASK_ENV=production
FLASK_DEBUG=False
MOCK_HARDWARE=False
TTS_PROVIDER=edge
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:1b
```

### 6. Test Installation

```bash
source venv/bin/activate
python -m raspi_storyteller.app
```

Access http://YOUR_PI_IP:5000 from another device.

## Systemd Service Setup

### Create Service File

```bash
sudo nano /etc/systemd/system/storyteller.service
```

```ini
[Unit]
Description=AI Storyteller Service
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/once-upon-a-time
Environment="PATH=/home/pi/once-upon-a-time/venv/bin"
Environment="FLASK_ENV=production"
ExecStart=/home/pi/once-upon-a-time/venv/bin/python -m raspi_storyteller.app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable storyteller.service
sudo systemctl start storyteller.service
```

### Check Status

```bash
sudo systemctl status storyteller.service
sudo journalctl -u storyteller.service -f
```

## HAT Microphone Setup (Optional)

For ReSpeaker 2-Mic HAT:

```bash
git clone https://github.com/HinTak/seeed-voicecard
cd seeed-voicecard
uname_r=$(uname -r)
version=$(echo "$uname_r" | sed 's/\([0-9]*\.[0-9]*\).*/\1/')
git checkout v$version
sudo ./install.sh
sudo reboot
```

Test microphone:

```bash
arecord -l
aplay /usr/share/sounds/alsa/Front_Center.wav
```

## Monitoring

### Health Check Script

```bash
cat > ~/storyteller_health.sh << 'EOF'
#!/bin/bash
echo "=== Storyteller Health Check ==="
systemctl status storyteller.service --no-pager | head -5
echo "Memory: $(free -h | grep Mem)"
echo "Disk: $(df -h /home/pi | tail -1)"
curl -s http://localhost:5000/api/status | head -50
EOF
chmod +x ~/storyteller_health.sh
```

### Auto Health Check (Cron)

```bash
crontab -e
# Add:
*/30 * * * * /home/pi/storyteller_health.sh >> /home/pi/health.log 2>&1
```

## Troubleshooting

### RFID Not Detected

```bash
# Check SPI is enabled
ls /dev/spidev*
# Should show: /dev/spidev0.0, /dev/spidev0.1

# If not, enable SPI
sudo raspi-config
# Interface Options → SPI → Enable
```

### No Audio Output

```bash
# List audio devices
aplay -l

# Test speaker
aplay /usr/share/sounds/alsa/Front_Center.wav

# Adjust volume
amixer set PCM 100%
```

### LED Not Working

```bash
# Must run as root for GPIO access
sudo python -m raspi_storyteller.app

# Or add user to gpio group
sudo usermod -a -G gpio $USER
```

### Service Won't Start

```bash
# Check logs
sudo journalctl -u storyteller.service -n 100

# Test manually
cd /home/pi/once-upon-a-time
source venv/bin/activate
python -m raspi_storyteller.app
```

## Backup and Restore

### Backup Cards Database

```bash
cp ~/once-upon-a-time/cards_db.json ~/cards_db_backup.json
```

### Restore

```bash
cp ~/cards_db_backup.json ~/once-upon-a-time/cards_db.json
sudo systemctl restart storyteller.service
```

## Updates

```bash
cd ~/once-upon-a-time
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart storyteller.service
```
