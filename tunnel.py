import asyncio
import threading
import time
import socket
import ssl
import logging
import aiohttp
from aiohttp import web
import telebot

logger = logging.getLogger("tg_tunnel")

WORKER_DOMAINS = [
    "zapretcore.altuhovd203.workers.dev",
    "zapretcore.bustzvania18.workers.dev",
    "zapretcore.macsim-rongerberg.workers.dev",
    "rknxyesos.dima-volko123.workers.dev",
]

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

class TelegramTunnel:
    def __init__(self):
        self.raw_tunnel_port = find_free_port()
        self.http_bridge_port = find_free_port()
        self.active_worker = WORKER_DOMAINS[0]
        self.loop = None
        self.thread = None
        self.is_ready = threading.Event()

    async def _ws_tunnel_handler(self, reader, writer):
        """Проксирует «сырые» TLS-байты между локальным сокетом и WebSocket Cloudflare Worker'а"""
        ws_url = f"wss://{self.active_worker}/apiws?dst=api.telegram.org"
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.ws_connect(ws_url, heartbeat=25) as ws:
                    async def s2w():
                        try:
                            while True:
                                data = await reader.read(65536)
                                if not data:
                                    await ws.close()
                                    break
                                await ws.send_bytes(data)
                        except Exception:
                            pass

                    async def w2s():
                        try:
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.BINARY:
                                    writer.write(msg.data)
                                    await writer.drain()
                                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                    break
                        except Exception:
                            pass
                        finally:
                            try:
                                writer.close()
                            except Exception:
                                pass

                    await asyncio.gather(s2w(), w2s())
        except Exception as e:
            logger.debug(f"Tunnel connection error: {e}")
            try:
                writer.close()
            except Exception:
                pass

    async def _http_proxy_handler(self, request):
        """Принимает локальный HTTP-запрос от telebot и перенаправляет в HTTPS-туннель"""
        path = request.match_info.get('tail', '')
        url = f"https://127.0.0.1:{self.raw_tunnel_port}/{path}"
        if request.query_string:
            url += f"?{request.query_string}"

        body = await request.read()
        headers = dict(request.headers)
        headers['Host'] = 'api.telegram.org'
        headers.pop('Content-Length', None)

        ctx = ssl.create_default_context()
        conn = aiohttp.TCPConnector(ssl=ctx)
        
        # Для long-polling Telegram API таймаут должен быть достаточным
        timeout = aiohttp.ClientTimeout(total=None, connect=20, sock_read=120)
        
        try:
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.request(
                    request.method,
                    url,
                    headers=headers,
                    data=body if body else None,
                    server_hostname='api.telegram.org',
                    timeout=timeout
                ) as resp:
                    resp_body = await resp.read()
                    return web.Response(
                        body=resp_body,
                        status=resp.status,
                        content_type=resp.content_type
                    )
        except Exception as e:
            logger.error(f"Proxy request error: {e}")
            return web.Response(status=502, text=f"Bad Gateway: {e}")

    def _run_event_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def start():
            await asyncio.start_server(self._ws_tunnel_handler, '127.0.0.1', self.raw_tunnel_port)
            app = web.Application()
            app.router.add_route('*', '/{tail:.*}', self._http_proxy_handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '127.0.0.1', self.http_bridge_port)
            await site.start()
            self.is_ready.set()

        self.loop.run_until_complete(start())
        self.loop.run_forever()

    def start(self):
        """Запускает фоновый туннель в отдельном потоке"""
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        self.is_ready.wait(timeout=10)

def setup_telegram_proxy():
    """Проверяет прямое подключение к Telegram, и если не доступно — поднимает прозрачный туннель"""
    # Пробуем проверить прямое подключение
    try:
        import requests
        r = requests.get("https://api.telegram.org", timeout=3)
        if r.status_code in (200, 302, 404):
            print("INFO: Прямое подключение к Telegram API доступно.")
            return None
    except Exception:
        pass

    print("INFO: Запуск автономного туннеля для Telegram API...")
    tunnel = TelegramTunnel()
    tunnel.start()

    bridge_url = f"http://127.0.0.1:{tunnel.http_bridge_port}"
    telebot.apihelper.API_URL = f"{bridge_url}/bot{{0}}/{{1}}"
    telebot.apihelper.FILE_URL = f"{bridge_url}/file/bot{{0}}/{{1}}"
    print(f"SUCCESS: Туннель активен на {bridge_url}")
    return tunnel
