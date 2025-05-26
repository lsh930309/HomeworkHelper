# launcher.py
import subprocess
import shlex
import os
import ctypes
import configparser # .url 파일 파싱을 위해 추가
from typing import Optional # 타입 힌트를 위해 추가

class Launcher:
    def __init__(self):
        pass

    def _get_url_from_file(self, file_path: str) -> Optional[str]:
        """
        .url 파일에서 URL 문자열을 추출합니다.
        configparser의 interpolation 기능을 비활성화하여 '%' 관련 오류를 방지합니다.
        """
        try:
            # interpolation=None으로 설정하여 '%' 문자로 인한 오류 방지
            parser = configparser.ConfigParser(interpolation=None) 
            
            # .url 파일은 다양한 인코딩을 가질 수 있습니다. utf-8을 먼저 시도하고, 실패 시 시스템 기본 인코딩을 시도합니다.
            # BOM(Byte Order Mark)이 있는 UTF-8 파일도 처리하기 위해 utf-8-sig 사용 가능성 고려
            try:
                # configparser.read는 파일 목록을 받을 수 있으므로 리스트로 전달
                parsed_files = parser.read(file_path, encoding='utf-8-sig') 
                if not parsed_files: # 파일 읽기 실패 시 (예: 파일 없음, 권한 없음)
                    # utf-8-sig로 실패 시 일반 utf-8로 재시도
                    parsed_files = parser.read(file_path, encoding='utf-8')
                    if not parsed_files:
                         # 그래도 실패하면 시스템 기본 인코딩으로 재시도
                        print(f"  '{file_path}' utf-8, utf-8-sig 디코딩 실패, 시스템 기본 인코딩으로 재시도.")
                        parsed_files = parser.read(file_path)

                if not parsed_files: # 모든 시도 후에도 파일 읽기 실패
                    print(f"오류: '{file_path}' 파일을 읽을 수 없습니다.")
                    return None

            except UnicodeDecodeError as ude: # 특정 인코딩으로 디코딩 실패 시
                print(f"  '{file_path}' 파일 디코딩 오류 발생: {ude}. 다른 방법으로 URL 추출 시도.")
                # configparser 실패 시 수동으로 URL= 패턴 검색
                # (이 부분은 configparser가 파일을 아예 못 읽는 경우보다는,
                #  형식이 약간 다르거나 섹션이 없을 때의 대비책으로 더 유용)
                pass # 아래 수동 검색 로직으로 넘어감
            except Exception as e_read: # 파일 읽기 중 기타 예외
                print(f"오류: '{file_path}' 파일 읽기 중 예외 발생: {e_read}")
                return None


            if 'InternetShortcut' in parser and 'URL' in parser['InternetShortcut']:
                url = parser['InternetShortcut']['URL']
                # 가끔 URL 값 양쪽에 불필요한 따옴표가 있는 경우가 있어 제거
                return url.strip('"') 
            
            # configparser로 못찾았거나, 섹션이 없는 매우 단순한 .url 파일 (URL=... 만 있는 경우)
            print(f"  '{file_path}' 에서 [InternetShortcut] 섹션의 URL을 찾지 못함. 수동으로 'URL=' 패턴 검색 시도.")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    cleaned_line = line.strip()
                    if cleaned_line.upper().startswith("URL="):
                        url_value = cleaned_line[len("URL="):]
                        return url_value.strip('"') # 여기서도 따옴표 제거
            
            print(f"오류: '{file_path}' .url 파일에서 URL 정보를 추출하지 못했습니다.")
            return None
        except configparser.Error as e_cfg: # configparser 관련 다른 오류 (거의 발생 안 할 것으로 예상)
            print(f"오류: '{file_path}' .url 파일 파싱 중 오류 발생 (configparser): {e_cfg}")
            return None
        except Exception as e: # 그 외 모든 예외
            print(f"오류: '{file_path}' .url 파일 처리 중 예기치 않은 예외 발생: {e}")
            return None

    def launch_process(self, launch_command: str) -> bool:
        if not launch_command:
            print("오류: 실행할 경로 또는 명령어가 제공되지 않았습니다.")
            return False

        print(f"다음 명령어로 프로세스 실행 시도: {launch_command}")
        
        try:
            # 1. .url 파일 처리 (Windows 우선)
            if launch_command.lower().endswith(".url"):
                print(f"  감지된 .url 파일: {launch_command}")
                url_to_launch = self._get_url_from_file(launch_command)
                if url_to_launch:
                    print(f"  추출된 URL: {url_to_launch}")
                    if os.name == 'nt':
                        try:
                            os.startfile(url_to_launch)
                            print(f"  '{url_to_launch}' URL 실행을 os.startfile로 시도했습니다.")
                            return True
                        except Exception as e_url_start:
                            print(f"  os.startfile로 URL '{url_to_launch}' 실행 중 오류: {e_url_start}")
                            print(f"  os.startfile 실패, ShellExecuteW (verb='open')으로 재시도합니다...")
                            try:
                                shell32 = ctypes.windll.shell32
                                ret = shell32.ShellExecuteW(None, "open", url_to_launch, None, None, 1)
                                if ret > 32:
                                    print(f"  '{url_to_launch}' URL 실행을 ShellExecuteW (open)로 요청했습니다. (반환 값: {ret})")
                                    return True
                                else:
                                    print(f"  ShellExecuteW (open)로 URL '{url_to_launch}' 실행 실패. 반환 코드: {ret}")
                                    return False
                            except Exception as e_shell_url:
                                print(f"  ShellExecuteW로 URL '{url_to_launch}' 실행 중 예외: {e_shell_url}")
                                return False
                    else: # 비-Windows
                        print(f"  비-Windows 환경({os.name})에서는 .url 파일 내 URL을 webbrowser로 실행 시도합니다.")
                        import webbrowser
                        try:
                            if webbrowser.open(url_to_launch):
                                print(f"  webbrowser.open으로 '{url_to_launch}' 실행 성공 (또는 시도됨).")
                                return True
                            else: # 일부 플랫폼에서는 open이 bool을 반환하지 않거나 항상 True일 수 있음
                                print(f"  webbrowser.open으로 '{url_to_launch}' 실행했으나, 명시적인 성공 반환값 없음.")
                                return True # 시도 자체를 성공으로 간주
                        except Exception as e_wb:
                            print(f"  webbrowser.open으로 URL '{url_to_launch}' 실행 중 오류: {e_wb}")
                            return False
                else:
                    return False # URL 추출 실패

            # 2. .lnk 파일 처리 (Windows 전용)
            elif launch_command.lower().endswith(".lnk"):
                # ... (이전 .lnk 처리 로직과 동일) ...
                if os.name == 'nt':
                    try:
                        os.startfile(launch_command)
                        print(f"  '{launch_command}' (.lnk 파일) 실행을 os.startfile로 시도했습니다.")
                        return True
                    except Exception as e_lnk_start:
                        print(f"  os.startfile로 .lnk '{launch_command}' 실행 중 오류: {e_lnk_start}")
                        return False
                else:
                    print(f"오류: .lnk 파일 실행은 Windows에서만 직접 지원됩니다. (현재 OS: {os.name})")
                    return False
            
            # 3. 기타 실행 파일 또는 명령어 (기존 로직 유지)
            else:
                if os.name == 'nt':
                    shell32 = ctypes.windll.shell32
                    print(f"  ShellExecuteW 호출 시도: verb='runas', file='{launch_command}', params=None")
                    # 관리자 권한 실행('runas')은 필요한 경우에만 사용. 일반 실행은 'open' 사용 가능.
                    # 현재는 기존 로직대로 'runas' 유지.
                    ret = shell32.ShellExecuteW(None, "runas", launch_command, None, None, 1) # SW_SHOWNORMAL = 1
                    if ret > 32:
                        print(f"  '{launch_command}' 실행을 ShellExecuteW (runas)로 요청했습니다. (반환 값: {ret})")
                        return True
                    else:
                        win_error_code = ret 
                        print(f"  ShellExecuteW (runas) 실패. 반환/오류 코드: {win_error_code}")
                        if win_error_code == 0: print("    오류 원인: 시스템 리소스 부족 또는 매우 심각한 오류.")
                        elif win_error_code == 2: print("    오류 원인: 지정된 파일을 찾을 수 없습니다.")
                        elif win_error_code == 3: print("    오류 원인: 지정된 경로를 찾을 수 없습니다.")
                        elif win_error_code == 5: print("    오류 원인: 접근이 거부되었습니다 (파일 권한 문제).")
                        elif win_error_code == 1223: print("    사용자가 UAC 프롬프트에서 작업을 취소했습니다.")
                        return False
                else: 
                    try:
                        args = shlex.split(launch_command, posix=True)
                        subprocess.Popen(args)
                        print(f"  프로세스 실행 시도 완료 (비 Windows): {args}")
                        return True
                    except Exception as e_shlex:
                        print(f"  비 Windows 환경 shlex.split 또는 Popen 오류: {e_shlex}")
                        return False
                        
        except FileNotFoundError: # 주로 subprocess.Popen에서 발생
            print(f"오류: 파일을 찾을 수 없습니다 - {launch_command}")
            return False
        except Exception as e: # 그 외 예외 처리
            print(f"프로세스 실행 중 예기치 않은 예외 발생: {e}")
            return False