import sys
import os
import csv
import sqlite3
import requests
import cv2

# Machine Learning
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestRegressor, RandomForestClassifier

# Charts
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPixmap, QColor, QPainter, QPen, QBrush, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QGridLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QProgressBar,
    QTextEdit, QDialog, QScrollArea, QMenu, QSizePolicy
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, "ecomind.db")
IMAGE_FOLDER = os.path.join(BASE_DIR, "waste_images")

APP_NAME = "EcoMind AI"

CATEGORIES = [
    "Food",
    "Plastic",
    "Paper",
    "Glass",
    "Metal",
    "E-waste"
]


# ============================================================
# DATABASE
# ============================================================

class Database:                                #type:ignore
    def __init__(self):
        self.connection = sqlite3.connect(DB_NAME)
        self.create_tables()

    def create_tables(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS waste_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_date TEXT NOT NULL,
                category TEXT NOT NULL,
                weight REAL NOT NULL,
                recycled INTEGER NOT NULL,
                description TEXT,
                image_path TEXT,
                ai_category TEXT,
                ai_confidence REAL
            )
        """)

        # Check existing columns
        cursor.execute("PRAGMA table_info(waste_records)")
        columns = {row[1] for row in cursor.fetchall()}

        # Add columns missing from older databases
        missing_columns = {
            "description": "TEXT",
            "image_path": "TEXT",
            "ai_category": "TEXT",
            "ai_confidence": "REAL"
        }

        for column, data_type in missing_columns.items():
            if column not in columns:
                cursor.execute(
                    f"ALTER TABLE waste_records ADD COLUMN {column} {data_type}"
                )

        self.connection.commit()

    def add_record(
        self,
        record_date,
        category,
        weight,
        recycled,
        description="",
        image_path="",
        ai_category="",
        ai_confidence=0
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            INSERT INTO waste_records
            (
                record_date,
                category,
                weight,
                recycled,
                description,
                image_path,
                ai_category,
                ai_confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record_date,
            category,
            weight,
            int(recycled),          
            description,
            image_path,
            ai_category,
            ai_confidence
        ))

        self.connection.commit()

    def get_records(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                id,
                record_date,
                category,
                weight,
                recycled,
                description,
                image_path,
                ai_category,
                ai_confidence
            FROM waste_records
            ORDER BY record_date DESC, id DESC
        """)

        return cursor.fetchall()

    def delete_record(self, record_id):
        cursor = self.connection.cursor()

        cursor.execute(
            "DELETE FROM waste_records WHERE id = ?",
            (record_id,)
        )

        self.connection.commit()

    def clear_all(self):
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM waste_records")
        self.connection.commit()

    def close(self):
        self.connection.close()

# ============================================================
# ANALYTICS
# ============================================================

class Analytics:

    def __init__(self, database):
        self.database = database

    def records(self):
        return self.database.get_records()

    def total_waste(self):
        return sum(row[3] for row in self.records())

    def recycled_waste(self):
        return sum(row[3] for row in self.records() if row[4] == 1)

    def recycling_rate(self):

        total = self.total_waste()

        if total == 0:
            return 0

        return (self.recycled_waste() / total) * 100

    def category_breakdown(self):

        result = {}

        for row in self.records():

            category = row[2]
            weight = row[3]

            result[category] = result.get(category, 0) + weight

        return result

    def highest_category(self):

        data = self.category_breakdown()

        if not data:
            return "No data"

        return max(data, key=data.get)    #type:ignore

    def sustainability_score(self):

        rate = self.recycling_rate()

        # Current foundation score.
        # Later this will combine ML-derived factors.
        score = min(100, rate)

        return score


# ============================================================
# MACHINE LEARNING ENGINE
# ============================================================

class EcoMindMLEngine:
    """Local ML engine trained from the user's own EcoMind records.

    Models:
    1. Isolation Forest for unusual daily waste/anomaly detection.
    2. Random Forest regression for next-day total-waste prediction.
    3. Random Forest image classifier trained from saved, manually
       labeled waste images when enough examples exist.

    The engine never invents a confidence score when there is not
    enough real data to train a model.
    """

    def __init__(self, database):
        self.database = database
        self.anomaly_model = None
        self.prediction_model = None
        self.vision_model = None
        self.vision_classes = []

    def _daily_data(self):
        daily = {}
        for row in self.database.get_records():
            date = str(row[1])
            category = str(row[2])
            weight = float(row[3] or 0)
            recycled = int(row[4] or 0)
            if date not in daily:
                daily[date] = {"total": 0.0, "recycled": 0.0, "categories": {}}
            daily[date]["total"] += weight
            daily[date]["recycled"] += weight if recycled else 0.0
            daily[date]["categories"][category] = daily[date]["categories"].get(category, 0.0) + weight
        return [(d, daily[d]) for d in sorted(daily)]

    def anomaly_detection(self):
        days = self._daily_data()
        if len(days) < 5:
            return {
                "status": "LEARNING",
                "is_anomaly": False,
                "strength": 0.0,
                "message": "Need at least 5 different days of data for anomaly detection."
            }

        X = []
        for _, item in days:
            total = item["total"]
            recycle_rate = (item["recycled"] / total * 100) if total else 0
            X.append([total, recycle_rate] + [item["categories"].get(c, 0.0) for c in CATEGORIES])

        self.anomaly_model = IsolationForest(
            n_estimators=150,
            contamination="auto",
            random_state=42
        )
        self.anomaly_model.fit(np.asarray(X, dtype=float))
        labels = self.anomaly_model.predict(np.asarray(X, dtype=float))
        scores = self.anomaly_model.decision_function(np.asarray(X, dtype=float))
        last_label = int(labels[-1])
        raw = float(scores[-1])
        strength = float(np.clip(50.0 - raw * 100.0, 0.0, 100.0))

        if last_label == -1:
            msg = f"Unusually high/low waste pattern detected today. Anomaly strength: {strength:.0f}/100."
        else:
            msg = f"Today's waste pattern is within the learned historical range. Normality strength: {100-strength:.0f}/100."

        return {
            "status": "ACTIVE",
            "is_anomaly": last_label == -1,
            "strength": strength,
            "message": msg
        }

    def waste_prediction(self):
        days = self._daily_data()
        if len(days) < 8:
            return {
                "status": "LEARNING",
                "prediction": None,
                "direction": "unknown",
                "message": "Need at least 8 different days of data for a meaningful next-day prediction."
            }

        totals = [item["total"] for _, item in days]
        X, y = [], []
        for i in range(3, len(totals)):
            history = totals[i-3:i]
            X.append(history + [float(np.mean(history))])
            y.append(totals[i])

        self.prediction_model = RandomForestRegressor(
            n_estimators=200,
            random_state=42,
            min_samples_leaf=1
        )
        self.prediction_model.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
        latest = totals[-3:]
        prediction = float(self.prediction_model.predict([latest + [float(np.mean(latest))]])[0])
        prediction = max(0.0, prediction)
        latest_total = totals[-1]

        if prediction > latest_total * 1.08:
            direction = "rising"
        elif prediction < latest_total * 0.92:
            direction = "falling"
        else:
            direction = "stable"

        return {
            "status": "ACTIVE",
            "prediction": prediction,
            "direction": direction,
            "message": f"ML predicts approximately {prediction:.2f} kg of total waste for the next recorded day."
        }

    @staticmethod
    def _image_features(path):
        image = cv2.imread(path)
        if image is None:
            return None
        image = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        features = []
        for channel in range(3):
            hist = cv2.calcHist([hsv], [channel], None, [16], [0, 256]).flatten()
            hist = hist / (hist.sum() + 1e-9)
            features.extend(hist.tolist())
        gray_hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).flatten()
        gray_hist = gray_hist / (gray_hist.sum() + 1e-9)
        features.extend(gray_hist.tolist())

        mean = image.mean(axis=(0, 1)) / 255.0
        std = image.std(axis=(0, 1)) / 255.0
        features.extend(mean.tolist())
        features.extend(std.tolist())
        return np.asarray(features, dtype=np.float32)

    def train_vision(self):
        X, y = [], []
        records = self.database.get_records()
        per_class = {}
        for row in records:
            image_path = row[6]
            category = row[2]
            if not image_path or not os.path.exists(image_path):
                continue
            features = self._image_features(image_path)
            if features is None:
                continue
            X.append(features)
            y.append(category)
            per_class[category] = per_class.get(category, 0) + 1

        usable_classes = [c for c, n in per_class.items() if n >= 3]
        if len(usable_classes) < 2:
            self.vision_model = None
            self.vision_classes = []
            return {
                "status": "LEARNING",
                "message": "Vision model needs at least 3 saved labeled images in each of 2 categories.",
                "classes": per_class
            }

        filtered = [(features, label) for features, label in zip(X, y) if label in usable_classes]
        X2 = np.asarray([item[0] for item in filtered], dtype=np.float32)
        y2 = np.asarray([item[1] for item in filtered])

        self.vision_model = RandomForestClassifier(
            n_estimators=250,
            random_state=42,
            class_weight="balanced"
        )
        self.vision_model.fit(X2, y2)
        self.vision_classes = list(self.vision_model.classes_)
        return {
            "status": "ACTIVE",
            "message": f"Vision classifier trained from {len(y2)} labeled images across {len(self.vision_classes)} categories.",
            "classes": per_class
        }

    def classify_image(self, image_path):
        result = self.train_vision()
        if self.vision_model is None:
            return "", 0.0, result["message"]

        features = self._image_features(image_path)
        if features is None:
            return "", 0.0, "Unable to read the image for ML classification."

        probabilities = self.vision_model.predict_proba([features])[0]
        index = int(np.argmax(probabilities))
        category = str(self.vision_model.classes_[index])
        confidence = float(probabilities[index] * 100.0)
        return category, confidence, "Trained local image classifier prediction."

    def analyze(self):
        anomaly = self.anomaly_detection()
        prediction = self.waste_prediction()
        vision = self.train_vision()
        return {
            "anomaly": anomaly,
            "prediction": prediction,
            "vision": vision,
            "active_models": sum([
                anomaly["status"] == "ACTIVE",
                prediction["status"] == "ACTIVE",
                vision["status"] == "ACTIVE"
            ])
        }

# ============================================================
# LOCATION SERVICE
# ============================================================

class LocationService:

    def __init__(self):

        self.location = None

    def get_location(self):

        if self.location:
            return self.location

        try:

            response = requests.get(
                "https://ipapi.co/json/",
                timeout=5
            )

            response.raise_for_status()

            data = response.json()

            self.location = {
                "city": data.get("city", "Unknown"),
                "region": data.get("region", ""),
                "country": data.get("country_name", ""),
                "lat": data.get("latitude"),
                "lon": data.get("longitude")
            }

            return self.location

        except Exception:

            self.location = {
                "city": "Patna",
                "region": "Bihar",
                "country": "India",
                "lat": 25.5941,
                "lon": 85.1376
            }

            return self.location


# ============================================================
# WEATHER SERVICE
# ============================================================

class WeatherService:

    def get_weather(self, lat, lon):

        try:

            url = "https://api.open-meteo.com/v1/forecast"

            params = {
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "wind_speed_10m,"
                    "weather_code"
                ),
                "timezone": "auto"
            }

            response = requests.get(
                url,
                params=params,
                timeout=8
            )

            response.raise_for_status()

            return response.json().get("current", {})

        except Exception:
            return {}


# ============================================================
# COMPUTER VISION
# ============================================================

class WasteVision:
    """
    Camera/object-detection foundation for EcoMind AI.

    Behaviour:
    - Opens the webcam and shows a live preview.
    - Gives the camera a short warm-up period.
    - Uses OpenCV foreground/background analysis to detect a
      visible object entering the scene.
    - Automatically captures the frame when an object is detected.
    - If no object is detected for 5 seconds, the camera closes
      and reports: "No waste detected."
    - SPACE can still be used as a manual capture fallback.

    Note: OpenCV detects an object; it does NOT claim to classify
    the object as Plastic/Paper/Food/etc. A trained ML classifier
    must be connected for genuine waste-category prediction.
    """

    def __init__(self):
        os.makedirs(IMAGE_FOLDER, exist_ok=True)
        self.no_detection_seconds = 5.0
        self.warmup_seconds = 1.0
        self.min_contour_area = 4500

    def _save_frame(self, frame):
        filename = (
            "waste_" +
            datetime.now().strftime("%Y%m%d_%H%M%S") +
            ".jpg"
        )
        saved_path = os.path.join(IMAGE_FOLDER, filename)
        if cv2.imwrite(saved_path, frame):
            return saved_path
        return None

    def _object_detected(self, frame, background_gray):
        """Detect a foreground object using simple OpenCV motion analysis."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        difference = cv2.absdiff(background_gray, gray)
        _, threshold = cv2.threshold(difference, 30, 255, cv2.THRESH_BINARY)
        threshold = cv2.dilate(threshold, None, iterations=2)

        contours, _ = cv2.findContours(
            threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        largest_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > largest_area:
                largest_area = area

        return largest_area >= self.min_contour_area, largest_area

    def capture_image(self):
        camera = cv2.VideoCapture(0)

        if not camera.isOpened():
            QMessageBox.warning(
                None,
                "Camera Error",
                "Could not access the camera.\n\n"
                "Check that your webcam is connected and not being used "
                "by another application."
            )
            return None

        start_time = datetime.now().timestamp()
        background_gray = None
        captured_path = None
        detected = False
        detection_streak = 0
        last_status = "Initializing camera..."

        try:
            while True:
                success, frame = camera.read()
                if not success:
                    break

                now = datetime.now().timestamp()
                elapsed = now - start_time

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                # Build a stable background during the warm-up period.
                if background_gray is None:
                    background_gray = gray.copy()
                elif elapsed < self.warmup_seconds:
                    background_gray = cv2.addWeighted(
                        background_gray, 0.85, gray, 0.15, 0
                    )

                if elapsed >= self.warmup_seconds:
                    found, area = self._object_detected(
                        frame, background_gray
                    )

                    if found:
                        detection_streak += 1
                        last_status = "Possible waste detected - checking..."
                    else:
                        detection_streak = 0
                        last_status = (
                            "Searching for waste... "
                            f"({elapsed:.1f}s / {self.no_detection_seconds:.0f}s)"
                        )

                    # Require two consecutive positive frames to reduce
                    # accidental captures caused by camera noise.

                    if detection_streak >= 2:
                        detected = True
                        cv2.putText(
                            frame,
                            "WASTE OBJECT DETECTED - CAPTURING...",
                            (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.75,
                            (80, 230, 170),
                            2
                        )
                        cv2.imshow(
                            "EcoMind AI - Camera | SPACE = Capture | ESC = Cancel",
                            frame
                        )
                        cv2.waitKey(300)
                        captured_path = self._save_frame(frame)
                        break


                cv2.putText(
                    frame,
                    last_status,
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2
                )
                cv2.putText(
                    frame,
                    "Place waste in front of camera | ESC = Cancel",
                    (20, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (220, 220, 220),
                    1
                )

                cv2.imshow(
                    "EcoMind AI - Camera | SPACE = Capture | ESC = Cancel",
                    frame
                )

                key = cv2.waitKey(1) & 0xFF

                if key == 32:
                    captured_path = self._save_frame(frame)
                    break

                if key == 27:
                    break

                if elapsed >= self.no_detection_seconds:
                    break

        finally:
            camera.release()
            cv2.destroyAllWindows()

        if detected and captured_path:
            QMessageBox.information(
                None,
                "Waste Detected",
                "Waste/object detected and image captured successfully."
            )
            return captured_path

        if not captured_path and not detected:
            QMessageBox.information(
                None,
                "No Waste Detected",
                "No waste detected for 5 seconds. Camera turned off."
            )

        return captured_path


# ============================================================
# MAIN APPLICATION
# ============================================================


class GraphWindow(QDialog):
    """Interactive bar/line graph window for EcoMind analytics."""
    def __init__(self, db, parent=None):
        super().__init__(parent) # type: ignore
        self.db = db
        self.setWindowTitle("EcoMind AI — Waste Graphs")
        self.resize(1050, 700)

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Graph:"))

        self.graph_type = QComboBox()
        self.graph_type.addItems(["Bar Graph — Category Waste",
                                  "Line Graph — Waste Trend"])
        controls.addWidget(self.graph_type)

        refresh = QPushButton("Refresh Graph")
        refresh.clicked.connect(self.draw_graph)
        controls.addWidget(refresh)
        controls.addStretch()
        layout.addLayout(controls)

        self.figure = Figure(figsize=(10, 6), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        self.draw_graph()

    def _rows(self):
        try:
            cur = self.db.connection.cursor()
            cur.execute("""
                SELECT record_date, category, weight
                FROM waste_records
                ORDER BY record_date ASC, id ASC
            """)
            return cur.fetchall()
        except Exception:
            return []

    def draw_graph(self):
        rows = self._rows()
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if not rows:
            ax.text(0.5, 0.5, "No waste data available yet.",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            self.canvas.draw()
            return

        graph = self.graph_type.currentText()

        if graph.startswith("Bar"):
            totals = {}
            for date, category, weight in rows:
                category = str(category or "Unknown")
                totals[category] = totals.get(category, 0.0) + float(weight or 0)

            categories = list(totals.keys())
            values = [totals[c] for c in categories]

            ax.bar(categories, values)
            ax.set_title("Waste Generated by Category")
            ax.set_xlabel("Waste Category")
            ax.set_ylabel("Weight (kg)")
            ax.tick_params(axis="x", rotation=30)

        else:
            daily = {}
            for date, category, weight in rows:
                day = str(date)
                daily[day] = daily.get(day, 0.0) + float(weight or 0)

            dates = list(daily.keys())
            values = [daily[d] for d in dates]

            ax.plot(dates, values, marker="o", linewidth=2)
            ax.set_title("Waste Generation Trend")
            ax.set_xlabel("Date")
            ax.set_ylabel("Waste (kg)")
            ax.tick_params(axis="x", rotation=30)
            ax.grid(True, alpha=0.25)

        self.figure.tight_layout()
        self.canvas.draw()


class EcoFlowMap(QWidget):
    """Stylized environmental command-center map inspired by industrial dashboards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.breakdown = {}
        self.score = 0.0
        self.phase = 0
        self.setMinimumHeight(330)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(90)

    def set_data(self, breakdown, score):
        self.breakdown = dict(breakdown or {})
        self.score = float(score or 0)
        self.update()

    def _animate(self):
        self.phase = (self.phase + 1) % 120
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(self.rect(), QColor('#06101E'))

        # Perspective-style grid
        grid_pen = QPen(QColor(16, 44, 70, 95), 1)
        painter.setPen(grid_pen)
        horizon = int(h * 0.64)
        for y in range(horizon, h + 30, 24):
            painter.drawLine(0, y, w, y)
        for x in range(-w, w * 2, 42):
            painter.drawLine(w // 2, horizon, x, h)

        # soft center glow
        glow = QRadialGradient(w * 0.50, h * 0.45, min(w, h) * 0.40)
        glow.setColorAt(0.0, QColor(20, 90, 130, 48))
        glow.setColorAt(0.45, QColor(10, 55, 95, 22))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(w*0.12), int(h*0.02), int(w*0.76), int(h*0.82))

        cx, cy = int(w * 0.50), int(h * 0.47)
        # Keep every node and its label inside the material-flow panel.
        # The original circular layout is preserved; only the vertical
        # coordinates are tightened to prevent clipping on smaller screens.
        # Move BATTERY WASTE upward by exactly 7 mm (using the widget's
        # logical DPI) so its circle and label stay comfortably visible.
        battery_shift_px = (7.0 / 25.4) * self.logicalDpiY()
        battery_py = 0.66 - (battery_shift_px / max(h, 1))

        positions = {
            # Balanced around the core so every stream remains visible
            # even on smaller laptop windows.
            'Food': (0.14, 0.22, '#39E6A4', 'ORGANIC'),
            'Plastic': (0.31, 0.10, '#31D8FF', 'PLASTIC'),
            'Paper': (0.64, 0.10, '#FFC857', 'PAPER'),
            'Battery Waste': (0.24, battery_py, '#FFD447', 'BATTERY WASTE'),
            'Glass': (0.84, 0.22, '#7895FF', 'GLASS'),
            'Metal': (0.79, 0.54, '#C184FF', 'METAL'),
            'E-waste': (0.61, 0.62, '#FF6FB5', 'E-WASTE'),
            'Other': (0.14, 0.43, '#61E6D2', 'OTHER'),
        }

        # Main process lines
        for cat, (px, py, color, label) in positions.items():
            x, y = int(w*px), int(h*py)
            pen = QPen(QColor(color), 2)
            painter.setPen(pen)
            painter.drawLine(cx, cy, x, y)
            # small animated pulse
            t = ((self.phase + list(positions).index(cat)*17) % 100) / 100
            pulse_x = cx + (x-cx)*t
            pulse_y = cy + (y-cy)*t
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(pulse_x)-3, int(pulse_y)-3, 6, 6)

            # node halo
            painter.setBrush(QBrush(QColor(color + '28')))
            painter.drawEllipse(x-20, y-20, 40, 40)
            painter.setBrush(QBrush(QColor('#091B2D')))
            painter.setPen(QPen(QColor(color), 2))
            painter.drawEllipse(x-13, y-13, 26, 26)
            painter.setPen(QColor(color))
            painter.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            painter.drawText(x-45, y+27, 90, 14, Qt.AlignmentFlag.AlignCenter, label)

        # central intelligence core
        r = 64
        pulse = 3 + int(4 * abs(((self.phase % 40) / 20) - 1))
        painter.setBrush(QBrush(QColor(31, 216, 180, 35)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx-r-pulse, cy-r-pulse, 2*(r+pulse), 2*(r+pulse))
        painter.setBrush(QBrush(QColor('#0B2034')))
        painter.setPen(QPen(QColor('#35D8FF'), 2.2))
        painter.drawEllipse(cx-r, cy-r, 2*r, 2*r)
        # Minimal central core label — intentionally only one clean title.
        painter.setPen(QColor('#F1FBFF'))
        painter.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        painter.drawText(cx-r, cy-9, 2*r, 22, Qt.AlignmentFlag.AlignCenter, 'AI CORE')

        # corner legend
        painter.setPen(QColor('#6E8AA5'))
        painter.setFont(QFont('Segoe UI', 7, QFont.Weight.Bold))
        painter.drawText(12, 17, 'LIVE MATERIAL FLOW  /  LOCAL INTELLIGENCE')
        painter.setPen(QColor('#3CE4B0'))
        painter.drawText(w-90, 17, 78, 12, Qt.AlignmentFlag.AlignRight, '● ONLINE')


class EcoMindApp(QMainWindow):

    def open_graphs(self):
        try:
            self.graph_window = GraphWindow(self.database, self)
            self.graph_window.exec()
        except Exception as e:
            QMessageBox.warning(self, "Graphs", f"Could not open graphs:\n{e}")

    def __init__(self):

        super().__init__()

        self.database = Database()
        self.analytics = Analytics(self.database)
        self.ml_engine = EcoMindMLEngine(self.database)

        self.location_service = LocationService()
        self.weather_service = WeatherService()
        self.vision = WasteVision()

        self.selected_image = ""
        self.ai_category = ""
        self.ai_confidence = 0

        self.setWindowTitle(
            "EcoMind AI — Intelligent Waste Management System"
        )

        screen = QApplication.primaryScreen().availableGeometry()
        width = min(1400, max(1100, int(screen.width() * 0.92)))
        height = min(820, max(650, int(screen.height() * 0.90)))
        self.resize(width, height)
        self.setMinimumSize(1050, 620)

        self.build_ui()

        self.load_dashboard()

        self.load_environment()

        self.weather_timer = QTimer()

        self.weather_timer.timeout.connect(
            self.load_environment
        )

        self.weather_timer.start(600000)

        # Live dashboard clock: refresh every second.
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

    def update_clock(self):
        """Update the compact local time/date display."""
        now = datetime.now()
        self.clock_time_label.setText(now.strftime('%I:%M:%S %p'))
        self.clock_date_label.setText(now.strftime('%d %b %Y'))

    # ========================================================
    # STYLE
    # ========================================================

    def apply_style(self):

        self.setStyleSheet("""
            QMainWindow {
                background-color: #050816;
            }

            QWidget {
                color: #e7fff7;
                font-family: Segoe UI;
            }

            QFrame#Sidebar {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #081A2B, stop:0.55 #071321, stop:1 #10102A);
                border-right: 1px solid #25405E;
            }

            QFrame#TopBar {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #081625, stop:0.55 #0A1730, stop:1 #15102B);
                border-bottom: 1px solid #182C45;
            }

            QLabel#Title {
                font-size: 25px;
                font-weight: bold;
                color: #7fffd4;
            }

            QLabel#Subtitle {
                color: #8AA0B6;
                font-size: 12px;
            }

            QPushButton {
                background-color: #0C1B2D;
                border: 1px solid #244563;
                border-radius: 8px;
                padding: 10px 15px;
                color: #DCEBFA;
            }

            QPushButton:hover {
                background-color: #172B4A;
                border: 1px solid #7B6CFF;
            }

            QPushButton#AccountButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #0b1d30, stop:0.55 #10263d, stop:1 #111a35);
            color: #eaf7ff;
            border: 1px solid #244d70;
            border-radius: 10px;
            text-align: left;
            padding: 8px 10px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton#AccountButton:hover {
            border: 1px solid #39d9ff;
            background: #132d46;
        }

        QPushButton#NavButton {
                text-align: left;
                padding: 13px;
                border: none;
                border-radius: 7px;
            }

            QPushButton#NavButton:hover {
                background-color: #10243A;
            }

            QPushButton#ActiveNav {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #183D67, stop:1 #29205B);
                color: #7FFFE0;
                border-left: 3px solid #45E5FF;
            }

            QFrame#Card {
                background-color: #0B1828;
                border: 1px solid #193452;
                border-radius: 12px;
            }

            QLabel#CardTitle {
                color: #8AA1B8;
                font-size: 12px;
            }

            QLabel#CardValue {
                color: #F2F8FF;
                font-size: 25px;
                font-weight: bold;
            }

            QLabel#SectionTitle {
                font-size: 20px;
                font-weight: bold;
                color: #69E8FF;
            }

            QLineEdit,
            QComboBox,
            QDoubleSpinBox,
            QTextEdit {
                background-color: #071421;
                border: 1px solid #1C3A59;
                border-radius: 7px;
                padding: 9px;
                color: white;
            }

            QTableWidget {
                background-color: #091813;
                border: 1px solid #193452;
                gridline-color: #172E48;
            }

            QHeaderView::section {
                background-color: #10243A;
                color: #69E8FF;
                padding: 8px;
                border: none;
            }

            QProgressBar {
                background-color: #10231e;
                border-radius: 8px;
                height: 14px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #37D7A5;
                border-radius: 8px;
            }
        """)

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        self.apply_style()

        root = QWidget()

        main_layout = QHBoxLayout(root)

        main_layout.setContentsMargins(0, 0, 0, 0)

        # ----------------------------------------------------
        # SIDEBAR
        # ----------------------------------------------------

        sidebar = QFrame()

        sidebar.setObjectName("Sidebar")

        sidebar.setFixedWidth(210)

        sidebar_layout = QVBoxLayout(sidebar)

        logo = QLabel("♻  ECOMIND AI")

        logo.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #72f5c7;
            padding: 15px;
        """)

        sidebar_layout.addWidget(logo)

        self.nav_buttons = []

        pages = [
            ("⌂   Dashboard", 0),
            ("＋   Add Waste", 1),
            ("▥   Waste Analytics", 2),
            ("↻   Recycling Tracker", 3),
            ("▤   History", 4),
            ("📊   Bar Graph", 5),
            ("🖼   Image Gallery", 6),
            ("⚙   Settings", 7)
        ]

        for text, index in pages:

            button = QPushButton(text)

            button.setObjectName("NavButton")

            button.clicked.connect(
                lambda checked=False, i=index:
                self.change_page(i)
            )

            sidebar_layout.addWidget(button)

            self.nav_buttons.append(button)

        sidebar_layout.addStretch()

        status = QLabel(
            "● AI Analysis Active\n"
            "EcoMind Intelligence Engine"
        )

        status.setStyleSheet("""
            color: #5ce0b2;
            padding: 8px 15px;
            font-size: 11px;
        """)

        sidebar_layout.addWidget(status)

        # ----------------------------------------------------
        # ACCOUNT MENU
        # ----------------------------------------------------
        account_button = QPushButton()
        account_button.setObjectName("AccountButton")
        account_button.setCursor(Qt.CursorShape.PointingHandCursor)
        account_button.setMinimumHeight(58)
        account_button.setMaximumHeight(64)
        account_button.setText("◉   Tech Inventor                 ⋮")
        account_button.setToolTip("Open Tech Inventor account menu")

        account_menu = QMenu(self)
        account_menu.setStyleSheet("""
            QMenu {
                background: #0b1b2c;
                color: #eaf7ff;
                border: 1px solid #24527a;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 9px 28px 9px 12px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background: #173a5d;
            }
        """)
        profile_action = account_menu.addAction("◉  Tech Inventor")
        profile_action.setEnabled(False)
        account_menu.addSeparator()
        account_menu.addAction("⚙  Account Settings", lambda: self.change_page(7))
        account_menu.addAction("ⓘ  About EcoMind AI", self.show_about)
        account_menu.addSeparator()
        account_menu.addAction("✕  Close Menu")

        account_button.clicked.connect(
            lambda: account_menu.exec(
                account_button.mapToGlobal(account_button.rect().topLeft())
            )
        )

        sidebar_layout.addWidget(account_button)

        # ----------------------------------------------------
        # RIGHT SIDE
        # ----------------------------------------------------

        right = QWidget()

        right_layout = QVBoxLayout(right)

        right_layout.setContentsMargins(0, 0, 0, 0)

        # ----------------------------------------------------
        # TOP BAR
        # ----------------------------------------------------

        topbar = QFrame()

        topbar.setObjectName("TopBar")

        top_layout = QHBoxLayout(topbar)

        title_box = QVBoxLayout()

        title = QLabel(
            "EcoMind AI"
        )

        title.setObjectName("Title")

        subtitle = QLabel(
            "Intelligent Waste Management System"
        )

        subtitle.setObjectName("Subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        top_layout.addLayout(title_box)

        top_layout.addStretch()

        # EXTRA FUNCTIONS ONLY HERE

        self.location_button = QPushButton(
            "📍 Location"
        )

        self.weather_button = QPushButton(
            "🌤 Weather"
        )

        # LIVE CLOCK ------------------------------------------------
        # Small, clean clock module: icon on the left, time/date on the right.
        clock_box = QFrame()
        clock_box.setFixedSize(136, 48)
        clock_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0B1A2D, stop:0.55 #101C35, stop:1 #17172F);
                border: 1px solid #304C72;
                border-radius: 10px;
            }
        """)
        clock_layout = QHBoxLayout(clock_box)
        clock_layout.setContentsMargins(8, 5, 9, 5)
        clock_layout.setSpacing(7)

        clock_icon = QLabel("◷")
        clock_icon.setFixedSize(28, 28)
        clock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clock_icon.setStyleSheet(
            "background:#15294A;border:1px solid #647DFF;border-radius:14px;"
            "color:#78E7FF;font-size:15px;font-weight:bold;"
        )
        clock_layout.addWidget(clock_icon)

        clock_text = QVBoxLayout()
        clock_text.setSpacing(0)
        self.clock_time_label = QLabel()
        self.clock_time_label.setStyleSheet(
            "font-size:11px;font-weight:700;color:#F4F8FF;background:transparent;border:none;padding:0;"
        )
        self.clock_date_label = QLabel()
        self.clock_date_label.setStyleSheet(
            "font-size:8px;color:#8FA6C0;background:transparent;border:none;padding:0;"
        )
        clock_text.addWidget(self.clock_time_label)
        clock_text.addWidget(self.clock_date_label)
        clock_layout.addLayout(clock_text)

        self.clock_widget = clock_box

        refresh_button = QPushButton(
            "⟳ Refresh"
        )

        export_button = QPushButton(
            "⇩ Export"
        )

        settings_button = QPushButton(
            "⚙"
        )

        about_button = QPushButton(
            "ⓘ"
        )

        self.location_button.clicked.connect(
            self.show_location
        )

        self.weather_button.clicked.connect(
            self.show_weather
        )

        refresh_button.clicked.connect(
            self.refresh_all
        )

        export_button.clicked.connect(
            self.export_csv
        )

        settings_button.clicked.connect(
            lambda: self.change_page(7)
        )

        about_button.clicked.connect(
            self.show_about
        )

        top_layout.addWidget(
            self.location_button
        )

        top_layout.addWidget(
            self.weather_button
        )

        top_layout.addWidget(
            self.clock_widget
        )

        top_layout.addWidget(
            refresh_button
        )

        top_layout.addWidget(
            export_button
        )

        top_layout.addWidget(
            settings_button
        )

        top_layout.addWidget(
            about_button
        )

        right_layout.addWidget(topbar)

        # ----------------------------------------------------
        # STACK
        # ----------------------------------------------------

        self.stack = QStackedWidget()

        # Dashboard pages. AI Insights and Sustainability Score are
        # intentionally removed from the navigation and page stack.
        self.dashboard_page = self.create_dashboard()
        self.add_page = self.create_add_waste()
        self.analytics_page = self.create_analytics()
        self.recycle_page = self.create_recycling()
        self.history_page = self.create_history()
        self.graph_page = self.create_graph_page()
        self.image_gallery_page = self.create_image_gallery_page()
        self.settings_page = self.create_settings()

        self.stack.addWidget(self.dashboard_page)      # 0
        self.stack.addWidget(self.add_page)            # 1
        self.stack.addWidget(self.analytics_page)     # 2
        self.stack.addWidget(self.recycle_page)        # 3
        self.stack.addWidget(self.history_page)        # 4
        self.stack.addWidget(self.graph_page)          # 5
        self.stack.addWidget(self.image_gallery_page)  # 6
        self.stack.addWidget(self.settings_page)       # 7

        right_layout.addWidget(self.stack)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(right)

        self.setCentralWidget(root)

        self.change_page(0)

    # ========================================================
    # CARD
    # ========================================================

    def card(self, title, value):

        frame = QFrame()

        frame.setObjectName("Card")

        layout = QVBoxLayout(frame)

        title_label = QLabel(title)

        title_label.setObjectName("CardTitle")

        value_label = QLabel(value)

        value_label.setObjectName("CardValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return frame, value_label

    # ========================================================
    # DASHBOARD
    # ========================================================

    def create_dashboard(self):
        """Original EcoMind national dashboard layout.

        Only targeted changes are made:
        - AI Insights panel/page removed.
        - Sustainability Index panel/page removed.
        - Environmental Material Flow is the dominant full-width visual.
        - Compact KPI strip remains above it.
        - Original donut, trend, impact and quick-action sections remain.
        """
        page = QWidget()
        page.setStyleSheet("background:#020A16;")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # ========================================================
        # 1. COMPACT KPI STRIP — ORIGINAL SIX CARDS
        # ========================================================
        metric_row = QHBoxLayout()
        metric_row.setSpacing(7)

        metric_data = [
            ("🗑", "TOTAL WASTE", "0.00 kg", "INPUT", "#25D9F5"),
            ("♻", "RECOVERED", "0.00 kg", "RECYCLE", "#35E6A1"),
            ("%", "RECOVERY RATE", "0.0%", "EFFICIENCY", "#5E91FF"),
            ("🍃", "TOP STREAM", "No data", "DOMINANT", "#FFC533"),
            ("◈", "ECO SCORE", "0.0", "INDEX", "#B477FF"),
            ("✦", "AI STATUS", "READY", "LOCAL ENGINE", "#FF4FA3"),
        ]

        refs = []

        for icon, label, value, sub, accent in metric_data:
            card = QFrame()
            card.setFixedHeight(56)
            card.setStyleSheet(
                f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 #07182A,stop:1 #081224);"
                f"border:1px solid #163B5A;"
                f"border-top:2px solid {accent};"
                f"border-radius:10px;"
            )

            row = QHBoxLayout(card)
            row.setContentsMargins(7, 3, 7, 3)
            row.setSpacing(6)

            icon_box = QLabel(icon)
            icon_box.setFixedSize(28, 28)
            icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_box.setStyleSheet(
                f"font-size:13px;font-weight:900;color:{accent};"
                f"background:{accent}18;"
                f"border:1px solid {accent}66;"
                f"border-radius:15px;"
            )
            row.addWidget(icon_box)

            text_col = QVBoxLayout()
            text_col.setSpacing(0)

            a = QLabel(label)
            a.setStyleSheet(
                f"font-size:7px;font-weight:900;letter-spacing:0.7px;"
                f"color:{accent};background:transparent;border:none;"
            )

            v = QLabel(value)
            v.setStyleSheet(
                "font-size:15px;font-weight:900;color:#F4FAFF;"
                "background:transparent;border:none;"
            )

            d = QLabel(sub)
            d.setStyleSheet(
                "font-size:6px;color:#718AA4;"
                "background:transparent;border:none;"
            )

            text_col.addWidget(a)
            text_col.addWidget(v)
            text_col.addWidget(d)

            row.addLayout(text_col, 1)
            metric_row.addWidget(card, 1)
            refs.append(v)

        self.total_value = refs[0]
        self.recycled_value = refs[1]
        self.rate_value = refs[2]
        self.highest_value = refs[3]
        self.ai_score_value = refs[4]
        self.ai_status_value = refs[5]

        self.reduction_value = QLabel("0.0")
        self.reduction_value.hide()

        layout.addLayout(metric_row, 0)

        # ========================================================
        # 2. LARGE ORIGINAL ENVIRONMENTAL MATERIAL FLOW
        #    NO AI INTELLIGENCE SIDE PANEL
        #    NO SUSTAINABILITY INDEX SIDE PANEL
        # ========================================================
        flow_card = QFrame()
        flow_card.setStyleSheet(
            "background:#03111F;"
            "border:1px solid #164C6B;"
            "border-radius:12px;"
        )

        flow_layout = QVBoxLayout(flow_card)
        flow_layout.setContentsMargins(10, 8, 10, 8)
        flow_layout.setSpacing(3)
        flow_card.setMinimumHeight(420)

        flow_head = QHBoxLayout()

        flow_title = QLabel("🌿  ENVIRONMENTAL MATERIAL FLOW")
        flow_title.setStyleSheet(
            "font-size:11px;font-weight:900;letter-spacing:1px;"
            "color:#EAF7FF;background:transparent;border:none;"
        )

        flow_head.addWidget(flow_title)
        flow_head.addStretch()

        flow_note = QLabel(
            "LIVE MATERIAL FLOW  /  LOCAL INTELLIGENCE"
        )
        flow_note.setStyleSheet(
            "font-size:7px;color:#6E8AA4;"
            "background:transparent;border:none;"
        )
        flow_head.addWidget(flow_note)

        online = QLabel("● ONLINE")
        online.setStyleSheet(
            "font-size:7px;font-weight:900;color:#35E6A1;"
            "background:#06261F;border:1px solid #1B6957;"
            "border-radius:6px;padding:4px 8px;"
        )
        flow_head.addSpacing(8)
        flow_head.addWidget(online)

        flow_layout.addLayout(flow_head)

        self.flow_map = EcoFlowMap()
        self.flow_map.setMinimumHeight(375)
        self.flow_map.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        flow_layout.addWidget(self.flow_map, 1)

        layout.addWidget(flow_card, 1)

        # ========================================================
        # 3. ORIGINAL ANALYTICS ROW
        # ========================================================
        analytics_row = QHBoxLayout()
        analytics_row.setSpacing(9)

        distribution = QFrame()
        distribution.setMinimumHeight(120)
        distribution.setMaximumHeight(126)
        distribution.setStyleSheet(
            "background:#061423;"
            "border:1px solid #18445D;"
            "border-radius:11px;"
        )

        dl = QVBoxLayout(distribution)
        dl.setContentsMargins(10, 7, 10, 7)
        dl.setSpacing(2)

        dt = QLabel("♻  WASTE STREAM DISTRIBUTION")
        dt.setStyleSheet(
            "font-size:8px;font-weight:900;letter-spacing:1px;"
            "color:#58E8D0;background:transparent;border:none;"
        )
        dl.addWidget(dt)

        self.dashboard_donut_figure = Figure(
            figsize=(3.2, 1.25),
            facecolor="#061423"
        )
        self.dashboard_donut_canvas = FigureCanvas(
            self.dashboard_donut_figure
        )
        self.dashboard_donut_canvas.setMinimumHeight(82)
        self.dashboard_donut_canvas.setMaximumHeight(94)

        dl.addWidget(self.dashboard_donut_canvas)
        analytics_row.addWidget(distribution, 4)

        trend = QFrame()
        trend.setMinimumHeight(120)
        trend.setMaximumHeight(126)
        trend.setStyleSheet(
            "background:#061423;"
            "border:1px solid #18445D;"
            "border-radius:11px;"
        )

        tl = QVBoxLayout(trend)
        tl.setContentsMargins(9, 7, 9, 7)
        tl.setSpacing(2)

        tt = QLabel("▥  WASTE TREND MONITOR")
        tt.setStyleSheet(
            "font-size:8px;font-weight:900;letter-spacing:1px;"
            "color:#62BFFF;background:transparent;border:none;"
        )
        tl.addWidget(tt)

        self.dashboard_chart_figure = Figure(
            figsize=(4.0, 1.15),
            facecolor="#061423"
        )
        self.dashboard_chart_canvas = FigureCanvas(
            self.dashboard_chart_figure
        )
        self.dashboard_chart_canvas.setMinimumHeight(82)
        self.dashboard_chart_canvas.setMaximumHeight(94)

        tl.addWidget(self.dashboard_chart_canvas)
        analytics_row.addWidget(trend, 5)

        impact = QFrame()
        impact.setMinimumHeight(120)
        impact.setMaximumHeight(126)
        impact.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #071B28,stop:1 #12102A);"
            "border:1px solid #315277;"
            "border-radius:11px;"
        )

        xl = QVBoxLayout(impact)
        xl.setContentsMargins(11, 8, 11, 8)
        xl.setSpacing(4)

        xt = QLabel("🍃  ECO IMPACT STATUS")
        xt.setStyleSheet(
            "font-size:8px;font-weight:900;letter-spacing:1px;"
            "color:#5BE9C1;background:transparent;border:none;"
        )
        xl.addWidget(xt)

        self.dashboard_distribution = QLabel(
            "No data recorded yet"
        )
        self.dashboard_distribution.setWordWrap(True)
        self.dashboard_distribution.setStyleSheet(
            "font-size:9px;font-weight:800;color:#F0F7FF;"
            "background:transparent;border:none;"
        )
        xl.addWidget(self.dashboard_distribution)

        xi = QLabel(
            "Use the collected data to identify high-waste "
            "streams and improve recovery."
        )
        xi.setWordWrap(True)
        xi.setStyleSheet(
            "font-size:7px;color:#7892AA;"
            "background:transparent;border:none;"
        )
        xl.addWidget(xi)
        xl.addStretch()

        analytics_row.addWidget(impact, 2)
        layout.addLayout(analytics_row, 0)

        # ========================================================
        # 4. QUICK ACTIONS — AI INSIGHTS REMOVED
        # ========================================================
        dock = QFrame()
        dock.setStyleSheet(
            "background:#04111E;"
            "border:1px solid #16415D;"
            "border-radius:11px;"
        )

        dock_layout = QHBoxLayout(dock)
        dock_layout.setContentsMargins(8, 4, 8, 4)
        dock_layout.setSpacing(7)

        dock_title = QLabel("QUICK ACTIONS")
        dock_title.setFixedWidth(120)
        dock_title.setStyleSheet(
            "font-size:8px;font-weight:900;letter-spacing:1px;"
            "color:#91A8BD;background:transparent;border:none;"
        )
        dock_layout.addWidget(dock_title)

        actions = [
            ("＋  Add Waste", lambda: self.change_page(1), "#35E6A1"),
            ("▣  Camera", lambda: self.change_page(1), "#25D9F5"),
            ("▧  Image Gallery", lambda: self.change_page(6), "#62BFFF"),
            ("▥  Analytics", lambda: self.change_page(2), "#FFC533"),
            ("♻  Recycling", lambda: self.change_page(3), "#35E6A1"),
        ]

        for text, command, accent in actions:
            btn = QPushButton(text)
            btn.setMinimumHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:#07182A;"
                f"border:1px solid #1A4160;"
                f"border-top:2px solid {accent};"
                f"border-radius:8px;color:#DDEBFA;"
                f"font-size:8px;font-weight:800;padding:6px 10px;}}"
                f"QPushButton:hover{{background:{accent}20;"
                f"border:1px solid {accent};color:white;}}"
            )
            btn.clicked.connect(command)
            dock_layout.addWidget(btn, 1)

        layout.addWidget(dock, 0)

        return page

    # ========================================================
    # ADD WASTE
    # ========================================================

    def create_add_waste(self):

        page = QWidget()

        layout = QVBoxLayout(page)

        title = QLabel(
            "Add Waste"
        )

        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        subtitle = QLabel(
            "Enter waste manually or optionally use Computer Vision."
        )

        subtitle.setStyleSheet(
            "color:#789d92;"
        )

        layout.addWidget(subtitle)

        form = QGridLayout()

        form.addWidget(
            QLabel("Date"),
            0, 0
        )

        self.date_input = QLineEdit(
            datetime.now().strftime("%Y-%m-%d")
        )

        form.addWidget(
            self.date_input,
            0, 1
        )

        form.addWidget(
            QLabel("Category"),
            1, 0
        )

        self.category_input = QComboBox()

        self.category_input.addItems(
            CATEGORIES
        )

        form.addWidget(
            self.category_input,
            1, 1
        )

        form.addWidget(
            QLabel("Weight (kg)"),
            2, 0
        )

        self.weight_input = QDoubleSpinBox()

        self.weight_input.setRange(
            0.01,
            10000
        )

        self.weight_input.setDecimals(2)

        form.addWidget(
            self.weight_input,
            2, 1
        )

        form.addWidget(
            QLabel("Recycled"),
            3, 0
        )

        self.recycled_input = QCheckBox(
            "This waste was recycled"
        )

        form.addWidget(
            self.recycled_input,
            3, 1
        )

        form.addWidget(
            QLabel("Description"),
            4, 0
        )

        self.description_input = QTextEdit()

        self.description_input.setMaximumHeight(
            100
        )

        form.addWidget(
            self.description_input,
            4, 1
        )

        layout.addLayout(form)

        # ----------------------------------------------------
        # CV BUTTONS
        # ----------------------------------------------------

        cv_box = QFrame()

        cv_box.setObjectName("Card")

        cv_layout = QHBoxLayout(cv_box)

        upload = QPushButton(
            "🖼 Upload Waste Image"
        )

        camera = QPushButton(
            "📷 Open Camera"
        )

        self.image_label = QLabel(
            "No image selected"
        )

        upload.clicked.connect(
            self.upload_image
        )

        camera.clicked.connect(
            self.capture_camera
        )

        cv_layout.addWidget(upload)
        cv_layout.addWidget(camera)
        cv_layout.addWidget(self.image_label)

        layout.addWidget(cv_box)

        self.ai_result_label = QLabel(
            "AI Vision: waiting for image..."
        )

        self.ai_result_label.setStyleSheet(
            "color:#72f5c7;"
        )

        layout.addWidget(
            self.ai_result_label
        )

        save_button = QPushButton(
            "✓ Save Waste Record"
        )

        save_button.setMinimumHeight(45)

        save_button.clicked.connect(
            self.save_waste
        )

        layout.addWidget(save_button)

        layout.addStretch()

        return page

    # ========================================================
    # IMAGE UPLOAD
    # ========================================================

    def upload_image(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Waste Image",
            "",
            "Images (*.png *.jpg *.jpeg)"
        )

        if not path:
            return

        self.selected_image = path

        self.display_image(path)

        self.run_vision(path)

    # ========================================================
    # CAMERA
    # ========================================================

    def capture_camera(self):

        path = self.vision.capture_image()

        if not path:
            return

        self.selected_image = path

        self.display_image(path)

        self.run_vision(path)

    # ========================================================
    # DISPLAY IMAGE
    # ========================================================

    def display_image(self, path):

        pixmap = QPixmap(path)

        if pixmap.isNull():
            return

        pixmap = pixmap.scaled(
            180,
            120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(
            pixmap
        )

    # ========================================================
    # COMPUTER VISION PIPELINE
    # ========================================================

    def run_vision(self, image_path):
        """Run the real local ML image classifier when enough labeled images exist."""
        self.ai_category = ""
        self.ai_confidence = 0.0

        try:
            category, confidence, message = self.ml_engine.classify_image(image_path)
            if category:
                self.ai_category = category
                self.ai_confidence = confidence
                self.ai_result_label.setText(
                    f"AI Vision: {category}  •  {confidence:.1f}% confidence\n"
                    f"{message}"
                )
            else:
                self.ai_result_label.setText(
                    "AI Vision: model is still learning.\n"
                    f"{message}\n"
                    "Save more correctly labeled waste images to train the classifier."
                )
        except Exception as error:
            self.ai_result_label.setText(
                f"AI Vision unavailable: {error}"
            )


    # ========================================================
    # SAVE WASTE
    # ========================================================

    def save_waste(self):

        date = self.date_input.text().strip()

        category = self.category_input.currentText()

        weight = self.weight_input.value()

        recycled = self.recycled_input.isChecked()

        description = (
            self.description_input
            .toPlainText()
            .strip()
        )

        if not date:

            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please enter a date."
            )

            return

        if weight <= 0:

            QMessageBox.warning(
                self,
                "Invalid Input",
                "Weight must be greater than zero."
            )

            return

        self.database.add_record(
            date,
            category,
            weight,
            recycled,
            description,
            self.selected_image,
            self.ai_category,
            self.ai_confidence
        )

        QMessageBox.information(
            self,
            "Saved",
            "Waste record saved successfully."
        )

        self.weight_input.setValue(0)

        self.description_input.clear()

        self.recycled_input.setChecked(False)

        self.selected_image = ""

        self.ai_category = ""

        self.ai_confidence = 0

        self.image_label.setText(
            "No image selected"
        )

        self.load_dashboard()

        self.load_history()

        self.load_analytics()

    # ========================================================
    # ANALYTICS
    # ========================================================

    def create_analytics(self):

        page = QWidget()

        layout = QVBoxLayout(page)

        title = QLabel(
            "Waste Analytics"
        )

        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        self.analytics_text = QTextEdit()

        self.analytics_text.setReadOnly(True)

        layout.addWidget(
            self.analytics_text
        )

        graph_button = QPushButton("📊  View Bar & Line Graphs")
        graph_button.setObjectName("PrimaryButton")
        graph_button.setMinimumHeight(44)
        graph_button.clicked.connect(self.open_graphs)
        layout.addWidget(graph_button)

        graph_hint = QLabel(
            "Bar graph: waste by category   •   Line graph: waste generation over time"
        )
        graph_hint.setStyleSheet("color:#86a99f; font-size:12px; padding:4px;")
        layout.addWidget(graph_hint)

        return page

    def load_analytics(self):

        data = self.analytics.category_breakdown()

        text = "CATEGORY BREAKDOWN\n\n"

        if not data:

            text += "No records available."

        else:

            for category, weight in sorted(
                data.items(),
                key=lambda x: x[1],
                reverse=True
            ):

                text += (
                    f"{category:<15} "
                    f"{weight:.2f} kg\n"
                )

            text += "\n"

            text += (
                f"Total Waste: "
                f"{self.analytics.total_waste():.2f} kg\n"
            )

            text += (
                f"Recycled Waste: "
                f"{self.analytics.recycled_waste():.2f} kg\n"
            )

            text += (
                f"Recycling Rate: "
                f"{self.analytics.recycling_rate():.1f}%\n"
            )

        self.analytics_text.setText(text)

    # ========================================================
    # AI INSIGHTS
    # ========================================================

    def create_ai_insights(self):

        page = QWidget()

        layout = QVBoxLayout(page)

        title = QLabel(
            "✦ AI Insights"
        )

        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        self.ai_insights_text = QTextEdit()

        self.ai_insights_text.setReadOnly(True)

        layout.addWidget(
            self.ai_insights_text
        )

        return page

    def load_ai_insights(self):
        records = self.analytics.records()

        if not records:
            self.ai_insights_text.setText(
                "ECOMIND AI\n\n"
                "No historical data yet. Add waste records to begin training the local ML models.\n\n"
                "ACTIVE ML MODULES\n"
                "• Isolation Forest anomaly detection\n"
                "• Random Forest waste prediction\n"
                "• Adaptive image classification\n"
                "\nThe models learn from your real EcoMind records; no fake AI confidence is shown."
            )
            return

        try:
            result = self.ml_engine.analyze()
        except Exception as error:
            self.ai_insights_text.setText(f"ML engine error:\n{error}")
            return

        anomaly = result["anomaly"]
        prediction = result["prediction"]
        vision = result["vision"]
        total = self.analytics.total_waste()
        rate = self.analytics.recycling_rate()
        highest = self.analytics.highest_category()

        text = (
            "ECOMIND AI — LOCAL MACHINE LEARNING\n\n"
            f"Records analyzed: {len(records)}\n"
            f"Total waste: {total:.2f} kg\n"
            f"Dominant stream: {highest}\n"
            f"Recycling rate: {rate:.1f}%\n\n"
            "ANOMALY DETECTION — ISOLATION FOREST\n"
            f"Status: {anomaly['status']}\n"
            f"{anomaly['message']}\n\n"
            "WASTE PREDICTION — RANDOM FOREST\n"
            f"Status: {prediction['status']}\n"
            f"{prediction['message']}\n"
        )

        if prediction.get("prediction") is not None:
            text += f"Trend: {prediction['direction'].upper()}\n\n"
        else:
            text += "\n"

        text += (
            "COMPUTER VISION — RANDOM FOREST\n"
            f"Status: {vision['status']}\n"
            f"{vision['message']}\n\n"
            "AI RECOMMENDATION\n"
        )

        if anomaly["is_anomaly"]:
            text += "• Investigate today's unusual waste spike before it becomes a recurring pattern.\n"
        if prediction.get("prediction") is not None and prediction["direction"] == "rising":
            text += f"• Predicted waste is rising; focus on reducing the {highest} stream.\n"
        if rate < 50:
            text += "• Increase recycling separation to improve recovery efficiency.\n"
        else:
            text += "• Maintain current recycling behavior and continue tracking daily waste.\n"

        self.ai_insights_text.setText(text)

    # ========================================================
    # RECYCLING
    # ========================================================

    def create_recycling(self):

        page = QWidget()

        layout = QVBoxLayout(page)

        title = QLabel(
            "Recycling Tracker"
        )

        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        self.recycling_progress = QProgressBar()

        layout.addWidget(
            self.recycling_progress
        )

        self.recycling_label = QLabel()

        layout.addWidget(
            self.recycling_label
        )

        layout.addStretch()

        return page

    def load_recycling(self):

        rate = self.analytics.recycling_rate()

        self.recycling_progress.setValue(
            int(rate)
        )

        self.recycling_label.setText(
            f"Current recycling rate: {rate:.1f}%"
        )

    # ========================================================
    # SCORE
    # ========================================================

    def create_score(self):

        page = QWidget()

        layout = QVBoxLayout(page)

        title = QLabel(
            "Sustainability Score"
        )

        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        self.score_progress = QProgressBar()

        self.score_progress.setMaximum(100)

        layout.addWidget(
            self.score_progress
        )

        self.score_label = QLabel()

        self.score_label.setStyleSheet(
            "font-size:20px; color:#7fffd4;"
        )

        layout.addWidget(
            self.score_label
        )

        layout.addStretch()

        return page

    def load_score(self):

        score = self.analytics.sustainability_score()

        self.score_progress.setValue(
            int(score)
        )

        self.score_label.setText(
            f"Sustainability Score: {score:.1f}/100"
        )

    # ========================================================
    # HISTORY
    # ========================================================

    def create_history(self):

        page = QWidget()

        layout = QVBoxLayout(page)

        title = QLabel(
            "Waste History"
        )

        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        self.history_table = QTableWidget()

        self.history_table.setColumnCount(8)

        self.history_table.setHorizontalHeaderLabels([
            "ID",
            "Date",
            "Category",
            "Weight",
            "Recycled",
            "Description",
            "Image",
            "AI Confidence"
        ])

        self.history_table.horizontalHeader().setStretchLastSection(
            True
        )

        layout.addWidget(
            self.history_table
        )

        return page

    def load_history(self):

        records = self.database.get_records()

        self.history_table.setRowCount(
            len(records)
        )

        for row_index, row in enumerate(records):

            values = [
                row[0],
                row[1],
                row[2],
                f"{row[3]:.2f} kg",
                "Yes" if row[4] else "No",
                row[5] or "",
                "Yes" if row[6] else "No",
                f"{row[8]:.1f}%"
                if row[8] else "—"
            ]

            for col, value in enumerate(values):

                self.history_table.setItem(
                    row_index,
                    col,
                    QTableWidgetItem(
                        str(value)
                    )
                )

    # ========================================================
    # BAR GRAPH PAGE
    # ========================================================

    def create_graph_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Waste Bar Graph")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Compare total waste generated by category.")
        subtitle.setStyleSheet("color:#86a99f; font-size:13px; padding-bottom:8px;")
        layout.addWidget(subtitle)

        self.graph_figure = Figure(figsize=(8, 5), facecolor="#101716")
        self.graph_canvas = FigureCanvas(self.graph_figure)
        layout.addWidget(self.graph_canvas)

        refresh = QPushButton("↻  Refresh Bar Graph")
        refresh.setObjectName("PrimaryButton")
        refresh.setMinimumHeight(42)
        refresh.clicked.connect(self.refresh_bar_graph)
        layout.addWidget(refresh)

        self.refresh_bar_graph()
        return page

    def refresh_bar_graph(self):
        self.graph_figure.clear()
        ax = self.graph_figure.add_subplot(111)
        ax.set_facecolor("#101716")

        try:
            cur = self.database.connection.cursor()
            cur.execute("""
                SELECT category, COALESCE(SUM(weight), 0)
                FROM waste_records
                GROUP BY category
                ORDER BY SUM(weight) DESC
            """)
            rows = cur.fetchall()
        except Exception as e:
            ax.text(0.5, 0.5, f"Could not load graph: {e}", ha="center", va="center", color="white")
            self.graph_canvas.draw()
            return

        if not rows:
            ax.text(0.5, 0.5, "No waste data available yet.", ha="center", va="center", fontsize=14, color="white")
            ax.set_axis_off()
        else:
            categories = [str(row[0]) for row in rows]
            weights = [float(row[1]) for row in rows]
            ax.bar(categories, weights)
            ax.set_title("Waste Generated by Category", fontsize=16, pad=15, color="white")
            ax.set_xlabel("Waste Category", color="white")
            ax.set_ylabel("Waste (kg)", color="white")
            ax.tick_params(axis="x", rotation=25, colors="white")
            ax.tick_params(axis="y", colors="white")
            ax.grid(axis="y", alpha=0.2)
            for spine in ax.spines.values():
                spine.set_color("#3b5f55")
            self.graph_figure.tight_layout()

        self.graph_canvas.draw()

    # ========================================================
    # IMAGE GALLERY PAGE
    # ========================================================

    def create_image_gallery_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Waste Image Gallery")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "View images saved with your waste records. Click View Image to open a larger preview."
        )
        subtitle.setStyleSheet("color:#86a99f; font-size:13px; padding-bottom:8px;")
        layout.addWidget(subtitle)

        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.image_gallery_container = QWidget()
        self.image_gallery_grid = QGridLayout(self.image_gallery_container)
        self.image_gallery_grid.setSpacing(16)
        self.image_scroll.setWidget(self.image_gallery_container)

        layout.addWidget(self.image_scroll)

        refresh = QPushButton("↻  Refresh Image Gallery")
        refresh.setObjectName("PrimaryButton")
        refresh.setMinimumHeight(42)
        refresh.clicked.connect(self.load_image_gallery)
        layout.addWidget(refresh)

        self.load_image_gallery()
        return page

    def load_image_gallery(self):
        # Remove old gallery cards.
        while self.image_gallery_grid.count():
            item = self.image_gallery_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        records = self.database.get_records()
        image_records = [row for row in records if row[6] and os.path.exists(row[6])]

        if not image_records:
            empty = QLabel(
                "No saved waste images found.\n\n"
                "Add a waste record with Upload Waste Image or Open Camera, then save it."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "color:#86a99f; font-size:15px; padding:40px;"
            )
            self.image_gallery_grid.addWidget(empty, 0, 0, 1, 2)
            return

        for i, row in enumerate(image_records):
            record_id, date, category, weight, recycled, description, image_path, ai_category, ai_confidence = row

            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)

            image = QLabel()
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                image.setPixmap(
                    pixmap.scaled(250, 170, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
                )
            else:
                image.setText("Image could not be loaded")
            image.setMinimumSize(250, 170)
            card_layout.addWidget(image)

            info = QLabel(
                f"Record #{record_id}  •  {date}\n"
                f"{category}  •  {float(weight):.2f} kg\n"
                f"{'Recycled' if recycled else 'Not recycled'}"
            )
            info.setStyleSheet("color:#d7eee7; font-size:12px; padding:4px;")
            card_layout.addWidget(info)

            view_button = QPushButton("👁  View Image")
            view_button.clicked.connect(
                lambda checked=False, path=image_path, rid=record_id: self.view_saved_image(path, rid)
            )
            card_layout.addWidget(view_button)

            column = i % 2
            row_number = i // 2
            self.image_gallery_grid.addWidget(card, row_number, column)

        self.image_gallery_grid.setColumnStretch(0, 1)
        self.image_gallery_grid.setColumnStretch(1, 1)

    def view_saved_image(self, image_path, record_id):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"EcoMind AI — Waste Image #{record_id}")
        dialog.resize(900, 650)

        layout = QVBoxLayout(dialog)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            image_label.setText("Could not open this image.")
            image_label.setStyleSheet("color:white; font-size:16px;")
        else:
            image_label.setPixmap(
                pixmap.scaled(820, 540, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )

        layout.addWidget(image_label)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec()

    # ========================================================
    # SETTINGS
    # ========================================================

    def create_settings(self):

        page = QWidget()

        layout = QVBoxLayout(page)

        title = QLabel(
            "Settings"
        )

        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        clear_button = QPushButton(
            "Clear All Waste Data"
        )

        clear_button.clicked.connect(
            self.clear_data
        )

        layout.addWidget(
            clear_button
        )

        info = QLabel(
            "Database: Local SQLite\n"
            "AI Vision: OpenCV pipeline ready\n"
            "Weather: Open-Meteo\n"
            "Location: Cached IP-based location"
        )

        info.setStyleSheet(
            "color:#7faaa0; padding:15px;"
        )

        layout.addWidget(info)

        layout.addStretch()

        return page

    # ========================================================
    # NAVIGATION
    # ========================================================

    def change_page(self, index):

        self.stack.setCurrentIndex(index)

        for i, button in enumerate(
            self.nav_buttons
        ):

            if i == index:
                button.setObjectName(
                    "ActiveNav"
                )

            else:
                button.setObjectName(
                    "NavButton"
                )

            button.style().unpolish(button)
            button.style().polish(button)

        if index == 0:
            self.load_dashboard()

        elif index == 2:
            self.load_analytics()

        elif index == 3:
            self.load_recycling()

        elif index == 4:
            self.load_history()

        elif index == 6:
            self.load_image_gallery()

    # ========================================================
    # DASHBOARD DATA
    # ========================================================

    def load_dashboard(self):

        total = self.analytics.total_waste()
        recycled = self.analytics.recycled_waste()
        rate = self.analytics.recycling_rate()
        highest = self.analytics.highest_category()
        score = self.analytics.sustainability_score()

        self.total_value.setText(f"{total:.2f} kg")
        self.recycled_value.setText(f"{recycled:.2f} kg")
        self.rate_value.setText(f"{rate:.1f}%")
        self.highest_value.setText(highest)
        self.ai_score_value.setText(f"{score:.1f}")

        # Keep the hidden reduction value for compatibility with
        # the existing analytics code, but do not show a dashboard
        # Sustainability Index panel.
        self.reduction_value.setText(f"{score:.1f}")

        if hasattr(self, "flow_map"):
            self.flow_map.set_data(
                self.analytics.category_breakdown(),
                score
            )

        # --------------------------------------------------------
        # DONUT CHART
        # --------------------------------------------------------
        if hasattr(self, "dashboard_donut_figure"):
            try:
                self.dashboard_donut_figure.clear()
                ax = self.dashboard_donut_figure.add_subplot(111)
                ax.set_facecolor("#061423")

                breakdown = self.analytics.category_breakdown()

                labels = [
                    cat for cat in CATEGORIES
                    if float(breakdown.get(cat, 0) or 0) > 0
                ]
                values = [
                    float(breakdown.get(cat, 0) or 0)
                    for cat in labels
                ]

                if values and sum(values) > 0:
                    palette = {
                        "Food": "#35E6A1",
                        "Plastic": "#25D9F5",
                        "Paper": "#FFC533",
                        "Glass": "#5E91FF",
                        "Metal": "#B477FF",
                        "E-waste": "#FF4FA3",
                        "Other": "#61E6D2"
                    }

                    wedges, _ = ax.pie(
                        values,
                        startangle=90,
                        counterclock=False,
                        colors=[
                            palette.get(c, "#55758E")
                            for c in labels
                        ],
                        wedgeprops={
                            "width": 0.34,
                            "edgecolor": "#061423",
                            "linewidth": 2.2
                        }
                    )

                    ax.legend(
                        wedges,
                        labels,
                        loc="center left",
                        bbox_to_anchor=(0.98, 0.5),
                        frameon=False,
                        labelcolor="#DDEBFA",
                        fontsize=7.2,
                        handlelength=0.9,
                        handletextpad=0.5,
                        borderaxespad=0.0
                    )

                else:
                    ax.text(
                        0.5, 0.54,
                        "NO WASTE RECORDED YET",
                        ha="center",
                        va="center",
                        color="#7895AE",
                        fontsize=8.5,
                        fontweight="bold",
                        transform=ax.transAxes
                    )
                    ax.text(
                        0.5, 0.43,
                        "Add your first waste entry to begin analysis",
                        ha="center",
                        va="center",
                        color="#506B83",
                        fontsize=6.5,
                        transform=ax.transAxes
                    )

                ax.set_axis_off()
                self.dashboard_donut_figure.tight_layout(pad=0.2)
                self.dashboard_donut_canvas.draw_idle()

            except Exception:
                pass

        # --------------------------------------------------------
        # TREND CHART
        # --------------------------------------------------------
        if hasattr(self, "dashboard_chart_figure"):
            try:
                self.dashboard_chart_figure.clear()
                ax = self.dashboard_chart_figure.add_subplot(111)
                ax.set_facecolor("#071523")

                records = self.database.get_records()
                dates = {}

                for row in records:
                    dates[row[1]] = (
                        dates.get(row[1], 0)
                        + float(row[3] or 0)
                    )

                items = sorted(dates.items())[-7:]

                if items:
                    x = list(range(len(items)))
                    y = [v for _, v in items]

                    ax.plot(
                        x, y,
                        marker="o",
                        linewidth=2,
                        markersize=4,
                        color="#31D8FF"
                    )

                    ax.fill_between(
                        x, y, [0] * len(y),
                        alpha=0.10,
                        color="#31D8FF"
                    )

                    ax.set_xticks(x)
                    ax.set_xticklabels(
                        [d[-5:] for d, _ in items],
                        color="#7E98B0",
                        fontsize=6
                    )

                    ax.tick_params(
                        axis="y",
                        colors="#7E98B0",
                        labelsize=6
                    )

                    ax.grid(
                        axis="y",
                        alpha=0.14,
                        color="#58738A"
                    )

                    ax.spines[:].set_visible(False)

                else:
                    ax.text(
                        0.5, 0.54,
                        "NO HISTORICAL DATA YET",
                        ha="center",
                        va="center",
                        color="#7895AE",
                        fontsize=8,
                        fontweight="bold",
                        transform=ax.transAxes
                    )
                    ax.text(
                        0.5, 0.43,
                        "Your daily waste trend will appear here",
                        ha="center",
                        va="center",
                        color="#506B83",
                        fontsize=6.5,
                        transform=ax.transAxes
                    )
                    ax.set_xticks([])
                    ax.set_yticks([])

                self.dashboard_chart_figure.tight_layout(pad=0.4)
                self.dashboard_chart_canvas.draw_idle()

            except Exception:
                pass

        # --------------------------------------------------------
        # ECO IMPACT STATUS
        # --------------------------------------------------------
        breakdown = self.analytics.category_breakdown()

        if hasattr(self, "dashboard_distribution"):
            if breakdown:
                ranked = sorted(
                    breakdown.items(),
                    key=lambda item: item[1],
                    reverse=True
                )

                self.dashboard_distribution.setText(
                    "   •   ".join(
                        f"{cat}: {value:.1f} kg"
                        for cat, value in ranked[:4]
                    )
                )
            else:
                self.dashboard_distribution.setText(
                    "No data recorded yet"
                )

        # --------------------------------------------------------
        # AI STATUS ONLY — NO AI INSIGHTS PANEL
        # --------------------------------------------------------
        if total == 0:
            self.ai_status_value.setText("READY")
        else:
            try:
                ml = self.ml_engine.analyze()
                active = ml["active_models"]
                self.ai_status_value.setText(
                    "ACTIVE" if active else "READY"
                )
            except Exception:
                self.ai_status_value.setText("ERROR")

    # ========================================================
    # LOCATION / WEATHER
    # ========================================================

    def load_environment(self):

        location = (
            self.location_service
            .get_location()
        )

        weather = (
            self.weather_service
            .get_weather(
                location["lat"],
                location["lon"]
            )
        )

        if location:

            self.location_button.setText(
                f"📍 {location['city']}"
            )

        if weather:

            temp = weather.get(
                "temperature_2m",
                "--"
            )

            self.weather_button.setText(
                f"🌤 {temp}°C"
            )

        else:

            self.weather_button.setText(
                "🌤 Weather"
            )

    def show_location(self):

        location = (
            self.location_service
            .get_location()
        )

        QMessageBox.information(
            self,
            "Current Location",
            (
                f"City: {location['city']}\n"
                f"Region: {location['region']}\n"
                f"Country: {location['country']}\n"
                f"Coordinates: "
                f"{location['lat']}, "
                f"{location['lon']}"
            )
        )

    def show_weather(self):

        location = (
            self.location_service
            .get_location()
        )

        weather = (
            self.weather_service
            .get_weather(
                location["lat"],
                location["lon"]
            )
        )

        if not weather:

            QMessageBox.warning(
                self,
                "Weather",
                "Unable to retrieve current weather."
            )

            return

        QMessageBox.information(
            self,
            "Environmental Context",
            (
                f"Location: {location['city']}\n\n"
                f"Temperature: "
                f"{weather.get('temperature_2m', '--')} °C\n"
                f"Humidity: "
                f"{weather.get('relative_humidity_2m', '--')}%\n"
                f"Feels Like: "
                f"{weather.get('apparent_temperature', '--')} °C\n"
                f"Precipitation: "
                f"{weather.get('precipitation', '--')} mm\n"
                f"Wind: "
                f"{weather.get('wind_speed_10m', '--')} km/h"
            )
        )

    # ========================================================
    # REFRESH
    # ========================================================

    def refresh_all(self):

        self.load_dashboard()

        self.load_analytics()

        self.load_recycling()

        self.load_history()

        self.load_environment()

    # ========================================================
    # CSV EXPORT
    # ========================================================

    def export_csv(self):

        records = self.database.get_records()

        if not records:

            QMessageBox.information(
                self,
                "Export",
                "There is no data to export."
            )

            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Waste Data",
            "ecomind_waste_data.csv",
            "CSV Files (*.csv)"
        )

        if not path:
            return

        try:

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(file)

                writer.writerow([
                    "ID",
                    "Date",
                    "Category",
                    "Weight",
                    "Recycled",
                    "Description",
                    "Image",
                    "AI Category",
                    "AI Confidence"
                ])

                writer.writerows(records)

            QMessageBox.information(
                self,
                "Export Complete",
                "Waste data exported successfully."
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Export Error",
                str(error)
            )

    # ========================================================
    # CLEAR DATA
    # ========================================================

    def clear_data(self):

        answer = QMessageBox.question(
            self,
            "Confirm",
            "Delete ALL waste records?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.database.clear_all()

        self.refresh_all()

        QMessageBox.information(
            self,
            "Complete",
            "All waste data has been cleared."
        )

    # ========================================================
    # ABOUT
    # ========================================================

    def show_about(self):

        QMessageBox.information(
            self,
            "About EcoMind AI",
            (
                "EcoMind AI\n\n"
                "Intelligent Waste Management System\n\n"
                "Core mission:\n"
                "Use AI and data intelligence to understand "
                "waste, detect patterns, predict trends, "
                "and help users reduce environmental impact.\n\n"
                "Python • PyQt6 • SQLite • OpenCV • scikit-learn • NumPy"
            )
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(self, event):

        self.database.close()

        event.accept()


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    app.setFont(
        QFont("Segoe UI", 10)
    )

    window = EcoMindApp()

    window.show()

    sys.exit(
        app.exec()
    )