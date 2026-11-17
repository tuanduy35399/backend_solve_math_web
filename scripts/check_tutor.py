"""Check the tutor model (shared OPENAI_* config with the research agent)."""
import argparse
import base64
import json
import os
import sys
from pathlib import Path
import httpx
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--infer',action='store_true',help='Gửi một bài hình học mẫu để kiểm tra JSON contract.')
    parser.add_argument('--image',type=Path,help='Ảnh đề bài của bạn, gửi tới OPENAI_BASE_URL.')
    args=parser.parse_args()
    base=os.getenv('OPENAI_BASE_URL','').rstrip('/')
    model=os.getenv('OPENAI_MODEL','')
    if not base or not model or not os.getenv('OPENAI_API_KEY'):
        parser.exit(2,'Chưa có OPENAI_BASE_URL/OPENAI_MODEL/OPENAI_API_KEY; chưa gọi dịch vụ nào.\n')
    try:
        with httpx.Client(timeout=15,trust_env=False) as client:
            response=client.get(base+'/models',headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']})
            response.raise_for_status()
            if model not in {m.get('id') for m in response.json().get('data',[])}:
                parser.exit(1,'Endpoint hoạt động nhưng không liệt kê OPENAI_MODEL đã cấu hình.\n')
        print('PASS: endpoint liệt kê đúng tên model gia sư.')
        if args.infer:
            photo=None
            if args.image:
                import io
                from PIL import Image
                raw=args.image.read_bytes()
                if len(raw)>10*1024*1024:raise ValueError('Ảnh vượt 10 MB.')
                with Image.open(io.BytesIO(raw)) as image:
                    image.verify();mime=Image.MIME[image.format]
                if mime not in ['image/png','image/jpeg','image/webp']:raise ValueError('Ảnh cần là PNG, JPEG hoặc WebP.')
                photo={'data':'data:'+mime+';base64,'+base64.b64encode(raw).decode()}
            from ai_service.providers import tutor_reply
            result=tutor_reply([{'role':'student','text':'Cho tam giác ABC vuông tại A, AB=3 cm, AC=4 cm. Em nên bắt đầu xác định cạnh huyền thế nào?'}],photo,[{'id':'g8-pythagore','title':'Định lý Pythagore'}])
            print('PASS: nhận và kiểm tra được JSON TutorResponse từ model gia sư.')
            print(json.dumps(result.model_dump(),ensure_ascii=False,indent=2))
            print('Đây là kiểm tra kết nối/schema; cần giáo viên đánh giá riêng tính đúng và phong cách Socratic.')
    except Exception as exc:
        parser.exit(1,f'FAIL: {type(exc).__name__}. Kiểm tra endpoint, tên model, khóa và log gateway.\n')


if __name__=='__main__':main()
