#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 스케줄 업데이트 및 메시지 수정 테스트 스크립트.

이 스크립트는 레이드 명령어 처리 후 스레드 시작 메시지 업데이트 기능을 테스트합니다.
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import discord
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import MagicMock, AsyncMock, patch

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
    load_raid_schedule,
    format_raid_message,
    update_thread_start_message_with_schedule
)
from utils.config_utils import load_yaml_config

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
    thread_id = 123456789
    
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


async def add_test_commands(thread_id: int, openai_service: OpenAIService) -> None:
    """
    테스트 명령어를 추가합니다.
    
    Args:
        thread_id: 스레드 ID
        openai_service: OpenAI 서비스 인스턴스
    """
    # 테스트 명령어 시나리오
    test_scenarios = [
        # 기본 참가 신청
        {"user_id": "user_1", "command": "추가 1차 딜러"},
        {"user_id": "user_2", "command": "추가 1차 서포터"},
        
        # 동일 유저가 다른 라운드에 중복 신청
        {"user_id": "user_1", "command": "추가 2차 딜러"},
        {"user_id": "user_2", "command": "추가 3차 서포터"},
        
        # 여러 역할 동시 신청
        {"user_id": "user_3", "command": "추가 1차 딜러 2차 서포터"},
        {"user_id": "user_4", "command": "추가 1차 서포터 2차 딜러 3차 딜러"},
        
        # 특정 라운드 일정 수정
        {"user_id": "user_5", "command": "수정 1차 토 21시"},
        
        # 기존 참가 취소
        {"user_id": "user_2", "command": "제거 1차 서포터"},
        {"user_id": "user_3", "command": "제거 1차 딜러"},
        
        # 새로운 참가자 추가 
        {"user_id": "user_6", "command": "추가 1차 딜러 1차 딜러 3차 서포터"},
        {"user_id": "user_7", "command": "추가 2차 서포터"},
        
        # 이미 수정된 일정 재수정
        {"user_id": "user_8", "command": "수정 1차 일 19시"},
        
        # 다른 라운드 일정 수정
        {"user_id": "user_5", "command": "수정 2차 월 20시"},
        {"user_id": "user_8", "command": "수정 3차 수 22시"},
        
        # 참가자가 없는 라운드의 일정 수정
        {"user_id": "user_9", "command": "수정 4차 목 18시"},
        
        # 참가 취소 후 다시 신청
        {"user_id": "user_1", "command": "제거 1차 딜러"},
        {"user_id": "user_1", "command": "추가 1차 서포터"}, 
        
        # 여러 라운드 동시 취소
        {"user_id": "user_4", "command": "제거 1차 서포터 2차 딜러"},
        
        # 라운드 지정 없이 신청 (적절한 라운드에 배정됨)
        {"user_id": "user_10", "command": "추가 딜러"},
        {"user_id": "user_11", "command": "추가 서포터"}
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
        
        # 각 시나리오 후 스케줄 업데이트하여 변화 확인 (실제 시스템에서는 명령어마다 적용)
        if process_raid_commands_and_update_schedule(thread_id, f"테스트_레이드_{thread_id}"):
            logger.info(f"시나리오 실행 후 스케줄 업데이트 성공: {command_text}")
            # 현재 스케줄 상태 로깅
            schedule = get_raid_schedule_for_thread(thread_id)
            rounds_info = []
            for r in schedule.get("rounds", []):
                round_str = f"Round {r.get('idx')}: time={r.get('time')}, dps={len(r.get('dps', []))}, sup={len(r.get('sup', []))}"
                rounds_info.append(round_str)
            logger.info(f"현재 스케줄 상태: {', '.join(rounds_info)}")
        else:
            logger.error(f"시나리오 실행 후 스케줄 업데이트 실패: {command_text}")


def generate_updated_message(thread_id: int, thread_name: str) -> str:
    """
    업데이트된 스레드 메시지를 생성합니다.
    
    Args:
        thread_id: 스레드 ID
        thread_name: 스레드 이름
        
    Returns:
        업데이트된 메시지 내용
    """
    from utils.discord_utils import load_raid_data
    
    # 레이드 데이터 로드
    raid_data = load_raid_data(thread_id)
    if not raid_data:
        logger.error(f"레이드 데이터를 찾을 수 없음: {thread_id}")
        return ""
        
    # 레이드 정보
    raid_info = raid_data.get("raid_info", {})
    
    # 기본 메시지 포맷팅
    base_message = format_raid_message(raid_info)
    
    # 스케줄 업데이트
    process_raid_commands_and_update_schedule(thread_id, thread_name)
    
    # 레이드 스케줄 가져오기
    schedule = get_raid_schedule_for_thread(thread_id)
    rounds = schedule.get("rounds", [])
    
    if not rounds:
        return base_message
        
    # 스케줄 정보 추가
    schedule_message = "\n\n## 레이드 스케줄\n"
    
    for round_data in rounds:
        round_idx = round_data.get("idx", 0)
        round_time = round_data.get("time", "미정")
        dps_list = round_data.get("dps", [])
        sup_list = round_data.get("sup", [])
        
        # 라운드 정보 포맷팅
        schedule_message += f"### Round: {round_idx}\n"
        schedule_message += f"- when: {round_time if round_time else 'None'}\n"
        schedule_message += "- who:\n"
        
        # 서포터 목록
        sup_count = len(sup_list)
        schedule_message += f"  - sup({sup_count}/2): ["
        if sup_list:
            sup_mentions = []
            for sup_id in sup_list:
                sup_mentions.append(f"<@{sup_id}>")
            schedule_message += ", ".join(sup_mentions)
        schedule_message += "]\n"
        
        # DPS 목록
        dps_count = len(dps_list)
        schedule_message += f"  - dps({dps_count}/6): ["
        if dps_list:
            dps_mentions = []
            for dps_id in dps_list:
                dps_mentions.append(f"<@{dps_id}>")
            schedule_message += ", ".join(dps_mentions)
        schedule_message += "]\n"
    
    # 전체 메시지 업데이트
    full_message = base_message + schedule_message
    return full_message


async def test_update_message(thread_id: int, thread_name: str) -> None:
    """
    메시지 업데이트 함수를 테스트합니다.
    
    Args:
        thread_id: 스레드 ID
        thread_name: 스레드 이름
    """
    logger.info("=== 메시지 업데이트 테스트 시작 ===")
    
    try:
        from utils.discord_utils import load_raid_data, update_thread_start_message_with_schedule
        
        # 레이드 데이터 로드
        raid_data = load_raid_data(thread_id)
        if not raid_data:
            logger.error(f"레이드 데이터를 찾을 수 없음: {thread_id}")
            return
            
        # 레이드 정보
        raid_info = raid_data.get("raid_info", {})
        
        # 모의 Thread 객체 생성
        mock_thread = AsyncMock(spec=discord.Thread)
        mock_thread.id = thread_id
        mock_thread.name = thread_name
        
        # mock_message 생성
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.content = "기존 메시지 내용"
        mock_message.author = MagicMock(spec=discord.Member)
        mock_message.author.bot = True
        mock_message.author.id = 123456  # 봇의 ID
        
        # mock_guild 생성
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.me = MagicMock(spec=discord.Member)
        mock_guild.me.id = 123456  # 봇의 ID
        
        # Thread에 guild 설정
        mock_thread.guild = mock_guild
        
        # Thread의 history 메서드가 리턴하는 값 설정
        mock_thread.history.return_value.__aiter__.return_value = [mock_message]
        
        # 시나리오 1: 봇 메시지가 있는 경우
        logger.info("시나리오 1: 봇 메시지 업데이트")
        await update_thread_start_message_with_schedule(mock_thread, raid_info)
        
        # edit이 호출되었는지 확인
        if mock_message.edit.called:
            logger.info("메시지 업데이트 함수가 edit을 호출했습니다.")
            call_args = mock_message.edit.call_args
            logger.info(f"메시지 내용 미리보기: {call_args[1]['content'][:100]}...")
        else:
            logger.error("메시지 업데이트 함수가 edit을 호출하지 않았습니다.")
            
        # 시나리오 2: 봇 메시지가 없는 경우
        logger.info("시나리오 2: 새 메시지 전송")
        mock_thread.history.return_value.__aiter__.return_value = []  # 비어있는 리스트
        await update_thread_start_message_with_schedule(mock_thread, raid_info)
        
        # send가 호출되었는지 확인
        if mock_thread.send.called:
            logger.info("메시지 업데이트 함수가 send를 호출했습니다.")
            call_args = mock_thread.send.call_args
            logger.info(f"메시지 내용 미리보기: {call_args[1]['content'][:100]}...")
        else:
            logger.error("메시지 업데이트 함수가 send를 호출하지 않았습니다.")
        
        logger.info("=== 메시지 업데이트 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"메시지 업데이트 테스트 중 오류 발생: {str(e)}")


async def main() -> None:
    """
    메인 함수.
    """
    parser = argparse.ArgumentParser(description='레이드 메시지 업데이트 테스트')
    parser.add_argument('--thread-id', type=int, help='기존 스레드 ID (없으면 새로 생성)')
    
    args = parser.parse_args()
    
    # 스레드 ID 가져오기 또는 새로 생성
    thread_id = args.thread_id if args.thread_id else create_test_raid_data()
    thread_name = f"테스트_레이드_{thread_id}"
    
    # OpenAI 서비스 초기화
    openai_service = OpenAIService()
    
    # 테스트 명령어 추가
    await add_test_commands(thread_id, openai_service)
    
    # 업데이트된 메시지 생성
    updated_message = generate_updated_message(thread_id, thread_name)
    
    # 업데이트된 메시지 출력
    logger.info("=== 업데이트된 메시지 내용 ===")
    logger.info(updated_message)
    
    # 메시지 업데이트 기능 테스트
    await test_update_message(thread_id, thread_name)
    
    logger.info("모든 테스트가 완료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main()) 