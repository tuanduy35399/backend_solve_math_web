"""Check the separately hosted Qwen checkpoint without any cloud fallback."""
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
    parser.add_argument('--image',type=Path,help='Ảnh đề bài của bạn, chỉ gửi tới QWEN_BASE_URL.')
    args=parser.parse_args()
    base=os.getenv('QWEN_BASE_URL','').rstrip('/')
    model=os.getenv('QWEN_MODEL','')
    if not base or not model:
        parser.exit(2,'Chưa có QWEN_BASE_URL/QWEN_MODEL. Xem docs/QWEN_DEPLOYMENT.md; chưa gọi dịch vụ nào.\n')
    try:
        with httpx.Client(timeout=15,trust_env=False) as client:
            response=client.get(base+'/models',headers={'Authorization':'Bearer '+(os.getenv('QWEN_API_KEY') or 'local')})
            response.raise_for_status()
            if model not in {m.get('id') for m in response.json().get('data',[])}:
                parser.exit(1,'Endpoint hoạt động nhưng không liệt kê QWEN_MODEL đã cấu hình.\n')
        print('PASS: endpoint Qwen liệt kê đúng tên model.')
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
            from ai_service.providers import qwen_reply
            result=qwen_reply([{'role':'student','text':'Cho tam giác ABC vuông tại A, AB=3 cm, AC=4 cm. Em nên bắt đầu xác định cạnh huyền thế nào?'}],photo,[{'id':'g8-pythagore','title':'Định lý Pythagore'}])
            print('PASS: nhận và kiểm tra được JSON TutorResponse từ Qwen thật.')
            print(json.dumps(result.model_dump(),ensure_ascii=False,indent=2))
            print('Đây là kiểm tra kết nối/schema; cần giáo viên đánh giá riêng tính đúng và phong cách Socratic.')
    except Exception as exc:
        parser.exit(1,f'FAIL: {type(exc).__name__}. Kiểm tra endpoint, tên model, khóa và log máy phục vụ; không gọi model bên ngoài.\n')


if __name__=='__main__':main()
