import uuid
from django.conf import settings
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=12, choices=[('student','Học sinh'),('educator','Giáo viên'),('admin','Quản trị viên')], default='student')
    grade = models.PositiveSmallIntegerField(default=9)

class LearningSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=140)
    kind = models.CharField(max_length=16, default='triangle')
    params = models.JSONField(default=dict)
    photo = models.JSONField(null=True, blank=True)
    messages = models.JSONField(default=list)
    completed = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Material(models.Model):
    id = models.SlugField(primary_key=True, max_length=80, default=uuid.uuid4)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=140)
    text = models.TextField(max_length=6000)
    formula = models.CharField(max_length=500, blank=True)
    note = models.TextField(max_length=1500, blank=True)
    topic = models.CharField(max_length=80)
    grade = models.PositiveSmallIntegerField(default=9)
    kind = models.CharField(max_length=16, default='triangle')
    minutes = models.PositiveSmallIntegerField(default=5)
    status = models.CharField(max_length=24, choices=[('Bản nháp','Bản nháp'),('Đã xuất bản','Đã xuất bản')], default='Bản nháp')
    source = models.CharField(max_length=500, blank=True)
    corpus_metadata = models.JSONField(default=dict, blank=True)
    updated = models.DateTimeField(auto_now=True)

class Prerequisite(models.Model):
    source = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='unlocks')
    target = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='requires')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','target'], name='unique_prerequisite')]

class KnowledgeGap(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    concept = models.ForeignKey(Material, on_delete=models.CASCADE)
    errors = models.PositiveIntegerField(default=0)
    resolved = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','concept'], name='unique_student_gap')]

class Quiz(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    kind = models.CharField(max_length=16)
    summary = models.TextField(blank=True)
    questions = models.JSONField(default=list)
    exercises = models.JSONField(default=list)
    source = models.CharField(max_length=32, default='curated')  # curated | gemini/openai (personal AI) | assignment
    contexts = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    # Teacher assignments: drafted and reviewed by the author (user), then published to students of `grade`.
    title = models.CharField(max_length=140, blank=True)
    status = models.CharField(max_length=12, choices=[('draft','draft'),('published','published')], default='published')
    grade = models.PositiveSmallIntegerField(null=True, blank=True)
    material = models.ForeignKey(Material, null=True, blank=True, on_delete=models.SET_NULL, related_name='assignments')
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

class QuizAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    answers = models.JSONField()
    score = models.PositiveSmallIntegerField()
    seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Story(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=12, choices=[('draft','draft'),('published','published')], default='draft')
    data = models.JSONField(default=dict)

class ResearchReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    content = models.TextField()
    sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

class SystemConfig(models.Model):
    key = models.CharField(primary_key=True, max_length=40)
    value = models.JSONField(default=dict)

class DailyUsage(models.Model):
    date = models.DateField(unique=True)
    calls = models.PositiveIntegerField(default=0)

class TrainingRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    method = models.CharField(max_length=32, choices=[('lora','LoRA'),('kd','Knowledge Distillation'),('grpo','GRPO')])
    checkpoint = models.CharField(max_length=500)
    metrics = models.JSONField(default=dict)
    note = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

class LearningReport(models.Model):
    """AI-written overview of class learning status for teachers (aggregated, no student names sent to the model)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    focus = models.JSONField(default=list)
    snapshot = models.JSONField(default=dict)
    source = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
