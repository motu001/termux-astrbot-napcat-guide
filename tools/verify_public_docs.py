"""Read-only checks for public tutorial source. No network or device access.
Run: python tools/verify_public_docs.py
Pattern checks are a safety net, not a substitute for human privacy review.
"""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
TEXT = {'.md', '.py', '.json', '.sh', '.txt', '.srt', '.frag', '.vert'}
SECRET = re.compile(r'\bsk-[A-Za-z0-9_-]{24,}|\bAIza[A-Za-z0-9_-]{30,}')
PRIVATE_IP = re.compile(r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b')
LINK = re.compile(r'\[[^\]\n]*\]\(([^)\n]+)\)')

def validate(root=ROOT):
    errors=[]; count=0; links=0
    # Validate tracked/public text, never descend into Git internals or generated media.
    for path in sorted(root.rglob('*')):
        if not path.is_file(): continue
        rel=path.relative_to(root)
        if any(part in {'.git','__pycache__','node_modules','.venv','audio','clips','cards','qa','06_成片'} for part in rel.parts):continue
        if path.suffix not in TEXT:continue
        try:text=path.read_text(encoding='utf-8-sig')
        except UnicodeError:
            errors.append(f'{rel}: invalid UTF-8');continue
        count+=1
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',text):errors.append(f'{rel}: control character')
        if SECRET.search(text):errors.append(f'{rel}: possible credential; inspect privately')
        if PRIVATE_IP.search(text):errors.append(f'{rel}: non-loopback private IP; sanitize before publication')
        if re.search(r'[A-Za-z]:[\\/]Users[\\/][^/\\\s\"\']+',text):errors.append(f'{rel}: user-specific absolute path')
        if path.suffix=='.md':
            fence=None
            for line in text.splitlines():
                match=re.match(r'^\s{0,3}(`{3,}|~{3,})',line)
                if match:
                    marker=match.group(1)
                    if fence is None:fence=marker[0]
                    elif marker[0]==fence:fence=None
            if fence:errors.append(f'{rel}: unclosed code fence')
            for target in LINK.findall(text):
                target=target.strip().split(' "',1)[0].strip('<>')
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'):continue
                target=unquote(target.split('#',1)[0])
                if not target:continue
                links+=1
                resolved=(path.parent/target).resolve()
                if not resolved.is_relative_to(root.resolve()):errors.append(f'{rel}: link leaves public repository')
                elif not resolved.exists():errors.append(f'{rel}: broken local link: {target}')
        elif path.suffix=='.json':
            try:json.loads(text)
            except json.JSONDecodeError:errors.append(f'{rel}: invalid JSON')
    return {'text_files':count,'local_links':links,'errors':errors,'passed':not errors}

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    report=validate();print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(0 if report['passed'] else 1)
