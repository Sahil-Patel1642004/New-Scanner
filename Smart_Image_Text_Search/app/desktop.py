# Feature version1
from pathlib import Path
from datetime import datetime, timedelta, timezone
import html
import re
import shutil
import sys,os

from PyQt6.QtCore import QEvent, QObject, QRunnable, QRectF, QSize, QThreadPool, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QImageReader, QKeySequence, QPainter, QPen, QPixmap, QIcon, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import main as backend
from .scanora_licensing.client import LicenceClient, LicenceError, LicenceServiceUnavailable


def escape_html(value: str) -> str:
    return html.escape(str(value), quote=False)


def logo_path() -> str:
    """Return the absolute path of logo.ico for both source and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "logo.ico")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "logo.ico"
    )


def ensure_licence() -> bool:
    try:
        client = LicenceClient()
    except LicenceError as error:
        QMessageBox.warning(None, "Licence configuration", str(error))
        return False

    cached = client.load_cached_licence()
    if cached is not None:
        try:
            client.refresh()
            return True
        except LicenceServiceUnavailable:
            return True
        except LicenceError as error:
            QMessageBox.warning(None, "Licence validation", str(error))

    while True:
        product_key, accepted = QInputDialog.getText(
            None,
            "Activate Prakshal-Scanora Search",
            "Enter your product key:",
        )
        if not accepted:
            return False
        try:
            client.activate(product_key)
            QMessageBox.information(None, "Licence activated", "This device is activated.")
            return True
        except LicenceError as error:
            QMessageBox.warning(None, "Activation failed", str(error))


class AppLoader(QWidget):
    """Frameless splash loader that shows the app logo while work is starting."""

    def __init__(
        self,
        message: str = "Loading Smart Image Text Search...",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        if parent is None:
            flags = (
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.SplashScreen
                | Qt.WindowType.WindowStaysOnTopHint
            )
        else:
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 380)

        card = QFrame(self)
        card.setObjectName("loaderCard")
        card.setStyleSheet("""
            QFrame#loaderCard {
                background: #ffffff;
                border: 1px solid #d7dade;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(14)
        layout.addStretch(1)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QIcon(logo_path())
        pixmap = icon.pixmap(132, 132)
        if pixmap.isNull():
            self.logo_label.setText("Prakshal-Scanora")
            self.logo_label.setStyleSheet("font-size: 20px; font-weight: 600; color: #2f5d8a;")
        else:
            self.logo_label.setPixmap(pixmap)
        layout.addWidget(self.logo_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("Prakshal-Scanora Search")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 600; color: #1f2430;")
        layout.addWidget(self.title_label)

        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        layout.addWidget(self.message_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet("""
            QProgressBar { background: #e7eaee; border: none; border-radius: 3px; }
            QProgressBar::chunk { background: #2f5d8a; border-radius: 3px; }
        """)
        layout.addWidget(self.progress)
        layout.addStretch(1)

        holder = QVBoxLayout()
        holder.setContentsMargins(0, 0, 0, 0)
        holder.addWidget(card)
        holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(holder)

    def set_message(self, message: str):
        self.message_label.setText(message)

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.center().x() - self.width() // 2,
            geometry.center().y() - self.height() // 2,
        )

    def center_on(self, parent: QWidget):
        parent_center = parent.rect().center()
        self.move(
            parent_center.x() - self.width() // 2,
            parent_center.y() - self.height() // 2,
        )
        self.raise_()


class ScanSignals(QObject):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)
    progress = pyqtSignal(dict)


class ScanTask(QRunnable):
    def __init__(self, folder: str, force_ocr: bool):
        super().__init__()
        self.folder = folder
        self.force_ocr = force_ocr
        self.signals = ScanSignals()

    def run(self):
        try:
            self.signals.finished.emit(
                backend.scan_folder(
                    self.folder,
                    self.force_ocr,
                    self.signals.progress.emit,
                )
            )
        except Exception as error:
            self.signals.failed.emit(str(error))


class WordBoxSignals(QObject):
    loaded = pyqtSignal(list)


class WordBoxTask(QRunnable):
    """Fetch OCR word boxes for an image without blocking the UI thread."""

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = WordBoxSignals()

    def run(self):
        try:
            self.signals.loaded.emit(backend.load_word_boxes(self.path))
        except Exception:
            self.signals.loaded.emit([])


class SearchSignals(QObject):
    finished = pyqtSignal(int, dict)
    failed = pyqtSignal(int, str)


class SearchTask(QRunnable):
    def __init__(self, generation: int, **search_options):
        super().__init__()
        self.generation = generation
        self.search_options = search_options
        self.signals = SearchSignals()

    def run(self):
        try:
            self.signals.finished.emit(
                self.generation,
                backend.search(**self.search_options),
            )
        except Exception as error:
            self.signals.failed.emit(self.generation, str(error))


class ImagePreview(QMainWindow):
    MIN_SCALE = 0.1
    MAX_SCALE = 8.0
    ZOOM_STEP = 1.25

    def __init__(self, path: str, query: str = ""):
        super().__init__()
        self.setWindowTitle(Path(path).name)
        self.resize(960, 720)
        self.path = path
        self.query = (query or "").strip()
        self.word_boxes: list = []
        self.highlight_enabled = bool(self.query)
        self.source_pixmap = QPixmap(path)
        self.scale_factor = 1.0
        self.fit_mode = True

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background: #10151c; border: none; }"
            "QScrollArea > QWidget > QWidget { background: #10151c; }"
            "QScrollBar:vertical { background: #10151c; width: 12px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #4a5568; border-radius: 6px; min-height: 32px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar:horizontal { background: #10151c; height: 12px; margin: 0; }"
            "QScrollBar::handle:horizontal { background: #4a5568; border-radius: 6px; min-width: 32px; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
        )

        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: #10151c; color: #d8dee8;")
        if self.source_pixmap.isNull():
            self.image_label.setText("Unable to load this image.")
        self.scroll_area.setWidget(self.image_label)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scroll_area, 1)

        toolbar = QWidget()
        toolbar.setStyleSheet("background: #1a212c;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 10, 12, 12)
        toolbar_layout.setSpacing(8)

        self.zoom_out_button = self._make_toolbar_button("Zoom Out", "-", "Zoom out (Ctrl+-)")
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.zoom_in_button = self._make_toolbar_button("Zoom In", "+", "Zoom in (Ctrl++)")
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.fit_button = self._make_toolbar_button("Fit", "Fit", "Fit image to window (Ctrl+0)")
        self.fit_button.clicked.connect(self.fit_to_window)
        self.actual_size_button = self._make_toolbar_button(
            "Actual Size",
            "1:1",
            "Show at actual size (Ctrl+1)",
        )
        self.actual_size_button.clicked.connect(self.actual_size)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(70)
        self.zoom_label.setStyleSheet("color: #d8dee8; font-size: 13px; font-weight: 600;")

        toolbar_layout.addWidget(self.zoom_out_button)
        toolbar_layout.addWidget(self.zoom_label)
        toolbar_layout.addWidget(self.zoom_in_button)
        toolbar_layout.addWidget(self.fit_button)
        toolbar_layout.addWidget(self.actual_size_button)
        self.highlight_button = self._make_toolbar_button(
            "Highlight",
            "Highlight",
            "Show or hide the boxes around the matching words",
        )
        self.highlight_button.setCheckable(True)
        self.highlight_button.setChecked(self.highlight_enabled)
        self.highlight_button.toggled.connect(self.set_highlight)
        toolbar_layout.addWidget(self.highlight_button)
        self.match_label = QLabel()
        self.match_label.setStyleSheet("color: #ffd166; font-size: 13px; font-weight: 600;")
        toolbar_layout.addWidget(self.match_label)
        toolbar_layout.addStretch(1)

        download_button = QPushButton("Download Image")
        download_button.setStyleSheet(
            "QPushButton { background-color: #2f7a4f; color: #ffffff;"
            "border: 1px solid #2f7a4f; border-radius: 4px; min-width: 150px;"
            "min-height: 36px; padding: 0px 14px; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background-color: #25633f; border-color: #25633f; }"
        )
        download_button.setToolTip("Save a copy of this image to your computer")
        download_button.clicked.connect(lambda: ImagePreview.download_file(self, path))
        toolbar_layout.addWidget(download_button)
        layout.addWidget(toolbar)

        self.setCentralWidget(container)

        self.zoom_shortcuts = [
            QShortcut(QKeySequence.StandardKey.ZoomIn, self),
            QShortcut(QKeySequence.StandardKey.ZoomOut, self),
            QShortcut(QKeySequence("Ctrl+="), self),
            QShortcut(QKeySequence("Ctrl+-"), self),
            QShortcut(QKeySequence("Ctrl+0"), self),
            QShortcut(QKeySequence("Ctrl+1"), self),
        ]
        self.zoom_shortcuts[0].activated.connect(self.zoom_in)
        self.zoom_shortcuts[1].activated.connect(self.zoom_out)
        self.zoom_shortcuts[2].activated.connect(self.zoom_in)
        self.zoom_shortcuts[3].activated.connect(self.zoom_out)
        self.zoom_shortcuts[4].activated.connect(self.fit_to_window)
        self.zoom_shortcuts[5].activated.connect(self.actual_size)

        if self.query:
            self.match_label.setText("Finding matches...")
            task = WordBoxTask(path)
            task.signals.loaded.connect(self.set_word_boxes)
            QThreadPool.globalInstance().start(task)

    def set_word_boxes(self, words: list):
        self.word_boxes = words if isinstance(words, list) else []
        self.apply_scale(self.scale_factor, anchor_center=False)
        self.scroll_to_first_match()

    def set_highlight(self, enabled: bool):
        self.highlight_enabled = bool(enabled)
        self.apply_scale(self.scale_factor, anchor_center=False)

    def matching_boxes(self) -> list:
        """Find the best matching OCR boxes for each search term."""
        if not self.query or not self.word_boxes:
            return []

        terms = backend.search_highlight_terms(self.query)
        parsed = []

        for box in self.word_boxes:
            try:
                word = str(box["text"]).strip()
                left = float(box["x"])
                top = float(box["y"])
                width = float(box["w"])
                height = float(box["h"])
            except (KeyError, TypeError, ValueError):
                continue

            if not word or width <= 0 or height <= 0:
                continue

            item = {
                "text": word,
                "x": left,
                "y": top,
                "w": width,
                "h": height,
                "cy": top + height / 2,
            }
            parsed.append(item)

        lines = []
        for item in sorted(parsed, key=lambda value: value["cy"]):
            line = next(
                (
                    candidate
                    for candidate in lines
                    if abs(
                        item["cy"]
                        - sum(box["cy"] for box in candidate) / len(candidate)
                    )
                    <= max(0.008, max(box["h"] for box in candidate) * 0.8)
                ),
                None,
            )
            if line is None:
                lines.append([item])
            else:
                line.append(item)

        # Keep short adjacent-box combinations for identifiers OCR split apart.
        sequences = []
        for line in lines:
            line.sort(key=lambda item: item["x"])
            for start in range(len(line)):
                sequence = [line[start]]
                compact = re.sub(r"[^a-z0-9]+", "", sequence[0]["text"].casefold())
                sequences.append((compact, sequence))

                for current in line[start + 1 : start + 5]:
                    previous = sequence[-1]
                    max_height = max(previous["h"], current["h"])
                    gap = current["x"] - (previous["x"] + previous["w"])
                    if gap < -0.005 or gap > max(0.015, max_height * 1.8):
                        break

                    sequence = [*sequence, current]
                    compact += re.sub(
                        r"[^a-z0-9]+", "", current["text"].casefold()
                    )
                    sequences.append((compact, sequence))

        matches = []
        for term in terms:
            term = str(term).strip().casefold()
            if not term:
                continue

            exact_words = [
                item
                for item in parsed
                if backend.search_term_matches(
                    term, item["text"], allow_fuzzy_numeric=False
                )
            ]
            if exact_words:
                matches.extend(
                    (item["x"], item["y"], item["w"], item["h"])
                    for item in exact_words
                )
                continue

            if term.isdigit():
                exact_sequences = [
                    sequence
                    for compact, sequence in sequences
                    if term in compact and len(sequence) > 1
                ]
                if exact_sequences:
                    shortest = min(map(len, exact_sequences))
                    for sequence in exact_sequences:
                        if len(sequence) == shortest:
                            left = min(item["x"] for item in sequence)
                            top = min(item["y"] for item in sequence)
                            right = max(item["x"] + item["w"] for item in sequence)
                            bottom = max(item["y"] + item["h"] for item in sequence)
                            matches.append((left, top, right - left, bottom - top))
                    continue

            fuzzy_words = [
                item
                for item in parsed
                if backend.search_term_matches(term, item["text"])
            ]
            if fuzzy_words:
                matches.extend(
                    (item["x"], item["y"], item["w"], item["h"])
                    for item in fuzzy_words
                )
                continue

            if term.isdigit():
                fuzzy_sequences = [
                    sequence
                    for compact, sequence in sequences
                    if len(sequence) > 1
                    and backend.search_term_matches(term, compact)
                ]
                if fuzzy_sequences:
                    shortest = min(map(len, fuzzy_sequences))
                    for sequence in fuzzy_sequences:
                        if len(sequence) == shortest:
                            left = min(item["x"] for item in sequence)
                            top = min(item["y"] for item in sequence)
                            right = max(item["x"] + item["w"] for item in sequence)
                            bottom = max(item["y"] + item["h"] for item in sequence)
                            matches.append((left, top, right - left, bottom - top))

        # Remove duplicate highlight rectangles.
        unique = []
        seen = set()

        for left, top, width, height in matches:
            key = tuple(
                round(value, 6)
                for value in (left, top, width, height)
            )

            if key not in seen:
                seen.add(key)
                unique.append((left, top, width, height))

        return unique

    def _render_pixmap(self) -> QPixmap:
        viewport_width, viewport_height = self._viewport_size()
        if self.fit_mode:
            width = max(1, viewport_width)
            height = max(1, viewport_height)
        else:
            width = max(1, int(self.source_pixmap.width() * self.scale_factor))
            height = max(1, int(self.source_pixmap.height() * self.scale_factor))
        rendered = self.source_pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not self.highlight_enabled:
            return rendered
        matches = self.matching_boxes()
        if not matches:
            return rendered
        painter = QPainter(rendered)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fill = QColor(255, 209, 102, 110)
        border = QColor(255, 145, 0, 235)
        painter.setBrush(fill)
        painter.setPen(QPen(border, max(1, rendered.width() // 500)))
        for left, top, box_width, box_height in matches:
            painter.drawRoundedRect(
                QRectF(
                    left * rendered.width(),
                    top * rendered.height(),
                    box_width * rendered.width(),
                    box_height * rendered.height(),
                ),
                2,
                2,
            )
        painter.end()
        return rendered

    def scroll_to_first_match(self):
        if not self.highlight_enabled:
            return
        matches = self.matching_boxes()
        if not matches:
            self.match_label.setText("No match")
            return
        self.match_label.setText(
            f"{len(matches)} match" + ("es" if len(matches) != 1 else "")
        )
        left, top, _, _ = matches[0]
        rendered = self.image_label.pixmap()
        if rendered is None or rendered.isNull():
            return
        horizontal = self.scroll_area.horizontalScrollBar()
        vertical = self.scroll_area.verticalScrollBar()
        horizontal.setValue(int(left * rendered.width()) - horizontal.pageStep() // 2)
        vertical.setValue(int(top * rendered.height()) - vertical.pageStep() // 2)

    def showEvent(self, event):
        if self.fit_mode:
            self.fit_to_window()
        super().showEvent(event)

    def resizeEvent(self, event):
        if self.fit_mode:
            self.fit_to_window()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        if self.source_pixmap.isNull():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        self.manual_zoom(
            self.scale_factor * (self.ZOOM_STEP if delta > 0 else 1 / self.ZOOM_STEP)
        )
        event.accept()

    @staticmethod
    def _make_toolbar_button(name: str, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        button.setToolTip(tooltip)
        button.setFixedHeight(36)
        button.setMinimumWidth(56 if len(text) <= 3 else 92)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton { background: #2f3a49; color: #e6edf3; border: 1px solid #3d4b5c;"
            "border-radius: 4px; padding: 0px 12px; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background: #3a4757; border-color: #56646f; }"
            "QPushButton:disabled { color: #7d8794; background: #26303c; }"
        )
        return button

    def _viewport_size(self) -> tuple[int, int]:
        viewport = self.scroll_area.viewport()
        return viewport.width(), viewport.height()

    def apply_scale(self, scale: float, anchor_center: bool = True):
        if self.source_pixmap.isNull():
            return
        scale = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))
        self.scale_factor = scale
        self.image_label.setPixmap(self._render_pixmap())
        if anchor_center:
            horizontal = self.scroll_area.horizontalScrollBar()
            vertical = self.scroll_area.verticalScrollBar()
            horizontal.setValue(
                (horizontal.minimum() + horizontal.maximum()) // 2
            )
            vertical.setValue(
                (vertical.minimum() + vertical.maximum()) // 2
            )
        self._update_zoom_label()

    def _update_zoom_label(self):
        if self.fit_mode:
            viewport_width, _ = self._viewport_size()
            if self.source_pixmap.width():
                displayed = self.image_label.pixmap().width() if self.image_label.pixmap() else 0
                ratio = displayed / self.source_pixmap.width() if displayed else 1.0
                self.zoom_label.setText(f"Fit {ratio * 100:.0f}%")
                return
        self.zoom_label.setText(f"{self.scale_factor * 100:.0f}%")

    def zoom_in(self):
        self.manual_zoom(self.scale_factor * self.ZOOM_STEP)

    def zoom_out(self):
        self.manual_zoom(self.scale_factor / self.ZOOM_STEP)

    def manual_zoom(self, scale: float):
        self.fit_mode = False
        self.apply_scale(scale)

    def fit_to_window(self):
        self.fit_mode = True
        viewport_width, viewport_height = self._viewport_size()
        if not self.source_pixmap.width() or not self.source_pixmap.height():
            return
        self.scale_factor = min(
            viewport_width / self.source_pixmap.width(),
            viewport_height / self.source_pixmap.height(),
        )
        self.apply_scale(self.scale_factor)

    def actual_size(self):
        self.manual_zoom(1.0)

    @staticmethod
    def download_file(window, path: str):
        source = Path(path)
        if not source.is_file():
            return
        save_path, _ = QFileDialog.getSaveFileName(
            window,
            "Download Image",
            str(Path.home() / "Downloads" / source.name),
            "Images (*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp);;All Files (*)",
        )
        if not save_path:
            return
        if Path(save_path).suffix.lower() not in backend.IMAGE_EXTENSIONS:
            save_path = f"{save_path}{source.suffix.lower()}"
        try:
            shutil.copyfile(source, save_path)
        except OSError as error:
            window.statusBar().showMessage(f"Download failed: {error}", 5000)
            return
        window.statusBar().showMessage(f"Image downloaded to {save_path}", 6000)


class ClickableImageLabel(QLabel):
    def __init__(self, path: str, open_image):
        super().__init__()
        self.path = path
        self.open_image = open_image

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_image(self.path)
        super().mousePressEvent(event)


class SearchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.search_images)
        self.scan_in_progress = False
        self.search_generation = 0
        self.search_tasks = []
        self.pending_search_results = []
        self.search_result_total = 0
        self.search_result_count = 0
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self.update_footer_clock)
        self.preview_windows = []
        self.scan_loader = None
        self.setWindowTitle("Prakshal-Scanora")
        self.setWindowIcon(QIcon(logo_path()))
        self.resize(1050, 760)
        self.setMinimumSize(760, 560)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f4f5f6; color: #1f2430; }
            QFrame#panel { background: #ffffff; border: 1px solid #d7dade; }
            QLineEdit { background: #ffffff; border: 1px solid #c7ccd3;
                                                padding: 10px; border-radius: 3px; font-size: 15px; }
            QPushButton { background: #2f5d8a; color: white; border: 1px solid #2f5d8a;
                                                    padding: 11px 16px; min-height: 22px; border-radius: 3px;
                                                    font-size: 15px; font-weight: 600; }

            QPushButton:hover { background: #24486d; }
            QPushButton[secondary="true"] { background: #ffffff; color: #1f2430;
                                              border-color: #c7ccd3; font-weight: 500; }
            QPushButton[secondary="true"]:checked { background: #2f5d8a; color: #ffffff;
                                                     border-color: #2f5d8a; }
            QPushButton#viewImageButton { background-color: #2f7a4f;
                                            color: #ffffff;
                                            border: 1px solid #2f7a4f;
                                            border-radius: 4px;
                                            min-width: 116px;
                                            min-height: 36px;
                                            padding: 0px 14px;
                                            font-size: 14px;
                                            font-weight: 600; }
            QPushButton#viewImageButton:hover { background: #25633f; border-color: #25633f; }
            QPushButton#copyPathButton { background-color: #ffffff;
                                            color: #2f5d8a;
                                            border: 1px solid #9bb4ce;
                                            border-radius: 4px;
                                            min-width: 146px;
                                            min-height: 36px;
                                            padding: 0px 10px;
                                            font-size: 14px;
                                            font-weight: 600; }
            QPushButton#copyPathButton:hover { background: #edf4fb; border-color: #2f5d8a; }
            QPushButton#downloadImageButton { background-color: #2f5d8a;
                                               color: #ffffff;
                                               border: 1px solid #8a5a2f;
                                               border-radius: 4px;
                                               min-width: 146px;
                                               min-height: 36px;
                                               padding: 0px 10px;
                                               font-size: 14px;
                                               font-weight: 600; }
            QPushButton#downloadImageButton:hover { background: #005385; border-color: #6f4726; }
            QLabel#muted { color: #6b7280; }
            QLabel#success { color: #2f7a4f; }
            QLabel#error { color: #b3261e; }
        """)
        self._build_ui()
        self.load_status()
        self.search_images()

    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(14)

        scan_panel = self._panel("Build your image index", "Choose a folder to scan recursively")
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText(r"Example: C:\Users\You\Images")
        self.scan_button = QPushButton("Scan / Index Folder")
        self.scan_button.clicked.connect(lambda: self.start_scan(False))
        self.rescan_button = QPushButton("Re-scan Changed Files")
        self.rescan_button.setProperty("secondary", True)
        self.rescan_button.clicked.connect(lambda: self.start_scan(False))
        self.new_scan_button = QPushButton("New Folder Scan")
        self.new_scan_button.setProperty("secondary", True)
        self.new_scan_button.clicked.connect(self.select_new_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.scan_button)
        folder_row.addWidget(self.rescan_button)
        folder_row.addWidget(self.new_scan_button)
        scan_panel.layout().addLayout(folder_row)
        self.status_label = QLabel()
        self.status_label.setObjectName("muted")
        scan_panel.layout().addWidget(self.status_label)
        self.last_folder_label = QLabel()
        self.last_folder_label.setObjectName("muted")
        self.last_folder_label.setWordWrap(True)
        scan_panel.layout().addWidget(self.last_folder_label)
        outer.addWidget(scan_panel)

        search_panel = self._panel("Search your archive", "Search words, numbers, names, or IDs")
        search_row = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(
            'Try "exact phrase", a partial word, name AND year, or term OR alternative'
        )
        self.query_edit.setToolTip(
            'Use quotes for an exact phrase, AND to require terms, or OR for alternatives. '
            "Partial words, minor spelling errors, and common OCR number substitutions are also matched."
        )
        self.query_edit.textChanged.connect(self.schedule_search)
        self.query_edit.returnPressed.connect(self.search_images)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_images)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("secondary", True)
        self.clear_button.clicked.connect(self.clear_search)
        search_row.addWidget(self.query_edit, 1)
        search_row.addWidget(self.search_button)
        search_row.addWidget(self.clear_button)
        search_panel.layout().addLayout(search_row)
        filter_row = QHBoxLayout()
        self.filter_buttons = {}
        for label, field in (("All", "all"), ("Name", "name"), ("Year", "year"), ("Number", "number"), ("Date", "date")):
            filter_button = QPushButton(label)
            filter_button.setCheckable(True)
            filter_button.setProperty("secondary", True)
            filter_button.clicked.connect(lambda checked, value=field: self.set_search_field(value))
            filter_row.addWidget(filter_button)
            self.filter_buttons[field] = filter_button
        self.filter_buttons["all"].setChecked(True)
        filter_row.addStretch(1)
        filter_row.addWidget(QLabel("Sort"))
        self.sort_box = QComboBox()
        for label, value in (
            ("Relevance", "relevance"),
            ("Name A-Z", "name"),
            ("Newest first", "newest"),
            ("Oldest first", "oldest"),
        ):
            self.sort_box.addItem(label, value)
        self.sort_box.setToolTip("Order of the search results")
        self.sort_box.currentIndexChanged.connect(self.schedule_search)
        filter_row.addWidget(self.sort_box)
        search_panel.layout().addLayout(filter_row)

        self.result_count = QLabel()
        self.result_count.setObjectName("muted")
        search_panel.layout().addWidget(self.result_count)
        self.results = QListWidget()
        self.results.setFrameShape(QFrame.Shape.NoFrame)
        self.results.setSpacing(8)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        search_panel.layout().addWidget(self.results, 1)
        outer.addWidget(search_panel, 1)
        self.setCentralWidget(central)
        self.footer = QLabel()
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setStyleSheet("""
            QLabel {

                color: #666666;
                font-size: 11px;
                padding: 8px;
            }
        """)
        outer.addWidget(self.footer)
        self.update_footer_clock()
        self.clock_timer.start()

    def update_footer_clock(self):
        mumbai_timezone = timezone(timedelta(hours=5, minutes=30), name="IST")
        current_time = datetime.now(mumbai_timezone)
        self.footer.setText(
            f"Powered by Prakshal Infotech Pvt. Ltd.  \t\t Time: "
            f"{current_time:%Y-%m-%d %H:%M:%S} IST"
        )

    @staticmethod
    def _panel(title: str, subtitle: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 16)
        heading = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("muted")
        heading.addWidget(title_label)
        heading.addWidget(subtitle_label)
        heading.addStretch(1)
        layout.addLayout(heading)
        return panel

    @staticmethod
    def _format_scan_time(value: str | None) -> str:
        if not value:
            return "date: unavailable\ntime: unavailable"
        try:
            scan_time = datetime.fromisoformat(value)
        except ValueError:
            return "date: unavailable\ntime: unavailable"
        return f"date: {scan_time:%Y-%m-%d}\ntime: {scan_time:%H:%M:%S}"

    def load_status(self):
        status = backend.status()
        last_folder = status.get("last_scan_folder")
        last_scan_time = status.get("last_scan_time")
        if last_folder:
            self.folder_edit.setText(last_folder)
            self.last_folder_label.setText(
                f"Last scanned folder: {last_folder}\n"
                f"Last scanned:\n{self._format_scan_time(last_scan_time)}"
            )
        else:
            self.last_folder_label.setText(
                "Last scanned folder: None\n"
                "Last scanned: date: unavailable\ntime: unavailable"
            )
        if status["ocr_available"]:
            self.status_label.setObjectName("success")
            self.status_label.setText("OCR ready · Select a folder to begin")
        else:
            self.status_label.setObjectName("error")
            self.status_label.setText(status["ocr_error"] or "OCR is not available.")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def start_scan(self, force_ocr: bool):
        if self.scan_in_progress:
            return
        folder = self.folder_edit.text().strip()
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "Select folder to scan")
            if not folder:
                return
            self.folder_edit.setText(folder)
        self.scan_in_progress = True
        self.search_timer.stop()
        self.search_generation += 1
        self.pending_search_results = []
        self.results.clear()
        self.result_count.setText("Waiting for the complete folder scan…")
        self.folder_edit.setEnabled(False)
        self._set_search_controls_enabled(False)
        self.scan_button.setEnabled(False)
        self.rescan_button.setEnabled(False)
        self.new_scan_button.setEnabled(False)
        self.status_label.setObjectName("muted")
        self.status_label.setText("Preparing folder scan...")
        self._show_loader(f"Scanning {Path(folder).name or folder}...")
        task = ScanTask(folder, force_ocr)
        task.signals.finished.connect(self.scan_finished)
        task.signals.failed.connect(self.scan_failed)
        task.signals.progress.connect(self.scan_progress)
        self.scan_loader.repaint()
        self.thread_pool.start(task)

    def select_new_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select a new folder",
            self.folder_edit.text().strip(),
        )
        if not folder:
            return

        self.search_timer.stop()
        self.search_generation += 1
        self.pending_search_results = []
        self.query_edit.blockSignals(True)
        self.query_edit.clear()
        self.query_edit.blockSignals(False)
        self.results.clear()
        self.result_count.setText("Preparing selected folder…")
        self.folder_edit.setText(folder)
        self.start_scan(False)

    def _show_loader(self, message: str):
        self.scan_loader = AppLoader(message)
        self.scan_loader.center_on(self)
        self.scan_loader.show()
        self.scan_loader.raise_()
        self.scan_loader.activateWindow()
        QApplication.processEvents()

    def _hide_loader(self):
        if self.scan_loader is not None:
            self.scan_loader.close()
            self.scan_loader.deleteLater()
            self.scan_loader = None

    def _set_search_controls_enabled(self, enabled: bool):
        self.folder_edit.setEnabled(enabled)
        self.query_edit.setEnabled(enabled)
        self.search_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.sort_box.setEnabled(enabled)
        for button in self.filter_buttons.values():
            button.setEnabled(enabled)

    def scan_progress(self, progress: dict):
        folder_name = Path(progress["folder"]).name or progress["folder"]
        total_pending = progress.get("total_pending", progress["total_files"])
        if progress.get("phase") == "ready":
            self.status_label.setObjectName("muted")
            self.status_label.setText(
                f"Found {progress['total_files']} files in {progress['folders']} folders. "
                "Completing the full scan before enabling search."
            )
            if self.scan_loader is not None:
                self.scan_loader.set_message(
                    f"Found {progress['total_files']} files. "
                    "Completing full text extraction before search..."
                )
            return

        message = (
            f"Scanning {folder_name} | folders: {progress['folders']} | "
            f"files: {progress['scanned']}/{total_pending} to scan "
            f"({progress['total_files']} found) | "
            f"remaining: {progress['remaining']}"
        )
        self.status_label.setText(message)
        if self.scan_loader is not None:
            self.scan_loader.set_message(message)
    def scan_finished(self, result: dict):
        self.scan_in_progress = False
        self._hide_loader()
        self.scan_button.setEnabled(True)
        self.rescan_button.setEnabled(True)
        self.new_scan_button.setEnabled(True)
        self._set_search_controls_enabled(True)
        self.status_label.setObjectName("success")
        if result["pending"]:
            scan_message = (
                f"Done. Scanned {result['indexed']} new or changed files; "
                f"skipped {result['skipped']} unchanged files. "
                f"Folders: {result['folders']}. Folder total: {result['found']} files."
            )
        else:
            scan_message = (
                f"Done. All {result['found']} files were already scanned; "
                f"no OCR was repeated. Folders: {result['folders']}."
            )
        if result.get("pdf_errors"):
            scan_message += (
                f" Could not read or OCR {len(result['pdf_errors'])} PDF file(s)."
            )
        if result.get("image_errors"):
            self.status_label.setObjectName("error")
            scan_message += (
                f" Could not extract searchable text from "
                f"{len(result['image_errors'])} image(s); they will be retried "
                "on the next scan."
            )
        self.status_label.setText(scan_message)
        last_scan_time = backend.status().get("last_scan_time")
        self.last_folder_label.setText(
            f"Last scanned folder: {self.folder_edit.text().strip()}\n"
            f"Last scanned:\n{self._format_scan_time(last_scan_time)}"
        )
        self.search_images()

    def scan_failed(self, error: str):
        self.scan_in_progress = False
        self._hide_loader()
        self.scan_button.setEnabled(True)
        self.rescan_button.setEnabled(True)
        self.new_scan_button.setEnabled(True)
        self._set_search_controls_enabled(True)
        self.status_label.setObjectName("error")
        self.status_label.setText(error)

    def search_images(self):
        if self.scan_in_progress:
            return
        folder = self.folder_edit.text().strip()
        if not folder:
            self.search_generation += 1
            self.pending_search_results = []
            self.results.clear()
            self.result_count.setText("Select and scan a folder to view images")
            return

        self.search_generation += 1
        generation = self.search_generation
        query = self.query_edit.text().strip()
        self.pending_search_results = []
        self.results.clear()
        task = SearchTask(
            generation,
            q=query,
            folder=folder,
            field=self.current_search_field(),
            sort=self.current_sort(),
            limit=500,
        )
        task.signals.finished.connect(self.search_finished)
        task.signals.failed.connect(self.search_failed)
        self.search_tasks.append(task)
        self.result_count.setText("Searching…")
        self.thread_pool.start(task)

    def search_finished(self, generation: int, data: dict):
        self.search_tasks = [task for task in self.search_tasks if task.generation != generation]
        # Ignore old results when the user has continued typing.
        if generation != self.search_generation:
            return
        self.results.clear()
        self.search_result_count = data["count"]
        self.search_result_total = len(data["results"])
        self.pending_search_results = list(data["results"])
        if self.pending_search_results:
            QTimer.singleShot(0, lambda: self._render_search_batch(generation))
        else:
            self._set_search_result_message()

    def _render_search_batch(self, generation: int):
        if generation != self.search_generation:
            return
        batch_size = 10
        batch = self.pending_search_results[:batch_size]
        del self.pending_search_results[:batch_size]
        for result in batch:
            self._add_result(result)
        if self.pending_search_results:
            loaded = self.results.count()
            self.result_count.setText(
                f"Loading results… {loaded} of {self.search_result_total}"
            )
            QTimer.singleShot(1, lambda: self._render_search_batch(generation))
        else:
            self._set_search_result_message()

    def _set_search_result_message(self):
        if self.query_edit.text().strip():
            message = f"{self.search_result_count} matching files"
        else:
            message = f"{self.search_result_count} files in this folder"
        if self.search_result_total < self.search_result_count:
            message += f" (showing best {self.search_result_total})"
        self.result_count.setText(message)

    def search_failed(self, generation: int, error: str):
        self.search_tasks = [task for task in self.search_tasks if task.generation != generation]
        if generation == self.search_generation:
            self.result_count.setText(f"Search failed: {error}")

    def current_search_field(self):
        for field, button in self.filter_buttons.items():
            if button.isChecked():
                return field
        return "all"

    def current_sort(self) -> str:
        return self.sort_box.currentData()

    def _highlight_html(self, value: str) -> str:
        """Escape text and wrap every search term in a highlight span."""
        query = self.query_edit.text().strip()
        if not query:
            return escape_html(value)
        terms = sorted(
            set(backend.search_highlight_terms(query)),
            key=len,
            reverse=True,
        )
        if not terms:
            return escape_html(value)

        parts = []
        position = 0
        for match in re.finditer(r"[a-z0-9]+(?:[.,][0-9]+)*", value, re.IGNORECASE):
            if not any(backend.search_term_matches(term, match.group()) for term in terms):
                continue
            parts.append(escape_html(value[position:match.start()]))
            parts.append(
                '<span style="background-color:#ffe08a; font-weight:600;">'
                f"{escape_html(match.group())}</span>"
            )
            position = match.end()
        parts.append(escape_html(value[position:]))
        return "".join(parts)

    def set_search_field(self, field):
        for name, button in self.filter_buttons.items():
            button.setChecked(name == field)
        self.schedule_search()

    def schedule_search(self):
        if self.scan_in_progress:
            return
        if not self.query_edit.text().strip():
            self.search_timer.stop()
            self.search_images()
            return
        # Numeric identifiers are often typed in several keystrokes (including
        # leading zeroes). Wait for an explicit submit instead of searching
        # partial values such as "0" and "00" along the way.
        if self.current_search_field() == "number" and self.query_edit.text().strip().isdigit():
            self.search_timer.stop()
            self.result_count.setText("Finish entering the number, then press Enter or Search")
            return
        self.search_timer.start()

    def _add_result(self, result: dict):
        item = QListWidgetItem(self.results)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 8, 8, 8)
        query = self.query_edit.text().strip()
        is_pdf = Path(result["path"]).suffix.casefold() == ".pdf"
        matched_in = result.get("matched_in", [])
        image_query = query
        thumbnail = ClickableImageLabel(
            result["path"], lambda path: self.open_result(path, image_query)
        )
        thumbnail.setFixedSize(136, 96)
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail.setCursor(Qt.CursorShape.PointingHandCursor)
        thumbnail.setToolTip("Open PDF" if is_pdf else "Open image")
        thumbnail.setStyleSheet("background: #eef1f4; border: 1px solid #d7dade;")
        if is_pdf:
            thumbnail.setText("PDF")
            thumbnail.setStyleSheet(
                "background: #eef1f4; border: 1px solid #d7dade;"
                "color: #b42318; font-size: 20px; font-weight: 700;"
            )
        else:
            image_reader = QImageReader(result["path"])
            image_size = image_reader.size()
            if image_size.isValid():
                image_reader.setScaledSize(
                    image_size.scaled(
                        thumbnail.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                    )
                )
            image = image_reader.read()
            if not image.isNull():
                thumbnail.setPixmap(QPixmap.fromImage(image))
        layout.addWidget(thumbnail)
        details = QVBoxLayout()
        name = QLabel(self._highlight_html(result["filename"]))
        name.setStyleSheet("font-weight: 600;")
        name.setTextFormat(Qt.TextFormat.RichText)
        name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        folder = QLabel(escape_html(result["folder"]))
        folder.setObjectName("muted")

        folder.setWordWrap(True)
        details.addWidget(name)
        details.addWidget(folder)
        if matched_in:
            match_label = QLabel("Matched in: " + ", ".join(matched_in))
            match_label.setObjectName("success" if "OCR text" in matched_in else "muted")
            details.addWidget(match_label)
        snippet = result.get("snippet") or result.get("match_snippet")
        if snippet:
            snippet_label = QLabel(
                escape_html("OCR match: ") + self._highlight_html(str(snippet))
            )
            snippet_label.setTextFormat(Qt.TextFormat.RichText)
            snippet_label.setWordWrap(True)
            details.addWidget(snippet_label)
        elif not matched_in:
            ocr_preview = result.get("text") or "No OCR text stored."
            if len(ocr_preview) > 160:
                ocr_preview = ocr_preview[:157] + "…"
            preview_label = QLabel(self._highlight_html(str(ocr_preview)))
            preview_label.setTextFormat(Qt.TextFormat.RichText)
            preview_label.setWordWrap(True)
            details.addWidget(preview_label)
        actions = QHBoxLayout()
        view_button = QPushButton("Open PDF" if is_pdf else "View Image")
        view_button.setObjectName("viewImageButton")
        view_button.setMinimumHeight(36)
        view_button.setToolTip("Open this PDF" if is_pdf else "Open this image in a larger window")
        view_button.clicked.connect(lambda: self.open_result(result["path"], image_query))
        path_button = QPushButton("Copy File Path")
        path_button.setObjectName("copyPathButton")
        path_button.setMinimumHeight(36)
        path_button.setProperty("secondary", True)
        path_button.setToolTip("Copy the file path")
        path_button.clicked.connect(lambda: self.copy_path(result["path"]))
        download_button = QPushButton("Download File")
        download_button.setObjectName("downloadImageButton")
        download_button.setMinimumHeight(36)
        download_button.setToolTip("Save a copy of this file to your computer")
        download_button.clicked.connect(lambda: self.download_image(result["path"]))
        actions.addWidget(view_button)
        actions.addWidget(path_button)
        actions.addWidget(download_button)
        actions.addStretch(1)
        details.addLayout(actions)
        layout.addLayout(details, 1)
        layout.activate()
        item.setSizeHint(QSize(0, max(140, row.sizeHint().height() + 8)))
        self.results.setItemWidget(item, row)

    def view_image(self, path: str, query: str | None = None):
        preview = ImagePreview(
            path,
            self.query_edit.text().strip() if query is None else query,
        )
        preview.show()
        self.preview_windows.append(preview)

    def open_result(self, path: str, query: str | None = None):
        if Path(path).suffix.casefold() == ".pdf":
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                self.status_label.setObjectName("error")
                self.status_label.setText("Could not open this PDF in the system viewer.")
            return
        self.view_image(path, query)

    def copy_path(self, path: str):
        QApplication.clipboard().setText(path)
        self.status_label.setText("File path copied to the clipboard.")

    def download_image(self, path: str):
        source = Path(path)
        if not source.is_file():
            self.status_label.setObjectName("error")
            self.status_label.setText("This file is no longer available on disk.")
            return
        suggested_name = source.name
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download File",
            str(Path.home() / "Downloads" / suggested_name),
            "Supported Files (*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp *.pdf);;All Files (*)",
        )
        if not save_path:
            self.status_label.setObjectName("muted")
            self.status_label.setText("Download cancelled.")
            return
        if Path(save_path).suffix.lower() not in backend.SUPPORTED_EXTENSIONS:
            save_path = f"{save_path}{source.suffix.lower()}"
        try:
            shutil.copyfile(source, save_path)
        except OSError as error:
            self.status_label.setObjectName("error")
            self.status_label.setText(f"Download failed: {error}")
            return
        self.status_label.setObjectName("success")
        self.status_label.setText(f"File downloaded to {save_path}")

    def clear_search(self):
        self.search_timer.stop()
        self.search_generation += 1
        self.pending_search_results = []
        self.query_edit.blockSignals(True)
        self.query_edit.clear()
        self.query_edit.blockSignals(False)
        self.search_images()

    def closeEvent(self, event):
        self._hide_loader()
        super().closeEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange or self.scan_loader is None:
            return
        if self.isMinimized():
            self.scan_loader.hide()
        elif self.isVisible():
            self.scan_loader.center_on(self)
            self.scan_loader.show()


def run_desktop():
    app = QApplication(sys.argv)
    app.setApplicationName("Prakshal-Scanora Search")
    app.setWindowIcon(QIcon(logo_path()))

    if not ensure_licence():
        return 0

    splash = AppLoader("Preparing your image index...")
    splash.center_on_screen()
    splash.show()
    app.processEvents()

    window = SearchWindow()
    window.show()

    splash.close()
    return app.exec()
