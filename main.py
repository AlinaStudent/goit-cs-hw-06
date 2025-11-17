
import json
import os
import socket
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from urllib.parse import parse_qs

from pymongo import MongoClient


# ---------------- Налаштування ----------------
HTTP_PORT = int(os.environ.get("HTTP_PORT", "3000"))
SOCKET_PORT = int(os.environ.get("SOCKET_PORT", "5000"))
SOCKET_HOST = os.environ.get("SOCKET_HOST", "0.0.0.0")
MONGO_HOST = os.environ.get("MONGO_HOST", "mongo")
MONGO_PORT = int(os.environ.get("MONGO_PORT", "27017"))
MONGO_DB = os.environ.get("MONGO_DB", "messages_db")
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION", "messages")


# ---------------- Сервер сокетів ----------------
def socket_server_udp():
    """
    UDP-сервер. Отримує JSON-байти виду {"username": "...", "message": "..."}
    та зберігає їх у MongoDB з доданим полем 'date' (поточний час).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SOCKET_HOST, SOCKET_PORT))
    print(f"[socket] UDP сервер запущено на {SOCKET_HOST}:{SOCKET_PORT}")

    # Підключення до MongoDB
    client = MongoClient(host=MONGO_HOST, port=MONGO_PORT)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]

    while True:
        data, addr = sock.recvfrom(65535)
        try:
            payload = json.loads(data.decode('utf-8'))
            користувач = str(payload.get("username", "")).strip()
            повідомлення = str(payload.get("message", "")).strip()

            документ = {
                "date": str(datetime.now()),
                "username": користувач,
                "message": повідомлення,
            }
            collection.insert_one(документ)
            print(f"[socket] Отримано повідомлення від {addr}: {документ}")
        except Exception as e:
            print(f"[socket] Помилка обробки пакету від {addr}: {e}")


# ---------------- HTTP сервер ----------------
class ПростийОбробник(BaseHTTPRequestHandler):
    """Обробник HTTP-запитів без використання фреймворків."""

    def _відправити_файл(self, ім_файлу: str, тип_вмісту: str):
        try:
            with open(ім_файлу, "rb") as f:
                дані = f.read()
            self.send_response(200)
            self.send_header("Content-Type", тип_вмісту)
            self.send_header("Content-Length", str(len(дані)))
            self.end_headers()
            self.wfile.write(дані)
        except FileNotFoundError:
            self._помилка_404()

    def _помилка_404(self):
        try:
            with open("error.html", "rb") as f:
                дані = f.read()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(дані)))
            self.end_headers()
            self.wfile.write(дані)
        except FileNotFoundError:
            self.send_error(404, "Не знайдено")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._відправити_файл("index.html", "text/html; charset=utf-8")
            return
        if self.path in ("/message.html", "/message"):
            self._відправити_файл("message.html", "text/html; charset=utf-8")
            return
        if self.path == "/style.css":
            self._відправити_файл("style.css", "text/css; charset=utf-8")
            return
        if self.path == "/logo.png":
            self._відправити_файл("logo.png", "image/png")
            return

        # Якщо нічого не підійшло — 404
        self._помилка_404()

    def do_POST(self):
        if self.path == "/message":
            довжина = int(self.headers.get("Content-Length", "0"))
            тіло = self.rfile.read(довжина).decode("utf-8")
            форма = parse_qs(тіло)
            користувач = форма.get("username", [""])[0]
            повідомлення = форма.get("message", [""])[0]

            # Відправлення на UDP-сервер
            дані = json.dumps({"username": користувач, "message": повідомлення}).encode("utf-8")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(дані, ("127.0.0.1", SOCKET_PORT))
            sock.close()

            # Повертаємо користувача назад до форми
            self.send_response(302)
            self.send_header("Location", "/message.html")
            self.end_headers()
        else:
            self._помилка_404()


def http_сервер():
    сервер = HTTPServer(("0.0.0.0", HTTP_PORT), ПростийОбробник)
    print(f"[http] Сервер запущено на 0.0.0.0:{HTTP_PORT}")
    try:
        сервер.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        сервер.server_close()


# ---------------- Точка входу ----------------
if __name__ == "__main__":
    # Запускаємо UDP-сервер у окремому процесі
    процес = Process(target=socket_server_udp, daemon=True)
    процес.start()

    # Основний процес — HTTP-сервер
    http_сервер()
