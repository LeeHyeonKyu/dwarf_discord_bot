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
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "당신은 디스코드 대화에서 정보를 추출하여 메시지를 업데이트하는 도우미입니다."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3
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
                        content = response_data['choices'][0]['message']['content']
                        
                        # 텍스트 정제 (불필요한 설명이나 마크다운 포맷 제거)
                        if "```" in content:
                            # 코드 블록 내용만 추출
                            content = content.split("```")[1].strip()
                            if content.startswith("markdown\n") or content.startswith("md\n"):
                                content = "\n".join(content.split("\n")[1:])
                        
                        result = {"content": content}
                        
                        # 결과를 캐시에 저장
                        self._save_to_cache(cache_key, result)
                        
                        return result
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