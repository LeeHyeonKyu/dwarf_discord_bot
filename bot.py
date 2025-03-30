import os
import sys
import discord
from discord.ext import commands
import asyncio
from typing import Dict, Any
import yaml
from dotenv import load_dotenv

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
        "LOCALE": "ko_KR"
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
        
    async def setup_hook(self):
        # cogs 디렉토리 생성
        os.makedirs('cogs', exist_ok=True)
        
        # cogs 확장 로드
        for extension in ['cogs.message_handler', 'cogs.lostark', 'cogs.character_updater', 'cogs.raid', 'cogs.event_handler', 'cogs.scheduler', 'cogs.channel_manager', 'cogs.thread_analyzer', 'cogs.raid_commands', 'cogs.schedule']:
            try:
                await self.load_extension(extension)
                print(f'{extension} 확장을 로드했습니다.')
            except Exception as e:
                print(f'{extension} 확장을 로드하는 중 오류가 발생했습니다: {e}')
        
        print('확장 모듈 로드 완료')
        
    async def on_ready(self):
        print(f'{self.user}로 로그인했습니다!')
        print('------')
        
        # 상태 메시지 설정
        await self.change_presence(activity=discord.Game(name="!help 명령어로 도움말 확인"))

# 봇 실행
async def main():
    bot = DwarfBot()
    config = bot.config
    
    if not config.get("TOKEN"):
        print("디스코드 토큰이 설정되지 않았습니다. configs/config.yaml 파일을 확인해주세요.")
        return
        
    # 봇 시작
    async with bot:
        await bot.start(config["TOKEN"])

# 메인 함수 실행
if __name__ == "__main__":
    asyncio.run(main()) 