"""Validate corpus references and mathematical examples without provider or database calls."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]/'knowledge'

def numeric_examples():
    # Independent checks of the input/result pairs written in the worked examples.
    checks=[
        ('rectangle 11x6',2*(11+6),34),('rectangle area',11*6,66),
        ('parallelogram area',10*6,60),('rhombus area',12*16/2,96),
        ('trapezoid area',(7+13)*6/2,60),('triangle angles',180-52-61,67),
        ('isosceles angles',(180-44)/2,68),('centroid',15*2/3,10),
        ('cuboid volume',7*4*9,252),('cuboid lateral area',2*(7+4)*9,198),
        ('cube surface',6*4**2,96),('triangular prism volume',6*8/2*9,216),
        ('triangle area',9*4/2,18),('quadrilateral angles',360-78-96-104,82),
        ('Thales',4/10*15,6),('bisector BD',10*6/(6+9),4),
        ('Pythagoras',math.hypot(5,12),13),('Pythagoras inverse',8**2+15**2,17**2),
        ('triangle pyramid volume',27*8/3,72),('square pyramid volume',6**2*4/3,48),
        ('square pyramid slant height',math.hypot(6/2,4),5),('square pyramid lateral area',2*6*5,60),
        ('triangle trigonometry',14*math.sin(math.radians(30)),7),
        ('arc length divided by pi',80*9/180,4),('sector area divided by pi',150*6**2/360,15),
        ('annulus area divided by pi',10**2-6**2,64),('inscribed angle',118/2,59),
        ('circumradius rectangle',math.hypot(8,15)/2,8.5),('regular octagon internal angle',(8-2)*180/8,135),
        ('cylinder volume divided by pi',4**2*9,144),('cone slant height',math.hypot(5,12),13),
        ('cone volume divided by pi',5**2*12/3,100),('sphere volume divided by pi',4/3*6**3,288),
    ]
    for name,actual,expected in checks:
        if not math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10):raise ValueError(f'Worked example failed: {name}')
    return len(checks)

def main():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    documents=manifest['documents'];by_id={d['id']:d for d in documents}
    sources={s['id']:s for s in json.loads((ROOT/'sources.json').read_text())['sources']}
    if len(by_id)!=len(documents):raise ValueError('Duplicate concept IDs')
    if len(documents)!=manifest['document_count']:raise ValueError('Wrong document count')
    actual_files={p.resolve() for p in (ROOT/'markdown').rglob('*.md')}
    expected_files={(ROOT/d['file']).resolve() for d in documents}
    if actual_files!=expected_files:raise ValueError('Manifest does not match Markdown files')
    required_sections=['## Phát biểu và ý nghĩa','## Điều kiện áp dụng','## Công thức và ký hiệu','## Ví dụ tự biên soạn','## Lỗi thường gặp','## Câu hỏi gợi mở Socratic','## Kiến thức tiên quyết đề xuất','## Nguồn đối chiếu']
    for document in documents:
        path=ROOT/document['file'];text=path.read_text()
        if not text.startswith('---\n'):raise ValueError(f'Missing frontmatter: {path}')
        front,body=text[4:].split('\n---\n',1);metadata=json.loads(front)
        for key in ['id','grade','title','document_type','formula_latex','prerequisites','review_status','source_ids']:
            if metadata[key]!=document[key]:raise ValueError(f'Metadata mismatch: {document["id"]}/{key}')
        if document['grade'] not in (6,7,8,9):raise ValueError('Unexpected grade')
        if path.parent.name!=f"lop-{document['grade']}":raise ValueError('Wrong grade folder')
        if hashlib.sha256(text.encode()).hexdigest()!=document['sha256']:raise ValueError(f'Changed content hash: {path}')
        if not all(section in body for section in required_sections):raise ValueError(f'Incomplete lesson: {path}')
        if any(token in body for token in ['Quảng cáo','HOT Sale','[image:','Trang trước']):raise ValueError(f'Web boilerplate in lesson: {path}')
        if chr(92)*2 in document['formula_latex']:raise ValueError(f'Unexpected double-escaped LaTeX: {path}')
        if len(document['formula_latex'])>500:raise ValueError(f'Formula exceeds current Material limit: {path}')
        for sid in document['source_ids']:
            source=sources[sid]
            if source['http_status']!=200 or not source['url'].startswith('https://vietjack.com/'):raise ValueError(f'Unverified source: {sid}')
            if source['url'] not in body:raise ValueError(f'Missing source citation: {path}')
        for prerequisite in document['prerequisites']:
            other=by_id[prerequisite]
            if prerequisite==document['id'] or other['grade']>document['grade']:raise ValueError(f'Invalid prerequisite: {document["id"]}')
            expected=f"../lop-{other['grade']}/{Path(other['file']).name}"
            if f']({expected})' not in body or not (path.parent/unquote(expected)).is_file():raise ValueError(f'Broken lesson link: {path}')
    visited=set();visiting=set()
    def visit(pk):
        if pk in visiting:raise ValueError(f'Prerequisite cycle at {pk}')
        if pk in visited:return
        visiting.add(pk)
        for parent in by_id[pk]['prerequisites']:visit(parent)
        visiting.remove(pk);visited.add(pk)
    for pk in by_id:visit(pk)
    graph=json.loads((ROOT/'graph-proposal.json').read_text())
    expected_edges={(parent,d['id']) for d in documents for parent in d['prerequisites']}
    actual_edges={(e['source'],e['target']) for e in graph['edges']}
    if actual_edges!=expected_edges or len(actual_edges)!=len(graph['edges']):raise ValueError('Wrong or duplicate graph edges')
    if {n['id'] for n in graph['nodes']}!=set(by_id):raise ValueError('Wrong graph nodes')
    numeric_count=numeric_examples()
    counts=dict(sorted(Counter(d['grade'] for d in documents).items()))
    if {str(k):v for k,v in counts.items()}!=manifest['by_grade']:raise ValueError('Wrong per-grade counts')
    print(f"PASS: {len(documents)} lessons, {len(sources)} verified source records, {len(expected_edges)} acyclic prerequisite edges.")
    print(f"PASS: {numeric_count} numerical worked-example checks; all Markdown links and content hashes match.")
    print('By grade:',counts)
    print('Teacher review remains pending; no database or provider was contacted.')

if __name__=='__main__':main()
