from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import KnowledgeGap, Material, DailyUsage, SystemConfig
import os


def record_gap(user, concept):
    if not Material.objects.filter(pk=concept, status='Đã xuất bản').exists():
        return
    gap, _ = KnowledgeGap.objects.get_or_create(user=user, concept_id=concept)
    KnowledgeGap.objects.filter(pk=gap.pk).update(errors=F('errors')+1, resolved=False, updated=timezone.now())


def reserve_generation():
    # Reserve atomically before calling a paid provider, including failed calls.
    with transaction.atomic():
        config = SystemConfig.objects.filter(key='gemini_daily_limit').first()
        limit = int(config.value) if config else int(os.getenv('GEMINI_DAILY_LIMIT','100'))
        usage, _ = DailyUsage.objects.get_or_create(date=timezone.localdate())
        if not DailyUsage.objects.filter(pk=usage.pk, calls__lt=limit).update(calls=F('calls')+1):
            from rest_framework.exceptions import Throttled
            raise Throttled(detail='Đã đạt hạn mức sinh học liệu hôm nay.')
