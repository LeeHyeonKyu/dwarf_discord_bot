import requests
import os
import json
from dotenv import load_dotenv
import urllib.parse

# .env.secret에서 API 키 로드
load_dotenv('.env.secret')
API_KEY = os.getenv('LOSTARK_API_KEY')

if not API_KEY:
    print("LOSTARK_API_KEY가 .env.secret 파일에 설정되어 있지 않습니다.")
    exit(1)

# 테스트할 캐릭터 이름 (여기서는 예시로 설정)
character_name = "놀러나온드워프"

# API 호출 헤더
headers = {
    'accept': 'application/json',
    'authorization': f'bearer {API_KEY}'
}

def fetch_character_siblings(character_name):
    """캐릭터의 계정 내 다른 캐릭터 정보 가져오기"""
    try:
        # URL 인코딩
        encoded_name = urllib.parse.quote(character_name)
        
        # API 엔드포인트 URL
        url = f'https://developer-lostark.game.onstove.com/characters/{encoded_name}/siblings'
        
        # API 요청
        response = requests.get(url, headers=headers)
        
        # 응답 코드 확인
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print(f"API 요청 한도 초과: {response.headers.get('X-RateLimit-Remaining', 'N/A')}")
            return None
        else:
            print(f"API 요청 실패: 상태 코드 {response.status_code}")
            if response.text:
                print(f"에러 메시지: {response.text}")
            return None
            
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return None

# 캐릭터 정보 가져오기
print(f"'{character_name}' 캐릭터 정보 조회 중...")
siblings_data = fetch_character_siblings(character_name)

if siblings_data:
    # 아이템 레벨 순으로 정렬
    sorted_characters = sorted(
        siblings_data,
        key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
        reverse=True
    )
    
    print(f"\n'{character_name}'의 계정에 {len(sorted_characters)}개의 캐릭터가 있습니다.")
    print("="*60)
    
    # 캐릭터 정보 출력
    for i, char in enumerate(sorted_characters, 1):
        char_name = char.get('CharacterName', '알 수 없음')
        char_class = char.get('CharacterClassName', '알 수 없음')
        char_server = char.get('ServerName', '알 수 없음')
        item_level = char.get('ItemMaxLevel', '0')
        
        print(f"{i}. {char_name} ({char_class}) - {char_server} 서버, 아이템 레벨: {item_level}")
    
    print("="*60)
    
    # 첫 번째 캐릭터(가장 높은 아이템 레벨)의 상세 정보 출력
    print("\n가장 높은 아이템 레벨 캐릭터 상세 정보:")
    print(json.dumps(sorted_characters[0], ensure_ascii=False, indent=2))
else:
    print(f"'{character_name}' 캐릭터 정보를 가져오는데 실패했습니다.") 