import discord
from discord.ext import commands
import asyncio
import datetime
import json
import re
import os
import aiohttp
import hashlib
import pathlib
from typing import List, Dict, Any, Optional

class ThreadCommands(commands.Cog):
    """스레드 내 일정 관리 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # 캐시 디렉토리 설정
        self.cache_dir = pathlib.Path('/tmp/discord_bot_llm_cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def cog_check(self, ctx):
        """모든 명령어가 이 검사를 통과해야 함
        
        스레드 내에서는 권한 체크를 우회하여 모든 사용자가 사용 가능
        """
        # 스레드 내에서만 명령 허용
        return isinstance(ctx.channel, discord.Thread)
    
    @commands.command(name="추가")
    async def add_schedule(self, ctx):
        """일정 추가 명령어"""
        # 스레드가 아니면 무시 (cog_check에서 이미 확인하지만 명확성을 위해 유지)
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("이 명령어는 스레드에서만 사용할 수 있습니다.")
            return
            
        await self.process_schedule_command(ctx, "추가")
    
    @commands.command(name="제거")
    async def remove_schedule(self, ctx):
        """일정 제거 명령어"""
        # 스레드가 아니면 무시
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("이 명령어는 스레드에서만 사용할 수 있습니다.")
            return
            
        await self.process_schedule_command(ctx, "제거")
    
    @commands.command(name="수정")
    async def update_schedule(self, ctx):
        """일정 수정 명령어"""
        # 스레드가 아니면 무시
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("이 명령어는 스레드에서만 사용할 수 있습니다.")
            return
            
        await self.process_schedule_command(ctx, "수정")
    
    async def process_schedule_command(self, ctx, command_type):
        """일정 명령어 처리 함수"""
        # 메시지 전송
        processing_msg = await ctx.send(f"일정 {command_type} 요청을 처리 중입니다...")
        
        try:
            # 1. 스레드 원본 메시지 가져오기
            thread = ctx.channel
            parent_message = None
            
            # 스레드가 속한 채널 확인
            parent_channel = thread.parent
            if not parent_channel:
                await processing_msg.edit(content="스레드의 원본 채널을 찾을 수 없습니다.")
                return
                
            # 원본 메시지 찾기
            try:
                # 스레드가 메시지에서 시작된 경우
                if hasattr(thread, 'starter_message_id') and thread.starter_message_id:
                    parent_message = await parent_channel.fetch_message(thread.starter_message_id)
                else:
                    await processing_msg.edit(content="스레드 원본 메시지를 찾을 수 없습니다.")
                    return
            except discord.NotFound:
                await processing_msg.edit(content="스레드 원본 메시지를 찾을 수 없습니다.")
                return
                
            # 2. 스레드 메시지 수집
            thread_messages = []
            async for message in thread.history(limit=100):
                if not message.author.bot:  # 봇 메시지 제외
                    thread_messages.append({
                        'author': message.author.display_name,
                        'author_id': str(message.author.id),
                        'content': message.content,
                        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            # 최신 메시지가 먼저 오기 때문에 순서 뒤집기
            thread_messages.reverse()
            
            # 3. LLM 요청 처리
            result = await self.analyze_schedule_with_llm(
                thread_messages, 
                parent_message.content,
                command_type,
                ctx.author.display_name,
                str(ctx.author.id),
                ctx.message.content
            )
            
            # 오류 확인
            if "error" in result:
                await processing_msg.edit(content=f"오류가 발생했습니다: {result['error']}")
                return
                
            # 4. 원본 메시지 업데이트
            if "updated_content" in result:
                try:
                    await parent_message.edit(content=result["updated_content"])
                    await processing_msg.edit(content=f"일정이 {command_type}되었습니다!")
                except discord.Forbidden:
                    await processing_msg.edit(content="메시지 수정 권한이 없습니다.")
                except discord.HTTPException as e:
                    await processing_msg.edit(content=f"메시지 업데이트 중 오류: {e}")
            else:
                await processing_msg.edit(content="일정 업데이트에 필요한 정보가 충분하지 않습니다.")
                
        except Exception as e:
            await processing_msg.edit(content=f"처리 중 오류가 발생했습니다: {e}")
    
    def get_cache_key(self, thread_messages, message_content, command_type, user_name, user_id, command_message):
        """캐시 키 생성"""
        # 입력 데이터를 문자열로 직렬화
        data_str = json.dumps({
            'thread_messages': thread_messages,
            'message_content': message_content,
            'command_type': command_type,
            'user_name': user_name,
            'user_id': user_id,
            'command_message': command_message
        }, sort_keys=True, ensure_ascii=False)
        
        # SHA-256 해시 생성
        hash_obj = hashlib.sha256(data_str.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def get_cached_result(self, cache_key):
        """캐시에서 결과 가져오기"""
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
    
    def save_to_cache(self, cache_key, result):
        """결과를 캐시에 저장"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"결과를 캐시에 저장했습니다: {cache_key}")
        except Exception as e:
            print(f"캐시 저장 중 오류 발생: {e}")
    
    async def analyze_schedule_with_llm(self, thread_messages, message_content, command_type, user_name, user_id, command_message):
        """OpenAI API를 사용하여 일정 정보 분석"""
        if not self.openai_api_key:
            return {"error": "OpenAI API 키가 설정되지 않았습니다."}
        
        # 캐시 키 생성
        cache_key = self.get_cache_key(thread_messages, message_content, command_type, user_name, user_id, command_message)
        
        # 캐시 확인
        cached_result = self.get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        # 메시지 포맷팅
        formatted_messages = []
        for msg in thread_messages:
            formatted_messages.append(f"{msg['author']} ({msg['created_at']}): {msg['content']}")
        
        messages_text = "\n".join(formatted_messages)
        
        # 분석하려는 대상 스레드의 레이드 이름 추출 시도
        raid_name = "레이드"
        raid_match = re.search(r"#\s+(.*?)\s+\(", message_content)
        if raid_match:
            raid_name = raid_match.group(1)
        
        # OpenAI에 보낼 프롬프트
        prompt = f"""
{user_name}(ID: {user_id})님이 '{raid_name}' 레이드 스레드에서 일정 {command_type} 명령어를 사용했습니다.

## 원본 메시지:
{message_content}

## 스레드 대화 내용:
{messages_text}

## 명령어 메시지:
{command_message}

{user_name}님의 의도를 파악하여 원본 메시지의 일정을 {command_type}해주세요.
다음과 같은 형식으로 원본 메시지를 업데이트해야 합니다:

1. 일정 추가: 일정이 없으면 추가하고, 이미 있으면 새로운 차수 추가
2. 일정 제거: 특정 일정이나 차수를 제거
3. 일정 수정: 기존 일정 정보 변경 (날짜, 시간, 참가자 등)

JSON 형식으로 응답해 주세요. 예시:
```json
{{
  "updated_content": "업데이트된 메시지 내용",
  "changes": "어떤 변경이 이루어졌는지 요약"
}}
```

원본 메시지 형식을 최대한 유지하면서 일정 정보만 업데이트해 주세요.
"""
        
        # API 요청
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.openai_api_key}"
                    },
                    json={
                        "model": "gpt-4-0125-preview",
                        "messages": [
                            {"role": "system", "content": "당신은 디스코드 봇의 일정 관리 기능을 돕는 AI 비서입니다. 일정 추가, 제거, 수정을 위한 요청을 처리하고 응답은 JSON 형식으로 제공합니다."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    }
                ) as response:
                    response_data = await response.json()
                    
                    if "error" in response_data:
                        return {"error": f"OpenAI API 오류: {response_data['error']}"}
                    
                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        content = response_data["choices"][0]["message"]["content"]
                        try:
                            result = json.loads(content)
                            self.save_to_cache(cache_key, result)
                            return result
                        except json.JSONDecodeError:
                            return {"error": "LLM 응답을 JSON으로 파싱할 수 없습니다."}
                    else:
                        return {"error": "LLM 응답에서 데이터를 찾을 수 없습니다."}
        except Exception as e:
            return {"error": f"OpenAI API 요청 중 오류: {e}"}

async def setup(bot):
    """확장 설정"""
    await bot.add_cog(ThreadCommands(bot)) 