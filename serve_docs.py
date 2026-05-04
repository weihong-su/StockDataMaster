"""本地文档服务器 - 在浏览器中访问 StockDataMaster 文档"""
import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8080
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 屏蔽每次请求的日志输出


def main():
    os.chdir(DOCS_DIR)
    url = f"http://localhost:{PORT}"
    print(f"文档服务已启动: {url}")
    print("按 Ctrl+C 停止服务")

    webbrowser.open(url)

    with socketserver.TCPServer(("", PORT), SilentHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")


if __name__ == "__main__":
    main()
