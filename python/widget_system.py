# widget_system.py
import sys
import os
import datetime
from typing import Optional, Dict, Any, Callable
from enum import Enum

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QGraphicsOpacityEffect, QSizePolicy,
    QSystemTrayIcon, QMenu, QMessageBox, QSlider, QSpinBox,
    QCheckBox, QGroupBox, QFormLayout, QDialog, QDialogButtonBox, QComboBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QAbstractScrollArea
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, 
    QPoint, QSize, Signal, QSettings, QThread, pyqtSignal
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QIcon

# 기존 모듈들 임포트
from data_manager import DataManager
from data_models import ManagedProcess, GlobalSettings
from scheduler import Scheduler, PROC_STATE_INCOMPLETE, PROC_STATE_COMPLETED, PROC_STATE_RUNNING
from process_monitor import ProcessMonitor
from notifier import Notifier
from launcher import Launcher
from dialogs import ProcessDialog

class WidgetPosition(Enum):
    """위젯 핸들의 위치"""
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"

class WidgetSettings:
    """위젯 설정을 관리하는 클래스"""
    def __init__(self):
        self.settings = QSettings("HomeworkHelper", "WidgetSettings")
        self.load_settings()
    
    def load_settings(self):
        """설정을 로드합니다"""
        self.handle_opacity = self.settings.value("handle_opacity", 0.7, type=float)
        self.main_widget_opacity = self.settings.value("main_widget_opacity", 0.9, type=float)
        self.position = WidgetPosition(self.settings.value("position", "right"))
        self.hover_delay_ms = self.settings.value("hover_delay_ms", 1000, type=int)
        self.is_position_locked = self.settings.value("is_position_locked", False, type=bool)
        self.animation_duration_ms = self.settings.value("animation_duration_ms", 300, type=int)
        self.handle_size = self.settings.value("handle_size", 20, type=int)
        self.main_widget_width = self.settings.value("main_widget_width", 300, type=int)
        self.main_widget_height = self.settings.value("main_widget_height", 400, type=int)
    
    def save_settings(self):
        """설정을 저장합니다"""
        self.settings.setValue("handle_opacity", self.handle_opacity)
        self.settings.setValue("main_widget_opacity", self.main_widget_opacity)
        self.settings.setValue("position", self.position.value)
        self.settings.setValue("hover_delay_ms", self.hover_delay_ms)
        self.settings.setValue("is_position_locked", self.is_position_locked)
        self.settings.setValue("animation_duration_ms", self.animation_duration_ms)
        self.settings.setValue("handle_size", self.handle_size)
        self.settings.setValue("main_widget_width", self.main_widget_width)
        self.settings.setValue("main_widget_height", self.main_widget_height)

class WidgetHandle(QWidget):
    """화면 가장자리의 위젯 핸들"""
    
    # 시그널 정의
    hover_entered = Signal()
    hover_left = Signal()
    position_changed = Signal(WidgetPosition)
    
    def __init__(self, position: WidgetPosition, settings: WidgetSettings):
        super().__init__()
        self.position = position
        self.settings = settings
        self.is_dragging = False
        self.drag_start_pos = QPoint()
        self.original_pos = QPoint()
        
        self.setup_ui()
        self.setup_animations()
        self.update_position()
        
    def setup_ui(self):
        """UI를 설정합니다"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 투명도 효과 설정
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(self.settings.handle_opacity)
        self.setGraphicsEffect(self.opacity_effect)
        
        # 핸들 크기 설정
        self.setFixedSize(self.settings.handle_size, self.settings.handle_size)
        
        # 마우스 추적 활성화
        self.setMouseTracking(True)
        
    def setup_animations(self):
        """애니메이션을 설정합니다"""
        # 투명도 애니메이션
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # 위치 애니메이션
        self.position_animation = QPropertyAnimation(self, b"pos")
        self.position_animation.setDuration(self.settings.animation_duration_ms)
        self.position_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def update_position(self):
        """화면 가장자리에 핸들을 배치합니다"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        if self.position == WidgetPosition.LEFT:
            x = 0
            y = (screen_geometry.height() - self.height()) // 2
        elif self.position == WidgetPosition.RIGHT:
            x = screen_geometry.width() - self.width()
            y = (screen_geometry.height() - self.height()) // 2
        elif self.position == WidgetPosition.TOP:
            x = (screen_geometry.width() - self.width()) // 2
            y = 0
        else:  # BOTTOM
            x = (screen_geometry.width() - self.width()) // 2
            y = screen_geometry.height() - self.height()
            
        self.move(x, y)
        self.original_pos = QPoint(x, y)
        
    def paintEvent(self, event):
        """핸들을 그립니다"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 배경 그리기
        painter.setBrush(QBrush(QColor(100, 100, 100, 150)))
        painter.setPen(QPen(QColor(200, 200, 200, 200), 2))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 5, 5)
        
        # 핸들 표시 그리기
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        center = self.rect().center()
        
        if self.position in [WidgetPosition.LEFT, WidgetPosition.RIGHT]:
            # 좌우 화살표
            points = [
                QPoint(center.x() - 4, center.y() - 6),
                QPoint(center.x() + 4, center.y()),
                QPoint(center.x() - 4, center.y() + 6)
            ]
        else:
            # 상하 화살표
            points = [
                QPoint(center.x() - 6, center.y() - 4),
                QPoint(center.x(), center.y() + 4),
                QPoint(center.x() + 6, center.y() - 4)
            ]
            
        painter.drawPolyline(points)
        
    def enterEvent(self, event):
        """마우스 진입 이벤트"""
        super().enterEvent(event)
        self.hover_entered.emit()
        
        # 투명도 애니메이션 (더 불투명하게)
        self.opacity_animation.setStartValue(self.opacity_effect.opacity())
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()
        
    def leaveEvent(self, event):
        """마우스 이탈 이벤트"""
        super().leaveEvent(event)
        self.hover_left.emit()
        
        # 투명도 애니메이션 (원래대로)
        self.opacity_animation.setStartValue(self.opacity_effect.opacity())
        self.opacity_animation.setEndValue(self.settings.handle_opacity)
        self.opacity_animation.start()
        
    def mousePressEvent(self, event):
        """마우스 누름 이벤트"""
        if event.button() == Qt.MouseButton.LeftButton and not self.settings.is_position_locked:
            self.is_dragging = True
            self.drag_start_pos = event.globalPosition().toPoint() - self.pos()
            
    def mouseMoveEvent(self, event):
        """마우스 이동 이벤트"""
        if self.is_dragging and not self.settings.is_position_locked:
            new_pos = event.globalPosition().toPoint() - self.drag_start_pos
            self.move(new_pos)
            
    def mouseReleaseEvent(self, event):
        """마우스 놓기 이벤트"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.snap_to_edge()
            
    def snap_to_edge(self):
        """가장 가까운 화면 가장자리로 스냅합니다"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        current_pos = self.pos()
        center_x = current_pos.x() + self.width() // 2
        center_y = current_pos.y() + self.height() // 2
        
        # 화면 중앙점
        screen_center_x = screen_geometry.width() // 2
        screen_center_y = screen_geometry.height() // 2
        
        # 가장 가까운 가장자리 결정
        if center_x < screen_center_x:
            if center_y < screen_center_y:
                # 좌상단
                if center_x < center_y:
                    new_position = WidgetPosition.LEFT
                else:
                    new_position = WidgetPosition.TOP
            else:
                # 좌하단
                if center_x < (screen_geometry.height() - center_y):
                    new_position = WidgetPosition.LEFT
                else:
                    new_position = WidgetPosition.BOTTOM
        else:
            if center_y < screen_center_y:
                # 우상단
                if (screen_geometry.width() - center_x) < center_y:
                    new_position = WidgetPosition.TOP
                else:
                    new_position = WidgetPosition.RIGHT
            else:
                # 우하단
                if (screen_geometry.width() - center_x) < (screen_geometry.height() - center_y):
                    new_position = WidgetPosition.RIGHT
                else:
                    new_position = WidgetPosition.BOTTOM
                    
        # 위치 변경
        if new_position != self.position:
            self.position = new_position
            self.position_changed.emit(new_position)
            
        self.update_position()

class MainWidget(QWidget):
    """메인 위젯 (숙제 관리 기능)"""
    
    def __init__(self, data_manager: DataManager, settings: WidgetSettings, scheduler: Scheduler, launcher: Launcher, widget_manager=None):
        super().__init__()
        self.data_manager = data_manager
        self.settings = settings
        self.scheduler = scheduler
        self.launcher = launcher
        self.widget_manager = widget_manager
        
        # 테이블 컬럼 인덱스 정의
        self.COL_ICON = 0
        self.COL_NAME = 1
        self.COL_PROGRESS = 2
        self.COL_LAUNCH_BTN = 3
        self.COL_STATUS = 4
        self.TOTAL_COLUMNS = 5
        
        # 색상 정의
        self.COLOR_INCOMPLETE = QColor("red")
        self.COLOR_COMPLETED = QColor("green")
        self.COLOR_RUNNING = QColor("yellow")
        
        self.setup_ui()
        self.setup_animations()
        self.populate_process_list()
        
    def setup_ui(self):
        """UI를 설정합니다"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 투명도 효과 설정
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(self.settings.main_widget_opacity)
        self.setGraphicsEffect(self.opacity_effect)
        
        # 크기 설정
        self.setFixedSize(self.settings.main_widget_width, self.settings.main_widget_height)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 제목
        title_label = QLabel("숙제 관리자")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: white;
                background-color: rgba(50, 50, 50, 200);
                padding: 8px;
                border-radius: 5px;
                margin-bottom: 5px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # 프로세스 테이블
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(self.TOTAL_COLUMNS)
        self.process_table.setHorizontalHeaderLabels(["", "이름", "진행률", "실행", "상태"])
        self.process_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.process_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.process_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # 테이블 크기 정책 설정
        self.process_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.process_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 테이블 행 높이 설정
        vh = self.process_table.verticalHeader()
        if vh:
            vh.setDefaultSectionSize(25)
            
        # 헤더 설정
        header = self.process_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(self.COL_ICON, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(self.COL_PROGRESS, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COL_LAUNCH_BTN, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
            
        # 테이블 스타일
        self.process_table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(30, 30, 30, 150);
                color: white;
                border: 1px solid rgba(100, 100, 100, 100);
                border-radius: 5px;
                gridline-color: rgba(100, 100, 100, 50);
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid rgba(100, 100, 100, 30);
            }
            QHeaderView::section {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                padding: 6px;
                border: none;
                border-right: 1px solid rgba(100, 100, 100, 50);
            }
        """)
        
        main_layout.addWidget(self.process_table)
        
        # 버튼들
        button_layout = QHBoxLayout()
        
        self.add_button = QPushButton("추가")
        self.add_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 150, 0, 200);
                color: white;
                border: none;
                padding: 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: rgba(0, 180, 0, 200);
            }
        """)
        
        self.settings_button = QPushButton("설정")
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 100, 100, 200);
                color: white;
                border: none;
                padding: 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: rgba(120, 120, 120, 200);
            }
        """)
        
        # 버튼 이벤트 연결
        self.add_button.clicked.connect(self.open_add_process_dialog)
        self.settings_button.clicked.connect(self.open_widget_settings_dialog)
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.settings_button)
        main_layout.addLayout(button_layout)
        
    def populate_process_list(self):
        """관리 대상 프로세스 목록을 테이블에 채웁니다"""
        self.process_table.setSortingEnabled(False)
        processes = self.data_manager.managed_processes
        self.process_table.setRowCount(len(processes))
        
        now_dt = datetime.datetime.now()
        gs = self.data_manager.global_settings
        palette = self.process_table.palette()
        df_bg, df_fg = palette.base(), palette.text()
        
        for r, p in enumerate(processes):
            # 아이콘 컬럼
            icon_item = QTableWidgetItem()
            # 아이콘은 간단히 텍스트로 대체
            icon_item.setText("📱")
            self.process_table.setItem(r, self.COL_ICON, icon_item)
            icon_item.setBackground(df_bg)
            icon_item.setForeground(df_fg)
            
            # 이름 컬럼
            name_item = QTableWidgetItem(p.name)
            name_item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.process_table.setItem(r, self.COL_NAME, name_item)
            name_item.setBackground(df_bg)
            name_item.setForeground(df_fg)
            
            # 진행률 컬럼
            percentage, time_str = self._calculate_progress_percentage(p, now_dt)
            progress_widget = self._create_progress_bar_widget(percentage, time_str)
            self.process_table.setCellWidget(r, self.COL_PROGRESS, progress_widget)
            
            # 실행 버튼 컬럼
            btn = QPushButton("실행")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 100, 200, 200);
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 120, 220, 200);
                }
            """)
            btn.clicked.connect(lambda checked, pid=p.id: self.handle_launch_button(pid))
            self.process_table.setCellWidget(r, self.COL_LAUNCH_BTN, btn)
            
            # 상태 컬럼
            st_str = self.scheduler.determine_process_visual_status(p, now_dt, gs)
            st_item = QTableWidgetItem(st_str)
            st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.process_table.setItem(r, self.COL_STATUS, st_item)
            st_item.setForeground(df_fg)
            
            # 상태에 따른 배경색 설정
            if st_str == PROC_STATE_RUNNING:
                st_item.setBackground(self.COLOR_RUNNING)
                st_item.setForeground(QColor("black"))
            elif st_str == PROC_STATE_INCOMPLETE:
                st_item.setBackground(self.COLOR_INCOMPLETE)
            elif st_str == PROC_STATE_COMPLETED:
                st_item.setBackground(self.COLOR_COMPLETED)
            else:
                st_item.setBackground(df_bg)
                
        self.process_table.setSortingEnabled(True)
        
    def _calculate_progress_percentage(self, process: ManagedProcess, current_dt: datetime.datetime) -> tuple[float, str]:
        """마지막 실행 시각을 기준으로 다음 접속까지의 진행률을 계산합니다"""
        if not process.last_played_timestamp or not process.user_cycle_hours:
            return 0.0, "기록 없음"
        
        try:
            last_played_dt = datetime.datetime.fromtimestamp(process.last_played_timestamp)
            cycle_hours = process.user_cycle_hours
            
            # 경과 시간 계산 (시간 단위)
            elapsed_hours = (current_dt - last_played_dt).total_seconds() / 3600
            
            # 진행률 계산 (0.0 ~ 1.0)
            progress = min(elapsed_hours / cycle_hours, 1.0)
            
            # 백분율로 변환
            percentage = progress * 100
            
            # 남은 시간 계산
            remaining_hours = max(cycle_hours - elapsed_hours, 0)
            
            if remaining_hours >= 24:
                remaining_days = int(remaining_hours // 24)
                remaining_hours_remainder = remaining_hours % 24
                if remaining_hours_remainder > 0:
                    time_str = f"{remaining_days}일 {int(remaining_hours_remainder)}시간"
                else:
                    time_str = f"{remaining_days}일"
            elif remaining_hours >= 1:
                time_str = f"{int(remaining_hours)}시간"
            else:
                remaining_minutes = int(remaining_hours * 60)
                time_str = f"{remaining_minutes}분"
            
            return percentage, time_str
            
        except Exception as e:
            print(f"진행률 계산 중 오류: {e}")
            return 0.0, "계산 오류"
            
    def _create_progress_bar_widget(self, percentage: float, time_str: str) -> QWidget:
        """진행률을 표시하는 위젯을 생성합니다"""
        if percentage == 0.0:
            # 기록이 없는 경우 텍스트 라벨 반환
            label = QLabel(time_str)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: white; font-size: 11px;")
            return label
        
        # QProgressBar 생성
        progress_bar = QProgressBar()
        progress_bar.setValue(int(percentage))
        progress_bar.setMaximum(100)
        progress_bar.setMinimum(0)
        progress_bar.setMinimumHeight(18)
        progress_bar.setTextVisible(True)
        progress_bar.setFormat(f"{percentage:.1f}%")
        
        # 진행률에 따른 색상 설정
        if percentage >= 100:
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #404040;
                    border-radius: 2px;
                    text-align: center;
                    background-color: #2d2d2d;
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                }
                QProgressBar::chunk {
                    background-color: #ff4444;
                    border-radius: 1px;
                }
            """)
        elif percentage >= 80:
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #404040;
                    border-radius: 2px;
                    text-align: center;
                    background-color: #2d2d2d;
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                }
                QProgressBar::chunk {
                    background-color: #ff8800;
                    border-radius: 1px;
                }
            """)
        elif percentage >= 50:
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #404040;
                    border-radius: 2px;
                    text-align: center;
                    background-color: #2d2d2d;
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                }
                QProgressBar::chunk {
                    background-color: #ffcc00;
                    border-radius: 1px;
                }
            """)
        else:
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #404040;
                    border-radius: 2px;
                    text-align: center;
                    background-color: #2d2d2d;
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                }
                QProgressBar::chunk {
                    background-color: #44cc44;
                    border-radius: 1px;
                }
            """)
        
        return progress_bar
        
    def handle_launch_button(self, process_id: str):
        """프로세스 실행 버튼을 처리합니다"""
        process = self.data_manager.get_process_by_id(process_id)
        if not process:
            return
            
        if not process.launch_path:
            QMessageBox.warning(self, "오류", f"'{process.name}' 실행 경로가 없습니다.")
            return
            
        if self.launcher.launch_process(process.launch_path):
            print(f"'{process.name}' 실행 시도")
            # 실행 성공 시 즉시 상태 업데이트
            self.populate_process_list()
        else:
            QMessageBox.warning(self, "실행 실패", f"'{process.name}' 실행에 실패했습니다.")
            
    def open_add_process_dialog(self):
        """새 프로세스 추가 대화상자를 엽니다"""
        dialog = ProcessDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data:
                name = data["name"].strip()
                # 이름이 비어있고 모니터링 경로가 있으면 파일명으로 자동 생성
                if not name and data["monitoring_path"]:
                    import os
                    name = os.path.splitext(os.path.basename(data["monitoring_path"]))[0] or "새 프로세스"
                
                # 새 프로세스 객체 생성
                new_p = ManagedProcess(
                    name=name,
                    monitoring_path=data["monitoring_path"],
                    launch_path=data["launch_path"],
                    server_reset_time_str=data["server_reset_time_str"],
                    user_cycle_hours=data["user_cycle_hours"],
                    mandatory_times_str=data["mandatory_times_str"],
                    is_mandatory_time_enabled=data["is_mandatory_time_enabled"],
                    original_launch_path=data["launch_path"]
                )
                
                self.data_manager.add_process(new_p)
                self.populate_process_list()
                print(f"'{new_p.name}' 추가 완료")
                
    def open_widget_settings_dialog(self):
        """위젯 설정 대화상자를 엽니다"""
        if self.widget_manager:
            self.widget_manager.show_settings_dialog()
        
    def setup_animations(self):
        """애니메이션을 설정합니다"""
        # 슬라이드 애니메이션
        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(self.settings.animation_duration_ms)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 투명도 애니메이션
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # 애니메이션 완료 시그널 연결
        self.slide_animation.finished.connect(self.on_animation_finished)
        
    def on_animation_finished(self):
        """애니메이션 완료 시 호출됩니다"""
        # 숨기기 애니메이션 완료 시 위젯을 실제로 숨김
        if not self.isVisible():
            self.hide()
            
    def show_widget(self, handle_position: WidgetPosition):
        """위젯을 표시합니다 (애니메이션과 함께)"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # 최종 위치 계산
        if handle_position == WidgetPosition.LEFT:
            final_x = self.settings.handle_size
            final_y = (screen_geometry.height() - self.height()) // 2
        elif handle_position == WidgetPosition.RIGHT:
            final_x = screen_geometry.width() - self.width() - self.settings.handle_size
            final_y = (screen_geometry.height() - self.height()) // 2
        elif handle_position == WidgetPosition.TOP:
            final_x = (screen_geometry.width() - self.width()) // 2
            final_y = self.settings.handle_size
        else:  # BOTTOM
            final_x = (screen_geometry.width() - self.width()) // 2
            final_y = screen_geometry.height() - self.height() - self.settings.handle_size
            
        final_pos = QPoint(final_x, final_y)
        
        # 시작 위치 설정 (화면 밖)
        start_pos = self.calculate_start_position(handle_position, screen_geometry)
        self.move(start_pos)
        
        # 애니메이션 설정
        self.slide_animation.setStartValue(start_pos)
        self.slide_animation.setEndValue(final_pos)
        
        # 표시 및 애니메이션 시작
        self.show()
        self.slide_animation.start()
        
    def hide_widget(self):
        """위젯을 숨깁니다 (애니메이션과 함께)"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # 현재 위치에서 화면 밖으로 이동
        current_pos = self.pos()
        end_pos = self.calculate_start_position(self.get_current_handle_position(), screen_geometry)
        
        self.slide_animation.setStartValue(current_pos)
        self.slide_animation.setEndValue(end_pos)
        
        # 애니메이션 시작
        self.slide_animation.start()
        
    def calculate_start_position(self, handle_position: WidgetPosition, screen_geometry: QRect) -> QPoint:
        """핸들 위치에 따른 시작 위치를 계산합니다"""
        if handle_position == WidgetPosition.LEFT:
            return QPoint(-self.width(), (screen_geometry.height() - self.height()) // 2)
        elif handle_position == WidgetPosition.RIGHT:
            return QPoint(screen_geometry.width(), (screen_geometry.height() - self.height()) // 2)
        elif handle_position == WidgetPosition.TOP:
            return QPoint((screen_geometry.width() - self.width()) // 2, -self.height())
        else:  # BOTTOM
            return QPoint((screen_geometry.width() - self.width()) // 2, screen_geometry.height())
            
    def get_current_handle_position(self) -> WidgetPosition:
        """현재 핸들 위치를 반환합니다 (간단한 구현)"""
        # 실제로는 WidgetManager에서 관리하는 위치를 사용해야 함
        return WidgetPosition.RIGHT
        
    def paintEvent(self, event):
        """위젯을 그립니다"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 배경 그리기
        painter.setBrush(QBrush(QColor(40, 40, 40, 200)))
        painter.setPen(QPen(QColor(100, 100, 100, 255), 2))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

class WidgetSettingsDialog(QDialog):
    """위젯 설정 대화상자"""
    
    def __init__(self, settings: WidgetSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("위젯 설정")
        self.setModal(True)
        self.setFixedSize(400, 500)
        
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        """UI를 설정합니다"""
        layout = QVBoxLayout(self)
        
        # 투명도 설정
        opacity_group = QGroupBox("투명도 설정")
        opacity_layout = QFormLayout(opacity_group)
        
        # 핸들 투명도
        self.handle_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.handle_opacity_slider.setRange(10, 100)
        self.handle_opacity_slider.setValue(int(self.settings.handle_opacity * 100))
        self.handle_opacity_label = QLabel(f"{int(self.settings.handle_opacity * 100)}%")
        self.handle_opacity_slider.valueChanged.connect(
            lambda v: self.handle_opacity_label.setText(f"{v}%")
        )
        opacity_layout.addRow("핸들 투명도:", self.handle_opacity_slider)
        opacity_layout.addRow("", self.handle_opacity_label)
        
        # 메인 위젯 투명도
        self.main_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.main_opacity_slider.setRange(10, 100)
        self.main_opacity_slider.setValue(int(self.settings.main_widget_opacity * 100))
        self.main_opacity_label = QLabel(f"{int(self.settings.main_widget_opacity * 100)}%")
        self.main_opacity_slider.valueChanged.connect(
            lambda v: self.main_opacity_label.setText(f"{v}%")
        )
        opacity_layout.addRow("메인 위젯 투명도:", self.main_opacity_slider)
        opacity_layout.addRow("", self.main_opacity_label)
        
        layout.addWidget(opacity_group)
        
        # 위치 설정
        position_group = QGroupBox("위치 설정")
        position_layout = QFormLayout(position_group)
        
        self.position_combo = QComboBox()
        self.position_combo.addItems(["왼쪽", "오른쪽", "위쪽", "아래쪽"])
        self.position_combo.setCurrentText(self.get_position_text(self.settings.position))
        position_layout.addRow("위치:", self.position_combo)
        
        self.lock_position_checkbox = QCheckBox("위치 고정")
        self.lock_position_checkbox.setChecked(self.settings.is_position_locked)
        position_layout.addRow("", self.lock_position_checkbox)
        
        layout.addWidget(position_group)
        
        # 애니메이션 설정
        animation_group = QGroupBox("애니메이션 설정")
        animation_layout = QFormLayout(animation_group)
        
        self.hover_delay_spinbox = QSpinBox()
        self.hover_delay_spinbox.setRange(100, 5000)
        self.hover_delay_spinbox.setValue(self.settings.hover_delay_ms)
        self.hover_delay_spinbox.setSuffix(" ms")
        animation_layout.addRow("호버 지연 시간:", self.hover_delay_spinbox)
        
        self.animation_duration_spinbox = QSpinBox()
        self.animation_duration_spinbox.setRange(100, 2000)
        self.animation_duration_spinbox.setValue(self.settings.animation_duration_ms)
        self.animation_duration_spinbox.setSuffix(" ms")
        animation_layout.addRow("애니메이션 지속 시간:", self.animation_duration_spinbox)
        
        layout.addWidget(animation_group)
        
        # 크기 설정
        size_group = QGroupBox("크기 설정")
        size_layout = QFormLayout(size_group)
        
        self.handle_size_spinbox = QSpinBox()
        self.handle_size_spinbox.setRange(15, 50)
        self.handle_size_spinbox.setValue(self.settings.handle_size)
        size_layout.addRow("핸들 크기:", self.handle_size_spinbox)
        
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(200, 800)
        self.width_spinbox.setValue(self.settings.main_widget_width)
        size_layout.addRow("메인 위젯 너비:", self.width_spinbox)
        
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(200, 1000)
        self.height_spinbox.setValue(self.settings.main_widget_height)
        size_layout.addRow("메인 위젯 높이:", self.height_spinbox)
        
        layout.addWidget(size_group)
        
        # 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def get_position_text(self, position: WidgetPosition) -> str:
        """위치 열거형을 한국어 텍스트로 변환"""
        position_map = {
            WidgetPosition.LEFT: "왼쪽",
            WidgetPosition.RIGHT: "오른쪽",
            WidgetPosition.TOP: "위쪽",
            WidgetPosition.BOTTOM: "아래쪽"
        }
        return position_map.get(position, "오른쪽")
        
    def get_position_enum(self, text: str) -> WidgetPosition:
        """한국어 텍스트를 위치 열거형으로 변환"""
        text_map = {
            "왼쪽": WidgetPosition.LEFT,
            "오른쪽": WidgetPosition.RIGHT,
            "위쪽": WidgetPosition.TOP,
            "아래쪽": WidgetPosition.BOTTOM
        }
        return text_map.get(text, WidgetPosition.RIGHT)
        
    def load_settings(self):
        """설정을 로드합니다"""
        pass  # UI 설정에서 이미 처리됨
        
    def accept(self):
        """설정을 저장하고 대화상자를 닫습니다"""
        # 설정 업데이트
        self.settings.handle_opacity = self.handle_opacity_slider.value() / 100.0
        self.settings.main_widget_opacity = self.main_opacity_slider.value() / 100.0
        self.settings.position = self.get_position_enum(self.position_combo.currentText())
        self.settings.is_position_locked = self.lock_position_checkbox.isChecked()
        self.settings.hover_delay_ms = self.hover_delay_spinbox.value()
        self.settings.animation_duration_ms = self.animation_duration_spinbox.value()
        self.settings.handle_size = self.handle_size_spinbox.value()
        self.settings.main_widget_width = self.width_spinbox.value()
        self.settings.main_widget_height = self.height_spinbox.value()
        
        # 설정 저장
        self.settings.save_settings()
        
        super().accept()

class WidgetManager:
    """위젯들을 관리하는 매니저 클래스"""
    
    def __init__(self, data_manager: DataManager, scheduler: Scheduler, launcher: Launcher):
        self.data_manager = data_manager
        self.scheduler = scheduler
        self.launcher = launcher
        self.settings = WidgetSettings()
        
        # 위젯들
        self.handle = None
        self.main_widget = None
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.show_main_widget)
        
        self.setup_widgets()
        
    def setup_widgets(self):
        """위젯들을 설정합니다"""
        # 핸들 생성
        self.handle = WidgetHandle(self.settings.position, self.settings)
        self.handle.hover_entered.connect(self.start_hover_timer)
        self.handle.hover_left.connect(self.cancel_hover_timer)
        self.handle.position_changed.connect(self.on_position_changed)
        
        # 메인 위젯 생성
        self.main_widget = MainWidget(self.data_manager, self.settings, self.scheduler, self.launcher, self)
        
        # 호버 타이머 설정
        self.hover_timer.setInterval(self.settings.hover_delay_ms)
        
    def start_hover_timer(self):
        """호버 타이머를 시작합니다"""
        self.hover_timer.start()
        
    def cancel_hover_timer(self):
        """호버 타이머를 취소합니다"""
        self.hover_timer.stop()
        if self.main_widget and self.main_widget.isVisible():
            self.main_widget.hide_widget()
            
    def show_main_widget(self):
        """메인 위젯을 표시합니다"""
        if self.main_widget:
            self.main_widget.show_widget(self.settings.position)
            
    def on_position_changed(self, new_position: WidgetPosition):
        """핸들 위치가 변경되었을 때"""
        self.settings.position = new_position
        self.settings.save_settings()
        
    def show_settings_dialog(self):
        """설정 대화상자를 표시합니다"""
        dialog = WidgetSettingsDialog(self.settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 설정이 변경되었으므로 위젯들을 업데이트
            self.update_widgets_from_settings()
            
    def update_widgets_from_settings(self):
        """설정 변경에 따라 위젯들을 업데이트합니다"""
        # 기존 위젯들 정리
        if self.main_widget and self.main_widget.isVisible():
            self.main_widget.hide_widget()
        if self.handle:
            self.handle.hide()
            
        # 새로운 설정으로 위젯들 다시 생성
        self.setup_widgets()
        
        # 핸들 표시
        self.show_handle()
            
    def show_handle(self):
        """핸들을 표시합니다"""
        if self.handle:
            self.handle.show()
            
    def hide_handle(self):
        """핸들을 숨깁니다"""
        if self.handle:
            self.handle.hide()
            
    def cleanup(self):
        """리소스를 정리합니다"""
        if self.hover_timer:
            self.hover_timer.stop()
        if self.main_widget:
            self.main_widget.hide()
        if self.handle:
            self.handle.hide()
