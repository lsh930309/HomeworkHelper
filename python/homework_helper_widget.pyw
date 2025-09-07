# homework_helper_widget.pyw
import sys
import os
import datetime
from typing import Optional

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtCore import QTimer, QSettings
from PySide6.QtGui import QIcon, QAction

# 기존 모듈들 임포트
from data_manager import DataManager
from data_models import GlobalSettings
from widget_system import WidgetManager, WidgetSettings
from notifier import Notifier
from scheduler import Scheduler
from process_monitor import ProcessMonitor
from launcher import Launcher

class HomeworkHelperWidgetApp:
    """숙제 관리자 위젯 애플리케이션"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("숙제 관리자 위젯")
        self.app.setQuitOnLastWindowClosed(False)
        
        # 데이터 매니저 초기화
        self.data_manager = self.initialize_data_manager()
        
        # 위젯 매니저 초기화 (나중에 설정)
        self.widget_manager = None
        
        # 기타 컴포넌트들 초기화
        self.setup_components()
        
        # 트레이 아이콘 설정
        self.setup_tray_icon()
        
        # 타이머 설정
        self.setup_timers()
        
    def initialize_data_manager(self) -> DataManager:
        """데이터 매니저를 초기화합니다"""
        # 데이터 저장 폴더 경로 설정
        data_folder_name = "homework_helper_data"
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(application_path, data_folder_name)
        
        return DataManager(data_folder=data_path)
        
    def setup_components(self):
        """기타 컴포넌트들을 설정합니다"""
        # 프로세스 모니터
        self.process_monitor = ProcessMonitor(self.data_manager)
        
        # 알림 시스템
        self.notifier = Notifier(self.app.applicationName())
        
        # 스케줄러
        self.scheduler = Scheduler(self.data_manager, self.notifier, self.process_monitor)
        
        # 런처
        self.launcher = Launcher(run_as_admin=self.data_manager.global_settings.run_as_admin)
        
        # 위젯 매니저 초기화
        self.widget_manager = WidgetManager(self.data_manager, self.scheduler, self.launcher)
        
    def setup_tray_icon(self):
        """시스템 트레이 아이콘을 설정합니다"""
        # 아이콘 설정
        icon_path = self.get_icon_path()
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QIcon()  # 기본 아이콘
            
        # 트레이 아이콘 생성
        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.tray_icon.setToolTip("숙제 관리자 위젯")
        
        # 컨텍스트 메뉴 생성
        self.create_tray_menu()
        
        # 트레이 아이콘 표시
        self.tray_icon.show()
        
    def get_icon_path(self) -> str:
        """아이콘 파일 경로를 반환합니다"""
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, "img", "app_icon.ico")
        
    def create_tray_menu(self):
        """트레이 아이콘의 컨텍스트 메뉴를 생성합니다"""
        menu = QMenu()
        
        # 위젯 표시/숨기기
        self.show_widget_action = QAction("위젯 표시", self.app)
        self.show_widget_action.triggered.connect(self.toggle_widget_visibility)
        menu.addAction(self.show_widget_action)
        
        # 설정
        settings_action = QAction("위젯 설정", self.app)
        settings_action.triggered.connect(self.widget_manager.show_settings_dialog)
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        # 종료
        quit_action = QAction("종료", self.app)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
        
    def toggle_widget_visibility(self):
        """위젯 표시/숨기기를 토글합니다"""
        if self.widget_manager.handle and self.widget_manager.handle.isVisible():
            self.widget_manager.hide_handle()
            self.show_widget_action.setText("위젯 표시")
        else:
            self.widget_manager.show_handle()
            self.show_widget_action.setText("위젯 숨기기")
            
    def setup_timers(self):
        """타이머들을 설정합니다"""
        # 프로세스 모니터 타이머 (1초)
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.run_process_monitor_check)
        self.monitor_timer.start(1000)
        
        # 스케줄러 타이머 (1초)
        self.scheduler_timer = QTimer()
        self.scheduler_timer.timeout.connect(self.run_scheduler_check)
        self.scheduler_timer.start(1000)
        
    def run_process_monitor_check(self):
        """프로세스 모니터 검사를 실행합니다"""
        if self.process_monitor.check_and_update_statuses():
            print("프로세스 상태 변경 감지됨")
            
    def run_scheduler_check(self):
        """스케줄러 검사를 실행합니다"""
        status_changed = self.scheduler.run_all_checks()
        if status_changed:
            print("스케줄러에 의해 상태 변경 감지됨")
            
    def quit_application(self):
        """애플리케이션을 종료합니다"""
        # 타이머들 중지
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()
        if hasattr(self, 'scheduler_timer'):
            self.scheduler_timer.stop()
            
        # 위젯들 정리
        if self.widget_manager:
            self.widget_manager.cleanup()
            
        # 트레이 아이콘 숨기기
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
            
        # 애플리케이션 종료
        self.app.quit()
        
    def run(self):
        """애플리케이션을 실행합니다"""
        # 위젯 핸들 표시
        self.widget_manager.show_handle()
        
        # 애플리케이션 이벤트 루프 시작
        return self.app.exec()

def main():
    """메인 함수"""
    try:
        app = HomeworkHelperWidgetApp()
        return app.run()
    except Exception as e:
        print(f"애플리케이션 실행 중 오류 발생: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
