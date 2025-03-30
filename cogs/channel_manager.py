import discord
from discord.ext import commands
import asyncio
import os

class ChannelManager(commands.Cog):
    """채널 관리 명령어 모음"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} Cog가 준비되었습니다.')
    
    @commands.command(name="reset")
    @commands.has_permissions(manage_messages=True)
    async def reset_channel(self, ctx):
        """현재 채널의 모든 메시지와 스레드를 삭제합니다."""
        channel = ctx.channel
        
        # 관리자 권한 확인
        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send("이 명령어를 사용하려면 메시지 관리 권한이 필요합니다.")
            return
        
        # 확인 메시지 전송
        confirm_message = await ctx.send(f"⚠️ 경고: 이 작업은 '{channel.name}' 채널의 모든 메시지와 스레드를 삭제합니다. 계속하시겠습니까? (y/n)")
        
        # 사용자 응답 대기
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['y', 'n', 'yes', 'no']
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await confirm_message.edit(content="시간이 초과되었습니다. 채널 초기화가 취소되었습니다.")
            return
        
        if msg.content.lower() not in ['y', 'yes']:
            await ctx.send("채널 초기화가 취소되었습니다.")
            return
        
        status_message = await ctx.send("채널 초기화 작업을 시작합니다...")
        
        try:
            # 채널의 모든 스레드 가져오기
            threads = []
            async for thread in channel.archived_threads(limit=None):
                threads.append(thread)
            
            active_threads = channel.threads
            for thread in active_threads:
                threads.append(thread)
            
            # 스레드 삭제
            thread_count = len(threads)
            if thread_count > 0:
                await status_message.edit(content=f"스레드 {thread_count}개 삭제 중...")
                
                for thread in threads:
                    try:
                        await thread.delete()
                    except discord.Forbidden:
                        await ctx.send(f"스레드 '{thread.name}' 삭제 권한이 없습니다.")
                    except discord.HTTPException as e:
                        await ctx.send(f"스레드 '{thread.name}' 삭제 중 오류 발생: {e}")
            
            # 메시지 삭제 (진행 상황 보고를 위한 메시지 제외)
            await status_message.edit(content="메시지 삭제 중... 이 작업은 시간이 걸릴 수 있습니다.")
            
            # status_message ID를 보존하여 삭제하지 않음
            status_id = status_message.id
            confirm_id = confirm_message.id
            user_reply_id = msg.id
            
            deleted_count = 0
            async for message in channel.history(limit=None):
                # 상태 메시지와 확인 메시지는 건너뜀
                if message.id in [status_id, confirm_id, user_reply_id]:
                    continue
                    
                try:
                    await message.delete()
                    deleted_count += 1
                    
                    # 10개 메시지마다 상태 업데이트 (API 속도 제한 방지)
                    if deleted_count % 10 == 0:
                        await status_message.edit(content=f"메시지 삭제 중... {deleted_count}개 완료")
                        await asyncio.sleep(1)
                    else:
                        await asyncio.sleep(0.5)
                        
                except discord.Forbidden:
                    await status_message.edit(content="메시지 삭제 권한이 없습니다.")
                    return
                except discord.HTTPException:
                    continue
            
            # 완료 메시지 업데이트
            await status_message.edit(content=f"채널 초기화 완료: {deleted_count}개의 메시지와 {thread_count}개의 스레드가 삭제되었습니다.")
            
        except Exception as e:
            await status_message.edit(content=f"채널 초기화 중 오류 발생: {e}")
    
    @reset_channel.error
    async def reset_channel_error(self, ctx, error):
        """reset_channel 명령어의 오류 처리"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 사용하려면 메시지 관리 권한이 필요합니다.")
        else:
            await ctx.send(f"오류 발생: {error}")

# Cog 설정 함수
async def setup(bot):
    await bot.add_cog(ChannelManager(bot)) 