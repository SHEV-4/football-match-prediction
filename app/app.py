import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QPushButton, QTextEdit, QLineEdit,QHBoxLayout
)
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QDateEdit, QDialogButtonBox, QFileDialog
from PySide6.QtCore import QDate
import scraper

def format_range(date_from, date_to):
    same_month = date_from.month() == date_to.month()
    same_year = date_from.year() == date_to.year()

    if same_month and same_year:
        return f"{date_from.day()} - {date_to.day()} {date_from.toString('MMM yyyy')}"
    elif same_year:
        return (
            f"{date_from.day()} {date_from.toString('MMM')} - "
            f"{date_to.day()} {date_to.toString('MMM yyyy')}"
        )
    else:
        return (
            f"{date_from.day()} {date_from.toString('MMM yyyy')} - "
            f"{date_to.day()} {date_to.toString('MMM yyyy')}"
        )

class WeekRangeDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Вибір діапазону")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Від:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate())
        layout.addWidget(self.date_from)

        layout.addWidget(QLabel("До:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate().addDays(6))
        layout.addWidget(self.date_to)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_range(self):
        return self.date_from.date(), self.date_to.date()

# --- Потік для парсера ---
class ParserThread(QThread):
    finished = Signal(str)
    progress = Signal(str)   # ← НОВИЙ сигнал

    def __init__(self, mode, week=None, folder=None):
        super().__init__()
        self.mode = mode
        self.week = week
        self.folder = folder

    def log(self, text):
        self.progress.emit(text)   # зручний хелпер

    def run(self):
        try:
            if self.mode == "teams":
                result = parser.parse_team_results(
                    self.folder,
                    logger=self.log     # ← передаємо логер
                )

            elif self.mode == "last_week":
                result = parser.parse_last_week_matches(
                    self.folder,
                    logger=self.log
                )

            elif self.mode == "by_week":
                result = parser.parse_matches_by_week(
                    self.folder,
                    self.week,
                    logger=self.log
                )

            else:
                result = "Невідомий режим"

            self.finished.emit("Готово")

        except Exception as e:
            self.finished.emit(f"Помилка: {e}")


# --- Головне вікно ---
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Парсер матчів")
        self.resize(500, 600)

        layout = QVBoxLayout()

        self.log = QTextEdit()
        self.log.setReadOnly(True)


        btn_teams = QPushButton("Результати команд")
        btn_last_week = QPushButton("Результати матчів за минулий тиждень")
        btn_by_week = QPushButton("Результати матчів за конкретний тиждень")
        folder_layout = QHBoxLayout()

        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)

        btn_folder = QPushButton("Вибрати папку")
        btn_folder.clicked.connect(self.select_folder)

        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(btn_folder)

        layout.addLayout(folder_layout)
        btn_teams.clicked.connect(self.run_teams)
        btn_last_week.clicked.connect(self.run_last_week)
        btn_by_week.clicked.connect(self.run_by_week)

        layout.addWidget(btn_teams)
        layout.addWidget(btn_last_week)
        layout.addWidget(btn_by_week)
        layout.addWidget(self.log)


        self.setLayout(layout)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Виберіть папку")
        if folder:
            self.selected_folder = folder
            self.folder_edit.setText(folder)

    def start_thread(self, mode, week=None):
        if not hasattr(self, "selected_folder"):
            self.log.append("⚠️ Спочатку виберіть папку")
            return

        self.log.append("⏳ Запуск парсера...")

        self.thread = ParserThread(mode, week, self.selected_folder)

        self.thread.progress.connect(self.on_progress)   # ← НОВЕ
        self.thread.finished.connect(self.on_finished)

        self.thread.start()

    def on_progress(self, text):
        self.log.append(text)

    def on_finished(self, text):
        self.log.append(f"✅ {text}")

    def run_teams(self):
        self.start_thread("teams")

    def run_last_week(self):
        self.start_thread("last_week")

    def run_by_week(self):
        dialog = WeekRangeDialog()
        if dialog.exec():
            date_from, date_to = dialog.get_range()
            formatted = format_range(date_from, date_to)

            self.log.append(f"📅 Обрано: {formatted}")
            self.start_thread("by_week", formatted)



app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
