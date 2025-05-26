# data_models.py
import datetime
import uuid # 프로세스 ID 생성을 위해 추가
from typing import List, Optional, Dict

class ManagedProcess:
    def __init__(self,
                 name: str,
                 monitoring_path: str,
                 launch_path: str,
                 id: Optional[str] = None, # ID는 내부적으로 생성
                 server_reset_time_str: Optional[str] = None, # "HH:MM"
                 user_cycle_hours: Optional[int] = 24, # 기본값 24시간
                 mandatory_times_str: Optional[List[str]] = None,
                 is_mandatory_time_enabled: bool = False,
                 last_played_timestamp: Optional[float] = None): # Unix timestamp
        
        self.id = id if id else str(uuid.uuid4()) # ID가 없으면 새로 생성
        self.name = name
        self.monitoring_path = monitoring_path
        self.launch_path = launch_path
        
        self.server_reset_time_str = server_reset_time_str
        self.user_cycle_hours = user_cycle_hours
        self.mandatory_times_str = mandatory_times_str if mandatory_times_str else []
        self.is_mandatory_time_enabled = is_mandatory_time_enabled
        
        self.last_played_timestamp = last_played_timestamp

    def __repr__(self):
        return f"<ManagedProcess(id='{self.id}', name='{self.name}')>"

    def to_dict(self) -> Dict:
        """JSON 저장을 위해 객체를 딕셔너리로 변환합니다."""
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict) -> 'ManagedProcess':
        """딕셔너리에서 객체를 생성합니다 (JSON 로드 시 사용)."""
        return cls(**data)

class GlobalSettings:
    def __init__(self,
                 sleep_start_time_str: str = "00:00",
                 sleep_end_time_str: str = "08:00",
                 sleep_correction_advance_notify_hours: float = 1.0,
                 cycle_deadline_advance_notify_hours: float = 2.0,
                 run_on_startup: bool = False): # <<< run_on_startup 추가
        
        self.sleep_start_time_str = sleep_start_time_str
        self.sleep_end_time_str = sleep_end_time_str
        self.sleep_correction_advance_notify_hours = sleep_correction_advance_notify_hours
        self.cycle_deadline_advance_notify_hours = cycle_deadline_advance_notify_hours
        self.run_on_startup = run_on_startup # <<< 새 속성 초기화

    def to_dict(self) -> Dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict) -> 'GlobalSettings':
        # 이전 버전과의 호환성을 위해 run_on_startup이 없을 경우 기본값 False 사용
        if 'run_on_startup' not in data:
            data['run_on_startup'] = False
        return cls(**data)