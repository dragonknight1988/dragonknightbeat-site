#!/usr/bin/env node
/**
 * 疯狂的龙骑士 - 内容推送API
 * 
 * 部署在ECS上，龙骑士随时可以通过POST接口更新内容
 * 
 * 接口：
 *   POST /api/dragon-knight/push  — 推送新内容
 *   GET  /api/dragon-knight/posts — 获取所有内容
 *   DELETE /api/dragon-knight/:id — 删除指定内容
 * 
 * 启动：node dragon-knight-api.js
 * 端口：3456（可配置）
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.DK_PORT || 3456;
const DATA_FILE = process.env.DK_DATA_FILE || '/var/www/dragonknightbeat.com/dragon-knight-posts.json';
const AUTH_TOKEN = process.env.DK_AUTH_TOKEN || 'dragonknight2026extreme';

// 初始化数据文件
function initData() {
    const dir = path.dirname(DATA_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    if (!fs.existsSync(DATA_FILE)) {
        fs.writeFileSync(DATA_FILE, JSON.stringify({
            date: new Date().toISOString().split('T')[0],
            posts: []
        }, null, 2));
    }
}

// 读取数据
function readData() {
    try {
        return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
    } catch {
        return { date: new Date().toISOString().split('T')[0], posts: [] };
    }
}

// 写入数据
function writeData(data) {
    data.date = new Date().toISOString().split('T')[0];
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// 验证Token
function auth(req) {
    const token = req.headers['authorization']?.replace('Bearer ', '') ||
                  new URL(req.url, 'http://localhost').searchParams.get('token');
    return token === AUTH_TOKEN;
}

// 解析Body
function parseBody(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
            try { resolve(JSON.parse(body)); }
            catch { reject(new Error('Invalid JSON')); }
        });
        req.on('error', reject);
    });
}

// 响应JSON
function sendJSON(res, code, data) {
    res.writeHead(code, {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    });
    res.end(JSON.stringify(data, null, 2));
}

const server = http.createServer(async (req, res) => {
    // CORS
    if (req.method === 'OPTIONS') {
        res.writeHead(204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        });
        return res.end();
    }

    const url = new URL(req.url, 'http://localhost');
    const pathname = url.pathname;

    // GET /api/dragon-knight/posts
    if (req.method === 'GET' && pathname === '/api/dragon-knight/posts') {
        const data = readData();
        return sendJSON(res, 200, data);
    }

    // POST /api/dragon-knight/push
    if (req.method === 'POST' && pathname === '/api/dragon-knight/push') {
        if (!auth(req)) return sendJSON(res, 401, { error: '未授权' });
        
        try {
            const body = await parseBody(req);
            const data = readData();
            
            const post = {
                id: `dk-${Date.now()}`,
                title: body.title || '无标题',
                content: body.content || '',
                type: body.type || 'article',
                mediaUrl: body.mediaUrl || null,
                link: body.link || null,
                publishTime: new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }),
                tags: body.tags || []
            };
            
            data.posts.unshift(post); // 最新的在前面
            
            // 限制最多保留200条
            if (data.posts.length > 200) data.posts = data.posts.slice(0, 200);
            
            writeData(data);
            
            // 同时复制到webroot供网站访问
            console.log(`🐉 新内容已推送: ${post.title}`);
            
            return sendJSON(res, 200, { success: true, post });
        } catch (e) {
            return sendJSON(res, 400, { error: e.message });
        }
    }

    // DELETE /api/dragon-knight/:id
    if (req.method === 'DELETE' && pathname.startsWith('/api/dragon-knight/')) {
        if (!auth(req)) return sendJSON(res, 401, { error: '未授权' });
        
        const id = pathname.split('/').pop();
        const data = readData();
        const idx = data.posts.findIndex(p => p.id === id);
        
        if (idx === -1) return sendJSON(res, 404, { error: '内容不存在' });
        
        const removed = data.posts.splice(idx, 1)[0];
        writeData(data);
        
        console.log(`🗑️ 已删除: ${removed.title}`);
        return sendJSON(res, 200, { success: true, removed });
    }

    // GET /api/dragon-knight/health
    if (req.method === 'GET' && pathname === '/api/dragon-knight/health') {
        return sendJSON(res, 200, { status: 'ok', timestamp: new Date().toISOString() });
    }

    sendJSON(res, 404, { error: 'Not found' });
});

initData();
server.listen(PORT, () => {
    console.log(`🐉 疯狂的龙骑士 API 已启动 → http://0.0.0.0:${PORT}`);
    console.log(`   数据文件: ${DATA_FILE}`);
    console.log(`   推送接口: POST /api/dragon-knight/push`);
    console.log(`   查看接口: GET  /api/dragon-knight/posts`);
});
