import json
import os
from tabulate import tabulate

# 데이터 파일 경로
data_path = 'data/character_data.json'

# 데이터 파일이 존재하는지 확인
if not os.path.exists(data_path):
    print(f"오류: {data_path} 파일이 존재하지 않습니다.")
    exit(1)

# 데이터 로드
with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 각 멤버별로 데이터 출력
for member_id, member_data in data.items():
    discord_name = member_data.get('discord_name', member_id)
    main_character = member_data.get('main_character', '없음')
    last_updated = member_data.get('last_updated', '알 수 없음')
    characters = member_data.get('characters', [])
    
    # 테이블 형식으로 캐릭터 정보 구성
    table_data = []
    for i, char in enumerate(characters, 1):
        is_main = "✓" if char.get('name') == main_character else ""
        table_data.append([
            i, 
            char.get('name', '알 수 없음'),
            char.get('class', '알 수 없음'),
            char.get('server', '알 수 없음'),
            char.get('item_level', '0'),
            is_main
        ])
    
    # 헤더 및 테이블 출력
    print(f"\n{'='*60}")
    print(f"📊 {discord_name}의 캐릭터 정보")
    print(f"🔹 메인 캐릭터: {main_character}")
    print(f"🔹 마지막 업데이트: {last_updated}")
    print(f"🔹 총 캐릭터 수: {len(characters)}개")
    print(f"{'='*60}")
    
    # 테이블 형식으로 출력
    headers = ["#", "캐릭터명", "클래스", "서버", "아이템 레벨", "메인"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print(f"{'='*60}\n") 