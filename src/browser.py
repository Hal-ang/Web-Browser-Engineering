import socket
import ssl
import os
import sys
from typing import Optional, Dict, Tuple

# 전역 연결 풀: 호스트:포트 -> 소켓 저장
connection_pool = {}

class URL:
    """URL 파싱 및 요청 처리를 위한 클래스"""
    
    def __init__(self, url: str, redirect_count: int = 0) -> None:
        """URL을 파싱하여 구성 요소로 분해합니다.
        
        Args:
            url: 파싱할 URL 문자열 (http, https, file, data 스킴 지원)
            redirect_count: 현재 리다이렉트 횟수 (최대 2번 제한)
        """
        self.scheme: str = ""
        self.host: Optional[str] = None
        self.port: Optional[int] = None
        self.path: str = ""
        self.content_type: Optional[str] = 'text/html'
        self.content: Optional[str] = None
        self.socket: Optional[socket.socket] = None
        self.redirect_count: int = redirect_count  # 리다이렉트 횟수 추가
        self._parse_url(url)
    
    def _parse_url(self, url: str) -> None:
        """URL을 파싱하여 구성 요소를 설정합니다."""
        if url.startswith('data:'):
            self._parse_data_url(url)
            return
            
        if url.startswith('view-source:'):
            self._parse_view_source_url(url)
            return

        try:
            remaining_url = self._parse_scheme_and_url(url)
        except ValueError as e:
            print(e)
            # 로컬 경로
            self._parse_self_url(url)
            return
        
        if self.scheme == 'file':
            self._parse_self_url(remaining_url)
            return

        self._parse_http_url(remaining_url)
    
    def _parse_data_url(self, url: str) -> None:
        """data: URL을 파싱합니다."""
        self.scheme, self.path = url.split(':', 1)
        self.content_type, self.content = self.path.split(',', 1)

    def _parse_view_source_url(self, url: str) -> None:
        """view-source: URL을 파싱합니다."""
        self.scheme, self.url = url.split(':', 1)
        self.content_type = 'text'
        
        remaining_url = self._parse_scheme_and_url(self.url)
        self._parse_http_url(remaining_url)
    
    def _parse_scheme_and_url(self, url: str) -> str:
        """스킴을 분리하고 검증합니다."""
        self.scheme, remaining_url = url.split('://', 1)
        if self.scheme not in ['http', 'https', 'file']:
            raise ValueError(f"지원하지 않는 스킴: {self.scheme}")
        return remaining_url
    
    def _parse_self_url(self, remaining_url: str) -> None:
        """self: URL을 파싱합니다."""
        self.path = '/' + remaining_url
    
    def _parse_http_url(self, remaining_url: str) -> None:
        """HTTP/HTTPS URL을 파싱합니다."""
        url = remaining_url
        
        # 경로가 없는 경우 기본 경로 추가
        if '/' not in url:
            url = url + '/'
            
        self.host, path_part = url.split('/', 1)
        self.path = '/' + path_part
        
        # 기본 포트 설정
        self.port = 443 if self.scheme == 'https' else 80
        
        # 호스트에서 포트 분리
        if ':' in self.host:
            self.host, port_str = self.host.split(':', 1)
            self.port = int(port_str)

    def _parse_self_url(self, remaining_url: str) -> None:
        """self: URL을 파싱합니다."""
        self.path = '/' + remaining_url


    def request(self) -> str:
        """URL에 따라 적절한 요청을 수행하고 응답을 반환합니다."""
        if self.scheme == 'data':
            return self._request_data()
        elif self.scheme == 'file':
            return self._request_file()
        else:  # http or https
            return self._request_http()
    
    def _request_data(self) -> str:
        """data: URL의 내용을 반환합니다."""
        return self.content or ""
    
    def _request_file(self) -> str:
        """로컬 파일을 읽어 반환합니다."""
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: File not found - {self.path}"
        except PermissionError:
            return f"Error: Permission denied - {self.path}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _request_http(self) -> str:
        """HTTP/HTTPS 요청을 수행하고 응답을 반환합니다."""
        # 연결 키 생성 (호스트:포트:스킴)
        connection_key = f"{self.host}:{self.port}:{self.scheme}"
        
        # 기존 연결이 있는지 확인
        if connection_key in connection_pool:
            sock = connection_pool[connection_key]
            print(f"기존 소켓 재사용: {connection_key}")  # 디버깅용
        else:
            # 새 소켓 생성 및 연결
            sock = self._create_socket()
            sock.connect((self.host, self.port))
            connection_pool[connection_key] = sock
            print(f"새 소켓 생성: {connection_key}")  # 디버깅용

        self._send_request(sock)
        response = self._receive_response(sock)
        
        # Content-Length가 있으면 소켓을 열어두고, 없으면 닫음
        return response
    
    def _create_socket(self) -> socket.socket:
        """소켓을 생성하고 HTTPS인 경우 SSL로 래핑합니다."""
        sock = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        
        if self.scheme == 'https':
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=self.host)
        
        return sock
    
    def _send_request(self, sock: socket.socket) -> None:
        """HTTP 요청을 전송합니다."""
        request = f"GET {self.path} HTTP/1.1\r\n"
        request += f"HOST: {self.host}\r\n"
        request += "CONNECTION: Keep-Alive\r\n"

        request += "USER-AGENT: harang/1.0\r\n"
        request += f"CONTENT-TYPE: {self.content_type}\r\n"
        request += "\r\n"
        
        print(request)  # 디버깅용
        sock.send(request.encode('utf-8'))
    
    def _receive_response(self, sock: socket.socket) -> str:
        """HTTP 응답을 수신하고 파싱합니다."""
        response = sock.makefile('r', encoding='utf-8', newline='\r\n')

        # 상태 라인 파싱
        statusline = response.readline()
        print(f"Status: {statusline.strip()}")  # 디버깅용
        
        # 헤더 파싱
        response_headers = self._parse_headers(response)
        

        if response_headers.get('location'):
            redirect_url = response_headers.get('location')
            
            # 리다이렉트 횟수 제한 확인 (최대 2번)
            max_redirects = 2
            if self.redirect_count >= max_redirects:
                error_msg = f"⚠️ 리다이렉트가 너무 많습니다! (최대 {max_redirects}번)"
                print(error_msg)
                return f"<html><body><h1>리다이렉트 제한 초과</h1><p>{error_msg}</p><p>현재 {self.redirect_count}번 리다이렉트됨</p></body></html>"
            
            print(f"🔄 리다이렉트 #{self.redirect_count + 1}: {redirect_url}")
            
            # 새로운 URL 객체 생성 (리다이렉트 횟수 증가)
            new_url = URL(redirect_url, self.redirect_count + 1)
            return new_url.request()
        
        # 지원하지 않는 인코딩 확인
        assert 'transfer-encoding' not in response_headers, "Transfer-Encoding은 지원되지 않습니다"
        assert 'content-encoding' not in response_headers, "Content-Encoding은 지원되지 않습니다"
        
        # Content-Length 헤더를 사용하여 정확한 바이트 수만큼 본문 읽기
        # (keep-alive 연결을 위해 필요)
        content_length = response_headers.get('content-length')
        if content_length:
            # 정확한 바이트 수만큼만 읽음 (소켓을 열어둠)
            body = response.read(int(content_length))
            print(f"Content-Length: {content_length}바이트 읽음 - 소켓 유지")  # 디버깅용
            # 소켓을 닫지 않음! keep-alive로 재사용 가능
        else:
            # Content-Length가 없으면 모든 내용을 읽음 (서버가 연결 종료)
            body = response.read()
            print("Content-Length 없음: 모든 내용 읽음 - 연결 종료")  # 디버깅용
            # 이 경우 서버가 연결을 끊으므로 풀에서 제거
            connection_key = f"{self.host}:{self.port}:{self.scheme}"
            if connection_key in connection_pool:
                del connection_pool[connection_key]
        
        return body
    
    def _parse_headers(self, response) -> Dict[str, str]:
        """HTTP 응답 헤더를 파싱합니다."""

        headers = {}
        
        while True:
            line = response.readline()
            if line == '\r\n':
                break
                
            header, value = line.split(':', 1)
            headers[header.casefold()] = value.strip()
        
        return headers


def show(body: str) -> None:
    """HTML 본문에서 태그를 제거하고 텍스트만 출력합니다.
    
    Args:
        body: 처리할 HTML 문자열
    """
    # body가 None이거나 비어있으면 처리하지 않음
    if not body:
        print("⚠️ 표시할 내용이 없습니다.")
        return
        
    in_tag = False
    
    for char in body:
        # HTML 엔티티 처리
        if char in ['&lt;', '&gt;']:
            if char == '&lt;':
                char = '<'
            elif char == '&gt;':
                char = '>'
            print(char, end='')
            continue
            
        # 태그 시작
        if char == '<':
            in_tag = True
            continue
            
        # 태그 끝
        if char == '>':
            in_tag = False
            continue
            
        # 태그 외부의 텍스트만 출력
        if not in_tag:
            print(char, end='')


def load(url: URL) -> None:
    """URL을 로드하고 내용을 출력합니다.
    
    Args:
        url: 로드할 URL 객체
    """
    body = url.request()
    show(body)


def main() -> None:
    """메인 함수: 명령행 인자를 처리하고 브라우저를 실행합니다."""
    if len(sys.argv) > 1:
        # 첫 번째 인자를 URL로 사용
        url = URL(sys.argv[1])
        load(url)
    else:
        # 기본 파일 로드
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_file_path = os.path.join(script_dir, '..', 'default.html')
        default_url = f"file://{default_file_path}"
        print(f"기본 파일을 로드합니다: {default_url}")
        
        url = URL(default_url)
        load(url)


if __name__ == '__main__':
    main()


# 사용법:
# python3 browser.py http://browser.engineering/http.html
# python3 browser.py file:///path/to/file.html
# python3 browser.py  # 기본 파일 로드
