import os
import sys
from datetime import datetime
import math
import signal
import logging

import requests
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QSpacerItem,
    QSizePolicy,
)
from dotenv import load_dotenv

load_dotenv()

# --- Logging ---
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train_app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a"),
    ],
)
logger = logging.getLogger(__name__)

# --- App config ---
CTA_API_KEY = os.environ.get("CTA_API_KEY")
STATION_ID = "40530"
STATION_NAME = "Diversey"
SELECTED_ROUTES = ["Brn"]
MAX_TRAINS = 6

# --- Timing (ms) ---
REFRESH_INTERVAL = 300_000
CLOCK_INTERVAL = 60_000
SIGNAL_TIMER_INTERVAL = 500

# --- API ---
API_URL = "https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx"
API_TIMEOUT = 10

# --- Colors ---
BG_COLOR = "#1E1E1E"
HEADER_BG_COLOR = "#4F4F4F"
ROUTE_STATUS_BG_COLOR = "#3F3F3F"

ROUTE_COLORS = {
    "Brn": "#63361c",
    "Red": "#ff0000",
    "Blu": "#0000ff",
    "Grn": "#008000",
    "Org": "#ffa500",
    "Pur": "#800080",
}

ROUTE_MAPPING = {
    "Brn": "Brown",
    "Red": "Red",
    "Blu": "Blue",
    "Grn": "Green",
    "Org": "Orange",
    "Pur": "Purple",
}

# --- Paths ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

# --- Scaling ---
_scale = 1.0  # Set in __main__ before any widgets are created


def s(value):
    """Scale a pixel value based on screen height (baseline: 1080p)."""
    return int(value * _scale)


def sf(value):
    """Scale a font size based on screen height (baseline: 1080p)."""
    return max(8, int(value * _scale))


def create_train_header():
    header = QLabel(f"Next trains at {STATION_NAME}")
    header.setFont(QFont("Arial", sf(24), QFont.Bold))
    header.setStyleSheet(f"color: white; background-color: {HEADER_BG_COLOR};")
    header.setContentsMargins(s(20), s(12), s(20), s(12))
    header.setFixedHeight(s(65))
    return header


def create_train_widget(train):
    train_widget = QWidget()
    train_layout = QHBoxLayout(train_widget)
    train_widget.setContentsMargins(s(25), s(12), s(25), s(12))
    train_widget.setFixedHeight(s(130))

    line_code = train["rt"]
    line_name = ROUTE_MAPPING.get(line_code, "Unknown Line")

    train_number = train["rn"]
    destination = train["destNm"]
    arr_time_str = train["arrT"]
    arr_time = datetime.strptime(arr_time_str, "%Y-%m-%dT%H:%M:%S")
    now = datetime.now()
    eta_minutes = math.ceil((arr_time - now).total_seconds() / 60)

    left_section = QVBoxLayout()
    left_section.setContentsMargins(0, 0, 0, 0)
    title_top = QLabel(f"{line_name} Line #{train_number} to")
    title_top.setFont(QFont("Arial", sf(22)))
    title_top.setStyleSheet("color: white;")
    title_top.setContentsMargins(0, 0, 0, -8)

    title_bottom = QLabel(destination)
    title_bottom.setFont(QFont("Arial", sf(44), QFont.Bold))
    title_bottom.setStyleSheet("color: white;")
    left_section.addWidget(title_top)
    left_section.addWidget(title_bottom)

    eta_text = "Due" if eta_minutes <= 1 else f"{eta_minutes} min"
    eta = QLabel(eta_text)
    eta.setFont(QFont("Arial", sf(44)))
    eta.setStyleSheet("color: white;")

    train_layout.addLayout(left_section)
    train_layout.addStretch()
    train_layout.addWidget(eta, alignment=Qt.AlignRight)
    train_layout.setContentsMargins(0, 0, 0, 0)

    line_color = ROUTE_COLORS.get(line_code, BG_COLOR)
    train_widget.setStyleSheet(f"background-color: {line_color}; border-radius: 0px;")

    return train_widget


class TrainApp(QWidget):
    def __init__(self):
        super().__init__()
        self._error_label = None
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(s(40), s(25), s(40), s(25))

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        logger.debug(f"Project directory: {project_root}")

        icon_sz = s(55)
        image = QPixmap(os.path.join(project_root, "res/info_icon.png"))
        image = image.scaled(icon_sz, icon_sz, mode=Qt.SmoothTransformation)
        header_image = QLabel()
        header_image.setPixmap(image)
        header_image.setFixedSize(icon_sz, icon_sz)

        header = QLabel("Estimated arrival information")
        header.setFont(QFont("Arial", sf(38), QFont.Bold))
        header.setStyleSheet("color: white;")

        self.current_time_label = QLabel("")
        self.current_time_label.setFont(QFont("Arial", sf(34), QFont.Bold))
        self.current_time_label.setStyleSheet("color: white;")

        header_layout.addWidget(header_image)
        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(self.current_time_label)

        self.main_layout.addWidget(header_widget)
        self.main_layout.addSpacerItem(
            QSpacerItem(20, s(20), QSizePolicy.Minimum, QSizePolicy.Fixed)
        )

        # --- Left column: train tracker ---
        train_header_widget = QWidget()
        train_header_layout = QHBoxLayout(train_header_widget)
        train_header_layout.setContentsMargins(0, 0, 0, 0)
        sec_icon_sz = s(45)
        train_icon = QPixmap(os.path.join(project_root, "res/train_icon.png"))
        train_icon = train_icon.scaled(sec_icon_sz, sec_icon_sz, mode=Qt.SmoothTransformation)
        train_icon_label = QLabel()
        train_icon_label.setPixmap(train_icon)
        train_icon_label.setFixedSize(sec_icon_sz, sec_icon_sz)

        train_label = QLabel("cta train tracker")
        train_label.setFont(QFont("Arial", sf(24), QFont.Bold))
        train_label.setStyleSheet("color: white;")

        train_header_layout.addWidget(train_icon_label)
        train_header_layout.addWidget(train_label)

        left_column_layout = QVBoxLayout()
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.addWidget(train_header_widget)

        self.train_arrival = QWidget()
        self.train_arrival.setContentsMargins(0, 0, 0, 0)
        self.train_arrival_layout = QVBoxLayout(self.train_arrival)
        self.train_arrival_layout.setSpacing(s(8))

        train_header = create_train_header()
        self.train_arrival_layout.addWidget(train_header)

        self.train_arrival_layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        self.train_arrival_layout.setContentsMargins(0, 0, 0, 0)

        left_column_layout.addWidget(self.train_arrival)

        # --- Right column: route status ---
        right_column_layout = QVBoxLayout()
        right_column_layout.setContentsMargins(0, 0, 0, 0)

        route_header_widget = QWidget()
        route_header_layout = QHBoxLayout(route_header_widget)
        route_header_layout.setContentsMargins(0, 0, 0, 0)
        route_icon = QPixmap(os.path.join(project_root, "res/route_icon.png"))
        route_icon_sz = s(45)
        route_icon = route_icon.scaled(route_icon_sz, route_icon_sz, mode=Qt.SmoothTransformation)
        route_icon_label = QLabel()
        route_icon_label.setPixmap(route_icon)
        route_icon_label.setFixedSize(route_icon_sz, route_icon_sz)

        l_route_status_label = QLabel("'L' route status")
        l_route_status_label.setFont(QFont("Arial", sf(24), QFont.Bold))
        l_route_status_label.setStyleSheet("color: white;")

        route_header_layout.addWidget(route_icon_label)
        route_header_layout.addWidget(l_route_status_label)

        right_column_layout.addWidget(route_header_widget)

        route_status_widget = QWidget()
        route_status_layout = QVBoxLayout(route_status_widget)
        route_status_layout.setSpacing(s(12))
        route_status_layout.setContentsMargins(s(16), s(16), s(16), s(16))

        route_lines = [
            ("Brown Line", "#63361c", "#4CAF50", "Normal Service"),
            ("Yellow Line", "#f9e300", "#4CAF50", "Normal Service"),
            ("Blue Line", "#00a1de", "#f44336", "Not in Service"),
        ]

        for line_name, line_color, dot_color, status_text in route_lines:
            row = QHBoxLayout()
            row.setSpacing(s(12))

            label = QLabel(line_name)
            label.setFont(QFont("Arial", sf(24), QFont.Bold))
            text_color = "black" if line_color == "#f9e300" else "white"
            label.setStyleSheet(
                f"color: {text_color}; background-color: {line_color}; "
                f"padding: {s(12)}px {s(18)}px; border-radius: {s(4)}px;"
            )
            label.setFixedWidth(s(220))

            dot = QLabel("\u25CF")
            dot.setFont(QFont("Arial", sf(24)))
            dot.setStyleSheet(f"color: {dot_color}; background-color: transparent;")
            dot.setFixedWidth(s(32))

            status = QLabel(status_text)
            status.setFont(QFont("Arial", sf(20), QFont.Bold))
            status.setStyleSheet("color: white; background-color: transparent;")

            row.addWidget(label)
            row.addWidget(dot)
            row.addWidget(status)
            row.addStretch()

            route_status_layout.addLayout(row)

        route_status_widget.setStyleSheet(
            f"background-color: {ROUTE_STATUS_BG_COLOR}; border-radius: {s(4)}px;"
        )

        right_column_layout.addWidget(route_status_widget)
        right_column_layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        # --- Two-column layout ---
        column_layout = QHBoxLayout()
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.addLayout(left_column_layout)
        column_layout.addLayout(right_column_layout)
        column_layout.setStretch(0, 3)
        column_layout.setStretch(1, 2)
        column_layout.setSpacing(s(30))

        self.main_layout.addLayout(column_layout)

        # --- Timers ---
        self.update_train_data()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_train_data)
        self.timer.start(REFRESH_INTERVAL)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(CLOCK_INTERVAL)
        self.clock_timer.setSingleShot(True)

        self.update_clock()

        self.setStyleSheet(f"background-color: {BG_COLOR};")

    def update_train_data(self):
        try:
            logger.debug("Fetching train data from API...")
            if CTA_API_KEY is None:
                raise ValueError("CTA_API_KEY is not set")
            full_url = (
                f"{API_URL}?mapid={STATION_ID}&key={CTA_API_KEY}&outputType=JSON"
            )
            response = requests.get(full_url, timeout=API_TIMEOUT)
            response.raise_for_status()
            train_data = response.json().get("ctatt", {}).get("eta", [])
            train_data = list(
                filter(lambda x: x["rt"] in SELECTED_ROUTES, train_data)
            )[:MAX_TRAINS]
            self.refresh_train_list(train_data)
            self.clear_error()
            logger.info(f"Successfully fetched {len(train_data)} train entries.")
        except Exception as e:
            logger.error(f"Error fetching train data: {e}")
            self.show_error(str(e))

    def refresh_train_list(self, train_data):
        for i in reversed(range(1, self.train_arrival_layout.count() - 1)):
            widget = self.train_arrival_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for train in train_data:
            train_widget = create_train_widget(train)
            self.train_arrival_layout.insertWidget(
                self.train_arrival_layout.count() - 1, train_widget
            )

    def show_error(self, message):
        self.clear_error()
        self._error_label = QLabel(f"Error: {message}")
        self._error_label.setFont(QFont("Arial", sf(18)))
        self._error_label.setStyleSheet(
            f"color: #ff6b6b; background-color: {HEADER_BG_COLOR}; padding: {s(12)}px;"
        )
        self._error_label.setObjectName("error_label")
        self.train_arrival_layout.insertWidget(
            self.train_arrival_layout.count() - 1, self._error_label
        )

    def clear_error(self):
        if self._error_label is not None:
            self._error_label.deleteLater()
            self._error_label = None

    def update_clock(self):
        now = datetime.now()
        current_time = now.strftime("%I:%M%p").lower()
        if current_time.startswith("0"):
            current_time = current_time[1:]
        self.current_time_label.setText(current_time)
        logger.debug(f"Clock updated: {current_time}")
        self.clock_timer.start(CLOCK_INTERVAL)


def sigint_handler(*args):
    """Handles Ctrl+C (SIGINT) to exit the application cleanly."""
    logger.info("Ctrl+C detected. Exiting application...")
    QApplication.quit()


if __name__ == "__main__":
    logger.info("Starting TrainApp...")
    signal.signal(signal.SIGINT, sigint_handler)

    app = QApplication(sys.argv)
    app.setOverrideCursor(Qt.BlankCursor)

    # Set resolution scale factor (baseline: 1080p)
    screen_height = app.primaryScreen().size().height()
    _scale = screen_height / 1080
    logger.info(f"Screen height: {screen_height}, scale factor: {_scale}")

    # Periodically allow Python to process signals
    timer = QTimer()
    timer.start(SIGNAL_TIMER_INTERVAL)
    timer.timeout.connect(lambda: None)

    # Initialize and start application
    window = TrainApp()
    window.setWindowTitle("Forever Brown")
    window.setWindowFlags(Qt.FramelessWindowHint)

    # Fill the screen (more reliable than showFullScreen alone on Pi)
    screen = app.primaryScreen().geometry()
    window.setGeometry(screen)
    window.showFullScreen()

    logger.info("TrainApp started successfully.")
    sys.exit(app.exec())
