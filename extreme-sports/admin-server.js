#!/usr/bin/env node
/**
 * 疯狂的龙骑士 - 网页管理后台
 * 
 * 功能：
 *   - 登录验证（Token）
 *   - 文章发布/编辑/删除
 *   - 草稿箱
 *   - 预览
 * 
 * 端口：3457（可配置）
 * 访问：http://8.130.185.192:3457
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = process.env.DK_ADMIN_PORT || 3457;
const DATA_FILE = process.env.DK_DATA_FILE || '/var/www/dragonknightbeat.com/dragon-knight-posts.json';
const AUTH_TOKEN = process.env.DK_AUTH_TOKEN || '1988520';
const SESSION_SECRET = crypto.randomBytes(32).toString('hex');

// 简易Session存储
const sessions = new Map();

// 初始化数据文件
function initData() {
    const dir = path.dirname(DATA_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    if (!fs.existsSync(DATA_FILE)) {
        fs.writeFileSync(DATA_FILE, JSON.stringify({ date: new Date().toISOString().split('T')[0], posts: [] }, null, 2));
    }
}

function readData() {
    try { return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8')); }
    catch { return { date: new Date().toISOString().split('T')[0], posts: [] }; }
}

function writeData(data) {
    data.date = new Date().toISOString().split('T')[0];
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

function sendHTML(res, html) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
}

function sendJSON(res, code, data) {
    res.writeHead(code, {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    });
    res.end(JSON.stringify(data));
}

function parseBody(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
            try { resolve(JSON.parse(body)); }
            catch { resolve({}); }
        });
        req.on('error', reject);
    });
}

function getCookies(req) {
    const cookies = {};
    (req.headers.cookie || '').split(';').forEach(c => {
        const [k, v] = c.trim().split('=');
        if (k) cookies[k] = v;
    });
    return cookies;
}

function checkAuth(req) {
    const cookies = getCookies(req);
    const sid = cookies['dk_session'];
    return sid && sessions.has(sid);
}

// ====== HTML页面 ======

function loginPage() {
    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐉 疯狂的龙骑士 - 登录</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { 
    min-height:100vh; display:flex; align-items:center; justify-content:center;
    background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2e 50%, #2d1b4e 100%);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.login-card {
    background: rgba(255,255,255,0.05); backdrop-filter: blur(20px);
    border: 1px solid rgba(255,107,53,0.3); border-radius: 20px;
    padding: 50px 40px; width: 380px; text-align: center;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.logo { font-size: 64px; margin-bottom: 10px; }
h1 { color: #ffdd00; font-size: 24px; margin-bottom: 8px; }
.subtitle { color: #ff6b35; font-size: 14px; margin-bottom: 30px; }
input {
    width: 100%; padding: 14px 18px; border-radius: 12px;
    border: 1px solid rgba(255,107,53,0.3); background: rgba(255,255,255,0.08);
    color: #fff; font-size: 16px; outline: none; margin-bottom: 16px;
    transition: border-color 0.3s;
}
input:focus { border-color: #ff6b35; }
input::placeholder { color: rgba(255,255,255,0.3); }
button {
    width: 100%; padding: 14px; border-radius: 12px; border: none;
    background: linear-gradient(135deg, #ff4500, #ff6b35);
    color: #fff; font-size: 16px; font-weight: bold; cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}
button:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(255,69,0,0.4); }
.error { color: #ff6b6b; font-size: 14px; margin-top: 12px; }
</style>
</head>
<body>
<div class="login-card">
    <div class="logo">🐉</div>
    <h1>疯狂的龙骑士</h1>
    <p class="subtitle">内容管理后台</p>
    <form onsubmit="login(event)">
        <input type="password" id="token" placeholder="输入访问密钥..." autofocus>
        <button type="submit">🚀 进入后台</button>
    </form>
    <div class="error" id="err"></div>
</div>
<script>
async function login(e) {
    e.preventDefault();
    const token = document.getElementById('token').value;
    const res = await fetch('./api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token})
    });
    const data = await res.json();
    if (data.success) location.href = './';
    else document.getElementById('err').textContent = data.error || '密钥错误';
}
</script>
</body>
</html>`;
}

function adminPage() {
    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐉 疯狂的龙骑士 - 管理后台</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
:root {
    --bg: #0a0a1a; --card: rgba(255,255,255,0.05);
    --border: rgba(255,107,53,0.2); --orange: #ff6b35;
    --yellow: #ffdd00; --red: #ff4500; --text: #e0e0e0;
    --dim: rgba(255,255,255,0.5);
}
body {
    background: linear-gradient(135deg, #0a0a1a, #1a0a2e, #2d1b4e);
    color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    min-height: 100vh;
}
/* 顶栏 */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 24px; border-bottom: 1px solid var(--border);
    background: rgba(0,0,0,0.3); backdrop-filter: blur(10px);
    position: sticky; top: 0; z-index: 100;
}
.topbar h1 { font-size: 20px; color: var(--yellow); }
.topbar .actions { display: flex; gap: 10px; }
.btn {
    padding: 10px 20px; border-radius: 10px; border: none;
    font-size: 14px; font-weight: bold; cursor: pointer;
    transition: all 0.2s;
}
.btn-primary { background: linear-gradient(135deg, var(--red), var(--orange)); color: #fff; }
.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(255,69,0,0.4); }
.btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--text); }
.btn-ghost:hover { border-color: var(--orange); }
.btn-danger { background: rgba(255,60,60,0.2); color: #ff6b6b; border: 1px solid rgba(255,60,60,0.3); }
.btn-danger:hover { background: rgba(255,60,60,0.3); }

/* 主内容 */
.container { max-width: 900px; margin: 0 auto; padding: 24px; }

/* 编辑器面板 */
.editor-panel {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 16px; padding: 24px; margin-bottom: 24px;
    display: none;
}
.editor-panel.active { display: block; }
.editor-panel h2 { color: var(--yellow); margin-bottom: 16px; font-size: 18px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: var(--dim); margin-bottom: 6px; }
.form-group input, .form-group textarea, .form-group select {
    width: 100%; padding: 12px 14px; border-radius: 10px;
    border: 1px solid var(--border); background: rgba(255,255,255,0.06);
    color: var(--text); font-size: 14px; outline: none;
    font-family: inherit; transition: border-color 0.3s;
}
.form-group input:focus, .form-group textarea:focus { border-color: var(--orange); }
.form-group textarea { min-height: 160px; resize: vertical; line-height: 1.6; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
.editor-actions { display: flex; gap: 10px; margin-top: 16px; }

/* 文章列表 */
.post-list { display: flex; flex-direction: column; gap: 12px; }
.post-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 14px; padding: 18px; transition: all 0.2s;
}
.post-card:hover { border-color: var(--orange); transform: translateY(-1px); }
.post-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.post-type {
    font-size: 20px; width: 36px; height: 36px; display: flex;
    align-items: center; justify-content: center;
    background: rgba(255,107,53,0.1); border-radius: 10px;
}
.post-title { font-size: 16px; font-weight: bold; color: #fff; flex: 1; }
.post-time { font-size: 12px; color: var(--dim); }
.post-content { font-size: 13px; color: var(--dim); line-height: 1.5; margin-bottom: 10px; }
.post-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.tag {
    font-size: 12px; padding: 3px 10px; border-radius: 20px;
    background: rgba(255,107,53,0.12); color: var(--orange);
}
.post-actions { display: flex; gap: 8px; }

/* 空状态 */
.empty {
    text-align: center; padding: 60px 20px; color: var(--dim);
}
.empty .icon { font-size: 48px; margin-bottom: 12px; }

/* 预览 */
.preview-content {
    background: rgba(255,255,255,0.03); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px; margin-top: 12px;
    white-space: pre-wrap; line-height: 1.6; font-size: 14px;
}
</style>
</head>
<body>
<div class="topbar">
    <h1>🐉 疯狂的龙骑士</h1>
    <div class="actions">
        <button class="btn btn-primary" onclick="showEditor()">✍️ 写新文章</button>
        <button class="btn btn-ghost" onclick="location.href='./api/logout'">退出</button>
    </div>
</div>

<div class="container">
    <!-- 编辑器 -->
    <div class="editor-panel" id="editor">
        <h2 id="editorTitle">✍️ 写新文章</h2>
        <input type="hidden" id="editId">
        <div class="form-group">
            <label>标题</label>
            <input type="text" id="fTitle" placeholder="输入文章标题...">
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>类型</label>
                <select id="fType">
                    <option value="article">📝 文章</option>
                    <option value="video">🎬 视频</option>
                    <option value="photo">📸 照片</option>
                    <option value="link">🔗 链接</option>
                </select>
            </div>
            <div class="form-group">
                <label>标签（逗号分隔）</label>
                <input type="text" id="fTags" placeholder="冲浪, 冒险, 训练">
            </div>
        </div>
        <div class="form-group">
            <label>内容</label>
            <textarea id="fContent" placeholder="写下你的冒险故事..."></textarea>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>媒体链接（可选）</label>
                <input type="text" id="fMediaUrl" placeholder="图片或视频URL">
            </div>
            <div class="form-group">
                <label>外部链接（可选）</label>
                <input type="text" id="fLink" placeholder="https://...">
            </div>
        </div>
        <div class="editor-actions">
            <button class="btn btn-primary" onclick="savePost()">🚀 发布</button>
            <button class="btn btn-ghost" onclick="previewPost()">👁️ 预览</button>
            <button class="btn btn-ghost" onclick="hideEditor()">取消</button>
        </div>
        <div id="previewArea"></div>
    </div>

    <!-- 文章列表 -->
    <div class="post-list" id="postList">
        <div class="empty"><div class="icon">🐉</div><p>加载中...</p></div>
    </div>
</div>

<script>
let posts = [];

async function loadPosts() {
    const res = await fetch('./api/posts');
    const data = await res.json();
    posts = data.posts || [];
    render();
}

function render() {
    const list = document.getElementById('postList');
    if (!posts.length) {
        list.innerHTML = '<div class="empty"><div class="icon">🐉</div><p>还没有内容，写第一篇文章吧！</p></div>';
        return;
    }
    list.innerHTML = posts.map(p => {
        const icons = {article:'📝',video:'🎬',photo:'📸',link:'🔗'};
        const tags = (p.tags||[]).map(t => '<span class="tag">'+t+'</span>').join('');
        return '<div class="post-card">'+
            '<div class="post-header">'+
                '<div class="post-type">'+(icons[p.type]||'🔥')+'</div>'+
                '<div class="post-title">'+esc(p.title)+'</div>'+
                '<div class="post-time">'+esc(p.publishTime||'')+'</div>'+
            '</div>'+
            '<div class="post-content">'+esc((p.content||'').substring(0,150))+'</div>'+
            (tags ? '<div class="post-tags">'+tags+'</div>' : '')+
            '<div class="post-actions">'+
                '<button class="btn btn-ghost" onclick="editPost(\\''+p.id+'\\')">✏️ 编辑</button>'+
                '<button class="btn btn-danger" onclick="deletePost(\\''+p.id+'\\')">🗑️ 删除</button>'+
            '</div>'+
        '</div>';
    }).join('');
}

function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

function showEditor(id) {
    document.getElementById('editor').classList.add('active');
    document.getElementById('editorTitle').textContent = id ? '✏️ 编辑文章' : '✍️ 写新文章';
    if (!id) {
        document.getElementById('editId').value = '';
        document.getElementById('fTitle').value = '';
        document.getElementById('fContent').value = '';
        document.getElementById('fType').value = 'article';
        document.getElementById('fTags').value = '';
        document.getElementById('fMediaUrl').value = '';
        document.getElementById('fLink').value = '';
    }
    document.getElementById('fTitle').focus();
}

function hideEditor() {
    document.getElementById('editor').classList.remove('active');
    document.getElementById('previewArea').innerHTML = '';
}

function editPost(id) {
    const p = posts.find(x => x.id === id);
    if (!p) return;
    showEditor(id);
    document.getElementById('editId').value = p.id;
    document.getElementById('fTitle').value = p.title || '';
    document.getElementById('fContent').value = p.content || '';
    document.getElementById('fType').value = p.type || 'article';
    document.getElementById('fTags').value = (p.tags||[]).join(', ');
    document.getElementById('fMediaUrl').value = p.mediaUrl || '';
    document.getElementById('fLink').value = p.link || '';
}

function previewPost() {
    const title = document.getElementById('fTitle').value;
    const content = document.getElementById('fContent').value;
    const area = document.getElementById('previewArea');
    area.innerHTML = '<div class="preview-content"><strong>'+esc(title)+'</strong>\\n\\n'+esc(content)+'</div>';
}

async function savePost() {
    const editId = document.getElementById('editId').value;
    const body = {
        title: document.getElementById('fTitle').value,
        content: document.getElementById('fContent').value,
        type: document.getElementById('fType').value,
        tags: document.getElementById('fTags').value.split(',').map(s=>s.trim()).filter(Boolean),
        mediaUrl: document.getElementById('fMediaUrl').value || null,
        link: document.getElementById('fLink').value || null
    };
    if (!body.title) return alert('请输入标题');
    
    const url = editId ? './api/posts/'+editId : './api/posts';
    const method = editId ? 'PUT' : 'POST';
    
    const res = await fetch(url, {
        method, headers: {'Content-Type':'application/json'},
        body: JSON.stringify(body)
    });
    const data = await res.json();
    if (data.success) {
        hideEditor();
        loadPosts();
    } else {
        alert(data.error || '保存失败');
    }
}

async function deletePost(id) {
    if (!confirm('确定删除这篇内容吗？')) return;
    const res = await fetch('./api/posts/'+id, {method:'DELETE'});
    const data = await res.json();
    if (data.success) loadPosts();
    else alert(data.error || '删除失败');
}

loadPosts();
</script>
</body>
</html>`;
}

// ====== HTTP服务 ======

const server = http.createServer(async (req, res) => {
    if (req.method === 'OPTIONS') {
        res.writeHead(204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        });
        return res.end();
    }

    const url = new URL(req.url, 'http://localhost');
    const p = url.pathname;

    // 登录页
    if (p === '/' && !checkAuth(req)) return sendHTML(res, loginPage());
    
    // 管理页
    if (p === '/' && checkAuth(req)) return sendHTML(res, adminPage());

    // 登录API
    if (p === '/api/login' && req.method === 'POST') {
        const body = await parseBody(req);
        if (body.token === AUTH_TOKEN) {
            const sid = crypto.randomBytes(24).toString('hex');
            sessions.set(sid, { created: Date.now() });
            res.writeHead(200, {
                'Content-Type': 'application/json',
                'Set-Cookie': `dk_session=${sid}; Path=/; HttpOnly; SameSite=Strict`
            });
            res.end(JSON.stringify({ success: true }));
        } else {
            sendJSON(res, 401, { error: '密钥错误' });
        }
        return;
    }

    // 退出
    if (p === '/api/logout') {
        const cookies = getCookies(req);
        if (cookies.dk_session) sessions.delete(cookies.dk_session);
        res.writeHead(302, {
            'Set-Cookie': 'dk_session=; Path=/; Max-Age=0',
            'Location': '/'
        });
        return res.end();
    }

    // 以下API需要认证
    if (!checkAuth(req) && p.startsWith('/api/')) {
        return sendJSON(res, 401, { error: '未登录' });
    }

    // 获取文章列表
    if (p === '/api/posts' && req.method === 'GET') {
        return sendJSON(res, 200, readData());
    }

    // 发布新文章
    if (p === '/api/posts' && req.method === 'POST') {
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
        data.posts.unshift(post);
        if (data.posts.length > 200) data.posts = data.posts.slice(0, 200);
        writeData(data);
        console.log(`🐉 新文章: ${post.title}`);
        return sendJSON(res, 200, { success: true, post });
    }

    // 编辑文章
    if (p.startsWith('/api/posts/') && req.method === 'PUT') {
        const id = p.split('/').pop();
        const body = await parseBody(req);
        const data = readData();
        const idx = data.posts.findIndex(x => x.id === id);
        if (idx === -1) return sendJSON(res, 404, { error: '文章不存在' });
        
        Object.assign(data.posts[idx], {
            title: body.title || data.posts[idx].title,
            content: body.content ?? data.posts[idx].content,
            type: body.type || data.posts[idx].type,
            mediaUrl: body.mediaUrl ?? data.posts[idx].mediaUrl,
            link: body.link ?? data.posts[idx].link,
            tags: body.tags || data.posts[idx].tags
        });
        writeData(data);
        console.log(`✏️ 编辑: ${data.posts[idx].title}`);
        return sendJSON(res, 200, { success: true, post: data.posts[idx] });
    }

    // 删除文章
    if (p.startsWith('/api/posts/') && req.method === 'DELETE') {
        const id = p.split('/').pop();
        const data = readData();
        const idx = data.posts.findIndex(x => x.id === id);
        if (idx === -1) return sendJSON(res, 404, { error: '文章不存在' });
        const removed = data.posts.splice(idx, 1)[0];
        writeData(data);
        console.log(`🗑️ 删除: ${removed.title}`);
        return sendJSON(res, 200, { success: true });
    }

    // 健康检查
    if (p === '/api/health') return sendJSON(res, 200, { status: 'ok' });

    sendJSON(res, 404, { error: 'Not found' });
});

initData();
server.listen(PORT, () => {
    console.log(`🐉 龙骑士管理后台已启动 → http://0.0.0.0:${PORT}`);
    console.log(`   密钥: ${AUTH_TOKEN}`);
});
