#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
멤버 캐릭터 정보 수집 스크립트.

이 스크립트는 모든 멤버의 로스트아크 캐릭터 정보를 수집하고 YAML 파일로 저장합니다.
"""

import argparse
import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, '.')  # 프로젝트 루트 디렉토리를 Python 경로에 추가

from services.lostark_service import LostarkService, collect_and_save_character_info


async def async_main(min_level: float = 1600.0, output_path: Optional[str] = None) -> None:
    """
    메인 비동기 함수입니다.
    
    Args:
        min_level: 필터링할 최소 아이템 레벨
        output_path: 출력 파일 경로
    """
    # 로스트아크 서비스 인스턴스 생성
    service = LostarkService()
    
    # 멤버 캐릭터 정보 수집
    print(f"캐릭터 정보 수집 중 (최소 레벨: {min_level})...")
    data = await service.collect_all_members_characters_async(min_level=min_level)
    
    # 캐릭터 수 계산
    total_members = len(data)
    total_characters = sum(len(chars) for chars in data.values())
    
    # 결과 저장
    if output_path:
        service.save_members_characters_info(data, output_path=output_path)
    else:
        service.save_members_characters_info(data)
    
    print(f"캐릭터 정보 수집 완료!")
    print(f"총 {total_members}명의 멤버, {total_characters}개의 캐릭터 정보를 수집했습니다.")


def main() -> None:
    """
    명령줄 인터페이스를 제공하는 메인 함수입니다.
    """
    # 명령줄 인자 파서 설정
    parser = argparse.ArgumentParser(description='로스트아크 멤버 캐릭터 정보 수집')
    parser.add_argument(
        '--min-level',
        type=float,
        default=1600.0,
        help='필터링할 최소 아이템 레벨 (기본값: 1600.0)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='출력 파일 경로 (기본값: data/members_character_info.yaml)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 로깅 활성화'
    )
    
    # 명령줄 인자 파싱
    args = parser.parse_args()
    
    # 로깅 설정
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 비동기 함수 실행
    asyncio.run(async_main(min_level=args.min_level, output_path=args.output))


if __name__ == "__main__":
    main() 