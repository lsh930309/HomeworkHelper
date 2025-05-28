# utils.py
import sys
import os

def resource_path(relative_path):
    """ 개발 환경 및 PyInstaller 환경 모두에서 리소스 파일의 절대 경로를 반환합니다. """
    try:
        # PyInstaller는 임시 폴더를 만들고 그 경로를 _MEIPASS에 저장합니다.
        base_path = sys._MEIPASS
    except Exception:
        # _MEIPASS가 정의되지 않았다면 개발 환경입니다.
        # 이 함수가 utils.py 안에 있고, utils.py가 workspace/python/ 안에 있다고 가정합니다.
        # 따라서 __file__은 workspace/python/utils.py의 경로가 됩니다.
        # workspace 폴더를 찾기 위해 두 단계 위로 올라갑니다.
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    return os.path.join(base_path, relative_path)