from typing import Optional

from PyQt6.QtWidgets import QMessageBox, QAbstractItemView
from PyQt6.QtCore import Qt, QObject, pyqtSlot

# To avoid circular imports with type hinting, you might use:
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from .homework_helper import MainWindow # Assuming homework_helper.py contains MainWindow
#     from .data_manager import DataManager


class GuiNotificationHandler(QObject):
    """
    Handles how the GUI (MainWindow) reacts to system notification activations,
    such as bringing the window to the front and highlighting the relevant task.
    """
    def __init__(self, main_window): # main_window will be an instance of MainWindow
        super().__init__(main_window) # Set main_window as parent
        self.main_window = main_window
        # It's often useful to have a direct reference to data_manager if used frequently
        # self.data_manager = main_window.data_manager

    @pyqtSlot(object) # Connected to Notifier's signal. 'object' for flexibility (str or None)
    def process_system_notification_activation(self, task_id_obj: Optional[str]):
        """
        This slot is connected to a signal from the Notifier when a system notification is clicked.
        It brings the main window to the front and highlights the task if a task_id is provided.
        """
        task_id = str(task_id_obj) if task_id_obj is not None else None

        print(f"GuiNotificationHandler: 시스템 알림 활성화 처리 시작 (Task ID: {task_id})")
        if hasattr(self.main_window, 'statusBar') and callable(self.main_window.statusBar):
            self.main_window.statusBar().showMessage(
                f"알림 클릭됨 (ID: {task_id if task_id else '정보 없음'})", 3000
            )

        # Bring the main window to the front
        if self.main_window.isMinimized():
            self.main_window.showNormal()
        else:
            self.main_window.show() # Ensure it's visible if hidden
        self.main_window.activateWindow()
        self.main_window.raise_()

        # If no specific task_id, just show a generic message
        if not task_id:
            QMessageBox.information(
                self.main_window,
                "알림",
                "일반 알림이 수신되었습니다."
            )
            return

        # Attempt to find and highlight the task in the table
        # MainWindow should have data_manager and process_table attributes
        # MainWindow should also define COL_NAME (index for the name column where ID is stored)
        if not hasattr(self.main_window, 'data_manager') or \
           not hasattr(self.main_window, 'process_table') or \
           not hasattr(self.main_window, 'COL_NAME'):
            print("GuiNotificationHandler: MainWindow에 필수 속성(data_manager, process_table, COL_NAME)이 없습니다.")
            QMessageBox.warning(self.main_window, "오류", "알림 처리 중 내부 오류 발생.")
            return

        target_process = self.main_window.data_manager.get_process_by_id(task_id)
        target_process_name = target_process.name if target_process else "알 수 없는 작업"

        found_item = None
        for row in range(self.main_window.process_table.rowCount()):
            name_item = self.main_window.process_table.item(row, self.main_window.COL_NAME)
            if name_item and name_item.data(Qt.ItemDataRole.UserRole) == task_id:
                found_item = name_item
                break

        if found_item:
            self.main_window.process_table.scrollToItem(found_item, QAbstractItemView.ScrollHint.PositionAtCenter)
            # Optionally, you could select the row if selection is enabled,
            # or briefly change its appearance for highlighting.
            # self.main_window.process_table.selectRow(found_item.row())
            QMessageBox.information(
                self.main_window,
                "알림 작업",
                f"'{target_process_name}' 작업과(와) 관련된 알림입니다."
            )
        else:
            QMessageBox.information(
                self.main_window,
                "알림 작업",
                f"알림을 받은 작업 ID '{task_id}' ({target_process_name})을(를) 현재 목록에서 찾을 수 없습니다."
            )