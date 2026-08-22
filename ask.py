#!/usr/bin/env python3
"""GDUFE 新生攻略 RAG 问答工具。

用法:
  python3 ask.py "问题" [--topk 5] [--prompt] [--llm-cmd "..."]
  --prompt   只输出组装好的 RAG 上下文 + 提示词模板（给 LLM Agent 用）
  --llm-cmd  可选：把上下文通过管道喂给外部 LLM CLI（如 ollama run qwen2.5）
"""
import argparse, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rag.search import search

PROMPT_TEMPLATE = """你是一位专属于广东财经大学（广财）的新生攻略助手，请基于下面提供的"参考资料"回答新生的问题。

要求：
- 优先使用参考资料中的信息作答；资料不足时如实说明，不要编造。
- 回答用中文，语气亲切、实用，可给出具体操作建议。
- 涉及具体地点/时间/电话时，尽量给出原始数据中的细节。

===== 参考资料 =====
{context}
===== 问题 =====
{query}
"""

def build_context(results, max_chars=6000):
    parts = []
    used = 0
    for i, r in enumerate(results, 1):
        block = f'[资料{i}] 来源：{r["source"]} / {r["section"]}\n{r["text"]}'
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return '\n\n'.join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('query')
    ap.add_argument('--topk', type=int, default=5)
    ap.add_argument('--prompt', action='store_true')
    ap.add_argument('--llm-cmd', default='', help='e.g. "ollama run qwen2.5:7b"')
    args = ap.parse_args()

    results = search(args.query, args.topk)
    ctx = build_context(results)
    prompt = PROMPT_TEMPLATE.format(context=ctx, query=args.query)

    if args.prompt:
        print(prompt)
        return
    if args.llm_cmd:
        p = subprocess.run(args.llm_cmd.split(), input=prompt, text=True, capture_output=True)
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        return
    # 默认：打印上下文 + 提示词，供 Agent 使用
    print(prompt)

if __name__ == '__main__':
    main()
