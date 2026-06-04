# Bandil's Polling Rate Detector

A real-time mouse polling rate detector for Windows with a modern 1920x1080 HUD.

## Features
- Detects polling rates up to **8000 Hz** accurately
- Beautiful two-column layout: circular speedometer gauge + large detection zone
- Smooth animated arc that lerps to your real polling rate
- Color-coded tiers: 125 / 250 / 500 / 1000 / 2000 / 4000 / 8000 Hz
- Mouse trail, animated border, pulsing cursor rings
- Uses a Windows low-level hook (`SetWindowsHookExW`) for accurate high-Hz detection

## Download
Grab the latest `.exe` from this repo — no install needed, just run it.

## Usage
1. Launch `Bandil's Polling Rate Detector.exe`
2. Move your mouse anywhere in the **Detection Zone** (right panel)
3. Your polling rate appears live on the gauge

## Build from source
```
pip install pyinstaller pillow
pyinstaller --onefile --windowed --name "BandilsPollingRateDetector" mouse_polling_rate.py
```

Requires Python 3.10+ and Windows.
