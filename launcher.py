# launcher.py
import subprocess
import shlex # 비-Windows 환경 또는 subprocess 대체 사용 시 여전히 필요할 수 있음
import os
import ctypes

class Launcher:
    def __init__(self):
        pass

    def launch_process(self, launch_command: str) -> bool:
        if not launch_command:
            print("오류: 실행할 경로 또는 명령어가 제공되지 않았습니다.")
            return False

        print(f"다음 명령어로 프로세스 실행 시도: {launch_command}")
        
        try:
            if launch_command.lower().endswith(".lnk"):
                if os.name == 'nt':
                    os.startfile(launch_command)
                    print(f"'{launch_command}' (.lnk 파일) 실행을 os.startfile로 시도했습니다.")
                    return True
                else:
                    print(f"오류: .lnk 파일 실행은 Windows에서만 직접 지원됩니다. (현재 OS: {os.name})")
                    return False
            else:
                # .exe 파일 또는 인자를 포함한 전체 명령어 문자열의 경우
                if os.name == 'nt':
                    shell32 = ctypes.windll.shell32
                    
                    # lpFile에 전체 launch_command를 전달하고, lpParameters는 None으로 설정.
                    # ShellExecuteW가 내부적으로 파싱합니다.
                    # 작동 디렉토리(lpDirectory)는 None으로 설정하면 OS가 적절히 처리하거나,
                    # 필요시 명령어에서 실행 파일 경로를 추출하여 설정할 수도 있습니다. (일단 None)
                    print(f"  ShellExecuteW 호출 시도: verb='runas', file='{launch_command}', params=None")
                    ret = shell32.ShellExecuteW(None, "runas", launch_command, None, None, 1) # SW_SHOWNORMAL = 1

                    if ret > 32:
                        print(f"'{launch_command}' 실행을 ShellExecuteW (runas)로 요청했습니다. (반환 값: {ret})")
                        return True
                    else:
                        # ShellExecuteW의 반환 값 < 32는 오류를 의미.
                        # ctypes.get_last_error()는 이 컨텍스트에서 항상 정확하지 않을 수 있으므로,
                        # ret 값 자체가 오류 코드일 가능성을 더 고려합니다.
                        win_error_code = ret # ShellExecuteW는 오류 시 오류 코드를 직접 반환할 수 있음
                        print(f"ShellExecuteW (runas) 실패. 반환/오류 코드: {win_error_code}")
                        
                        # 알려진 오류 코드에 대한 설명 추가
                        if win_error_code == 0: # 시스템 메모리 부족 등 매우 심각한 오류
                            print("  오류 원인: 시스템 리소스 부족 또는 매우 심각한 오류.")
                        elif win_error_code == 2: # ERROR_FILE_NOT_FOUND
                            print("  오류 원인: 지정된 파일을 찾을 수 없습니다. 경로를 확인하세요.")
                        elif win_error_code == 3: # ERROR_PATH_NOT_FOUND
                            print("  오류 원인: 지정된 경로를 찾을 수 없습니다.")
                        elif win_error_code == 5: # ERROR_ACCESS_DENIED (UAC 거부와 다름, 파일 접근 권한 문제)
                            print("  오류 원인: 접근이 거부되었습니다. (파일 권한 문제일 수 있음)")
                        elif win_error_code == 1223: # ERROR_CANCELLED (사용자가 UAC 프롬프트에서 '아니요' 선택)
                            print("  사용자가 UAC 프롬프트에서 작업을 취소했습니다.")
                        # 기타 ShellExecuteW 오류 코드 참고 (MSDN)
                        
                        return False # 실행 실패
                else: 
                    # 비-Windows 환경 (이전 로직 유지, 필요시 shlex.split 사용)
                    # 비-Windows에서 공백 포함 경로는 따옴표로 감싸야 shlex.split이 잘 작동합니다.
                    try:
                        args = shlex.split(launch_command, posix=True)
                        subprocess.Popen(args)
                        print(f"프로세스 실행 시도 완료 (비 Windows): {args}")
                        return True
                    except Exception as e_shlex:
                        print(f"비 Windows 환경 shlex.split 또는 Popen 오류: {e_shlex}")
                        return False
                
        except FileNotFoundError: # 이 예외는 주로 shlex.split 이후 Popen에서 발생했었음
            print(f"오류: 파일을 찾을 수 없습니다 - {launch_command}")
            return False
        except Exception as e:
            print(f"프로세스 실행 중 예외 발생: {e}")
            return False