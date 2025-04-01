import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import aiohttp
import datetime
import hashlib
import pathlib
from typing import Optional
import re

class ThreadAnalyzer(commands.Cog):
    """스레드 메시지를 분석하여 레이드 정보를 업데이트하는 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.schedule_channel_id = int(os.getenv("SCHEDULE_CHANNEL_ID", "0"))
        if not self.openai_api_key:
            print("경고: OPENAI_API_KEY가 설정되지 않았습니다.")
        
        # 캐시 디렉토리 생성
        self.cache_dir = pathlib.Path('/tmp/discord_bot_llm_cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"LLM 캐시 디렉토리: {self.cache_dir}")
        
        # 오래된 캐시 파일 정리
        self.cleanup_cache()
        
        # 자동 분석 작업 시작 - 비활성화
        # self.auto_analyze_threads.start()
        print("자동 스레드 분석 스케줄러가 비활성화되었습니다.")
    
    async def cog_unload(self):
        """Cog가 언로드될 때 작업 중지"""
        # self.auto_analyze_threads.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} Cog가 준비되었습니다.')
    
    async def get_thread_messages(self, thread):
        """스레드에서 메시지 가져오기"""
        messages = []
        latest_bot_message_time = None
        
        try:
            # 가장 최근 봇 메시지 찾기 (역순으로 검색)
            async for message in thread.history(limit=100, oldest_first=False):
                if message.author.bot and message.author.id == self.bot.user.id:
                    latest_bot_message_time = message.created_at
                    break
            
            # 메시지 수집 (시간순으로)
            async for message in thread.history(limit=100, oldest_first=True):
                # 봇 메시지 제외
                if message.author.bot:
                    continue
                
                # 봇의 마지막 메시지 이후 메시지만 포함
                if latest_bot_message_time and message.created_at <= latest_bot_message_time:
                    continue
                
                # 메시지 생성 시간 변환
                created_at = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                
                # 메시지 정보 저장
                messages.append({
                    'author': message.author.display_name,
                    'author_id': str(message.author.id),
                    'content': message.content,
                    'created_at': created_at
                })
            
            # 디버그 메시지
            if latest_bot_message_time:
                print(f"봇의 마지막 메시지 이후 {len(messages)}개의 새 메시지 수집 ({latest_bot_message_time.strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                print(f"봇 메시지가 없어 모든 사용자 메시지 {len(messages)}개 수집")
            
            return messages
        
        except Exception as e:
            print(f"스레드 메시지 가져오기 오류: {e}")
            return []
    
    def _get_cache_key(self, thread_messages, message_content, raid_name):
        """입력 데이터의 해시값(캐시 키)을 생성합니다"""
        # 입력 데이터를 문자열로 직렬화
        data_str = json.dumps({
            'thread_messages': thread_messages,
            'message_content': message_content,
            'raid_name': raid_name
        }, sort_keys=True, ensure_ascii=False)
        
        # SHA-256 해시 생성
        hash_obj = hashlib.sha256(data_str.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def _get_cached_result(self, cache_key):
        """캐시에서 결과를 가져옵니다"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                print(f"캐시에서 결과를 로드했습니다: {cache_key}")
                return cached_data
            except Exception as e:
                print(f"캐시 로드 중 오류 발생: {e}")
        return None
    
    def _save_to_cache(self, cache_key, result):
        """결과를 캐시에 저장합니다"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"결과를 캐시에 저장했습니다: {cache_key}")
        except Exception as e:
            print(f"캐시 저장 중 오류 발생: {e}")
    
    async def analyze_messages_with_openai(self, thread_messages, message_content, raid_name):
        """OpenAI API를 사용하여 메시지 분석 (캐싱 적용)"""
        if not self.openai_api_key:
            return {"error": "OpenAI API 키가 설정되지 않았습니다. .env.secret 파일을 확인해주세요."}
        
        # 캐시 키 생성
        cache_key = self._get_cache_key(thread_messages, message_content, raid_name)
        
        # 캐시 확인
        cached_result = self._get_cached_result(cache_key)
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
스레드 대화 내용을 분석하여 다음 명령어 형식으로 정보를 반환해주세요:

```json
{
  "사용자명1": [
    "add(1차, 딜러)",  // 1차에 딜러로 참가
    "add(2차, 서포터)" // 2차에 서포터로 참가
  ],
  "사용자명2": [
    "edit(1차, when: 7/5(수) 21:00)"  // 1차 일정 수정
  ],
  "일정": [
    "add(2차, when: 7/6(목) 21:00)"  // 2차 일정 추가
  ],
  "notes": [
    "add(1차, note: 숙련자만)"  // 1차 노트 추가/수정
  ]
}
```

- 사용자명은 디스코드 멘션 형식(<@사용자ID>)이 아닌 원래 사용자명을 그대로 사용하세요.
- 사용자 ID 정보: {json.dumps(user_ids, ensure_ascii=False)}
- "일정" 키는 when 정보를 수정할 때 사용합니다.
- "notes" 키는 참고사항을 추가/수정할 때 사용합니다.
- 명령어는 add, edit, remove 세 가지가 있습니다.
- 변경이 필요한 사항만 간결하게 명령어로 표현하세요.
- 오직 JSON 형식으로만 응답하세요.
"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "당신은 디스코드 대화에서 정보를 추출하여 JSON 형식으로 명령어를 반환하는 도우미입니다."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            
            print(f"OpenAI API 호출 중... (캐시 키: {cache_key[:8]}...)")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions", 
                    headers=headers, 
                    json=payload
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        content = response_data['choices'][0]['message']['content'].strip()
                        
                        try:
                            # JSON 파싱 시도
                            commands = json.loads(content)
                            result = {
                                "commands": commands,
                                "original_content": message_content
                            }
                            
                            # 결과를 캐시에 저장
                            self._save_to_cache(cache_key, result)
                            print(f"명령어 응답을 성공적으로 파싱했습니다: {len(commands)} 사용자/항목")
                            
                            return result
                        except json.JSONDecodeError as e:
                            error_result = {"error": f"JSON 파싱 오류: {str(e)}", "raw_content": content}
                            return error_result
                    else:
                        error_result = {"error": f"OpenAI API 오류: 상태 코드 {response.status}"}
                        return error_result
        
        except Exception as e:
            error_result = {"error": f"OpenAI API 오류: {str(e)}"}
            return error_result
    
    @tasks.loop(minutes=30)
    async def auto_analyze_threads(self):
        """30분마다 모든 레이드 스레드를 자동으로 분석하고 업데이트"""
        if self.schedule_channel_id == 0:
            print("스케줄 채널 ID가 설정되지 않아 자동 분석을 건너뜁니다.")
            return
        
        print(f"{datetime.datetime.now()} - 자동 스레드 분석 시작")
        
        channel = self.bot.get_channel(self.schedule_channel_id)
        if not channel:
            print(f"스케줄 채널을 찾을 수 없습니다: {self.schedule_channel_id}")
            return
        
        if not isinstance(channel, discord.TextChannel):
            print(f"채널 '{channel.name}'은(는) 텍스트 채널이 아닙니다.")
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
                print(f"'{channel.name}' 채널에 분석할 스레드가 없습니다.")
                return
            
            updated_count = 0
            error_count = 0
            
            # 각 스레드 분석
            for thread in threads:
                try:
                    print(f"스레드 '{thread.name}' 자동 분석 중... ({threads.index(thread) + 1}/{len(threads)})")
                    
                    # 스레드 내 메시지 분석 및 업데이트
                    await self.auto_update_raid_message(thread)
                    updated_count += 1
                    
                    # API 부하 방지를 위한 지연
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    error_count += 1
                    print(f"스레드 '{thread.name}' 자동 분석 중 오류 발생: {e}")
            
            print(f"자동 분석 완료: 총 {len(threads)}개 스레드 중 {updated_count}개 업데이트됨, {error_count}개 오류 발생")
            
        except Exception as e:
            print(f"자동 스레드 분석 중 오류 발생: {e}")
    
    @auto_analyze_threads.before_loop
    async def before_auto_analyze(self):
        """봇이 준비될 때까지 대기"""
        await self.bot.wait_until_ready()
        # 시작 시 1분 대기 (봇 초기화 후 안정화 시간)
        await asyncio.sleep(60)
        
    async def process_commands_and_update_message(self, message, commands, thread_name="", ctx=None):
        """JSON 명령어를 처리하여 메시지를 업데이트하는 함수"""
        try:
            # 메시지 내용을 줄 단위로 분리하여 처리
            lines = message.content.split('\n')
            
            # 차수 인덱스 찾기 (ex: "## 1차", "## 2차" 등)
            round_indices = {}
            for i, line in enumerate(lines):
                if line.startswith('## ') and '차' in line:
                    round_name = line.replace('## ', '').strip()
                    round_indices[round_name] = i
            
            changes_made = False
            changes_description = []
            
            # 명령어 처리
            for user, user_commands in commands.items():
                if user == "일정":
                    # 일정 관련 명령
                    for cmd in user_commands:
                        if cmd.startswith('add('):
                            # 새 차수 일정 추가
                            match = re.search(r'add\(([^,]+),\s*when:\s*([^)]+)\)', cmd)
                            if match:
                                round_name = match.group(1)
                                when_value = match.group(2)
                                
                                # 이미 해당 차수가 있는지 확인
                                if round_name in round_indices:
                                    # when 값 업데이트
                                    round_index = round_indices[round_name]
                                    for j in range(round_index + 1, len(lines)):
                                        if lines[j].startswith('- when:'):
                                            lines[j] = f'- when: {when_value}'
                                            changes_made = True
                                            changes_description.append(f"{round_name} 일정 설정: {when_value}")
                                            break
                                else:
                                    # 새 차수 추가
                                    last_round_index = max(round_indices.values()) if round_indices else 0
                                    new_round_section = [
                                        f"## {round_name}",
                                        f"- when: {when_value}",
                                        "- who: ",
                                        "  - 서포터(0/2): ",
                                        "  - 딜러(0/6): ",
                                        "- note: "
                                    ]
                                    lines = lines[:last_round_index + 7] + new_round_section + lines[last_round_index + 7:]
                                    round_indices[round_name] = last_round_index + 7
                                    changes_made = True
                                    changes_description.append(f"{round_name} 추가: {when_value}")
                        
                        elif cmd.startswith('edit('):
                            # 기존 차수 일정 수정
                            match = re.search(r'edit\(([^,]+),\s*when:\s*([^)]+)\)', cmd)
                            if match:
                                round_name = match.group(1)
                                when_value = match.group(2)
                                
                                if round_name in round_indices:
                                    round_index = round_indices[round_name]
                                    for j in range(round_index + 1, len(lines)):
                                        if lines[j].startswith('- when:'):
                                            lines[j] = f'- when: {when_value}'
                                            changes_made = True
                                            changes_description.append(f"{round_name} 일정 수정: {when_value}")
                                            break
                
                elif user == "notes":
                    # 메모 관련 명령
                    for cmd in user_commands:
                        if cmd.startswith('add(') or cmd.startswith('edit('):
                            # 메모 추가/수정
                            match = re.search(r'(?:add|edit)\(([^,]+),\s*note:\s*([^)]+)\)', cmd)
                            if match:
                                round_name = match.group(1)
                                note_value = match.group(2)
                                
                                if round_name in round_indices:
                                    round_index = round_indices[round_name]
                                    for j in range(round_index + 1, len(lines)):
                                        if lines[j].startswith('- note:'):
                                            lines[j] = f'- note: {note_value}'
                                            changes_made = True
                                            changes_description.append(f"{round_name} 메모 추가/수정: {note_value}")
                                            break
                
                else:
                    # 사용자 참가 관련 명령
                    for cmd in user_commands:
                        if cmd.startswith('add('):
                            # 참가자 추가
                            match = re.search(r'add\(([^,]+),\s*([^)]+)\)', cmd)
                            if match:
                                round_name = match.group(1)
                                role = match.group(2)
                                
                                if round_name in round_indices:
                                    round_index = round_indices[round_name]
                                    
                                    # 역할에 따라 적절한 라인 찾기
                                    role_type = "서포터" if role.lower() in ["서포터", "폿", "서폿"] else "딜러"
                                    
                                    for j in range(round_index + 1, len(lines)):
                                        if f"{role_type}(" in lines[j]:
                                            # 현재 인원 수 파싱
                                            current_line = lines[j]
                                            count_pattern = rf"{role_type}\((\d+)/(\d+)\):"
                                            count_match = re.search(count_pattern, current_line)
                                            
                                            if count_match:
                                                current_count = int(count_match.group(1))
                                                max_count = int(count_match.group(2))
                                                
                                                # 인원 수 업데이트
                                                new_count = current_count + 1
                                                if new_count <= max_count:
                                                    # 라인 업데이트: 새 참가자 추가
                                                    if ": " in current_line:
                                                        if current_line.endswith(': '):
                                                            # 첫 번째 참가자
                                                            lines[j] = f"{current_line}{user}"
                                                        else:
                                                            # 기존 참가자에 추가
                                                            lines[j] = f"{current_line}, {user}"
                                                    
                                                    # 인원 수 텍스트 업데이트
                                                    lines[j] = lines[j].replace(f"{role_type}({current_count}/{max_count}):", f"{role_type}({new_count}/{max_count}):")
                                                    
                                                    changes_made = True
                                                    changes_description.append(f"{user} {round_name}에 {role_type}로 참가")
                                            break
                        
                        elif cmd.startswith('remove('):
                            # 참가자 제거
                            match = re.search(r'remove\(([^,]+),\s*([^)]+)\)', cmd)
                            if match:
                                round_name = match.group(1)
                                role = match.group(2)
                                
                                if round_name in round_indices:
                                    round_index = round_indices[round_name]
                                    
                                    # 역할에 따라 적절한 라인 찾기
                                    role_type = "서포터" if role.lower() in ["서포터", "폿", "서폿"] else "딜러"
                                    
                                    for j in range(round_index + 1, len(lines)):
                                        if f"{role_type}(" in lines[j] and user in lines[j]:
                                            # 현재 인원 수 파싱
                                            current_line = lines[j]
                                            count_pattern = rf"{role_type}\((\d+)/(\d+)\):"
                                            count_match = re.search(count_pattern, current_line)
                                            
                                            if count_match:
                                                current_count = int(count_match.group(1))
                                                max_count = int(count_match.group(2))
                                                
                                                # 인원 수 업데이트
                                                new_count = max(0, current_count - 1)
                                                
                                                # 참가자 제거
                                                if f", {user}" in current_line:
                                                    current_line = current_line.replace(f", {user}", "")
                                                elif f"{user}, " in current_line:
                                                    current_line = current_line.replace(f"{user}, ", "")
                                                else:
                                                    current_line = current_line.replace(user, "")
                                                
                                                # 인원 수 텍스트 업데이트
                                                current_line = current_line.replace(f"{role_type}({current_count}/{max_count}):", f"{role_type}({new_count}/{max_count}):")
                                                
                                                lines[j] = current_line
                                                changes_made = True
                                                changes_description.append(f"{user} {round_name}에서 {role_type} 참가 취소")
                                            break
            
            if changes_made:
                # 업데이트된 내용으로 메시지 수정
                updated_content = '\n'.join(lines)
                
                # 메시지 길이 제한 확인
                if len(updated_content) > 2000:
                    print(f"경고: 메시지가 Discord 길이 제한(2000자)을 초과합니다. 길이: {len(updated_content)}자")
                    updated_content = updated_content[:1997] + "..."
                
                await message.edit(content=updated_content)
                
                # 결과 반환
                changes_summary = "\n".join(changes_description)
                log_message = f"'{thread_name}' 메시지 업데이트 완료: {len(changes_description)}개 변경\n{changes_summary}"
                print(log_message)
                
                if ctx:
                    await ctx.send(f"메시지 업데이트 완료: {len(changes_description)}개 변경\n{changes_summary}")
                
                return True, changes_description
            else:
                log_message = f"'{thread_name}' 메시지 변경 사항이 없습니다."
                print(log_message)
                
                if ctx:
                    await ctx.send("메시지 변경 사항이 없습니다.")
                
                return False, []
                
        except Exception as e:
            error_message = f"명령어 처리 중 오류 발생: {e}"
            print(error_message)
            if ctx:
                await ctx.send(error_message)
            return False, [error_message]

    async def auto_update_raid_message(self, thread):
        """(자동) 스레드 내 메시지 분석하여 원본 레이드 메시지 업데이트"""
        try:
            # 레이드 채널 가져오기
            channel = self.bot.get_channel(self.schedule_channel_id)
            if not channel:
                print("스케줄 채널을 찾을 수 없습니다.")
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
                    print(f"메시지 확인 중 오류: {e}")
                    continue
            
            # 찾지 못한 경우 스레드 이름으로 검색
            if not message:
                async for msg in channel.history(limit=100):
                    if thread.name.lower() in msg.content.lower():
                        message = msg
                        break
            
            if not message:
                print(f"'{thread.name}' 스레드의 원본 메시지를 찾을 수 없습니다.")
                return
            
            # 레이드 이름 추출
            raid_name = "알 수 없음"
            if message.content.startswith("# "):
                raid_name = message.content.split("\n")[0][2:]
                if " (" in raid_name:
                    raid_name = raid_name.split(" (")[0]
                
            # 스레드 메시지 가져오기
            thread_messages = await self.get_thread_messages(thread)
            
            # 새 메시지가 없는 경우 업데이트 건너뛰기
            if not thread_messages:
                print(f"'{thread.name}' 스레드에 새로운 메시지가 없어 업데이트를 건너뜁니다.")
                return
            
            # OpenAI를 사용하여 메시지 분석
            print(f"'{thread.name}' 스레드 메시지 분석 시작 (새 메시지 {len(thread_messages)}개)")
            analysis_result = await self.analyze_messages_with_openai(thread_messages, message.content, raid_name)
            
            if "error" in analysis_result:
                print(f"메시지 분석 오류: {analysis_result['error']}")
                return
            
            # 명령어 처리 및 메시지 업데이트
            if "commands" in analysis_result:
                await self.process_commands_and_update_message(
                    message=message,
                    commands=analysis_result["commands"],
                    thread_name=thread.name
                )
            else:
                print(f"'{thread.name}' 스레드 메시지 분석 결과에 commands가 없습니다.")
            
        except Exception as e:
            print(f"자동 메시지 업데이트 오류: {e}")
    
    @commands.command(name="analyze")
    @commands.has_permissions(manage_messages=True)
    async def analyze_threads(self, ctx, channel_id: Optional[int] = None):
        """
        지정된 채널의 모든 스레드를 분석하고 레이드 메시지를 업데이트합니다.
        채널 ID가 지정되지 않으면 현재 채널을 사용합니다.
        """
        # 분석할 채널 결정
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await ctx.send(f"채널 ID {channel_id}를 찾을 수 없습니다.")
                return
        else:
            channel = ctx.channel
        
        # 채널 타입 확인
        if not isinstance(channel, discord.TextChannel):
            await ctx.send(f"채널 '{channel.name}'은(는) 텍스트 채널이 아닙니다. 텍스트 채널만 지원됩니다.")
            return
        
        # 작업 시작 메시지
        status_message = await ctx.send(f"'{channel.name}' 채널의 모든 스레드를 분석하는 중...")
        
        try:
            # 채널의 모든 스레드 가져오기
            threads = []
            async for thread in channel.archived_threads(limit=None):
                threads.append(thread)
            
            active_threads = channel.threads
            for thread in active_threads:
                threads.append(thread)
            
            if not threads:
                await status_message.edit(content=f"'{channel.name}' 채널에 분석할 스레드가 없습니다.")
                return
            
            updated_count = 0
            error_count = 0
            
            # 각 스레드 분석
            for thread in threads:
                try:
                    await status_message.edit(content=f"스레드 '{thread.name}' 분석 중... ({threads.index(thread) + 1}/{len(threads)})")
                    
                    # 스레드 내 메시지 분석
                    await self.update_raid_message(ctx, thread)
                    
                except Exception as e:
                    error_count += 1
                    print(f"스레드 '{thread.name}' 처리 중 오류 발생: {e}")
            
            # 최종 결과 메시지 업데이트
            await status_message.edit(
                content=f"분석 완료: 총 {len(threads)}개 스레드 중 {updated_count}개 업데이트됨, {error_count}개 오류 발생"
            )
            
        except Exception as e:
            await status_message.edit(content=f"스레드 분석 중 오류 발생: {e}")
    
    @analyze_threads.error
    async def analyze_threads_error(self, ctx, error):
        """analyze_threads 명령어의 오류 처리"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 사용하려면 메시지 관리 권한이 필요합니다.")
        else:
            await ctx.send(f"오류 발생: {error}")

    async def update_raid_message(self, ctx, thread):
        """스레드 내 메시지 분석하여 원본 레이드 메시지 업데이트"""
        try:
            # 원본 메시지 가져오기
            schedule_channel_id = os.getenv("SCHEDULE_CHANNEL_ID")
            if not schedule_channel_id:
                await ctx.send("스케줄 채널 ID가 설정되지 않았습니다.")
                return
            
            channel = self.bot.get_channel(int(schedule_channel_id))
            if not channel:
                await ctx.send("스케줄 채널을 찾을 수 없습니다.")
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
                    print(f"메시지 확인 중 오류: {e}")
                    continue
            
            # 찾지 못한 경우 스레드 이름으로 검색
            if not message:
                async for msg in channel.history(limit=100):
                    if thread.name.lower() in msg.content.lower():
                        message = msg
                        break
            
            if not message:
                await ctx.send("레이드 메시지를 찾을 수 없습니다.")
                return
            
            # 레이드 이름 추출
            raid_name = "알 수 없음"
            if message.content.startswith("# "):
                raid_name = message.content.split("\n")[0][2:]
                if " (" in raid_name:
                    raid_name = raid_name.split(" (")[0]
                
            # 스레드 메시지 가져오기
            thread_messages = await self.get_thread_messages(thread)
            
            # 새 메시지가 없는 경우
            if not thread_messages:
                await ctx.send("봇의 마지막 메시지 이후에 새로운 메시지가 없습니다. 분석이 필요하지 않습니다.")
                return
            
            # 진행 상황 메시지
            progress_msg = await ctx.send(f"'{thread.name}' 스레드 메시지 분석 중... (새 메시지 {len(thread_messages)}개)")
            
            # OpenAI를 사용하여 메시지 분석
            analysis_result = await self.analyze_messages_with_openai(thread_messages, message.content, raid_name)
            
            if "error" in analysis_result:
                await progress_msg.edit(content=f"메시지 분석 오류: {analysis_result['error']}")
                if "raw_content" in analysis_result:
                    await ctx.send(f"원본 응답:\n```json\n{analysis_result['raw_content'][:1000]}\n```")
                return
            
            # 명령어 처리 및 메시지 업데이트
            if "commands" in analysis_result:
                success, changes = await self.process_commands_and_update_message(
                    message=message,
                    commands=analysis_result["commands"],
                    thread_name=thread.name,
                    ctx=ctx
                )
                
                if success:
                    await progress_msg.edit(content=f"'{thread.name}' 스레드 메시지가 업데이트되었습니다.")
                else:
                    await progress_msg.edit(content=f"'{thread.name}' 스레드 메시지 업데이트 중 문제가 발생했습니다.")
            else:
                await progress_msg.edit(content=f"'{thread.name}' 스레드 메시지 분석 결과에 commands가 없습니다.")
            
        except Exception as e:
            print(f"레이드 메시지 업데이트 오류: {e}")
            await ctx.send(f"오류 발생: {e}")

    def cleanup_cache(self):
        """오래된 캐시 파일 정리 (30일 이상 지난 파일)"""
        try:
            current_time = datetime.datetime.now()
            cache_files = list(self.cache_dir.glob('*.json'))
            cleanup_count = 0
            
            for cache_file in cache_files:
                file_time = datetime.datetime.fromtimestamp(cache_file.stat().st_mtime)
                # 30일 이상 지난 파일은 삭제
                if (current_time - file_time).days > 30:
                    cache_file.unlink()
                    cleanup_count += 1
            
            if cleanup_count > 0:
                print(f"오래된 캐시 파일 {cleanup_count}개를 정리했습니다.")
                
            print(f"현재 캐시 파일 개수: {len(list(self.cache_dir.glob('*.json')))}")
        except Exception as e:
            print(f"캐시 정리 중 오류 발생: {e}")

    @commands.command(name="cache_stats")
    @commands.has_permissions(administrator=True)
    async def cache_stats(self, ctx):
        """
        LLM 캐시 통계를 확인합니다.
        사용법: !cache_stats
        """
        try:
            cache_files = list(self.cache_dir.glob('*.json'))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            # 파일 시간 정보
            if cache_files:
                oldest_file = min(cache_files, key=lambda f: f.stat().st_mtime)
                newest_file = max(cache_files, key=lambda f: f.stat().st_mtime)
                
                oldest_time = datetime.datetime.fromtimestamp(oldest_file.stat().st_mtime)
                newest_time = datetime.datetime.fromtimestamp(newest_file.stat().st_mtime)
                
                oldest_str = oldest_time.strftime("%Y-%m-%d %H:%M:%S")
                newest_str = newest_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                oldest_str = "없음"
                newest_str = "없음"
            
            # 임베드 생성
            embed = discord.Embed(
                title="LLM 캐시 통계",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="캐시 위치", value=str(self.cache_dir), inline=False)
            embed.add_field(name="캐시 파일 개수", value=f"{len(cache_files)}개", inline=True)
            embed.add_field(name="총 크기", value=f"{total_size / 1024 / 1024:.2f} MB", inline=True)
            embed.add_field(name="가장 오래된 파일", value=oldest_str, inline=True)
            embed.add_field(name="가장 최근 파일", value=newest_str, inline=True)
            
            await ctx.send(embed=embed)
            
            # 오래된 캐시 정리
            self.cleanup_cache()
            
        except Exception as e:
            await ctx.send(f"캐시 통계 확인 중 오류 발생: {e}")
            
    @cache_stats.error
    async def cache_stats_error(self, ctx, error):
        """cache_stats 명령어의 오류 처리"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 사용하려면 관리자 권한이 필요합니다.")
        else:
            await ctx.send(f"오류 발생: {error}")

    @commands.command(name="clear_cache")
    @commands.has_permissions(administrator=True)
    async def clear_cache(self, ctx):
        """
        LLM 캐시를 모두 삭제합니다.
        사용법: !clear_cache
        """
        try:
            cache_files = list(self.cache_dir.glob('*.json'))
            
            if not cache_files:
                await ctx.send("삭제할 캐시 파일이 없습니다.")
                return
                
            # 확인 메시지
            confirm_msg = await ctx.send(f"{len(cache_files)}개의 캐시 파일을 모두 삭제하시겠습니까? (y/n)")
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['y', 'n']
            
            try:
                # 사용자 응답 대기
                response = await self.bot.wait_for('message', check=check, timeout=30.0)
                
                if response.content.lower() == 'y':
                    # 캐시 삭제
                    for cache_file in cache_files:
                        cache_file.unlink()
                    
                    await ctx.send(f"{len(cache_files)}개의 캐시 파일을 삭제했습니다.")
                else:
                    await ctx.send("캐시 삭제가 취소되었습니다.")
                    
            except asyncio.TimeoutError:
                await ctx.send("시간이 초과되었습니다. 캐시 삭제가 취소되었습니다.")
            
        except Exception as e:
            await ctx.send(f"캐시 삭제 중 오류 발생: {e}")
            
    @clear_cache.error
    async def clear_cache_error(self, ctx, error):
        """clear_cache 명령어의 오류 처리"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 사용하려면 관리자 권한이 필요합니다.")
        else:
            await ctx.send(f"오류 발생: {error}")

# Cog 설정 함수
async def setup(bot):
    await bot.add_cog(ThreadAnalyzer(bot)) 