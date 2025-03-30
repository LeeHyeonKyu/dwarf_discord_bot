import requests
import os
import json
import yaml
import time
import urllib.parse
from dotenv import load_dotenv

# .env.secret에서 API 키 로드
load_dotenv('.env.secret')
API_KEY = os.getenv('LOSTARK_API_KEY')

if not API_KEY:
    print("LOSTARK_API_KEY가 .env.secret 파일에 설정되어 있지 않습니다.")
    exit(1)

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
            # 요청 한도 초과 시 5초 대기 후 재시도
            time.sleep(5)
            return fetch_character_siblings(character_name)
        else:
            print(f"API 요청 실패: 상태 코드 {response.status_code}")
            if response.text:
                print(f"에러 메시지: {response.text}")
            return None
            
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return None

# 멤버 설정 파일 로드
with open('configs/members_config.yaml', 'r', encoding='utf-8') as f:
    config_data = yaml.safe_load(f)
    members = config_data.get('members', [])

print(f"총 {len(members)}명의 멤버 정보를 로드했습니다.")

# 결과를 저장할 데이터 구조
character_data = {}

# 각 멤버별로 처리
for member in members:
    member_id = member.get('id')
    discord_name = member.get('discord_name')
    discord_id = member.get('discord_id')
    main_characters = member.get('main_characters', [])
    
    if not main_characters:
        print(f"멤버 {discord_name} (ID: {discord_id})의 메인 캐릭터가 지정되어 있지 않습니다. 건너뜁니다.")
        continue
    
    # 메인 캐릭터로 API 요청
    main_character = main_characters[0]
    print(f"\n{discord_name} (ID: {discord_id})의 메인 캐릭터 '{main_character}' 정보 조회 중...")
    
    siblings_data = fetch_character_siblings(main_character)
    
    if siblings_data:
        # 아이템 레벨 기준 내림차순 정렬
        sorted_characters = sorted(
            siblings_data,
            key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
            reverse=True
        )
        
        # 1600 레벨 이상인 캐릭터만 필터링
        filtered_characters = [
            char for char in sorted_characters 
            if float(char.get('ItemMaxLevel', '0').replace(',', '')) >= 1600
        ]
        
        # 캐릭터 정보 출력
        print(f"계정 내 총 {len(sorted_characters)}개 캐릭터 중 1600 이상 {len(filtered_characters)}개 캐릭터:")
        for i, char in enumerate(filtered_characters, 1):
            char_name = char.get('CharacterName', '알 수 없음')
            char_class = char.get('CharacterClassName', '알 수 없음')
            char_server = char.get('ServerName', '알 수 없음')
            item_level = char.get('ItemMaxLevel', '0')
            
            print(f"  {i}. {char_name} ({char_class}) - {char_server} 서버, 아이템 레벨: {item_level}")
        
        # 필터링된 캐릭터 정보만 저장
        if filtered_characters:
            character_data[discord_id] = {
                'id': member_id,
                'discord_name': discord_name,
                'discord_id': discord_id,
                'characters': filtered_characters
            }
        else:
            print(f"  경고: {discord_name}의 캐릭터 중 1600 이상 레벨이 없습니다.")
        
        # API 요청 사이에 지연 추가 (API 제한에 의한 오류 방지)
        time.sleep(1)
    else:
        print(f"멤버 {discord_name}의 캐릭터 정보를 가져오는데 실패했습니다.")

# 데이터 저장
output_path = 'data/member_characters.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(character_data, f, ensure_ascii=False, indent=2)

print(f"\n총 {len(character_data)}명의 멤버 캐릭터 정보를 {output_path}에 저장했습니다.") 