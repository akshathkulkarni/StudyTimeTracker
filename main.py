from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtGui import QAction, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from db import (
    StudyEntry,
    delete_entries_for_date,
    fetch_entries,
    init_db,
    insert_entries,
)

CATEGORY_OPTIONS = [
    "GenAI",
    "Operating Systems",
    "Digital Electronics and Logic Design",
]


def minutes_between(start_str: str, end_str: str) -> int:
    start = datetime.strptime(start_str, "%H:%M")
    end = datetime.strptime(end_str, "%H:%M")
    if end < start:
        end += timedelta(days=1)
    return int((end - start).total_seconds() // 60)


class StudyLoggerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        init_db()
        self.setWindowTitle("Study Logging System")
        self.resize(900, 520)
        self._setup_palette()
        self._build_ui()
        self.load_entries_for_date()

    def _setup_palette(self) -> None:
        palette = self.palette()
        base = QColor("#101218")
        card = QColor("#1b1e27")
        text = QColor("#f5f7fb")
        accent = QColor("#4f8cff")
        palette.setColor(QPalette.Window, base)
        palette.setColor(QPalette.Base, card)
        palette.setColor(QPalette.AlternateBase, card.darker(108))
        palette.setColor(QPalette.Text, text)
        palette.setColor(QPalette.ButtonText, text)
        palette.setColor(QPalette.WindowText, text)
        palette.setColor(QPalette.Highlight, accent)
        palette.setColor(QPalette.Button, card)
        self.setPalette(palette)

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout()
        central.setLayout(layout)

        # Top bar
        top = QHBoxLayout()
        date_label = QLabel("Date:")
        self.date_picker = QDateEdit()
        self.date_picker.setDisplayFormat("yyyy-MM-dd")
        self.date_picker.setCalendarPopup(True)
        self.date_picker.dateChanged.connect(self.load_entries_for_date)

        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self.add_empty_row)

        remove_row_btn = QPushButton("Remove Selected")
        remove_row_btn.clicked.connect(self.remove_selected_row)

        top.addWidget(date_label)
        top.addWidget(self.date_picker)
        top.addStretch()
        top.addWidget(add_row_btn)
        top.addWidget(remove_row_btn)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["From", "To", "Category", "Duration", "Notes"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        # Buttons and total
        bottom_layout = QHBoxLayout()
        self.total_label = QLabel("Total: 0h 0m")
        save_btn = QPushButton("Save Day")
        save_btn.clicked.connect(self.save_entries)
        bottom_layout.addWidget(self.total_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(save_btn)

        layout.addLayout(top)
        layout.addWidget(self.table)
        layout.addLayout(bottom_layout)
        self.setCentralWidget(central)

        self._add_menu()

        # Set default date after all widgets exist to avoid early signal firing
        self.date_picker.blockSignals(True)
        self.date_picker.setDate(QDate.currentDate())
        self.date_picker.blockSignals(False)

    def _add_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        export_action = QAction("Export (Coming soon)", self)
        export_action.setEnabled(False)
        file_menu.addAction(export_action)

    def add_empty_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        start_item = QTableWidgetItem("")
        end_item = QTableWidgetItem("")
        category_widget = QComboBox()
        category_widget.addItems(CATEGORY_OPTIONS)
        duration_item = QTableWidgetItem("—")
        duration_item.setFlags(Qt.ItemIsEnabled)
        notes_item = QTableWidgetItem("")

        for column, widget in enumerate(
            (start_item, end_item, category_widget, duration_item, notes_item)
        ):
            if isinstance(widget, QTableWidgetItem):
                self.table.setItem(row, column, widget)
            else:
                self.table.setCellWidget(row, column, widget)

        self.table.itemChanged.connect(self._on_time_changed)
        self._update_duration_for_row(row)

    def remove_selected_row(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        for model_index in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.table.removeRow(model_index.row())
        self.update_total_label()

    def _on_time_changed(self, item: QTableWidgetItem) -> None:
        if item.column() not in (0, 1):  # From / To
            return
        self._update_duration_for_row(item.row())

    def _update_duration_for_row(self, row: int) -> None:
        start_item = self.table.item(row, 0)
        end_item = self.table.item(row, 1)
        duration_item = self.table.item(row, 3)
        if not (start_item and end_item and duration_item):
            return
        start_text = start_item.text().strip()
        end_text = end_item.text().strip()
        try:
            minutes = minutes_between(start_text, end_text)
            duration_item.setText(self._format_minutes(minutes))
        except ValueError:
            duration_item.setText("—")
        self.update_total_label()

    def _format_minutes(self, minutes: int) -> str:
        hours = minutes // 60
        mins = minutes % 60
        if hours:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def update_total_label(self) -> None:
        total = 0
        for row in range(self.table.rowCount()):
            duration_item = self.table.item(row, 3)
            if duration_item:
                text = duration_item.text()
                total += self._parse_duration_text(text)
        hours = total // 60
        mins = total % 60
        self.total_label.setText(f"Total: {hours}h {mins}m")

    def _parse_duration_text(self, text: str) -> int:
        if text == "—" or not text:
            return 0
        parts = text.replace("h", "").replace("m", "").split()
        if len(parts) == 2:
            hours, mins = parts
        else:
            hours, mins = "0", parts[0]
        return int(hours) * 60 + int(mins)

    def collect_entries(self) -> Tuple[List[StudyEntry], List[str]]:
        errors: List[str] = []
        entries: List[StudyEntry] = []
        date_iso = self.date_picker.date().toString("yyyy-MM-dd")
        for row in range(self.table.rowCount()):
            start_item = self.table.item(row, 0)
            end_item = self.table.item(row, 1)
            category_widget = self.table.cellWidget(row, 2)
            if not (start_item and end_item and isinstance(category_widget, QComboBox)):
                continue
            start = start_item.text().strip()
            end = end_item.text().strip()
            category = category_widget.currentText() or "Other"
            try:
                duration_min = minutes_between(start, end)
            except ValueError:
                errors.append(f"Row {row + 1}: invalid time format (use HH:MM).")
                continue
            entries.append(
                StudyEntry(
                    date_iso=date_iso,
                    start_time=start,
                    end_time=end,
                    category=category,
                    duration_minutes=duration_min,
                )
            )
        return entries, errors

    def save_entries(self) -> None:
        entries, errors = self.collect_entries()
        if errors:
            QMessageBox.warning(self, "Validation errors", "\n".join(errors))
            return
        if not entries:
            QMessageBox.information(self, "Nothing to save", "No rows to save.")
            return
        date_iso = self.date_picker.date().toString("yyyy-MM-dd")
        delete_entries_for_date(date_iso)
        insert_entries(entries)
        QMessageBox.information(self, "Saved", "Entries saved to database.")

    def load_entries_for_date(self) -> None:
        date_iso = self.date_picker.date().toString("yyyy-MM-dd")
        entries = fetch_entries(date_iso)
        self.table.setRowCount(0)
        for entry in entries:
            self._append_entry(entry)
        if not entries:
            self.add_empty_row()
        self.update_total_label()

    def _append_entry(self, entry: StudyEntry) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(entry.start_time))
        self.table.setItem(row, 1, QTableWidgetItem(entry.end_time))

        category_widget = QComboBox()
        category_widget.addItems(CATEGORY_OPTIONS)
        if entry.category in CATEGORY_OPTIONS:
            category_widget.setCurrentText(entry.category)
        else:
            category_widget.setEditText(entry.category)
        self.table.setCellWidget(row, 2, category_widget)

        duration_item = QTableWidgetItem(self._format_minutes(entry.duration_minutes))
        duration_item.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(row, 3, duration_item)

        notes_item = QTableWidgetItem("")
        self.table.setItem(row, 4, notes_item)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = StudyLoggerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

