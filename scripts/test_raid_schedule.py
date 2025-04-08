#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 스케줄 관리 테스트 스크립트.

이 스크립트는 레이드 명령어 처리 및 스케줄 업데이트 기능을 테스트합니다.
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from typing import Dict, List, Any, Optional, Tuple

# 프로젝트 루트 디렉토리를 파이썬 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.openai_service import OpenAIService
from utils.discord_utils import (
    init_raid_data_directory,
    create_raid_data_file,
    add_command_to_raid_history,
    get_raid_command_history,
    process_raid_commands_and_update_schedule,
    get_raid_schedule_for_thread,
    load_raid_schedule
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_raid_data() -> int:
    """
    테스트용 레이드 데이터를 생성합니다.
    
    Returns:
        생성된 레이드 스레드 ID
    """
    # 디렉토리 초기화
    init_raid_data_directory()
    
    # 테스트용 스레드 ID
    thread_id = 987654321
    
    # 샘플 레이드 데이터
    raid_data = {
        "name": "발탄",
        "description": "하드",
        "min_level": 1540.0,
        "max_level": 1600.0,
        "members": 8,
        "elapsed_time": 60,
        "day_of_week": "금",
        "time": "20:00"
    }
    
    # 파일 생성
    file_path = create_raid_data_file(thread_id, raid_data)
    logger.info(f"테스트 레이드 데이터 파일 생성: {file_path}")
    
    return thread_id


async def add_test_commands(thread_id: int, openai_service: OpenAIService, user_ids: List[str]) -> None:
    """
    테스트 명령어를 추가합니다.
    
    Args:
        thread_id: 스레드 ID
        openai_service: OpenAI 서비스 인스턴스
        user_ids: 테스트용 사용자 ID 목록
    """
    # 테스트 명령어 시나리오
    test_scenarios = [
        # 1차에 DPS 추가
        {"user_id": user_ids[0], "command": "추가 1차 딜러"},
        {"user_id": user_ids[1], "command": "추가 1차 1딜"},
        {"user_id": user_ids[2], "command": "추가 1차 1딜"},
        # 1차에 서포터 추가
        {"user_id": user_ids[3], "command": "추가 1차 서포터"},
        {"user_id": user_ids[4], "command": "추가 1차 폿"},
        # 2차에 DPS 추가
        {"user_id": user_ids[5], "command": "추가 2차 딜러"},
        {"user_id": user_ids[6], "command": "추가 2차 딜러"},
        # 특정 차수 없이 추가 (자동 배정)
        {"user_id": user_ids[7], "command": "추가 딜러"},
        {"user_id": user_ids[0], "command": "추가 서포터"},  # 다른 역할로 추가 시도
        # 특정 유저 제거
        {"user_id": user_ids[1], "command": "제거 딜러"},
        # 시간 수정
        {"user_id": user_ids[0], "command": "수정 1차 금 21시"},
        {"user_id": user_ids[0], "command": "수정 2차 토 19시 30분"}
    ]
    
    # 각 시나리오 실행
    for scenario in test_scenarios:
        user_id = scenario["user_id"]
        command_text = scenario["command"]
        
        logger.info(f"명령어 실행: {user_id} - {command_text}")
        
        # 명령어 파싱
        commands = await openai_service.parse_raid_command(user_id, command_text)
        if not commands:
            logger.error(f"명령어 파싱 실패: {command_text}")
            continue
            
        # 명령어 검증 및 포맷팅
        valid_commands = await openai_service.validate_and_format_commands(commands, user_id)
        if not valid_commands:
            logger.error(f"유효한 명령어 없음: {command_text}")
            continue
            
        # 히스토리에 명령어 추가
        for cmd in valid_commands:
            if add_command_to_raid_history(thread_id, cmd):
                logger.info(f"명령어 히스토리 추가 성공: {json.dumps(cmd, ensure_ascii=False)}")
            else:
                logger.error(f"명령어 히스토리 추가 실패: {json.dumps(cmd, ensure_ascii=False)}")
                
        # 잠시 대기
        await asyncio.sleep(0.5)


def display_schedule(thread_id: int, thread_name: str) -> None:
    """
    레이드 스케줄을 표시합니다.
    
    Args:
        thread_id: 스레드 ID
        thread_name: 스레드 이름
    """
    # 스케줄 업데이트
    process_raid_commands_and_update_schedule(thread_id, thread_name)
    
    # 스케줄 가져오기
    schedule = get_raid_schedule_for_thread(thread_id)
    
    logger.info(f"=== 레이드 스케줄: {schedule.get('raid_name', '알 수 없음')} ===")
    logger.info(f"스레드: {thread_name} (ID: {thread_id})")
    
    # 라운드 정보
    for round_data in schedule.get("rounds", []):
        round_idx = round_data.get("idx", 0)
        round_time = round_data.get("time", "미정")
        dps_list = round_data.get("dps", [])
        sup_list = round_data.get("sup", [])
        
        logger.info(f"--- {round_idx}차 ---")
        logger.info(f"시간: {round_time if round_time else '미정'}")
        
        # DPS 목록
        logger.info("DPS:")
        if dps_list:
            for i, dps_id in enumerate(dps_list):
                logger.info(f"  {i+1}. {dps_id}")
        else:
            logger.info("  없음")
            
        # 서포터 목록
        logger.info("서포터:")
        if sup_list:
            for i, sup_id in enumerate(sup_list):
                logger.info(f"  {i+1}. {sup_id}")
        else:
            logger.info("  없음")
    
    logger.info(f"마지막 업데이트: {schedule.get('updated_at', '')}")


def display_raid_history(thread_id: int) -> None:
    """
    레이드 명령어 히스토리를 표시합니다.
    
    Args:
        thread_id: 스레드 ID
    """
    history = get_raid_command_history(thread_id)
    
    logger.info(f"=== 레이드 명령어 히스토리 (총 {len(history)}개) ===")
    
    for cmd in history:
        cmd_info = f"- {cmd.get('timestamp', '알 수 없음')} | {cmd.get('user')} | {cmd.get('command')} | {cmd.get('role')}"
        
        if cmd.get('round') is not None:
            cmd_info += f" | 라운드: {cmd.get('round')}"
        
        round_edit = cmd.get('round_edit')
        if round_edit:
            cmd_info += f" | 라운드 편집: {round_edit.get('round_index')} -> {round_edit.get('start_time')}"
        
        logger.info(cmd_info)


def display_all_schedules() -> None:
    """
    전체 레이드 스케줄을 표시합니다.
    """
    # 스케줄 로드
    schedule_data = load_raid_schedule()
    
    logger.info("=== 전체 레이드 스케줄 ===")
    
    # 스레드별 스케줄
    for thread_id, thread_schedule in schedule_data.get("threads", {}).items():
        thread_name = thread_schedule.get("name", "알 수 없음")
        raid_name = thread_schedule.get("raid_name", "알 수 없음")
        
        logger.info(f"--- 스레드: {thread_name} (ID: {thread_id}) ---")
        logger.info(f"레이드: {raid_name}")
        
        # 라운드 정보
        rounds = thread_schedule.get("rounds", [])
        if not rounds:
            logger.info("라운드 정보 없음")
            continue
            
        for round_data in rounds:
            round_idx = round_data.get("idx", 0)
            round_time = round_data.get("time", "미정")
            dps_count = len(round_data.get("dps", []))
            sup_count = len(round_data.get("sup", []))
            
            logger.info(f"  {round_idx}차: 시간={round_time if round_time else '미정'}, DPS={dps_count}명, 서포터={sup_count}명")
        
        logger.info(f"마지막 업데이트: {thread_schedule.get('updated_at', '')}")
        logger.info("")


async def main() -> None:
    """
    메인 함수.
    """
    parser = argparse.ArgumentParser(description='레이드 스케줄 관리 기능 테스트')
    parser.add_argument('--thread-id', type=int, help='기존 스레드 ID (없으면 새로 생성)')
    parser.add_argument('--display-only', action='store_true', help='스케줄만 표시')
    
    args = parser.parse_args()
    
    # 스레드 ID 가져오기 또는 새로 생성
    thread_id = args.thread_id if args.thread_id else create_test_raid_data()
    thread_name = f"테스트_레이드_{thread_id}"
    
    # 표시만 하는 경우
    if args.display_only:
        display_raid_history(thread_id)
        display_schedule(thread_id, thread_name)
        display_all_schedules()
        return
    
    # OpenAI 서비스 초기화
    openai_service = OpenAIService()
    
    # 테스트용 사용자 ID 목록
    user_ids = [f"user_{i}" for i in range(1, 10)]
    
    # 테스트 명령어 추가
    await add_test_commands(thread_id, openai_service, user_ids)
    
    # 히스토리 표시
    display_raid_history(thread_id)
    
    # 스케줄 표시
    display_schedule(thread_id, thread_name)
    
    # 전체 스케줄 표시
    display_all_schedules()
    
    logger.info("모든 테스트가 완료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main()) 