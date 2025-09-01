import asyncio
import curses
import json
import hashlib
import os
import time
from getpass import getpass
import websockets
from collections import deque
import termios
import sys
from auth import authenticate
LOGIN_FILE = 'login.json'
MESSAGE_HISTORY_SIZE = 1000
REFRESH_RATE = 0.01  

COLOR_NORMAL = 10
COLOR_SYSTEM = 11
COLOR_TIMESTAMP = 12
COLOR_NICKNAME = 27
COLOR_MESSAGE = 14
COLOR_INPUT = 13
COLOR_BORDER = 16
COLOR_ERROR = 17
COLOR_WARNING = 18
COLOR_HIGHLIGHT = 19


COLOR_NICK_BASE = 20
MAX_NICK_COLORS = 6 

def log_timestamp():
    return time.strftime("[%H:%M:%S]", time.localtime())

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    
    if curses.can_change_color():
        try:
            curses.init_color(100, 800, 800, 800)  # Bright white
            curses.init_color(101, 1000, 500, 0)   # Orange
            curses.init_color(102, 200, 800, 200)   # Pastel green
        except:
            pass
    
    curses.init_pair(COLOR_NORMAL, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_SYSTEM, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_TIMESTAMP, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_MESSAGE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_INPUT, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BORDER, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_ERROR, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_WARNING, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_HIGHLIGHT, curses.COLOR_MAGENTA, -1)
    
    curses.init_pair(COLOR_NICK_BASE + 0, curses.COLOR_GREEN, -1)       # Green
    curses.init_pair(COLOR_NICK_BASE + 1, curses.COLOR_MAGENTA, -1)    # Magenta
    curses.init_pair(COLOR_NICK_BASE + 2, curses.COLOR_RED, -1)        # Red
    curses.init_pair(COLOR_NICK_BASE + 3, curses.COLOR_BLUE, -1)       # Blue
    curses.init_pair(COLOR_NICK_BASE + 4, curses.COLOR_YELLOW, -1)     # Yellow
    curses.init_pair(COLOR_NICK_BASE + 5, curses.COLOR_CYAN, -1)       # Cyan
    curses.init_pair(COLOR_NICK_BASE + 6, 101, -1)                     # Orange (custom if available)
    curses.init_pair(COLOR_NICK_BASE + 7, 102, -1)                     # Pastel green (custom if available)

def get_nick_color(nick):
    nick_hash = hash(nick)
    return COLOR_NICK_BASE + (abs(nick_hash) % MAX_NICK_COLORS)

def wrap_text(text, width):
    if not text:
        return []
    
    lines = []
    current_line = []
    current_length = 0
    
    for word in text.split(' '):
        word_length = len(word)
        if current_length + word_length + len(current_line) > width:
            lines.append(' '.join(current_line))
            current_line = [word]
            current_length = word_length
        else:
            current_line.append(word)
            current_length += word_length
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

async def curses_main(stdscr):
    init_colors()
    
    curses.curs_set(0)
    curses.halfdelay(1) 
    stdscr.nodelay(True)
    
    height, width = stdscr.getmaxyx()
    msg_win = curses.newwin(height - 3, width, 0, 0)
    input_win = curses.newwin(3, width, height - 3, 0)
    input_win.keypad(True)

    scroll_pos = 0
    max_scroll = 0
    last_display_update = 0

    uri = 'wss://YOUR_SERVER_HERE.com'
    async with websockets.connect(uri, ping_interval=None) as ws:
        auth_response = await authenticate(ws, stdscr)
        auth = json.loads(auth_response)
        if not auth.get('success'):
            input_win.addstr(1, 1, "Authentication failed. Press any key to exit.", curses.color_pair(COLOR_SYSTEM))
            input_win.getch()
            return



        timestamp = log_timestamp()

        nickname = auth['nickname']
        messages = deque(maxlen=MESSAGE_HISTORY_SIZE)
        wrapped_messages = []
        message_updated = False

        welcome_msg = (f" [+] Welcome to the chat, {nickname}!", COLOR_TIMESTAMP)
        help_msg = (f" /online - show online users",COLOR_TIMESTAMP)
        help_msg1 = (" /quit - exit", COLOR_TIMESTAMP)
        
        bn1 = ("  _____              ___ _         _   ",COLOR_HIGHLIGHT)
        bn2 = (" |_   _|__ _ _ _ __ / __| |_  __ _| |_ ",COLOR_HIGHLIGHT)
        bn3 = ("   | |/ -_) '_| '  \\ (__| ' \\/ _` |  _|",COLOR_HIGHLIGHT)
        bn4 = ("   |_|\\___|_| |_|_|_\\___|_||_\\__,_|\\__| v1.0",COLOR_HIGHLIGHT)
        

        messages.extend([bn1,bn2,bn3,bn4," ",welcome_msg," ", help_msg,help_msg1, "-----------------------------------------------"])

        await ws.send(json.dumps({
            'action': 'get_online_users'
        }))
        async def receiver():
            nonlocal messages, wrapped_messages, message_updated, max_scroll
            while True:
                try:
                    msg = json.loads(await ws.recv())

                    if msg['type'] == 'message':
                        nick, content = msg['data'].split("|", 1)
                        nick_color = get_nick_color(nick.strip())
                        full_msg = (f"{timestamp} <{nick.strip()}> {content.strip()}", 
                                   (COLOR_TIMESTAMP, nick_color, COLOR_MESSAGE))
                        messages.append(full_msg)
                        wrapped_messages.extend(wrap_text(full_msg[0], width - 1))


                    elif msg['type'] == 'online_users':
                        users_list = ", ".join(msg['data'])
                        full_msg = (f"{timestamp} Online users: {users_list}", COLOR_SYSTEM)
                        messages.append(full_msg)
                        wrapped_messages.extend(wrap_text(full_msg[0], width - 1))
                        message_updated = True


                    elif msg['type'] == 'system':
                        nick, action = msg['data'].split("|", 1)
                        if action.strip() == 'connected':
                            full_msg = (f"{timestamp} *** {nick.strip()} joined the chat ***", 
                                       COLOR_NICKNAME)
                        elif action.strip() == 'disconnected':
                            full_msg = (f"{timestamp} *** {nick.strip()} left the chat ***", 
                                       COLOR_ERROR)
                        else:
                            full_msg = (f"{timestamp} SYSTEM: {msg['data']}", 
                                       COLOR_SYSTEM)
                        messages.append(full_msg)
                        wrapped_messages.extend(wrap_text(full_msg[0], width - 1))
                    
                    message_updated = True
                    max_scroll = max(0, len(wrapped_messages) - (height - 4))

                except websockets.exceptions.ConnectionClosed:
                    full_msg = (f"{log_timestamp()} *** Connection to server lost ***", 
                               COLOR_ERROR)
                    messages.append(full_msg)
                    wrapped_messages.extend(wrap_text(full_msg[0], width - 1))
                    message_updated = True
                    break
                except Exception as e:
                    full_msg = (f"{log_timestamp()} Error: {str(e)}", 
                               COLOR_SYSTEM)
                    messages.append(full_msg)
                    wrapped_messages.extend(wrap_text(full_msg[0], width - 1))
                    message_updated = True
                    break

        def update_display():
            nonlocal scroll_pos, message_updated, last_display_update
            current_time = time.time()

            if not message_updated and current_time - last_display_update < REFRESH_RATE:
                return

            msg_win.clear()

            all_wrapped = []
            for msg in messages:
                if isinstance(msg, tuple):
                    text, colors = msg
                else:
                    text, colors = msg, COLOR_NORMAL
                
                wrapped = wrap_text(text, width - 2)
                for line in wrapped:
                    all_wrapped.append((line, colors))

            visible_height = height - 4
            max_scroll = max(0, len(all_wrapped) - visible_height)
            scroll_pos = min(scroll_pos, max_scroll)

            start_idx = max(0, len(all_wrapped) - visible_height - scroll_pos)
            end_idx = start_idx + visible_height

            for i, (line, colors) in enumerate(all_wrapped[start_idx:end_idx]):
                try:
                    if isinstance(colors, tuple):
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            msg_win.addstr(i, 0, parts[0], curses.color_pair(colors[0]))
                            msg_win.addstr(" ")
                            
                            msg_win.addstr(parts[1], curses.color_pair(colors[1]))
                            msg_win.addstr(" ")

                            msg_win.addstr(parts[2], curses.color_pair(colors[2]))
                        else:
                            msg_win.addstr(i, 0, line, curses.color_pair(COLOR_NORMAL))
                    else:
                        msg_win.addstr(i, 0, line, curses.color_pair(colors))
                except curses.error:
                    pass

            msg_win.refresh()
            message_updated = False
            last_display_update = current_time

        receiver_task = asyncio.create_task(receiver())

        try:
            buffer = ""
            while True:
                current_time = time.time()
                
                new_height, new_width = stdscr.getmaxyx()
                if new_height != height or new_width != width:
                    height, width = new_height, new_width
                    msg_win.resize(height - 3, width)
                    input_win.mvwin(height - 3, 0)
                    input_win.resize(3, width)
                    stdscr.clear()
                    stdscr.refresh()
                    
                    wrapped_messages = []
                    for msg in messages:
                        wrapped_messages.extend(wrap_text(msg[0], width - 1))
                    
                    max_scroll = max(0, len(wrapped_messages) - (height - 4))
                    scroll_pos = min(scroll_pos, max_scroll)
                    message_updated = True

                update_display()

                input_win.clear()
                input_win.border()
                input_win.attron(curses.color_pair(COLOR_BORDER))
                input_win.box()
                input_win.attroff(curses.color_pair(COLOR_BORDER))
                
                visible_width = width - len(nickname) - 4
                visible_buffer = buffer[-visible_width:]
                input_win.addstr(1, 2, f"{nickname}: ", curses.color_pair(COLOR_NICKNAME))
                input_win.addstr(visible_buffer, curses.color_pair(COLOR_INPUT))

                input_win.refresh()

                try:
                    ch = input_win.getch()
                    if ch != -1:  
                        if ch in [10, 13]:  # Enter key
                            if buffer.strip():
                                if buffer.strip().lower() == "/quit":
                                    break
                                elif buffer.strip().lower() == "/online":
                                    await ws.send(json.dumps({
                                        'action': 'get_online_users'
                                    }))
                                    buffer = ""
                                    continue


                                try:
                                    timestamp = log_timestamp()
                                    full_msg = (f"{timestamp} <{nickname}>  {buffer.strip()}", 
                                              (COLOR_TIMESTAMP, COLOR_NICKNAME, COLOR_MESSAGE))
                                    messages.append(full_msg)
                                    wrapped_messages.extend(wrap_text(full_msg[0], width - 1))
                                    message_updated = True
                                    
                                    await ws.send(json.dumps({
                                        'action': 'message',
                                        'data': {'text': buffer}
                                    }))
                                except websockets.exceptions.ConnectionClosed:
                                    break
                            buffer = ""
                        elif ch in [127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                            buffer = buffer[:-1] if buffer else ""
                        elif 32 <= ch <= 126:
                            buffer += chr(ch)
                        elif ch == curses.KEY_UP and scroll_pos > 0:
                            scroll_pos += 1
                            message_updated = True
                        elif ch == curses.KEY_DOWN and scroll_pos < max_scroll:
                            scroll_pos -= 1
                            message_updated = True

                        elif ch == curses.KEY_PPAGE:
                            scroll_pos = min(scroll_pos + (height - 4), max_scroll)
                            message_updated = True
                        elif ch == curses.KEY_NPAGE:
                            scroll_pos = max(scroll_pos - (height - 4), 0)
                            message_updated = True
                        elif ch == curses.KEY_HOME: 
                            scroll_pos = max_scroll
                            message_updated = True
                        elif ch == curses.KEY_END: 
                            scroll_pos = 0
                            message_updated = True

                except curses.error:
                    pass

                await asyncio.sleep(0.01)
        finally:
            receiver_task.cancel()
            try:
                await ws.close()
            except:
                pass

def restore_terminal():
    fd = sys.stdin.fileno()
    if os.isatty(fd):
        attrs = termios.tcgetattr(fd)
        attrs[3] |= termios.ECHO | termios.ICANON 
        termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
        print("\033[?25h", end="", flush=True)  

def main():
    try:
        asyncio.run(curses.wrapper(curses_main))
    except KeyboardInterrupt:
        print("\n\n\nExiting chat client...\n\n")
        os.system("stty sane")
    finally:
        restore_terminal()

if __name__ == '__main__':
    main()
