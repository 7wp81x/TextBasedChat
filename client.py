import asyncio
import websockets
import json
import hashlib
import os
import time
from aioconsole import ainput
from getpass import getpass

LOGIN_FILE = 'login.json'

# Colorful logging functions
LOG_SUCCESS = lambda message, nl="": print(f"{nl}\033[1;92m[+] \033[0m{message}")
LOG_INFO = lambda message, nl="": print(f"{nl}\033[1;94m[*] \033[0m{message}")
LOG_ERROR = lambda message, nl="": print(f"{nl}\033[1;91m[!] \033[0m{message}")
LOG_SPECIAL = lambda message, nl="": print(f"{nl}\033[1;96m[+] \033[0m{message}")

async def authenticate(ws):
    if os.path.exists(LOGIN_FILE):
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
    else:
        LOG_SUCCESS("Register New Account")
        while True:
            username = input("\033[1;92m[+] Username: \033[0m").strip()
            nickname = input("\033[1;92m[?] Nickname: \033[0m").strip()
            password = getpass("\033[1;92m[?] Password: \033[0m")
            confirm = getpass("\033[1;92m[?] Confirm Password: \033[0m")
            
            if password != confirm:
                LOG_ERROR("Passwords don't match!")
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
                LOG_ERROR(response['error'])
                continue
                
            with open(LOGIN_FILE, 'w') as f:
                json.dump({
                    'username': username,
                    'password': password
                }, f)
            return await authenticate(ws)

async def chat_client():
    async with websockets.connect('ws://localhost:8090') as ws:
        auth = json.loads(await authenticate(ws))
        if not auth.get('success'):
            LOG_ERROR("Authentication failed")
            return
            
        nickname = auth['nickname']
        LOG_SUCCESS(f"Logged in as {nickname}")
        print()
        
        async def receiver():
            while True:
                try:

                    msg = json.loads(await ws.recv())
                
                    if msg['type'] == 'message':
                        rcv_nickname, rcv_message = msg['data'].split("|", 1)
                        print(f"\r\033[0;97m<\033[0;96m{rcv_nickname.strip()}\033[0;97m> \033[0;92m{rcv_message.strip()}\n\033[0mmessage:#\033[0;93m ", end="", flush=True)
                    
                    elif msg['type'] == 'system':
                            sys_nick, sys_action = msg['data'].split("|", 1)
                            
                            if sys_action.strip() == "connected":
                                print(f"\r\033[1;93m[SYSTEM] \033[0;92m{sys_nick}\033[0m => \033[1;92mhas joined the chat\033[0m\n\033[0mmessage:#\033[0;93m ", end="", flush=True)
                            elif sys_action.strip() == "disconnected":
                                print(f"\r\033[1;91m[SYSTEM] \033[0;92m{sys_nick}\033[0m => \033[1;91mhas left the chat\033[0m\n\033[0mmessage:#\033[0;93m ", end="", flush=True)
                            else:
                                # Fallback for unexpected system messages
                                print(f"\r\033[1;93m[SYSTEM] \033[0;92m{msg['data']}\033[0m\n\033[0mmessage:#\033[0;93m ", end="", flush=True)
                except websockets.exceptions.ConnectionClosed:
                    LOG_ERROR("Connection to server lost")
                    return
                except Exception as e:
                    LOG_ERROR(f"Error: {str(e)}")
                    return
        
        receiver_task = asyncio.create_task(receiver())
        
        try:
            while True:
                try:
                    text = await ainput("\033[0mmessage:#\033[0;93m ")
                    if text.lower() == '/quit':
                        break
                    await ws.send(json.dumps({
                        'action': 'message',
                        'data': {'text': text}
                    }))
                except KeyboardInterrupt:
                    LOG_INFO("Disconnecting...")
                    break
        finally:
            receiver_task.cancel()
            try:
                await ws.close()
            except:
                pass
            LOG_INFO("Disconnected from chat server")

asyncio.get_event_loop().run_until_complete(chat_client())