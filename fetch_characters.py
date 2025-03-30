import json
from pathlib import Path
import requests
import yaml
import urllib.parse
from pprint import pprint
import datetime
import os

# .env.secret에서 API 키 가져오기
from dotenv import load_dotenv
load_dotenv('.env.secret')
api_key = os.getenv('LOSTARK_API_KEY')

print(f"API 키 로드: {'성공' if api_key else '실패'}")

# 멤버 설정 로드
with open('configs/members_config.yaml', 'r', encoding='utf-8') as f:
    config_data = yaml.safe_load(f)
    all_members = config_data.get('members', [])
    
    # active 상태인 멤버만 필터링
    members = [member for member in all_members if member.get('active', False)]

print(f"멤버 설정 로드 완료: 전체 {len(all_members)}명 중 활성화된 {len(members)}명의 멤버 정보 확인")

# API 호출에 필요한 헤더 설정
headers = {
    'accept': 'application/json',
    'authorization': f'bearer {api_key}'
}

# 데이터 저장 디렉토리 생성
os.makedirs('data', exist_ok=True)

# 결과 저장할 데이터 객체
all_data = {}

for member in members:
    member_id = member.get('id')
    discord_name = member.get('discord_name')
    main_characters = member.get('main_characters', [])
    
    if not main_characters:
        print(f'멤버 {member_id}의 메인 캐릭터가 없습니다.')
        continue
    
    main_character = main_characters[0]
    print(f'멤버 {discord_name}의 캐릭터 정보 조회 중...')
    
    # 계정 내 캐릭터 목록 조회
    siblings_url = f'https://developer-lostark.game.onstove.com/characters/{urllib.parse.quote(main_character)}/siblings'
    
    try:
        response = requests.get(siblings_url, headers=headers)
        
        if response.status_code == 200:
            siblings_data = response.json()
            
            # 아이템 레벨 기준 내림차순 정렬
            sorted_characters = sorted(
                siblings_data,
                key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
                reverse=True
            )
            
            # 처리된 캐릭터 목록
            processed_characters = []
            
            for char in sorted_characters:
                char_name = char.get('CharacterName', '')
                char_class = char.get('CharacterClassName', '')
                char_server = char.get('ServerName', '')
                item_level = char.get('ItemMaxLevel', '0')
                
                # 캐릭터 정보 구성
                character_info = {
                    'name': char_name,
                    'class': char_class,
                    'server': char_server,
                    'item_level': item_level,
                    'last_updated': datetime.datetime.now().isoformat()
                }
                
                processed_characters.append(character_info)
                print(f'  - {char_name} ({char_class}): {item_level}')
            
            # 멤버 데이터 저장
            all_data[member_id] = {
                'discord_name': discord_name,
                'main_character': sorted_characters[0].get('CharacterName', '') if sorted_characters else main_character,
                'characters': processed_characters,
                'last_updated': datetime.datetime.now().isoformat()
            }
            
            print(f'총 {len(processed_characters)}개의 캐릭터 정보 조회 완료')
            
        elif response.status_code == 429:
            print(f'API 요청 한도 초과!')
        else:
            print(f'API 요청 실패: 상태 코드 {response.status_code}')
            
    except Exception as e:
        print(f'캐릭터 정보 조회 중 오류: {e}')

# 데이터 저장
with open('data/character_data.json', 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print('모든 데이터가 data/character_data.json 파일에 저장되었습니다.') 