import discord
import os
import asyncio
import sys
from dotenv import load_dotenv
from utils.raid_manager import create_raid_threads

# .env.secret 파일 로드
load_dotenv('.env.secret')
TOKEN = os.getenv('DISCORD_TOKEN')
SCHEDULE_CHANNEL_ID = int(os.getenv('SCHEDULE_CHANNEL_ID', '0'))
TEST_CHANNEL_ID = int(os.getenv('TEST_CHANNEL_ID', '0'))

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True

# 클라이언트 초기화
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'{client.user}로 로그인했습니다!')
    
    # 명령줄 인자 확인
    is_test = '--test' in sys.argv
    
    # 테스트 모드 여부에 따라 채널 ID 결정
    channel_id = TEST_CHANNEL_ID if is_test else SCHEDULE_CHANNEL_ID
    channel_type = "테스트" if is_test else "일반"
    
    print(f"{channel_type} 모드로 레이드 스레드를 생성합니다...")
    # 레이드 스레드 생성 (활성화된 멤버만)
    success = await create_raid_threads(client, channel_id, active_only=True, is_test=is_test)
    # 작업 완료 후 봇 종료
    await client.close()

# 봇 실행
if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_TOKEN이 설정되어 있지 않습니다. .env.secret 파일을 확인해주세요.")
    elif SCHEDULE_CHANNEL_ID == 0 and TEST_CHANNEL_ID == 0:
        print("SCHEDULE_CHANNEL_ID와 TEST_CHANNEL_ID가 모두 .env.secret 파일에 설정되어 있지 않습니다.")
    else:
        is_test = '--test' in sys.argv
        if is_test:
            if TEST_CHANNEL_ID == 0:
                print("테스트 모드를 사용하려면 TEST_CHANNEL_ID가 .env.secret 파일에 설정되어 있어야 합니다.")
                sys.exit(1)
            print("테스트 모드로 레이드 스레드 생성을 시작합니다...")
        else:
            if SCHEDULE_CHANNEL_ID == 0:
                print("SCHEDULE_CHANNEL_ID가 .env.secret 파일에 설정되어 있지 않습니다.")
                sys.exit(1)
            print("일반 모드로 레이드 스레드 생성을 시작합니다...")
        asyncio.run(client.start(TOKEN)) 