import sys
import json
import shutil
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QListWidget, QFileDialog, QInputDialog,
                             QLabel, QStyle, QProgressDialog, QMessageBox, QComboBox)
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal

def list_drives():
    return [f'{drive}:' for drive in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{drive}:')]

class MoveThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, games_to_move, source, destination):
        super().__init__()
        self.games_to_move = games_to_move
        self.source = source
        self.destination = destination

    def run(self):
        total = len(self.games_to_move)
        for i, game in enumerate(self.games_to_move):
            source_path = game['path']
            if not os.path.exists(source_path):
                print(f"경고: 원본 경로가 존재하지 않습니다: {source_path}")
                continue

            # 원본 경로 구조를 유지하면서 목적지 경로 생성
            if 'original_path' in game:
                relative_path = os.path.relpath(game['original_path'], game['original_drive'])
                destination_path = os.path.join(self.destination, relative_path)
            else:
                destination_path = os.path.join(self.destination, os.path.basename(source_path))
            
            destination_dir = os.path.dirname(destination_path)

            try:
                if not os.path.exists(destination_dir):
                    os.makedirs(destination_dir)

                if os.path.isdir(source_path):
                    shutil.move(source_path, destination_path)
                else:
                    shutil.copy2(source_path, destination_path)
                    os.remove(source_path)

                game['path'] = destination_path
            except Exception as e:
                print(f"오류 발생: {e}")
                print(f"원본 경로: {source_path}")
                print(f"대상 경로: {destination_path}")

            self.progress.emit(int((i + 1) / total * 100))

        self.finished.emit()

class GameMover(QWidget):
    def __init__(self):
        super().__init__()
        exe_path = sys.argv[0]
        exe_drive = os.path.splitdrive(os.path.abspath(exe_path))[0].upper()
        self.exe_drive = exe_drive
        self.drives = [drive for drive in list_drives() if drive != self.exe_drive]
        if len(self.drives) < 1:
            QMessageBox.critical(self, "오류", "사용 가능한 드라이브가 1개 미만입니다. 프로그램을 종료합니다.")
            sys.exit()
        self.games = self.load_games()
        self.initUI()
        self.move_thread = None

    def initUI(self):
        self.setWindowTitle('게임 파일 이동 프로그램')
        self.setGeometry(100, 100, 800, 500)
        self.setStyleSheet("""
            QWidget {
                background-color: #2C3E50;
                color: #ECF0F1;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton, QComboBox {
                background-color: #3498DB;
                border: none;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover, QComboBox:hover {
                background-color: #2980B9;
            }
            QListWidget {
                background-color: #34495E;
                border: 1px solid #7F8C8D;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #3498DB;
            }
            QLabel {
                font-size: 14px;
                font-weight: bold;
            }
        """)

        layout = QHBoxLayout()

        # 왼쪽 드라이브 레이아웃
        left_layout = QVBoxLayout()
        left_title_layout = QHBoxLayout()
        self.left_drive_combo = QComboBox()
        self.left_drive_combo.addItems(self.drives)
        self.left_drive_combo.setFixedWidth(60)
        self.left_drive_combo.currentTextChanged.connect(self.update_lists)
        left_label = QLabel("게임 목록")
        left_title_layout.addStretch()
        left_title_layout.addWidget(self.left_drive_combo)
        left_title_layout.addWidget(left_label)
        left_title_layout.addStretch()
        left_layout.addLayout(left_title_layout)

        self.left_drive_list = QListWidget()
        self.left_drive_list.setSelectionMode(QListWidget.ExtendedSelection)
        left_layout.addWidget(self.left_drive_list)

        add_game_btn = QPushButton('게임 추가')
        add_game_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        add_game_btn.clicked.connect(self.add_game)
        left_layout.addWidget(add_game_btn)

        open_folder_btn = QPushButton('폴더 열기')
        open_folder_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        open_folder_btn.clicked.connect(self.open_game_folder)
        left_layout.addWidget(open_folder_btn)

        move_to_right_btn = QPushButton('오른쪽으로 이동')
        move_to_right_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        move_to_right_btn.clicked.connect(self.move_to_right)
        left_layout.addWidget(move_to_right_btn)

        # 오른쪽 드라이브 레이아웃
        right_layout = QVBoxLayout()
        right_title_layout = QHBoxLayout()
        right_label = QLabel(f"{self.exe_drive} 드라이브 게임 목록")
        right_title_layout.addStretch()
        right_title_layout.addWidget(right_label)
        right_title_layout.addStretch()
        right_layout.addLayout(right_title_layout)

        self.right_drive_list = QListWidget()
        self.right_drive_list.setSelectionMode(QListWidget.ExtendedSelection)
        right_layout.addWidget(self.right_drive_list)

        open_folder_btn = QPushButton('폴더 열기')
        open_folder_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        open_folder_btn.clicked.connect(self.open_game_folder)
        right_layout.addWidget(open_folder_btn)

        move_to_left_btn = QPushButton('왼쪽으로 이동')
        move_to_left_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        move_to_left_btn.clicked.connect(self.move_to_left)
        right_layout.addWidget(move_to_left_btn)

        layout.addLayout(left_layout)
        layout.addLayout(right_layout)

        self.setLayout(layout)
        self.update_lists()

    def load_games(self):
        try:
            with open('games.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {drive: [] for drive in self.drives + [self.exe_drive]}

    def save_games(self):
        with open('games.json', 'w', encoding='utf-8') as f:
            json.dump(self.games, f, ensure_ascii=False, indent=2)

    def update_lists(self):
        left_drive = self.left_drive_combo.currentText()
        self.left_drive_list.clear()
        self.right_drive_list.clear()

        for game in self.games.get(left_drive, []):
            item_text = f"{game['name']} ({os.path.basename(game['path'])}) [{game['path']}]"
            self.left_drive_list.addItem(item_text)

        for game in self.games.get(self.exe_drive, []):
            item_text = f"{game['name']} ({os.path.basename(game['path'])}) [{game['path']}]"
            self.right_drive_list.addItem(item_text)

    def add_game(self):
        current_drive = self.left_drive_combo.currentText()
        folder = QFileDialog.getExistingDirectory(self, "게임 폴더 선택", current_drive)
        if folder:
            name, ok = QInputDialog.getText(self, "게임 이름", "게임의 이름을 입력하세요:")
            if ok and name:
                drive = os.path.splitdrive(folder)[0].upper()
                if drive not in self.games:
                    self.games[drive] = []
                self.games[drive].append({
                    "name": name,
                    "path": folder,
                    "original_path": folder,
                    "original_drive": drive
                })
                self.save_games()
                self.update_lists()

    def open_game_folder(self):
        current_list = self.left_drive_list if self.left_drive_list.hasFocus() else self.right_drive_list
        selected_item = current_list.currentItem()
        if selected_item:
            game_path = selected_item.text().split('[')[-1].rstrip(']')
            os.startfile(game_path)

    def move_games(self, source, destination):
        source_list = self.left_drive_list if source != self.exe_drive else self.right_drive_list
        selected_items = source_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "이동할 게임을 선택해주세요.")
            return

        games_to_move = []
        for item in selected_items:
            game_path = item.text().split('[')[-1].rstrip(']')
            try:
                game = next(game for game in self.games[source] if game['path'] == game_path)
                games_to_move.append(game)
            except StopIteration:
                continue

        self.progress_dialog = QProgressDialog("파일 이동 중...", "취소", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setCancelButton(None)

        self.move_thread = MoveThread(games_to_move, source, destination)
        self.move_thread.progress.connect(self.progress_dialog.setValue)
        self.move_thread.finished.connect(lambda: self.move_finished(games_to_move, source, destination))
        self.move_thread.start()

    def move_finished(self, games_to_move, source, destination):
        self.progress_dialog.close()
        
        for game in games_to_move:
            self.games[source].remove(game)
            if destination not in self.games:
                self.games[destination] = []
            self.games[destination].append(game)
            if 'original_path' in game:
                relative_path = os.path.relpath(game['original_path'], game['original_drive'])
                game['path'] = os.path.join(destination, relative_path)
        
        self.save_games()
        self.update_lists()
        QMessageBox.information(self, "완료", f"{len(games_to_move)}개의 게임 이동이 완료되었습니다.")

    def move_to_right(self):
        self.move_games(self.left_drive_combo.currentText(), self.exe_drive)

    def move_to_left(self):
        self.move_games(self.exe_drive, self.left_drive_combo.currentText())

    def closeEvent(self, event):
        if self.move_thread and self.move_thread.isRunning():
            event.ignore()
            QMessageBox.warning(self, "경고", "파일 이동 중에는 프로그램을 종료할 수 없습니다.")
        else:
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GameMover()
    ex.show()
    sys.exit(app.exec_())