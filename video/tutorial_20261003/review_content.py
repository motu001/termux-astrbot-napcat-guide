"""No-network content gate before a paid TTS batch."""
from pathlib import Path
import importlib.util,json,re,sys
BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('b',BASE/'build_video.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def check():
    data=b.scenes();items=data['scenes'];errors=[];warnings=[];counts={}
    titles={c['id']:c['title'] for c in data['chapters']}
    if len(items)<80:errors.append('Full tutorial has fewer than 80 teaching units')
    text_length=sum(len(s['speech']) for s in items)
    if text_length<6500:errors.append('Narration is too short for the requested detailed coverage')
    for s in items:
        sid=s['id'];counts[s['chapter']]=counts.get(s['chapter'],0)+1
        if s['chapter_title']!=titles.get(s['chapter']):errors.append(sid+': inconsistent chapter title')
        if len(s.get('code',[]))>7:errors.append(sid+': more than 7 screen code lines')
        if len(s['title'])>22:warnings.append(sid+': long title')
        if ''.join(b.caption_chunks(s['speech']))!=s['speech']:errors.append(sid+': subtitle text lost')
        for code in s.get('code',[]):
            if re.search(r'curl\b.*\|\s*(?:bash|sh)\b',code):errors.append(sid+': blindly piped network installer')
            if re.search(r'\b(?:docker|podman)\s+run\b',code):errors.append(sid+': inappropriate rootless PRoot container command')
            if len(code)>75:warnings.append(sid+': long command needs visual line wrapping')
        text=json.dumps(s,ensure_ascii=False)
        if re.search(r'\bsk-[A-Za-z0-9_-]{24,}|\b192\.168\.\d+\.\d+',text):errors.append(sid+': potential privacy issue')
    actual_chapters=[s['chapter'] for i,s in enumerate(items) if i==0 or s['chapter']!=items[i-1]['chapter']]
    if actual_chapters!=list(titles):errors.append('Chapter order is not contiguous or declared order differs')
    if set(counts)!=set(titles):errors.append('Empty or undeclared chapter')
    result={'scene_count':len(items),'chapter_count':len(titles),'narration_characters':text_length,
            'chapter_scene_counts':counts,'errors':errors,'warnings':warnings,'passed':not errors,
            'note':'Mechanical gate only; official command review and visual/audio review are separate.'}
    b.save_json(BASE/'content_gate.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));return not errors

if __name__=='__main__':raise SystemExit(0 if check() else 1)
