"""Import the audited Markdown corpus without overwriting existing teacher work."""
import io
import json
import re
from contextlib import redirect_stdout

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from learning.models import Material, Prerequisite
from scripts.validate_geometry_corpus import main as validate_corpus


class Command(BaseCommand):
    help = 'Nhập học liệu knowledge/; mặc định bản nháp, --publish để đưa vào RAG.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--publish', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        with redirect_stdout(io.StringIO()):
            validate_corpus()
        root = settings.BASE_DIR / 'knowledge'
        documents = json.loads((root / 'manifest.json').read_text())['documents']
        edges = {(p, d['id']) for d in documents for p in d['prerequisites']}
        pairs = edges | set(Prerequisite.objects.values_list('source_id', 'target_id'))
        children = {}
        for source, target in pairs:
            children.setdefault(source, []).append(target)
        visited, visiting = set(), set()

        def visit(node):
            if node in visiting:
                raise CommandError(f'Quan hệ mới tạo chu kỳ tại {node}; chưa nhập dữ liệu.')
            if node in visited:
                return
            visiting.add(node)
            for child in children.get(node, []):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in children:
            visit(node)
        created = skipped = 0
        for document in documents:
            raw = (root / document['file']).read_text()
            _, body = raw[4:].split('\n---\n', 1)
            parts = re.split(r'^## (.+)\n', body, flags=re.MULTILINE)
            sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}
            metadata = {**document, 'sections': sections}
            existing = Material.objects.filter(pk=document['id']).first()
            if existing:
                if existing.corpus_metadata.get('sha256') != document['sha256']:
                    raise CommandError(f"Mã {document['id']} đã có nội dung khác. Không ghi đè; giao dịch đã hủy.")
                if options['publish'] and existing.status != 'Đã xuất bản':
                    existing.status = 'Đã xuất bản'
                    existing.save(update_fields=['status', 'updated'])
                skipped += 1
                continue
            material = Material(
                id=document['id'], title=document['title'], grade=document['grade'],
                text=sections['Phát biểu và ý nghĩa'], formula=document['formula_latex'],
                note=sections['Điều kiện áp dụng'] + '\n' + sections['Lỗi thường gặp'],
                topic='Hình học phẳng', kind='general', minutes=5,
                status='Đã xuất bản' if options['publish'] else 'Bản nháp',
                source=document['source_reference'], corpus_metadata=metadata,
            )
            if any(word in document['id'] for word in ['hinh-hop', 'lap-phuong', 'lang-tru', 'chop-', 'hinh-tru', 'hinh-non', 'hinh-cau']):
                material.topic = 'Hình học không gian'
            material.full_clean(exclude=['owner'])  # System corpus has no individual owner.
            material.save()
            created += 1
        added_edges = 0
        for source, target in sorted(edges):
            _, added = Prerequisite.objects.get_or_create(source_id=source, target_id=target)
            added_edges += added
        if options['dry_run']:
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(
            f"{'DRY RUN' if options['dry_run'] else 'OK'}: {created} bài mới, {skipped} bài giữ nguyên, "
            f'{added_edges} cạnh mới. Trạng thái thẩm định nguồn được giữ nguyên.'
        ))
