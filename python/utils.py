# utils.py
import sys
import os
import shutil
from typing import Optional

def resource_path(relative_path):
    """ 개발 환경 및 PyInstaller 환경 모두에서 리소스 파일의 절대 경로를 반환합니다. """
    try:
        # PyInstaller는 임시 폴더를 만들고 그 경로를 _MEIPASS에 저장합니다.
        # type: ignore[attr-defined] - PyInstaller에서만 존재하는 속성
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        # _MEIPASS가 정의되지 않았다면 개발 환경입니다.
        # 이 함수가 utils.py 안에 있고, utils.py가 workspace/python/ 안에 있다고 가정합니다.
        # 따라서 __file__은 workspace/python/utils.py의 경로가 됩니다.
        # workspace 폴더를 찾기 위해 두 단계 위로 올라갑니다.
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    return os.path.join(base_path, relative_path)

def get_shortcuts_directory() -> str:
    """homework_helper_data/shortcuts 디렉토리 경로를 반환합니다."""
    # 현재 스크립트 위치에서 homework_helper_data/shortcuts 경로 계산
    current_dir = os.path.dirname(os.path.abspath(__file__))
    shortcuts_dir = os.path.join(current_dir, "homework_helper_data", "shortcuts")
    return os.path.abspath(shortcuts_dir)

def ensure_shortcuts_directory() -> bool:
    """shortcuts 디렉토리가 존재하는지 확인하고, 없으면 생성합니다."""
    shortcuts_dir = get_shortcuts_directory()
    try:
        if not os.path.exists(shortcuts_dir):
            os.makedirs(shortcuts_dir, exist_ok=True)
        return True
    except Exception as e:
        print(f"shortcuts 디렉토리 생성 실패: {e}")
        return False

def copy_shortcut_file(source_path: str) -> Optional[str]:
    """바로가기 파일을 shortcuts 디렉토리에 복사하고 복사된 경로를 반환합니다."""
    if not os.path.exists(source_path):
        print(f"원본 파일이 존재하지 않습니다: {source_path}")
        return None
    
    # 파일 확장자 확인
    file_ext = os.path.splitext(source_path)[1].lower()
    if file_ext not in ['.lnk', '.url', '.exe', '.bat', '.cmd']:
        print(f"지원하지 않는 파일 형식입니다: {file_ext}")
        return None
    
    # shortcuts 디렉토리 확인/생성
    if not ensure_shortcuts_directory():
        return None
    
    shortcuts_dir = get_shortcuts_directory()
    
    # 원본 파일명 가져오기
    original_filename = os.path.basename(source_path)
    name, ext = os.path.splitext(original_filename)
    
    # 중복 방지를 위한 파일명 생성
    counter = 1
    new_filename = original_filename
    new_path = os.path.join(shortcuts_dir, new_filename)
    
    while os.path.exists(new_path):
        new_filename = f"{name}_{counter}{ext}"
        new_path = os.path.join(shortcuts_dir, new_filename)
        counter += 1
    
    try:
        # 파일 복사
        shutil.copy2(source_path, new_path)
        print(f"바로가기 파일 복사 완료: {source_path} → {new_path}")
        return new_path
    except Exception as e:
        print(f"바로가기 파일 복사 실패: {e}")
        return None