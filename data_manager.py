# data_manager.py
import json
import os
from typing import List, Optional, Dict
from data_models import ManagedProcess, GlobalSettings, WebShortcut # 바로 위 파일에서 정의한 클래스 임포트

class DataManager:
    """
    ManagedProcess 객체들과 GlobalSettings 객체를 JSON 파일에서 로드하고 저장합니다.
    """
    def __init__(self, data_folder: str = "app_data"):
        self.data_folder = data_folder
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder) # 데이터 저장 폴더 생성

        self.settings_file_path = os.path.join(self.data_folder, "global_settings.json")
        self.processes_file_path = os.path.join(self.data_folder, "managed_processes.json")
        self.web_shortcuts_file_path = os.path.join(self.data_folder, "web_shortcuts.json")
        
        self.global_settings: GlobalSettings = self._load_global_settings()
        self.managed_processes: List[ManagedProcess] = self._load_managed_processes()
        self.web_shortcuts: List[WebShortcut] = self._load_web_shortcuts()

    def _load_global_settings(self) -> GlobalSettings:
        """파일에서 전역 설정을 로드합니다. 파일이 없으면 기본값으로 객체를 생성합니다."""
        if os.path.exists(self.settings_file_path):
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return GlobalSettings.from_dict(data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading global settings: {e}. Using default settings.")
                return GlobalSettings() # 오류 발생 시 기본 설정 사용
        return GlobalSettings() # 파일 없을 시 기본 설정 사용

    def save_global_settings(self):
        """파일에 현재 전역 설정을 저장합니다."""
        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.global_settings.to_dict(), f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Error saving global settings: {e}")

    def _load_managed_processes(self) -> List[ManagedProcess]:
        """파일에서 관리 대상 프로세스 목록을 로드합니다."""
        if os.path.exists(self.processes_file_path):
            try:
                with open(self.processes_file_path, 'r', encoding='utf-8') as f:
                    data_list = json.load(f)
                    return [ManagedProcess.from_dict(data) for data in data_list]
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading managed processes: {e}. Returning empty list.")
                return [] # 오류 발생 시 빈 목록 반환
        return [] # 파일 없을 시 빈 목록 반환

    def save_managed_processes(self):
        """파일에 현재 관리 대상 프로세스 목록을 저장합니다."""
        try:
            data_list = [process.to_dict() for process in self.managed_processes]
            with open(self.processes_file_path, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Error saving managed processes: {e}")

    def add_process(self, process: ManagedProcess) -> bool:
        """새로운 프로세스를 목록에 추가하고 저장합니다."""
        if any(p.id == process.id for p in self.managed_processes):
            print(f"Process with ID {process.id} already exists.")
            return False
        self.managed_processes.append(process)
        self.save_managed_processes()
        return True

    def remove_process(self, process_id: str) -> bool:
        """ID로 프로세스를 찾아 목록에서 제거하고 저장합니다."""
        initial_len = len(self.managed_processes)
        self.managed_processes = [p for p in self.managed_processes if p.id != process_id]
        if len(self.managed_processes) < initial_len:
            self.save_managed_processes()
            return True
        print(f"Process with ID {process_id} not found.")
        return False

    def update_process(self, updated_process: ManagedProcess) -> bool:
        """기존 프로세스 정보를 업데이트하고 저장합니다."""
        for i, p in enumerate(self.managed_processes):
            if p.id == updated_process.id:
                self.managed_processes[i] = updated_process
                self.save_managed_processes()
                return True
        print(f"Process with ID {updated_process.id} not found for update.")
        return False

    def get_process_by_id(self, process_id: str) -> Optional[ManagedProcess]:
        """ID로 프로세스를 찾아 반환합니다."""
        for process in self.managed_processes:
            if process.id == process_id:
                return process
        return None
    
    def _load_web_shortcuts(self) -> List[WebShortcut]:
        """ 저장된 웹 바로 가기 목록을 불러옵니다. 파일이 없거나 비어있으면 기본값을 생성합니다. """
        shortcuts = []
        file_exists = os.path.exists(self.web_shortcuts_file_path)
        
        if file_exists:
            try:
                with open(self.web_shortcuts_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded_data = data.get("web_shortcuts")
                    if isinstance(loaded_data, list):
                        shortcuts = [WebShortcut.from_dict(item) for item in loaded_data]
                    else:
                        print(f"경고: '{self.web_shortcuts_file_path}' 파일 형식이 잘못되었거나 'web_shortcuts' 리스트가 없습니다. 기본값으로 대체합니다.")
                        file_exists = False 
            except (IOError, json.JSONDecodeError, TypeError) as e:
                print(f"웹 바로 가기 파일 로드 오류: {e}. 기본값으로 대체합니다.")
                file_exists = False
        
        if not file_exists or not shortcuts: # 파일이 없거나, 있었지만 비어있거나, 로드에 실패한 경우
            print("웹 바로 가기 데이터가 없거나 로드에 실패하여 기본값을 생성합니다.")
            default_shortcuts = [
                WebShortcut(
                    name="스타레일 출석",
                    url="https://act.hoyolab.com/bbs/event/signin/hkrpg/e202303301540311.html?act_id=e202303301540311&bbs_auth_required=true&bbs_presentation_style=fullscreen&lang=ko-kr&utm_source=share&utm_medium=link&utm_campaign=web",
                    refresh_time_str="05:00" # 예시: 매일 새벽 5시 초기화
                ),
                WebShortcut(
                    name="젠존제 출석",
                    url="https://act.hoyolab.com/bbs/event/signin/zzz/e202406031448091.html?act_id=e202406031448091&bbs_auth_required=true&bbs_presentation_style=fullscreen&lang=ko-kr&utm_source=share&utm_medium=link&utm_campaign=web",
                    refresh_time_str="05:00" # 예시: 매일 새벽 5시 초기화
                )
            ]
            # last_reset_timestamp는 초기에 None으로 설정됨 (WebShortcut 생성자 기본값)
            shortcuts = default_shortcuts
            self._save_web_shortcuts(shortcuts) 
            
        return shortcuts

    def _save_web_shortcuts(self, shortcuts: List[WebShortcut]):
        """ 웹 바로 가기 목록을 파일에 저장합니다. """
        try:
            with open(self.web_shortcuts_file_path, 'w', encoding='utf-8') as f:
                # WebShortcut 객체를 딕셔너리로 변환하여 저장
                json.dump({"web_shortcuts": [sc.to_dict() for sc in shortcuts]}, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"웹 바로 가기 파일 저장 오류: {e}")

    def get_web_shortcuts(self) -> List[WebShortcut]:
        """ 모든 웹 바로 가기 목록을 반환합니다. """
        return list(self.web_shortcuts) # 복사본 반환

    def add_web_shortcut(self, shortcut: WebShortcut) -> bool:
        """ 새 웹 바로 가기를 추가합니다. """
        if not isinstance(shortcut, WebShortcut):
            return False
        # 이름 중복 방지 (선택 사항)
        # if any(sc.name == shortcut.name for sc in self.web_shortcuts):
        #     print(f"오류: 웹 바로 가기 이름 '{shortcut.name}'이(가) 이미 존재합니다.")
        #     return False
        self.web_shortcuts.append(shortcut)
        self._save_web_shortcuts(self.web_shortcuts)
        print(f"웹 바로 가기 추가됨: {shortcut.name}")
        return True

    def get_web_shortcut_by_id(self, shortcut_id: str) -> Optional[WebShortcut]:
        """ ID로 웹 바로 가기를 찾습니다. """
        for shortcut in self.web_shortcuts:
            if shortcut.id == shortcut_id:
                return shortcut
        return None

    def update_web_shortcut(self, updated_shortcut: WebShortcut) -> bool:
        """ 기존 웹 바로 가기 정보를 업데이트합니다. """
        for i, shortcut in enumerate(self.web_shortcuts):
            if shortcut.id == updated_shortcut.id:
                self.web_shortcuts[i] = updated_shortcut
                self._save_web_shortcuts(self.web_shortcuts)
                print(f"웹 바로 가기 업데이트됨: {updated_shortcut.name}")
                return True
        print(f"오류: 업데이트할 웹 바로 가기 ID '{updated_shortcut.id}'을(를) 찾을 수 없습니다.")
        return False

    def remove_web_shortcut(self, shortcut_id: str) -> bool:
        """ ID로 웹 바로 가기를 삭제합니다. """
        original_len = len(self.web_shortcuts)
        self.web_shortcuts = [sc for sc in self.web_shortcuts if sc.id != shortcut_id]
        if len(self.web_shortcuts) < original_len:
            self._save_web_shortcuts(self.web_shortcuts)
            print(f"웹 바로 가기 ID '{shortcut_id}' 삭제됨.")
            return True
        print(f"오류: 삭제할 웹 바로 가기 ID '{shortcut_id}'을(를) 찾을 수 없습니다.")
        return False