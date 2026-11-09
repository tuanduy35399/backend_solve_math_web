import io
import os
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from learning.models import Material, Prerequisite
from learning.serializers import MaterialSerializer


class GeometryCorpusTests(TestCase):
    def test_disabled_rag_never_reuses_cached_resources(self):
        from integrations.geometry_rag import resources
        from ai_service.providers import ProviderUnavailable
        with patch('integrations.geometry_rag._resources', return_value='cached') as cached:
            with patch.dict(os.environ, {'RAG_ENABLED':'true'}):
                self.assertEqual(resources(), 'cached')
            with patch.dict(os.environ, {'RAG_ENABLED':'false'}):
                with self.assertRaises(ProviderUnavailable):
                    resources()
            self.assertEqual(cached.call_count, 1)

    def run_import(self, **kwargs):
        call_command('import_geometry_corpus', stdout=io.StringIO(), **kwargs)

    def test_dry_run_does_not_publish_or_persist(self):
        self.run_import(dry_run=True, publish=True)
        self.assertEqual(Material.objects.count(), 0)
        self.assertEqual(Prerequisite.objects.count(), 0)

    def test_import_is_repeatable_and_preserves_teacher_work(self):
        call_command('seed_learning', stdout=io.StringIO())
        self.run_import(publish=True)
        material = Material.objects.get(pk='g8-pythagore')
        self.assertEqual(material.kind, 'general')
        self.assertEqual(material.corpus_metadata['review_status'], 'cho-giao-vien-duyet')
        self.assertIn('Ví dụ tự biên soạn', material.corpus_metadata['sections'])
        material.note = 'Ghi chú giáo viên đã chỉnh'
        material.save()
        self.run_import(publish=True)
        material.refresh_from_db()
        self.assertEqual(material.note, 'Ghi chú giáo viên đã chỉnh')
        self.assertEqual(Material.objects.count(), 94)
        self.assertEqual(Prerequisite.objects.count(), 154)

    def test_collision_rolls_back_entire_import(self):
        Material.objects.create(id='g8-pythagore', title='Bài riêng', text='Không ghi đè', topic='Hình học')
        with self.assertRaises(CommandError):
            self.run_import(publish=True)
        self.assertEqual(Material.objects.count(), 1)
        self.assertEqual(Prerequisite.objects.count(), 0)

    def test_existing_edge_cannot_introduce_cycle_with_corpus(self):
        self.run_import()
        Prerequisite.objects.filter(source_id='g6-hinh-vuong-truc-quan', target_id='g8-pythagore').delete()
        Prerequisite.objects.create(source_id='g8-pythagore', target_id='g6-hinh-vuong-truc-quan')
        with self.assertRaises(CommandError):
            self.run_import(publish=True)
        self.assertFalse(Material.objects.filter(status='Đã xuất bản').exists())

    def test_general_material_is_valid_and_provenance_is_read_only(self):
        serializer = MaterialSerializer(data={
            'title':'Góc', 'text':'Hai tia chung gốc', 'topic':'Hình học phẳng',
            'grade':6, 'kind':'general', 'corpus_metadata':{'review_status':'approved'},
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        material = serializer.save()
        self.assertEqual(material.corpus_metadata, {})
