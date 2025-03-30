import discord
import os
import sys
import asyncio
from dotenv import load_dotenv

# 상위 디렉토리 경로를 추가하여 프로젝트 모듈을 import할 수 있게 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.raid_manager import reset_channel

# .env.secret 파일 로드
load_dotenv('.env.secret')
TOKEN = os.getenv('DISCORD_TOKEN')
TEST_CHANNEL_ID = int(os.getenv('TEST_CHANNEL_ID', '0'))

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True

# 클라이언트 초기화
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'{client.user}로 로그인했습니다!')
    # 테스트 채널 초기화
    success = await reset_channel(client, TEST_CHANNEL_ID, is_test=True)
    # 작업 완료 후 봇 종료
    await client.close()

# 봇 실행
if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_TOKEN이 설정되어 있지 않습니다. .env.secret 파일을 확인해주세요.")
    elif TEST_CHANNEL_ID == 0:
        print("TEST_CHANNEL_ID가 .env.secret 파일에 설정되어 있지 않습니다.")
    else:
        print("테스트 채널 초기화를 시작합니다...")
        asyncio.run(client.start(TOKEN)) 