#!/usr/bin/env python3
"""OCR all images in images/ and save text results."""
import json, os, glob
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
results = {}
for img in sorted(glob.glob('images/*.jpeg') + glob.glob('images/*.png') + glob.glob('images/*.webp')):
    name = os.path.basename(img)
    try:
        result, _ = ocr(img)
        texts = [t[1] for t in result] if result else []
        results[name] = texts
        print(f'{name}: {len(texts)} lines')
    except Exception as e:
        print(f'{name}: ERROR {e}')
        results[name] = []

os.makedirs('ocr', exist_ok=True)
json.dump(results, open('ocr/ocr_results.json', 'w'), ensure_ascii=False, indent=1)

# also per-image text files
for name, texts in results.items():
    safe = name.rsplit('.', 1)[0]
    with open(f'ocr/{safe}.txt', 'w') as f:
        f.write('\n'.join(texts))
print('done')
