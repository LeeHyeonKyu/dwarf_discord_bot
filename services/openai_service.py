#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI API 서비스 모듈.

이 모듈은 OpenAI API와 통신하여 레이드 명령어를 처리하는 기능을 제공합니다.
"""

import re
import json
import logging
import os
from typing import Dict, List, Any, Optional, Tuple, Union, cast

import aiohttp
from dotenv import load_dotenv
from discord import TextChannel
import discord

# 로깅 설정
logger = logging.getLogger("openai_service")

# 환경 변수 로드
load_dotenv(".env.secret")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 상수 정의
GPT_MODEL = "gpt-4o"  # 사용할 모델


class OpenAIService:
    """
    OpenAI API와 통신하여 레이드 명령어를 처리하는 서비스 클래스.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        OpenAIService 클래스 초기화.
        
        Args:
            api_key: OpenAI API 키. 제공되지 않으면 환경 변수에서 로드합니다.
        """
        # API 키 설정
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = OPENAI_API_KEY
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # 헤더 설정
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    async def parse_raid_command(self, user_id: str, command_text: str, command_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        레이드 명령어를 파싱하여 JSON 형식으로 변환합니다.
        
        Args:
            user_id: 사용자 ID 또는 discord.Message 객체
            command_text: 명령어 텍스트 (user_id가 message 객체인 경우 무시됨)
            command_type: 명령어 타입 (add/remove/edit)
            
        Returns:
            파싱된 명령어 데이터 리스트
        """
         
            # 이 명령어가 숫자+역할 패턴인지 확인

        pattern_count = 0
        num_role_patterns = [
            (r'(\d+)딜', 'dps'),
            (r'(\d+)딜러', 'dps'),
            (r'(\d+)폿', 'sup'),
            (r'(\d+)서포터', 'sup')
        ]
        
        for pattern, role_type in num_role_patterns:
            matches = re.findall(pattern, command_text)
            for match in matches:
                try:
                    pattern_count += int(match)
                except ValueError:
                    pass
        
        logger.info(f"[DEBUG] 숫자+역할 패턴 감지됨, 예상 명령어 수: {pattern_count}")
        
        # 명령어 수가 10개를 초과하는 경우 방어 로직
        if pattern_count > 10:
            logger.warning(f"[DEBUG] 과도한 명령어 수 감지: {pattern_count}개")
            raise ValueError(f"한 번에 최대 10개까지의 명령어만 처리할 수 있습니다. (감지된 명령어 수: {pattern_count}개)")


        # discord.Message 객체가 전달된 경우 필요한 정보 추출
        if isinstance(user_id, discord.Message):
            message = user_id
            command_text = message.content
            user_id = str(message.author.id)
            
        # 명령어 타입이 외부에서 전달되지 않은 경우에만 텍스트에서 추출 시도
        if command_type is None:
            # 명령어 타입 추출 (첫 번째 단어가 add/remove/edit 중 하나라면)
            parts = command_text.split(maxsplit=1)
            
            if parts and parts[0] in ["add", "remove", "edit"]:
                command_type = parts[0]
                # 명령어 타입 제거하고 실제 명령어 내용만 사용
                logger.info(f"[DEBUG] 명령어 타입 감지: {command_type}, 내용: {command_text}")
        
        # GPT 모델에 전달할 프롬프트
        system_prompt = """
당신은 게임 스케줄을 관리하는 어시스턴트입니다. 사용자의 명령어를 JSON 형식으로 변환하는 것이 당신의 역할입니다.

명령어는 다음과 같은 형식의 JSON으로 변환해야 합니다:
```json
{
  "commands": [
    {
      "user": "사용자 ID",
      "command": "add" 또는 "remove" 또는 "edit" 중 하나,
      "role": "sup" 또는 "dps" 또는 null,
      "round": 정수 또는 null,
      "round_edit": {
        "round_index": 정수,
        "start_time": "요일 시간"
      } 또는 null
    },
    {
      "user": "사용자 ID",
      "command": "add" 또는 "remove" 또는 "edit" 중 하나,
      "role": "sup" 또는 "dps" 또는 null,
      "round": 정수 또는 null,
      "round_edit": {
        "round_index": 정수,
        "start_time": "요일 시간"
      } 또는 null
    },
    ...
  ]
}
```

중요한 규칙:
1. 숫자+역할 패턴은 해당 개수만큼의 명령어를 생성해야 합니다.
   예: "2딜"은 딜러 역할 명령어 2개를 생성해야 함
   예: "3폿"은 서포터 역할 명령어 3개를 생성해야 함

2. 각 명령어는 하나의 사용자에 대한 하나의 역할을 나타냅니다.
   절대 하나의 명령어에 여러 개수를 넣지 마세요.

다음은 명령어 예시입니다:

user:
사용자 ID: random_id_123
명령어: 추가 1딜 1폿

output: {"commands": [{"user":"random_id_123", "command":"add", "role":"dps", "round":null, "round_edit":null}, {"user":"random_id_123", "command":"add", "role":"sup", "round":null, "round_edit":null}]}

user:
사용자 ID: random_id_456
명령어: 추가 2딜 2폿

output: {"commands": [{"user":"random_id_456", "command":"add", "role":"dps", "round":null, "round_edit":null}, {"user":"random_id_456", "command":"add", "role":"dps", "round":null, "round_edit":null}, {"user":"random_id_456", "command":"add", "role":"sup", "round":null, "round_edit":null}, {"user":"random_id_456", "command":"add", "role":"sup", "round":null, "round_edit":null}]}

user:
사용자 ID: random_id_789
명령어: 추가 1차 1딜

output: {"commands": [{"user":"random_id_789", "command":"add", "role":"dps", "round":1, "round_edit":null}]}

user:
사용자 ID: random_id_101
명령어: 제거 1딜

output: {"commands": [{"user":"random_id_101", "command":"remove", "role":"dps", "round":null, "round_edit":null}]}

user:
사용자 ID: random_id_202
명령어: 제거 1차

output: {"commands": [{"user":"random_id_202", "command":"remove", "role":null, "round":1, "round_edit":null}]}

user:
사용자 ID: random_id_303
명령어: 제거 1딜 2폿

output: {"commands": [{"user":"random_id_303", "command":"remove", "role":"dps", "round":null, "round_edit":null}, {"user":"random_id_303", "command":"remove", "role":"sup", "round":null, "round_edit":null}, {"user":"random_id_303", "command":"remove", "role":"sup", "round":null, "round_edit":null}]}

user:
사용자 ID: random_id_404
명령어: 수정 1차 목 9시

output: {"commands": [{"user":"random_id_404", "command":"edit", "role":null, "round":null, "round_edit":{"round_index":1, "start_time":"목 9시"}}]}

user:
사용자 ID: random_id_505
명령어: 수정 2차 토 9시 10분

output: {"commands": [{"user":"random_id_505", "command":"edit", "role":null, "round":null, "round_edit":{"round_index":2, "start_time":"토 9시 10분"}}]}

특별한 주의사항:
- "2딜"이나 "3폿"과 같은 패턴이 있으면, 해당 숫자만큼 동일한 역할의 명령어를 생성해야 합니다.
- 예: "2딜"은 반드시 {"role":"dps"} 객체가 2개 있어야 합니다.
- 반드시 올바른 개수의 명령어를 생성하세요.

반드시 유효한 JSON 객체 형식으로 응답하세요. 다른 설명이나 추가 텍스트는 포함하지 마세요.
"""
        
        logger.info(f"[DEBUG] OpenAI 파싱 요청: 사용자 {user_id}, 입력 '{command_text}'")
        # logger.info(f"[DEBUG] 시스템 프롬프트: {system_prompt.strip()}")

        # 특수 문자 보정
        command_text = command_text.replace('\n', ' ').strip()
        
        # 백업 파싱: 만약 OpenAI 파싱이 실패하거나 예상대로 동작하지 않는 경우에 대한 처리
        # backup_parsed = self._backup_parse_command(user_id, command_text, command_type)
        command_map = {
            "add": "추가",
            "remove": "제거",
            "edit": "수정"
        }
        user_prompt = f"사용자 ID: {user_id}\n명령어: {command_map[command_type]} {command_text}"
        logger.info(f"[DEBUG] 유저 프롬프트 - {user_prompt}")
        
        try:
            # API 엔드포인트
            url = "https://api.openai.com/v1/chat/completions"
            
            # 요청 데이터
            payload = {
                "model": GPT_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0,  # 낮은 temperature로 일관된 응답 유도
                "max_tokens": 1000,
                "response_format": {"type": "json_object"}  # JSON 형식 응답 요청
            }
           
            
            logger.info(f"[DEBUG] OpenAI 요청: {payload['messages'][1]['content']}")
            
            # API 호출
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    response_json = await response.json()
                    
                    if response.status != 200:
                        logger.error(f"OpenAI API 오류: {response_json}")
                        # logger.info(f"[DEBUG] 백업 파싱 결과 사용: {backup_parsed}")
                        # return backup_parsed
                        return []
                    
                    # 응답에서 명령어 데이터 추출
                    content = response_json.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    logger.info(f"[DEBUG] OpenAI 응답 원본: {content}")
                    
                    # JSON 파싱
                    try:
                        parsed_data = json.loads(content)
                        # 응답이 배열 형태가 아니면 배열로 변환
                        commands = []
                        if isinstance(parsed_data, dict):
                            if "commands" in parsed_data:
                                commands = parsed_data["commands"]
                                logger.info(f"[DEBUG] 파싱된 명령어(commands 필드): {commands}")
                            else:
                                commands = [parsed_data]
                                logger.info(f"[DEBUG] 파싱된 명령어(단일 객체): {commands}")
                        else:
                            commands = parsed_data
                            logger.info(f"[DEBUG] 파싱된 명령어(배열): {commands}")
                        
                        # 숫자+역할 패턴인 경우 명령어 수 체크
                        if pattern_count > 0 and len(commands) < pattern_count:
                            logger.warning(f"[DEBUG] 숫자+역할 패턴에 대한 명령어 수({len(commands)})가 예상({pattern_count})보다 적음")
                            # 명령어 복제하여 맞추기
                            if len(commands) > 0 and pattern_count > 0:
                                first_cmd = commands[0]
                                while len(commands) < pattern_count:
                                    commands.append(first_cmd.copy())
                                logger.info(f"[DEBUG] 명령어 복제 후 개수: {len(commands)}")
                        
                        return commands
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 파싱 오류: {str(e)}, 원본 내용: {content}")
                        # logger.info(f"[DEBUG] 백업 파싱 결과 사용: {backup_parsed}")
                        # return backup_parsed
                        return []
                        
        except Exception as e:
            logger.error(f"OpenAI API 요청 중 오류 발생: {str(e)}")
            # logger.info(f"[DEBUG] 백업 파싱 결과 사용: {backup_parsed}")
            # return backup_parsed
            return []

    def _backup_parse_command(self, user_id: str, command_text: str, command_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        OpenAI 파싱 실패 시 백업 파싱 메소드. 
        명령어 텍스트를 분석하여 명령어 객체 리스트를 생성합니다.
        
        Args:
            user_id: 사용자 ID
            command_text: 명령어 텍스트
            command_type: 명령어 타입
            
        Returns:
            파싱된 명령어 데이터 리스트
        """
        logger.info(f"[DEBUG] 백업 파싱 시작: {command_text}")
        commands = []
        
        # 명령어 타입 결정 - 외부에서 전달받은 타입이 있으면 우선 사용
        if command_type:
            # 이미 명령어 타입이 전달됨
            pass
        else:
            # 기본값
            command_type = "add"
            
            # 텍스트 기반으로 명령어 타입 판단
            if "제거" in command_text or "삭제" in command_text:
                command_type = "remove"
            elif "수정" in command_text or "변경" in command_text:
                command_type = "edit"
        
        logger.info(f"[DEBUG] 백업 파싱 명령어 타입: {command_type}")
        
        # 수정 명령어 처리
        if command_type == "edit":
            parts = command_text.split()
            round_index = None
            start_time = ""
            
            # 라운드 인덱스 추출
            for i, part in enumerate(parts):
                if "차" in part:
                    try:
                        round_index = int(part.replace("차", ""))
                        # 남은 부분을 시작 시간으로 결합
                        if i + 1 < len(parts):
                            start_time = " ".join(parts[i+1:])
                        break
                    except ValueError:
                        pass
            
            if round_index is not None and start_time:
                command = {
                    "user": user_id,
                    "command": "edit",
                    "role": None,
                    "round": None,
                    "round_edit": {
                        "round_index": round_index,
                        "start_time": start_time
                    }
                }
                commands.append(command)
                return commands
        
        # 추가/제거 명령어 처리
        # 라운드 숫자 확인
        round_num = None
        for part in command_text.split():
            if "차" in part:
                try:
                    round_num = int(part.replace("차", ""))
                    break
                except ValueError:
                    pass
        
        # 역할과 수량 추출
        roles_count = []
        
        # 정규식으로 숫자+역할 패턴 찾기 (예: 2딜, 3폿)
        import re
        patterns = [
            (r'(\d+)딜', 'dps'),
            (r'(\d+)딜러', 'dps'),
            (r'(\d+)폿', 'sup'),
            (r'(\d+)서포터', 'sup')
        ]
        
        for pattern, role_type in patterns:
            matches = re.findall(pattern, command_text)
            for match in matches:
                try:
                    count = int(match)
                    roles_count.append((role_type, count))
                except ValueError:
                    pass
        
        # 역할만 명시된 경우 (예: 딜러, 서포터)
        if not roles_count:
            if "딜" in command_text or "딜러" in command_text:
                roles_count.append(("dps", 1))
            if "폿" in command_text or "서포터" in command_text:
                roles_count.append(("sup", 1))
        
        # 명령어 생성
        for role, count in roles_count:
            for _ in range(count):
                command = {
                    "user": user_id,
                    "command": command_type,
                    "role": role,
                    "round": round_num,
                    "round_edit": None
                }
                commands.append(command)
        
        # 명령어가 없으면 기본 명령어 추가
        if not commands:
            command = {
                "user": user_id,
                "command": command_type,
                "role": "dps",  # 기본값
                "round": round_num,
                "round_edit": None
            }
            commands.append(command)
        
        logger.info(f"[DEBUG] 백업 파싱 결과: {commands}")
        return commands

    def _estimate_expected_command_count(self, command_text: str) -> int:
        """
        명령어 텍스트에서 예상되는 명령어 수를 추정합니다.
        
        Args:
            command_text: 명령어 텍스트
            
        Returns:
            예상 명령어 수
        """
        # 정규식으로 숫자+역할 패턴 찾기
        import re
        expected_count = 0
        
        # 숫자+역할 패턴 확인 (예: 2딜, 3폿)
        patterns = [
            r'(\d+)딜',
            r'(\d+)딜러',
            r'(\d+)폿',
            r'(\d+)서포터'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, command_text)
            for match in matches:
                try:
                    expected_count += int(match)
                except ValueError:
                    pass
        
        # 패턴을 못찾았으면 최소 1개 이상의 명령어
        if expected_count == 0:
            # 역할만 있는 경우 확인
            roles = 0
            if "딜" in command_text or "딜러" in command_text:
                roles += 1
            if "폿" in command_text or "서포터" in command_text:
                roles += 1
            expected_count = max(1, roles)
        
        logger.info(f"[DEBUG] 예상 명령어 수: {expected_count}")
        return expected_count

    async def validate_and_format_commands(self, commands: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
        """
        명령어 데이터를 검증하고 포맷팅합니다.
        
        Args:
            commands: 원본 명령어 데이터 리스트
            user_id: 사용자 ID
            
        Returns:
            검증 및 포맷팅된 명령어 데이터 리스트
        """
        logger.info(f"[DEBUG] 검증 전 명령어: {commands}")
        valid_commands = []
        
        for cmd in commands:
            # 필수 필드 확인
            if not isinstance(cmd, dict):
                logger.warning(f"[DEBUG] 유효하지 않은 명령어 형식: {cmd}")
                continue
                
            # 명령어 타입 확인
            command_type = cmd.get("command")
            if command_type not in ["add", "remove", "edit"]:
                logger.warning(f"[DEBUG] 유효하지 않은 명령어 타입: {command_type}")
                continue
                
            # 사용자 ID 추가 또는 업데이트
            cmd["user"] = user_id
            
            # role이 없으면 null로 설정
            if "role" not in cmd:
                cmd["role"] = None
                
            # round가 없으면 null로 설정
            if "round" not in cmd:
                cmd["round"] = None
                
            # round_edit이 없으면 null로 설정
            if "round_edit" not in cmd or not cmd["round_edit"]:
                cmd["round_edit"] = None
                
            valid_commands.append(cmd)
            
        logger.info(f"[DEBUG] 검증 후 명령어: {valid_commands}")
        return valid_commands 

    async def find_starter_message(self, thread: discord.Thread) -> Optional[discord.Message]:
        """
        스레드의 원본 메시지를 찾습니다.
        
        Args:
            thread: 스레드 객체
            
        Returns:
            원본 메시지 또는 None
        """
        if hasattr(thread, 'parent') and thread.parent:
            channel = thread.parent
            if isinstance(channel, TextChannel) or isinstance(channel, discord.TextChannel):
                async for message in channel.history(limit=50):
                    if hasattr(message, 'thread') and message.thread and message.thread.id == thread.id:
                        return message
        return None
