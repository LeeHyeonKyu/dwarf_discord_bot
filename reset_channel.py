import discord
import os
import asyncio
from dotenv import load_dotenv
from utils.raid_manager import reset_channel

# .env.secret 파일 로드
load_dotenv('.env.secret')
TOKEN = os.getenv('DISCORD_TOKEN')
SCHEDULE_CHANNEL_ID = int(os.getenv('SCHEDULE_CHANNEL_ID', '0'))

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True

# 클라이언트 초기화
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'{client.user}로 로그인했습니다!')
    # 채널 초기화 (실제 환경)
    success = await reset_channel(client, SCHEDULE_CHANNEL_ID, is_test=False)
    # 작업 완료 후 봇 종료
    await client.close()

# 봇 실행
if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_TOKEN이 설정되어 있지 않습니다. .env.secret 파일을 확인해주세요.")
    elif SCHEDULE_CHANNEL_ID == 0:
        print("SCHEDULE_CHANNEL_ID가 .env.secret 파일에 설정되어 있지 않습니다.")
    else:
        print("채널 초기화를 시작합니다...")
        asyncio.run(client.start(TOKEN)) 