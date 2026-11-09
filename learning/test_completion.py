import io
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from fastapi.testclient import TestClient
from ai_service.main import app
from learning.models import Material, Profile
from integrations.geometry_extraction import entity_id, extract_document, graph_for_concept, make_extractor


class ContentReviewTests(TestCase):
    def setUp(self):
        self.teacher=User.objects.create_user('review_teacher')
        Profile.objects.create(user=self.teacher,role='educator')
        self.student=User.objects.create_user('review_student')
        Profile.objects.create(user=self.student,role='student')
        self.client=APIClient()
        self.material=Material.objects.create(id='g8-review',title='Pythagore',text='Tam giác vuông',topic='Hình học',kind='general',status='Đã xuất bản',corpus_metadata={'review_status':'cho-giao-vien-duyet'})

    def test_student_cannot_approve_content(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post('/api/v1/materials/g8-review/review/',{'approved':True},format='json').status_code,403)

    def test_teacher_review_and_edit_invalidate_old_approval(self):
        self.client.force_authenticate(self.teacher)
        response=self.client.post('/api/v1/materials/g8-review/review/',{'approved':True},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['corpus_metadata']['review_status'],'approved')
        response=self.client.patch('/api/v1/materials/g8-review/',{'text':'Bản sửa cần rà lại'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['corpus_metadata']['review_status'],'cho-giao-vien-duyet')

    def test_teacher_cannot_approve_another_teachers_private_material(self):
        self.material.owner=self.student;self.material.save()
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post('/api/v1/materials/g8-review/review/',{'approved':True},format='json').status_code,403)


class ExtractionTests(TestCase):
    def setUp(self):
        self.material=Material.objects.create(id='g6-extraction',title='Hình chữ nhật',text='Diện tích bằng tích hai cạnh.',formula='S=ab',topic='Hình học',status='Đã xuất bản')

    def extracted_node(self,evidence):
        from llama_index.core.graph_stores.types import KG_NODES_KEY,KG_RELATIONS_KEY
        return SimpleNamespace(metadata={
            KG_NODES_KEY:[SimpleNamespace(id='a',label='CONCEPT',name='Hình chữ nhật'),SimpleNamespace(id='b',label='FORMULA',name='S=ab')],
            KG_RELATIONS_KEY:[SimpleNamespace(source_id='a',target_id='b',label='HAS_FORMULA',properties={'evidence':evidence})],
        })

    def test_extraction_requires_a_verbatim_source_passage(self):
        extractor=MagicMock(return_value=[self.extracted_node('Công thức đúng cho mọi tứ giác')])
        with self.assertRaises(ValueError):
            extract_document(extractor,self.material,self.material.text)

    def test_extraction_preserves_evidence_and_stable_entity_identity(self):
        extractor=MagicMock(return_value=[self.extracted_node(self.material.text)])
        result=extract_document(extractor,self.material,self.material.text)
        self.assertEqual(result['edges'][0]['evidence'],self.material.text)
        self.assertEqual(entity_id('CONCEPT','Hình  chữ nhật'),entity_id('CONCEPT','HÌNH CHỮ NHẬT'))

    def test_unknown_latex_escape_is_repaired_but_evidence_stays_exact(self):
        import os
        from pydantic import ValidationError
        with patch.dict(os.environ,{'CONTENT_PROVIDER':'openai','OPENAI_MODEL':'test-model','OPENAI_API_KEY':'fixture-key','OPENAI_BASE_URL':'http://localhost/v1'}):
            real=make_extractor()
        raw=r'{"triplets":[{"subject":{"type":"THEOREM","name":"Góc vuông"},"relation":{"type":"HAS_FORMULA","properties":{"evidence":"Công thức \hat{A}=90"}},"object":{"type":"FORMULA","name":"A = 90"}}]}'
        try:
            real.kg_schema_cls.model_validate_json(raw)
        except ValidationError as exc:
            extractor=MagicMock(side_effect=exc)
        extractor.kg_schema_cls=real.kg_schema_cls
        extractor._prune_invalid_triplets=real._prune_invalid_triplets
        text=r'Công thức \hat{A}=90'
        result=extract_document(extractor,self.material,text)
        self.assertEqual(result['edges'][0]['evidence'],text)

    def test_empty_model_response_is_not_repaired_into_a_graph(self):
        from pydantic import BaseModel, ValidationError
        class Payload(BaseModel):
            triplets:list
        try:
            Payload.model_validate_json('')
        except ValidationError as exc:
            extractor=MagicMock(side_effect=exc)
        with self.assertRaises(ValidationError):
            extract_document(extractor,self.material,self.material.text)

    def test_changed_source_hides_stale_extracted_evidence(self):
        driver=MagicMock()
        driver.session.return_value.__enter__.return_value.run.return_value.single.return_value={'hash':'old-source'}
        graph=graph_for_concept(driver,self.material.pk)
        self.assertTrue(graph['stale'])
        self.assertEqual(graph['nodes'],[])
        self.assertEqual(graph['edges'],[])

    def test_resume_reuses_cached_extraction_without_another_model_call(self):
        result={'concept_id':self.material.pk,'nodes':[],'edges':[{'source':'a','target':'b','type':'HAS_FORMULA','evidence':self.material.text}]}
        with tempfile.TemporaryDirectory() as temp, override_settings(BASE_DIR=Path(temp)), \
             patch('learning.management.commands.extract_geometry_graph.make_extractor'), \
             patch('learning.management.commands.extract_geometry_graph.load_source'), \
             patch('learning.management.commands.extract_geometry_graph.extract_document',return_value=result) as extract, \
             patch('learning.management.commands.extract_geometry_graph.write_document'), \
             patch('neo4j.GraphDatabase.driver'):
            for _ in range(2):
                call_command('extract_geometry_graph',stdout=io.StringIO())
            self.assertEqual(extract.call_count,1)


class ReadinessPermissionsTests(TransactionTestCase):
    def setUp(self):
        self.student=User.objects.create_user('health_student')
        Profile.objects.create(user=self.student,role='student')
        self.headers={'Authorization':'Token '+Token.objects.create(user=self.student).key}
        self.ai=TestClient(app)

    def test_student_cannot_probe_server_configuration(self):
        with patch('integrations.service_checks.check_services') as probe:
            response=self.ai.post('/api/v1/system/check',headers=self.headers)
        self.assertEqual(response.status_code,403)
        probe.assert_not_called()

    def test_extracted_graph_rejects_unpublished_lesson_before_database_call(self):
        Material.objects.create(id='private-graph',title='Nháp',text='Nháp',topic='Hình học')
        with patch('integrations.geometry_extraction.graph_for_concept') as graph:
            response=self.ai.get('/api/v1/rag/graph?concept_id=private-graph',headers=self.headers)
        self.assertEqual(response.status_code,404)
        graph.assert_not_called()
