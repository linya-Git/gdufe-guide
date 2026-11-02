#!/usr/bin/env python3
"""广财新生攻略 RAG Web 服务（纯标准库，无第三方依赖）。

启动:  python3 server.py [port]
访问:  http://127.0.0.1:8899
"""
import json, os, re, sys, time, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

# --- 读取 API key（.env，chmod 600） ---
AGNES_KEY = ''
env_file = BASE / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith('AGNES_API_KEY='):
            AGNES_KEY = line.split('=', 1)[1].strip()
if not AGNES_KEY:
    AGNES_KEY = os.environ.get('AGNES_API_KEY', '')

# --- 模型提供商 ---
PROVIDERS = {
    'agnes': {
        'name': 'Agnes（免费）',
        'url': 'https://apihub.agnes-ai.com/v1/chat/completions',
        'key': AGNES_KEY,
        'models': ['agnes-2.5-flash'],
    },
}
DEFAULT_MODEL = 'agnes-2.5-flash'  # 默认用免费的 Agnes

# --- 反馈记录（不确定/矛盾/纠错的问题，仅广财相关） ---
FEEDBACK_DIR = BASE / 'feedback'
FEEDBACK_DIR.mkdir(exist_ok=True)
FEEDBACK_FILE = FEEDBACK_DIR / 'feedback.jsonl'

# 广财相关关键词：命中才记录（非广财问题不记录）
GDUFE_KEYWORDS = [
    '广财', '广东财经', '财经大学', '学校', '校区', '佛山', '三水', '广州校区',
    '宿舍', '食堂', '上课', '军训', '报到', '学费', '转专业', '辅修', '社团',
    '医务室', '门诊', '快递', '图书馆', '教学楼', '校历', '医保', '缴费',
    '入学', '专业', '学院', '选课', '学分', '绩点', '考试', '校车', '小白车',
    '小绿', '开学', '录取', '通知书', '新生', '校训', '校徽', '章程', '网',
]

LOCK = threading.Lock()

# missing 去重：同一 query 60 秒内只记一条
_last_missing = {}
_last_missing_lock = threading.Lock()

def is_gdufe_related(q):
    return any(k in q for k in GDUFE_KEYWORDS)

def record_feedback(entry):
    """追加一条反馈记录（线程安全）。只读文件系统下静默跳过。"""
    entry.setdefault('ts', time.strftime('%Y-%m-%d %H:%M:%S'))
    with LOCK:
        try:
            with open(FEEDBACK_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except OSError:
            # Vercel 等只读环境：写不了就放弃记录，不要影响问答
            pass

def record_missing(query, max_score, results, answer_tail=''):
    """记录 missing 反馈，60 秒内同问题去重。"""
    now = time.time()
    with _last_missing_lock:
        last = _last_missing.get(query, 0)
        if now - last < 60:
            return False
        _last_missing[query] = now
    record_feedback({
        'type': 'missing',
        'query': query,
        'max_score': round(max_score, 3),
        'hits': [f"{r['source']}/{r['section']}" for r in results[:3]],
        'answer_tail': answer_tail[-80:],
    })
    return True

# --- 延迟导入 RAG（首次请求时构建检索器，线程安全） ---
_search = None
_search_lock = threading.Lock()


def _build_vector_search():
    """向量检索：需要 chromadb + fastembed + 预建索引（本地用）。"""
    import chromadb
    from fastembed import TextEmbedding
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    client = chromadb.PersistentClient(path=str(BASE / 'rag' / 'index'))
    col = client.get_collection('gdufe_guide')
    model = TextEmbedding(model_name='BAAI/bge-small-zh-v1.5')

    def search(query, topk=6):
        emb = list(model.embed([query]))[0]
        res = col.query(query_embeddings=[emb.tolist()], n_results=topk,
                        include=['documents', 'metadatas', 'distances'])
        out = []
        for doc, meta, dist in zip(res['documents'][0], res['metadatas'][0], res['distances'][0]):
            out.append({'text': doc, 'source': meta['source'], 'section': meta['section'],
                        'score': round(1 - dist, 4)})
        return out

    return search


def _build_keyword_search():
    """纯标准库的关键词检索：读 kb/*.md，按二级标题切块，字符二元组打分。

    没有向量库、没有预建索引的环境（比如 Vercel）靠它兜底。
    """
    kb_dir = BASE / 'kb'
    docs = []
    if kb_dir.exists():
        for f in sorted(kb_dir.glob('*.md')):
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            for part in re.split(r'\n(?=## )', text):
                part = part.strip()
                if len(part) < 10:
                    continue
                m = re.match(r'##\s*(.+)', part)
                docs.append({
                    'source': f.name,
                    'section': (m.group(1).strip() if m else '正文')[:40],
                    'text': part,
                })
    if not docs:
        return lambda query, topk=6: []

    def bigrams(s):
        s = re.sub(r'\s+', '', s)
        if len(s) < 2:
            return {s} if s else set()
        return {s[i:i + 2] for i in range(len(s) - 1)}

    indexed = [(d, bigrams(d['text'])) for d in docs]

    def search(query, topk=6):
        qg = bigrams(query)
        if not qg:
            return []
        scored = []
        for d, grams in indexed:
            hit = len(qg & grams)
            if hit:
                scored.append((hit / len(qg), d))
        scored.sort(key=lambda x: -x[0])
        return [
            {'text': d['text'][:900], 'source': d['source'],
             'section': d['section'], 'score': round(s, 4)}
            for s, d in scored[:topk]
        ]

    return search


def get_search():
    global _search
    if _search is None:
        with _search_lock:
            if _search is None:
                try:
                    _search = _build_vector_search()
                except Exception:
                    _search = _build_keyword_search()
    return _search

SYSTEM_PROMPT = """你是"广财新生攻略助手"，专属于广东财经大学（广财）的新生校园生活助手。
你的知识来自《2026广东财经大学新生攻略》一手资料（含图片OCR识别文本）。

回答要求：
1. 优先使用"参考资料"中的信息作答；资料不足时如实说明"资料里没有"，不要编造。
2. 用中文回答，语气亲切、实用、具体；可以直接给出操作建议。
3. 涉及具体地点、时间、电话、路线时，尽量保留原始数据细节。
4. 如果用户问图片类内容（宿舍实景、公众号二维码等），告知可用图片查看，并提示图片来源。
5. 回答控制在合理长度：简单问题简洁回答，复杂问题分点说明。"""

def build_prompt(query, history):
    ctx_parts = []
    max_score = 0.0
    try:
        results = get_search()(query, topk=6)
        max_score = max((r['score'] for r in results), default=0.0)
    except Exception as e:
        results = []
        ctx_parts.append(f'（检索暂不可用：{e}）')
    for i, r in enumerate(results, 1):
        ctx_parts.append(f'[资料{i}] 来源：{r["source"]} / {r["section"]}\n{r["text"]}')
    context = '\n\n'.join(ctx_parts) if ctx_parts else '（无检索结果）'
    user_content = f'===== 参考资料 =====\n{context}\n===== 问题 =====\n{query}'
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    # 最近 6 条历史（保留上下文，控制 token）
    for h in history[-6:]:
        messages.append(h)
    messages.append({'role': 'user', 'content': user_content})
    # 低置信度 + 广财相关 → 记录为“资料可能缺失”
    if is_gdufe_related(query) and max_score < 0.35:
        record_missing(query, max_score, results)
    return messages, results

# --- 知识文件 → 图片关联（用于问答时展示相关图片） ---
KB_IMAGES_CACHE = None
def kb_images_map():
    """解析 kb/*.md 里的 ![..](images/xx) 引用，返回 {文件名: [图片名]}"""
    global KB_IMAGES_CACHE
    if KB_IMAGES_CACHE is None:
        m = {}
        for f in (BASE / 'kb').glob('*.md'):
            txt = f.read_text(encoding='utf-8', errors='ignore')
            imgs = re.findall(r'!\[.*?\]\(images/([^)]+)\)', txt)
            if imgs:
                m[f.name] = list(dict.fromkeys(imgs))
        KB_IMAGES_CACHE = m
    return KB_IMAGES_CACHE

# 图片展示白名单：只保留明确“看图”意图，避免乱放
# 规则：含以下关键词才显示对应图片；普通问答不显示图片
IMAGE_WHITELIST = {
    '地图': ['教学楼_1.jpeg'],
    '平面图': ['教学楼_1.jpeg'],
    '校园地图': ['教学楼_1.jpeg'],
    '地图吗': ['教学楼_1.jpeg'],
    '有图': ['教学楼_1.jpeg'],
    '图片': [],  # 占位：匹配'图片'不自动配图，除非其他词命中
    '二维码': ['常用公众号_1.jpeg', '常用公众号_2.jpeg', '常用公众号_3.jpeg',
               '常用公众号_4.jpeg', '常用公众号_5.jpeg', '常用公众号_6.jpeg'],
    '公众号': ['常用公众号_1.jpeg', '常用公众号_2.jpeg', '常用公众号_3.jpeg',
               '常用公众号_4.jpeg', '常用公众号_5.jpeg', '常用公众号_6.jpeg'],
    '上课时间': ['上课时间_1.jpeg'],
    '时间表': ['上课时间_1.jpeg'],
    '医务室': ['就医详解_1.webp'],
    '就诊': ['就医详解_1.webp'],
    '楼层': ['图书馆_1.png', '图书馆_2.png', '图书馆_3.png'],
    '校徽': ['校训校徽_1.jpeg', '校训校徽_2.jpeg'],
    '校歌': ['校训校徽_3.jpeg'],
    '照片': ['学校历史_1.jpeg', '学校历史_2.jpeg', '学校历史_3.jpeg'],
}
# 位置类疑问（在哪/哪里/位置）不再自动配图，避免乱放；文本回答即可

# 图片名解析：kb 引用可能无扩展名，映射到 images/ 实际文件名
IMAGE_NAMES = None
def resolve_image(name):
    global IMAGE_NAMES
    if IMAGE_NAMES is None:
        IMAGE_NAMES = {p.stem: p.name for p in (BASE / 'images').glob('*') if p.is_file()}
    return IMAGE_NAMES.get(name, name)

def related_images(query, results):
    """白名单关键词匹配：只展示与问题明确相关的图片，最多 6 张。"""
    imgs = []
    for kw, names in IMAGE_WHITELIST.items():
        if kw in query:
            for n in names:
                n = resolve_image(n)
                if n not in imgs:
                    imgs.append(n)
    return imgs[:6]

def resolve_provider(model):
    """根据模型名找到 provider，返回 (provider_name, model_name)。"""
    for pname, p in PROVIDERS.items():
        if model in p['models']:
            return pname, model
    # 兼容传 provider 名
    if model in PROVIDERS:
        return model, PROVIDERS[model]['models'][0]
    # 默认
    return 'agnes', DEFAULT_MODEL

def call_llm(messages, model=None, stream=True):
    model = model or DEFAULT_MODEL
    pname, resolved = resolve_provider(model)
    p = PROVIDERS[pname]
    body = json.dumps({
        'model': resolved,
        'messages': messages,
        'stream': stream,
        'temperature': 0.6,
        'max_tokens': 2000,
    }).encode()
    req = urllib.request.Request(p['url'], data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {p["key"]}',
    })
    return urllib.request.urlopen(req, timeout=120)

def sse_parse_line(line):
    """解析 SSE data: 行，返回 (delta_text, finish_reason or None)。"""
    line = line.strip()
    if not line.startswith('data:'):
        return None, None
    payload = line[5:].strip()
    if payload == '[DONE]':
        return None, 'done'
    try:
        obj = json.loads(payload)
    except Exception:
        return None, None
    if 'choices' in obj and obj['choices']:
        ch = obj['choices'][0]
        delta = ch.get('delta', {}) or {}
        text = delta.get('content') or ''
        return text, ch.get('finish_reason')
    return None, None

def iter_sse_events(chunks):
    """把网络分块字节流按 SSE 事件（\n\n 分隔）切分，避免跨包截断。"""
    buf = b''
    for chunk in chunks:
        buf += chunk
        while True:
            idx = buf.find(b'\n\n')
            if idx == -1:
                break
            event = buf[:idx]
            buf = buf[idx + 2:]
            if event.strip():
                yield event.decode('utf-8', 'ignore')
    if buf.strip():
        yield buf.decode('utf-8', 'ignore')

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.md': 'text/markdown; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp',
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write('[%s] %s\n' % (time.strftime('%H:%M:%S'), fmt % args))

    def _send(self, code, body, ctype='application/json; charset=utf-8', headers=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path, base_dir):
        base = base_dir.resolve()
        p = (base_dir / path).resolve()
        try:
            os.path.commonpath([str(p), str(base)])
        except ValueError:
            return self._send(403, 'forbidden')
        if p != base and str(base) not in str(p.parent):
            return self._send(403, 'forbidden')
        if not p.exists() or not p.is_file():
            return self._send(404, 'not found')
        ext = p.suffix.lower()
        self._send(200, p.read_bytes(), MIME.get(ext, 'application/octet-stream'))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path == '/' or path == '/index.html':
            self._serve_file('index.html', BASE)
        elif path.startswith('/kb/'):
            self._serve_file(path[4:], BASE / 'kb')
        elif path.startswith('/images/'):
            self._serve_file(path[8:], BASE / 'images')
        elif path == '/api/tabs':
            tabs = []
            for f in sorted((BASE / 'kb').glob('*.md')):
                tabs.append({'file': f.name, 'title': f.name})
            self._send(200, json.dumps(tabs, ensure_ascii=False))
        elif path == '/api/models':
            out = [{'provider': pname, 'name': p['name'], 'models': p['models']}
                   for pname, p in PROVIDERS.items()]
            self._send(200, json.dumps(out, ensure_ascii=False))
        elif path == '/api/images':
            imgs = sorted(p.name for p in (BASE / 'images').glob('*') if p.suffix.lower() in ('.jpeg', '.jpg', '.png', '.gif', '.webp'))
            self._send(200, json.dumps(imgs, ensure_ascii=False))
        else:
            self._send(404, 'not found')

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/feedback':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length) or b'{}')
            except Exception:
                return self._send(400, json.dumps({'error': 'bad request'}))
            query = (body.get('query') or '').strip()
            ftype = body.get('type') or 'correction'
            note = (body.get('note') or '').strip()
            if not query:
                return self._send(400, json.dumps({'error': 'empty query'}))
            if ftype not in ('correction', 'conflict', 'missing', 'uncertain'):
                ftype = 'correction'
            # 仅记录广财相关问题
            if not is_gdufe_related(query) and not is_gdufe_related(note):
                return self._send(200, json.dumps({'ok': False, 'reason': 'not-gdufe'}))
            record_feedback({'type': ftype, 'query': query, 'note': note})
            return self._send(200, json.dumps({'ok': True}))
        if parsed.path != '/api/ask':
            return self._send(404, 'not found')
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) or b'{}')
        except Exception:
            return self._send(400, json.dumps({'error': 'bad request'}))
        query = (body.get('query') or '').strip()
        history = body.get('history') or []
        model = body.get('model') or DEFAULT_MODEL
        if not isinstance(history, list):
            history = []
        if not query:
            return self._send(400, json.dumps({'error': 'empty query'}))

        messages, results = build_prompt(query, history)
        if not AGNES_KEY:
            # 无 key 时降级为纯检索
            return self._send(200, json.dumps({
                'answer': '（未配置 AGNES_API_KEY，以下为检索到的资料）\n\n' + '\n\n'.join(
                    f'【{r["source"]} / {r["section"]}】\n{r["text"]}' for r in results),
                'references': results, 'stream': False,
            }, ensure_ascii=False))
        try:
            resp = call_llm(messages, model=model, stream=True)
        except Exception as e:
            return self._send(502, json.dumps({'error': f'LLM 调用失败: {e}'}, ensure_ascii=False))

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        # 先发引用（按 来源/章节 去重）+ 相关图片
        seen_refs = set()
        dedup_refs = []
        for r in results:
            key = (r.get('source'), r.get('section'))
            if key not in seen_refs:
                seen_refs.add(key)
                dedup_refs.append(r)
        imgs = related_images(query, results)
        self.wfile.write(f'data: {json.dumps({"type": "refs", "refs": dedup_refs, "images": imgs}, ensure_ascii=False)}\n\n'.encode())
        answer_text = ''
        try:
            for event in iter_sse_events(resp):
                for line in event.split('\n'):
                    text, finish = sse_parse_line(line)
                    if text:
                        answer_text += text
                        self.wfile.write(f'data: {json.dumps({"type": "delta", "text": text}, ensure_ascii=False)}\n\n'.encode())
                        self.wfile.flush()
                    if finish == 'done':
                        break
        except Exception as e:
            try:
                self.wfile.write(f'data: {json.dumps({"type": "error", "text": str(e)}, ensure_ascii=False)}\n\n'.encode())
            except Exception:
                pass
        finally:
            try:
                self.wfile.write(b'data: {"type":"done"}\n\n')
                self.wfile.flush()
            except Exception:
                pass
            # 模型自述资料不足 → 记录（广财相关 + 回答含“没有”类表述，60s 去重）
            if is_gdufe_related(query):
                lacks = ['资料里没有', '没有找到', '暂时没有', '没有相关信息', '未查询到',
                         '资料中没有', '未能找到', '没有收录', '没有具体']
                if any(k in answer_text for k in lacks):
                    record_missing(query, max((r['score'] for r in results), default=0), results, answer_text)

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'广财新生攻略前端已启动: http://127.0.0.1:{port}')
    print('(按 Ctrl+C 停止)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')

if __name__ == '__main__':
    main()
