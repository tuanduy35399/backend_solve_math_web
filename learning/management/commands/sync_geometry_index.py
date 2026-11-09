import json
import os
from pathlib import Path
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from integrations.geometry_rag import close_resources, resources, retrieve, sync_corpus
from learning.models import Material, Prerequisite


class Command(BaseCommand):
    help = 'Đồng bộ học liệu đã xuất bản sang BGE-M3/Chroma và Neo4j.'

    def add_arguments(self, parser):
        parser.add_argument('--verify', action='store_true')
        parser.add_argument('--report', default='data/index-build-report.json')

    def handle(self, *args, **options):
        try:
            result = sync_corpus(progress=self.stdout.write)
            if options['verify']:
                result['verification'] = self.verify_index()
            result['completed_at'] = datetime.now(timezone.utc).isoformat()
            report = Path(options['report'])
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
            self.stdout.write(self.style.SUCCESS(json.dumps(result, ensure_ascii=False)))
        finally:
            close_resources()

    def verify_index(self):
        _, store, driver, _ = resources()
        ids = set(Material.objects.filter(status='Đã xuất bản').values_list('id', flat=True))
        edges = set(Prerequisite.objects.filter(source_id__in=ids, target_id__in=ids).values_list('source_id', 'target_id'))
        if set(store.collection.get()['ids']) != ids:
            raise ValueError('Chroma không khớp danh sách học liệu đã xuất bản.')
        with driver.session(database=os.getenv('NEO4J_DATABASE', 'neo4j')) as session:
            graph_ids = {r['id'] for r in session.run('MATCH (n:MindGeoConcept) RETURN n.id AS id')}
            graph_edges = {(r['source'], r['target']) for r in session.run('MATCH (a:MindGeoConcept)-[:PREREQUISITE_OF]->(b:MindGeoConcept) RETURN a.id AS source,b.id AS target')}
        if graph_ids != ids or graph_edges != edges:
            raise ValueError('Neo4j không khớp nút/cạnh trong Django.')
        samples = []
        for pk in ['g6-trung-diem', 'g7-tam-giac-can', 'g8-pythagore', 'g9-tiep-tuyen']:
            context = retrieve(pk)
            direct = {a for a,b in edges if b == pk}
            found = {p['id'] for p in context['prerequisites']}
            if not direct.issubset(found) or not context['contexts']:
                raise ValueError(f'Truy xuất thiếu kiến thức nền: {pk}')
            if any(c['concept_id'] not in ids or not c['source'] for c in context['contexts']):
                raise ValueError(f'Truy xuất mất nguồn hoặc sai mã: {pk}')
            samples.append({'concept_id':pk, 'prerequisites':len(found), 'contexts':len(context['contexts']), 'channels':context['channels']})
            self.stdout.write(f'PASS truy xuất thật: {pk}')
        vector = store.collection.get(ids=[sorted(ids)[0]], include=['embeddings'])['embeddings'][0]
        return {'status':'passed', 'neo4j_nodes':len(graph_ids), 'neo4j_edges':len(graph_edges),
                'chroma_documents':len(ids), 'vector_dimension':len(vector), 'samples':samples}
