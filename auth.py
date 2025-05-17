import os
import sys
import json
import termios
import hashlib
import curses

LOGIN_FILE = 'login.json'

def _curses_input(stdscr, y, x, prompt, hidden=False):
    stdscr.addstr(y, x, prompt)
    stdscr.refresh()
    input_str = []
    while True:
        ch = stdscr.getch()
        if ch == curses.KEY_ENTER or ch == 10 or ch == 13:  # Enter key
            break
        elif ch == curses.KEY_BACKSPACE or ch == 127:  # Backspace
            if len(input_str) > 0:
                input_str.pop()
                stdscr.addch(y, x + len(prompt) + len(input_str), ' ')
                stdscr.move(y, x + len(prompt) + len(input_str))
        elif ch >= 32 and ch <= 126:  # Printable characters
            input_str.append(chr(ch))
            if hidden:
                stdscr.addch(y, x + len(prompt) + len(input_str) - 1, '*')
            else:
                stdscr.addch(y, x + len(prompt) + len(input_str) - 1, chr(ch))
        stdscr.refresh()
    return ''.join(input_str)

async def authenticate(ws, stdscr):
    stdscr.clear()
    stdscr.refresh()
    
    height, width = stdscr.getmaxyx()
    auth_win = curses.newwin(height, width, 0, 0)
    auth_win.keypad(True)
    
    if os.path.exists(LOGIN_FILE):
        try:
            with open(LOGIN_FILE) as f:
                creds = json.load(f)
            await ws.send(json.dumps({
                'action': 'login',
                'data': {
                    'username': creds['username'],
                    'password': hashlib.sha256(creds['password'].encode()).hexdigest()
                }
            }))
            return await ws.recv()
        except (json.JSONDecodeError, KeyError):
            os.remove(LOGIN_FILE)
            return await authenticate(ws, stdscr)
    else:
        while True:
            auth_win.clear()
            auth_win.addstr(1, 1, "[*] login.json not found, please create account.")
            
            auth_win.addstr(3, 1, "[?] Username: ")
            username = _curses_input(auth_win, 3, 15, "", False)
            
            auth_win.addstr(4, 1, "[?] Nickname: ")
            nickname = _curses_input(auth_win, 4, 15, "", False)
            
            auth_win.addstr(5, 1, "[?] Password: ")
            password = _curses_input(auth_win, 5, 15, "", True)
            
            auth_win.addstr(6, 1, "[?] Confirm : ")
            confirm = _curses_input(auth_win, 6, 15, "", True)
            
            if password != confirm:
                auth_win.addstr(8, 1, "[!] Passwords don't match. Please try again.", curses.A_BOLD)
                auth_win.refresh()
                auth_win.getch()
                continue

            await ws.send(json.dumps({
                'action': 'register',
                'data': {
                    'username': username,
                    'nickname': nickname,
                    'password': hashlib.sha256(password.encode()).hexdigest()
                }
            }))

            response = json.loads(await ws.recv())
            if response.get('error'):
                auth_win.addstr(8, 1, f"Error: {response['error']}", curses.A_BOLD)
                auth_win.refresh()
                auth_win.getch()
                continue

            with open(LOGIN_FILE, 'w') as f:
                json.dump({'username': username, 'password': password}, f)
            break

        return await authenticate(ws, stdscr)
