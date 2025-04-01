import requests
import os
import json
import sys
import argparse
import yaml
from dotenv import load_dotenv
import urllib.parse

# 상위 디렉토리 경로를 추가하여 프로젝트 모듈을 import할 수 있게 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# .env.secret에서 API 키 로드
load_dotenv('.env.secret')
API_KEY = os.getenv('LOSTARK_API_KEY')

# 파일 경로 설정
MEMBERS_CONFIG_PATH = './configs/members_config.yaml'

def load_members_config():
    """멤버 구성 정보 로드"""
    try:
        with open(MEMBERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('members', [])
    except Exception as e:
        print(f"멤버 구성 정보 로드 중 오류: {e}")
        return []

def find_discord_id_by_character(members, character_name):
    """특정 캐릭터 이름을 메인 캐릭터로 등록한 멤버의 discord_id 찾기"""
    for member in members:
        main_characters = member.get('main_characters', [])
        if character_name in main_characters:
            return member.get('discord_id'), member
    return None, None

def find_member_by_discord_id(members, discord_id):
    """디스코드 ID로 멤버 찾기"""
    for member in members:
        if member.get('discord_id') == discord_id:
            return member
    return None

def find_member_by_id(members, member_id):
    """멤버 ID로 멤버 찾기"""
    for member in members:
        if member.get('id') == member_id:
            return member
    return None

def fetch_character_siblings(character_name):
    """캐릭터의 계정 내 다른 캐릭터 정보 가져오기"""
    try:
        # URL 인코딩
        encoded_name = urllib.parse.quote(character_name)
        
        # API 엔드포인트 URL
        url = f'https://developer-lostark.game.onstove.com/characters/{encoded_name}/siblings'
        
        # API 호출 헤더
        headers = {
            'accept': 'application/json',
            'authorization': f'bearer {API_KEY}'
        }
        
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

def filter_main_characters(all_characters, main_character_names):
    """메인 캐릭터 목록에 있는 캐릭터만 필터링"""
    if not main_character_names:
        return all_characters
        
    filtered_chars = []
    
    for char in all_characters:
        char_name = char.get('CharacterName', '')
        if char_name in main_character_names:
            filtered_chars.append(char)
            
    return filtered_chars

def fetch_all_characters_for_member(member):
    """멤버의 모든 메인 캐릭터에 대해 데이터 조회 및 통합"""
    if not member or not member.get('main_characters'):
        return []
    
    all_characters = []
    processed_chars = set()  # 이미 처리한 캐릭터 추적
    
    main_characters = member.get('main_characters', [])
    
    print(f"멤버 {member.get('id')}의 메인 캐릭터 {len(main_characters)}개에 대해 조회합니다...")
    
    for char_name in main_characters:
        # 이미 처리한 캐릭터는 건너뜀
        if char_name in processed_chars:
            continue
            
        print(f"  - '{char_name}' 캐릭터 정보 조회 중...")
        siblings_data = fetch_character_siblings(char_name)
        
        if siblings_data:
            # 아직 처리하지 않은 캐릭터만 추가
            for char in siblings_data:
                char_name = char.get('CharacterName', '')
                if char_name not in processed_chars:
                    all_characters.append(char)
                    processed_chars.add(char_name)
            
            print(f"    → {len(siblings_data)}개 캐릭터 정보 로드됨")
        else:
            print(f"    → 캐릭터 정보를 찾을 수 없습니다.")
    
    # 아이템 레벨 순으로 정렬
    sorted_characters = sorted(
        all_characters,
        key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
        reverse=True
    )
    
    print(f"총 {len(sorted_characters)}개의 고유 캐릭터 정보를 로드했습니다.")
    return sorted_characters

def main():
    parser = argparse.ArgumentParser(description='로스트아크 캐릭터 정보 조회')
    parser.add_argument('--character', type=str, help='조회할 캐릭터 이름')
    parser.add_argument('--discord-id', type=str, help='디스코드 ID로 멤버 조회')
    parser.add_argument('--member-id', type=str, help='멤버 ID로 조회 (예: 드워프, 하프)')
    parser.add_argument('--save', action='store_true', help='결과를 JSON 파일로 저장')
    parser.add_argument('--main-only', action='store_true', help='메인 캐릭터만 표시')
    parser.add_argument('--raid-manager', action='store_true', help='raid_manager.py의 로직 테스트')
    parser.add_argument('--list-members', action='store_true', help='멤버 목록 표시')
    
    args = parser.parse_args()
    character_name = args.character
    discord_id = args.discord_id
    member_id = args.member_id
    save_to_file = args.save
    main_only = args.main_only
    raid_manager_test = args.raid_manager
    list_members = args.list_members
    
    if not API_KEY:
        print("LOSTARK_API_KEY가 .env.secret 파일에 설정되어 있지 않습니다.")
        return
    
    # 멤버 구성 정보 로드
    members = load_members_config()
    if not members:
        print("멤버 정보를 로드하지 못했습니다.")
        return
        
    # 멤버 목록 출력 옵션
    if list_members:
        print("\n## 멤버 목록:")
        for idx, member in enumerate(members, 1):
            active_status = "✅" if member.get('active', False) else "❌"
            main_chars = ", ".join(member.get('main_characters', []))
            print(f"{idx}. [{active_status}] {member.get('id')} - 디스코드: {member.get('discord_name')} ({member.get('discord_id')})")
            if main_chars:
                print(f"   메인 캐릭터: {main_chars}")
            print()
        return
    
    # 멤버 정보 및 캐릭터 조회 방식 결정
    member_info = None
    siblings_data = None
    
    if discord_id:
        # 디스코드 ID로 조회
        member_info = find_member_by_discord_id(members, discord_id)
        if member_info:
            print(f"디스코드 ID '{discord_id}'로 멤버 '{member_info.get('id')}'를 찾았습니다.")
            siblings_data = fetch_all_characters_for_member(member_info)
        else:
            print(f"디스코드 ID '{discord_id}'와 일치하는 멤버를 찾을 수 없습니다.")
            return
            
    elif member_id:
        # 멤버 ID로 조회
        member_info = find_member_by_id(members, member_id)
        if member_info:
            print(f"멤버 ID '{member_id}'로 멤버를 찾았습니다. (디스코드: {member_info.get('discord_name')})")
            siblings_data = fetch_all_characters_for_member(member_info)
        else:
            print(f"멤버 ID '{member_id}'와 일치하는 멤버를 찾을 수 없습니다.")
            return
            
    elif character_name:
        # 특정 캐릭터로 조회
        print(f"'{character_name}' 캐릭터 정보 조회 중...")
        
        # 멤버 정보 찾기
        discord_id, member_info = find_discord_id_by_character(members, character_name)
        
        # 캐릭터 정보 가져오기
        siblings_data = fetch_character_siblings(character_name)
    else:
        print("캐릭터 이름(--character), 디스코드 ID(--discord-id) 또는 멤버 ID(--member-id) 중 하나를 지정해야 합니다.")
        return

    if siblings_data:
        # 아이템 레벨 순으로 정렬 (디스코드 ID나 멤버 ID로 조회한 경우는 이미 정렬됨)
        if character_name and not (discord_id or member_id):
            sorted_characters = sorted(
                siblings_data,
                key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
                reverse=True
            )
        else:
            sorted_characters = siblings_data
        
        # 멤버 정보 출력
        if member_info:
            member_id = member_info.get('id', '알 수 없음')
            discord_name = member_info.get('discord_name', '알 수 없음')
            discord_id = member_info.get('discord_id', '')
            main_characters = member_info.get('main_characters', [])
            active_status = "활성" if member_info.get('active', False) else "비활성"
            
            print(f"\n## 멤버 정보:")
            print(f"ID: {member_id}")
            print(f"디스코드: {discord_name} ({discord_id})")
            print(f"메인 캐릭터: {', '.join(main_characters)}")
            print(f"활성 상태: {active_status}")
            print("="*60)
        
        # raid_manager.py 로직 테스트 모드
        if raid_manager_test and member_info:
            main_characters = member_info.get('main_characters', [])
            filtered_characters = filter_main_characters(sorted_characters, main_characters)
            
            print(f"\n### raid_manager.py 로직 테스트 결과")
            print(f"멤버 {member_info.get('id')}({discord_id})의 메인 캐릭터 필터링: {main_characters}")
            
            for char in filtered_characters:
                char_name = char.get('CharacterName', '')
                item_level = char.get('ItemMaxLevel', '0')
                print(f"  - 메인 캐릭터 '{char_name}' 추가됨 (레벨: {item_level})")
                
            # 서포터/딜러 구분
            support_chars = []
            dealer_chars = []
            for char in filtered_characters:
                class_name = char.get('CharacterClassName', '')
                char_name = char.get('CharacterName', '')
                item_level = char.get('ItemMaxLevel', '0')
                
                if class_name in ['바드', '홀리나이트', '도화가']:
                    support_chars.append({
                        'name': char_name,
                        'class': class_name,
                        'level': item_level
                    })
                else:
                    dealer_chars.append({
                        'name': char_name,
                        'class': class_name,
                        'level': item_level
                    })
            
            print(f"\n### 서포터/딜러 구분 결과")
            print(f"- 서포터: {len(support_chars)}개")
            for char in support_chars:
                print(f"  - {char['name']} ({char['class']}, {char['level']})")
                
            print(f"- 딜러: {len(dealer_chars)}개")
            for char in dealer_chars:
                print(f"  - {char['name']} ({char['class']}, {char['level']})")
            
            print("="*60)
            
        # main_only 옵션이 켜져 있으면 메인 캐릭터만 필터링
        if main_only and member_info:
            main_characters = member_info.get('main_characters', [])
            filtered_chars = filter_main_characters(sorted_characters, main_characters)
            
            print(f"\n메인 캐릭터로 등록된 {len(filtered_chars)}개의 캐릭터:")
            sorted_characters = filtered_chars
        else:
            print(f"\n계정에 {len(sorted_characters)}개의 캐릭터가 있습니다.")
            
        print("="*60)
        
        # 캐릭터 정보 출력
        for i, char in enumerate(sorted_characters, 1):
            char_name = char.get('CharacterName', '알 수 없음')
            char_class = char.get('CharacterClassName', '알 수 없음')
            char_server = char.get('ServerName', '알 수 없음')
            item_level = char.get('ItemMaxLevel', '0')
            
            # 메인 캐릭터 표시
            main_indicator = ""
            if member_info and char_name in member_info.get('main_characters', []):
                main_indicator = " [메인]"
                
            print(f"{i}. {char_name}{main_indicator} ({char_class}) - {char_server} 서버, 아이템 레벨: {item_level}")
        
        print("="*60)
        
        # 결과를 파일로 저장
        if save_to_file:
            # 저장할 파일명 결정
            if member_info:
                file_name = member_info.get('id', 'unknown')
            elif character_name:
                file_name = character_name
            else:
                file_name = "characters"
                
            output_file = f"../data/{file_name}_characters.json"
            os.makedirs('../data', exist_ok=True)
            
            # main_only 옵션에 따라 저장할 데이터 선택
            save_data = sorted_characters
            
            # 멤버 정보와 함께 저장
            if member_info:
                # 캐릭터 데이터를 딕셔너리 형태로 변경
                save_dict = {
                    "id": member_info.get('id', ''),
                    "discord_name": member_info.get('discord_name', ''),
                    "discord_id": member_info.get('discord_id', ''),
                    "characters": save_data
                }
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(save_dict, f, ensure_ascii=False, indent=2)
            else:
                # 기존 방식대로 캐릭터 목록만 저장
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
                    
            print(f"\n캐릭터 정보가 {output_file} 파일에 저장되었습니다.")
    else:
        print(f"캐릭터 정보를 가져오는데 실패했습니다.")

if __name__ == "__main__":
    main() 