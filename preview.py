"""Local-only visual preview with disposable data, never a production auth bypass."""
import hashlib
import hmac
import json
import os
import tempfile
import time
import urllib.parse
from datetime import timedelta
from pathlib import Path
from http.server import ThreadingHTTPServer

def main():
    with tempfile.TemporaryDirectory(prefix="cats-ui-preview-") as scratch:
        os.environ.update(DATA_DIR=scratch, BOT_TOKEN="123456:local-preview-only", ALLOWED_USER_IDS="999")
        import config
        import database
        from web_server import CatAppHandler
        database.init_db()
        now = config.get_current_time()
        database.record_pair_feeding(999, "Матвей", now - timedelta(hours=1))
        database.add_feeding(999, "Сестра", now - timedelta(hours=10))
        database.complete_quest(f"water_{now:%Y-%m-%d}", 999, "Матвей")
        values = {"auth_date": str(int(time.time())), "user": json.dumps({"id":999,"first_name":"Локальное демо"})}
        secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
        values["hash"] = hmac.new(secret, "\n".join(f"{k}={v}" for k,v in sorted(values.items())).encode(), hashlib.sha256).hexdigest()
        init_data = urllib.parse.urlencode(values)
        mock = '<script>window.Telegram={WebApp:{initData:' + json.dumps(init_data) + ',initDataUnsafe:{user:{id:999,first_name:"Демо"}},ready(){},expand(){}}};</script>'

        class PreviewHandler(CatAppHandler):
            def do_GET(self):
                if urllib.parse.urlparse(self.path).path == "/":
                    html = (Path(__file__).parent / "web/index.html").read_text(encoding="utf-8")
                    html = html.replace('<script src="https://telegram.org/js/telegram-web-app.js"></script>', mock)
                    payload = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                super().do_GET()
        server = ThreadingHTTPServer(("127.0.0.1", 8190), PreviewHandler)
        try:
            print("Disposable preview: http://127.0.0.1:8190", flush=True)
            server.serve_forever()
        finally:
            server.server_close()

if __name__ == "__main__":
    main()
