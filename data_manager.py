# data_manager.py
import json
import os
from typing import List, Optional, Dict
from data_models import ManagedProcess, GlobalSettings # 바로 위 파일에서 정의한 클래스 임포트

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
        
        self.global_settings: GlobalSettings = self._load_global_settings()
        self.managed_processes: List[ManagedProcess] = self._load_managed_processes()

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