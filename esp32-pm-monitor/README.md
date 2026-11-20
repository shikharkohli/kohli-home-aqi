# Kohli Home AQI

Real-time air quality monitor using an **ESP32** and **PMS5003 / PMS7003** sensor.
The ESP32 posts readings over HTTP to a **Vercel** backend backed by **Neon (PostgreSQL)**.
Data is displayed on a dashboard at **<https://kohli-home-aqi.vercel.app>**.

## Before you start

You need an ESP32 development board, a PMS5003 or PMS7003 sensor, jumper wires,
a USB data cable, and a 2.4 GHz Wi-Fi network. The USB cable matters: many cheap
cables provide power but cannot upload firmware or show serial logs.

This guide assumes no prior microcontroller experience. You will first connect
the four required wires, upload firmware through PlatformIO, then confirm a
reading in the serial monitor before leaving the device on wall power.

---

## What it measures

| Value | Description |
|---|---|
| PM1.0 std / atm | 1.0 µm particles — standard & atmospheric (µg/m³) |
| PM2.5 std / atm | 2.5 µm particles — standard & atmospheric (µg/m³) |
| PM10 std / atm  | 10 µm particles — standard & atmospheric (µg/m³) |
| >0.3 µm count   | Particle count per 0.1 L of air |
| >0.5 / 1.0 / 2.5 / 5.0 / 10 µm | Same, for each size threshold |

---

## Architecture

```
PMS5003/7003 ──UART──▶ ESP32 ──HTTP POST──▶ Vercel (FastAPI + pg8000)
                                                      │
                                               Neon PostgreSQL
                                                      │
                                          kohli-home-aqi.vercel.app
                                             ↑ browse from anywhere
```

The ESP32:
- POSTs a sensor reading to `POST /api/data` every N seconds (default 5 min)
- Receives updated config (`interval_sec`, `deep_sleep_enabled`) in the same response
- GETs `GET /api/config` on first boot to sync config before the first sample

---

## Setup — Step by step

### Step 1 — Wire the hardware

| PMS5003 / PMS7003 pin | ESP32 pin | Notes |
|---|---|---|
| VCC | 5 V | |
| GND | GND | |
| TX  | GPIO 16 | `PMS_RX_PIN` in config.h |
| RX  | GPIO 17 | `PMS_TX_PIN` in config.h |
| SET | **GPIO 25** | `PMS_SET_PIN` — controls deep sleep standby |
| RST | 3.3 V | keep HIGH |

Important: cross the data wires—sensor **TX goes to ESP32 GPIO 16 (RX)** and
sensor **RX goes to ESP32 GPIO 17 (TX)**. Always connect ground between the two
boards. Start with only VCC, GND, TX, and RX; add SET only when you want to use
deep sleep.

> **Deep sleep wiring:** `SET` must be wired to **GPIO 25** (not 3.3 V) to enable deep sleep mode.
> When deep sleep is off, the pin is held HIGH continuously (same as tying to 3.3 V).
> Toggling deep sleep from the dashboard requires this rewire — without it the sensor
> fan and laser run 24/7 regardless of firmware settings.

---

### Step 2 — Deploy the backend (Vercel + Neon)

1. Create a free account at <https://vercel.com> and import this repo.
2. Set the **Root Directory** to `esp32-pm-monitor` in the Vercel project settings.
3. Add a **Neon Postgres** integration (Storage tab → Connect) — Vercel sets `POSTGRES_URL` automatically.
4. Add these **Environment Variables** in the Vercel dashboard:

   | Key | Value |
   |---|---|
   | `API_KEY` | random string — `openssl rand -hex 16` |
   | `DASH_USER` | `admin` (or your choice) |
   | `DASH_PASS` | strong password |
   | `MAX_RECORDS` | `10000` |

5. Deploy. Your URL: `https://<project>.vercel.app`

> Tables are created automatically on first request. No manual DB setup needed.

---

### Step 3 — Install PlatformIO and prepare the ESP32

#### Using PlatformIO (recommended)

1. Install [VS Code](https://code.visualstudio.com) + the
   [PlatformIO extension](https://platformio.org/install/ide?install=vscode).
2. Download or clone this repository, then open the **`esp32-pm-monitor/esp32/`**
   folder in VS Code. PlatformIO should show an alien-head icon in the left sidebar.
3. In `src/`, copy `config.h.example` and rename the copy to `config.h` (if a
   `config.h` file already exists, edit that file instead). Do not edit the
   example file; `config.h` is your private device configuration.
4. Open `config.h` and fill in your Wi-Fi name, Wi-Fi password, deployed dashboard
   URL, and API key:
   ```c
   #define WIFI_SSID     "YourWiFiName"
   #define WIFI_PASSWORD "YourWiFiPassword"
   #define SERVER_URL    "https://your-project.vercel.app"  // no trailing slash
   #define API_KEY       "the-api-key-from-step-2"
   #define SENSOR_MODEL  5003   // or 7003
   ```
5. Set `SENSOR_MODEL` to `5003` or `7003` to match your sensor. Leave the pin
   numbers unchanged unless you wired different GPIOs.
6. Connect the ESP32 with a **data** USB cable. In PlatformIO, click **Upload**
   (the right-arrow button in the bottom toolbar). The first build can take a few
   minutes while PlatformIO downloads board tools.

If Upload cannot find a board, unplug and reconnect the cable, close any Serial
Monitor window, then try again. Some ESP32 boards require holding the **BOOT**
button while the upload begins and releasing it once `Connecting...` appears.

### Step 4 — Confirm the sensor before mounting it

1. In PlatformIO, open **Serial Monitor**, or run this from the `esp32/` folder:

   ```bash
   pio device monitor --baud 115200
   ```

2. Press the ESP32 **EN** or **RST** button once. Within about 30 seconds you
   should see `[Boot]`, `[PMS] Warming up`, a Wi-Fi connection message, and an
   `[HTTP] POST /api/data → 200` line.
3. Open your dashboard. A reading should appear within 15–30 seconds after the
   successful POST.

If the monitor shows unreadable characters, close it and reopen it at **115200**
baud. The PMS sensor itself uses 9600 baud internally; do not attach the computer
to the sensor TX/RX pins to debug the project.

#### Alternative: Arduino IDE

1. Install [Arduino IDE 2](https://www.arduino.cc/en/software).
2. Add ESP32 board support:
   - File → Preferences → Additional boards URLs:
     `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Tools → Board → Boards Manager → search "esp32" → Install.
3. Install library: Sketch → Include Library → Manage → search **ArduinoJson** → Install.
4. Open `esp32/src/pm_monitor.ino` and create `src/config.h` as above.
5. Select board: **ESP32 Dev Module** | Upload speed: **921600**.
6. Upload.

---

### Step 5 — Leave it running

Open in any browser (desktop or mobile):

```
https://your-project.vercel.app
```

Interval and deep sleep settings require `DASH_USER` / `DASH_PASS`.  
The dashboard auto-refreshes every 15 seconds.

The firmware automatically attempts Wi-Fi recovery if the router restarts: it
tries the existing connection first, then re-joins the configured network up to
three times before waiting for the next sample cycle. Keep the ESP32 on reliable
5 V power; a wall adapter is fine once setup is verified.

---

## Common first-time problems

| Symptom | Check this first |
|---|---|
| Upload fails or no serial port appears | Use a USB **data** cable, unplug/replug the board, close Serial Monitor, and hold BOOT during upload if needed. |
| `[PMS] Frame timeout` | Check 5 V, common GND, and crossed TX/RX wires. Confirm the sensor is a PMS5003 or PMS7003. |
| `[WiFi] Reconnect failed` | Confirm the network is 2.4 GHz, credentials are correct, and the router is online. |
| `[HTTP] POST ... → 401` | `API_KEY` in `config.h` does not match Vercel. |
| `[HTTP] POST ... → 404` or no dashboard data | Check `SERVER_URL`, including `https://` and no trailing `/`; confirm Vercel Root Directory is `esp32-pm-monitor`. |
| Garbled Serial Monitor text | Reopen at 115200 baud: `pio device monitor --baud 115200`. |

---

## Dashboard features

- **Light / dark theme** — Apple HIG design system, follows system preference (toggle in header)
- **AQI cards** — US EPA and India CPCB AQI calculated from PM2.5 + PM10
- **PM cards** — PM1.0 / PM2.5 / PM10 with healthy / unhealthy tags
- **PM and particle-count charts** — time-range selector (1 h → All)
- **Sampling interval selector** — 30 s / 1 min / 15 min / 30 min (requires auth)
- **Deep sleep toggle** — put ESP32 into deep sleep between readings to extend sensor laser life  
  Requires `SET` pin rewired to GPIO 25 (see wiring above). Disables intervals < 2 min.

---

## API reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/data` | `X-API-Key` header | ESP32 posts a reading; response includes current config |
| GET | `/api/data?hours=24&limit=500` | none | Retrieve historical readings |
| GET | `/api/config` | none | Get config `{"interval_sec": N, "deep_sleep_enabled": bool}` |
| PUT | `/api/config` | Basic Auth | Update interval and/or deep sleep `{"interval_sec": 300, "deep_sleep_enabled": true}` |
| GET | `/api/health` | none | Health check |
| GET | `/` | none | Dashboard |

---

## Local development

```bash
cd esp32-pm-monitor
python -m venv .venv && source .venv/bin/activate
pip install fastapi pg8000 uvicorn

export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"
export API_KEY=dev DASH_USER=admin DASH_PASS=dev
python app.py
# → http://localhost:8000
```

Test a fake reading:
```bash
curl -X POST http://localhost:8000/api/data \
  -H "X-API-Key: dev" \
  -H "Content-Type: application/json" \
  -d '{"pm1_0_std":5,"pm2_5_std":12,"pm10_std":18,
       "pm1_0_atm":4,"pm2_5_atm":11,"pm10_atm":17,
       "cnt_0_3um":1200,"cnt_0_5um":350,"cnt_1_0um":80,
       "cnt_2_5um":20,"cnt_5_0um":4}'
```

---

## Security notes

- The dashboard requires HTTP Basic Auth.  Credentials travel over HTTPS.
- The ESP32 authenticates with a per-deployment `API_KEY` header.
- `config.h.example` is a safe template; your actual `config.h` contains your
  Wi-Fi and API credentials. Never share it or add it to a public repository.
