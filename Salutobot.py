import socket
import threading
import time
import queue

# Carica configurazione
try:
    from config import *
except ImportError:
    from config_example import *
    print("[WARN] Stai usando la configurazione di esempio! Crea un file config.py con i tuoi dati.")

class IRCBot:
    def __init__(self, server, port, nickname, realname, channels, pm_template):
        self.server = server
        self.port = port
        self.nickname = nickname
        self.realname = realname
        self.channels = channels
        self.pm_template = pm_template
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = True
        self.msg_queue = queue.Queue()
        self.contattati = set()

    def connect(self):
        print(f"[INFO] Connessione a {self.server}:{self.port}...")
        self.sock.connect((self.server, self.port))
        self.send_raw(f"NICK {self.nickname}")
        self.send_raw(f"USER {self.nickname} 0 * :{self.realname}")
        threading.Thread(target=self.listen, daemon=True).start()
        threading.Thread(target=self.process_queue, daemon=True).start()

    def send_raw(self, msg):
        print(f"[SEND] {msg}")
        self.sock.send((msg + "\r\n").encode())

    def join_channels(self):
        for channel in self.channels:
            self.send_raw(f"JOIN {channel}")
            time.sleep(1)

    def send_private_message(self, user, message):
        self.msg_queue.put(f"PRIVMSG {user} :{message}")

    def process_queue(self):
        while self.running:
            if not self.msg_queue.empty():
                msg = self.msg_queue.get()
                self.send_raw(msg)
                time.sleep(MESSAGE_INTERVAL)
            else:
                time.sleep(0.5)

    def listen(self):
        buffer = ""
        while self.running:
            try:
                data = self.sock.recv(2048).decode("utf-8", errors="ignore")
                if not data:
                    break
                buffer += data
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    self.handle_line(line)
            except Exception as e:
                print(f"[ERROR] {e}")
                break

    def handle_line(self, line):
        print(f"[RECV] {line}")
        if line.startswith("PING"):
            self.send_raw(f"PONG {line.split()[1]}")
        elif " 001 " in line:
            # Autenticazione NickServ
            if USE_NICKSERV_AUTH and NICKSERV_PASSWORD:
                self.send_raw(f"PRIVMSG NickServ :IDENTIFY {NICKSERV_PASSWORD}")
                time.sleep(2)
            self.join_channels()
        elif "JOIN" in line and self.nickname in line:
            channel = line.split("JOIN")[1].split(":")[-1].strip()
            self.send_raw(f"NAMES {channel}")
        elif " 353 " in line:
            parts = line.split(":", 2)
            if len(parts) >= 3:
                user_list = parts[2].strip().split()
                for user in user_list:
                    user = user.lstrip("@+")
                    if user != self.nickname and user not in self.contattati:
                        self.contattati.add(user)
                        msg = self.pm_template.format(user=user)
                        self.send_private_message(user, msg)

    def stop(self):
        self.running = False
        self.sock.close()

if __name__ == "__main__":
    bot = IRCBot(SERVER, PORT, NICKNAME, REALNAME, CHANNELS, PM_MESSAGE_TEMPLATE)
    try:
        bot.connect()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Disconnessione...")
        bot.stop()
