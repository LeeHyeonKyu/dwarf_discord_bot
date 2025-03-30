import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional

def load_config() -> Dict[str, Any]:
    """
    환경 변수 로드 및 설정 사전 반환
    """
    # .env.secret 파일 로드
    load_dotenv(".env.secret")
    
    # 필수 환경 변수
    TOKEN: Optional[str] = os.getenv('DISCORD_TOKEN')
    CHANNEL_ID: str = os.getenv('CHANNEL_ID', '0')
    LOSTARK_API_KEY: Optional[str] = os.getenv('LOSTARK_API_KEY')
    
    # 설정 사전 생성
    config = {
        "TOKEN": TOKEN,
        "CHANNEL_ID": CHANNEL_ID,
        "LOSTARK_API_KEY": LOSTARK_API_KEY
    }
    
    return config 