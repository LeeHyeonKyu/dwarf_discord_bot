#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
키워드로 환경변수에서 채널 ID를 찾아 초기화하는 스크립트.

이 스크립트는 지정된 키워드에 해당하는 환경변수의 채널 ID를 사용하여
해당 채널의 모든 스레드와 메시지를 초기화합니다.
"""

import asyncio
import logging
import os
import sys
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("channel_cleaner")

# 환경 변수 로드
load_dotenv(".env.secret")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
AUTHORIZED_USERS = os.getenv("AUTHORIZED_USERS", "").split(",")

# 채널 키워드 매핑 (모두 대문자로 변환하여 비교)
CHANNEL_KEYWORDS = {
    "test": "TEST_CHANNEL_ID",
    "members": "MEMBERS_CHANNEL_ID",
    "levelup": "LEVELUP_CHANNEL_ID",
    "schedule": "SCHEDULE_CHANNEL_ID"
}


class MockMessage:
    """
    가상 메시지 객체.
    
    edit 메서드를 구현하여 progress_msg.edit() 호출을 지원합니다.
    """
    def __init__(self, content: str = "", channel: Optional[discord.abc.Messageable] = None):
        self.content = content
        self.channel = channel
    
    async def edit(self, content: str = None, **kwargs):
        """
        메시지 수정 동작을 시뮬레이션합니다.
        
        Args:
            content: 새 메시지 내용
            **kwargs: 추가 매개변수
        """
        if content:
            self.content = content
            logger.info(f"메시지 수정됨: {content}")
        return self
    
    async def add_reaction(self, emoji):
        """
        이모지 반응 추가를 시뮬레이션합니다.
        
        Args:
            emoji: 추가할 이모지
        """
        logger.debug(f"이모지 추가됨: {emoji}")
        return self


async def patch_channel_messages_cog(bot: commands.Bot) -> None:
    """
    ChannelMessages Cog를 패치하여 progress_msg.edit 오류를 방지합니다.
    
    Args:
        bot: 봇 인스턴스
    """
    channel_messages_cog = bot.get_cog("ChannelMessages")
    if not channel_messages_cog:
        logger.error("ChannelMessages Cog를 찾을 수 없습니다.")
        return
    
    # 원본 clean_channel 메서드 참조 저장
    original_clean_channel = channel_messages_cog.clean_channel
    
    # 패치된 clean_channel 메서드 생성
    async def patched_clean_channel(self, ctx, channel_id, limit=100):
        try:
            # 권한 체크
            if not await self.check_authorized(ctx):
                return
            
            # 서버 확인
            if not ctx.guild:
                await ctx.send("이 명령어는 서버 내에서만 사용 가능합니다.")
                return
                
            # 메시지 삭제 제한 설정
            if limit is not None and limit > 1000:
                limit = 1000
                await ctx.send("안전을 위해 메시지 삭제는 최대 1000개로 제한됩니다.")
            
            try:
                # 채널 찾기 (동기 함수 사용)
                channel = self.get_channel_by_id(channel_id)
                if not channel:
                    await ctx.send(f"채널을 찾을 수 없습니다: {channel_id}")
                    return
                
                # 텍스트 채널 확인 (동기 함수 사용)
                if not self.is_text_channel(channel):
                    await ctx.send(f"해당 ID({channel_id})는 텍스트 채널이 아닙니다.")
                    return
                
                # 채널에 대한 권한 확인
                channel_typed = discord.utils.get(ctx.guild.text_channels, id=int(channel_id))
                if not channel_typed:
                    await ctx.send(f"채널을 찾을 수 없습니다: {channel_id}")
                    return
                    
                me = ctx.guild.me if ctx.guild else None
                if not me:
                    await ctx.send("서버 정보를 가져올 수 없습니다.")
                    return
                    
                if not channel_typed.permissions_for(me).manage_threads:
                    await ctx.send("해당 채널의 스레드를 관리할 권한이 없습니다.")
                    return
                
                if not channel_typed.permissions_for(me).manage_messages:
                    await ctx.send("해당 채널의 메시지를 관리할 권한이 없습니다.")
                    return
                
                # 진행 상황 메시지 (MockMessage로 대체)
                logger.info(f"채널 {channel_typed.mention} 정리 시작... 스레드를 확인 중입니다.")
                # await ctx.send() 대신 MockMessage 생성
                progress_msg = MockMessage(f"채널 {channel_typed.mention} 정리 시작... 스레드를 확인 중입니다.")
                
                # 스레드 수 확인 (동기 함수 사용)
                thread_count = self.count_active_threads(channel_typed)
                
                # 스레드 삭제 진행
                deleted_threads = 0
                for thread in channel_typed.threads:
                    try:
                        await thread.delete()
                        deleted_threads += 1
                        # 진행 상황 업데이트 로깅
                        if deleted_threads % 5 == 0 or deleted_threads == thread_count:
                            logger.info(f"채널 {channel_typed.mention} 정리 중... {deleted_threads}/{thread_count} 스레드 삭제 완료")
                    except Exception as e:
                        logger.error(f"스레드 삭제 중 오류 발생: {str(e)}")
                
                # 스레드 삭제 완료 메시지
                if thread_count > 0:
                    logger.info(f"채널 {channel_typed.mention}의 모든 스레드({deleted_threads}개) 삭제 완료. 메시지 삭제를 시작합니다...")
                else:
                    logger.info(f"채널 {channel_typed.mention}에 삭제할 스레드가 없습니다. 메시지 삭제를 시작합니다...")
                
                # 메시지 삭제
                try:
                    deleted_count = await channel_typed.purge(limit=limit)
                    await ctx.send(f"채널 {channel_typed.mention} 정리 완료! {deleted_threads}개의 스레드와 {len(deleted_count)}개의 메시지를 삭제했습니다.")
                except discord.errors.HTTPException as e:
                    logger.error(f"메시지 삭제 중 HTTP 오류 발생: {str(e)}")
                    await ctx.send(f"메시지 삭제 중 오류가 발생했습니다. 일부 메시지는 너무 오래되어 일괄 삭제할 수 없을 수 있습니다.")
                    logger.info(f"채널 {channel_typed.mention} 정리 부분 완료. {deleted_threads}개의 스레드는 삭제되었으나, 메시지 삭제 중 오류가 발생했습니다.")
            
            except discord.Forbidden:
                await ctx.send("해당 채널을 정리할 권한이 없습니다.")
            except Exception as e:
                logger.error(f"채널 정리 중 오류 발생: {str(e)}", exc_info=True)
                await ctx.send(f"채널 정리 중 오류가 발생했습니다: {str(e)}")
        except Exception as e:
            logger.error(f"채널 정리 명령어 실행 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"오류 발생: {str(e)}")
    
    # 원본 메서드를 패치된 메서드로 대체
    channel_messages_cog.clean_channel = patched_clean_channel.__get__(channel_messages_cog, type(channel_messages_cog))
    
    logger.info("ChannelMessages Cog의 clean_channel 메서드가 패치되었습니다.")


async def clean_channel_by_keyword(keyword: str, message_limit: int = 100) -> None:
    """
    키워드에 해당하는 채널을 초기화합니다.
    
    Args:
        keyword: 채널 키워드 (test, members 등)
        message_limit: 삭제할 메시지 개수 (기본값: 100)
    """
    # 키워드 검사
    keyword_lower = keyword.lower()
    if keyword_lower not in CHANNEL_KEYWORDS:
        logger.error(f"지원되지 않는 키워드입니다: {keyword}")
        logger.info(f"사용 가능한 키워드: {', '.join(CHANNEL_KEYWORDS.keys())}")
        return
    
    # 환경 변수에서 채널 ID 가져오기
    env_var_name = CHANNEL_KEYWORDS[keyword_lower]
    channel_id = os.getenv(env_var_name)
    
    if not channel_id:
        logger.error(f"환경 변수 {env_var_name}에 채널 ID가 설정되지 않았습니다.")
        return
    
    logger.info(f"키워드 '{keyword}'에 해당하는 채널 ID: {channel_id}")
    
    # 봇 토큰 확인
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN이 설정되지 않았습니다.")
        return
    
    # 봇 초기화
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready() -> None:
        """봇이 준비되면 실행되는 이벤트 핸들러."""
        if bot.user:
            logger.info(f"{bot.user.name}으로 로그인했습니다.")
        else:
            logger.info("봇에 로그인했습니다.")
        
        try:
            # 필요한 Cog 로드
            from cogs.channel_messages import setup
            await setup(bot)
            logger.info("ChannelMessages Cog가 로드되었습니다.")
            
            # Cog 패치
            await patch_channel_messages_cog(bot)
            
            # 채널 명령어 직접 실행
            await execute_channel_command(channel_id, message_limit)
            
            # 작업 완료 대기
            logger.info("초기화 명령을 실행했습니다. 작업이 완료될 때까지 10초 기다립니다...")
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"채널 초기화 중 오류 발생: {str(e)}", exc_info=True)
        finally:
            # 봇 종료
            await bot.close()
    
    async def execute_channel_command(channel_id: str, limit: int) -> None:
        """
        채널 초기화 명령어를 실행합니다.
        
        Args:
            channel_id: 초기화할 채널 ID
            limit: 삭제할 메시지 개수
        """
        try:
            # 채널 찾기
            channel = bot.get_channel(int(channel_id))
            if not channel:
                logger.error(f"채널을 찾을 수 없습니다: {channel_id}")
                return
            
            # 직접 명령어 메시지를 생성하여 처리
            # 봇이 권한을 갖도록 AUTHORIZED_USERS에서 첫 번째 ID를 사용 (또는 없으면 임의의 ID)
            auth_user_id = AUTHORIZED_USERS[0] if AUTHORIZED_USERS else "123456789012345678"
            
            # 메시지 생성
            message_content = f"!채널정리 {channel_id} {limit}"
            
            # 봇이 명령어를 처리하도록 함
            logger.info(f"명령어 실행: {message_content} (권한 있는 사용자 ID: {auth_user_id})")
            
            # 간소화된 사용자 클래스
            class SimpleUser:
                def __init__(self, user_id: str) -> None:
                    self.id = int(user_id)
                    self.name = f"User_{user_id}"
                    self.display_name = self.name
                    self.mention = f"<@{user_id}>"
                    self.bot = False
            
            # 간소화된 컨텍스트 클래스
            class SimpleContext:
                def __init__(self, channel_obj, author_obj, guild_obj=None) -> None:
                    self.channel = channel_obj
                    self.author = author_obj
                    self.guild = guild_obj
                    self.bot = bot
                
                async def send(self, content=None, **kwargs):
                    """메시지 전송을 시뮬레이션하고 MockMessage 객체를 반환합니다."""
                    logger.info(f"봇 응답: {content}")
                    return MockMessage(content, self.channel)
            
            # 간단한 컨텍스트 생성
            guild = getattr(channel, 'guild', None)
            user = SimpleUser(auth_user_id)
            ctx = SimpleContext(channel, user, guild)
            
            # 명령어 실행
            cog = bot.get_cog("ChannelMessages")
            if cog:
                await cog.clean_channel(ctx, channel_id, limit)
            else:
                logger.error("ChannelMessages Cog를 찾을 수 없습니다.")
            
        except Exception as e:
            logger.error(f"명령어 실행 중 오류 발생: {str(e)}", exc_info=True)
    
    # 봇 실행
    try:
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"봇 실행 중 오류 발생: {str(e)}", exc_info=True)


if __name__ == "__main__":
    import argparse
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="키워드로 채널을 찾아 초기화하는 스크립트")
    parser.add_argument("keyword", type=str, help="채널 키워드 (test, members, levelup, schedule)")
    parser.add_argument("--limit", type=int, default=100, help="삭제할 메시지 개수 (기본값: 100)")
    
    args = parser.parse_args()
    
    # 키워드로 채널 초기화 실행
    logger.info(f"키워드 '{args.keyword}'로 채널 초기화를 시작합니다...")
    asyncio.run(clean_channel_by_keyword(args.keyword, args.limit))