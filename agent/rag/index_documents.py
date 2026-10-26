"""Explicit offline OCR indexing. Requires Poppler and Tesseract rus+eng."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from pypdf import PdfReader
import csv,io
EXTRACTOR_VERSION="pdf-tables-ocr-tsv-v3"


def index(directory='data_alfbnk'):
    root = Path(directory)
    for pdf in root.glob('*.pdf'):
        if pdf.stat().st_size>50_000_000:raise ValueError('PDF exceeds 50 MB indexing limit')
        checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
        target = pdf.with_suffix('.pages.json')
        if target.exists() and json.loads(target.read_text()).get('checksum') == checksum and json.loads(target.read_text()).get('extractor_version')==EXTRACTOR_VERSION:
            print(pdf.name, 'unchanged', flush=True)
            continue
        pages = []
        reader = PdfReader(pdf)
        if len(reader.pages)>200:raise ValueError('PDF page limit exceeded')
        try:
            import pdfplumber
            table_reader=pdfplumber.open(pdf)
        except ImportError:table_reader=None
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or '').strip()
            method = 'text';confidence=1.;tables=[]
            if table_reader:
                tables=table_reader.pages[number-1].extract_tables()
                if tables:text+='\n'+json.dumps(tables,ensure_ascii=False)
            if len(text) < 50:
                with tempfile.TemporaryDirectory() as temp:
                    prefix = str(Path(temp)/'page')
                    subprocess.run(['pdftoppm','-f',str(number),'-l',str(number),'-scale-to','1800','-png','-singlefile',str(pdf),prefix], check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    tsv=subprocess.check_output(['tesseract',prefix+'.png','stdout','-l','rus+eng','tsv'],timeout=90,stderr=subprocess.DEVNULL).decode()
                    words=[r for r in csv.DictReader(io.StringIO(tsv),delimiter='\t') if r.get('text','').strip() and float(r.get('conf','-1'))>=0]
                    text=' '.join(w['text'] for w in words)
                    confidence=sum(float(w['conf']) for w in words)/max(len(words),1)/100
                    method = 'ocr'
            pages.append({'page':number,'text':text,'extraction_method':method,'confidence':confidence,'tables':tables})
        if table_reader:table_reader.close()
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'checksum':checksum,'pages':pages,'extractor_version':EXTRACTOR_VERSION},ensure_ascii=False))
        os.replace(temporary,target)
        print(pdf.name,'pages',len(pages),'characters',sum(len(p['text']) for p in pages),flush=True)

if __name__ == '__main__':
    index()
