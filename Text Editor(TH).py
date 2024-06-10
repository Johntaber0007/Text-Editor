import sys
import re
import os
import shutil
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QTextEdit, QPushButton, QFileDialog, QLabel, QLineEdit, QCheckBox, 
    QRadioButton, QButtonGroup, QMessageBox, QTabWidget, QComboBox, QToolBar, QDialog, QTabBar
)
from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtGui import QFont, QTextCursor, QTextDocument, QIcon, QAction, QTextCharFormat
import chardet
import pythainlp
from pythainlp.tokenize import word_tokenize

class FindReplaceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.target_tab = self.parent.tabs.currentWidget()
        self.setWindowTitle("ค้นหา & แทนที่")

        find_label = QLabel("ค้นหา:")
        self.find_edit = QLineEdit()

        replace_label = QLabel("แทนที่ด้วย:")
        self.replace_edit = QLineEdit()

        self.direction_group = QButtonGroup()
        self.forward_radio = QRadioButton("ไปข้างหน้า")
        self.forward_radio.setChecked(True)
        self.backward_radio = QRadioButton("ย้อนกลับ")
        self.direction_group.addButton(self.forward_radio)
        self.direction_group.addButton(self.backward_radio)

        self.match_case_checkbox = QCheckBox("ตรงกับทั้งคำเท่านั้น")
        self.wrap_around_checkbox = QCheckBox("Wrap around")
        self.wrap_around_checkbox.setChecked(True)

        self.search_mode_group = QButtonGroup()
        self.normal_radio = QRadioButton("ธรรมดา")
        self.normal_radio.setChecked(True)
        self.extended_radio = QRadioButton("Extended (\\n, \\r, \\t, \\0, \\x...)")
        self.regex_radio = QRadioButton("Regular expression")
        self.search_mode_group.addButton(self.normal_radio)
        self.search_mode_group.addButton(self.extended_radio)
        self.search_mode_group.addButton(self.regex_radio)

        find_button = QPushButton("ค้นหาถัดไป")
        find_button.clicked.connect(self.find)
        replace_button = QPushButton("แทนที่")
        replace_button.clicked.connect(self.replace)
        replace_all_button = QPushButton("แทนที่ทั้งหมด")
        replace_all_button.clicked.connect(self.replace_all)
        close_button = QPushButton("ปิด")
        close_button.clicked.connect(self.close)

        layout = QVBoxLayout()
        layout.addWidget(find_label)
        layout.addWidget(self.find_edit)
        layout.addWidget(replace_label)
        layout.addWidget(self.replace_edit)

        direction_layout = QHBoxLayout()
        direction_layout.addWidget(self.forward_radio)
        direction_layout.addWidget(self.backward_radio)
        layout.addLayout(direction_layout)

        layout.addWidget(self.match_case_checkbox)
        layout.addWidget(self.wrap_around_checkbox)

        layout.addWidget(QLabel("โหมดการค้นหา:"))
        layout.addWidget(self.normal_radio)
        layout.addWidget(self.extended_radio)
        layout.addWidget(self.regex_radio)

        button_layout = QHBoxLayout()
        button_layout.addWidget(find_button)
        button_layout.addWidget(replace_button)
        button_layout.addWidget(replace_all_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def find(self):
        current_tab = self.parent.tabs.currentWidget()
        if current_tab is None:
            return

        text_to_find = self.find_edit.text()
        if not text_to_find:
            return

        match_case = self.match_case_checkbox.isChecked()
        wrap_around = self.wrap_around_checkbox.isChecked()
        search_forward = self.forward_radio.isChecked()

        cursor = current_tab.target_text_area.textCursor()
        if not cursor.hasSelection():
            if search_forward:
                cursor.movePosition(QTextCursor.Start)
            else:
                cursor.movePosition(QTextCursor.End)

        find_flags = QTextDocument.FindFlags(0)
        if not search_forward:
            find_flags |= QTextDocument.FindBackward

        if self.regex_radio.isChecked():
            pattern = QRegularExpression(text_to_find)
            if match_case:
                pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        else:
            pattern = text_to_find
            if match_case and self.normal_radio.isChecked():
                find_flags |= QTextDocument.FindCaseSensitively | QTextDocument.FindWholeWords 
            elif match_case:
                find_flags |= QTextDocument.FindCaseSensitively

        found_cursor = current_tab.target_text_area.document().find(pattern, cursor, find_flags)

        if found_cursor.isNull() and wrap_around:
            if search_forward:
                found_cursor = current_tab.target_text_area.document().find(
                    pattern, QTextCursor(current_tab.target_text_area.document()), find_flags
                )
            else:
                found_cursor = current_tab.target_text_area.document().find(
                    pattern,
                    QTextCursor(current_tab.target_text_area.document()),
                    find_flags | QTextDocument.FindBackward,
                )

        if not found_cursor.isNull():
            current_tab.target_text_area.setTextCursor(found_cursor)
        else:
            QMessageBox.information(self, "Find", f"ไม่พบข้อความ '{text_to_find}'")

    def replace(self):
        current_tab = self.parent.tabs.currentWidget()
        if current_tab is None:
            return

        text_to_find = self.find_edit.text()
        text_to_replace = self.replace_edit.text()
        if not text_to_find:
            return

        match_case = self.match_case_checkbox.isChecked()
        wrap_around = self.wrap_around_checkbox.isChecked()
        search_forward = self.forward_radio.isChecked()

        cursor = current_tab.target_text_area.textCursor()

        if self.regex_radio.isChecked():
            pattern = QRegularExpression(text_to_find)
            if match_case:
                pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
            find_flags = QTextDocument.FindFlags(0)
        else:
            pattern = text_to_find
            find_flags = QTextDocument.FindFlags(0)
            if not search_forward:
                find_flags |= QTextDocument.FindBackward
            if match_case and self.normal_radio.isChecked():
                find_flags |= QTextDocument.FindCaseSensitively | QTextDocument.FindWholeWords 
            elif match_case:
                find_flags |= QTextDocument.FindCaseSensitively

        if cursor.hasSelection() and (self.regex_radio.isChecked() or cursor.selectedText() == text_to_find):
            cursor.removeSelectedText()
            cursor.insertText(text_to_replace)

        found_cursor = current_tab.target_text_area.document().find(pattern, cursor, find_flags)
        if found_cursor.isNull() and wrap_around:
            if search_forward:
                found_cursor = current_tab.target_text_area.document().find(
                    pattern, QTextCursor(current_tab.target_text_area.document()), find_flags
                )
            else:
                found_cursor = current_tab.target_text_area.document().find(
                    pattern,
                    QTextCursor(current_tab.target_text_area.document()),
                    find_flags | QTextDocument.FindBackward,
                )

        if not found_cursor.isNull():
            current_tab.target_text_area.setTextCursor(found_cursor)

    def replace_all(self):
        current_tab = self.parent.tabs.currentWidget()
        if current_tab is None:
            return

        text_to_find = self.find_edit.text()
        text_to_replace = self.replace_edit.text()
        if not text_to_find:
            return

        match_case = self.match_case_checkbox.isChecked()
        document = current_tab.target_text_area.document()
        cursor = QTextCursor(document)

        if self.regex_radio.isChecked():
            pattern = QRegularExpression(text_to_find)
            if match_case:
                pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        else:
            if match_case and self.normal_radio.isChecked():
                pattern = text_to_find
                find_flags = QTextDocument.FindFlags(QTextDocument.FindWholeWords) | QTextDocument.FindCaseSensitively
            elif match_case:
                pattern = text_to_find
                find_flags = QTextDocument.FindFlags(QTextDocument.FindCaseSensitively)
            else:
                pattern = text_to_find.lower()
                find_flags = QTextDocument.FindFlags(0)

        replacements = 0
        cursor.beginEditBlock()
        while True:
            if self.regex_radio.isChecked():
                found_cursor = document.find(pattern, cursor)
            else:
                found_cursor = document.find(pattern, cursor, find_flags)
            if found_cursor.isNull():
                break
            found_cursor.removeSelectedText()
            found_cursor.insertText(text_to_replace)
            replacements += 1
            cursor = found_cursor

        cursor.endEditBlock()

        if replacements > 0:
            QMessageBox.information(
                self, "Replace All", f"Replaced '{text_to_find}' with '{text_to_replace}' {replacements} times"
            )
        else:
            QMessageBox.information(self, "Replace All", f"Not found: '{text_to_find}'")

class TextComparisonTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file2_path = None
        self.file2_encoding = None 

        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems([str(size) for size in range(10, 31)])
        self.font_size_combo.setCurrentText("10")
        self.font_size_combo.currentTextChanged.connect(self.update_font_size)

        self.source_text_area = QTextEdit()
        self.source_text_area.setReadOnly(True)
        self.source_text_area.setLineWrapMode(QTextEdit.NoWrap)
        self.target_text_area = QTextEdit()
        self.target_text_area.setLineWrapMode(QTextEdit.NoWrap)

        self.source_text_area.setUndoRedoEnabled(True)
        self.target_text_area.setUndoRedoEnabled(True)

        self.source_text_area.verticalScrollBar().valueChanged.connect(self.target_text_area.verticalScrollBar().setValue)
        self.target_text_area.verticalScrollBar().valueChanged.connect(self.source_text_area.verticalScrollBar().setValue)

        self.open_source_button = QPushButton("เปิดไฟล์ต้นฉบับ")
        self.open_source_button.clicked.connect(self.open_source_file)
        self.open_target_button = QPushButton("เปิดไฟล์ที่ต้องการแปล")
        self.open_target_button.clicked.connect(self.open_target_file)
        self.save_button = QPushButton("บันทึกไฟล์")
        self.save_button.clicked.connect(self.save_file)
        self.compare_button = QPushButton("ตรวจสอบสถานะการแปล")
        self.compare_button.clicked.connect(self.calculate_thai_percentage)

        layout = QVBoxLayout()
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("ขนาดตัวอักษร:"))
        font_layout.addWidget(self.font_size_combo)
        layout.addLayout(font_layout)

        text_layout = QHBoxLayout()
        text_layout.addWidget(self.source_text_area)
        text_layout.addWidget(self.target_text_area)
        layout.addLayout(text_layout)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.open_source_button)
        button_layout.addWidget(self.open_target_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.compare_button)
        layout.addLayout(button_layout)

        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["UTF-8", "UTF-16"])
        self.encoding_combo.setCurrentText("UTF-8")
        button_layout.addWidget(self.encoding_combo)

        self.setLayout(layout)


        self.target_text_area.textChanged.connect(self.auto_save) 

    def detect_and_open_file(self, text_area):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select a File", ".", "Text files (*.txt);;All files (*.*)"
        )
        if filepath:
            with open(filepath, 'rb') as f:
                rawdata = f.read()
                result = chardet.detect(rawdata)
                encoding = result['encoding']

            try:
                with open(filepath, "r", encoding=encoding) as file:
                    text_area.setPlainText(file.read())
            except UnicodeError:
                QMessageBox.warning(
                    self,
                    "Encoding Error",
                    f"Unable to open file with detected encoding ({encoding}). "
                    "Please select manually.",
                )
                encoding, ok = QInputDialog.getItem(
                    self,
                    "Select Encoding",
                    "Encoding:",
                    ["UTF-8", "UTF-16"],
                    0,
                    False,
                )
                if ok and encoding:
                    try:
                        with open(filepath, "r", encoding=encoding) as file:
                            text_area.setPlainText(file.read())
                    except UnicodeError:
                        QMessageBox.critical(
                            self,
                            "Encoding Error",
                            "Failed to open file. Please check the encoding.",
                        )
                        return

            if text_area == self.target_text_area:
                self.file2_path = filepath
                self.file2_encoding = encoding

    def update_font_size(self):
        font = QFont()
        font.setPointSize(int(self.font_size_combo.currentText()))
        self.source_text_area.setFont(font)
        self.target_text_area.setFont(font)

    def open_source_file(self):
        file1_path, _ = QFileDialog.getOpenFileName(self, "เปิดไฟล์ต้นฉบับ", "", 
                                                   "Text Files (*.txt);;All Files (*)")
        if file1_path:
            with open(file1_path, "rb") as file1:
                raw_data = file1.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding']

                if encoding.startswith('UTF-16'):
                    if raw_data.startswith(b'\xFF\xFE'):
                        encoding = 'UTF-16-LE'
                    elif raw_data.startswith(b'\xFE\xFF'):
                        encoding = 'UTF-16-BE'

            with open(file1_path, "r", encoding=encoding) as file1:
                self.source_text_area.setPlainText(file1.read())

    def set_tab_name(self, file2_path):
        if file2_path:
            tab_name = os.path.basename(file2_path)
        else:
            tab_name = "New Tab"
        TextComparisonApp.instance.tabs.setTabText(TextComparisonApp.instance.tabs.indexOf(self), tab_name)

    def open_target_file(self):
        self.file2_path, _ = QFileDialog.getOpenFileName(self, "เปิดไฟล์ที่ต้องการแปล", "", 
                                                       "Text Files (*.txt);;All Files (*)")
        if self.file2_path:
            with open(self.file2_path, "rb") as file2:
                raw_data = file2.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding']

                if encoding.startswith('UTF-16'):
                    if raw_data.startswith(b'\xFF\xFE'):
                        encoding = 'UTF-16-LE'
                    elif raw_data.startswith(b'\xFE\xFF'):
                        encoding = 'UTF-16-BE'

            with open(self.file2_path, "r", encoding=encoding) as file2:
                self.target_text_area.setPlainText(file2.read())
        self.set_tab_name(self.file2_path)

    def save_file(self):
        file2_path, _ = QFileDialog.getSaveFileName(
            self, "Save Translate File", "", "Text Files (*.txt);;All Files (*)"
        )
        if file2_path:
            self.file2_path = file2_path
            self.file2_encoding = self.encoding_combo.currentText()
            with open(self.file2_path, "w", encoding=self.file2_encoding) as file2:
                file2.write(self.target_text_area.toPlainText())

            self.set_tab_name(self.file2_path)

    def auto_save(self):
        if self.file2_path:
            backup_folder = "Backup"
            os.makedirs(backup_folder, exist_ok=True)
            backup_filename = os.path.join(
                backup_folder, os.path.basename(self.file2_path) + ".bak"
            )
            encoding = self.encoding_combo.currentText() 
            try:
                with open(backup_filename, "w", encoding=encoding) as backup_file:
                    backup_file.write(self.target_text_area.toPlainText())
            except UnicodeEncodeError as e:
                error_message = QMessageBox()
                error_message.setIcon(QMessageBox.Critical)
                error_message.setText(
                    f"Error saving backup file: {e}\nPlease check the encoding of your text."
                )
                error_message.exec()
                return

    def calculate_thai_percentage(self):
        editable_text = self.target_text_area.toPlainText()

        editable_text = editable_text.replace("\r\n", "\n")
        editable_lines = editable_text.splitlines()
        if not editable_lines:
            QMessageBox.information(self, "Translation Progress", "No text to analyze.")
            return

        thai_line_count = 0
        non_thai_line_count = 0
        total_line_count = len(editable_lines)

        for line in editable_lines:
            line = line.strip()
            if line:
                words = word_tokenize(line, engine='newmm')
                if any(any(ord(char) >= 3585 and ord(char) <= 3675 for char in word) for word in words):
                    thai_line_count += 1
                else:
                    non_thai_line_count += 1

        thai_percentage = (thai_line_count / total_line_count) * 100 if total_line_count > 0 else 0

        QMessageBox.information(
            self,
            "Translation Progress",
            f"Total lines: {total_line_count}\n"
            f"Translated lines: {thai_line_count}\n"
            f"Non-translated lines: {non_thai_line_count}\n"
            f"Translation Progress: {thai_percentage:.2f}%"
        )

    def to_dict(self):
        return {
            "source_text": self.source_text_area.toPlainText(),
            "target_text": self.target_text_area.toPlainText(),
            "file2_path": self.file2_path,
            "font_size": self.font_size_combo.currentText(),
            "encoding": self.encoding_combo.currentText(),
        }

    def from_dict(self, data):
        self.source_text_area.setPlainText(data["source_text"])
        self.target_text_area.setPlainText(data["target_text"])
        self.file2_path = data["file2_path"]
        self.font_size_combo.setCurrentText(data["font_size"])
        self.encoding_combo.setCurrentText(
            data.get("encoding", "UTF-8")
        ) 

class TextComparisonApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text Editor By Johntaber")
        self.setGeometry(100, 100, 800, 600)

        TextComparisonApp.instance = self

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("ไฟล์")
        
        new_tab_action = QAction("แท็บใหม่", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(self.add_new_tab)
        file_menu.addAction(new_tab_action)

        close_tab_action = QAction("ปิดแท็บ", self)
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(self.close_current_tab)
        file_menu.addAction(close_tab_action)

        toolbar = QToolBar("Toolbar")
        self.addToolBar(toolbar)

        find_action = QAction(QIcon.fromTheme("edit-find"), "ค้นหา", self)
        find_action.triggered.connect(self.open_find_replace_dialog)
        toolbar.addAction(find_action)

        replace_action = QAction(QIcon.fromTheme("edit-find-replace"), "ค้นหา", self)
        replace_action.triggered.connect(self.open_find_replace_dialog)
        toolbar.addAction(replace_action)

        undo_action = QAction(QIcon.fromTheme("edit-undo"), "Undo", self)
        undo_action.triggered.connect(self.undo)
        toolbar.addAction(undo_action)

        redo_action = QAction(QIcon.fromTheme("edit-redo"), "Redo", self)
        redo_action.triggered.connect(self.redo)
        toolbar.addAction(redo_action)

        self.dark_mode_action = QAction("Dark Mode", self, checkable=True)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        toolbar.addAction(self.dark_mode_action)

        self.is_dark_mode = False
        self.update_stylesheet()

        self.add_new_tab()

        save_project_action = QAction(QIcon.fromTheme("document-save"), "บันทึกเป็นโปรเจกต์", self)
        save_project_action.triggered.connect(self.save_project)
        file_menu.addAction(save_project_action)

        load_project_action = QAction(QIcon.fromTheme("document-open"), "โหลดโปรเจกต์", self)
        load_project_action.triggered.connect(self.load_project)
        file_menu.addAction(load_project_action)


    def save_project(self):
        project_path, _ = QFileDialog.getSaveFileName(
            self, "บันทึกเป็นโปรเจกต์", "", "Project Files (*.project)"
        )
        if project_path:
            project_data = {
                "tabs": [tab.to_dict() for tab in self.get_all_tabs()]
            }
            with open(project_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=4)

    def load_project(self):
        project_path, _ = QFileDialog.getOpenFileName(
            self, "โหลดโปรเจกต์", "", "Project Files (*.project)"
        )
        if project_path:
            with open(project_path, "r", encoding="utf-8") as f:
                project_data = json.load(f)
            self.tabs.clear()
            for tab_data in project_data["tabs"]:
                new_tab = TextComparisonTab(self)
                new_tab.from_dict(tab_data)
                self.tabs.addTab(new_tab, "Loading...")
                self.add_close_button(new_tab)
                new_tab.set_tab_name(tab_data.get("file2_path"))

    def get_all_tabs(self):
        return [
            self.tabs.widget(i) for i in range(self.tabs.count())
        ]

    def add_new_tab(self):
        new_tab = TextComparisonTab(self)
        self.tabs.addTab(new_tab, "New Tab")
        self.tabs.setCurrentWidget(new_tab)
        self.add_close_button(new_tab)

    def add_close_button(self, tab):
        index = self.tabs.indexOf(tab)
        tab_button = QPushButton("x", self)
        tab_button.setFixedSize(16, 16)
        tab_button.clicked.connect(lambda: self.close_tab(index))
        self.tabs.tabBar().setTabButton(index, QTabBar.RightSide, tab_button)

    def close_tab(self, index):
        self.tabs.removeTab(index)

    def close_current_tab(self):
        current_tab_index = self.tabs.currentIndex()
        if current_tab_index != -1:
            self.tabs.removeTab(current_tab_index)

    def open_find_replace_dialog(self):
        current_tab_index = self.tabs.currentIndex()
        if current_tab_index == -1:
            return

        self.find_replace_dialog = FindReplaceDialog(self)
        self.find_replace_dialog.show()

    def highlight_all_matches(self, text_to_find):
        pass

    def find_in_current_tab(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            self.find_replace_dialog.target_text_area = current_tab.target_text_area
            self.find_replace_dialog.find()

    def find_in_next_tab(self):
        current_index = self.tabs.currentIndex()
        next_index = (current_index + 1) % self.tabs.count()
        self.tabs.setCurrentIndex(next_index)
        self.find_in_current_tab()

    def undo(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.target_text_area.undo()

    def redo(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.target_text_area.redo()

    def toggle_dark_mode(self):
        self.is_dark_mode = not self.is_dark_mode
        self.update_stylesheet()

    def update_stylesheet(self):
        if self.is_dark_mode:
            self.setStyleSheet("""
            QMainWindow { background-color: #121212; color: #EEEEEE; } 
            QTextEdit { background-color: #1E1E1E; color: #EEEEEE; }
            QMenuBar { background-color: #242424; color: #EEEEEE; }
            QMenu { background-color: #242424; color: #EEEEEE; }
            QPushButton { background-color: #303030; color: #EEEEEE; }
            QComboBox { background-color: #303030; color: #EEEEEE; }
            QToolBar { background-color: #242424; }
            QCheckBox { color: #EEEEEE; }
            QRadioButton { color: #EEEEEE; }
            QTabWidget::pane { background-color: #1E1E1E; border: none; }
            QTabBar::tab { background-color: #242424; color: #EEEEEE; }
            QTabBar::tab:selected { background-color: #303030; }
        """)
        else:
            self.setStyleSheet(
                """
                QTabBar::tab {
                    background-color: lightgray;  
                    color: black; 
                    padding: 5px;
                }
                QTabBar::tab:selected {
                    background-color: gray;
                    color: white;
                }
            """
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TextComparisonApp()
    window.show()
    sys.exit(app.exec())