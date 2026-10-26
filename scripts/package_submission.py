"""Package only explicitly supplied PDFs and their matching OCR, never arbitrary folders."""
import argparse, hashlib, json, tarfile, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('pdf_directory', type=Path);p.add_argument('output',type=Path);a=p.parse_args()
files=[];manifest=[]
for pdf in sorted(a.pdf_directory.glob('*.pdf')):
    checksum=hashlib.sha256(pdf.read_bytes()).hexdigest()
    sidecar=pdf.with_suffix('.pages.json')
    if not sidecar.exists():raise SystemExit('Missing OCR sidecar: '+pdf.name)
    cache=json.loads(sidecar.read_text())
    if cache.get('checksum')!=checksum:raise SystemExit('OCR checksum mismatch: '+pdf.name)
    manifest.append({'filename':pdf.name,'sha256':checksum,'bytes':pdf.stat().st_size,'pages':len(cache['pages']),'ocr_sha256':hashlib.sha256(sidecar.read_bytes()).hexdigest(),'extractor_version':cache.get('extractor_version','legacy')})
    files.extend([pdf,sidecar])
if not files:raise SystemExit('No reports: a bank-material submission cannot be claimed')
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'MANIFEST.json';path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(a.output,'w:gz') as archive:
        for item in files:archive.add(item,arcname='data_alfbnk/'+item.name,recursive=False)
        archive.add(path,arcname='data_alfbnk/MANIFEST.json')
print(json.dumps({'reports':len(manifest),'archive':str(a.output),'bytes':a.output.stat().st_size,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()},indent=2))
