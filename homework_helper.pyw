import sys
import datetime
import os
import functools
from typing import List, Optional, Dict, Any

# PyQt6 임포트
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QWidget,
    QHeaderView, QPushButton, QSizePolicy, QFileIconProvider, QAbstractItemView,
    QMessageBox, QMenu, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl, QEvent
from PyQt6.QtGui import QAction, QIcon, QColor, QDesktopServices

# --- 로컬 모듈 임포트 ---
from dialogs import ProcessDialog, GlobalSettingsDialog, NumericTableWidgetItem, WebShortcutDialog
from tray_manager import TrayManager
from gui_notification_handler import GuiNotificationHandler
from instance_manager import run_with_single_instance_check, SingleInstanceApplication

# --- 기타 로컬 유틸리티/데이터 모듈 임포트 ---
from data_manager import DataManager
from data_models import ManagedProcess, GlobalSettings, WebShortcut
from process_utils import get_qicon_for_file
from windows_utils import set_startup_registry
from launcher import Launcher
from notifier import Notifier
from scheduler import Scheduler, PROC_STATE_INCOMPLETE, PROC_STATE_COMPLETED, PROC_STATE_RUNNING

class MainWindow(QMainWindow):
    INSTANCE = None # 다른 모듈에서 메인 윈도우 인스턴스에 접근하기 위함
    request_table_refresh_signal = pyqtSignal() # 테이블 새로고침 요청 시그널

    # UI 색상 정의
    COLOR_INCOMPLETE = QColor("red")      # 미완료 상태 색상
    COLOR_COMPLETED = QColor("green")     # 완료 상태 색상
    COLOR_RUNNING = QColor("yellow")      # 실행 중 상태 색상
    COLOR_WEB_BTN_RED = QColor("red")     # 웹 버튼 (리셋 필요) 색상
    COLOR_WEB_BTN_GREEN = QColor("green") # 웹 버튼 (리셋 완료) 색상

    # 테이블 컬럼 인덱스 정의
    COL_ICON = 0
    COL_NAME = 1
    COL_LAST_PLAYED = 2
    COL_LAUNCH_BTN = 3
    COL_STATUS = 4
    TOTAL_COLUMNS = 5 # 전체 컬럼 개수 (0부터 시작하므로 5개면 range(6) 대신 5)

    def __init__(self, data_manager: DataManager, instance_manager: Optional[SingleInstanceApplication] = None):
        super().__init__()
        MainWindow.INSTANCE = self
        self.data_manager = data_manager
        self._instance_manager = instance_manager # 종료 시 정리를 위해 인스턴스 매니저 참조 저장
        self.launcher = Launcher()

        from process_monitor import ProcessMonitor # 순환 참조 방지를 위한 동적 임포트
        self.process_monitor = ProcessMonitor(self.data_manager)

        self.system_notifier = Notifier(QApplication.applicationName()) # 시스템 알림 객체 생성
        self.gui_notification_handler = GuiNotificationHandler(self) # GUI 알림 처리기 생성
        # 시스템 알림 콜백을 GUI 알림 처리기에 연결
        if hasattr(self.system_notifier, 'main_window_activated_callback'):
            self.system_notifier.main_window_activated_callback = self.gui_notification_handler.process_system_notification_activation

        self.scheduler = Scheduler(self.data_manager, self.system_notifier, self.process_monitor) # 스케줄러 객체 생성

        self.setWindowTitle(QApplication.applicationName() or "숙제 관리자") # 창 제목 설정
        self.setMinimumWidth(500) # 최소 너비 설정
        self.setGeometry(100, 100, 500, 400) # 창 초기 위치 및 크기 설정 (웹 버튼 고려하여 너비 확장)
        self._set_window_icon() # 창 아이콘 설정
        self.tray_manager = TrayManager(self) # 트레이 아이콘 관리자 생성
        self._create_menu_bar() # 메뉴 바 생성

        # --- UI 구성 ---
        central_widget = QWidget(self) # 중앙 위젯 생성
        self.setCentralWidget(central_widget) # 중앙 위젯 설정
        main_layout = QVBoxLayout(central_widget) # 메인 수직 레이아웃 생성

        # 상단 버튼 영역 레이아웃 (게임 추가 버튼 + 동적 웹 버튼들 + 웹 바로가기 추가 버튼)
        self.top_button_area_layout = QHBoxLayout() # 수평 레이아웃
        self.add_game_button = QPushButton("새 게임 추가") # '새 게임 추가' 버튼 생성
        self.add_game_button.clicked.connect(self.open_add_process_dialog) # 버튼 클릭 시그널 연결
        self.top_button_area_layout.addWidget(self.add_game_button) # 레이아웃에 버튼 추가
        self.top_button_area_layout.addStretch(1) # 버튼들 사이의 공간 확장

        self.dynamic_web_buttons_layout = QHBoxLayout() # 동적 웹 버튼들을 위한 수평 레이아웃
        self.top_button_area_layout.addLayout(self.dynamic_web_buttons_layout) # 상단 버튼 영역에 동적 웹 버튼 레이아웃 추가

        self.add_web_shortcut_button = QPushButton("+") # 웹 바로가기 추가 버튼 생성
        self.add_web_shortcut_button.setToolTip("새로운 웹 바로 가기 버튼을 추가합니다.") # 툴팁 설정

        # '+' 버튼 크기를 텍스트에 맞게 조절
        font_metrics = self.add_web_shortcut_button.fontMetrics()
        text_width = font_metrics.horizontalAdvance(" + ") # 텍스트 너비 계산 (양 옆 공백 포함)
        icon_button_size = text_width + 8 # 아이콘 버튼 크기 (여유 공간 추가)
        self.add_web_shortcut_button.setFixedSize(icon_button_size, icon_button_size) # 버튼 크기 고정

        self.add_web_shortcut_button.clicked.connect(self._open_add_web_shortcut_dialog) # 버튼 클릭 시그널 연결
        self.top_button_area_layout.addWidget(self.add_web_shortcut_button) # 상단 버튼 영역에 웹 바로가기 추가 버튼 추가
        main_layout.addLayout(self.top_button_area_layout) # 메인 레이아웃에 상단 버튼 영역 추가

        # 프로세스 테이블 설정
        self.process_table = QTableWidget() # 테이블 위젯 생성
        self.process_table.setColumnCount(self.TOTAL_COLUMNS) # 컬럼 개수 설정
        self.process_table.setHorizontalHeaderLabels(["", "이름", "마지막 플레이", "실행", "상태"]) # 헤더 라벨 설정
        self._configure_table_header() # 테이블 헤더 상세 설정
        self.process_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # 편집 불가 설정
        self.process_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection) # 선택 불가 설정
        self.process_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu) # 컨텍스트 메뉴 정책 설정
        self.process_table.customContextMenuRequested.connect(self.show_table_context_menu) # 컨텍스트 메뉴 요청 시그널 연결
        main_layout.addWidget(self.process_table) # 메인 레이아웃에 테이블 추가

        # 초기 데이터 로드 및 UI 업데이트
        self.populate_process_list() # 프로세스 목록 채우기
        self._load_and_display_web_buttons() # 웹 바로가기 버튼 로드 및 표시
        self._adjust_window_height_to_table() # 테이블 내용에 맞게 창 높이 조절

        # 시그널 및 타이머 설정
        self.request_table_refresh_signal.connect(self.populate_process_list_slot) # 테이블 새로고침 시그널 연결
        self.monitor_timer = QTimer(self); self.monitor_timer.timeout.connect(self.run_process_monitor_check); self.monitor_timer.start(1000) # 프로세스 모니터 타이머 (1초)
        self.scheduler_timer = QTimer(self); self.scheduler_timer.timeout.connect(self.run_scheduler_check); self.scheduler_timer.start(1000) # 스케줄러 타이머 (1초)

        self.web_button_refresh_timer = QTimer(self) # 웹 버튼 상태 새로고침 타이머
        self.web_button_refresh_timer.timeout.connect(self._refresh_web_button_states) # 타이머 타임아웃 시그널 연결
        self.web_button_refresh_timer.start(1000 * 60) # 1분마다 웹 버튼 상태 갱신 (1000ms * 60)

        self.statusBar().showMessage("준비 완료.", 5000) # 상태 표시줄 메시지 설정
        self.apply_startup_setting() # 시작 프로그램 설정 적용

    def changeEvent(self, event: QEvent):
        """창 상태 변경 이벤트를 처리합니다 (최소화 시 트레이로 보내는 로직 포함)."""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized: # 창이 최소화 상태로 변경될 때
                if hasattr(self, 'tray_manager') and self.tray_manager.is_tray_icon_visible(): # 트레이 아이콘이 보이는 경우
                    self.tray_manager.handle_minimize_event() # 트레이 관리자에게 최소화 처리 위임
        super().changeEvent(event)

    def activate_and_show(self):
        """IPC 등을 통해 외부에서 창을 활성화하고 표시하도록 요청받았을 때 호출됩니다."""
        print("MainWindow: activate_and_show() 호출됨.")
        self.showNormal() # 창을 보통 크기로 표시 (최소화/숨김 상태에서 복원)
        self.activateWindow() # 창 활성화 (포커스 가져오기)
        self.raise_() # 창을 최상단으로 올림

    def open_webpage(self, url: str):
        """주어진 URL을 기본 웹 브라우저에서 엽니다."""
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, "URL 열기 실패", f"다음 URL을 여는 데 실패했습니다:\n{url}")

    def _set_window_icon(self):
        """창 아이콘을 설정합니다. 'app_icon.png' 파일이 있으면 사용하고, 없으면 표준 아이콘을 사용합니다."""
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

    def _configure_table_header(self):
        """테이블 헤더의 크기 조절 모드 및 컬럼 너비를 설정합니다."""
        h = self.process_table.horizontalHeader()
        h.setSectionResizeMode(self.COL_ICON, QHeaderView.ResizeMode.ResizeToContents) # 아이콘 컬럼: 내용에 맞게
        h.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch) # 이름 컬럼: 남은 공간 채우기
        h.setSectionResizeMode(self.COL_LAST_PLAYED, QHeaderView.ResizeMode.ResizeToContents) # 마지막 플레이 컬럼: 내용에 맞게
        h.setSectionResizeMode(self.COL_LAUNCH_BTN, QHeaderView.ResizeMode.ResizeToContents) # 실행 버튼 컬럼: 내용에 맞게
        self.process_table.setColumnWidth(self.COL_ICON, 40) # 아이콘 컬럼 너비 고정
        self.process_table.setColumnWidth(self.COL_STATUS, 60) # 상태 컬럼 너비 고정

    def _create_menu_bar(self):
        """메뉴 바와 메뉴 항목들을 생성합니다."""
        mb = self.menuBar(); fm = mb.addMenu("파일(&F)") # 파일 메뉴
        try:
            # 표준 종료 아이콘 가져오기 시도
            ei_px = self.style().standardPixmap(QStyle.StandardPixmap.SP_DialogCloseButton)
            ei = QIcon.fromTheme("app-exit", QIcon(ei_px)) # 테마 아이콘 우선, 없으면 표준 아이콘 사용
        except AttributeError: # 예외 발생 시 빈 아이콘 사용 (안전 장치)
            ei = QIcon()
        ea = QAction(ei, "종료(&X)", self); ea.setShortcut("Ctrl+Q"); ea.triggered.connect(self.initiate_quit_sequence); fm.addAction(ea) # 종료 액션

        sm = mb.addMenu("설정(&S)") # 설정 메뉴
        gsa = QAction("전역 설정 변경...", self); gsa.triggered.connect(self.open_global_settings_dialog); sm.addAction(gsa) # 전역 설정 변경 액션

    def open_global_settings_dialog(self):
        """전역 설정 대화 상자를 엽니다."""
        cur_gs = self.data_manager.global_settings # 현재 전역 설정 가져오기
        dlg = GlobalSettingsDialog(cur_gs, self) # 대화 상자 생성
        if dlg.exec(): # 대화 상자 실행 및 'OK' 클릭 시
            upd_gs = dlg.get_updated_settings() # 업데이트된 설정 가져오기
            self.data_manager.global_settings = upd_gs # 데이터 매니저에 설정 업데이트
            self.data_manager.save_global_settings() # 설정 저장
            self.statusBar().showMessage("전역 설정 저장됨.", 3000) # 상태 표시줄 메시지
            self.apply_startup_setting() # 시작 프로그램 설정 적용
            self.populate_process_list_slot() # 프로세스 목록 새로고침
            self._refresh_web_button_states() # 웹 버튼 상태 새로고침 (전역 설정 변경이 웹 버튼에 영향을 줄 수 있는 경우)

    def apply_startup_setting(self):
        """시작 프로그램 자동 실행 설정을 적용합니다."""
        run = self.data_manager.global_settings.run_on_startup # 자동 실행 여부 가져오기
        if set_startup_registry(run): # 레지스트리 설정 시도
            self.statusBar().showMessage(f"시작 시 자동 실행: {'활성' if run else '비활성'}", 3000)
        else:
            self.statusBar().showMessage("자동 실행 설정 중 문제 발생 가능.", 3000)

    def run_process_monitor_check(self):
        """실행 중인 프로세스를 확인하고 상태 변경 시 테이블을 새로고침합니다."""
        if self.process_monitor.check_and_update_statuses(): # 상태 변경 감지 시
            self.statusBar().showMessage("프로세스 상태 변경 감지됨.", 2000)
            self.request_table_refresh_signal.emit() # 테이블 새로고침 시그널 발생

    def run_scheduler_check(self):
        """스케줄러 검사를 실행하고 게임 테이블 및 웹 버튼 상태를 새로고침합니다."""
        self.scheduler.run_all_checks() # 게임 관련 스케줄 검사
        self.request_table_refresh_signal.emit() # 게임 테이블 새로고침
        # 웹 버튼 상태는 별도 타이머(_refresh_web_button_states)로 주기적으로 체크하므로 여기서 호출하지 않음

    def populate_process_list_slot(self):
        """테이블 새로고침 시그널에 연결된 슬롯입니다."""
        self.populate_process_list()

    def populate_process_list(self):
        """관리 대상 프로세스 목록을 테이블에 채웁니다."""
        self.process_table.setSortingEnabled(False) # 정렬 기능 임시 비활성화
        processes = self.data_manager.managed_processes # 관리 대상 프로세스 목록 가져오기
        self.process_table.setRowCount(len(processes)) # 행 개수 설정

        now_dt = datetime.datetime.now() # 현재 시각
        gs = self.data_manager.global_settings # 전역 설정
        palette = self.process_table.palette() # 테이블 팔레트
        df_bg, df_fg = palette.base(), palette.text() # 기본 배경색 및 글자색

        for r, p in enumerate(processes): # 각 프로세스에 대해 반복
            # 아이콘 컬럼
            icon_item = QTableWidgetItem()
            qi = get_qicon_for_file(p.monitoring_path) # 파일 경로로부터 아이콘 가져오기
            if qi and not qi.isNull(): icon_item.setIcon(qi)
            self.process_table.setItem(r, self.COL_ICON, icon_item); icon_item.setBackground(df_bg); icon_item.setForeground(df_fg)

            # 이름 컬럼 (UserRole에 ID 저장)
            name_item = QTableWidgetItem(p.name)
            name_item.setData(Qt.ItemDataRole.UserRole, p.id) # UserRole에 프로세스 ID 저장
            self.process_table.setItem(r, self.COL_NAME, name_item); name_item.setBackground(df_bg); name_item.setForeground(df_fg)

            # 마지막 플레이 컬럼
            lp_str = "기록 없음"
            if p.last_played_timestamp:
                try: lp_str = datetime.datetime.fromtimestamp(p.last_played_timestamp).strftime("%m월 %d일 %H시 %M분")
                except: lp_str = "변환 오류" # 타임스탬프 변환 오류 시
            lp_item = QTableWidgetItem(lp_str)
            self.process_table.setItem(r, self.COL_LAST_PLAYED, lp_item); lp_item.setBackground(df_bg); lp_item.setForeground(df_fg)

            # 실행 버튼 컬럼
            btn = QPushButton("실행")
            btn.clicked.connect(functools.partial(self.handle_launch_button_in_row, p.id)) # 버튼 클릭 시그널 연결
            self.process_table.setCellWidget(r, self.COL_LAUNCH_BTN, btn) # 셀에 버튼 위젯 설정

            # 상태 컬럼
            st_str = self.scheduler.determine_process_visual_status(p, now_dt, gs) # 시각적 상태 결정
            st_item = QTableWidgetItem(st_str)
            st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) # 텍스트 가운데 정렬
            self.process_table.setItem(r, self.COL_STATUS, st_item)
            st_item.setForeground(df_fg) # 기본 글자색 설정

            # 상태에 따른 배경색 설정
            if st_str == PROC_STATE_RUNNING: st_item.setBackground(self.COLOR_RUNNING); st_item.setForeground(QColor("black")) # 실행 중: 노란색 배경, 검은색 글자
            elif st_str == PROC_STATE_INCOMPLETE: st_item.setBackground(self.COLOR_INCOMPLETE) # 미완료: 빨간색 배경
            elif st_str == PROC_STATE_COMPLETED: st_item.setBackground(self.COLOR_COMPLETED) # 완료: 초록색 배경
            else: st_item.setBackground(df_bg) # 그 외: 기본 배경색

        self.process_table.setSortingEnabled(True) # 정렬 기능 다시 활성화
        self.process_table.sortByColumn(self.COL_NAME, Qt.SortOrder.AscendingOrder) # 이름 컬럼 기준 오름차순 정렬
        self.process_table.resizeColumnsToContents() # 컬럼 너비 내용에 맞게 조절
        self.process_table.horizontalHeader().setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch) # 이름 컬럼은 남은 공간 채우도록 설정

    def show_table_context_menu(self, pos): # 게임 테이블용 컨텍스트 메뉴
        """게임 테이블의 항목에 대한 컨텍스트 메뉴를 표시합니다."""
        item = self.process_table.itemAt(pos) # 클릭 위치의 아이템 가져오기
        if not item: return # 아이템 없으면 반환

        pid = self.process_table.item(item.row(), self.COL_NAME).data(Qt.ItemDataRole.UserRole) # 선택된 행의 프로세스 ID 가져오기
        if not pid: return # ID 없으면 반환

        menu = QMenu(self) # 컨텍스트 메뉴 생성
        edit_act = QAction("편집", self) # 편집 액션
        del_act = QAction("삭제", self) # 삭제 액션

        edit_act.triggered.connect(functools.partial(self.handle_edit_action_for_row, pid)) # 편집 액션 시그널 연결
        del_act.triggered.connect(functools.partial(self.handle_delete_action_for_row, pid)) # 삭제 액션 시그널 연결

        menu.addActions([edit_act, del_act]) # 메뉴에 액션 추가
        menu.exec(self.process_table.mapToGlobal(pos)) # 컨텍스트 메뉴 표시

    def handle_edit_action_for_row(self, pid:str): # 게임 수정
        """선택된 게임 프로세스의 정보를 수정하는 대화 상자를 엽니다."""
        p_edit = self.data_manager.get_process_by_id(pid) # ID로 프로세스 정보 가져오기
        if not p_edit: QMessageBox.warning(self, "오류", f"ID '{pid}' 프로세스 없음."); return

        dialog = ProcessDialog(self, existing_process=p_edit) # 프로세스 수정 대화 상자 생성
        if dialog.exec(): # 'OK' 클릭 시
            data = dialog.get_data() # 수정된 데이터 가져오기
            if data:
                name = data["name"].strip() or p_edit.name # 이름이 비었으면 기존 이름 사용
                # 업데이트된 프로세스 객체 생성
                upd_p = ManagedProcess(id=p_edit.id, name=name, monitoring_path=data["monitoring_path"],
                                       launch_path=data["launch_path"], server_reset_time_str=data["server_reset_time_str"],
                                       user_cycle_hours=data["user_cycle_hours"], mandatory_times_str=data["mandatory_times_str"],
                                       is_mandatory_time_enabled=data["is_mandatory_time_enabled"],
                                       last_played_timestamp=p_edit.last_played_timestamp) # 마지막 플레이 시간은 유지
                if self.data_manager.update_process(upd_p): # 프로세스 정보 업데이트
                    self.populate_process_list_slot() # 테이블 새로고침
                    self.statusBar().showMessage(f"'{upd_p.name}' 수정 완료.", 3000)
                else: QMessageBox.warning(self, "오류", "프로세스 수정 실패.")

    def handle_delete_action_for_row(self, pid:str): # 게임 삭제
        """선택된 게임 프로세스를 삭제합니다."""
        p_del = self.data_manager.get_process_by_id(pid) # ID로 프로세스 정보 가져오기
        if not p_del: QMessageBox.warning(self, "오류", f"ID '{pid}' 프로세스 없음."); return

        # 삭제 확인 대화 상자 표시
        reply = QMessageBox.question(self, "삭제 확인", f"'{p_del.name}' 삭제?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No) # 기본 선택은 'No'
        if reply == QMessageBox.StandardButton.Yes: # 'Yes' 클릭 시
            if self.data_manager.remove_process(pid): # 프로세스 삭제
                self.populate_process_list_slot() # 테이블 새로고침
                self.statusBar().showMessage(f"'{p_del.name}' 삭제 완료.", 3000)
            else: QMessageBox.warning(self, "오류", "프로세스 삭제 실패.")

    def handle_launch_button_in_row(self, pid:str): # 게임 실행
        """선택된 게임 프로세스를 실행합니다."""
        p_launch = self.data_manager.get_process_by_id(pid) # ID로 프로세스 정보 가져오기
        if not p_launch: QMessageBox.warning(self, "오류", f"ID '{pid}' 프로세스 없음."); return
        if not p_launch.launch_path: QMessageBox.warning(self, "오류", f"'{p_launch.name}' 실행 경로 없음."); return

        if self.launcher.launch_process(p_launch.launch_path): # 프로세스 실행 시도
            self.system_notifier.send_notification(title="프로세스 실행", message=f"'{p_launch.name}' 실행함.", task_id_to_highlight=None)
            self.statusBar().showMessage(f"'{p_launch.name}' 실행 시도.", 3000)
        else: # 실행 실패 시
            self.system_notifier.send_notification(title="실행 실패", message=f"'{p_launch.name}' 실행 실패. 로그 확인.", task_id_to_highlight=None)
            self.statusBar().showMessage(f"'{p_launch.name}' 실행 실패.", 3000)

    def open_add_process_dialog(self): # "새 게임 추가" 버튼에 연결
        """새 게임 프로세스를 추가하는 대화 상자를 엽니다."""
        dialog = ProcessDialog(self) # 새 프로세스 추가 대화 상자 생성
        if dialog.exec(): # 'OK' 클릭 시
            data = dialog.get_data() # 입력 데이터 가져오기
            if data:
                name = data["name"].strip()
                # 이름이 비어있고 모니터링 경로가 있으면 파일명으로 자동 생성
                if not name and data["monitoring_path"]:
                    name = os.path.splitext(os.path.basename(data["monitoring_path"]))[0] or "새 프로세스"
                # 새 프로세스 객체 생성
                new_p = ManagedProcess(name=name, monitoring_path=data["monitoring_path"],
                                       launch_path=data["launch_path"], server_reset_time_str=data["server_reset_time_str"],
                                       user_cycle_hours=data["user_cycle_hours"], mandatory_times_str=data["mandatory_times_str"],
                                       is_mandatory_time_enabled=data["is_mandatory_time_enabled"])
                self.data_manager.add_process(new_p) # 데이터 매니저에 프로세스 추가
                self.populate_process_list_slot() # 테이블 새로고침
                self.statusBar().showMessage(f"'{new_p.name}' 추가 완료.", 3000)

    # --- 웹 바로 가기 버튼 관련 메소드들 ---
    def _clear_layout(self, layout: QHBoxLayout):
        """주어진 QHBoxLayout의 모든 위젯을 제거하고 삭제합니다."""
        if layout is not None:
            while layout.count(): # 레이아웃에 아이템이 있는 동안 반복
                item = layout.takeAt(0) # 첫 번째 아이템 가져오기 (제거됨)
                widget = item.widget() # 아이템에서 위젯 가져오기
                if widget is not None:
                    widget.deleteLater() # 위젯 나중에 삭제 (메모리 누수 방지)

    def _determine_web_button_state(self, shortcut: WebShortcut, current_dt: datetime.datetime) -> str:
        """웹 바로가기 버튼의 현재 상태 (RED, GREEN, DEFAULT)를 결정합니다."""
        if not shortcut.refresh_time_str: return "DEFAULT" # 초기화 시간 없으면 기본 상태

        try:
            # 문자열 형식의 초기화 시간을 datetime.time 객체로 변환
            rt_hour, rt_minute = map(int, shortcut.refresh_time_str.split(':'))
            refresh_time_today_obj = datetime.time(rt_hour, rt_minute)
        except (ValueError, TypeError): # 변환 실패 시 기본 상태
            return "DEFAULT"

        # 오늘의 초기화 이벤트 시각
        todays_refresh_event_dt = datetime.datetime.combine(current_dt.date(), refresh_time_today_obj)
        # 마지막 초기화 타임스탬프 (없으면 None)
        last_reset_dt = datetime.datetime.fromtimestamp(shortcut.last_reset_timestamp) if shortcut.last_reset_timestamp else None

        if current_dt >= todays_refresh_event_dt: # 현재 시각이 오늘의 초기화 시각 이후인 경우
            # 마지막 초기화가 없거나, 오늘의 초기화 시각 이전이면 RED (리셋 필요)
            # 그렇지 않으면 GREEN (오늘 리셋 완료)
            return "RED" if last_reset_dt is None or last_reset_dt < todays_refresh_event_dt else "GREEN"
        else: # 현재 시각이 오늘의 초기화 시각 이전인 경우
            if last_reset_dt is None: return "DEFAULT" # 마지막 초기화 기록 없으면 기본
            # 어제의 초기화 이벤트 시각
            yesterdays_refresh_event_dt = datetime.datetime.combine(current_dt.date() - datetime.timedelta(days=1), refresh_time_today_obj)
            # 마지막 초기화가 어제의 초기화 시각 이후면 GREEN (어제 리셋 완료)
            # 그렇지 않으면 DEFAULT (어제 리셋 안 함 또는 해당 없음)
            return "GREEN" if last_reset_dt >= yesterdays_refresh_event_dt else "DEFAULT"

    def _apply_button_style(self, button: QPushButton, state: str):
        """버튼 상태에 따라 스타일시트를 적용합니다."""
        button.setStyleSheet("") # 기존 스타일 초기화
        if state == "RED":
            button.setStyleSheet(f"background-color: {self.COLOR_WEB_BTN_RED.name()};") # 빨간색 배경
        elif state == "GREEN":
            button.setStyleSheet(f"background-color: {self.COLOR_WEB_BTN_GREEN.name()};") # 초록색 배경

    def _refresh_web_button_states(self):
        """동적으로 생성된 모든 웹 바로가기 버튼의 상태를 새로고침합니다."""
        # print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 웹 버튼 상태 새로고침") # 디버그용 로그
        current_dt = datetime.datetime.now()
        for i in range(self.dynamic_web_buttons_layout.count()): # 레이아웃 내 모든 위젯에 대해 반복
            widget = self.dynamic_web_buttons_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton): # 위젯이 QPushButton인 경우
                button = widget
                shortcut_id = button.property("shortcut_id") # 버튼 속성에서 바로가기 ID 가져오기
                if shortcut_id:
                    shortcut = self.data_manager.get_web_shortcut_by_id(shortcut_id) # ID로 바로가기 정보 가져오기
                    if shortcut:
                        state = self._determine_web_button_state(shortcut, current_dt) # 상태 결정
                        self._apply_button_style(button, state) # 스타일 적용

    def _load_and_display_web_buttons(self):
        """저장된 웹 바로가기 정보를 불러와 동적 버튼으로 UI에 표시합니다."""
        self._clear_layout(self.dynamic_web_buttons_layout) # 기존 버튼들 모두 제거
        shortcuts = self.data_manager.get_web_shortcuts() # 모든 웹 바로가기 정보 가져오기
        current_dt = datetime.datetime.now()

        for sc_data in shortcuts: # 각 바로가기에 대해 버튼 생성
            button = QPushButton(sc_data.name) # 버튼 텍스트는 바로가기 이름
            # 버튼 클릭 시 _handle_web_button_clicked 메소드 호출 (ID와 URL 전달)
            button.clicked.connect(functools.partial(self._handle_web_button_clicked, sc_data.id, sc_data.url))
            button.setProperty("shortcut_id", sc_data.id) # 버튼에 바로가기 ID 저장 (나중에 참조용)
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu) # 컨텍스트 메뉴 사용 설정
            # 컨텍스트 메뉴 요청 시 _show_web_button_context_menu 메소드 호출 (버튼 객체 전달)
            button.customContextMenuRequested.connect(functools.partial(self._show_web_button_context_menu, button))

            state = self._determine_web_button_state(sc_data, current_dt) # 버튼 초기 상태 결정
            self._apply_button_style(button, state) # 스타일 적용
            self.dynamic_web_buttons_layout.addWidget(button) # 레이아웃에 버튼 추가

    def _handle_web_button_clicked(self, shortcut_id: str, url: str):
        """웹 바로가기 버튼 클릭 시 호출됩니다. URL을 열고, 필요한 경우 상태를 업데이트합니다."""
        print(f"웹 버튼 클릭 (ID: {shortcut_id}): {url} 열기 시도")
        shortcut = self.data_manager.get_web_shortcut_by_id(shortcut_id) # 바로가기 정보 가져오기
        if not shortcut: # 바로가기 정보 없으면 경고 후 URL 열기 시도
            QMessageBox.warning(self, "오류", "해당 웹 바로 가기 정보를 찾을 수 없습니다.")
            self.open_webpage(url) # URL 열기 시도
            return

        self.open_webpage(url) # URL 열기

        # 초기화 시간이 설정된 바로가기인 경우, 마지막 초기화 타임스탬프 업데이트
        if shortcut.refresh_time_str:
            shortcut.last_reset_timestamp = datetime.datetime.now().timestamp() # 현재 시각으로 업데이트
            if self.data_manager.update_web_shortcut(shortcut): # 데이터 매니저 통해 정보 업데이트
                print(f"웹 바로 가기 '{shortcut.name}' 상태 업데이트 (last_reset_timestamp).")
                self._refresh_web_button_states() # 버튼 상태 즉시 새로고침
            else:
                print(f"웹 바로 가기 '{shortcut.name}' 상태 업데이트 실패.")

    def _open_add_web_shortcut_dialog(self):
        """새 웹 바로가기를 추가하는 대화 상자를 엽니다."""
        dialog = WebShortcutDialog(self) # 웹 바로가기 추가/편집 대화 상자 생성
        if dialog.exec(): # 'OK' 클릭 시
            data = dialog.get_data() # 입력 데이터 가져오기
            if data:
                # 새 웹 바로가기 객체 생성
                new_shortcut = WebShortcut(name=data["name"], url=data["url"],
                                           refresh_time_str=data.get("refresh_time_str")) # refresh_time_str은 선택 사항
                if self.data_manager.add_web_shortcut(new_shortcut): # 데이터 매니저에 추가
                    self._load_and_display_web_buttons() # 버튼 목록 새로고침
                    self.statusBar().showMessage(f"웹 바로 가기 '{new_shortcut.name}' 추가됨.", 3000)
                else:
                    QMessageBox.warning(self, "추가 실패", "웹 바로 가기 추가에 실패했습니다.")

    def _show_web_button_context_menu(self, button: QPushButton, position):
        """웹 바로가기 버튼의 컨텍스트 메뉴 (편집, 삭제)를 표시합니다."""
        shortcut_id = button.property("shortcut_id") # 버튼에서 바로가기 ID 가져오기
        if not shortcut_id: return

        menu = QMenu(self) # 컨텍스트 메뉴 생성
        edit_action = QAction("편집", self) # 편집 액션
        delete_action = QAction("삭제", self) # 삭제 액션

        # 액션 트리거 시 해당 메소드 호출 (바로가기 ID 전달)
        edit_action.triggered.connect(functools.partial(self._edit_web_shortcut, shortcut_id))
        delete_action.triggered.connect(functools.partial(self._delete_web_shortcut, shortcut_id))

        menu.addActions([edit_action, delete_action]) # 메뉴에 액션 추가
        menu.exec(button.mapToGlobal(position)) # 컨텍스트 메뉴 표시 (버튼 기준 전역 좌표)

    def _edit_web_shortcut(self, shortcut_id: str):
        """선택된 웹 바로가기를 편집하는 대화 상자를 엽니다."""
        shortcut_to_edit = self.data_manager.get_web_shortcut_by_id(shortcut_id) # 편집할 바로가기 정보 가져오기
        if not shortcut_to_edit:
            QMessageBox.warning(self, "오류", "편집할 웹 바로 가기를 찾을 수 없습니다.")
            return

        # 기존 데이터로 채워진 웹 바로가기 편집 대화 상자 생성
        dialog = WebShortcutDialog(self, shortcut_data=shortcut_to_edit.to_dict())
        if dialog.exec(): # 'OK' 클릭 시
            data = dialog.get_data() # 수정된 데이터 가져오기
            if data:
                # 업데이트된 웹 바로가기 객체 생성 (ID와 마지막 초기화 시간은 유지 또는 조건부 업데이트)
                updated_shortcut = WebShortcut(id=shortcut_id, name=data["name"], url=data["url"],
                                               refresh_time_str=data.get("refresh_time_str"),
                                               last_reset_timestamp=shortcut_to_edit.last_reset_timestamp)
                # 초기화 시간이 제거되면 마지막 초기화 타임스탬프도 제거
                if not updated_shortcut.refresh_time_str:
                    updated_shortcut.last_reset_timestamp = None

                if self.data_manager.update_web_shortcut(updated_shortcut): # 데이터 매니저 통해 정보 업데이트
                    self._load_and_display_web_buttons() # 버튼 목록 새로고침
                    self.statusBar().showMessage(f"웹 바로 가기 '{updated_shortcut.name}' 수정됨.", 3000)
                else:
                    QMessageBox.warning(self, "수정 실패", "웹 바로 가기 수정에 실패했습니다.")

    def _delete_web_shortcut(self, shortcut_id: str):
        """선택된 웹 바로가기를 삭제합니다."""
        shortcut_to_delete = self.data_manager.get_web_shortcut_by_id(shortcut_id) # 삭제할 바로가기 정보 가져오기
        if not shortcut_to_delete:
            QMessageBox.warning(self, "오류", "삭제할 웹 바로 가기를 찾을 수 없습니다.")
            return

        # 삭제 확인 대화 상자 표시
        reply = QMessageBox.question(self, "삭제 확인",
                                     f"웹 바로 가기 '{shortcut_to_delete.name}'을(를) 정말 삭제하시겠습니까?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No) # 기본 선택은 'No'
        if reply == QMessageBox.StandardButton.Yes: # 'Yes' 클릭 시
            if self.data_manager.remove_web_shortcut(shortcut_id): # 데이터 매니저 통해 삭제
                self._load_and_display_web_buttons() # 버튼 목록 새로고침
                self.statusBar().showMessage(f"웹 바로 가기 '{shortcut_to_delete.name}' 삭제됨.", 3000)
            else:
                QMessageBox.warning(self, "삭제 실패", "웹 바로 가기 삭제에 실패했습니다.")

    def closeEvent(self, event: QEvent):
        """창 닫기 이벤트를 처리합니다. 트레이 관리자가 있으면 트레이로 숨깁니다."""
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.handle_window_close_event(event) # 트레이 관리자에게 이벤트 처리 위임
        else: # 트레이 관리자 없으면 기본 동작 (숨기기)
            event.ignore()
            self.hide()

    def initiate_quit_sequence(self):
        """애플리케이션 종료 절차를 시작합니다 (타이머 중지, 아이콘 숨기기, 리소스 정리 등)."""
        print("애플리케이션 종료 절차 시작...")
        # 활성화된 타이머들 중지
        if hasattr(self, 'monitor_timer') and self.monitor_timer.isActive(): self.monitor_timer.stop()
        if hasattr(self, 'scheduler_timer') and self.scheduler_timer.isActive(): self.scheduler_timer.stop()
        if hasattr(self, 'web_button_refresh_timer') and self.web_button_refresh_timer.isActive():
            self.web_button_refresh_timer.stop(); print("웹 버튼 상태 새로고침 타이머 중지됨.")
        # 트레이 아이콘 숨기기
        if hasattr(self, 'tray_manager') and self.tray_manager: self.tray_manager.hide_tray_icon()
        # 인스턴스 매니저 리소스 정리 (단일 인스턴스 실행 관련)
        if self._instance_manager and hasattr(self._instance_manager, 'cleanup'):
            self._instance_manager.cleanup()
        # QApplication 종료
        app_instance = QApplication.instance()
        if app_instance: app_instance.quit()

    def _adjust_window_height_to_table(self):
        """테이블 내용에 맞춰 메인 윈도우의 높이를 자동으로 조절합니다."""
        if not self.centralWidget() or not self.centralWidget().layout():
            return # 중앙 위젯이나 레이아웃 없으면 실행 불가

        # 테이블 행 높이를 내용에 맞게 먼저 조절 (주석 처리됨 - 필요시 활성화)
        # if self.process_table.rowCount() > 0:
        #     self.process_table.resizeRowsToContents()

        table_content_height = 0

        # 1. 수평 헤더 높이 추가
        header = self.process_table.horizontalHeader()
        if header and not header.isHidden(): # 헤더가 존재하고 숨겨지지 않았으면
            table_content_height += header.height()
            # print(f"계산된 헤더 높이: {header.height()}") # 디버그용

        # 2. 모든 행의 높이 합산
        if self.process_table.rowCount() > 0:
            for i in range(self.process_table.rowCount()):
                table_content_height += self.process_table.rowHeight(i)
                # print(f"계산된 행 높이 ({i}): {self.process_table.rowHeight(i)}") # 디버그용
            table_content_height += self.process_table.frameWidth() * 2 # 테이블 테두리 두께 고려
        else: # 행이 없을 경우, 기본 높이 추정치 사용
            default_row_height_approx = self.fontMetrics().height() + 12 # 폰트 높이 + 여백
            table_content_height += default_row_height_approx
            table_content_height += self.process_table.frameWidth() * 2 # 테이블 테두리 두께 고려

        self.process_table.setFixedHeight(table_content_height) # 테이블의 고정 높이 설정
        self.adjustSize() # 창 크기를 내용에 맞게 조절

        # print(f"윈도우 높이 조절됨. 새 높이: {self.height()}, 계산된 테이블 내용 높이: {table_content_height}") # 디버그용

# --- 애플리케이션 실행 로직 ---
def start_main_application(instance_manager: SingleInstanceApplication):
    """메인 애플리케이션을 설정하고 실행합니다."""
    app = QApplication(sys.argv)
    app.setApplicationName("숙제 관리자") # 애플리케이션 이름 설정
    app.setOrganizationName("HomeworkHelperOrg") # 조직 이름 설정 (설정 파일 경로 등에 사용될 수 있음)
    app.setQuitOnLastWindowClosed(False) # 마지막 창이 닫혀도 애플리케이션 종료되지 않도록 설정 (트레이 아이콘 사용 시 필수)

    # 데이터 저장 폴더 경로 설정
    data_folder_name = "homework_helper_data"
    if getattr(sys, 'frozen', False): # PyInstaller 등으로 패키징된 경우
        application_path = os.path.dirname(sys.executable)
    else: # 일반 파이썬 스크립트로 실행된 경우
        application_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(application_path, data_folder_name)
    data_manager_instance = DataManager(data_folder=data_path) # 데이터 매니저 생성

    # 메인 윈도우 생성 (인스턴스 매니저 전달)
    main_window = MainWindow(data_manager_instance, instance_manager=instance_manager)
    # IPC 서버 시작 (다른 인스턴스로부터의 활성화 요청 처리용)
    instance_manager.start_ipc_server(main_window_to_activate=main_window)
    main_window.show() # 메인 윈도우 표시
    exit_code = app.exec() # 애플리케이션 이벤트 루프 시작
    sys.exit(exit_code) # 종료 코드로 시스템 종료

if __name__ == "__main__":
    # 단일 인스턴스 실행 확인 로직을 통해 애플리케이션 시작
    run_with_single_instance_check(
        application_name="숙제 관리자", # QApplication.applicationName()과 일치해야 IPC가 제대로 동작
        main_app_start_callback=start_main_application # 실제 애플리케이션 시작 함수 전달
    )
