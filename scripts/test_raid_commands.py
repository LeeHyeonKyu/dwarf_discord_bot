#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 명령어 처리 테스트 스크립트.

이 스크립트는 레이드 명령어 처리 기능을 테스트합니다.
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
    get_raid_command_history
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


async def test_command_parsing(openai_service: OpenAIService, user_id: str, command_text: str) -> Optional[List[Dict[str, Any]]]:
    """
    명령어 파싱 기능을 테스트합니다.
    
    Args:
        openai_service: OpenAI 서비스 인스턴스
        user_id: 테스트용 사용자 ID
        command_text: 테스트할 명령어 텍스트
        
    Returns:
        유효한 명령어 리스트 또는 None
    """
    logger.info(f"명령어 파싱 테스트: '{command_text}'")
    
    try:
        # OpenAI 서비스로 명령어 파싱
        commands = await openai_service.parse_raid_command(user_id, command_text)
        
        if not commands:
            logger.error("명령어를 파싱할 수 없습니다.")
            return None
            
        # 명령어 검증 및 포맷팅
        valid_commands = await openai_service.validate_and_format_commands(commands, user_id)
        
        if not valid_commands:
            logger.error("유효한 명령어가 없습니다.")
            return None
        
        # 결과 출력
        logger.info(f"파싱 결과: {json.dumps(valid_commands, ensure_ascii=False, indent=2)}")
        
        return valid_commands
    
    except Exception as e:
        logger.error(f"명령어 파싱 중 오류 발생: {str(e)}")
        return None


async def test_command_processing(thread_id: int, openai_service: OpenAIService, user_id: str, command_text: str) -> None:
    """
    명령어 처리 과정을 테스트합니다. 파싱부터 히스토리 저장까지의 전체 흐름을 테스트합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
        openai_service: OpenAI 서비스 인스턴스
        user_id: 테스트용 사용자 ID
        command_text: 테스트할 명령어 텍스트
    """
    logger.info(f"명령어 처리 테스트: '{command_text}'")
    
    try:
        # 명령어 파싱
        valid_commands = await test_command_parsing(openai_service, user_id, command_text)
        
        if not valid_commands:
            logger.warning("처리할 명령어가 없습니다.")
            return
        
        # 레이드 히스토리에 명령어 추가
        success_count = 0
        for cmd in valid_commands:
            if add_command_to_raid_history(thread_id, cmd):
                success_count += 1
                
        logger.info(f"{success_count}개의 명령어가 처리되었습니다.")
        
        # 커맨드 히스토리 확인
        history = get_raid_command_history(thread_id)
        logger.info(f"현재 커맨드 히스토리 개수: {len(history)}")
        
        # 최신 5개 명령어 출력
        for cmd in history[-5:]:
            cmd_info = f"- {cmd.get('timestamp', '알 수 없음')} | {cmd.get('user')} | {cmd.get('command')} | {cmd.get('role')}"
            
            if cmd.get('round') is not None:
                cmd_info += f" | 라운드: {cmd.get('round')}"
            
            round_edit = cmd.get('round_edit')
            if round_edit:
                cmd_info += f" | 라운드 편집: {round_edit.get('round_index')} -> {round_edit.get('start_time')}"
            
            logger.info(cmd_info)
    
    except Exception as e:
        logger.error(f"명령어 처리 중 오류 발생: {str(e)}")


async def run_tests(thread_id: int) -> None:
    """
    모든 테스트를 실행합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
    """
    # OpenAI 서비스 초기화
    openai_service = OpenAIService()
    
    # 테스트용 사용자 ID
    user_id = "test_user_123"
    
    # 테스트할 명령어 목록
    test_commands = [
        "!추가 1딜 1폿",
        "!추가 1차 1딜",
        "!제거 1딜",
        "!수정 1차 목 9시"
    ]
    
    # 각 명령어 테스트
    for command in test_commands:
        # 명령어 텍스트 추출
        if command.startswith("!"):
            command_text = command[1:].strip()
        else:
            command_text = command.strip()
            
        # 명령어 처리 테스트
        await test_command_processing(thread_id, openai_service, user_id, command_text)
        
        # 테스트 간 간격
        await asyncio.sleep(1)


async def main() -> None:
    """
    메인 함수.
    """
    parser = argparse.ArgumentParser(description='레이드 명령어 처리 기능 테스트')
    parser.add_argument('--thread-id', type=int, help='기존 스레드 ID (없으면 새로 생성)')
    parser.add_argument('--command', type=str, help='테스트할 단일 명령어')
    
    args = parser.parse_args()
    
    # 스레드 ID 가져오기 또는 새로 생성
    thread_id = args.thread_id if args.thread_id else create_test_raid_data()
    
    # 단일 명령어 테스트
    if args.command:
        openai_service = OpenAIService()
        await test_command_processing(thread_id, openai_service, "test_user_123", args.command)
    else:
        # 모든 테스트 실행
        await run_tests(thread_id)
    
    logger.info("모든 테스트가 완료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main()) 