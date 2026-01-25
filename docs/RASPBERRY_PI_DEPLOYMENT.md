# Raspberry Pi Deployment Guide

## Hardware Requirements

- Raspberry Pi 5 (16GB RAM recommended)
- MicroSD card (32GB+)
- RC522 RFID reader module
- NeoPixel/WS2812 LED ring (12 LEDs)
- Speaker (3.5mm jack or USB)
- (Optional) MCP3008 ADC + 10K potentiometer for story length control
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

### MCP3008 ADC (for Story Length Potentiometer)

The story length slider uses an MCP3008 ADC to read a potentiometer value.

**MCP3008 Wiring:**

| MCP3008 Pin | Raspberry Pi Pin |
|-------------|-----------------|
| VDD (16) | 3.3V |
| VREF (15) | 3.3V |
| AGND (14) | Ground |
| CLK (13) | GPIO 11 (SCLK) |
| DOUT (12) | GPIO 9 (MISO) |
| DIN (11) | GPIO 10 (MOSI) |
| CS/SHDN (10) | GPIO 7 (CE1) |
| DGND (9) | Ground |

**Note:** The MCP3008 uses CE1 (GPIO 7) to avoid conflict with the RC522 RFID reader which uses CE0 (GPIO 8).

**Potentiometer (10K ohm) Wiring:**

| Potentiometer Pin | Connection |
|-------------------|------------|
| Left terminal | Ground |
| Center (wiper) | MCP3008 CH0 (pin 1) |
| Right terminal | 3.3V |

This allows the potentiometer to control story duration from 1-15 minutes.

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
pip install .
```

For development with additional tools:
```bash
pip install -e ".[dev,raspberry-pi]"
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
raspi-storyteller
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
ExecStart=/home/pi/once-upon-a-time/venv/bin/raspi-storyteller
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
sudo /home/pi/once-upon-a-time/venv/bin/raspi-storyteller

# Or add user to gpio group
sudo usermod -a -G gpio $USER
```

### Potentiometer/Slider Not Working

```bash
# Check SPI is enabled
ls /dev/spidev*
# Should show: /dev/spidev0.0, /dev/spidev0.1

# Test MCP3008 connection with Python
python3 << 'EOF'
import spidev

spi = spidev.SpiDev()
spi.open(0, 1)  # CE1
spi.max_speed_hz = 1350000

def read_adc(channel):
    cmd = [1, (8 + channel) << 4, 0]
    response = spi.xfer2(cmd)
    value = ((response[1] & 3) << 8) + response[2]
    return value

# Read channel 0 (potentiometer)
for i in range(5):
    val = read_adc(0)
    print(f"ADC Value: {val} ({val/1023*100:.1f}%)")
    import time; time.sleep(0.5)

spi.close()
EOF

# If values change when turning potentiometer, wiring is correct
```

If the slider isn't responding:
1. Check all MCP3008 wiring connections
2. Ensure SPI is enabled in `raspi-config`
3. Verify the potentiometer center pin is connected to CH0
4. Check that you're using CE1 (GPIO 7), not CE0 (used by RFID)

### Service Won't Start

```bash
# Check logs
sudo journalctl -u storyteller.service -n 100

# Test manually
cd /home/pi/once-upon-a-time
source venv/bin/activate
raspi-storyteller
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
pip install --upgrade .
sudo systemctl restart storyteller.service
```
