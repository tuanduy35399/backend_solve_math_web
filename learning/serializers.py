from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import Material, LearningSession, QuizAttempt, TrainingRun
from .permissions import role

def profile_data(user):
    from .models import Profile
    profile, _ = Profile.objects.get_or_create(user=user,defaults={'role':'admin' if user.is_superuser else 'student'})
    return {'id': str(user.id), 'username': user.username, 'name': user.first_name or user.username,
            'email': user.email, 'grade': str(profile.grade), 'role': role(user), 'active': user.is_active}

class Registration(serializers.Serializer):
    username = serializers.RegexField(r'^[\w.@+-]+$', min_length=3, max_length=150)
    password = serializers.CharField(write_only=True, max_length=128)
    name = serializers.CharField(max_length=60)
    email = serializers.EmailField(required=False, allow_blank=True)
    grade = serializers.IntegerField(min_value=6, max_value=12, default=9)
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Tên đăng nhập đã tồn tại.')
        return value
    def validate(self, data):
        validate_password(data['password'], User(username=data['username'], first_name=data['name'], email=data.get('email','')))
        return data

class MaterialSerializer(serializers.ModelSerializer):
    ownerId = serializers.CharField(source="owner_id",read_only=True,allow_null=True)
    id = serializers.SlugField(required=False, max_length=80, validators=[UniqueValidator(queryset=Material.objects.all(),message="Mã học liệu đã tồn tại.")])
    grade = serializers.IntegerField(min_value=6, max_value=12)
    minutes = serializers.IntegerField(min_value=1, max_value=120, required=False)
    kind = serializers.ChoiceField(choices=['triangle','prism','sphere','general'])
    def validate(self,data):
        if self.instance and 'grade' in data:
            grade=data['grade']
            if self.instance.requires.filter(source__grade__gt=grade).exists() or self.instance.unlocks.filter(target__grade__lt=grade).exists():
                raise serializers.ValidationError({'grade':'Lớp mới làm quan hệ tiên quyết đi từ lớp cao xuống lớp thấp. Điều chỉnh quan hệ trước khi đổi lớp.'})
        return data
    class Meta:
        model = Material
        exclude = ['owner']
        read_only_fields = ['updated', 'corpus_metadata']

class SessionSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='kind', read_only=True)
    date = serializers.DateTimeField(source='created_at', read_only=True)
    stage = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    class Meta:
        model = LearningSession
        fields = ['id','title','type','date','stage','status','params','photo','messages','version']
        read_only_fields = ['id','params','photo','messages','version']
    def get_stage(self, obj): return sum(m.get('correct') is True for m in obj.messages)
    def get_status(self, obj): return 'Hoàn thành' if obj.completed else 'Đang học'

class AttemptSerializer(serializers.ModelSerializer):
    mastered = serializers.SerializerMethodField()
    kind = serializers.CharField(source='quiz.kind')
    total = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at')
    class Meta:
        model = QuizAttempt
        fields = ['id','kind','total','score','date','seconds','answers','mastered']
    def get_total(self, obj): return len(obj.quiz.questions)
    def get_mastered(self, obj):
        missed={q['concept'] for a,q in zip(obj.answers,obj.quiz.questions) if a!=q['correct']}
        return sorted({q['concept'] for a,q in zip(obj.answers,obj.quiz.questions) if a==q['correct']} - missed)

class TrainingSerializer(serializers.ModelSerializer):
    def validate_metrics(self, value):
        if not isinstance(value, dict): raise serializers.ValidationError("Metrics cần là đối tượng JSON.")
        return value
    class Meta:
        model = TrainingRun
        exclude = ['owner']
        read_only_fields = ['id','created_at']


class StorySource(serializers.Serializer):
    title=serializers.CharField(max_length=300)
    url=serializers.URLField(max_length=2000)
    scope=serializers.CharField(max_length=2000)
    def validate_url(self,value):
        if not value.startswith(('https://','http://')): raise serializers.ValidationError('Nguồn cần URL HTTP hoặc HTTPS.')
        return value

class StoryPayload(serializers.Serializer):
    id=serializers.RegexField(r'^bai-viet-[a-zA-Z0-9_-]+$',max_length=80)
    status=serializers.ChoiceField(choices=['draft','published'])
    kind=serializers.ChoiceField(choices=['history','legend','discovery'])
    paragraphs=serializers.ListField(child=serializers.CharField(max_length=40000),max_length=100)
    sources=StorySource(many=True)
    def get_fields(self):
        fields=super().get_fields()
        limits={'title':140,'theorem':120,'hook':400,'topic':80,'level':80,'era':160,'insight':2000,'formula':2000,'condition':2000,'evidence':3000,'question':2000,'answer':4000,'lesson':80,'lab':16,'createdAt':80,'updatedAt':80,'publishedAt':80}
        for name,limit in limits.items():fields[name]=serializers.CharField(max_length=limit,allow_blank=True,allow_null=name=='publishedAt',required=False,default='')
        return fields
    def validate(self,data):
        if data['status']=='published':
            for key in ['title','theorem','hook','topic','insight','formula','condition','evidence','question','answer']:
                if not data.get(key,'').strip(): raise serializers.ValidationError({key:'Bắt buộc khi xuất bản.'})
            if not data['paragraphs'] or not data['sources']: raise serializers.ValidationError('Bài xuất bản cần nội dung và nguồn.')
        if sum(len(p) for p in data['paragraphs'])>40000: raise serializers.ValidationError('Nội dung tối đa 40.000 ký tự.')
        return data
