"""Explicit offline OCR indexing. Requires Poppler and Tesseract rus+eng."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from pypdf import PdfReader


def index(directory='data_alfbnk'):
    root = Path(directory)
    for pdf in root.glob('*.pdf'):
        checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
        target = pdf.with_suffix('.pages.json')
        if target.exists() and json.loads(target.read_text()).get('checksum') == checksum:
            print(pdf.name, 'unchanged', flush=True)
            continue
        pages = []
        reader = PdfReader(pdf)
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or '').strip()
            method = 'text'
            if len(text) < 50:
                with tempfile.TemporaryDirectory() as temp:
                    prefix = str(Path(temp)/'page')
                    subprocess.run(['pdftoppm','-f',str(number),'-l',str(number),'-scale-to','1800','-png','-singlefile',str(pdf),prefix], check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    text = subprocess.check_output(['tesseract',prefix+'.png','stdout','-l','rus+eng'], timeout=90, stderr=subprocess.DEVNULL).decode()
                    method = 'ocr'
            pages.append({'page':number,'text':text,'extraction_method':method})
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'checksum':checksum,'pages':pages},ensure_ascii=False))
        os.replace(temporary,target)
        print(pdf.name,'pages',len(pages),'characters',sum(len(p['text']) for p in pages),flush=True)

if __name__ == '__main__':
    index()
