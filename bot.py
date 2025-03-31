import os
import sys
import discord
from discord.ext import commands
import asyncio
import logging
from typing import Dict, Any
import yaml
from dotenv import load_dotenv

# 로깅 설정
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

# 표준 출력으로 로그 보내기
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# root 로거 설정도 업데이트
root_logger = logging.getLogger()
if not root_logger.handlers:
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

# 설정 파일 로드
def load_config():
    config_path = 'configs/config.yaml'
    
    # 기본 설정값
    config = {
        "TOKEN": os.environ.get("DISCORD_TOKEN", ""),
        "TEST_CHANNEL_ID": os.environ.get("TEST_CHANNEL_ID", ""),
        "MEMBERS_CHANNEL_ID": os.environ.get("MEMBERS_CHANNEL_ID", ""),
        "UPDATES_CHANNEL_ID": os.environ.get("UPDATES_CHANNEL_ID", ""),
        "LEVELUP_CHANNEL_ID": os.environ.get("LEVELUP_CHANNEL_ID", ""),
        "SCHEDULE_CHANNEL_ID": os.environ.get("SCHEDULE_CHANNEL_ID", ""),
        "LOSTARK_API_KEY": os.environ.get("LOSTARK_API_KEY", ""),
        "CHECK_INTERVAL_MINUTES": 30,
        "TIMEZONE": "Asia/Seoul",
        "LOCALE": "ko_KR",
        "AUTHORIZED_USERS": []  # 명령어 사용이 허가된 사용자 ID 목록
    }
    
    # .env.secret 파일에서 민감한 정보 로드
    if os.path.exists('.env.secret'):
        load_dotenv('.env.secret')
        config["TOKEN"] = os.environ.get("DISCORD_TOKEN", "")
        config["TEST_CHANNEL_ID"] = os.environ.get("TEST_CHANNEL_ID", "")
        config["MEMBERS_CHANNEL_ID"] = os.environ.get("MEMBERS_CHANNEL_ID", "")
        config["UPDATES_CHANNEL_ID"] = os.environ.get("UPDATES_CHANNEL_ID", "")
        config["SCHEDULE_CHANNEL_ID"] = os.environ.get("SCHEDULE_CHANNEL_ID", "")
        config["LOSTARK_API_KEY"] = os.environ.get("LOSTARK_API_KEY", "")
        
        # 명령어 사용이 허가된 사용자 ID 목록
        authorized_users = os.environ.get("AUTHORIZED_USERS", "")
        if authorized_users:
            config["AUTHORIZED_USERS"] = [user_id.strip() for user_id in authorized_users.split(',')]
    
    # configs/config.yaml 파일에서 기타 설정 로드
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                # 민감한 정보를 제외한 다른 설정들만 업데이트
                for key, value in yaml_config.items():
                    if key not in ["TOKEN", "TEST_CHANNEL_ID", "MEMBERS_CHANNEL_ID", "UPDATES_CHANNEL_ID", "SCHEDULE_CHANNEL_ID", "LOSTARK_API_KEY"]:
                        config[key] = value
    
    return config

# 인텐트 설정 (권한)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class DwarfBot(commands.Bot):
    """드워프 디스코드 봇 클래스"""
    
    def __init__(self):
        self.config = load_config()
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
    
    # 명령어 권한 검사 함수
    async def is_authorized(self, ctx):
        """명령어 사용 권한 검사 - 특정 사용자만 명령어 사용 가능"""
        # 스레드 명령어는 모든 사용자가 사용 가능
        if ctx.command and ctx.command.name in ['추가', '제거', '수정'] and isinstance(ctx.channel, discord.Thread):
            return True
            
        authorized_users = self.config.get("AUTHORIZED_USERS", [])
        
        # 권한 목록이 비어있으면 모든 사용자 허용 (설정 전이므로)
        if not authorized_users:
            return True
            
        # 사용자 ID가 허용 목록에 있는지 확인
        return str(ctx.author.id) in authorized_users
        
    async def setup_hook(self):
        # cogs 디렉토리 생성
        os.makedirs('cogs', exist_ok=True)
        
        # 명령어 권한 체크 추가
        self.add_check(self.is_authorized)
        
        # cogs 확장 로드
        for extension in ['cogs.message_handler', 'cogs.lostark', 'cogs.character_updater', 'cogs.raid', 'cogs.event_handler', 'cogs.scheduler', 'cogs.channel_manager', 'cogs.thread_analyzer', 'cogs.raid_commands', 'cogs.schedule', 'cogs.thread_commands']:
            try:
                await self.load_extension(extension)
                logger.info(f'{extension} 확장을 로드했습니다.')
            except Exception as e:
                logger.error(f'{extension} 확장을 로드하는 중 오류가 발생했습니다: {e}')
        
        logger.info('확장 모듈 로드 완료')
        
    async def on_ready(self):
        logger.info(f'{self.user}로 로그인했습니다!')
        logger.info('------')
        
        # 상태 메시지 설정
        await self.change_presence(activity=discord.Game(name="!help 명령어로 도움말 확인"))
    
    async def on_command_error(self, ctx, error):
        """명령어 처리 중 오류 발생 시 처리"""
        if isinstance(error, commands.errors.CheckFailure):
            # 권한 체크 실패 시 메시지 전송
            await ctx.send("이 명령어를 사용할 권한이 없습니다.")
        else:
            # 다른 오류는 로거에 출력
            logger.error(f"명령어 처리 중 오류 발생: {error}")

# 봇 실행
async def main():
    bot = DwarfBot()
    config = bot.config
    
    if not config.get("TOKEN"):
        logger.error("디스코드 토큰이 설정되지 않았습니다. configs/config.yaml 파일을 확인해주세요.")
        return
        
    # 봇 시작
    logger.info("봇 시작 시도 중...")
    async with bot:
        await bot.start(config["TOKEN"])

# 메인 함수 실행
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"봇 실행 중 치명적 오류 발생: {e}", exc_info=True) 