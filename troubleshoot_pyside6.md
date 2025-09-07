# PySide6 패키징 문제 해결 가이드

## 문제 상황
```
ModuleNotFoundError: No module named 'PySide6'
```

## 해결 방법

### 1. 가상환경에서 PySide6 설치 확인
```bash
# 가상환경 활성화
.venv\Scripts\activate

# PySide6 설치 확인
pip list | findstr PySide6

# PySide6 재설치 (필요시)
pip uninstall PySide6
pip install PySide6==6.9.2
```

### 2. PyInstaller 버전 확인
```bash
pip install --upgrade pyinstaller
```

### 3. 빌드 방법 선택

#### 방법 1: 간단한 빌드 (권장)
```bash
build_widget_simple.bat
```

#### 방법 2: spec 파일 사용
```bash
build_widget_spec.bat
```

#### 방법 3: 수동 명령어
```bash
pyinstaller --onefile --windowed --collect-all=PySide6 python\homework_helper_widget.pyw
```

### 4. 문제가 지속되는 경우

#### 4.1 가상환경 재생성
```bash
# 기존 가상환경 삭제
rmdir /s /q .venv

# 새 가상환경 생성
python -m venv .venv
.venv\Scripts\activate

# 필요한 패키지 설치
pip install -r requirements.txt
```

#### 4.2 PyInstaller 캐시 삭제
```bash
# PyInstaller 캐시 삭제
rmdir /s /q build
rmdir /s /q dist
del *.spec
```

#### 4.3 디버그 모드로 빌드
```bash
pyinstaller --onefile --console --collect-all=PySide6 python\homework_helper_widget.pyw
```

### 5. 실행 파일 테스트
```bash
# 빌드된 실행 파일 테스트
release\homework_helper_widget.exe
```

## 추가 정보

- PySide6는 Qt6의 Python 바인딩입니다
- PyInstaller가 PySide6를 자동으로 감지하지 못할 수 있습니다
- `--collect-all=PySide6` 옵션을 사용하면 모든 PySide6 모듈을 포함합니다
- spec 파일을 사용하면 더 정확한 제어가 가능합니다
