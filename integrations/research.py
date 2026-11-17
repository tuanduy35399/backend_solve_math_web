import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from django.conf import settings
from .upstream import ROOT

def create_report(material=None,topic=None,mode='material'):
    """mode='material': supporting sources for a lesson; mode='story': history/anecdote sources for a story draft."""
    topic=topic or material.title+' / '+material.topic
    from ai_service.providers import ProviderUnavailable
    if not all(os.getenv(k) for k in ['OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_MODEL','TAVILY_API_KEY']):
        raise ProviderUnavailable('Cần OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL và TAVILY_API_KEY cho agent nghiên cứu.')
    source=ROOT/'ai_agent_game_maker_plan'
    if not (source/'tools.py').exists(): raise ProviderUnavailable('Chưa clone repo agent. Chạy scripts/clone_sources.py.')
    with tempfile.TemporaryDirectory(prefix='mindgeo-report-') as temp:
        try:
            process=subprocess.run([sys.executable,str(settings.BASE_DIR/'integrations/research_worker.py'),str(source)],input=json.dumps({'topic':topic,'mode':mode},ensure_ascii=False),text=True,cwd=temp,capture_output=True,timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise ProviderUnavailable('Lập báo cáo quá thời gian 3 phút. Thử lại sau hoặc chọn chủ đề hẹp hơn.') from exc
        if process.returncode:
            messages={
                'model_connection':'Không kết nối được gateway model sinh báo cáo (OPENAI_BASE_URL). Bật lại gateway hoặc kiểm tra địa chỉ, rồi thử lại.',
                'model_auth':'Gateway model từ chối xác thực. Kiểm tra OPENAI_API_KEY và quyền truy cập model.',
                'model_rate_limit':'Gateway model đang giới hạn lượt gọi hoặc đã hết hạn mức. Thử lại sau.',
                'model_request':'Gateway model từ chối yêu cầu gọi công cụ. Kiểm tra model và khả năng hỗ trợ tool calling.',
                'search_failed':'Không tìm nguồn được qua Tavily. Kiểm tra kết nối, TAVILY_API_KEY và hạn mức tìm kiếm.',
                'dependency':'Thiếu thư viện chạy agent. Cài requirements-ai.txt cho môi trường backend.',
                'timeout':'Gateway model phản hồi quá chậm. Thử lại sau hoặc kiểm tra dịch vụ model.',
                'no_report':'Agent chưa hoàn thành bước ghi báo cáo. Thử lại với chủ đề cụ thể hơn.',
                'no_sources':'Agent chưa trả về nguồn web để đối chiếu, nên báo cáo chưa được lưu.',
            }
            error_path=Path(temp)/'error.json'
            try:code=json.loads(error_path.read_text()).get('code')
            except (OSError,ValueError):code=None
            raise ProviderUnavailable(messages.get(code,'Agent lập báo cáo chưa hoàn thành. Thử lại sau hoặc kiểm tra dịch vụ model và tìm kiếm.'))
        result=json.loads((Path(temp)/'result.json').read_text())
        if len(result['content'])>100000: raise ValueError('Báo cáo quá dài.')
        return result
