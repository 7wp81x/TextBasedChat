const WebSocket = require('ws');
const http = require('http');
const fs = require('fs');
const crypto = require('crypto');
const url = require('url');

const WS_PORT = 8081;
const HTTP_PORT = 8080;
const USERS_FILE = 'users.json';
let users = {};

if (fs.existsSync(USERS_FILE)) {
  users = JSON.parse(fs.readFileSync(USERS_FILE));
} else {
  fs.writeFileSync(USERS_FILE, '{}');
}

function hashPassword(password) {
  return crypto.createHash('sha256').update(password).digest('hex');
}

// Create HTTP server
const httpServer = http.createServer((req, res) => {
  const reqUrl = url.parse(req.url, true);
  
  // Handle specific robot endpoint
  if (reqUrl.pathname === '/getuptimerb') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', message: 'Uptime robot check' }));
    return;
  }
  
  // Reject all other requests
  res.writeHead(503, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Forbidden' }));
});

// Create WebSocket server
const wss = new WebSocket.Server({ port: WS_PORT });

function broadcastSystemMessage(message) {
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify({
        type: 'system',
        data: message
      }));
    }
  });
}

wss.on('connection', (ws, req) => {
  ws.on('message', (message) => {
    try {
      const { action, data } = JSON.parse(message);
      
      if (action === 'register') {
        const { username, nickname, password } = data;
        if (users[username]) {
          ws.send(JSON.stringify({ error: 'Username exists' }));
          return;
        }
        
        users[username] = {
          nickname,
          password: hashPassword(password),
          online: true
        };
        
        fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
        ws.send(JSON.stringify({ success: true }));
      }
      else if (action === 'login') {
        const { username, password } = data;
        const user = users[username];
        
        if (!user || user.password !== hashPassword(password)) {
          ws.send(JSON.stringify({ error: 'Invalid credentials' }));
          ws.close();
          return;
        }
        
        user.online = true;
        ws.user = { username, nickname: user.nickname };
        ws.send(JSON.stringify({ 
          success: true, 
          nickname: user.nickname 
        }));
        
        broadcastSystemMessage(`${user.nickname}|connected`);
      }
      else if (action === 'message') {
        if (!ws.user) return;
        const msg = `${ws.user.nickname}|${data.text}`;
        
        wss.clients.forEach(client => {
          if (client !== ws && client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify({ 
              type: 'message',
              data: msg 
            }));
          }
        });
      }
      else if (action === 'get_online_users') {
          const onlineUsers = Object.values(users)
              .filter(user => user.online)
              .map(user => user.nickname);
          
          ws.send(JSON.stringify({
              type: 'online_users',
              data: onlineUsers
          }));
      }
    } catch (e) {
      console.error('Message error:', e);
    }
  });

  ws.on('close', () => {
    if (ws.user && users[ws.user.username]) {
      users[ws.user.username].online = false;
      const user = users[ws.user.username];
      broadcastSystemMessage(`${user.nickname}|disconnected`);
    }
  });
});

// Start both servers
httpServer.listen(HTTP_PORT, () => {
  console.log(`HTTP server running on http://localhost:${HTTP_PORT}`);
});

console.log(`WebSocket server running on ws://localhost:${WS_PORT}`);