# homework_helper.py
import sys
import datetime
import os
import functools
from typing import List, Optional, Dict, Any

# PyQt6 라이브러리 임포트
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget,
    QHeaderView, QPushButton, QSizePolicy, QFileIconProvider, QAbstractItemView,
    QMessageBox, QMenu, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl, QEvent # QEvent 추가
from PyQt6.QtGui import QAction, QIcon, QColor, QDesktopServices

# 로컬 애플리케이션 모듈 임포트
from dialogs import ProcessDialog, GlobalSettingsDialog, NumericTableWidgetItem
from tray_manager import TrayManager
from gui_notification_handler import GuiNotificationHandler
from instance_manager import run_with_single_instance_check, SingleInstanceApplication # 수정된 임포트

from data_manager import DataManager
from data_models import ManagedProcess, GlobalSettings
from process_utils import get_qicon_for_file
from windows_utils import set_startup_registry
from launcher import Launcher
from notifier import Notifier
from scheduler import Scheduler, PROC_STATE_INCOMPLETE, PROC_STATE_COMPLETED, PROC_STATE_RUNNING

class MainWindow(QMainWindow):
    INSTANCE = None # 다른 모듈에서 메인 윈도우 인스턴스에 접근하기 위함
    request_table_refresh_signal = pyqtSignal()

    # UI 색상 및 테이블 컬럼 정의
    COLOR_INCOMPLETE = QColor("red")
    COLOR_COMPLETED = QColor("green")
    COLOR_RUNNING = QColor("yellow")

    COL_ICON = 0
    COL_NAME = 1
    COL_LAST_PLAYED = 2
    COL_LAUNCH_BTN = 3
    COL_STATUS = 4
    TOTAL_COLUMNS = 5 # 위 컬럼 개수와 일치

    def __init__(self, data_manager: DataManager, instance_manager: Optional[SingleInstanceApplication] = None):
        super().__init__()
        MainWindow.INSTANCE = self
        self.data_manager = data_manager
        self._instance_manager = instance_manager # 종료 시 cleanup을 위해 참조 저장
        self.launcher = Launcher()

        # 순환 참조 방지를 위한 동적 임포트
        from process_monitor import ProcessMonitor
        self.process_monitor = ProcessMonitor(self.data_manager)

        self.system_notifier = Notifier(QApplication.applicationName())
        self.gui_notification_handler = GuiNotificationHandler(self)

        # 시스템 알리미 콜백을 GUI 핸들러에 연결
        if hasattr(self.system_notifier, 'main_window_activated_callback'):
            self.system_notifier.main_window_activated_callback = \
                self.gui_notification_handler.process_system_notification_activation

        self.scheduler = Scheduler(self.data_manager, self.system_notifier, self.process_monitor)

        self.setWindowTitle(QApplication.applicationName() or "숙제 관리자")
        self.setGeometry(100, 100, 520, 400) # 초기 위치 및 크기
        self._set_window_icon()

        self.tray_manager = TrayManager(self) # TrayManager 생성 및 self 전달
        self._create_menu_bar()
        self._setup_ui()

        self.populate_process_list()
        self._connect_signals()
        self._start_timers()

        self.statusBar().showMessage("준비 완료.", 5000)
        self.apply_startup_setting()

    def _setup_ui(self):
        """창의 주요 UI 요소들을 설정합니다."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 상단 버튼 레이아웃
        top_button_layout = QHBoxLayout()
        self.add_button = QPushButton("새 게임 추가")
        top_button_layout.addWidget(self.add_button)
        top_button_layout.addStretch(1)

        # 웹 버튼들
        HSR_URL = r"https://act.hoyolab.com/bbs/event/signin/hkrpg/e202303301540311.html?act_id=e202303301540311&bbs_auth_required=true&bbs_presentation_style=fullscreen&lang=ko-kr&utm_source=share&utm_medium=link&utm_campaign=web"
        self.HSR_Web_button = QPushButton("스타레일 출석")
        self.HSR_Web_button.clicked.connect(functools.partial(self.open_webpage, HSR_URL))
        top_button_layout.addWidget(self.HSR_Web_button)

        ZZZ_URL = r"https://act.hoyolab.com/bbs/event/signin/zzz/e202406031448091.html?act_id=e202406031448091&bbs_auth_required=true&bbs_presentation_style=fullscreen&lang=ko-kr&utm_source=share&utm_medium=link&utm_campaign=web"
        self.ZZZ_Web_button = QPushButton("젠존제 출석")
        self.ZZZ_Web_button.clicked.connect(functools.partial(self.open_webpage, ZZZ_URL))
        top_button_layout.addWidget(self.ZZZ_Web_button)

        main_layout.addLayout(top_button_layout)

        # 프로세스 테이블
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(self.TOTAL_COLUMNS)
        self.process_table.setHorizontalHeaderLabels(["", "이름", "마지막 플레이", "실행", "상태"])
        self._configure_table_header()
        self.process_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.process_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.process_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        main_layout.addWidget(self.process_table)

    def _connect_signals(self):
        """위젯 시그널을 해당 슬롯에 연결합니다."""
        self.add_button.clicked.connect(self.open_add_process_dialog)
        self.process_table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.request_table_refresh_signal.connect(self.populate_process_list_slot)

    def _start_timers(self):
        """백그라운드 타이머를 초기화하고 시작합니다."""
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.run_process_monitor_check)
        self.monitor_timer.start(10 * 1000) # 10초

        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.run_scheduler_check)
        self.scheduler_timer.start(10 * 1000) # 10초

    def changeEvent(self, event: QEvent):
        """
        창 상태 변경을 처리하며, 특히 트레이로 최소화하는 경우를 다룹니다.
        """
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized: # 창이 최소화 상태로 변경될 때
                if hasattr(self, 'tray_manager') and self.tray_manager.is_tray_icon_visible():
                    # TrayManager에게 최소화 처리 위임
                    self.tray_manager.handle_minimize_event()
                    # tray_manager에 의해 hide()가 호출되므로, event.ignore()는 중복될 수 있음
        super().changeEvent(event)

    def activate_and_show(self):
        """
        메인 창을 활성화하고 표시하며, 일반적으로 단일 인스턴스를 위해 IPC를 통해 호출됩니다.
        """
        print("MainWindow: activate_and_show() 호출됨.")
        self.showNormal() # 최소화된 상태에서 복원하거나 숨겨진 경우 표시
        self.activateWindow() # 창을 최상단으로 가져옴
        self.raise_()         # 다른 창들보다 위에 있도록 보장

    def open_webpage(self, url_string: str):
        """주어진 URL 문자열을 기본 웹 브라우저에서 엽니다."""
        qurl = QUrl(url_string)
        if not QDesktopServices.openUrl(qurl):
            print(f"URL 열기 실패: '{url_string}'")
            QMessageBox.warning(self, "URL 열기 실패", f"다음 URL을 여는 데 실패했습니다:\n{url_string}")

    def _set_window_icon(self):
        """로컬 파일 또는 표준 시스템 아이콘으로부터 창 아이콘을 설정합니다."""
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

    def _configure_table_header(self):
        """프로세스 테이블 헤더의 모양과 동작을 설정합니다."""
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(self.COL_ICON, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_LAST_PLAYED, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_LAUNCH_BTN, QHeaderView.ResizeMode.ResizeToContents)
        # COL_STATUS 너비도 중요함
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)

        self.process_table.setColumnWidth(self.COL_ICON, 40) # 아이콘 고정 너비
        # 상태 컬럼을 내용에 맞게 크기 조정하거나, 선호하는 경우 고정/최소 너비 설정
        # self.process_table.setColumnWidth(self.COL_STATUS, 60)

    def _create_menu_bar(self):
        """애플리케이션의 메인 메뉴 바를 생성합니다."""
        menu_bar = self.menuBar()

        # 파일 메뉴
        file_menu = menu_bar.addMenu("파일(&F)")
        try:
            # 표준 닫기 아이콘을 가져오려고 시도하고, 실패 시 대체 아이콘 제공
            exit_icon_pixmap = self.style().standardPixmap(QStyle.StandardPixmap.SP_DialogCloseButton)
            exit_icon = QIcon.fromTheme("application-exit", QIcon(exit_icon_pixmap))
        except AttributeError: # QStyle에서는 발생하지 않아야 하지만, 안전 장치로 사용
            exit_icon = QIcon()

        exit_action = QAction(exit_icon, "종료(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("애플리케이션을 종료합니다.")
        exit_action.triggered.connect(self.initiate_quit_sequence)
        file_menu.addAction(exit_action)

        # 설정 메뉴
        settings_menu = menu_bar.addMenu("설정(&S)")
        global_settings_action = QAction("전역 설정 변경...", self)
        global_settings_action.triggered.connect(self.open_global_settings_dialog)
        settings_menu.addAction(global_settings_action)

    def open_global_settings_dialog(self):
        """전역 애플리케이션 설정을 수정하는 대화 상자를 엽니다."""
        current_global_settings = self.data_manager.global_settings
        dialog = GlobalSettingsDialog(current_global_settings, self)
        if dialog.exec():
            updated_settings = dialog.get_updated_settings()
            self.data_manager.global_settings = updated_settings
            self.data_manager.save_global_settings()
            self.statusBar().showMessage("전역 설정이 성공적으로 저장되었습니다.", 3000)
            self.apply_startup_setting()
            self.populate_process_list_slot() # 설정이 표시에 영향을 줄 수 있으므로 목록 새로고침

    def apply_startup_setting(self):
        """Windows 레지스트리를 수정하여 '시작 시 실행' 설정을 적용합니다."""
        run_on_startup = self.data_manager.global_settings.run_on_startup
        if set_startup_registry(run_on_startup):
            status_message = f"시작 프로그램 자동 실행: {'활성화됨' if run_on_startup else '비활성화됨'}"
            self.statusBar().showMessage(status_message, 3000)
        else:
            self.statusBar().showMessage("시작 프로그램 자동 실행 설정 중 문제가 발생했을 수 있습니다.", 3000)

    def run_process_monitor_check(self):
        """실행 중인 프로세스를 주기적으로 확인하고 변경 사항이 감지되면 상태를 업데이트합니다."""
        if self.process_monitor.check_and_update_statuses():
            self.statusBar().showMessage("프로세스 상태 변경 감지됨, 목록 업데이트 중...", 2000)
            self.request_table_refresh_signal.emit()

    def run_scheduler_check(self):
        """알림 및 업데이트를 위해 스케줄러 검사를 주기적으로 실행합니다."""
        self.scheduler.run_all_checks()
        self.request_table_refresh_signal.emit() # 상태가 변경되었을 수 있으므로 테이블 새로고침

    def populate_process_list_slot(self):
        """프로세스 목록을 새로고침하는 슬롯으로, 일반적으로 시그널에 연결됨."""
        self.populate_process_list()

    def populate_process_list(self):
        """관리되는 프로세스와 해당 상태로 메인 테이블을 채웁니다."""
        self.process_table.setSortingEnabled(False)
        processes = self.data_manager.managed_processes
        self.process_table.setRowCount(len(processes))

        now_dt = datetime.datetime.now()
        global_settings = self.data_manager.global_settings
        palette = self.process_table.palette()
        default_bg_brush = palette.base()
        default_fg_brush = palette.text()

        for row_idx, process_obj in enumerate(processes):
            # 컬럼: 아이콘
            icon_item = QTableWidgetItem()
            q_icon = get_qicon_for_file(process_obj.monitoring_path)
            if q_icon and not q_icon.isNull():
                icon_item.setIcon(q_icon)
            icon_item.setBackground(default_bg_brush)
            icon_item.setForeground(default_fg_brush)
            self.process_table.setItem(row_idx, self.COL_ICON, icon_item)

            # 컬럼: 이름 (UserRole에 프로세스 ID 저장)
            name_item = QTableWidgetItem(process_obj.name)
            name_item.setData(Qt.ItemDataRole.UserRole, process_obj.id)
            name_item.setBackground(default_bg_brush)
            name_item.setForeground(default_fg_brush)
            self.process_table.setItem(row_idx, self.COL_NAME, name_item)

            # 컬럼: 마지막 플레이 타임스탬프
            last_played_str = "기록 없음"
            if process_obj.last_played_timestamp:
                try:
                    dt_object = datetime.datetime.fromtimestamp(process_obj.last_played_timestamp)
                    last_played_str = dt_object.strftime("%m월 %d일 %H시 %M분") # 날짜/시간 형식 변경
                except Exception: # 타임스탬프 변환 시 발생할 수 있는 다양한 예외 처리
                    last_played_str = "변환 오류"
            last_played_item = QTableWidgetItem(last_played_str)
            last_played_item.setBackground(default_bg_brush)
            last_played_item.setForeground(default_fg_brush)
            self.process_table.setItem(row_idx, self.COL_LAST_PLAYED, last_played_item)

            # 컬럼: 실행 버튼
            launch_button = QPushButton("실행")
            launch_button.clicked.connect(
                functools.partial(self.handle_launch_button_in_row, process_obj.id)
            )
            self.process_table.setCellWidget(row_idx, self.COL_LAUNCH_BTN, launch_button)

            # 컬럼: 상태 (텍스트 및 색상)
            status_str = self.scheduler.determine_process_visual_status(process_obj, now_dt, global_settings)
            status_item = QTableWidgetItem(status_str)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(default_fg_brush) # 기본 텍스트 색상

            if status_str == PROC_STATE_RUNNING:
                status_item.setBackground(self.COLOR_RUNNING)
                status_item.setForeground(QColor("black")) # 텍스트 가시성 확보
            elif status_str == PROC_STATE_INCOMPLETE:
                status_item.setBackground(self.COLOR_INCOMPLETE)
            elif status_str == PROC_STATE_COMPLETED:
                status_item.setBackground(self.COLOR_COMPLETED)
            else: # 기본 또는 알 수 없는 상태
                status_item.setBackground(default_bg_brush)
            self.process_table.setItem(row_idx, self.COL_STATUS, status_item)

        self.process_table.setSortingEnabled(True)
        self.process_table.sortByColumn(self.COL_NAME, Qt.SortOrder.AscendingOrder)
        self.process_table.resizeColumnsToContents()
        # 다른 컬럼 크기 조정 후 이름 컬럼이 확장되도록 보장
        self.process_table.horizontalHeader().setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)

    def show_table_context_menu(self, position):
        """주어진 위치의 테이블 항목에 대한 컨텍스트 메뉴를 표시합니다."""
        item_at_pos = self.process_table.itemAt(position)
        if not item_at_pos: # 테이블의 빈 공간 클릭됨
            return

        row = item_at_pos.row()
        name_item = self.process_table.item(row, self.COL_NAME)
        if not name_item:
            return

        process_id = name_item.data(Qt.ItemDataRole.UserRole)
        if not process_id:
            return

        menu = QMenu(self)
        edit_action = QAction("편집", self)
        delete_action = QAction("삭제", self)

        edit_action.triggered.connect(functools.partial(self.handle_edit_action_for_row, process_id))
        delete_action.triggered.connect(functools.partial(self.handle_delete_action_for_row, process_id))

        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(self.process_table.mapToGlobal(position))

    def handle_edit_action_for_row(self, process_id: str):
        """특정 프로세스 ID에 대한 '편집' 작업을 처리합니다."""
        process_to_edit = self.data_manager.get_process_by_id(process_id)
        if not process_to_edit:
            QMessageBox.warning(self, "오류", f"ID '{process_id}'에 해당하는 프로세스를 찾을 수 없습니다.")
            return

        dialog = ProcessDialog(self, existing_process=process_to_edit)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                name = data["name"].strip() or process_to_edit.name # 새 이름이 비어있는 경우 기존 이름 유지
                updated_process = ManagedProcess(
                    id=process_to_edit.id, # 중요: 기존 ID 사용
                    name=name,
                    monitoring_path=data["monitoring_path"],
                    launch_path=data["launch_path"],
                    server_reset_time_str=data["server_reset_time_str"],
                    user_cycle_hours=data["user_cycle_hours"],
                    mandatory_times_str=data["mandatory_times_str"],
                    is_mandatory_time_enabled=data["is_mandatory_time_enabled"],
                    last_played_timestamp=process_to_edit.last_played_timestamp # 마지막 플레이 기록 보존
                )
                if self.data_manager.update_process(updated_process):
                    self.populate_process_list_slot()
                    self.statusBar().showMessage(f"프로세스 '{updated_process.name}'이(가) 성공적으로 수정되었습니다.", 3000)
                else:
                    QMessageBox.warning(self, "오류", "프로세스 수정에 실패했습니다.")

    def handle_delete_action_for_row(self, process_id: str):
        """특정 프로세스 ID에 대한 '삭제' 작업을 처리합니다."""
        process_to_delete = self.data_manager.get_process_by_id(process_id)
        if not process_to_delete:
            QMessageBox.warning(self, "오류", f"ID '{process_id}'에 해당하는 프로세스를 찾을 수 없습니다.")
            return

        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{process_to_delete.name}' 프로세스를 정말 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No # 기본 버튼
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted_name = process_to_delete.name # 상태 메시지를 위한 이름 저장
            if self.data_manager.remove_process(process_id):
                self.populate_process_list_slot()
                self.statusBar().showMessage(f"프로세스 '{deleted_name}'이(가) 성공적으로 삭제되었습니다.", 3000)
            else:
                QMessageBox.warning(self, "오류", "프로세스 삭제에 실패했습니다.")

    def handle_launch_button_in_row(self, process_id: str):
        """특정 프로세스 ID에 대한 '실행' 버튼 클릭을 처리합니다."""
        process_to_launch = self.data_manager.get_process_by_id(process_id)
        if not process_to_launch:
            QMessageBox.warning(self, "오류", f"ID '{process_id}'에 해당하는 프로세스를 찾을 수 없습니다.")
            return
        if not process_to_launch.launch_path:
            QMessageBox.warning(self, "오류", f"'{process_to_launch.name}' 프로세스에 설정된 실행 경로가 없습니다.")
            return

        if self.launcher.launch_process(process_to_launch.launch_path):
            self.system_notifier.send_notification(
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
        """새 관리 프로세스를 추가하는 대화 상자를 엽니다."""
        dialog = ProcessDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                name = data["name"].strip()
                monitoring_path = data["monitoring_path"]
                if not name and monitoring_path: # 비어있는 경우 이름 자동 생성
                    base_name = os.path.basename(monitoring_path)
                    name = os.path.splitext(base_name)[0] or "새 프로세스"

                new_process = ManagedProcess(
                    name=name,
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

    def closeEvent(self, event: QEvent):
        """창 닫기 이벤트를 처리하며, 일반적으로 트레이로 숨깁니다."""
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.handle_window_close_event(event)
        else:
            # 어떤 이유로 tray_manager를 사용할 수 없는 경우의 대체 처리
            event.ignore()
            self.hide()

    def initiate_quit_sequence(self):
        """애플리케이션 종료 절차를 시작합니다."""
        print("애플리케이션 종료 절차 시작...")
        if hasattr(self, 'monitor_timer') and self.monitor_timer.isActive():
            self.monitor_timer.stop()
        if hasattr(self, 'scheduler_timer') and self.scheduler_timer.isActive():
            self.scheduler_timer.stop()
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.hide_tray_icon() # 트레이 아이콘 제거 확인

        # InstanceManager의 리소스 정리 호출
        if self._instance_manager and hasattr(self._instance_manager, 'cleanup'):
            print("InstanceManager 리소스 정리 호출 중...")
            self._instance_manager.cleanup()

        app_instance = QApplication.instance()
        if app_instance:
            print("QApplication.quit() 호출 중...")
            app_instance.quit()

# 애플리케이션의 주 실행 로직 (instance_manager에 의해 호출됨)
def start_main_application(instance_manager: SingleInstanceApplication):
    """메인 Qt 애플리케이션을 설정하고 실행합니다."""
    app = QApplication(sys.argv)
    app.setApplicationName("숙제 관리자")
    app.setOrganizationName("MyHomeworkHelperOrg") # 더 고유하거나 설정 가능하도록 만드는 것을 고려
    app.setQuitOnLastWindowClosed(False) # 트레이 아이콘 기능에 필수적

    data_folder_name = "homework_helper_data"
    if getattr(sys, 'frozen', False): # 번들된 실행 파일로 실행 중인지 확인
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(application_path, data_folder_name)

    data_manager_instance = DataManager(data_folder=data_path)

    # MainWindow 생성 시 instance_manager 참조 전달
    main_window = MainWindow(data_manager_instance, instance_manager=instance_manager)

    # 주 인스턴스이므로 IPC 서버 시작 (MainWindow 인스턴스가 생성된 후 호출)
    # 이를 통해 다른 인스턴스가 이 메인 인스턴스에 신호를 보낼 수 있음
    instance_manager.start_ipc_server(main_window_to_activate=main_window)

    main_window.show()
    exit_code = app.exec()

    # 정리는 주로 initiate_quit_sequence에서 처리됨.
    # 만약 app.exec()가 반환되기 전에 initiate_quit_sequence 호출이 보장된다면
    # (예: QMainWindow.closeEvent -> tray_manager.quit_action -> initiate_quit_sequence 경로)
    # 이 경우 _instance_manager에 대한 명시적인 정리는 중복될 수 있음.
    # 그러나 다른 방법으로 앱이 종료될 경우를 대비해 정리하는 것이 좋음.
    # 현재로서는 initiate_quit_sequence가 이를 처리한다고 가정.
    print(f"애플리케이션 종료 코드: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    # instance_manager의 래퍼 함수를 사용하여 애플리케이션 실행
    # 이를 통해 애플리케이션의 단일 인스턴스만 실행되도록 보장.
    run_with_single_instance_check(
        application_name="숙제 관리자", # IPC를 위해 QApplication.applicationName()과 일치해야 함
        main_app_start_callback=start_main_application
    )