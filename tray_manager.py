from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import QObject # QObject is a base class for many Qt classes

# It's good practice to type hint the main_window argument if possible,
# but it creates a circular dependency if MainWindow also imports TrayManager.
# Forward declaration as a string or using `typing.TYPE_CHECKING` can solve this
# for more complex scenarios. For now, we'll use 'Any' or omit explicit type.
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from homework_helper import MainWindow # Assuming homework_helper.py contains MainWindow

class TrayManager(QObject): # Inherit from QObject if using signals/slots internally
    def __init__(self, main_window): # main_window will be an instance of MainWindow
        super().__init__(main_window) # Pass main_window as parent to QObject
        self.main_window = main_window
        self.tray_icon = QSystemTrayIcon(self.main_window) # Parent correctly set

        self._setup_tray_icon_and_menu()

    def _setup_tray_icon_and_menu(self):
        """Sets up the tray icon, its tooltip, and context menu."""
        # Use the main window's icon for the tray
        tray_icon_image = self.main_window.windowIcon()
        if tray_icon_image.isNull():
            # Fallback if main window icon wasn't set or is null
            tray_icon_image = QIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setIcon(tray_icon_image)
        self.tray_icon.setToolTip(QApplication.applicationName() or "숙제 관리자") # Use app name if set

        # Create context menu
        tray_menu = QMenu(self.main_window) # Parent QMenu to main_window

        # Show/Hide action
        show_hide_action = QAction("창 보이기/숨기기", self.main_window)
        show_hide_action.triggered.connect(self.toggle_window_visibility)
        tray_menu.addAction(show_hide_action)

        # Settings action
        # Assuming main_window has a method open_global_settings_dialog
        if hasattr(self.main_window, 'open_global_settings_dialog'):
            settings_action_tray = QAction("전역 설정...", self.main_window)
            settings_action_tray.triggered.connect(self.main_window.open_global_settings_dialog)
            tray_menu.addAction(settings_action_tray)
            tray_menu.addSeparator()

        # Quit action
        # Assuming main_window has a method like 'initiate_quit_sequence'
        # that handles stopping timers and other cleanup before quitting.
        quit_action_tray = QAction("종료", self.main_window)
        if hasattr(self.main_window, 'initiate_quit_sequence'):
            quit_action_tray.triggered.connect(self.main_window.initiate_quit_sequence)
        else:
            # Fallback if the method doesn't exist (less ideal)
            quit_action_tray.triggered.connect(self.direct_quit_application)
        tray_menu.addAction(quit_action_tray)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._handle_tray_icon_activation)
        self.tray_icon.show()
        print("TrayManager: 트레이 아이콘 생성 및 표시됨.")

    def toggle_window_visibility(self):
        """Shows or hides the main window."""
        if self.main_window.isVisible() and not self.main_window.isMinimized():
            self.main_window.hide()
            print("TrayManager: 창 숨김.")
        else:
            self.main_window.showNormal() # Restores and shows
            self.main_window.activateWindow() # Brings to front
            self.main_window.raise_()         # Ensures it's above others
            print("TrayManager: 창 보임.")


    def _handle_tray_icon_activation(self, reason: QSystemTrayIcon.ActivationReason):
        """Handles activation events for the tray icon (e.g., click, double-click)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger or \
           reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_window_visibility()

    def handle_window_close_event(self, event):
        """
        Called by the MainWindow's closeEvent.
        Ignores the event and hides the window to tray.
        """
        if event:
            event.ignore()
        self.main_window.hide()
        print("TrayManager: 창 닫기 이벤트 가로채서 숨김 처리.")

    def hide_tray_icon(self):
        """Hides the tray icon. Should be called before application quits."""
        self.tray_icon.hide()
        print("TrayManager: 트레이 아이콘 숨김.")

    def direct_quit_application(self):
        """Directly quits the application without main window cleanup. (Less ideal)"""
        print("TrayManager: 직접 종료 (메인 윈도우 정리 작업 없을 수 있음).")
        self.hide_tray_icon()
        QApplication.instance().quit()