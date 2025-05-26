import sys
import datetime
import os
import functools # partial 함수 사용을 위해 추가
from typing import List, Optional, Dict, Any

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QHeaderView, QPushButton,
    QSizePolicy, QFileIconProvider, QAbstractItemView, QMessageBox, # QMessageBox 추가 (handle_edit/delete 등에서 사용 가능성)
    QMenu, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QIcon, QColor, QDesktopServices

# --- Local module imports ---
from dialogs import ProcessDialog, GlobalSettingsDialog, NumericTableWidgetItem
from tray_manager import TrayManager
from gui_notification_handler import GuiNotificationHandler

# --- Other local utility/data module imports ---
from data_manager import DataManager
from data_models import ManagedProcess, GlobalSettings # MainWindow에서 직접 ManagedProcess 객체를 다루므로 필요
from process_utils import get_qicon_for_file
from windows_utils import set_startup_registry
from launcher import Launcher
from notifier import Notifier # 시스템 알림 전송용
from scheduler import Scheduler, PROC_STATE_INCOMPLETE, PROC_STATE_COMPLETED, PROC_STATE_RUNNING
# from process_monitor import ProcessMonitor # 아래에서 동적 import

class MainWindow(QMainWindow):
    request_table_refresh_signal = pyqtSignal()
    # 이전 notification_activated_signal은 GuiNotificationHandler로 기능 이전

    # Status colors
    COLOR_INCOMPLETE = QColor("red")
    COLOR_COMPLETED = QColor("green")
    COLOR_RUNNING = QColor("yellow")

    # Table column indices
    COL_ICON = 0
    COL_NAME = 1
    COL_LAST_PLAYED = 2
    COL_LAUNCH_BTN = 3
    COL_STATUS = 4
    TOTAL_COLUMNS = 5

    def __init__(self, data_manager: DataManager):
        super().__init__()
        self.data_manager = data_manager
        self.launcher = Launcher()

        # Dynamically import ProcessMonitor to avoid circular dependency if it imports MainWindow
        from process_monitor import ProcessMonitor
        self.process_monitor = ProcessMonitor(self.data_manager)

        # System Notifier (from notifier.py)
        self.system_notifier = Notifier(
            application_name=QApplication.applicationName(), # 앱 이름 사용
            main_window_activated_callback=None # 콜백은 아래에서 GuiNotificationHandler의 메소드로 설정
        )

        # GUI Notification Handler (from gui_notification_handler.py)
        self.gui_notification_handler = GuiNotificationHandler(self)

        # Connect Notifier's activation to GuiNotificationHandler
        # Notifier가 직접적인 Qt 시그널을 보내지 않고 콜백을 사용하는 기존 구조를 따른다고 가정
        # Notifier의 생성자나 별도 메소드를 통해 알림 클릭 시 호출될 콜백을 설정
        if hasattr(self.system_notifier, 'main_window_activated_callback'):
             # Notifier가 main_window_activated_callback 속성을 직접 사용하거나,
             # 혹은 set_activation_callback 같은 메소드가 있다면 그것을 사용합니다.
             # 기존 코드에서는 Notifier 생성 시 콜백을 전달했으므로, Notifier 내부에서 해당 콜백을 저장하고 사용할 것입니다.
             # 여기서는 GuiNotificationHandler의 메소드를 해당 콜백으로 지정해줍니다.
             self.system_notifier.main_window_activated_callback = self.gui_notification_handler.process_system_notification_activation
             print("MainWindow: System Notifier의 콜백을 GuiNotificationHandler의 메소드로 설정했습니다.")
        else:
            print("경고: system_notifier에 main_window_activated_callback을 설정할 수 없습니다. 알림 클릭 피드백이 동작하지 않을 수 있습니다.")


        self.scheduler = Scheduler(
            self.data_manager,
            self.system_notifier, # 시스템 알림 발송용 Notifier 전달
            process_monitor_ref=self.process_monitor
        )

        self.setWindowTitle(QApplication.applicationName() or "숙제 관리자")
        self.setGeometry(100, 100, 500, 400) # Initial size
        self._set_window_icon()

        # Tray Manager (from tray_manager.py)
        # TrayManager 생성 시 self (MainWindow 인스턴스)를 전달합니다.
        self.tray_manager = TrayManager(self)

        self._create_menu_bar()

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top button layout
        top_button_layout = QHBoxLayout()
        self.add_button = QPushButton("새 게임 추가")
        self.add_button.clicked.connect(self.open_add_process_dialog)
        
        self.HSR_Web_button = QPushButton("스타레일 출석")
        self.HSR_Web_button.clicked.connect(functools.partial(self.open_webpage, r"https://act.hoyolab.com/bbs/event/signin/hkrpg/e202303301540311.html?act_id=e202303301540311&bbs_auth_required=true&bbs_presentation_style=fullscreen&lang=ko-kr&utm_source=share&utm_medium=link&utm_campaign=web"))
        self.ZZZ_Web_button = QPushButton("젠존제 출석")
        self.ZZZ_Web_button.clicked.connect(functools.partial(self.open_webpage, r"https://act.hoyolab.com/bbs/event/signin/zzz/e202406031448091.html?act_id=e202406031448091&bbs_auth_required=true&bbs_presentation_style=fullscreen&lang=ko-kr&utm_source=share&utm_medium=link&utm_campaign=web"))
        
        top_button_layout.addWidget(self.add_button)
        top_button_layout.addStretch(1)
        top_button_layout.addWidget(self.HSR_Web_button)
        top_button_layout.addWidget(self.ZZZ_Web_button)
        main_layout.addLayout(top_button_layout)

        # Process table
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(self.TOTAL_COLUMNS)
        self.process_table.setHorizontalHeaderLabels(["", "이름", "마지막 플레이", "실행", "상태"])
        self._configure_table_header()
        self.process_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.process_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection) # 수정: QTableWidget -> QAbstractItemView
        self.process_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.process_table.customContextMenuRequested.connect(self.show_table_context_menu)
        main_layout.addWidget(self.process_table)

        self.populate_process_list()

        # Signal connections
        self.request_table_refresh_signal.connect(self.populate_process_list_slot)

        # Timers for background tasks
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.run_process_monitor_check)
        self.monitor_timer.start(10 * 1000) # 10 seconds

        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.run_scheduler_check)
        self.scheduler_timer.start(10 * 1000) # 10 seconds

        print("백그라운드 ProcessMonitor 및 Scheduler 타이머 시작됨.")
        self.statusBar().showMessage("준비 완료.", 5000)
        self.apply_startup_setting()

    def open_webpage(self, url_string):
        qurl = QUrl(url_string)
        if not QDesktopServices.openUrl(qurl):
            print(f"'{url_string}'을(를) 여는 데 실패하였습니다.")

    def _set_window_icon(self):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

    def _configure_table_header(self):
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(self.COL_ICON, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_LAST_PLAYED, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_LAUNCH_BTN, QHeaderView.ResizeMode.ResizeToContents)
        # header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents) # Dynamic width
        self.process_table.setColumnWidth(self.COL_ICON, 40)
        self.process_table.setColumnWidth(self.COL_STATUS, 60)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("파일(&F)")
        try: # QStyle.StandardPixmap 사용 시 발생 가능 오류 방지
            exit_icon_pixmap = self.style().standardPixmap(QStyle.StandardPixmap.SP_DialogCloseButton)
            exit_icon = QIcon.fromTheme("application-exit", QIcon(exit_icon_pixmap))
        except AttributeError: # 일부 환경에서 standardPixmap 접근 불가 시
            exit_icon = QIcon() # 빈 아이콘 또는 기본 아이콘
            print("경고: 표준 종료 아이콘을 로드할 수 없습니다.")

        exit_action = QAction(exit_icon, "종료(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("애플리케이션을 종료합니다.")
        exit_action.triggered.connect(self.initiate_quit_sequence) # TrayManager와 동일한 종료 로직 호출
        file_menu.addAction(exit_action)

        settings_menu = menu_bar.addMenu("설정(&S)")
        global_settings_action = QAction("전역 설정 변경...", self)
        global_settings_action.triggered.connect(self.open_global_settings_dialog)
        settings_menu.addAction(global_settings_action)

    def open_global_settings_dialog(self):
        current_gs = self.data_manager.global_settings
        dialog = GlobalSettingsDialog(current_gs, self) # from dialogs.py
        if dialog.exec():
            updated_gs = dialog.get_updated_settings()
            self.data_manager.global_settings = updated_gs
            self.data_manager.save_global_settings()
            self.statusBar().showMessage("전역 설정이 성공적으로 저장되었습니다.", 3000)
            print(f"전역 설정 업데이트됨: {vars(updated_gs)}")
            self.apply_startup_setting()
            self.populate_process_list_slot()

    def apply_startup_setting(self):
        run_on_startup = self.data_manager.global_settings.run_on_startup
        if set_startup_registry(run_on_startup): # from windows_utils.py
            status = "활성화됨" if run_on_startup else "비활성화됨"
            print(f"시작 프로그램 자동 실행 상태: {status}")
            self.statusBar().showMessage(f"시작 프로그램 자동 실행: {status}", 3000)
        else:
            print("시작 프로그램 자동 실행 설정 변경 중 문제가 발생했을 수 있습니다. 콘솔 로그를 확인하세요.")
            self.statusBar().showMessage("시작 프로그램 자동 실행 설정 중 문제 발생 가능.", 3000)

    def run_process_monitor_check(self):
        if self.process_monitor.check_and_update_statuses():
            print("ProcessMonitor: 변경 감지됨, 테이블 새로고침 요청.")
            self.statusBar().showMessage("프로세스 상태 변경 감지됨, 목록 업데이트 중...", 2000)
            self.request_table_refresh_signal.emit()

    def run_scheduler_check(self):
        self.scheduler.run_all_checks()
        self.request_table_refresh_signal.emit()

    def populate_process_list_slot(self):
        self.populate_process_list()

    def populate_process_list(self):
        self.process_table.setSortingEnabled(False)
        processes = self.data_manager.managed_processes
        self.process_table.setRowCount(0)
        self.process_table.setRowCount(len(processes))
        now_dt = datetime.datetime.now()
        global_settings = self.data_manager.global_settings
        default_bg_brush = self.process_table.palette().base()
        default_fg_brush = self.process_table.palette().text()

        for row, process_obj in enumerate(processes):
            # Icon
            icon_item = QTableWidgetItem() # 일반 QTableWidgetItem 사용
            q_icon = get_qicon_for_file(process_obj.monitoring_path) # from process_utils.py
            if q_icon and not q_icon.isNull():
                icon_item.setIcon(q_icon)
            self.process_table.setItem(row, self.COL_ICON, icon_item)
            icon_item.setBackground(default_bg_brush)
            icon_item.setForeground(default_fg_brush)

            # Name (Store Process ID in UserRole)
            name_item = QTableWidgetItem(process_obj.name) # 일반 QTableWidgetItem 사용
            name_item.setData(Qt.ItemDataRole.UserRole, process_obj.id)
            self.process_table.setItem(row, self.COL_NAME, name_item)
            name_item.setBackground(default_bg_brush)
            name_item.setForeground(default_fg_brush)

            # Last Played
            last_played_str = "기록 없음"
            if process_obj.last_played_timestamp:
                try:
                    dt_object = datetime.datetime.fromtimestamp(process_obj.last_played_timestamp)
                    last_played_str = dt_object.strftime("%m월 %d일 %H시 %M분")
                except Exception as e:
                    print(f"Timestamp 변환 오류 for {process_obj.name}: {e}")
                    last_played_str = "변환 오류"
            last_played_item = QTableWidgetItem(last_played_str) # 일반 QTableWidgetItem 사용
            self.process_table.setItem(row, self.COL_LAST_PLAYED, last_played_item)
            last_played_item.setBackground(default_bg_brush)
            last_played_item.setForeground(default_fg_brush)
            
            # Launch Button
            launch_btn_cell_widget = QPushButton("실행")
            launch_btn_cell_widget.clicked.connect(
                functools.partial(self.handle_launch_button_in_row, process_obj.id)
            )
            self.process_table.setCellWidget(row, self.COL_LAUNCH_BTN, launch_btn_cell_widget)

            # Status
            status_str = self.scheduler.determine_process_visual_status(process_obj, now_dt, global_settings)
            status_item = QTableWidgetItem(status_str) # 일반 QTableWidgetItem 사용
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.process_table.setItem(row, self.COL_STATUS, status_item)
            status_item.setForeground(default_fg_brush)
            if status_str == PROC_STATE_RUNNING:
                status_item.setBackground(self.COLOR_RUNNING)
                status_item.setForeground(QColor("black"))
            elif status_str == PROC_STATE_INCOMPLETE:
                status_item.setBackground(self.COLOR_INCOMPLETE)
            elif status_str == PROC_STATE_COMPLETED:
                status_item.setBackground(self.COLOR_COMPLETED)
            else:
                status_item.setBackground(default_bg_brush)
        
        self.process_table.setSortingEnabled(True)
        self.process_table.sortByColumn(self.COL_NAME, Qt.SortOrder.AscendingOrder)
        self.process_table.resizeColumnsToContents()
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)

    def show_table_context_menu(self, position):
        item_at_pos = self.process_table.itemAt(position)
        if not item_at_pos: return
        row = item_at_pos.row()
        name_item = self.process_table.item(row, self.COL_NAME)
        if not name_item: return
        process_id = name_item.data(Qt.ItemDataRole.UserRole)
        if not process_id: return

        menu = QMenu(self)
        edit_action = QAction("편집", self)
        delete_action = QAction("삭제", self)
        edit_action.triggered.connect(functools.partial(self.handle_edit_action_for_row, process_id))
        delete_action.triggered.connect(functools.partial(self.handle_delete_action_for_row, process_id))
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(self.process_table.mapToGlobal(position))

    def handle_edit_action_for_row(self, process_id: str):
        process_to_edit = self.data_manager.get_process_by_id(process_id)
        if not process_to_edit:
            QMessageBox.warning(self, "오류", f"ID '{process_id}'에 해당하는 프로세스를 찾을 수 없습니다.")
            return
        dialog = ProcessDialog(self, existing_process=process_to_edit) # from dialogs.py
        if dialog.exec():
            data = dialog.get_data()
            if data:
                edited_name = data["name"].strip()
                if not edited_name: edited_name = process_to_edit.name
                updated_process = ManagedProcess( # from data_models.py
                    id=process_to_edit.id,
                    name=edited_name,
                    monitoring_path=data["monitoring_path"],
                    launch_path=data["launch_path"],
                    server_reset_time_str=data["server_reset_time_str"],
                    user_cycle_hours=data["user_cycle_hours"],
                    mandatory_times_str=data["mandatory_times_str"],
                    is_mandatory_time_enabled=data["is_mandatory_time_enabled"],
                    last_played_timestamp=process_to_edit.last_played_timestamp
                )
                if self.data_manager.update_process(updated_process):
                    self.populate_process_list_slot()
                    self.statusBar().showMessage(f"프로세스 '{updated_process.name}'이(가) 성공적으로 수정되었습니다.", 3000)
                else:
                    QMessageBox.warning(self, "오류", "프로세스 수정에 실패했습니다.")

    def handle_delete_action_for_row(self, process_id: str):
        process_to_delete = self.data_manager.get_process_by_id(process_id)
        if not process_to_delete:
            QMessageBox.warning(self, "오류", f"ID '{process_id}'에 해당하는 프로세스를 찾을 수 없습니다.")
            return
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{process_to_delete.name}' 프로세스를 정말 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted_name = process_to_delete.name
            if self.data_manager.remove_process(process_id):
                self.populate_process_list_slot()
                self.statusBar().showMessage(f"프로세스 '{deleted_name}'이(가) 성공적으로 삭제되었습니다.", 3000)
            else:
                QMessageBox.warning(self, "오류", "프로세스 삭제에 실패했습니다.")

    def handle_launch_button_in_row(self, process_id: str):
        process_to_launch = self.data_manager.get_process_by_id(process_id)
        if not process_to_launch:
            QMessageBox.warning(self, "오류", f"ID '{process_id}'에 해당하는 프로세스를 찾을 수 없습니다.")
            return
        if not process_to_launch.launch_path:
            QMessageBox.warning(self, "오류", f"'{process_to_launch.name}' 프로세스에 설정된 실행 경로가 없습니다.")
            return
        print(f"'{process_to_launch.name}' 실행 시도: {process_to_launch.launch_path}")
        if self.launcher.launch_process(process_to_launch.launch_path): # from launcher.py
            self.system_notifier.send_notification( # from notifier.py
                title="프로세스 실행",
                message=f"'{process_to_launch.name}'을(를) 실행했습니다.",
                task_id_to_highlight=None
            )
            self.statusBar().showMessage(f"'{process_to_launch.name}' 실행 시도됨.", 3000)
        else:
            self.system_notifier.send_notification(
                title="실행 실패",
                message=f"'{process_to_launch.name}' 실행에 실패했습니다. 콘솔 로그를 확인해주세요.",
                task_id_to_highlight=None
            )
            self.statusBar().showMessage(f"'{process_to_launch.name}' 실행 실패.", 3000)

    def open_add_process_dialog(self):
        dialog = ProcessDialog(self) # from dialogs.py
        if dialog.exec():
            data = dialog.get_data()
            if data:
                process_name = data["name"].strip()
                monitoring_path = data["monitoring_path"]
                if not process_name and monitoring_path:
                    base_name = os.path.basename(monitoring_path)
                    process_name = os.path.splitext(base_name)[0]
                    if not process_name: process_name = "새 프로세스"
                
                new_process = ManagedProcess( # from data_models.py
                    name=process_name,
                    monitoring_path=monitoring_path,
                    launch_path=data["launch_path"],
                    server_reset_time_str=data["server_reset_time_str"],
                    user_cycle_hours=data["user_cycle_hours"],
                    mandatory_times_str=data["mandatory_times_str"],
                    is_mandatory_time_enabled=data["is_mandatory_time_enabled"]
                )
                self.data_manager.add_process(new_process)
                self.populate_process_list_slot()
                self.statusBar().showMessage(f"프로세스 '{new_process.name}'이(가) 성공적으로 추가되었습니다.", 3000)

    # --- Methods related to TrayManager and application lifecycle ---
    def closeEvent(self, event):
        """Overrides the window close event to delegate to TrayManager."""
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.handle_window_close_event(event)
        else: # Fallback if tray_manager not initialized (should ideally not happen)
            event.ignore()
            self.hide()
            print("경고: TrayManager가 초기화되지 않아 기본 숨김 처리합니다.")

    def initiate_quit_sequence(self):
        """Handles pre-quit cleanup and then quits the application."""
        print("애플리케이션 종료 절차 시작...")
        if hasattr(self, 'monitor_timer') and self.monitor_timer.isActive():
            self.monitor_timer.stop()
            print("모니터 타이머 중지됨.")
        if hasattr(self, 'scheduler_timer') and self.scheduler_timer.isActive():
            self.scheduler_timer.stop()
            print("스케줄러 타이머 중지됨.")
        
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.hide_tray_icon() # TrayManager에게 아이콘 숨기기 요청
        
        app_instance = QApplication.instance()
        if app_instance:
            app_instance.quit()
            print("애플리케이션 종료 신호 전송됨.")
        else:
            print("오류: QApplication 인스턴스를 찾을 수 없어 종료할 수 없습니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("숙제 관리자")
    app.setOrganizationName("MyHomeworkApp") # 적절한 이름으로 변경 가능
    app.setQuitOnLastWindowClosed(False) # 트레이 아이콘 동작에 매우 중요

    # 데이터 폴더 설정 (예: my_homework_app_data)
    # 사용자 문서 폴더 등에 저장하는 것이 일반적일 수 있습니다.
    # 여기서는 실행 파일 위치 기준으로 상대 경로를 사용합니다.
    data_folder_name = "homework_helper_data"
    if getattr(sys, 'frozen', False): # PyInstaller 등으로 패키징된 경우
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(application_path, data_folder_name)

    data_manager_instance = DataManager(data_folder=data_path)
    
    main_window = MainWindow(data_manager_instance)
    main_window.show()

    sys.exit(app.exec())
