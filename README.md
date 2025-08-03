# 숙제 관리자 (Homework Helper)

[![Python](httpshttps://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GUI](https://img.shields.io/badge/GUI-PyQt6-orange)](https://riverbankcomputing.com/software/pyqt/)

게임의 일일 과제와 웹사이트 방문을 관리하고, 알림을 통해 놓치지 않도록 도와주는 Windows 데스크톱 애플리케이션입니다.

---

## ✨ 주요 기능

- 🎮 **게임 관리:** 실행 여부를 모니터링하고 마지막 플레이 시간을 기반으로 진행률을 표시합니다.
- 🌐 **웹 바로가기:** 자주 가는 사이트를 버튼으로 추가하고, 초기화 시간에 따라 완료 여부를 색상으로 표시합니다.
- ⏰ **맞춤 알림:** 서버 리셋, 주기 만료, 특정 시간 등 원하는 조건에 맞춰 Windows 알림을 받습니다.
- ⚙️ **편의 기능:**
    - 시스템 트레이 지원
    - Windows 시작 시 자동 실행
    - 항상 위(Always on Top) 설정
    - 수면 시간대 알림 보정

## 🚀 시작하기

### 1. 설치 파일 다운로드 (권장)

가장 쉬운 방법은 최신 릴리즈 페이지에서 설치 파일을 다운로드하는 것입니다.

1.  **[최신 릴리즈 페이지](https://github.com/lsh930309/HomeworkHelper/releases)로 이동합니다.**
2.  `Assets` 목록에서 `homework_helper.exe` 파일을 다운로드합니다.
3.  다운로드한 파일을 실행합니다.

### 2. 소스 코드로 직접 실행 (개발자용)

Python 개발 환경이 준비된 경우, 다음 단계를 따라 직접 실행할 수 있습니다.

```bash
# 1. 이 저장소를 클론합니다.
git clone https://github.com/lsh930309/HomeworkHelper.git
cd HomeworkHelper

# 2. 가상 환경을 생성하고 활성화합니다.
python -m venv .venv
.venv\Scripts\activate # Windows

# 3. 필요한 패키지를 설치합니다.
pip install -r requirements.txt

# 4. 애플리케이션을 실행합니다.
python python/homework_helper.pyw
```

## 🖼️ 스크린샷

*(여기에 애플리케이션 스크린샷을 추가하면 좋습니다.)*

![App Screenshot](img/app_icon.png)


## 📜 라이선스

본 프로젝트는 [MIT 라이선스](LICENSE)를 따릅니다.