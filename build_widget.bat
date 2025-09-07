@echo OFF
chcp 65001 > nul
setlocal

echo.
echo ==================================================
echo  Homework Helper Widget 패키징을 시작합니다...
echo ==================================================
echo.
echo 가상 환경을 활성화합니다...
call .\.venv\Scripts\activate

:: PyInstaller 실행
:: --noconfirm: build 폴더가 이미 있을 경우 덮어쓰기 전 묻지 않음
pyinstaller --noconfirm --onefile --windowed --icon="img\app_icon.ico" --distpath="release" --workpath="build" --add-data="img;img" --add-data="font;font" python\homework_helper_widget.pyw

:: requirements.txt 업데이트
pip freeze > requirements.txt

:: 빌드 성공 여부 확인
if %errorlevel% neq 0 (
    echo.
    echo !!!!!!!!!!  패키징 실패  !!!!!!!!!!
    echo.
    echo PyInstaller가 출력한 오류 메시지를 확인하세요.
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo ==================================================
echo  패키징 성공! 임시 파일을 정리합니다...
echo ==================================================
echo.

:: 불필요한 파일 및 폴더 삭제
echo 'homework_helper_widget.spec' 파일을 삭제합니다...
del homework_helper_widget.spec

echo 'build' 폴더를 삭제합니다...
rmdir /s /q build

echo.
echo ==================================================
echo  모든 작업 완료!
echo.
echo  'release' 폴더에서 homework_helper_widget.exe 파일을 확인하세요.
echo ==================================================
echo.
pause