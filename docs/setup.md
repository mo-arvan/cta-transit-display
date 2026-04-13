# Setup

Set these variables before following this guide:

```bash
export PI_USER="ar"                              # Your Pi username
export PI_HOST="raspberrypi.local"               # Your Pi hostname or IP
export PROJECT_DIR="/home/$PI_USER/cta-transit-display"  # Install path on the Pi
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A [CTA Train Tracker API key](https://www.transitchicago.com/developers/traintracker/) (approval is usually instant)

## Installation

```bash
git clone <repo-url>
cd cta-transit-display
uv sync
```

## Configuration

Create a `.env` file in the project root:

```
CTA_API_KEY=your_api_key_here
```

### Changing the Station

Edit `STATION_ID` in `src/main.py`. Station IDs can be found in the [CTA GTFS data](https://www.transitchicago.com/developers/gtfs/). Default is `40530` (Diversey).

### Changing Tracked Lines

Edit `SELECTED_ROUTES` in `src/main.py`. Available route codes:

| Code  | Line   |
|-------|--------|
| `Brn` | Brown  |
| `Red` | Red    |
| `Blu` | Blue   |
| `Grn` | Green  |
| `Org` | Orange |
| `Pur` | Purple |

Default is `["Brn"]` (Brown Line only).

## Running Locally

```bash
uv run src/main.py
```

## Deploying to Raspberry Pi

Install uv on the Pi:

```bash
ssh $PI_USER@$PI_HOST
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Deploy with the script (copies code, config, and assets to the Pi):

```bash
PI_HOST="$PI_USER@$PI_HOST" ./scripts/deploy.sh
```

## Auto-Start

The Pi boots normally into labwc. To have the app launch automatically, add it to the labwc autostart using lwrespawn (a process supervisor that restarts the app if it crashes):

```bash
nano $HOME/.config/labwc/autostart
```

Add:

```
/usr/bin/lwrespawn $PROJECT_DIR/scripts/start_app.sh
```

## Troubleshooting

App logs:

```bash
cat $PROJECT_DIR/train_app.log
```
