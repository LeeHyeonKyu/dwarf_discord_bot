import json
import os
from tabulate import tabulate
from collections import Counter

# 데이터 파일 경로
data_path = 'data/member_characters.json'

# 데이터 파일이 존재하는지 확인
if not os.path.exists(data_path):
    print(f"오류: {data_path} 파일이 존재하지 않습니다.")
    exit(1)

# 데이터 로드
with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"총 {len(data)}명의 멤버 데이터를 로드했습니다.\n")

# 클래스 별 통계
all_classes = []
for discord_id, member_data in data.items():
    characters = member_data.get('characters', [])
    for character in characters:
        char_class = character.get('CharacterClassName')
        if char_class:
            all_classes.append(char_class)

class_counter = Counter(all_classes)
total_characters = len(all_classes)

# 클래스 분포 테이블 생성
class_table = []
for class_name, count in sorted(class_counter.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / total_characters) * 100 if total_characters > 0 else 0
    class_table.append([class_name, count, f"{percentage:.1f}%"])

print("== 캐릭터 클래스 분포 ==")
print(tabulate(class_table, headers=["클래스", "캐릭터 수", "비율"], tablefmt="grid"))
print()

# 아이템 레벨 구간별 분포
level_ranges = {
    "1700 이상": 0,
    "1650 ~ 1699": 0,
    "1600 ~ 1649": 0,
    "1550 ~ 1599": 0,
    "1500 ~ 1549": 0,
    "1400 ~ 1499": 0,
    "1300 ~ 1399": 0,
    "1000 ~ 1299": 0,
    "1 ~ 999": 0,
    "0": 0
}

for discord_id, member_data in data.items():
    characters = member_data.get('characters', [])
    for character in characters:
        item_level_str = character.get('ItemMaxLevel', '0')
        try:
            item_level = float(item_level_str.replace(',', ''))
            if item_level >= 1700:
                level_ranges["1700 이상"] += 1
            elif 1650 <= item_level < 1700:
                level_ranges["1650 ~ 1699"] += 1
            elif 1600 <= item_level < 1650:
                level_ranges["1600 ~ 1649"] += 1
            elif 1550 <= item_level < 1600:
                level_ranges["1550 ~ 1599"] += 1
            elif 1500 <= item_level < 1550:
                level_ranges["1500 ~ 1549"] += 1
            elif 1400 <= item_level < 1500:
                level_ranges["1400 ~ 1499"] += 1
            elif 1300 <= item_level < 1400:
                level_ranges["1300 ~ 1399"] += 1
            elif 1000 <= item_level < 1300:
                level_ranges["1000 ~ 1299"] += 1
            elif 1 <= item_level < 1000:
                level_ranges["1 ~ 999"] += 1
            else:
                level_ranges["0"] += 1
        except ValueError:
            level_ranges["0"] += 1

# 아이템 레벨 분포 테이블 생성
level_table = []
for level_range, count in level_ranges.items():
    percentage = (count / total_characters) * 100 if total_characters > 0 else 0
    level_table.append([level_range, count, f"{percentage:.1f}%"])

print("== 아이템 레벨 분포 ==")
print(tabulate(level_table, headers=["아이템 레벨 구간", "캐릭터 수", "비율"], tablefmt="grid"))
print()

# 멤버별 최고 아이템 레벨 캐릭터
member_top_chars = []
for discord_id, member_data in data.items():
    discord_name = member_data.get('discord_name', '알 수 없음')
    characters = member_data.get('characters', [])
    if not characters:
        continue
    
    # 아이템 레벨 기준 정렬
    sorted_characters = sorted(
        characters,
        key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
        reverse=True
    )
    
    top_char = sorted_characters[0]
    char_name = top_char.get('CharacterName', '알 수 없음')
    char_class = top_char.get('CharacterClassName', '알 수 없음')
    item_level = top_char.get('ItemMaxLevel', '0')
    char_count = len(characters)
    
    member_top_chars.append([discord_name, char_name, char_class, item_level, char_count])

# 아이템 레벨 기준 정렬
member_top_chars.sort(key=lambda x: float(x[3].replace(',', '')), reverse=True)

print("== 멤버별 최고 레벨 캐릭터 ==")
print(tabulate(member_top_chars, headers=["디스코드 이름", "캐릭터 이름", "클래스", "아이템 레벨", "보유 캐릭터 수"], tablefmt="grid"))
print()

# 서버별 캐릭터 분포
servers = {}
for discord_id, member_data in data.items():
    characters = member_data.get('characters', [])
    for character in characters:
        server = character.get('ServerName', '알 수 없음')
        if server not in servers:
            servers[server] = 0
        servers[server] += 1

# 서버 분포 테이블 생성
server_table = []
for server, count in sorted(servers.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / total_characters) * 100 if total_characters > 0 else 0
    server_table.append([server, count, f"{percentage:.1f}%"])

print("== 서버별 분포 ==")
print(tabulate(server_table, headers=["서버", "캐릭터 수", "비율"], tablefmt="grid"))
print()

# 요약 정보
print(f"== 종합 요약 ==")
print(f"총 멤버 수: {len(data)}명")
print(f"총 캐릭터 수: {total_characters}개")
print(f"평균 캐릭터 보유 수: {total_characters / len(data):.1f}개/멤버")
print(f"멤버당 최소 캐릭터 수: {min([len(member_data.get('characters', [])) for _, member_data in data.items()])}개")
print(f"멤버당 최대 캐릭터 수: {max([len(member_data.get('characters', [])) for _, member_data in data.items()])}개")

# 1650 이상 고레벨 캐릭터 수
high_level_chars = level_ranges["1700 이상"] + level_ranges["1650 ~ 1699"]
high_level_percentage = (high_level_chars / total_characters) * 100 if total_characters > 0 else 0
print(f"1650 이상 고레벨 캐릭터 비율: {high_level_percentage:.1f}% ({high_level_chars}개)")

# 가장 많은/적은 클래스
most_common_class = class_counter.most_common(1)[0] if class_counter else ('없음', 0)
least_common_class = class_counter.most_common()[-1] if class_counter else ('없음', 0)
print(f"가장 많은 클래스: {most_common_class[0]} ({most_common_class[1]}개)")
print(f"가장 적은 클래스: {least_common_class[0]} ({least_common_class[1]}개)")

# 결과 파일에 저장
with open('data/member_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(f"멤버 캐릭터 분석 보고서\n")
    f.write(f"====================\n\n")
    f.write(f"총 멤버 수: {len(data)}명\n")
    f.write(f"총 캐릭터 수: {total_characters}개\n")
    f.write(f"평균 캐릭터 보유 수: {total_characters / len(data):.1f}개/멤버\n")
    f.write(f"1650 이상 고레벨 캐릭터 비율: {high_level_percentage:.1f}% ({high_level_chars}개)\n\n")
    
    f.write("== 멤버별 최고 레벨 캐릭터 ==\n")
    f.write(tabulate(member_top_chars, headers=["디스코드 이름", "캐릭터 이름", "클래스", "아이템 레벨", "보유 캐릭터 수"], tablefmt="grid"))
    f.write("\n\n")
    
    f.write("== 캐릭터 클래스 분포 ==\n")
    f.write(tabulate(class_table, headers=["클래스", "캐릭터 수", "비율"], tablefmt="grid"))
    f.write("\n\n")
    
    f.write("== 아이템 레벨 분포 ==\n")
    f.write(tabulate(level_table, headers=["아이템 레벨 구간", "캐릭터 수", "비율"], tablefmt="grid"))
    f.write("\n\n")
    
    f.write("== 서버별 분포 ==\n")
    f.write(tabulate(server_table, headers=["서버", "캐릭터 수", "비율"], tablefmt="grid"))

print(f"\n분석 결과가 data/member_analysis.txt 파일에 저장되었습니다.") 