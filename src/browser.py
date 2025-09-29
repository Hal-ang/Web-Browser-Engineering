import socket

class URL:
  def __init__(self, url):
    # 입력: "http://example.com/path"
    self.scheme, url = url.split('://', 1)
    # 출력: self.scheme = "http", url = "example.com/path"
    assert self.scheme == 'http'


    if '/' not in url:
      url = url + '/'

    # 입력: "example.com/path"
    self.host, url = url.split('/', 1)
    # 출력: self.host = "example.com", url = "path"
    self.path = '/' + url

  def request(self):
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

    # 소켓 연결 (다른 컴퓨터에 연결)
    s.connect((self.host, 80))

    request = "GET {} HTTP/1.0\r\n".format(self.path)
    request += "HOT: {}\r\n".format(self.host)
    # 줄바꿈은 \r\n 으로 표시, \n은 줄바꿈 불가
    # 마지막에는 꼭 두 번 보내야 함, 서버는 줄바꿈을 기다림
    request += "\r\n"
    s.send(request.encode('utf-8'))


    # 이미 도착한 응답을 전달하는 socket.read를 사용함
    # 그러면 데이터가 도착할 때마다 수집하는 루프 작성 필요, 
    # makefile은 헬퍼 함수, 루프를 감추는 역할
    # 파이썬이 아닌 다른 언어는 read만 지원할 수 있음 / 이때는 소켓 상태를 확인하는 루프 작성 필요
    response = s.makefile('r', encoding='utf-8', newline='\r\n')

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
  # 첫번째 인자를 읽어서 URL로 사용
  import sys
  load(URL(sys.argv[1]))
  
# 명령
# python3 browser.py http://browser.engineering/http.html
