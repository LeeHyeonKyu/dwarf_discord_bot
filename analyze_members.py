#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
멤버 캐릭터 정보 분석 스크립트.

이 스크립트는 수집된 멤버 캐릭터 정보를 분석하고 요약합니다.
"""

import yaml
from typing import Dict, List, Any
import os

def load_data(file_path: str = "data/members_character_info.yaml") -> Dict[str, List[Dict[str, Any]]]:
    """
    멤버 캐릭터 정보 파일을 로드합니다.
    
    Args:
        file_path: 데이터 파일 경로
        
    Returns:
        멤버 캐릭터 정보
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file) or {}

def analyze_member_data(data: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    멤버 캐릭터 정보를 분석하고 출력합니다.
    
    Args:
        data: 멤버 캐릭터 정보
    """
    print(f"\n{'=' * 50}")
    print(f"멤버 캐릭터 정보 분석")
    print(f"{'=' * 50}")
    
    total_members = len(data)
    total_characters = sum(len(chars) for chars in data.values())
    
    print(f"\n총 {total_members}명의 멤버, {total_characters}개의 캐릭터 정보가 있습니다.\n")
    
    # 서버별 캐릭터 분포
    server_distribution = {}
    for member_id, characters in data.items():
        for char in characters:
            server_name = char.get('ServerName', '알 수 없음')
            server_distribution[server_name] = server_distribution.get(server_name, 0) + 1
    
    print(f"\n서버별 캐릭터 분포:")
    for server, count in sorted(server_distribution.items(), key=lambda x: x[1], reverse=True):
        print(f"  {server}: {count}캐릭터 ({count/total_characters*100:.1f}%)")
    
    # 클래스별 캐릭터 분포
    class_distribution = {}
    for member_id, characters in data.items():
        for char in characters:
            class_name = char.get('CharacterClassName', '알 수 없음')
            class_distribution[class_name] = class_distribution.get(class_name, 0) + 1
    
    print(f"\n클래스별 캐릭터 분포:")
    for class_name, count in sorted(class_distribution.items(), key=lambda x: x[1], reverse=True):
        print(f"  {class_name}: {count}캐릭터 ({count/total_characters*100:.1f}%)")
    
    # 아이템 레벨 통계
    all_levels = []
    for member_id, characters in data.items():
        for char in characters:
            item_level_str = char.get('ItemMaxLevel', '0')
            try:
                # 쉼표 제거하고 숫자로 변환
                item_level = float(item_level_str.replace(',', ''))
                all_levels.append(item_level)
            except (ValueError, TypeError):
                continue
    
    if all_levels:
        average_level = sum(all_levels) / len(all_levels)
        max_level = max(all_levels)
        min_level = min(all_levels)
        
        print(f"\n아이템 레벨 통계:")
        print(f"  평균 레벨: {average_level:.2f}")
        print(f"  최고 레벨: {max_level:.2f}")
        print(f"  최저 레벨: {min_level:.2f}")
        
        # 레벨대별 분포
        level_ranges = {
            "1600~1620": 0,
            "1620~1640": 0,
            "1640~1660": 0,
            "1660~1680": 0,
            "1680~1700": 0,
            "1700 이상": 0
        }
        
        for level in all_levels:
            if 1600 <= level < 1620:
                level_ranges["1600~1620"] += 1
            elif 1620 <= level < 1640:
                level_ranges["1620~1640"] += 1
            elif 1640 <= level < 1660:
                level_ranges["1640~1660"] += 1
            elif 1660 <= level < 1680:
                level_ranges["1660~1680"] += 1
            elif 1680 <= level < 1700:
                level_ranges["1680~1700"] += 1
            elif level >= 1700:
                level_ranges["1700 이상"] += 1
        
        print(f"\n레벨대별 캐릭터 분포:")
        for range_name, count in level_ranges.items():
            print(f"  {range_name}: {count}캐릭터 ({count/len(all_levels)*100:.1f}%)")
    
    # 멤버별 캐릭터 수 및 최고 레벨
    print(f"\n멤버별 캐릭터 정보:")
    for member_id, characters in sorted(data.items(), key=lambda x: len(x[1]), reverse=True):
        char_count = len(characters)
        if char_count == 0:
            continue
        
        # 최고 레벨 캐릭터 찾기
        try:
            highest_char = max(
                characters,
                key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', ''))
            )
            highest_level = highest_char.get('ItemMaxLevel', '0')
            highest_name = highest_char.get('CharacterName', '알 수 없음')
            highest_class = highest_char.get('CharacterClassName', '알 수 없음')
            
            print(f"  {member_id}: {char_count}캐릭터, 최고 레벨: {highest_name}({highest_class}) - {highest_level}")
        except (ValueError, TypeError):
            print(f"  {member_id}: {char_count}캐릭터, 레벨 정보 없음")
    
    print(f"\n{'=' * 50}\n")

def main() -> None:
    """
    메인 함수입니다.
    """
    if not os.path.exists("data/members_character_info.yaml"):
        print("캐릭터 정보 파일이 존재하지 않습니다.")
        return
    
    data = load_data()
    analyze_member_data(data)

if __name__ == "__main__":
    main() 