"""FastAPI inference; Django owns accounts, authorization and persistent learning records."""
import base64
import io
import json
import logging
import os
from pathlib import Path
from uuid import UUID

os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend_web.settings')
import django
django.setup()
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import Throttled
from fastapi import FastAPI, Depends, Header, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from learning.models import LearningSession, Material, Quiz, ResearchReport
from learning.permissions import role
from learning.serializers import SessionSerializer
from learning.services import record_gap
from .providers import qwen_reply, generate_learning, ProviderUnavailable, Geometry

logger=logging.getLogger(__name__)
app=FastAPI(title='MindGeoTutorAI · Qwen & Hybrid RAG',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=settings.CORS_ALLOWED_ORIGINS,allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Authorization','Content-Type'])


def current_user(authorization: str = Header(default='')):
    close_old_connections()
    try:
        scheme,key=authorization.split(' ',1)
        if scheme.lower() not in ('token','bearer'): raise ValueError()
        token=Token.objects.select_related('user').get(key=key,user__is_active=True)
    except (ValueError,Token.DoesNotExist):
        raise HTTPException(401,'Phiên đăng nhập không hợp lệ. Hãy đăng nhập lại.')
    try:
        yield token.user
    finally: close_old_connections()


def educator(user=Depends(current_user)):
    if role(user) not in ('educator','admin'): raise HTTPException(403,'Chức năng dành cho giáo viên và quản trị viên.')
    return user


def admin(user=Depends(current_user)):
    if role(user)!='admin': raise HTTPException(403,'Chức năng dành cho quản trị viên.')
    return user


def failure(exc):
    if isinstance(exc,ProviderUnavailable): raise HTTPException(503,str(exc))
    if isinstance(exc,ModuleNotFoundError): raise HTTPException(503,'Thiếu thư viện AI tùy chọn. Cài requirements-ai.txt trước khi sử dụng tính năng này.')
    if isinstance(exc,Throttled): raise HTTPException(429,str(exc.detail))
    # Provider exception messages may contain endpoints or credentials. Keep them off the response.
    logger.warning('AI operation failed (%s)',type(exc).__name__)
    raise HTTPException(502,'Dịch vụ AI hoặc kho tri thức chưa sẵn sàng, hoặc phản hồi chưa đúng định dạng. Kiểm tra cấu hình và thử lại.')


def decode_photo(photo):
    if not photo: return None
    raw=photo.file.read(10*1024*1024+1)
    if len(raw)>10*1024*1024: raise HTTPException(413,'Ảnh tối đa 10 MB.')
    if photo.content_type not in ['image/jpeg','image/png','image/webp']: raise HTTPException(422,'Chỉ nhận JPG, PNG hoặc WEBP.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ['JPEG','PNG','WEBP'] or image.width*image.height>24000000: raise ValueError()
            image.verify()
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError): raise HTTPException(422,'Nội dung ảnh không hợp lệ hoặc kích thước quá lớn.')
    return {'name':Path(photo.filename or 'photo').name,'data':'data:'+photo.content_type+';base64,'+base64.b64encode(raw).decode()}


@app.get('/api/v1/ai/health')
def health(): return {'status':'ok','service':'fastapi','qwen_configured':bool(os.getenv('QWEN_BASE_URL') and os.getenv('QWEN_MODEL'))}


@app.get('/api/v1/system/status')
def system_status(user=Depends(admin)):
    from django.db import connection
    from learning.models import TrainingRun
    connection.ensure_connection()
    return {'database':{'status':'connected'},'fastapi':{'status':'running'},
            'qwen':{'status':'configured' if os.getenv('QWEN_BASE_URL') and os.getenv('QWEN_MODEL') else 'not_configured','model':os.getenv('QWEN_MODEL','')},
            'rag':{'status':'enabled' if os.getenv('RAG_ENABLED','false').lower()=='true' else 'not_configured'},
            'neo4j':{'status':'configured' if os.getenv('NEO4J_URI') and os.getenv('NEO4J_PASSWORD') else 'not_configured'},
            'content':{'provider':os.getenv('CONTENT_PROVIDER','gemini'),'status':'configured' if (os.getenv('GEMINI_API_KEY') and os.getenv('GEMINI_MODEL') if os.getenv('CONTENT_PROVIDER','gemini')=='gemini' else os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')) else 'not_configured'},
            'research':{'status':'configured' if all(os.getenv(k) for k in ['OPENAI_API_KEY','OPENAI_MODEL','TAVILY_API_KEY']) else 'not_configured'},
            'note':'configured chỉ xác nhận đã khai báo; chưa chứng minh dịch vụ từ xa đang kết nối.'}


@app.post('/api/v1/tutor/socratic-ask')
def socratic_ask(prompt_question: str = Form(default='',max_length=2000),session_id: UUID|None=Form(default=None),photo: UploadFile|None=File(default=None),hint: bool=Form(default=False),user=Depends(current_user)):
    text=prompt_question.strip()
    if not text and not photo: raise HTTPException(422,'Nhập câu hỏi hoặc tải ảnh đề bài.')
    if session_id:
        session=LearningSession.objects.filter(pk=session_id,user=user).first()
        if not session: raise HTTPException(404,'Không tìm thấy phiên học của bạn.')
        if session.completed: raise HTTPException(409,'Phiên học đã hoàn thành. Hãy bắt đầu phiên mới.')
        if photo: raise HTTPException(422,'Ảnh đề bài chỉ được gửi khi bắt đầu phiên.')
    else:
        session=LearningSession(user=user,title=text[:140] or 'Bài toán từ ảnh',photo=decode_photo(photo))
    if len(session.messages)>=100: raise HTTPException(422,'Phiên học đạt 100 lượt trao đổi. Hãy mở phiên mới.')
    message={'role':'student','text':text or 'Em muốn tìm hiểu bài toán trong ảnh này.'}
    messages=[*session.messages,message]
    concepts=list(Material.objects.filter(status='Đã xuất bản').values('id','title'))
    try:
        reply=qwen_reply(messages,session.photo,concepts)
    except Exception as exc: failure(exc)
    response={'role':'tutor',**reply.model_dump(exclude={'geometry'})}
    if hint: response['hint']=True
    response['incorrect']=reply.correct is False
    new_values={'messages':messages+[response],'completed':reply.done,'version':session.version+1,'updated_at':timezone.now()}
    if reply.geometry:
        new_values['kind']=reply.geometry.type
        new_values['params']=reply.geometry.model_dump(exclude={'type'})
    with transaction.atomic():
        if session._state.adding:
            for key,value in new_values.items(): setattr(session,key,value)
            session.save()
        else:
            if not LearningSession.objects.filter(pk=session.pk,version=session.version).update(**new_values):
                raise HTTPException(409,'Phiên vừa thay đổi ở cửa sổ khác. Tải lại trước khi gửi tiếp.')
            session.refresh_from_db()
        if reply.correct is False and reply.concept: record_gap(user,reply.concept)
    gap_context=None
    if reply.correct is False and reply.concept and os.getenv('RAG_ENABLED','false').lower()=='true':
        from integrations.geometry_rag import retrieve
        try: gap_context={'status':'retrieved',**retrieve(reply.concept,query=text)}
        except Exception: gap_context={'status':'unavailable','detail':'Đã ghi nhận kiến thức cần ôn; kho RAG chưa truy xuất được.'}
    return {'session':SessionSerializer(session).data,'geometry':reply.geometry.model_dump() if reply.geometry else None,'response':response,'gap_context':gap_context}


class ConceptRequest(BaseModel):
    concept_id: str = Field(min_length=1,max_length=80)
    query: str|None = Field(default=None,max_length=2000)


def published_material(pk):
    material=Material.objects.filter(pk=pk,status='Đã xuất bản').first()
    if not material: raise HTTPException(404,'Không tìm thấy học liệu đã xuất bản.')
    return material


@app.post('/api/v1/rag/analyze-gap')
def analyze_gap(body: ConceptRequest,user=Depends(current_user)):
    published_material(body.concept_id)
    from integrations.geometry_rag import retrieve
    try: return retrieve(body.concept_id,query=body.query)
    except Exception as exc: failure(exc)


@app.post('/api/v1/rag/sync')
def sync_rag(user=Depends(educator)):
    from integrations.geometry_rag import sync_corpus
    try: return sync_corpus()
    except Exception as exc: failure(exc)


@app.post('/api/v1/recommend/quiz-summary')
def recommend(body: ConceptRequest,user=Depends(current_user)):
    material=published_material(body.concept_id)
    from integrations.geometry_rag import retrieve
    try:
        context=retrieve(body.concept_id,query=body.query)
        content,provider=generate_learning(context)
        quiz=Quiz.objects.create(user=user,kind=material.kind,summary=content.summary,questions=[q.model_dump() for q in content.questions],source=provider,exercises=[e.model_dump() for e in content.exercises],contexts=context['contexts'])
    except Exception as exc: failure(exc)
    return {'quiz_id':str(quiz.pk),'summary':content.summary,'exercises':[e.model_dump() for e in content.exercises],'source':provider,'contexts':context['contexts'],'notice':'Nội dung AI cần đối chiếu; đáp án quiz được chấm tại máy chủ.'}


@app.post('/api/v1/system/check')
def check_system(user=Depends(admin)):
    from integrations.service_checks import check_services
    return check_services()


@app.get('/api/v1/rag/graph')
def extracted_graph(concept_id:str,user=Depends(current_user)):
    published_material(concept_id)
    from integrations.geometry_extraction import graph_for_concept
    try:
        from neo4j import GraphDatabase
        if not os.getenv('NEO4J_URI') or not os.getenv('NEO4J_PASSWORD'):
            raise ProviderUnavailable('Chưa cấu hình Neo4j.')
        with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.getenv('NEO4J_USERNAME','neo4j'),os.environ['NEO4J_PASSWORD']),connection_timeout=5) as driver:
            return graph_for_concept(driver,concept_id)
    except Exception as exc:failure(exc)


@app.post('/api/v1/research/report')
def research_report(body: ConceptRequest,user=Depends(educator)):
    material=published_material(body.concept_id)
    from integrations.research import create_report
    try:
        result=create_report(material)
        report=ResearchReport.objects.create(owner=user,material=material,content=result['content'],sources=result['sources'])
    except Exception as exc: failure(exc)
    return {'id':str(report.pk),**result}


class GeometryRequest(BaseModel):
    session_id: UUID
    geometry: Geometry
    version: int = Field(ge=0)


@app.post('/api/v1/Geometry2D/sync')
def sync_geometry(body:GeometryRequest,user=Depends(current_user)):
    session=LearningSession.objects.filter(pk=body.session_id,user=user).first()
    if not session: raise HTTPException(404,'Không tìm thấy phiên học.')
    if not session.completed: raise HTTPException(409,'Giữ nguyên dữ kiện đề bài trong lúc giải; xoay/phóng to được xử lý tại trình duyệt.')
    if not LearningSession.objects.filter(pk=session.pk,version=body.version).update(kind=body.geometry.type,params=body.geometry.model_dump(exclude={'type'}),version=body.version+1,updated_at=timezone.now()): raise HTTPException(409,'Phiên đã thay đổi, hãy tải lại.')
    session.refresh_from_db()
    return SessionSerializer(session).data
