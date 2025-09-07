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
:: --hidden-import: PySide6 관련 모듈들을 명시적으로 포함
pyinstaller --noconfirm --onefile --windowed --icon="img\app_icon.ico" --distpath="release" --workpath="build" --add-data="img;img" --add-data="font;font" --hidden-import=PySide6.QtCore --hidden-import=PySide6.QtWidgets --hidden-import=PySide6.QtGui --hidden-import=PySide6.QtNetwork --hidden-import=PySide6.QtMultimedia --hidden-import=PySide6.QtMultimediaWidgets --hidden-import=PySide6.QtPositioning --hidden-import=PySide6.QtQml --hidden-import=PySide6.QtQuick --hidden-import=PySide6.QtQuickWidgets --hidden-import=PySide6.QtSensors --hidden-import=PySide6.QtSql --hidden-import=PySide6.QtSvgWidgets --hidden-import=PySide6.QtTextToSpeech --hidden-import=PySide6.QtWebChannel --hidden-import=PySide6.QtWebEngineCore --hidden-import=PySide6.QtWebEngine --hidden-import=PySide6.QtWebView --hidden-import=PySide6.Qt3DCore --hidden-import=PySide6.Qt3DRender --hidden-import=PySide6.Qt3DInput --hidden-import=PySide6.Qt3DLogic --hidden-import=PySide6.Qt3DAnimation --hidden-import=PySide6.Qt3DExtras --hidden-import=PySide6.QtCharts --hidden-import=PySide6.QtDataVisualization --hidden-import=PySide6.QtDesigner --hidden-import=PySide6.QtHelp --hidden-import=PySide6.QtLocation --hidden-import=PySide6.QtOpenGLWidgets --hidden-import=PySide6.QtPdf --hidden-import=PySide6.QtPdfWidgets --hidden-import=PySide6.QtRemoteObjects --hidden-import=PySide6.QtScxml --hidden-import=PySide6.QtStateMachine --hidden-import=PySide6.QtSvg --hidden-import=PySide6.QtTest --hidden-import=PySide6.QtUiTools --hidden-import=PySide6.QtWebEngineWidgets --hidden-import=PySide6.QtWebSockets --hidden-import=PySide6.QtXml --hidden-import=PySide6.QtOpenGL --hidden-import=PySide6.QtPrintSupport --hidden-import=PySide6.QtSvg --hidden-import=PySide6.QtTest --hidden-import=PySide6.QtUiTools --hidden-import=PySide6.QtWebEngineWidgets --hidden-import=PySide6.QtWebSockets --hidden-import=PySide6.QtXml --hidden-import=PySide6.QtNetwork --hidden-import=PySide6.QtMultimedia --hidden-import=PySide6.QtMultimediaWidgets --hidden-import=PySide6.QtPositioning --hidden-import=PySide6.QtQml --hidden-import=PySide6.QtQuick --hidden-import=PySide6.QtQuickWidgets --hidden-import=PySide6.QtSensors --hidden-import=PySide6.QtSql --hidden-import=PySide6.QtSvgWidgets --hidden-import=PySide6.QtTextToSpeech --hidden-import=PySide6.QtWebChannel --hidden-import=PySide6.QtWebEngineCore --hidden-import=PySide6.QtWebEngine --hidden-import=PySide6.QtWebView --hidden-import=PySide6.Qt3DCore --hidden-import=PySide6.Qt3DRender --hidden-import=PySide6.Qt3DInput --hidden-import=PySide6.Qt3DLogic --hidden-import=PySide6.Qt3DAnimation --hidden-import=PySide6.Qt3DExtras --hidden-import=PySide6.QtCharts --hidden-import=PySide6.QtDataVisualization --hidden-import=PySide6.QtDesigner --hidden-import=PySide6.QtHelp --hidden-import=PySide6.QtLocation --hidden-import=PySide6.QtOpenGLWidgets --hidden-import=PySide6.QtPdf --hidden-import=PySide6.QtPdfWidgets --hidden-import=PySide6.QtRemoteObjects --hidden-import=PySide6.QtScxml --hidden-import=PySide6.QtStateMachine python\homework_helper_widget.pyw

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
