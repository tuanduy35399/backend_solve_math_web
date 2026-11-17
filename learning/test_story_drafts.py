from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from learning.models import Profile,Story


class StoryDraftValidationTests(TestCase):
    def setUp(self):
        teacher=User.objects.create_user('draft_teacher');Profile.objects.create(user=teacher,role='educator')
        self.client=APIClient();self.client.force_authenticate(teacher)
        self.payload={'id':'bai-viet-partial-source','status':'draft','kind':'discovery','title':'Nháp đang viết','paragraphs':['Nội dung đang viết'],'sources':[{'title':'Nguồn đang tìm','url':'','scope':''}]}

    def test_incomplete_source_is_preserved_in_a_draft(self):
        response=self.client.post('/api/v1/stories/',self.payload,format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(Story.objects.get(pk=self.payload['id']).data['sources'][0]['title'],'Nguồn đang tìm')

    def test_invalid_source_has_a_specific_nested_field_error(self):
        self.payload['sources'][0]['url']='not-a-url'
        response=self.client.post('/api/v1/stories/',self.payload,format='json')
        self.assertEqual(response.status_code,400)
        self.assertIn('url',response.data['sources'][0])
        self.assertFalse(Story.objects.exists())

    def test_publication_still_requires_every_source_to_be_complete(self):
        self.payload.update(status='published',theorem='Định lý',hook='Lời dẫn',topic='Hình học',insight='Ý tưởng',formula='a=b',condition='Điều kiện',evidence='Bằng chứng',question='Câu hỏi',answer='Lời giải')
        response=self.client.post('/api/v1/stories/',self.payload,format='json')
        self.assertEqual(response.status_code,400)
        self.assertIn('sources',response.data)
        self.assertFalse(Story.objects.exists())
