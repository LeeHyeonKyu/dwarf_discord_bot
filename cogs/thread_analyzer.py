import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import aiohttp
import datetime
from typing import Optional

class ThreadAnalyzer(commands.Cog):
    """스레드 메시지를 분석하여 레이드 정보를 업데이트하는 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.raids_channel_id = int(os.getenv("RAIDS_CHANNEL_ID", "0"))
        if not self.openai_api_key:
            print("경고: OPENAI_API_KEY가 설정되지 않았습니다.")
        
        # 자동 분석 작업 시작
        self.auto_analyze_threads.start()
    
    async def cog_unload(self):
        """Cog가 언로드될 때 작업 중지"""
        self.auto_analyze_threads.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} Cog가 준비되었습니다.')
    
    async def get_thread_messages(self, thread):
        """스레드에서 메시지 가져오기"""
        messages = []
        
        try:
            # 스레드의 모든 메시지 가져오기
            async for message in thread.history(limit=100, oldest_first=True):
                if message.author.bot:
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
            
            return messages
        
        except Exception as e:
            print(f"스레드 메시지 가져오기 오류: {e}")
            return []
    
    async def analyze_messages_with_openai(self, thread_messages, message_content, raid_name):
        """OpenAI API를 사용하여 메시지 분석"""
        if not self.openai_api_key:
            return {"error": "OpenAI API 키가 설정되지 않았습니다. .env.secret 파일을 확인해주세요."}
        
        # 메시지 포맷팅
        formatted_messages = []
        for msg in thread_messages:
            formatted_messages.append(f"{msg['author']} ({msg['created_at']}): {msg['content']}")
        
        messages_text = "\n".join(formatted_messages)
        
        # 디스코드 ID 매핑 생성
        user_ids = {}
        for msg in thread_messages:
            user_ids[msg['author']] = msg['author_id']
        
        # OpenAI에 보낼 프롬프트
        prompt = f"""
이것은 '{raid_name}' 레이드 참가에 관한 디스코드 스레드의 원본 메시지와 대화 내용입니다.

## 원본 메시지:
{message_content}

## 스레드 대화 내용:
{messages_text}

대화 내용을 분석하여 원본 메시지를 업데이트해주세요:
1. 참가자 목록을 서포터와 딜러로 구분하여 추가하세요
2. 참가자 이름은 디스코드 멘션 형식(<@사용자ID>)으로 변경해주세요
   - 사용자 ID 정보: {json.dumps(user_ids, ensure_ascii=False)}
3. 일정 정보(날짜, 시간)가 있으면 추가하세요
   - 날짜 형식은 "월/일(요일)" 형태로 통일해주세요 (예: "7/5(수)")
   - 시간은 24시간제로 표시해주세요 (예: "21:00")
   - 날짜와 시간은 함께 표시하세요 (예: "7/5(수) 21:00")
4. 추가 정보(메모, 특이사항 등)가 있으면 추가하세요
5. 2차, 3차 등의 추가 일정이 언급되었다면 새 섹션으로 추가하세요

## 참가자 규칙:
- 8인 레이드의 경우 서포터는 최대 2명까지만 가능합니다
- 4인 레이드의 경우 서포터는 최대 1명만 가능합니다
- "폿1딜2 참여"와 같은 메시지는 총 3번에 걸쳐서 참여하겠다는 의미입니다
  (서포터로 1번, 딜러로 2번 참여)
- 특정 차수를 지정하지 않은 경우, 모든 일정에 해당 참가자를 추가해야 합니다
- 서포터가 이미 최대 인원인 경우, 새로운 차수(예: 다음 차수)를 생성하여 초과된 서포터를 배정하세요

원본 메시지 형식을 유지하면서 대화 내용에서 파악한 정보를 채워넣은 완성된 메시지를 반환해주세요.
추가 설명 없이 업데이트된 메시지 내용만 반환해주세요.
"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "당신은 디스코드 대화에서 정보를 추출하여 메시지를 업데이트하는 도우미입니다."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions", 
                    headers=headers, 
                    json=payload
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        content = response_data['choices'][0]['message']['content']
                        
                        # 텍스트 정제 (불필요한 설명이나 마크다운 포맷 제거)
                        if "```" in content:
                            # 코드 블록 내용만 추출
                            content = content.split("```")[1].strip()
                            if content.startswith("markdown\n") or content.startswith("md\n"):
                                content = "\n".join(content.split("\n")[1:])
                        
                        return {"content": content}
                    else:
                        return {"error": f"OpenAI API 오류: 상태 코드 {response.status}"}
        
        except Exception as e:
            return {"error": f"OpenAI API 오류: {str(e)}"}
    
    @tasks.loop(minutes=30)
    async def auto_analyze_threads(self):
        """30분마다 모든 레이드 스레드를 자동으로 분석하고 업데이트"""
        if self.raids_channel_id == 0:
            print("레이드 채널 ID가 설정되지 않아 자동 분석을 건너뜁니다.")
            return
        
        print(f"{datetime.datetime.now()} - 자동 스레드 분석 시작")
        
        channel = self.bot.get_channel(self.raids_channel_id)
        if not channel:
            print(f"레이드 채널을 찾을 수 없습니다: {self.raids_channel_id}")
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
        
    async def auto_update_raid_message(self, thread):
        """(자동) 스레드 내 메시지 분석하여 원본 레이드 메시지 업데이트"""
        try:
            # 레이드 채널 가져오기
            channel = self.bot.get_channel(self.raids_channel_id)
            if not channel:
                print("레이드 채널을 찾을 수 없습니다.")
                return
            
            # 스레드의 소유자 메시지 찾기
            message = None
            async for msg in channel.history(limit=100):
                for thrd in msg.threads:
                    if thrd.id == thread.id:
                        message = msg
                        break
                if message:
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
            if not thread_messages:
                print(f"'{thread.name}' 스레드에 분석할 메시지가 없습니다.")
                return
            
            # OpenAI를 사용하여 메시지 분석
            analysis_result = await self.analyze_messages_with_openai(thread_messages, message.content, raid_name)
            
            if "error" in analysis_result:
                print(f"메시지 분석 오류: {analysis_result['error']}")
                return
            
            # 메시지 업데이트
            await message.edit(content=analysis_result["content"])
            print(f"'{thread.name}' 스레드 메시지가 자동으로 업데이트되었습니다.")
            
        except Exception as e:
            print(f"자동 메시지 업데이트 오류: {e}")
            raise
    
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
            raids_channel_id = os.getenv("RAIDS_CHANNEL_ID")
            if not raids_channel_id:
                await ctx.send("레이드 채널 ID가 설정되지 않았습니다.")
                return
            
            channel = self.bot.get_channel(int(raids_channel_id))
            if not channel:
                await ctx.send("레이드 채널을 찾을 수 없습니다.")
                return
            
            # 스레드의 소유자 메시지 찾기
            message = None
            async for msg in channel.history(limit=100):
                for thrd in msg.threads:
                    if thrd.id == thread.id:
                        message = msg
                        break
                if message:
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
            if not thread_messages:
                await ctx.send("분석할 메시지가 없습니다.")
                return
            
            # OpenAI를 사용하여 메시지 분석
            analysis_result = await self.analyze_messages_with_openai(thread_messages, message.content, raid_name)
            
            if "error" in analysis_result:
                await ctx.send(f"메시지 분석 오류: {analysis_result['error']}")
                return
            
            # 메시지 업데이트
            await message.edit(content=analysis_result["content"])
            await ctx.send("레이드 메시지가 업데이트되었습니다.")
            
        except Exception as e:
            print(f"레이드 메시지 업데이트 오류: {e}")
            await ctx.send(f"오류 발생: {e}")

# Cog 설정 함수
async def setup(bot):
    await bot.add_cog(ThreadAnalyzer(bot)) 