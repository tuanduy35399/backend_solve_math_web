import uuid
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.throttling import ScopedRateThrottle
from .models import Profile, LearningSession, Material, Prerequisite, KnowledgeGap, Quiz, QuizAttempt, Story, ResearchReport, SystemConfig, TrainingRun
from .serializers import Registration, StoryPayload, MaterialSerializer, SessionSerializer, AttemptSerializer, TrainingSerializer, profile_data
from .permissions import role, MaterialAccess, EducatorOnly, AdminOnly
from .services import record_gap

class AuthThrottle(ScopedRateThrottle):
    scope = 'auth'
    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}
    def allow_request(self, request, view):
        self.rate = '10/min'
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super(ScopedRateThrottle, self).allow_request(request, view)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register(request):
    data = Registration(data=request.data)
    data.is_valid(raise_exception=True)
    values = data.validated_data
    if any(k not in ('username','password','name','email','grade') for k in request.data):
        raise ValidationError('Đăng ký công khai chỉ tạo tài khoản học sinh.')
    with transaction.atomic():
        user = User.objects.create_user(username=values['username'], password=values['password'], first_name=values['name'], email=values.get('email',''))
        Profile.objects.create(user=user, grade=values['grade'])
        token = Token.objects.create(user=user)
    return Response({'token': token.key, 'profile': profile_data(user)}, status=201)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
    if not user: return Response({'detail':'Tên đăng nhập hoặc mật khẩu không đúng.'}, status=400)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token':token.key, 'profile':profile_data(user)})

@api_view(['POST'])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=204)

@api_view(['GET','PATCH'])
def me(request):
    if request.method == 'PATCH':
        if set(request.data) - {'name','email','grade'}: raise ValidationError('Không thể đổi vai trò qua hồ sơ cá nhân.')
        class Fields(serializers.Serializer):
            name = serializers.CharField(max_length=60, required=False)
            email = serializers.EmailField(required=False, allow_blank=True)
            grade = serializers.IntegerField(min_value=6, max_value=12, required=False)
        fields = Fields(data=request.data); fields.is_valid(raise_exception=True)
        data = fields.validated_data
        with transaction.atomic():
            if 'name' in data: request.user.first_name = data['name']
            if 'email' in data: request.user.email = data['email']
            request.user.save()
            profile, _ = Profile.objects.get_or_create(user=request.user)
            if 'grade' in data: profile.grade = data['grade']; profile.save()
    return Response(profile_data(request.user))

@api_view(['GET','PATCH'])
@permission_classes([AdminOnly])
def users(request):
    if request.method == 'PATCH':
        class Change(serializers.Serializer):
            id = serializers.IntegerField()
            role = serializers.ChoiceField(choices=['student','educator','admin'], required=False)
            active = serializers.BooleanField(required=False)
        fields=Change(data=request.data);fields.is_valid(raise_exception=True);data=fields.validated_data
        try: user=User.objects.get(pk=data['id'])
        except User.DoesNotExist: raise ValidationError('Tài khoản không tồn tại.')
        if user == request.user or user.is_superuser: raise ValidationError('Không thay đổi tài khoản quản trị đang dùng hoặc superuser tại đây.')
        with transaction.atomic():
            profile,_=Profile.objects.get_or_create(user=user)
            if 'role' in data: profile.role=data['role'];profile.save()
            if 'active' in data: user.is_active=data['active'];user.save()
            Token.objects.filter(user=user).delete()
    return Response([profile_data(u) for u in User.objects.order_by('id')])

class MaterialViewSet(viewsets.ModelViewSet):
    serializer_class = MaterialSerializer
    permission_classes = [MaterialAccess]
    def get_queryset(self):
        qs=Material.objects.order_by('title')
        if role(self.request.user)=='student': qs=qs.filter(status='Đã xuất bản')
        elif role(self.request.user)=='educator':
            from django.db.models import Q
            qs=qs.filter(Q(status='Đã xuất bản')|Q(owner=self.request.user))
        return qs
    def perform_create(self, serializer): serializer.save(owner=self.request.user)
    def perform_update(self, serializer):
        if 'id' in serializer.validated_data and serializer.validated_data['id'] != serializer.instance.pk:
            raise ValidationError('Không đổi mã học liệu đã tạo.')
        serializer.save()

class SessionViewSet(viewsets.ModelViewSet):
    serializer_class = SessionSerializer
    http_method_names = ['get','patch','delete','head','options']
    def get_queryset(self): return LearningSession.objects.filter(user=self.request.user).order_by('-created_at')
    def partial_update(self, request, *args, **kwargs):
        if set(request.data) != {'title'}: raise ValidationError('Chỉ được sửa tên phiên học.')
        return super().partial_update(request,*args,**kwargs)

@api_view(['GET','POST','DELETE'])
def edges(request):
    if request.method != 'GET' and role(request.user) not in ('educator','admin'): raise PermissionDenied()
    if request.method != 'GET':
        source=request.data.get('source');target=request.data.get('target')
        if not Material.objects.filter(pk=source).exists() or not Material.objects.filter(pk=target).exists(): raise ValidationError('Kiến thức không tồn tại.')
        if request.method=='POST':
            with transaction.atomic():
                pairs=list(Prerequisite.objects.values_list('source_id','target_id'))
                def reaches(a,b,seen=None):
                    seen=set() if seen is None else seen
                    if a==b: return True
                    if a in seen: return False
                    seen.add(a)
                    return any(reaches(y,b,seen) for x,y in pairs if x==a)
                if source==target or reaches(target,source): raise ValidationError('Quan hệ tạo vòng lặp tiên quyết.')
                if (source,target) in pairs: raise ValidationError('Quan hệ đã tồn tại.')
                Prerequisite.objects.create(source_id=source,target_id=target)
        else: Prerequisite.objects.filter(source_id=source,target_id=target).delete()
    qs=Prerequisite.objects.all()
    if role(request.user)=='student': qs=qs.filter(source__status='Đã xuất bản',target__status='Đã xuất bản')
    return Response(list(qs.values_list('source_id','target_id')))

@api_view(['GET'])
def gaps(request):
    return Response([{'concept':g.concept_id,'errors':g.errors,'resolved':g.resolved,'date':g.updated.isoformat()} for g in KnowledgeGap.objects.filter(user=request.user)])

@api_view(['GET'])
def attempts(request):
    return Response(AttemptSerializer(QuizAttempt.objects.filter(user=request.user).select_related('quiz').order_by('-created_at'),many=True).data)

@api_view(['GET'])
def quiz_detail(request, pk):
    from django.db.models import Q
    quiz=Quiz.objects.filter(Q(user=request.user)|Q(user__isnull=True),pk=pk).first()
    if not quiz: return Response(status=404)
    return Response({'id':str(quiz.pk),'kind':quiz.kind,'summary':quiz.summary,'source':quiz.source,'exercises':quiz.exercises,'contexts':quiz.contexts,
                     'questions':[{k:v for k,v in q.items() if k not in ('correct','explanation')} for q in quiz.questions]})

@api_view(['POST'])
def submit_quiz(request, pk):
    from django.db.models import Q
    quiz=Quiz.objects.filter(Q(user=request.user)|Q(user__isnull=True),pk=pk).first()
    if not quiz: return Response(status=404)
    answers=request.data.get('answers');seconds=request.data.get('seconds',0)
    if not isinstance(answers,list) or len(answers)!=len(quiz.questions): raise ValidationError('Trả lời đầy đủ các câu hỏi.')
    if not isinstance(seconds,int) or isinstance(seconds,bool) or not 0<=seconds<=86400: raise ValidationError('Thời gian không hợp lệ.')
    if any(type(a) is not int or not 0<=a<len(q['options']) for a,q in zip(answers,quiz.questions)): raise ValidationError('Đáp án không hợp lệ.')
    missed={q['concept'] for a,q in zip(answers,quiz.questions) if a!=q['correct']}
    mastered={q['concept'] for a,q in zip(answers,quiz.questions) if a==q['correct']} - missed
    with transaction.atomic():
        attempt=QuizAttempt.objects.create(user=request.user,quiz=quiz,answers=answers,score=sum(a==q['correct'] for a,q in zip(answers,quiz.questions)),seconds=seconds)
        for concept in missed: record_gap(request.user,concept)
        KnowledgeGap.objects.filter(user=request.user,concept_id__in=mastered).update(resolved=True,updated=timezone.now())
    return Response({'result':AttemptSerializer(attempt).data,'questions':quiz.questions})

@api_view(['GET'])
@permission_classes([EducatorOnly])
def statistics(request):
    return Response({'students':Profile.objects.filter(role='student',user__is_superuser=False).count(), 'sessions':LearningSession.objects.count(),
                     'attempts':QuizAttempt.objects.count(),'gaps':list(KnowledgeGap.objects.filter(resolved=False).values('concept_id','concept__title').annotate(students=Count('user',distinct=True),errors=Sum('errors')))})

@api_view(['GET','POST','DELETE'])
def stories(request):
    from django.db.models import Q
    if request.method!='GET':
        if role(request.user) not in ('educator','admin'): raise PermissionDenied()
        data=request.data;pk=data.get('id')
        if not isinstance(pk,str) or not pk.startswith('bai-viet-') or len(pk)>80: raise ValidationError('Mã bài viết không hợp lệ.')
        existing=Story.objects.filter(pk=pk).first()
        if existing and existing.owner_id!=request.user.id and role(request.user)!='admin': raise PermissionDenied()
        if request.method=='DELETE':
            if existing: existing.delete()
        else:
            checked=StoryPayload(data=data);checked.is_valid(raise_exception=True);data=checked.validated_data
            if len(str(data))>80000: raise ValidationError('Bài viết quá dài.')
            owner=existing.owner if existing else request.user
            safe={**data,'authorId':str(owner.id),'authorName':owner.first_name or owner.username,'custom':True}
            Story.objects.update_or_create(pk=pk,defaults={'owner':owner,'status':data['status'],'data':safe})
    qs=Story.objects.all()
    if role(request.user)!='admin': qs=qs.filter(Q(status='published')|Q(owner=request.user))
    return Response([s.data for s in qs])

@api_view(['GET'])
@permission_classes([EducatorOnly])
def reports(request):
    qs=ResearchReport.objects.all() if role(request.user)=='admin' else ResearchReport.objects.filter(owner=request.user)
    return Response([{'id':str(r.pk),'title':r.material.title,'content':r.content,'sources':r.sources,'date':r.created_at.isoformat()} for r in qs.select_related('material').order_by('-created_at')])

@api_view(['DELETE'])
def clear_learning(request):
    with transaction.atomic():
        LearningSession.objects.filter(user=request.user).delete()
        QuizAttempt.objects.filter(user=request.user).delete()
        Quiz.objects.filter(user=request.user).delete()
        KnowledgeGap.objects.filter(user=request.user).delete()
    return Response(status=204)

@api_view(['GET','PATCH'])
@permission_classes([AdminOnly])
def configuration(request):
    if request.method=='PATCH':
        limit=request.data.get('gemini_daily_limit')
        if type(limit) is not int or not 0<=limit<=10000: raise ValidationError('Hạn mức từ 0 đến 10.000.')
        SystemConfig.objects.update_or_create(key='gemini_daily_limit',defaults={'value':limit})
    import os
    obj=SystemConfig.objects.filter(key='gemini_daily_limit').first()
    return Response({'gemini_daily_limit': obj.value if obj else int(os.getenv('GEMINI_DAILY_LIMIT','100'))})

class TrainingViewSet(viewsets.ModelViewSet):
    permission_classes=[AdminOnly]
    serializer_class=TrainingSerializer
    queryset=TrainingRun.objects.order_by('-created_at')
    http_method_names=['get','post','delete','head','options']
    def perform_create(self,serializer): serializer.save(owner=self.request.user)

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request): return Response({'status':'ok','service':'django-rest'})

@api_view(['GET'])
def quizzes(request):
    from django.db.models import Q
    qs=Quiz.objects.filter(Q(user=request.user)|Q(user__isnull=True)).order_by('-created_at')
    return Response([{'id':str(q.pk),'kind':q.kind,'source':q.source,'summary':q.summary} for q in qs])
