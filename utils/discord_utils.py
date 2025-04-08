#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Discord 관련 공통 유틸리티 모듈.

이 모듈은 Discord 메시지 전송 및 스레드 관리 등 공통 유틸리티 함수를 제공합니다.
"""

import logging
import os
import yaml
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, cast

import discord
from discord.channel import TextChannel
from discord.threads import Thread

from utils.config_utils import format_raid_message

# 로깅 설정
logger = logging.getLogger("discord_utils")

# 레이드 데이터 저장 디렉토리
RAID_DATA_DIR = "data/raids"


def init_raid_data_directory() -> None:
    """
    레이드 데이터 저장 디렉토리를 초기화합니다.
    """
    os.makedirs(RAID_DATA_DIR, exist_ok=True)
    logger.info(f"레이드 데이터 디렉토리 초기화: {RAID_DATA_DIR}")


def create_raid_data_file(thread_id: int, raid: Dict[str, Any]) -> str:
    """
    레이드 스레드 데이터 파일을 생성합니다.
    
    Args:
        thread_id: 스레드 ID
        raid: 레이드 정보
        
    Returns:
        생성된 데이터 파일 경로
    """
    # 디렉토리 확인
    init_raid_data_directory()
    
    # 파일명 생성
    file_path = os.path.join(RAID_DATA_DIR, f"raid_{thread_id}.yaml")
    
    # 초기 데이터 생성
    raid_data = {
        "thread_id": thread_id,
        "raid_info": raid,
        "created_at": datetime.now().isoformat(),
        "participants": [],
        "status": "open",
        "command_history": [],  # 사용자 커맨드 히스토리 추가
        "meta": {
            "name": raid.get("name", "알 수 없음"),
            "description": raid.get("description", ""),
            "min_level": raid.get("min_level", 0),
            "max_level": raid.get("max_level"),
            "members": raid.get("members", 0),
            "elapsed_time": raid.get("elapsed_time", 0)
        }
    }
    
    # 파일 저장
    with open(file_path, 'w', encoding='utf-8') as file:
        yaml.dump(raid_data, file, allow_unicode=True, sort_keys=False)
    
    logger.info(f"레이드 데이터 파일 생성: {file_path}")
    return file_path


def load_raid_data(thread_id: int) -> Optional[Dict[str, Any]]:
    """
    레이드 스레드 데이터 파일을 로드합니다.
    
    Args:
        thread_id: 스레드 ID
        
    Returns:
        레이드 데이터 또는 None
    """
    file_path = os.path.join(RAID_DATA_DIR, f"raid_{thread_id}.yaml")
    
    if not os.path.exists(file_path):
        logger.warning(f"레이드 데이터 파일을 찾을 수 없습니다: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except Exception as e:
        logger.error(f"레이드 데이터 파일 로드 실패: {str(e)}")
        return None


def save_raid_data(thread_id: int, data: Dict[str, Any]) -> bool:
    """
    레이드 스레드 데이터를 파일에 저장합니다.
    
    Args:
        thread_id: 스레드 ID
        data: 저장할 데이터
        
    Returns:
        저장 성공 여부
    """
    file_path = os.path.join(RAID_DATA_DIR, f"raid_{thread_id}.yaml")
    
    try:
        # 디렉토리 확인
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 데이터 저장
        with open(file_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file, allow_unicode=True, sort_keys=False)
        
        logger.info(f"레이드 데이터 저장 완료: {file_path}")
        return True
    except Exception as e:
        logger.error(f"레이드 데이터 저장 실패: {str(e)}")
        return False


def add_participant_to_raid(thread_id: int, participant: Dict[str, Any]) -> bool:
    """
    레이드 참가자를 추가합니다.
    
    Args:
        thread_id: 스레드 ID
        participant: 참가자 정보 (예: {"member_id": "user1", "character_name": "Character1", "class": "Berserker", "level": 1680.0})
        
    Returns:
        성공 여부
    """
    # 레이드 데이터 로드
    raid_data = load_raid_data(thread_id)
    if not raid_data:
        return False
    
    # 참가자 목록 확인
    if "participants" not in raid_data:
        raid_data["participants"] = []
    
    # 기존 참가자 검사 (동일 멤버 ID, 동일 캐릭터명)
    for i, p in enumerate(raid_data["participants"]):
        if (p.get("member_id") == participant.get("member_id") and 
            p.get("character_name") == participant.get("character_name")):
            # 기존 참가자 정보 업데이트
            raid_data["participants"][i] = participant
            return save_raid_data(thread_id, raid_data)
    
    # 새 참가자 추가
    participant["joined_at"] = datetime.now().isoformat()
    raid_data["participants"].append(participant)
    
    # 데이터 저장
    return save_raid_data(thread_id, raid_data)


def remove_participant_from_raid(thread_id: int, member_id: str, character_name: Optional[str] = None) -> bool:
    """
    레이드 참가자를 제거합니다.
    
    Args:
        thread_id: 스레드 ID
        member_id: 멤버 ID
        character_name: 캐릭터명 (None인 경우 해당 멤버의 모든 캐릭터 제거)
        
    Returns:
        성공 여부
    """
    # 레이드 데이터 로드
    raid_data = load_raid_data(thread_id)
    if not raid_data or "participants" not in raid_data:
        return False
    
    if character_name:
        # 특정 캐릭터만 제거
        raid_data["participants"] = [
            p for p in raid_data["participants"] 
            if not (p.get("member_id") == member_id and p.get("character_name") == character_name)
        ]
    else:
        # 멤버의 모든 캐릭터 제거
        raid_data["participants"] = [
            p for p in raid_data["participants"] if p.get("member_id") != member_id
        ]
    
    # 데이터 저장
    return save_raid_data(thread_id, raid_data)


def get_raid_participants(thread_id: int) -> List[Dict[str, Any]]:
    """
    레이드 참가자 목록을 가져옵니다.
    
    Args:
        thread_id: 스레드 ID
        
    Returns:
        참가자 목록
    """
    raid_data = load_raid_data(thread_id)
    if not raid_data or "participants" not in raid_data:
        return []
    
    return raid_data["participants"]


def update_raid_status(thread_id: int, status: str) -> bool:
    """
    레이드 상태를 업데이트합니다.
    
    Args:
        thread_id: 스레드 ID
        status: 레이드 상태 (예: "open", "closed", "in_progress", "completed")
        
    Returns:
        성공 여부
    """
    raid_data = load_raid_data(thread_id)
    if not raid_data:
        return False
    
    raid_data["status"] = status
    raid_data["updated_at"] = datetime.now().isoformat()
    
    return save_raid_data(thread_id, raid_data)


async def send_raid_info(client: discord.Client, channel_id: int, raid: Dict[str, Any], post_characters: bool = True) -> Optional[discord.Thread]:
    """
    레이드 정보를 디스코드 채널에 전송하고 스레드를 생성합니다.
    
    Args:
        client: 디스코드 클라이언트
        channel_id: 전송할 채널 ID
        raid: 레이드 정보
        post_characters: 참여 가능 캐릭터를 스레드에 자동으로 게시할지 여부
        
    Returns:
        생성된 스레드 객체 또는 None
    """
    try:
        # 채널 가져오기
        channel = client.get_channel(channel_id)
        if not channel:
            logger.error(f"채널을 찾을 수 없습니다: {channel_id}")
            return None
        
        # TextChannel 확인
        if not isinstance(channel, TextChannel):
            logger.error(f"채널 {channel_id}은(는) 텍스트 채널이 아닙니다.")
            return None
        
        # 레이드 정보 메시지 포맷팅
        message_content = format_raid_message(raid)
        
        # 메시지 전송
        logger.info(f"채널 {channel.name}에 레이드 정보 전송 중: {raid.get('name')}")
        sent_message = await channel.send(message_content)
        
        # 스레드 이름 생성
        min_level = raid.get('min_level', 0)
        max_level = raid.get('max_level', '')
        max_level_str = str(max_level) if max_level is not None else ''
        thread_name = f"{raid.get('name', '레이드')} ({min_level} ~ {max_level_str})"
        
        # 스레드 생성
        thread = await sent_message.create_thread(
            name=thread_name,
            auto_archive_duration=1440  # 24시간(1440분) 후 자동 보관
        )
        
        logger.info(f"스레드 생성 완료: {thread_name}")
        
        # 레이드 데이터 파일 생성
        create_raid_data_file(thread.id, raid)
        
        # 옵션이 활성화된 경우에만 캐릭터 정보 게시
        if post_characters:
            await post_eligible_characters_to_thread(client, thread, raid)
        
        return thread
        
    except Exception as e:
        logger.error(f"레이드 정보 전송 중 오류 발생: {str(e)}")
        return None


def load_characters_data(file_path: str = "data/members_character_info.yaml") -> Dict[str, List[Dict[str, Any]]]:
    """
    멤버 캐릭터 정보 파일을 로드합니다.
    
    Args:
        file_path: 데이터 파일 경로
        
    Returns:
        멤버 캐릭터 정보
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"캐릭터 정보 파일을 찾을 수 없습니다: {file_path}")
            return {}
        
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except Exception as e:
        logger.error(f"캐릭터 정보 파일 로드 실패: {str(e)}")
        return {}


def filter_characters_by_raid_level(characters: List[Dict[str, Any]], min_level: float, max_level: Optional[float] = None) -> List[Dict[str, Any]]:
    """
    레이드 레벨 범위에 맞는 캐릭터를 필터링합니다.
    
    Args:
        characters: 필터링할 캐릭터 목록
        min_level: 최소 아이템 레벨
        max_level: 최대 아이템 레벨 (None인 경우 상한 없음)
        
    Returns:
        필터링된 캐릭터 목록
    """
    filtered_characters = []
    
    for character in characters:
        try:
            item_level_str = character.get('ItemMaxLevel', '0')
            # 쉼표 제거, 숫자만 추출
            item_level_str = item_level_str.replace(',', '')
            item_level = float(item_level_str)
            
            # min_level 이상이고, max_level이 None이거나 item_level이 max_level 미만인 경우
            if item_level >= min_level and (max_level is None or item_level < max_level):
                filtered_characters.append(character)
        except (ValueError, TypeError) as e:
            logger.warning(f"아이템 레벨 파싱 오류 - 캐릭터: {character.get('CharacterName', 'Unknown')}, 값: {character.get('ItemMaxLevel', 'None')}, 오류: {str(e)}")
            continue
    
    return filtered_characters


async def post_eligible_characters_to_thread(client: discord.Client, thread: Thread, raid: Dict[str, Any]) -> None:
    """
    레이드에 참여 가능한 캐릭터 정보를 스레드에 게시합니다.
    
    Args:
        client: 디스코드 클라이언트
        thread: 게시할 스레드
        raid: 레이드 정보
    """
    try:
        # 캐릭터 정보 로드
        data = load_characters_data()
        if not data:
            await thread.send("캐릭터 정보를 찾을 수 없습니다. `!캐릭터갱신` 명령어를 사용하여 정보를 수집해주세요.")
            return
        
        # 레이드 레벨 정보 가져오기
        min_level = raid.get('min_level', 0)
        max_level = raid.get('max_level')  # None이면 상한 없음
        
        # 모든 멤버의 적합한 캐릭터 필터링
        eligible_members_characters = {}
        total_eligible_characters = 0
        
        for member_id, characters in data.items():
            eligible_chars = filter_characters_by_raid_level(characters, min_level, max_level)
            if eligible_chars:
                eligible_members_characters[member_id] = eligible_chars
                total_eligible_characters += len(eligible_chars)
        
        if not eligible_members_characters:
            await thread.send(f"**참여 가능한 캐릭터가 없습니다.**\n- 필요 레벨: {min_level}~{max_level if max_level else ''}")
            return
        
        # 레이드 참여 가능한 캐릭터 정보 메시지 생성
        raid_name = raid.get('name', '알 수 없는 레이드')
        level_range = f"{min_level}~{max_level}" if max_level else f"{min_level} 이상"
        
        message = f"**{raid_name} 참여 가능 캐릭터 목록**\n"
        message += f"- 필요 레벨: {level_range}\n"
        message += f"- 총 {total_eligible_characters}개의 캐릭터가 참여 가능합니다.\n\n"
        
        # 각 멤버별 캐릭터 정보 추가
        for member_id, characters in eligible_members_characters.items():
            # 디스코드 ID는 숫자 형식이므로 문자열인 경우 변환하지 않음
            message += f"**<@{member_id}>**\n"
            
            # 캐릭터 레벨 높은 순으로 정렬
            sorted_chars = sorted(
                characters,
                key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
                reverse=True
            )
            
            for char in sorted_chars:
                char_name = char.get('CharacterName', '알 수 없음')
                char_class = char.get('CharacterClassName', '알 수 없음')
                char_level = char.get('ItemMaxLevel', '0')
                
                message += f"- {char_name} ({char_class}) - {char_level}\n"
            
            message += "\n"
        
        # 메시지가 너무 길면 분할하여 전송
        max_message_length = 2000
        messages = []
        current_message = message
        
        while len(current_message) > max_message_length:
            # 최대한 문장 중간에서 끊어지지 않도록 적절한 위치 찾기
            split_pos = current_message.rfind('\n\n', 0, max_message_length)
            if split_pos == -1:  # 적절한 위치를 찾지 못한 경우
                split_pos = current_message.rfind('\n', 0, max_message_length)
            if split_pos == -1:  # 그래도 못 찾은 경우
                split_pos = max_message_length
            
            messages.append(current_message[:split_pos])
            current_message = current_message[split_pos:]
        
        if current_message:
            messages.append(current_message)
        
        # 분할된 메시지 전송
        for msg in messages:
            await thread.send(msg)
        
        logger.info(f"'{thread.name}' 스레드에 {total_eligible_characters}개의 참여 가능 캐릭터 정보를 게시했습니다.")
        
    except Exception as e:
        logger.error(f"캐릭터 정보 게시 중 오류 발생: {str(e)}")
        await thread.send(f"캐릭터 정보 게시 중 오류가 발생했습니다: {str(e)}")


async def update_and_post_characters(client: discord.Client, thread: Thread, raid: Dict[str, Any]) -> None:
    """
    캐릭터 정보를 업데이트하고 레이드 스레드에 참여 가능 캐릭터를 게시합니다.
    
    Args:
        client: 디스코드 클라이언트
        thread: 게시할 스레드
        raid: 레이드 정보
    """
    from services.lostark_service import collect_and_save_character_info
    
    try:
        # 정보 수집 진행 중 메시지
        await thread.send("캐릭터 정보를 수집 중입니다. 잠시만 기다려주세요...")
        
        # 캐릭터 정보 수집 및 저장
        await collect_and_save_character_info()
        
        # 수집 완료 후 레이드 참여 가능한 캐릭터 정보 게시
        await post_eligible_characters_to_thread(client, thread, raid)
        
    except Exception as e:
        logger.error(f"캐릭터 정보 업데이트 및 게시 중 오류 발생: {str(e)}")
        await thread.send(f"캐릭터 정보 업데이트 중 오류가 발생했습니다: {str(e)}")
        

async def send_raid_info_with_characters(client: discord.Client, channel_id: int, raid: Dict[str, Any], update_characters: bool = False) -> Optional[discord.Thread]:
    """
    레이드 정보를 디스코드 채널에 전송하고 스레드를 생성한 후, 참여 가능 캐릭터 정보를 게시합니다.
    
    Args:
        client: 디스코드 클라이언트
        channel_id: 전송할 채널 ID
        raid: 레이드 정보
        update_characters: 캐릭터 정보를 업데이트할지 여부
        
    Returns:
        생성된 스레드 객체 또는 None
    """
    # 레이드 정보 전송 및 스레드 생성 (post_characters=False로 설정하여 중복 호출 방지)
    thread = await send_raid_info(client, channel_id, raid, post_characters=False)
    
    if thread:
        try:
            if update_characters:
                # 캐릭터 정보 업데이트 및 게시
                await update_and_post_characters(client, thread, raid)
            else:
                # 기존 캐릭터 정보로 게시
                await post_eligible_characters_to_thread(client, thread, raid)
        except Exception as e:
            logger.error(f"레이드 스레드에 캐릭터 정보 게시 중 오류 발생: {str(e)}")
    
    return thread


def add_command_to_raid_history(thread_id: int, command_data: Dict[str, Any]) -> bool:
    """
    레이드 커맨드 히스토리에 새 커맨드를 추가합니다.
    
    Args:
        thread_id: 스레드 ID
        command_data: 커맨드 데이터 (예: {"user": "user_id", "command": "add", "role": "dps", "round": 1})
        
    Returns:
        성공 여부
    """
    logger.info(f"[DEBUG] 히스토리 추가 시도: 스레드 {thread_id}, 명령어 {command_data}")
    
    # 레이드 데이터 로드
    raid_data = load_raid_data(thread_id)
    if not raid_data:
        logger.error(f"[DEBUG] 레이드 데이터 로드 실패: {thread_id}")
        return False
    
    # 커맨드 히스토리 확인
    if "command_history" not in raid_data:
        raid_data["command_history"] = []
    
    # 타임스탬프 추가
    command_data["timestamp"] = datetime.now().isoformat()
    
    # 커맨드 추가
    raid_data["command_history"].append(command_data)
    logger.info(f"[DEBUG] 히스토리에 명령어 추가됨: {command_data}")
    
    # 데이터 저장
    success = save_raid_data(thread_id, raid_data)
    logger.info(f"[DEBUG] 히스토리 저장 결과: {success}")
    return success


def get_raid_command_history(thread_id: int) -> List[Dict[str, Any]]:
    """
    레이드의 커맨드 히스토리를 가져옵니다.
    
    Args:
        thread_id: 스레드 ID
        
    Returns:
        커맨드 히스토리 목록
    """
    raid_data = load_raid_data(thread_id)
    if not raid_data or "command_history" not in raid_data:
        return []
    
    return raid_data["command_history"]


# 레이드 스케줄 관련 상수 및 함수
RAID_SCHEDULE_FILE = os.path.join("data", "raids", "weekly_schedule.yaml")


def init_raid_schedule_file() -> None:
    """
    레이드 주간 스케줄 파일을 초기화합니다.
    """
    # 디렉토리 확인
    init_raid_data_directory()
    
    # 파일이 존재하지 않으면 생성
    if not os.path.exists(RAID_SCHEDULE_FILE):
        empty_schedule = {
            "threads": {},
            "updated_at": datetime.now().isoformat()
        }
        with open(RAID_SCHEDULE_FILE, 'w', encoding='utf-8') as file:
            yaml.dump(empty_schedule, file, allow_unicode=True, sort_keys=False)
        logger.info(f"레이드 스케줄 파일 초기화: {RAID_SCHEDULE_FILE}")


def load_raid_schedule() -> Dict[str, Any]:
    """
    레이드 주간 스케줄을 로드합니다.
    
    Returns:
        주간 스케줄 데이터
    """
    init_raid_schedule_file()
    
    try:
        with open(RAID_SCHEDULE_FILE, 'r', encoding='utf-8') as file:
            schedule_data = yaml.safe_load(file)
            return schedule_data if schedule_data else {"threads": {}, "updated_at": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"레이드 스케줄 로드 실패: {str(e)}")
        return {"threads": {}, "updated_at": datetime.now().isoformat()}


def save_raid_schedule(schedule_data: Dict[str, Any]) -> bool:
    """
    레이드 주간 스케줄을 저장합니다.
    
    Args:
        schedule_data: 저장할 스케줄 데이터
        
    Returns:
        성공 여부
    """
    try:
        # 업데이트 시간 추가
        schedule_data["updated_at"] = datetime.now().isoformat()
        
        with open(RAID_SCHEDULE_FILE, 'w', encoding='utf-8') as file:
            yaml.dump(schedule_data, file, allow_unicode=True, sort_keys=False)
            
        logger.info(f"레이드 스케줄 저장 완료: {RAID_SCHEDULE_FILE}")
        return True
    except Exception as e:
        logger.error(f"레이드 스케줄 저장 실패: {str(e)}")
        return False


def process_raid_commands_and_update_schedule(thread_id: int, thread_name: str) -> bool:
    """
    레이드 명령어 히스토리를 처리하여 스케줄을 업데이트합니다.
    
    Args:
        thread_id: 스레드 ID
        thread_name: 스레드 이름
        
    Returns:
        성공 여부
    """
    try:
        logger.info(f"[DEBUG] 스레드 {thread_id}의 명령어 처리 및 스케줄 업데이트 시작")
        
        # 레이드 데이터 로드
        raid_data = load_raid_data(thread_id)
        if not raid_data:
            logger.error(f"[DEBUG] 레이드 데이터를 찾을 수 없음: {thread_id}")
            return False
            
        # 명령어 히스토리 가져오기
        command_history = raid_data.get("command_history", [])
        logger.info(f"[DEBUG] 로드된 명령어 히스토리 수: {len(command_history)}")
        
        if not command_history:
            logger.info(f"[DEBUG] 처리할 명령어 히스토리가 없음: {thread_id}")
            return True
            
        # 레이드 정보
        raid_info = raid_data.get("raid_info", {})
        raid_name = raid_info.get("name", "알 수 없음")
        
        # 현재 스케줄 로드
        schedule_data = load_raid_schedule()
        
        # 스레드 ID를 문자열로 변환
        thread_id_str = str(thread_id)
        
        # 스레드별 스케줄 데이터 초기화
        if "threads" not in schedule_data:
            schedule_data["threads"] = {}
            
        if thread_id_str not in schedule_data["threads"]:
            schedule_data["threads"][thread_id_str] = {
                "name": thread_name,
                "raid_name": raid_name,
                "rounds": [],
                "updated_at": datetime.now().isoformat()
            }
            
        thread_schedule = schedule_data["threads"][thread_id_str]
        
        # 라운드 정보를 처음부터 다시 계산
        # 기존 라운드 정보를 백업
        original_rounds = thread_schedule.get("rounds", [])
        logger.info(f"[DEBUG] 기존 라운드 정보: {original_rounds}")
        
        # 명령어 처리 전 상태 저장
        before_commands = []
        if original_rounds:
            for r in original_rounds:
                round_info = {
                    "idx": r.get("idx"),
                    "dps_count": len(r.get("dps", [])),
                    "sup_count": len(r.get("sup", [])),
                    "time": r.get("time")
                }
                before_commands.append(round_info)
        logger.info(f"[DEBUG] 명령어 처리 전 상태: {before_commands}")
        
        # 라운드 초기화 - 기본 라운드 생성
        base_rounds = []
        for i in range(1, 4):  # 기본 3개 라운드 생성
            base_rounds.append({
                "idx": i,
                "dps": [],
                "sup": [],
                "time": None
            })
        
        # 처음부터 모든 명령어를 실행하여 최종 상태 계산
        # 명령어 타임스탬프 기준으로 정렬 (오래된 순)
        sorted_history = sorted(command_history, key=lambda x: x.get("timestamp", ""))
        
        for i, cmd in enumerate(sorted_history):
            command_type = cmd.get("command")
            role = cmd.get("role")
            round_num = cmd.get("round")
            user_id = cmd.get("user")
            round_edit = cmd.get("round_edit")
            
            logger.info(f"[DEBUG] 처리 중인 명령어 {i+1}/{len(sorted_history)}: {cmd}")
            
            # 1. add 명령어 처리
            if command_type == "add" and role:
                if round_num is not None:
                    # 특정 라운드에 추가
                    logger.info(f"[DEBUG] 특정 라운드에 추가: 라운드 {round_num}, 역할 {role}, 사용자 {user_id}")
                    _add_user_to_specific_round(base_rounds, round_num, user_id, role)
                else:
                    # 적합한 라운드에 추가
                    logger.info(f"[DEBUG] 적합한 라운드에 추가: 역할 {role}, 사용자 {user_id}")
                    _add_user_to_appropriate_round(base_rounds, user_id, role)
            
            # 2. remove 명령어 처리
            elif command_type == "remove":
                if round_num is not None:
                    # 특정 라운드에서 제거
                    if role:
                        logger.info(f"[DEBUG] 특정 라운드에서 제거: 라운드 {round_num}, 역할 {role}, 사용자 {user_id}")
                        _remove_user_from_specific_round(base_rounds, round_num, user_id, role)
                    else:
                        # 특정 라운드에서 모든 역할 제거
                        logger.info(f"[DEBUG] 특정 라운드에서 모든 역할 제거: 라운드 {round_num}, 사용자 {user_id}")
                        _remove_user_from_specific_round(base_rounds, round_num, user_id, "dps")
                        _remove_user_from_specific_round(base_rounds, round_num, user_id, "sup")
                else:
                    if role:
                        # 적합한 라운드에서 제거
                        logger.info(f"[DEBUG] 모든 라운드에서 제거: 역할 {role}, 사용자 {user_id}")
                        _remove_user_from_rounds(base_rounds, user_id, role)
                    else:
                        # 모든 라운드에서 모든 역할 제거
                        logger.info(f"[DEBUG] 모든 라운드에서 모든 역할 제거: 사용자 {user_id}")
                        _remove_user_from_rounds(base_rounds, user_id, "dps")
                        _remove_user_from_rounds(base_rounds, user_id, "sup")
            
            # 3. edit 명령어 처리
            elif command_type == "edit" and round_edit:
                round_index = round_edit.get("round_index")
                start_time = round_edit.get("start_time")
                
                if round_index is not None and start_time:
                    logger.info(f"[DEBUG] 라운드 시간 업데이트: 라운드 {round_index}, 시간 {start_time}")
                    _update_round_time(base_rounds, round_index, start_time)
        
        # 계산된 라운드로 스케줄 업데이트
        thread_schedule["rounds"] = base_rounds
        
        # 명령어 처리 후 상태 저장
        after_commands = []
        if thread_schedule["rounds"]:
            for r in thread_schedule["rounds"]:
                round_info = {
                    "idx": r.get("idx"),
                    "dps_count": len(r.get("dps", [])),
                    "sup_count": len(r.get("sup", [])),
                    "time": r.get("time")
                }
                after_commands.append(round_info)
        logger.info(f"[DEBUG] 명령어 처리 후 상태: {after_commands}")
        
        # 빈 라운드 제거
        thread_schedule["rounds"] = [r for r in base_rounds if r.get("dps") or r.get("sup")]
        
        # 라운드가 없는 경우 기본 라운드 생성
        if not thread_schedule["rounds"]:
            thread_schedule["rounds"] = [{
                "idx": 1,
                "dps": [],
                "sup": [],
                "time": None
            }]
        
        # 라운드 인덱스 재설정
        for i, round_data in enumerate(thread_schedule["rounds"]):
            round_data["idx"] = i + 1
        
        # 업데이트 시간 설정
        thread_schedule["updated_at"] = datetime.now().isoformat()
        
        # 스케줄 저장
        return save_raid_schedule(schedule_data)
    
    except Exception as e:
        logger.error(f"레이드 스케줄 업데이트 중 오류 발생: {str(e)}")
        return False


def _add_user_to_specific_round(rounds: List[Dict[str, Any]], round_num: int, user_id: str, role: str) -> None:
    """
    특정 라운드에 사용자를 추가합니다.
    
    Args:
        rounds: 라운드 목록
        round_num: 라운드 번호
        user_id: 사용자 ID
        role: 역할 (dps 또는 sup)
    """
    # 라운드 번호가 잘못된 경우 첫 번째 라운드에 추가
    if round_num < 1:
        round_num = 1
    
    # 해당 라운드가 없으면 생성
    while len(rounds) < round_num:
        rounds.append({
            "idx": len(rounds) + 1,
            "dps": [],
            "sup": [],
            "time": None
        })
    
    # 라운드 인덱스는 1부터 시작하지만, 리스트 인덱스는 0부터 시작
    round_index = round_num - 1
    current_round = rounds[round_index]
    
    # 역할이 유효한지 확인
    if role not in ["dps", "sup"]:
        return
    
    # 사용자가 이미 다른 역할로 참여 중인지 확인
    other_role = "sup" if role == "dps" else "dps"
    if user_id in current_round.get(other_role, []):
        return
    
    # 해당 역할에 사용자 추가
    if user_id not in current_round.get(role, []):
        if role not in current_round:
            current_round[role] = []
        current_round[role].append(user_id)


def _add_user_to_appropriate_round(rounds: List[Dict[str, Any]], user_id: str, role: str) -> None:
    """
    적합한 라운드에 사용자를 추가합니다.
    
    - 한 라운드에 동일 사용자는 한 번만 등장 가능 (역할 무관)
    - 라운드별 역할 제한: DPS 6명, 서포터 2명
    - 사용자가 여러 명령어를 보내면 여러 라운드에 분산
    
    Args:
        rounds: 라운드 목록
        user_id: 사용자 ID
        role: 역할 (dps 또는 sup)
    """
    # 역할이 유효한지 확인
    if role not in ["dps", "sup"]:
        return
    
    # 역할별 최대 인원 설정
    max_members = 6 if role == "dps" else 2
    
    # 라운드가 없으면 첫 번째 라운드 생성
    if not rounds:
        rounds.append({
            "idx": 1,
            "dps": [],
            "sup": [],
            "time": None
        })
    
    # 사용자가 아직 없는 라운드를 찾아 추가
    for round_data in rounds:
        # 사용자가 이미 이 라운드에 있는지 확인 (역할 무관)
        if user_id in round_data.get("dps", []) or user_id in round_data.get("sup", []):
            continue  # 사용자가 이미 있으면 다음 라운드 확인
            
        # 역할에 공간이 있는지 확인
        if role not in round_data:
            round_data[role] = []
            
        if len(round_data[role]) < max_members:
            # 조건 만족: 사용자가 없고 역할에 공간 있음
            round_data[role].append(user_id)
            return  # 추가 성공 시 종료
    
    # 적합한 라운드를 찾지 못한 경우 새 라운드 생성
    new_round = {
        "idx": len(rounds) + 1,
        "dps": [],
        "sup": [],
        "time": None
    }
    
    new_round[role].append(user_id)
    rounds.append(new_round)


def _remove_user_from_specific_round(rounds: List[Dict[str, Any]], round_num: int, user_id: str, role: str) -> None:
    """
    특정 라운드에서 사용자를 제거합니다.
    
    Args:
        rounds: 라운드 목록
        round_num: 라운드 번호
        user_id: 사용자 ID
        role: 역할 (dps 또는 sup)
    """
    # 라운드 번호가 잘못된 경우 또는 라운드가 없는 경우 종료
    if round_num < 1 or round_num > len(rounds):
        return
    
    # 라운드 인덱스는 1부터 시작하지만, 리스트 인덱스는 0부터 시작
    round_index = round_num - 1
    current_round = rounds[round_index]
    
    # 역할이 유효한지 확인
    if role not in ["dps", "sup"]:
        return
    
    # 해당 역할에서 사용자 제거
    if role in current_round and user_id in current_round[role]:
        current_round[role].remove(user_id)


def _remove_user_from_rounds(rounds: List[Dict[str, Any]], user_id: str, role: str) -> None:
    """
    모든 라운드에서 사용자를 제거합니다.
    
    Args:
        rounds: 라운드 목록
        user_id: 사용자 ID
        role: 역할 (dps 또는 sup)
    """
    # 역할이 유효한지 확인
    if role not in ["dps", "sup"]:
        return
    
    # 라운드가 없으면 종료
    if not rounds:
        return
    
    # 가장 높은 인덱스부터 역순으로 순회
    for i in range(len(rounds) - 1, -1, -1):
        current_round = rounds[i]
        
        # 해당 역할에서 사용자 제거
        if role in current_round and user_id in current_round[role]:
            current_round[role].remove(user_id)
            
            # 라운드에 참여자가 없으면 라운드 제거
            if not current_round.get("dps") and not current_round.get("sup"):
                rounds.pop(i)
            
            # 제거 성공했으므로 종료
            return


def _update_round_time(rounds: List[Dict[str, Any]], round_index: int, start_time: str) -> None:
    """
    특정 라운드의 시작 시간을 업데이트합니다.
    
    Args:
        rounds: 라운드 목록
        round_index: 라운드 인덱스
        start_time: 시작 시간
    """
    # 라운드 인덱스가 잘못된 경우 종료
    if round_index < 1 or round_index > len(rounds):
        return
    
    # 라운드 인덱스는 1부터 시작하지만, 리스트 인덱스는 0부터 시작
    round_idx = round_index - 1
    rounds[round_idx]["time"] = start_time


def get_raid_schedule_for_thread(thread_id: int) -> Dict[str, Any]:
    """
    특정 스레드의 레이드 스케줄을 가져옵니다.
    
    Args:
        thread_id: 스레드 ID
        
    Returns:
        스레드의 레이드 스케줄
    """
    schedule_data = load_raid_schedule()
    thread_id_str = str(thread_id)
    
    if "threads" in schedule_data and thread_id_str in schedule_data["threads"]:
        return schedule_data["threads"][thread_id_str]
    
    return {
        "name": "",
        "raid_name": "",
        "rounds": [],
        "updated_at": datetime.now().isoformat()
    }


async def update_thread_start_message_with_schedule(thread: discord.Thread, raid: Dict[str, Any]) -> bool:
    """
    스레드가 시작된 원본 메시지를 레이드 스케줄 정보로 업데이트합니다.
    
    Args:
        thread: 디스코드 스레드 객체
        raid: 레이드 정보
        
    Returns:
        성공 여부
    """
    try:
        # 레이드 정보 포맷팅
        base_message = format_raid_message(raid)
        
        # 레이드 스케줄 가져오기
        schedule = get_raid_schedule_for_thread(thread.id)
        rounds = schedule.get("rounds", [])
        
        # 메시지 내용 구성
        content = base_message
        
        if rounds:
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
            
            # 전체 메시지에 스케줄 추가
            content += schedule_message

        # 스레드 시작 메시지 찾기
        # 방법 1: 스레드의 시작 메시지를 직접 가져오기
        starter_message = None
        try:
            if hasattr(thread, 'parent') and thread.parent:
                # 스레드가 시작된 채널의 메시지 중에서 찾기
                channel = thread.parent
                
                # 채널이 TextChannel인지 확인
                if isinstance(channel, TextChannel) or isinstance(channel, discord.TextChannel):
                    # 채널에서 메시지를 검색
                    async for message in channel.history(limit=50):
                        # 메시지에 연결된 스레드가 현재 스레드와 일치하는지 확인
                        if hasattr(message, 'thread') and message.thread and message.thread.id == thread.id:
                            starter_message = message
                            break
        except Exception as e:
            logger.warning(f"스레드 시작 메시지 검색 중 오류 발생: {str(e)}")
        
        # 메시지 업데이트 또는 새 메시지 전송
        if starter_message:
            try:
                # 기존 메시지 업데이트
                await starter_message.edit(content=content)
                logger.info(f"스레드 {thread.id}의 시작 메시지를 업데이트했습니다.")
                return True
            except Exception as e:
                logger.error(f"시작 메시지 업데이트 실패: {str(e)}")
        
        # 시작 메시지를 찾지 못했거나 업데이트에 실패한 경우, 대체 방법으로 새 메시지 전송
        # 기존에 보낸 메시지를 찾아 업데이트 시도
        raid_info_tag = f"raid_info_{thread.id}"
        update_message = None
        
        try:
            async for message in thread.history(limit=20, oldest_first=True):
                if message.author.bot and message.author.id == thread.guild.me.id:
                    # 메시지 내용에서 레이드 관련 키워드 확인
                    if "레이드 스케줄" in message.content or "## " + raid.get("name", "") in message.content:
                        update_message = message
                        break
                        
            if update_message:
                await update_message.edit(content=content)
                logger.info(f"스레드 {thread.id}의 기존 레이드 정보 메시지를 업데이트했습니다.")
                return True
        except Exception as e:
            logger.warning(f"메시지 검색/업데이트 중 오류 발생: {str(e)}")
        
        # 모든 방법이 실패한 경우, 새 메시지 전송
        await thread.send(content=content)
        logger.info(f"스레드 {thread.id}에 새 레이드 정보 메시지를 전송했습니다.")
        return True
        
    except Exception as e:
        logger.error(f"스레드 메시지 업데이트 중 오류 발생: {str(e)}")
        return False 