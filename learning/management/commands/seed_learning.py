import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from learning.models import Material, Prerequisite, Quiz

class Command(BaseCommand):
    help='Thêm học liệu và quiz biên soạn sẵn; không ghi đè nội dung đã sửa hoặc tạo tài khoản.'
    @transaction.atomic
    def handle(self,*args,**kwargs):
        data=json.loads((Path(__file__).resolve().parents[2]/'seed.json').read_text())
        for lesson in data['lessons']:
            values={k:v for k,v in lesson.items() if k not in ('id','level')}
            values['status']='Đã xuất bản'
            Material.objects.get_or_create(pk=lesson['id'],defaults=values)
        for a,b in data['prerequisites']: Prerequisite.objects.get_or_create(source_id=a,target_id=b)
        for kind,questions in data['quizSets'].items():
            if not Quiz.objects.filter(kind=kind,source='curated',user__isnull=True).exists(): Quiz.objects.create(kind=kind,questions=questions,source='curated')
        self.stdout.write(self.style.SUCCESS('Đã thêm học liệu, quan hệ và quiz mẫu.'))
