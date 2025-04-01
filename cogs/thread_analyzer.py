import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import aiohttp
import datetime
import hashlib
import pathlib
from typing import Optional, List, Dict, Set, Tuple
from dataclasses import dataclass, field
import re

from .raid_scheduler_common import RaidSchedulerBase, logger

@dataclass
class Character:
    name: str
    role: str  # "서포터" 또는 "딜러"
    
@dataclass
class UserPreference:
    user_id: str
    user_name: str
    characters: List[Character] = field(default_factory=list)
    # 특정 차수에 특정 캐릭터로 참가하고 싶은 명시적 요청
    explicit_requests: Dict[str, List[Character]] = field(default_factory=dict)  # round_name -> 캐릭터 목록
    # 우선순위: 명시적 요청이 없는 경우 사용
    priority: int = 0  # 캐릭터 수에 기반한 우선순위
    
@dataclass
class RoundInfo:
    name: str
    when: str = ""
    note: str = ""
    supporter_max: int = 2
    dealer_max: int = 6
    # 참가가 확정된 사용자들
    confirmed_supporters: List[Tuple[str, str]] = field(default_factory=list)  # (user_name, character_name)
    confirmed_dealers: List[Tuple[str, str]] = field(default_factory=list)  # (user_name, character_name)
    
@dataclass
class RaidData:
    header: str
    info: List[str] = field(default_factory=list)
    rounds: List[RoundInfo] = field(default_factory=list)
    # 사용자 선호도 및 참가 요청
    user_preferences: Dict[str, UserPreference] = field(default_factory=dict)  # user_name -> UserPreference

class ThreadAnalyzer(commands.Cog, RaidSchedulerBase):
    """스레드 메시지를 분석하여 레이드 정보를 업데이트하는 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        RaidSchedulerBase.__init__(self, bot)
        self.schedule_channel_id = int(os.getenv("SCHEDULE_CHANNEL_ID", "0"))
        
        # 자동 분석 작업 시작 - 비활성화
        # self.auto_analyze_threads.start()
        logger.info("자동 스레드 분석 스케줄러가 비활성화되었습니다.")
    
    async def cog_unload(self):
        """Cog가 언로드될 때 작업 중지"""
        # self.auto_analyze_threads.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'{self.__class__.__name__} Cog가 준비되었습니다.')
    
    # 자동 분석 기능 - 현재 비활성화 상태
    """
    @tasks.loop(minutes=30)
    async def auto_analyze_threads(self):
        # 30분마다 스레드를 분석하여 레이드 메시지 업데이트
        logger.info("자동 스레드 분석 작업 시작")
        
        # 레이드 채널 가져오기
        channel = self.bot.get_channel(self.schedule_channel_id)
        if not channel:
            logger.error("스케줄 채널을 찾을 수 없습니다.")
            return
        
        try:
            # 채널의 모든 스레드 가져오기
            threads = []
            async for thread in channel.archived_threads(limit=None):
                threads.append(thread)
            
            active_threads = channel.threads
            for thread in active_threads:
                threads.append(thread)
            
            if not threads:
                logger.info("분석할 스레드가 없습니다.")
                return
            
            logger.info(f"{len(threads)}개 스레드 분석 시작")
            
            # 각 스레드 분석
            for thread in threads:
                try:
                    # 스레드 내 메시지 분석
                    await self.auto_update_raid_message(thread)
                    # 과부하 방지를 위한 딜레이
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"스레드 '{thread.name}' 처리 중 오류 발생: {e}")
            
            logger.info("자동 스레드 분석 완료")
            
        except Exception as e:
            logger.error(f"자동 스레드 분석 중 오류 발생: {e}")
    
    @auto_analyze_threads.before_loop
    async def before_auto_analyze(self):
        # 봇이 준비될 때까지 대기
        await self.bot.wait_until_ready()
        # 시작 시 1분 대기 (봇 초기화 후 안정화 시간)
        await asyncio.sleep(60)
    """
    
    async def get_thread_messages(self, thread):
        """스레드 내 메시지 가져오기 (마지막으로 봇이 보낸 메시지 이후)"""
        # 봇이 마지막으로 보낸 메시지 찾기
        last_bot_message = None
        last_bot_message_time = None
        
        async for message in thread.history(limit=100):
            if message.author.id == self.bot.user.id and "분석 결과:" in message.content:
                last_bot_message = message
                last_bot_message_time = message.created_at
                break
        
        # 스레드 내 새 메시지 수집
        thread_messages = []
        
        async for message in thread.history(limit=100):
            # 봇 메시지 제외
            if message.author.bot:
                continue
                
            # 마지막 봇 메시지 이후 메시지만 수집
            if last_bot_message_time and message.created_at <= last_bot_message_time:
                continue
                
            thread_messages.append({
                'author': message.author.display_name,
                'author_id': str(message.author.id),
                'content': message.content,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'author_mention': message.author.mention
            })
        
        # 최신 메시지가 먼저 오기 때문에 순서 뒤집기
        thread_messages.reverse()
        
        return thread_messages
    
    async def analyze_messages_with_openai(self, thread_messages, message_content, raid_name):
        """OpenAI API를 사용하여 메시지 분석 (캐싱 적용)"""
        if not self.openai_api_key:
            return {"error": "OpenAI API 키가 설정되지 않았습니다. .env.secret 파일을 확인해주세요."}
        
        # 캐시 키 생성
        cache_key = self.get_cache_key({
            "thread_messages": thread_messages,
            "message_content": message_content,
            "raid_name": raid_name
        })
        
        # 캐시 확인
        cached_result = self.get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        # 메시지 포맷팅
        formatted_messages = []
        for msg in thread_messages:
            formatted_messages.append(f"{msg['author']} ({msg['created_at']}): {msg['content']}")
        
        messages_text = "\n".join(formatted_messages)
        
        # 디스코드 ID 매핑 생성
        user_ids = {}
        for msg in thread_messages:
            user_ids[msg['author']] = msg['author_id']
        
        # 메시지 개수에 대한 정보
        message_count_info = f"분석 대상: 봇이 마지막으로 보낸 메시지 이후의 {len(thread_messages)}개 메시지"
        if not thread_messages:
            message_count_info = "새로운 메시지가 없습니다."
        
        # OpenAI에 보낼 프롬프트
        prompt = f"""
이것은 '{raid_name}' 레이드 참가에 관한 디스코드 스레드의 원본 메시지와 대화 내용입니다.

## 원본 메시지:
{message_content}

## 스레드 대화 내용({message_count_info}):
{messages_text}

## 참가자 규칙:
- 8인 레이드의 경우 서포터는 최대 2명까지만 가능합니다
- 4인 레이드의 경우 서포터는 최대 1명만 가능합니다
- "폿1딜2 참여"와 같은 메시지는 총 3번에 걸쳐서 참여하겠다는 의미입니다
  (서포터로 1번, 딜러로 2번 참여)
- 특정 차수를 지정하지 않은 경우, 모든 일정에 해당 참가자를 추가해야 합니다
- 서포터가 이미 최대 인원인 경우, 새로운 차수(예: 다음 차수)를 생성하여 초과된 서포터를 배정하세요

## 분석 및 명령어 반환 요청:
스레드 대화 내용을 분석하여 다음과 같은 JSON 형식으로 변경 사항을 반환해주세요:

```json
{
  "changes": [
    {
      "type": "add_participant", 
      "user": "사용자명",
      "round": "1차",
      "role": "딜러"
    },
    {
      "type": "remove_participant",
      "user": "사용자명",
      "round": "1차",
      "role": "서포터"
    },
    {
      "type": "update_schedule",
      "round": "1차",
      "when": "7/5(수) 21:00"
    },
    {
      "type": "add_round",
      "round": "2차",
      "when": "7/6(목) 21:00"
    },
    {
      "type": "update_note",
      "round": "1차",
      "note": "숙련자만 참여 가능"
    }
  ]
}
```

## 오늘 대화에서의 예시 상황과 응답:

### 상황 1: 새 참가자 추가
```
유저1: 1차에 딜러로 참가할게요
유저2: 서폿으로 참가합니다
```

응답:
```json
{
  "changes": [
    {
      "type": "add_participant",
      "user": "유저1",
      "round": "1차",
      "role": "딜러"
    },
    {
      "type": "add_participant",
      "user": "유저2",
      "round": "1차",
      "role": "서포터"
    }
  ]
}
```

### 상황 2: 일정 변경 및 참가자 취소
```
유저1: 1차 일정 목요일 9시로 변경해주세요
유저2: 1차 참가 취소할게요
유저3: 1차 딜러만 취소할게요 (서포터로는 계속 참가)
```

응답:
```json
{
  "changes": [
    {
      "type": "update_schedule",
      "round": "1차",
      "when": "목요일 21:00"
    },
    {
      "type": "remove_participant",
      "user": "유저2",
      "round": "1차"
    },
    {
      "type": "remove_participant",
      "user": "유저3",
      "round": "1차",
      "role": "딜러"
    }
  ]
}
```

### 상황 3: 새 차수 추가 및 메모 업데이트
```
유저1: 2차 일정 금요일 9시에 추가해주세요
유저2: 1차 메모에 "숙련자만" 추가해주세요
```

응답:
```json
{
  "changes": [
    {
      "type": "add_round",
      "round": "2차",
      "when": "금요일 21:00"
    },
    {
      "type": "update_note",
      "round": "1차",
      "note": "숙련자만"
    }
  ]
}
```

### 상황 4: 다수의 차수에 참가
```
유저1: 1차, 2차 모두 딜러로 참가합니다
```

응답:
```json
{
  "changes": [
    {
      "type": "add_participant",
      "user": "유저1",
      "round": "1차",
      "role": "딜러"
    },
    {
      "type": "add_participant",
      "user": "유저1",
      "round": "2차",
      "role": "딜러"
    }
  ]
}
```

### 상황 5: 역할 지정 참가
```
유저1: 폿1딜2로 참가할게요
```

응답:
```json
{
  "changes": [
    {
      "type": "add_participant",
      "user": "유저1",
      "round": "1차",
      "role": "서포터"
    },
    {
      "type": "add_participant",
      "user": "유저1",
      "round": "1차",
      "role": "딜러"
    },
    {
      "type": "add_participant",
      "user": "유저1",
      "round": "2차",
      "role": "딜러"
    }
  ]
}
```

### 상황 6: 특정 차수 미지정 제거
```
유저1: 1딜 취소할게요
```

응답:
```json
{
  "changes": [
    {
      "type": "remove_participant",
      "user": "유저1",
      "role": "1딜"
    }
  ]
}
```

### 상황 7: 특정 개수 제거
```
유저1: !제거 2딜
```

응답:
```json
{
  "changes": [
    {
      "type": "remove_participant",
      "user": "유저1",
      "role": "2딜"
    }
  ]
}
```

- 중요: 변경 사항만 반환하고, 기존 정보는 반환하지 마세요.
- 사용자명은 디스코드 멘션 형식(<@사용자ID>)이 아닌 원래 사용자명을 그대로 사용하세요.
- 사용자 ID 정보: {json.dumps(user_ids, ensure_ascii=False)}
- 오직 JSON 형식으로만 응답하세요.
"""

        # OpenAI API 호출
        messages = [
            {"role": "system", "content": "당신은 디스코드 대화에서 레이드 참가 정보와 일정 변경 등의 요청을 추출하여 JSON 형식으로 명령어를 반환하는 도우미입니다."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.call_openai_api(
            messages=messages,
            model="gpt-4o-mini",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        if "error" in response:
            return response
        
        try:
            # JSON 파싱 시도
            changes_data = json.loads(response["content"])
            result = {
                "changes_data": changes_data,
                "original_content": message_content
            }
            
            # 결과를 캐시에 저장
            self.save_to_cache(cache_key, result)
            
            # 변경 항목 수 계산
            changes_count = len(changes_data.get("changes", []))
            logger.info(f"변경 사항을 성공적으로 파싱했습니다: {changes_count}개 항목")
            
            return result
        except json.JSONDecodeError as e:
            error_result = {"error": f"JSON 파싱 오류: {str(e)}", "raw_content": response["content"]}
            return error_result
    
    async def process_commands_and_update_message(self, message, commands, thread_name="", ctx=None):
        """변경 명령어를 처리하여 메시지를 업데이트하는 함수"""
        try:
            # 1. 메시지 내용을 데이터 구조로 파싱
            raid_data = await self.parse_message_to_data(message.content)
            
            # 2. 변환 및 검증
            formatted_changes = []
            
            logger.info(f"원본 명령: {json.dumps(commands, ensure_ascii=False)}")
            
            for change in commands.get("changes", []):
                try:
                    # API 응답 형식에서 공통 형식으로 변환
                    formatted_change = {
                        "type": change.get("type", "")
                    }
                    
                    if change.get("type") == "add_participant":
                        formatted_change.update({
                            "user_name": change.get("user", ""),
                            "round_name": change.get("round", ""),
                            "role": change.get("role", "")
                        })
                    elif change.get("type") == "remove_participant":
                        formatted_change.update({
                            "user_name": change.get("user", ""),
                            "round_name": change.get("round", ""),
                            "role": change.get("role", "")  # 역할 정보도 포함
                        })
                    elif change.get("type") == "update_schedule":
                        formatted_change.update({
                            "round_name": change.get("round", ""),
                            "schedule": change.get("when", "")
                        })
                    elif change.get("type") == "add_round":
                        formatted_change.update({
                            "round_name": change.get("round", ""),
                            "schedule": change.get("when", "")
                        })
                        logger.info(f"차수 추가 변환 전: {json.dumps(change, ensure_ascii=False)}")
                        logger.info(f"차수 추가 변환 후: {json.dumps(formatted_change, ensure_ascii=False)}")
                    elif change.get("type") == "update_note":
                        formatted_change.update({
                            "round_name": change.get("round", ""),
                            "note": change.get("note", "")
                        })
                    
                    formatted_changes.append(formatted_change)
                except Exception as e:
                    logger.error(f"명령어 변환 중 오류: {e}")
            
            logger.info(f"변환된 명령: {json.dumps(formatted_changes, ensure_ascii=False)}")
            
            # 3. 명령어를 데이터 구조에 적용
            changes_applied = await self.apply_changes_to_data(raid_data, formatted_changes)
            
            logger.info(f"적용된 변경사항: {changes_applied}")
            
            if changes_applied:
                # 4. 업데이트된 데이터 구조를 기반으로 새 메시지 내용 생성
                updated_content = await self.format_data_to_message(raid_data)
                
                logger.info(f"생성된 메시지 내용 길이: {len(updated_content)}")
                
                # 5. 메시지 업데이트
                update_result = await self.update_message_safely(message, updated_content)
                
                logger.info(f"메시지 업데이트 결과: {update_result}")
                
                if update_result["status"] == "success":
                    changes_summary = "\n".join(changes_applied)
                    log_message = f"'{thread_name}' 메시지 업데이트 완료: {len(changes_applied)}개 변경\n{changes_summary}"
                    logger.info(log_message)
                    
                    if ctx:
                        await ctx.send(f"메시지 업데이트 완료: {len(changes_applied)}개 변경\n{changes_summary}")
                    
                    return True, changes_applied
                else:
                    log_message = f"'{thread_name}' 메시지 업데이트 실패: {update_result['reason']}"
                    logger.error(log_message)
                    
                    if ctx:
                        await ctx.send(f"메시지 업데이트 실패: {update_result['reason']}")
                    
                    return False, []
            else:
                log_message = f"'{thread_name}' 메시지 변경 사항이 없습니다."
                logger.info(log_message)
                
                if ctx:
                    await ctx.send("메시지 변경 사항이 없습니다.")
                
                return False, []
                
        except Exception as e:
            error_message = f"명령어 처리 중 오류 발생: {e}"
            logger.error(error_message, exc_info=True)
            if ctx:
                await ctx.send(error_message)
            return False, [error_message]
    
    async def auto_update_raid_message(self, thread):
        """(자동) 스레드 내 메시지 분석하여 원본 레이드 메시지 업데이트"""
        try:
            # 레이드 채널 가져오기
            channel = self.bot.get_channel(self.schedule_channel_id)
            if not channel:
                logger.error("스케줄 채널을 찾을 수 없습니다.")
                return
            
            # 스레드의 소유자 메시지 찾기
            message = None
            async for msg in channel.history(limit=100):
                try:
                    # 메시지에 직접 threads 속성 접근 대신 스레드 ID와 스레드 시작 메시지 ID 비교
                    if hasattr(thread, 'starter_message_id') and thread.starter_message_id == msg.id:
                        message = msg
                        break
                except Exception as e:
                    logger.error(f"메시지 확인 중 오류: {e}")
                    continue
            
            # 찾지 못한 경우 스레드 이름으로 검색
            if not message:
                async for msg in channel.history(limit=100):
                    if thread.name.lower() in msg.content.lower():
                        message = msg
                        break
            
            if not message:
                logger.error(f"'{thread.name}' 스레드의 원본 메시지를 찾을 수 없습니다.")
                return
            
            # 레이드 이름 추출
            raid_name = "알 수 없음"
            if "\n" in message.content:
                raid_name = message.content.split("\n")[0]
                if " (" in raid_name:
                    raid_name = raid_name.split(" (")[0]
                
            # 스레드 메시지 가져오기
            thread_messages = await self.get_thread_messages(thread)
            
            # 새 메시지가 없는 경우 업데이트 건너뛰기
            if not thread_messages:
                logger.info(f"'{thread.name}' 스레드에 새로운 메시지가 없어 업데이트를 건너뜁니다.")
                return
            
            # OpenAI를 사용하여 메시지 분석
            logger.info(f"'{thread.name}' 스레드 메시지 분석 시작 (새 메시지 {len(thread_messages)}개)")
            analysis_result = await self.analyze_messages_with_openai(thread_messages, message.content, raid_name)
            
            if "error" in analysis_result:
                logger.error(f"메시지 분석 오류: {analysis_result['error']}")
                return
            
            # 명령어 처리 및 메시지 업데이트
            if "changes_data" in analysis_result:
                await self.process_commands_and_update_message(
                    message=message,
                    commands=analysis_result["changes_data"],
                    thread_name=thread.name
                )
            else:
                logger.error(f"'{thread.name}' 스레드 메시지 분석 결과에 changes_data가 없습니다.")
            
        except Exception as e:
            logger.error(f"자동 메시지 업데이트 오류: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(ThreadAnalyzer(bot)) 