# homework_helper.py
import sys
import datetime
import os
import functools
from typing import List, Optional, Dict, Any

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QWidget,
    QHeaderView, QPushButton, QSizePolicy, QFileIconProvider, QAbstractItemView,
    QMessageBox, QMenu, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl, QEvent
from PyQt6.QtGui import QAction, QIcon, QColor, QDesktopServices

# --- Local module imports ---
from dialogs import ProcessDialog, GlobalSettingsDialog, NumericTableWidgetItem, WebShortcutDialog
from tray_manager import TrayManager
from gui_notification_handler import GuiNotificationHandler
from instance_manager import run_with_single_instance_check, SingleInstanceApplication

# --- Other local utility/data module imports ---
from data_manager import DataManager
from data_models import ManagedProcess, GlobalSettings, WebShortcut
from process_utils import get_qicon_for_file
from windows_utils import set_startup_registry
from launcher import Launcher
from notifier import Notifier
from scheduler import Scheduler, PROC_STATE_INCOMPLETE, PROC_STATE_COMPLETED, PROC_STATE_RUNNING

class MainWindow(QMainWindow):
    INSTANCE = None 
    request_table_refresh_signal = pyqtSignal()

    COLOR_INCOMPLETE, COLOR_COMPLETED, COLOR_RUNNING = QColor("red"), QColor("green"), QColor("yellow")
    # 웹 버튼 색상 (연한 색으로 변경)
    COLOR_WEB_BTN_RED = QColor("red")
    COLOR_WEB_BTN_GREEN = QColor("green")
    
    COL_ICON, COL_NAME, COL_LAST_PLAYED, COL_LAUNCH_BTN, COL_STATUS, TOTAL_COLUMNS = range(6)

    def __init__(self, data_manager: DataManager, instance_manager: Optional[SingleInstanceApplication] = None):
        super().__init__()
        MainWindow.INSTANCE = self
        self.data_manager = data_manager
        self._instance_manager = instance_manager 
        self.launcher = Launcher()

        from process_monitor import ProcessMonitor
        self.process_monitor = ProcessMonitor(self.data_manager)

        self.system_notifier = Notifier(QApplication.applicationName())
        self.gui_notification_handler = GuiNotificationHandler(self)
        if hasattr(self.system_notifier, 'main_window_activated_callback'):
            self.system_notifier.main_window_activated_callback = self.gui_notification_handler.process_system_notification_activation
        
        self.scheduler = Scheduler(self.data_manager, self.system_notifier, self.process_monitor)
        
        self.setWindowTitle(QApplication.applicationName() or "숙제 관리자")
        self.setGeometry(100, 100, 500, 400) # 너비 확장 (웹 버튼 고려)
        self._set_window_icon()
        self.tray_manager = TrayManager(self) 
        self._create_menu_bar()

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.top_button_area_layout = QHBoxLayout()
        self.add_game_button = QPushButton("새 게임 추가")
        self.add_game_button.clicked.connect(self.open_add_process_dialog)
        self.top_button_area_layout.addWidget(self.add_game_button)
        self.top_button_area_layout.addStretch(1) 
        
        self.dynamic_web_buttons_layout = QHBoxLayout()
        self.top_button_area_layout.addLayout(self.dynamic_web_buttons_layout)

        self.add_web_shortcut_button = QPushButton("+")
        self.add_web_shortcut_button.setToolTip("새로운 웹 바로 가기 버튼을 추가합니다.")
        
        font_metrics = self.add_web_shortcut_button.fontMetrics()
        text_width = font_metrics.horizontalAdvance(" + ")
        icon_button_size = text_width + 8 
        self.add_web_shortcut_button.setFixedSize(icon_button_size, icon_button_size)
        
        self.add_web_shortcut_button.clicked.connect(self._open_add_web_shortcut_dialog)
        self.top_button_area_layout.addWidget(self.add_web_shortcut_button)
        main_layout.addLayout(self.top_button_area_layout)

        self.process_table = QTableWidget()
        self.process_table.setColumnCount(self.TOTAL_COLUMNS)
        self.process_table.setHorizontalHeaderLabels(["", "이름", "마지막 플레이", "실행", "상태"])
        self._configure_table_header()
        self.process_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.process_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.process_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.process_table.customContextMenuRequested.connect(self.show_table_context_menu)
        main_layout.addWidget(self.process_table)

        self.populate_process_list() 
        self._load_and_display_web_buttons() 

        self.request_table_refresh_signal.connect(self.populate_process_list_slot)
        self.monitor_timer = QTimer(self); self.monitor_timer.timeout.connect(self.run_process_monitor_check); self.monitor_timer.start(10000)
        self.scheduler_timer = QTimer(self); self.scheduler_timer.timeout.connect(self.run_scheduler_check); self.scheduler_timer.start(10000)
        
        self.web_button_refresh_timer = QTimer(self)
        self.web_button_refresh_timer.timeout.connect(self._refresh_web_button_states)
        self.web_button_refresh_timer.start(60 * 1000) # 1분마다 웹 버튼 상태 갱신

        self.statusBar().showMessage("준비 완료.", 5000)
        self.apply_startup_setting()

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                if hasattr(self, 'tray_manager') and self.tray_manager.tray_icon.isVisible():
                    self.tray_manager.handle_minimize_event()
        super().changeEvent(event)

    def activate_and_show(self):
        print("MainWindow: activate_and_show() 호출됨.")
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def open_webpage(self, url: str):
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, "URL 열기 실패", f"다음 URL을 여는 데 실패했습니다:\n{url}")

    def _set_window_icon(self):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.png')
        if os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        else: self.setWindowIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

    def _configure_table_header(self):
        h = self.process_table.horizontalHeader()
        h.setSectionResizeMode(self.COL_ICON, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(self.COL_LAST_PLAYED, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(self.COL_LAUNCH_BTN, QHeaderView.ResizeMode.ResizeToContents)
        self.process_table.setColumnWidth(self.COL_ICON, 40)
        self.process_table.setColumnWidth(self.COL_STATUS, 60)

    def _create_menu_bar(self):
        mb = self.menuBar(); fm = mb.addMenu("파일(&F)")
        try: ei_px = self.style().standardPixmap(QStyle.StandardPixmap.SP_DialogCloseButton); ei = QIcon.fromTheme("app-exit", QIcon(ei_px))
        except AttributeError: ei = QIcon()
        ea = QAction(ei, "종료(&X)", self); ea.setShortcut("Ctrl+Q"); ea.triggered.connect(self.initiate_quit_sequence); fm.addAction(ea)
        sm = mb.addMenu("설정(&S)"); gsa = QAction("전역 설정 변경...", self); gsa.triggered.connect(self.open_global_settings_dialog); sm.addAction(gsa)

    def open_global_settings_dialog(self):
        cur_gs = self.data_manager.global_settings; dlg = GlobalSettingsDialog(cur_gs, self)
        if dlg.exec(): 
            upd_gs = dlg.get_updated_settings()
            self.data_manager.global_settings = upd_gs
            self.data_manager.save_global_settings()
            self.statusBar().showMessage("전역 설정 저장됨.", 3000)
            self.apply_startup_setting()
            self.populate_process_list_slot()
            self._refresh_web_button_states() # 전역 설정 변경이 웹 버튼에도 영향 줄 수 있다면 (현재는 아님)

    def apply_startup_setting(self):
        run = self.data_manager.global_settings.run_on_startup
        if set_startup_registry(run): self.statusBar().showMessage(f"시작 시 자동 실행: {'활성' if run else '비활성'}", 3000)
        else: self.statusBar().showMessage("자동 실행 설정 중 문제 발생 가능.", 3000)

    def run_process_monitor_check(self):
        if self.process_monitor.check_and_update_statuses(): 
            self.statusBar().showMessage("프로세스 상태 변경 감지됨.", 2000)
            self.request_table_refresh_signal.emit()

    def run_scheduler_check(self): 
        self.scheduler.run_all_checks() # 게임 관련 스케줄
        self.request_table_refresh_signal.emit() # 게임 테이블 새로고침
        # 웹 버튼 상태도 여기서 주기적으로 체크할 수 있으나, 별도 타이머 사용 중

    def populate_process_list_slot(self): self.populate_process_list()

    def populate_process_list(self):
        self.process_table.setSortingEnabled(False); processes = self.data_manager.managed_processes; self.process_table.setRowCount(len(processes))
        now_dt = datetime.datetime.now(); gs = self.data_manager.global_settings; palette = self.process_table.palette(); df_bg, df_fg = palette.base(), palette.text()
        for r, p in enumerate(processes):
            icon_item = QTableWidgetItem(); qi = get_qicon_for_file(p.monitoring_path);
            if qi and not qi.isNull(): icon_item.setIcon(qi)
            self.process_table.setItem(r, self.COL_ICON, icon_item); icon_item.setBackground(df_bg); icon_item.setForeground(df_fg)
            name_item = QTableWidgetItem(p.name); name_item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.process_table.setItem(r, self.COL_NAME, name_item); name_item.setBackground(df_bg); name_item.setForeground(df_fg)
            lp_str = "기록 없음";
            if p.last_played_timestamp:
                try: lp_str = datetime.datetime.fromtimestamp(p.last_played_timestamp).strftime("%m월 %d일 %H시 %M분")
                except: lp_str = "변환 오류"
            lp_item = QTableWidgetItem(lp_str); self.process_table.setItem(r, self.COL_LAST_PLAYED, lp_item); lp_item.setBackground(df_bg); lp_item.setForeground(df_fg)
            btn = QPushButton("실행"); btn.clicked.connect(functools.partial(self.handle_launch_button_in_row, p.id)); self.process_table.setCellWidget(r, self.COL_LAUNCH_BTN, btn)
            st_str = self.scheduler.determine_process_visual_status(p,now_dt,gs); st_item = QTableWidgetItem(st_str); st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.process_table.setItem(r, self.COL_STATUS, st_item); st_item.setForeground(df_fg)
            if st_str == PROC_STATE_RUNNING: st_item.setBackground(self.COLOR_RUNNING); st_item.setForeground(QColor("black"))
            elif st_str == PROC_STATE_INCOMPLETE: st_item.setBackground(self.COLOR_INCOMPLETE)
            elif st_str == PROC_STATE_COMPLETED: st_item.setBackground(self.COLOR_COMPLETED)
            else: st_item.setBackground(df_bg)
        self.process_table.setSortingEnabled(True); self.process_table.sortByColumn(self.COL_NAME, Qt.SortOrder.AscendingOrder)
        self.process_table.resizeColumnsToContents(); self.process_table.horizontalHeader().setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)

    def show_table_context_menu(self, pos): # 게임 테이블용 컨텍스트 메뉴
        item = self.process_table.itemAt(pos);
        if not item: return
        pid = self.process_table.item(item.row(), self.COL_NAME).data(Qt.ItemDataRole.UserRole)
        if not pid: return
        menu = QMenu(self); edit_act = QAction("편집", self); del_act = QAction("삭제", self)
        edit_act.triggered.connect(functools.partial(self.handle_edit_action_for_row, pid))
        del_act.triggered.connect(functools.partial(self.handle_delete_action_for_row, pid))
        menu.addActions([edit_act, del_act]); menu.exec(self.process_table.mapToGlobal(pos))

    def handle_edit_action_for_row(self, pid:str): # 게임 수정
        p_edit = self.data_manager.get_process_by_id(pid)
        if not p_edit: QMessageBox.warning(self, "오류", f"ID '{pid}' 프로세스 없음."); return
        dialog = ProcessDialog(self, existing_process=p_edit)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                name = data["name"].strip() or p_edit.name
                upd_p = ManagedProcess(id=p_edit.id, name=name, monitoring_path=data["monitoring_path"], launch_path=data["launch_path"], server_reset_time_str=data["server_reset_time_str"], user_cycle_hours=data["user_cycle_hours"], mandatory_times_str=data["mandatory_times_str"], is_mandatory_time_enabled=data["is_mandatory_time_enabled"], last_played_timestamp=p_edit.last_played_timestamp)
                if self.data_manager.update_process(upd_p): 
                    self.populate_process_list_slot()
                    self.statusBar().showMessage(f"'{upd_p.name}' 수정 완료.", 3000)
                else: QMessageBox.warning(self, "오류", "프로세스 수정 실패.")

    def handle_delete_action_for_row(self, pid:str): # 게임 삭제
        p_del = self.data_manager.get_process_by_id(pid)
        if not p_del: QMessageBox.warning(self, "오류", f"ID '{pid}' 프로세스 없음."); return
        reply = QMessageBox.question(self, "삭제 확인", f"'{p_del.name}' 삭제?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.data_manager.remove_process(pid): 
                self.populate_process_list_slot()
                self.statusBar().showMessage(f"'{p_del.name}' 삭제 완료.", 3000)
            else: QMessageBox.warning(self, "오류", "프로세스 삭제 실패.")

    def handle_launch_button_in_row(self, pid:str): # 게임 실행
        p_launch = self.data_manager.get_process_by_id(pid)
        if not p_launch: QMessageBox.warning(self, "오류", f"ID '{pid}' 프로세스 없음."); return
        if not p_launch.launch_path: QMessageBox.warning(self, "오류", f"'{p_launch.name}' 실행 경로 없음."); return
        if self.launcher.launch_process(p_launch.launch_path):
            self.system_notifier.send_notification(title="프로세스 실행", message=f"'{p_launch.name}' 실행함.", task_id_to_highlight=None)
            self.statusBar().showMessage(f"'{p_launch.name}' 실행 시도.", 3000)
        else:
            self.system_notifier.send_notification(title="실행 실패", message=f"'{p_launch.name}' 실행 실패. 로그 확인.", task_id_to_highlight=None)
            self.statusBar().showMessage(f"'{p_launch.name}' 실행 실패.", 3000)

    def open_add_process_dialog(self): # "새 게임 추가" 버튼에 연결
        dialog = ProcessDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                name = data["name"].strip()
                if not name and data["monitoring_path"]: name = os.path.splitext(os.path.basename(data["monitoring_path"]))[0] or "새 프로세스"
                new_p = ManagedProcess(name=name, monitoring_path=data["monitoring_path"], launch_path=data["launch_path"], server_reset_time_str=data["server_reset_time_str"], user_cycle_hours=data["user_cycle_hours"], mandatory_times_str=data["mandatory_times_str"], is_mandatory_time_enabled=data["is_mandatory_time_enabled"])
                self.data_manager.add_process(new_p)
                self.populate_process_list_slot()
                self.statusBar().showMessage(f"'{new_p.name}' 추가 완료.", 3000)

    # --- 웹 바로 가기 버튼 관련 메소드들 ---
    def _clear_layout(self, layout: QHBoxLayout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0); widget = item.widget()
                if widget is not None: widget.deleteLater()

    def _determine_web_button_state(self, shortcut: WebShortcut, current_dt: datetime.datetime) -> str:
        if not shortcut.refresh_time_str: return "DEFAULT"
        try:
            rt_hour, rt_minute = map(int, shortcut.refresh_time_str.split(':'))
            refresh_time_today_obj = datetime.time(rt_hour, rt_minute)
        except (ValueError, TypeError): return "DEFAULT"
        todays_refresh_event_dt = datetime.datetime.combine(current_dt.date(), refresh_time_today_obj)
        last_reset_dt = datetime.datetime.fromtimestamp(shortcut.last_reset_timestamp) if shortcut.last_reset_timestamp else None
        if current_dt >= todays_refresh_event_dt:
            return "RED" if last_reset_dt is None or last_reset_dt < todays_refresh_event_dt else "GREEN"
        else:
            if last_reset_dt is None: return "DEFAULT"
            yesterdays_refresh_event_dt = datetime.datetime.combine(current_dt.date() - datetime.timedelta(days=1), refresh_time_today_obj)
            return "GREEN" if last_reset_dt >= yesterdays_refresh_event_dt else "DEFAULT"

    def _apply_button_style(self, button: QPushButton, state: str):
        button.setStyleSheet("") 
        if state == "RED": button.setStyleSheet(f"background-color: {self.COLOR_WEB_BTN_RED.name()};")
        elif state == "GREEN": button.setStyleSheet(f"background-color: {self.COLOR_WEB_BTN_GREEN.name()};")

    def _refresh_web_button_states(self):
        # print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 웹 버튼 상태 새로고침") # 디버그용
        current_dt = datetime.datetime.now()
        for i in range(self.dynamic_web_buttons_layout.count()):
            widget = self.dynamic_web_buttons_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                button = widget; shortcut_id = button.property("shortcut_id")
                if shortcut_id:
                    shortcut = self.data_manager.get_web_shortcut_by_id(shortcut_id)
                    if shortcut:
                        state = self._determine_web_button_state(shortcut, current_dt)
                        self._apply_button_style(button, state)

    def _load_and_display_web_buttons(self):
        self._clear_layout(self.dynamic_web_buttons_layout) 
        shortcuts = self.data_manager.get_web_shortcuts()
        current_dt = datetime.datetime.now()
        for sc_data in shortcuts:
            button = QPushButton(sc_data.name)
            button.clicked.connect(functools.partial(self._handle_web_button_clicked, sc_data.id, sc_data.url))
            button.setProperty("shortcut_id", sc_data.id) 
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(functools.partial(self._show_web_button_context_menu, button))
            state = self._determine_web_button_state(sc_data, current_dt)
            self._apply_button_style(button, state)
            self.dynamic_web_buttons_layout.addWidget(button)

    def _handle_web_button_clicked(self, shortcut_id: str, url: str):
        print(f"웹 버튼 클릭 (ID: {shortcut_id}): {url} 열기 시도")
        shortcut = self.data_manager.get_web_shortcut_by_id(shortcut_id)
        if not shortcut: QMessageBox.warning(self, "오류", "해당 웹 바로 가기 정보를 찾을 수 없습니다."); self.open_webpage(url); return
        self.open_webpage(url)
        if shortcut.refresh_time_str:
            shortcut.last_reset_timestamp = datetime.datetime.now().timestamp()
            if self.data_manager.update_web_shortcut(shortcut):
                print(f"웹 바로 가기 '{shortcut.name}' 상태 업데이트 (last_reset_timestamp).")
                self._refresh_web_button_states() 
            else: print(f"웹 바로 가기 '{shortcut.name}' 상태 업데이트 실패.")

    def _open_add_web_shortcut_dialog(self):
        dialog = WebShortcutDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                new_shortcut = WebShortcut(name=data["name"], url=data["url"], refresh_time_str=data.get("refresh_time_str"))
                if self.data_manager.add_web_shortcut(new_shortcut):
                    self._load_and_display_web_buttons() 
                    self.statusBar().showMessage(f"웹 바로 가기 '{new_shortcut.name}' 추가됨.", 3000)
                else: QMessageBox.warning(self, "추가 실패", "웹 바로 가기 추가에 실패했습니다.")
    
    def _show_web_button_context_menu(self, button: QPushButton, position):
        shortcut_id = button.property("shortcut_id")
        if not shortcut_id: return
        menu = QMenu(self); edit_action = QAction("편집", self); delete_action = QAction("삭제", self)
        edit_action.triggered.connect(functools.partial(self._edit_web_shortcut, shortcut_id))
        delete_action.triggered.connect(functools.partial(self._delete_web_shortcut, shortcut_id))
        menu.addActions([edit_action, delete_action]); menu.exec(button.mapToGlobal(position))

    def _edit_web_shortcut(self, shortcut_id: str):
        shortcut_to_edit = self.data_manager.get_web_shortcut_by_id(shortcut_id)
        if not shortcut_to_edit: QMessageBox.warning(self, "오류", "편집할 웹 바로 가기를 찾을 수 없습니다."); return
        dialog = WebShortcutDialog(self, shortcut_data=shortcut_to_edit.to_dict()) 
        if dialog.exec():
            data = dialog.get_data()
            if data:
                updated_shortcut = WebShortcut(id=shortcut_id, name=data["name"], url=data["url"], 
                                             refresh_time_str=data.get("refresh_time_str"),
                                             last_reset_timestamp=shortcut_to_edit.last_reset_timestamp)
                if not updated_shortcut.refresh_time_str: updated_shortcut.last_reset_timestamp = None
                if self.data_manager.update_web_shortcut(updated_shortcut):
                    self._load_and_display_web_buttons() 
                    self.statusBar().showMessage(f"웹 바로 가기 '{updated_shortcut.name}' 수정됨.", 3000)
                else: QMessageBox.warning(self, "수정 실패", "웹 바로 가기 수정에 실패했습니다.")

    def _delete_web_shortcut(self, shortcut_id: str):
        shortcut_to_delete = self.data_manager.get_web_shortcut_by_id(shortcut_id)
        if not shortcut_to_delete: QMessageBox.warning(self, "오류", "삭제할 웹 바로 가기를 찾을 수 없습니다."); return
        reply = QMessageBox.question(self, "삭제 확인", f"웹 바로 가기 '{shortcut_to_delete.name}'을(를) 정말 삭제하시겠습니까?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.data_manager.remove_web_shortcut(shortcut_id):
                self._load_and_display_web_buttons()
                self.statusBar().showMessage(f"웹 바로 가기 '{shortcut_to_delete.name}' 삭제됨.", 3000)
            else: QMessageBox.warning(self, "삭제 실패", "웹 바로 가기 삭제에 실패했습니다.")

    def closeEvent(self, event: QEvent):
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.handle_window_close_event(event)
        else: event.ignore(); self.hide()

    def initiate_quit_sequence(self):
        print("애플리케이션 종료 절차 시작...")
        if hasattr(self, 'monitor_timer') and self.monitor_timer.isActive(): self.monitor_timer.stop()
        if hasattr(self, 'scheduler_timer') and self.scheduler_timer.isActive(): self.scheduler_timer.stop()
        if hasattr(self, 'web_button_refresh_timer') and self.web_button_refresh_timer.isActive(): 
            self.web_button_refresh_timer.stop(); print("웹 버튼 상태 새로고침 타이머 중지됨.")
        if hasattr(self, 'tray_manager') and self.tray_manager: self.tray_manager.hide_tray_icon()
        if self._instance_manager and hasattr(self._instance_manager, 'cleanup'):
            self._instance_manager.cleanup()
        app_instance = QApplication.instance()
        if app_instance: app_instance.quit()

# --- 애플리케이션 실행 로직 ---
def start_main_application(instance_manager: SingleInstanceApplication):
    app = QApplication(sys.argv)
    app.setApplicationName("숙제 관리자")
    app.setOrganizationName("HomeworkHelperOrg")
    app.setQuitOnLastWindowClosed(False)

    data_folder_name = "homework_helper_data"
    if getattr(sys, 'frozen', False): application_path = os.path.dirname(sys.executable)
    else: application_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(application_path, data_folder_name)
    data_manager_instance = DataManager(data_folder=data_path)
    
    main_window = MainWindow(data_manager_instance, instance_manager=instance_manager)
    instance_manager.start_ipc_server(main_window_to_activate=main_window)
    main_window.show()
    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == "__main__":
    run_with_single_instance_check(
        application_name="숙제 관리자",
        main_app_start_callback=start_main_application
    )