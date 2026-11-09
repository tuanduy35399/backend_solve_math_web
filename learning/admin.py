from django.contrib import admin
from .models import Profile, Material, Prerequisite, LearningSession, KnowledgeGap, Quiz, TrainingRun
for model in [Profile,Material,Prerequisite,LearningSession,KnowledgeGap,Quiz,TrainingRun]: admin.site.register(model)
