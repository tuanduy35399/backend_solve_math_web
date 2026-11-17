import uuid
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.throttling import ScopedRateThrottle
from .models import Profile, LearningSession, Material, Prerequisite, KnowledgeGap, Quiz, QuizAttempt, Story, ResearchReport, SystemConfig, TrainingRun, LearningReport
from .serializers import Registration, StoryPayload, AssignmentPayload, MaterialSerializer, SessionSerializer, AttemptSerializer, TrainingSerializer, profile_data
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
        qs=Material.objects.order_by('title','pk')
        if role(self.request.user)=='student': qs=qs.filter(status='Đã xuất bản')
        elif role(self.request.user)=='educator':
            from django.db.models import Q
            qs=qs.filter(Q(status='Đã xuất bản')|Q(owner=self.request.user))
        return qs
    def list(self, request, *args, **kwargs):
        from .serializers import MaterialOverviewSerializer, MaterialListSerializer
        from rest_framework.pagination import PageNumberPagination
        from django.db.models import Q
        qs=self.get_queryset()
        if request.query_params.get('brief')=='1':
            return Response(MaterialOverviewSerializer(qs.defer('corpus_metadata'),many=True).data)
        if 'page' not in request.query_params:
            return super().list(request,*args,**kwargs)
        search=request.query_params.get('search','').strip().casefold()
        if search:
            # SQLite's icontains does not fold Vietnamese letters such as Đ/đ.
            ids=[pk for pk,title in qs.values_list('pk','title').iterator() if search in title.casefold()]
            qs=qs.filter(pk__in=ids)
        status_filter=request.query_params.get('status','all')
        if status_filter!='all': qs=qs.filter(status=status_filter)
        review=request.query_params.get('review','all')
        approved=Q(corpus_metadata__review_status='approved')
        if review=='approved': qs=qs.filter(approved)
        elif review=='pending': qs=qs.filter(~approved|Q(corpus_metadata__review_status__isnull=True))
        elif review!='all': raise ValidationError('Trạng thái duyệt không hợp lệ.')
        paginator=PageNumberPagination()
        paginator.page_size=10
        paginator.page_size_query_param='page_size'
        paginator.max_page_size=50
        page=paginator.paginate_queryset(qs.defer('text','note','source'),request,view=self)
        return paginator.get_paginated_response(MaterialListSerializer(page,many=True).data)
    def perform_create(self, serializer): serializer.save(owner=self.request.user)
    def perform_update(self, serializer):
        if 'id' in serializer.validated_data and serializer.validated_data['id'] != serializer.instance.pk:
            raise ValidationError('Không đổi mã học liệu đã tạo.')
        metadata=dict(serializer.instance.corpus_metadata)
        if metadata and any(key in serializer.validated_data and serializer.validated_data[key]!=getattr(serializer.instance,key) for key in ['title','text','formula','note','source']):
            metadata.update(review_status='cho-giao-vien-duyet',reviewed_at=None,reviewed_by=None)
        serializer.save(corpus_metadata=metadata)

    @action(detail=True,methods=['post'])
    def review(self,request,pk=None):
        material=self.get_object()
        if type(request.data.get('approved')) is not bool:
            raise ValidationError('approved phải là true hoặc false.')
        metadata=dict(material.corpus_metadata)
        metadata.update(review_status='approved' if request.data['approved'] else 'cho-giao-vien-duyet',
                        reviewed_at=timezone.now().isoformat(),reviewed_by=request.user.pk)
        material.corpus_metadata=metadata
        material.save(update_fields=['corpus_metadata','updated'])
        return Response(self.get_serializer(material).data)

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
                source_grade=Material.objects.get(pk=source).grade
                target_grade=Material.objects.get(pk=target).grade
                if source_grade>target_grade:
                    raise ValidationError('Kiến thức lớp cao hơn không thể là tiên quyết bắt buộc của bài lớp thấp hơn.')
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

def visible_quizzes(user):
    """Curated quizzes, the user's own (personal AI or authored), and assignments published for the student's grade."""
    from django.db.models import Q
    published=Q(source='assignment',status='published')
    if role(user)=='student':
        grade=Profile.objects.get_or_create(user=user)[0].grade
        published&=Q(grade__isnull=True)|Q(grade=grade)
    return Quiz.objects.filter(Q(user=user)|Q(user__isnull=True)|published)


@api_view(['GET'])
def quiz_detail(request, pk):
    quiz=visible_quizzes(request.user).filter(pk=pk).first()
    if not quiz: return Response(status=404)
    return Response({'id':str(quiz.pk),'kind':quiz.kind,'title':quiz.title,'summary':quiz.summary,'source':quiz.source,'exercises':quiz.exercises,'contexts':quiz.contexts,
                     'questions':[{k:v for k,v in q.items() if k not in ('correct','explanation')} for q in quiz.questions]})

@api_view(['POST'])
def submit_quiz(request, pk):
    quiz=visible_quizzes(request.user).filter(pk=pk).first()
    if not quiz: return Response(status=404)
    if quiz.source=='assignment' and quiz.status!='published': raise ValidationError('Bài giao đang ở trạng thái nháp.')
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


def assignment_data(quiz,detail=False):
    attempts=list(quiz.quizattempt_set.all()) if quiz.pk else []
    total=len(quiz.questions) or 1
    data={'id':str(quiz.pk),'title':quiz.title,'status':quiz.status,'grade':quiz.grade,'material':quiz.material_id,
          'material_title':quiz.material.title if quiz.material else '','questions_count':len(quiz.questions),
          'attempts':len(attempts),'students':len({a.user_id for a in attempts}),
          'average':round(sum(a.score for a in attempts)/len(attempts)/total*100) if attempts else None,
          'author':quiz.user.first_name or quiz.user.username if quiz.user else '','published_at':quiz.published_at,'updated_at':quiz.updated_at}
    if detail: data.update(summary=quiz.summary,questions=quiz.questions)
    return data


def own_assignment(request,pk):
    quiz=Quiz.objects.filter(pk=pk,source='assignment').select_related('material','user').first()
    if not quiz: raise NotFound('Không tìm thấy bài giao.')
    if role(request.user)!='admin' and quiz.user_id!=request.user.id: raise PermissionDenied('Chỉ tác giả hoặc quản trị viên được chỉnh bài giao này.')
    return quiz


@api_view(['GET','POST'])
@permission_classes([EducatorOnly])
def assignments(request):
    if request.method=='POST':
        payload=AssignmentPayload(data=request.data);payload.is_valid(raise_exception=True);data=payload.validated_data
        material=Material.objects.get(pk=data['material'])
        quiz=Quiz.objects.create(user=request.user,source='assignment',status='draft',title=data['title'],grade=data['grade'],material=material,
                                 kind=material.kind,summary=data['summary'],questions=[dict(q) for q in data['questions']])
        return Response(assignment_data(quiz,True),status=201)
    qs=Quiz.objects.filter(source='assignment').select_related('material','user').prefetch_related('quizattempt_set').order_by('-updated_at')
    if role(request.user)!='admin': qs=qs.filter(user=request.user)
    return Response([assignment_data(q) for q in qs])


@api_view(['GET','PATCH','DELETE'])
@permission_classes([EducatorOnly])
def assignment_detail(request,pk):
    quiz=own_assignment(request,pk)
    has_attempts=quiz.quizattempt_set.exists()
    if request.method=='DELETE':
        if has_attempts: raise ValidationError('Bài giao đã có học sinh làm; hãy chuyển về nháp để ẩn thay vì xóa kết quả của học sinh.')
        quiz.delete();return Response(status=204)
    if request.method=='PATCH':
        payload=AssignmentPayload(data=request.data);payload.is_valid(raise_exception=True);data=payload.validated_data
        questions=[dict(q) for q in data['questions']]
        if has_attempts and questions!=quiz.questions: raise ValidationError('Bài giao đã có học sinh làm nên không đổi câu hỏi hoặc đáp án; hãy tạo bài mới.')
        material=Material.objects.get(pk=data['material'])
        quiz.title=data['title'];quiz.grade=data['grade'];quiz.material=material;quiz.kind=material.kind;quiz.summary=data['summary'];quiz.questions=questions
        quiz.save()
    return Response(assignment_data(quiz,True))


@api_view(['POST'])
@permission_classes([EducatorOnly])
def publish_assignment(request,pk):
    quiz=own_assignment(request,pk)
    if type(request.data.get('published')) is not bool: raise ValidationError('published phải là true hoặc false.')
    if request.data['published']:
        if not quiz.questions: raise ValidationError('Bài giao chưa có câu hỏi.')
        quiz.status='published';quiz.published_at=quiz.published_at or timezone.now()
    else: quiz.status='draft'
    quiz.save(update_fields=['status','published_at','updated_at'])
    return Response(assignment_data(quiz,True))


@api_view(['GET'])
@permission_classes([EducatorOnly])
def assignment_results(request,pk):
    quiz=own_assignment(request,pk)
    attempts=list(quiz.quizattempt_set.select_related('user').order_by('created_at'))
    per_question=[]
    for i,q in enumerate(quiz.questions):
        picks=[a.answers[i] for a in attempts if i<len(a.answers)]
        wrong=[p for p in picks if p!=q['correct']]
        common=max(set(wrong),key=wrong.count) if wrong else None
        per_question.append({'index':i,'question':q['question'],'concept':q['concept'],'correct_rate':round(sum(p==q['correct'] for p in picks)/len(picks)*100) if picks else None,
                             'common_wrong':q['options'][common] if common is not None else None,'common_wrong_count':wrong.count(common) if wrong else 0})
    students={}
    for a in attempts:
        entry=students.setdefault(a.user_id,{'name':a.user.first_name or a.user.username,'attempts':0,'best':0,'last':None})
        entry['attempts']+=1;entry['best']=max(entry['best'],a.score);entry['last']=a.created_at
    return Response({**assignment_data(quiz),'total':len(quiz.questions),'questions':per_question,'student_rows':sorted(students.values(),key=lambda s:s['best'])})


@api_view(['GET'])
@permission_classes([EducatorOnly])
def statistics(request):
    own=Quiz.objects.filter(source='assignment').select_related('material','user').prefetch_related('quizattempt_set').order_by('-updated_at')
    if role(request.user)!='admin': own=own.filter(user=request.user)
    return Response({'students':Profile.objects.filter(role='student',user__is_superuser=False).count(), 'sessions':LearningSession.objects.count(),
                     'attempts':QuizAttempt.objects.count(),'gaps':list(KnowledgeGap.objects.filter(resolved=False).values('concept_id','concept__title').annotate(students=Count('user',distinct=True),errors=Sum('errors')).order_by('-errors')),
                     'assignments':[assignment_data(q) for q in own]})


@api_view(['GET'])
@permission_classes([EducatorOnly])
def learning_reports(request):
    qs=LearningReport.objects.all() if role(request.user)=='admin' else LearningReport.objects.filter(owner=request.user)
    return Response([{'id':str(r.pk),'content':r.content,'focus':r.focus,'source':r.source,'date':r.created_at.isoformat()} for r in qs.order_by('-created_at')[:20]])


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
    qs=visible_quizzes(request.user).select_related('material').order_by('-created_at')
    best={}
    for quiz_id,score in QuizAttempt.objects.filter(user=request.user).values_list('quiz_id','score'): best[quiz_id]=max(best.get(quiz_id,0),score)
    return Response([{'id':str(q.pk),'kind':q.kind,'source':q.source,'summary':q.summary,'title':q.title,'status':q.status,'grade':q.grade,
                      'material_title':q.material.title if q.material else '','questions_count':len(q.questions),'created_at':q.created_at.isoformat(),
                      'best_score':best.get(q.pk)} for q in qs if q.source!='assignment' or q.status=='published' or q.user_id==request.user.id])
