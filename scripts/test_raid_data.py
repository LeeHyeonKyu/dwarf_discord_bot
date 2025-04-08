#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 데이터 파일 관리 기능 테스트 스크립트.

이 스크립트는 레이드 스레드별 데이터 파일 생성 및 관리 기능을 테스트합니다.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, List, Optional

# 프로젝트 루트 디렉토리를 파이썬 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.discord_utils import (
    init_raid_data_directory,
    create_raid_data_file,
    load_raid_data,
    save_raid_data,
    add_participant_to_raid,
    remove_participant_from_raid,
    get_raid_participants,
    update_raid_status,
    add_command_to_raid_history,
    get_raid_command_history
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_raid_data() -> Dict[str, Any]:
    """
    샘플 레이드 데이터를 생성합니다.
    
    Returns:
        샘플 레이드 데이터
    """
    return {
        "name": "노기르 카제로스",
        "description": "1막 노말",
        "min_level": 1620.0,
        "max_level": 1700.0,
        "members": 8,
        "elapsed_time": 120,
        "day_of_week": "목",
        "time": "19:30"
    }


def create_sample_participant(member_id: str, character_name: str, character_class: str, level: float) -> Dict[str, Any]:
    """
    샘플 참가자 데이터를 생성합니다.
    
    Args:
        member_id: 멤버 ID
        character_name: 캐릭터명
        character_class: 직업명
        level: 아이템 레벨
        
    Returns:
        샘플 참가자 데이터
    """
    return {
        "member_id": member_id,
        "character_name": character_name,
        "class": character_class,
        "level": level
    }


def create_sample_command(user_id: str, command_type: str, role: str, round_num: Optional[int] = None, round_edit: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    샘플 커맨드 데이터를 생성합니다.
    
    Args:
        user_id: 사용자 ID
        command_type: 커맨드 타입 ("add", "remove", "edit")
        role: 역할 ("sup", "dps")
        round_num: 라운드 번호 (None 가능)
        round_edit: 라운드 편집 정보 (선택 사항)
        
    Returns:
        샘플 커맨드 데이터
    """
    command_data = {
        "user": user_id,
        "command": command_type,
        "role": role,
        "round": round_num
    }
    
    if round_edit:
        command_data["round_edit"] = round_edit
    
    return command_data


def test_create_raid_data_file() -> int:
    """
    레이드 데이터 파일 생성 기능을 테스트합니다.
    
    Returns:
        테스트가 생성한 스레드 ID (모의값)
    """
    logger.info("테스트: 레이드 데이터 파일 생성")
    
    # 디렉토리 초기화
    init_raid_data_directory()
    
    # 테스트용 스레드 ID
    thread_id = 123456789
    
    # 샘플 레이드 데이터
    raid_data = create_sample_raid_data()
    
    # 파일 생성
    file_path = create_raid_data_file(thread_id, raid_data)
    logger.info(f"생성된 파일: {file_path}")
    
    # 생성된 파일 확인
    if os.path.exists(file_path):
        logger.info("파일 생성 성공!")
    else:
        logger.error("파일 생성 실패!")
    
    return thread_id


def test_add_participants(thread_id: int) -> None:
    """
    레이드 참가자 추가 기능을 테스트합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
    """
    logger.info("테스트: 레이드 참가자 추가")
    
    # 샘플 참가자 데이터
    participants = [
        create_sample_participant("user1", "캐릭터1", "버서커", 1650.0),
        create_sample_participant("user2", "캐릭터2", "디스트로이어", 1630.0),
        create_sample_participant("user3", "캐릭터3", "소서리스", 1680.0),
        create_sample_participant("user1", "캐릭터4", "홀리나이트", 1660.0)
    ]
    
    # 참가자 추가
    for participant in participants:
        success = add_participant_to_raid(thread_id, participant)
        logger.info(f"참가자 추가 {'성공' if success else '실패'}: {participant['member_id']} - {participant['character_name']}")
    
    # 참가자 목록 확인
    show_participants(thread_id)


def test_remove_participant(thread_id: int) -> None:
    """
    레이드 참가자 제거 기능을 테스트합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
    """
    logger.info("테스트: 레이드 참가자 제거")
    
    # 특정 캐릭터 제거
    success = remove_participant_from_raid(thread_id, "user1", "캐릭터1")
    logger.info(f"참가자 제거 {'성공' if success else '실패'}: user1 - 캐릭터1")
    
    # 참가자 목록 확인
    show_participants(thread_id)
    
    # 멤버의 모든 캐릭터 제거
    success = remove_participant_from_raid(thread_id, "user2")
    logger.info(f"멤버 참가 제거 {'성공' if success else '실패'}: user2")
    
    # 참가자 목록 확인
    show_participants(thread_id)


def test_update_status(thread_id: int) -> None:
    """
    레이드 상태 업데이트 기능을 테스트합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
    """
    logger.info("테스트: 레이드 상태 업데이트")
    
    # 상태 업데이트
    statuses = ["in_progress", "completed", "closed"]
    
    for status in statuses:
        success = update_raid_status(thread_id, status)
        logger.info(f"상태 업데이트 {'성공' if success else '실패'}: {status}")
        
        # 업데이트된 데이터 확인
        raid_data = load_raid_data(thread_id)
        if raid_data:
            logger.info(f"현재 상태: {raid_data.get('status')}")
            logger.info(f"업데이트 시간: {raid_data.get('updated_at')}")


def show_participants(thread_id: int) -> None:
    """
    현재 레이드 참가자 목록을 출력합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
    """
    participants = get_raid_participants(thread_id)
    logger.info(f"현재 참가자 수: {len(participants)}")
    
    for p in participants:
        logger.info(f"- {p.get('member_id')} - {p.get('character_name')} ({p.get('class')}) - {p.get('level')}")


def test_add_commands(thread_id: int) -> None:
    """
    레이드 커맨드 히스토리 추가 기능을 테스트합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
    """
    logger.info("테스트: 레이드 커맨드 히스토리 추가")
    
    # 샘플 커맨드 데이터
    commands = [
        create_sample_command("user1", "add", "dps", 1),
        create_sample_command("user2", "add", "sup", 2),
        create_sample_command("user3", "remove", "dps", 1),
        create_sample_command("user1", "edit", "dps", None, {"round_index": 1, "start_time": "목 19:30"})
    ]
    
    # 커맨드 추가
    for cmd in commands:
        success = add_command_to_raid_history(thread_id, cmd)
        logger.info(f"커맨드 추가 {'성공' if success else '실패'}: {cmd['user']} - {cmd['command']} - {cmd['role']}")
    
    # 커맨드 히스토리 확인
    show_command_history(thread_id)


def show_command_history(thread_id: int) -> None:
    """
    현재 레이드 커맨드 히스토리를 출력합니다.
    
    Args:
        thread_id: 레이드 스레드 ID
    """
    commands = get_raid_command_history(thread_id)
    logger.info(f"현재 커맨드 히스토리 개수: {len(commands)}")
    
    for cmd in commands:
        cmd_info = f"- {cmd.get('timestamp', '알 수 없음')} | {cmd.get('user')} | {cmd.get('command')} | {cmd.get('role')}"
        
        if cmd.get('round') is not None:
            cmd_info += f" | 라운드: {cmd.get('round')}"
        
        round_edit = cmd.get('round_edit')
        if round_edit:
            cmd_info += f" | 라운드 편집: {round_edit.get('round_index')} -> {round_edit.get('start_time')}"
        
        logger.info(cmd_info)


def main() -> None:
    """
    메인 함수.
    """
    parser = argparse.ArgumentParser(description='레이드 데이터 파일 관리 기능 테스트')
    parser.add_argument('--thread-id', type=int, help='기존 스레드 ID (없으면 새로 생성)')
    
    args = parser.parse_args()
    
    # 스레드 ID 가져오기 또는 새로 생성
    thread_id = args.thread_id if args.thread_id else test_create_raid_data_file()
    
    # 참가자 추가 테스트
    test_add_participants(thread_id)
    
    # 참가자 제거 테스트
    test_remove_participant(thread_id)
    
    # 상태 업데이트 테스트
    test_update_status(thread_id)
    
    # 커맨드 히스토리 추가 테스트
    test_add_commands(thread_id)
    
    logger.info("모든 테스트가 완료되었습니다.")


if __name__ == "__main__":
    main() 