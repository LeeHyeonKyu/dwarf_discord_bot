import discord
import asyncio
import os
from dotenv import load_dotenv

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
    
    try:
        # 테스트 채널 가져오기
        channel = client.get_channel(TEST_CHANNEL_ID)
        if not channel:
            print(f"채널 ID {TEST_CHANNEL_ID}를 찾을 수 없습니다.")
            await client.close()
            return
        
        # 채널 타입 확인
        if not isinstance(channel, discord.TextChannel):
            print(f"채널 ID {TEST_CHANNEL_ID}는 텍스트 채널이 아닙니다. 텍스트 채널만 지원됩니다.")
            await client.close()
            return
        
        print(f"'{channel.name}' 채널의 모든 메시지와 스레드를 초기화합니다...")
        
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
            print(f"스레드 {thread_count}개 삭제 중...")
            
            for thread in threads:
                try:
                    await thread.delete()
                    print(f"- 스레드 '{thread.name}' 삭제됨")
                except discord.Forbidden:
                    print(f"- 스레드 '{thread.name}' 삭제 권한이 없습니다.")
                except discord.HTTPException as e:
                    print(f"- 스레드 '{thread.name}' 삭제 중 오류 발생: {e}")
        
        # 메시지 삭제
        print("메시지 삭제 중... 이 작업은 시간이 걸릴 수 있습니다.")
        
        deleted_count = 0
        async for message in channel.history(limit=None):
            try:
                await message.delete()
                deleted_count += 1
                
                # 10개 메시지마다 상태 업데이트 (API 속도 제한 방지)
                if deleted_count % 10 == 0:
                    print(f"메시지 삭제 중... {deleted_count}개 완료")
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.5)
                    
            except discord.Forbidden:
                print("메시지 삭제 권한이 없습니다.")
                break
            except discord.HTTPException:
                continue
        
        # 완료 메시지
        print(f"채널 초기화 완료: {deleted_count}개의 메시지와 {thread_count}개의 스레드가 삭제되었습니다.")
        
    except Exception as e:
        print(f"채널 초기화 중 오류 발생: {e}")
    
    # 작업 완료 후 봇 종료
    await client.close()

# 봇 실행
if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_TOKEN이 설정되어 있지 않습니다. .env.secret 파일을 확인해주세요.")
    elif TEST_CHANNEL_ID == 0:
        print("TEST_CHANNEL_ID가 .env.secret 파일에 설정되어 있지 않습니다.")
    else:
        asyncio.run(client.start(TOKEN)) 