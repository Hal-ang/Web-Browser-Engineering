import socket
import ssl

class URL:
  def __init__(self, url):
    # 입력: "http://example.com/path" 또는 "file:///path/to/file"
    self.scheme, url = url.split('://', 1)
    # 출력: self.scheme = "http", url = "example.com/path"
    assert self.scheme in ['http', 'https', 'file']

    if self.scheme == 'file':
      # file:///path/to/file -> /path/to/file
      self.path = '/' + url
      self.host = None
      self.port = None
      return

    if '/' not in url:
      url = url + '/'
  # 입력: "example.com/path"
    self.host, url = url.split('/', 1)
    # 출력: self.host = "example.com", url = "path"
    self.path = '/' + url

    if (self.scheme == 'https'):
      self.port = 443
    else:
      self.port = 80
    # port 전달 시
    if ':' in self.host:
      self.host, self.port = self.host.split(':', 1)
      self.port = int(self.port)


  def request(self):
    if self.scheme == 'file':
      # 로컬 파일 읽기
      try:
        with open(self.path, 'r', encoding='utf-8') as f:
          return f.read()
      except FileNotFoundError:
        return f"Error: File not found - {self.path}"
      except PermissionError:
        return f"Error: Permission denied - {self.path}"
      except Exception as e:
        return f"Error: {str(e)}"
    
    # HTTP/HTTPS 처리
    # HTTP/1.1 지원
    # 소켓 생성
    s = socket.socket(
      family=socket.AF_INET,
      # 소켓 타입
      # 각 컴퓨터가 임의의 양의 데이터를 전송할 수 있는 타입
      type=socket.SOCK_STREAM,
      # 프로토콜 타입
      # 데이터 전송 방식
      proto=socket.IPPROTO_TCP,
    )

    if (self.scheme == 'https'):
      ctx = ssl.create_default_context()
      s = ctx.wrap_socket(s, server_hostname=self.host)

    # 소켓 연결 (다른 컴퓨터에 연결)
    s.connect((self.host, self.port))

    request = "GET {} HTTP/1.1\r\n".format(self.path)
    request += "HOST: {}\r\n".format(self.host)
    request += "CONNECTION: close\r\n"
    request += "USER-AGENT: harang/1.0\r\n"
    # 줄바꿈은 \r\n 으로 표시, \n은 줄바꿈 불가
    # 마지막에는 꼭 두 번 보내야 함, 서버는 줄바꿈을 기다림
    request += "\r\n"
    print(request)
    s.send(request.encode('utf-8'))


    # 이미 도착한 응답을 전달하는 socket.read를 사용함
    # 그러면 데이터가 도착할 때마다 수집하는 루프 작성 필요, 
    # makefile은 헬퍼 함수, 루프를 감추는 역할
    # 파이썬이 아닌 다른 언어는 read만 지원할 수 있음 / 이때는 소켓 상태를 확인하는 루프 작성 필요
    response = s.makefile('r', encoding='utf-8', newline='\r\n')

    print(response)
    statusline = response.readline()
    version, status, explanation = statusline.split(' ', 2)

    response_headers = {}

    while True:
      line = response.readline()
      if line == '\r\n': break

      # 콜론을 기준으로 분리, map 처리
      header, value = line.split(':', 1)
      # 시작과 끝에 공백 제거
      response_headers[header.casefold()] = value.strip()


      # 특히 중요한 헤더
      # 접근하려는 데이터가 특별한 형태로 전송되었는지 알려주는 헤더가 포함되어있는지 확인


      # 서버는 웹페이지 전송 전 Content-Encoding 헤더를 사용해 압축 진행
      # 텍스트가 많은 대형 웹페이지 압축 시 페이지 로드가 빨라질 수 있음
      # 브라우저는 자신이 지원하는 압축 알고리즘을 알려주기 위해 Accept-Encoding 헤더를 전송 해야 함
      # Transfer-Encoding 헤더도 비슷한 기능을 하지만, 압축 뿐 아니라 데이터를 쪼개서 전송함을 알려줌 (chunked)
      assert 'transfer-encoding' not in response_headers
      assert 'content-encoding' not in response_headers

      body = response.read()
      s.close()

      return body


def show(body):
  in_tag = False
  for c in body:
    if c == '<':
      in_tag = True
      continue
    if c == '>':
      in_tag = False
      continue
    if not in_tag:
      print(c, end='')
      

def load(url):
  body = url.request()
  show(body)


# CLI에서 스크립트를 실행했을 때만 실행되도록 하는 파이썬의 main 함수
if __name__ == '__main__':
  import sys
  import os
  
  if len(sys.argv) > 1:
    # 첫번째 인자를 읽어서 URL로 사용
    load(URL(sys.argv[1]))
  else:
    # URL 없이 시작하면 기본 로컬 파일 열기
    default_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'default.html')
    default_url = f"file://{default_file_path}"
    print(f"기본 파일을 로드합니다: {default_url}")
    load(URL(default_url))
  
# 명령
# python3 browser.py http://browser.engineering/http.html
# python3 browser.py file:///path/to/file.html
# python3 browser.py (기본 파일 로드)
