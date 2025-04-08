#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 설정 및 메시지 포맷팅 테스트 스크립트.

이 스크립트는 레이드 설정 로드 및 메시지 포맷팅 기능을 테스트합니다.
"""

import os
import sys
from typing import Dict, List, Any

# 프로젝트 루트 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_utils import load_yaml_config, format_raid_message


def create_mock_raids_config() -> Dict[str, List[Dict[str, Any]]]:
    """
    테스트용 모의 레이드 설정을 생성합니다.
    
    Returns:
        모의 레이드 설정
    """
    return {
        "raids": [
            {
                "name": "노기르",
                "members": 8,
                "min_level": 1660,
                "max_level": 1680,
                "description": "카제로스 1막 노말",
                "elapsed_time": 30
            },
            {
                "name": "하기르",
                "members": 8,
                "min_level": 1680,
                "max_level": None,
                "description": "카제로스 1막 하드",
                "elapsed_time": 30
            },
            {
                "name": "노브렐",
                "members": 8,
                "min_level": 1670,
                "max_level": 1690,
                "description": "카제로스 2막 노말",
                "elapsed_time": 30
            }
        ]
    }


def test_format_raid_message() -> None:
    """
    레이드 메시지 포맷팅 기능을 테스트합니다.
    """
    mock_config = create_mock_raids_config()
    
    print("레이드 메시지 포맷팅 테스트:")
    print("-" * 50)
    
    for raid in mock_config["raids"]:
        print(f"레이드: {raid['name']}")
        message = format_raid_message(raid)
        print(f"포맷팅된 메시지:\n{message}")
        print("-" * 50)


def main() -> None:
    """
    메인 테스트 함수.
    """
    print("레이드 설정 및 메시지 포맷팅 테스트 시작\n")
    
    # 1. 실제 설정 파일이 있으면 로드
    real_config_path = "configs/raids_config.yaml"
    
    if os.path.exists(real_config_path):
        print(f"실제 설정 파일 '{real_config_path}' 로드 테스트:")
        try:
            config = load_yaml_config(real_config_path)
            print(f"성공! {len(config.get('raids', []))}개의 레이드 정보 로드됨.")
            
            # 실제 레이드 정보로 메시지 포맷팅 테스트
            print("\n실제 레이드 정보 메시지 포맷팅 테스트:")
            print("-" * 50)
            
            for raid in config.get('raids', []):
                print(f"레이드: {raid.get('name', '알 수 없음')}")
                message = format_raid_message(raid)
                print(f"포맷팅된 메시지:\n{message}")
                print("-" * 50)
                
        except Exception as e:
            print(f"실패: {str(e)}")
    else:
        print(f"실제 설정 파일 '{real_config_path}'을 찾을 수 없어 모의 데이터로 테스트합니다.")
        test_format_raid_message()
    
    print("\n테스트 완료!")


if __name__ == "__main__":
    main() 