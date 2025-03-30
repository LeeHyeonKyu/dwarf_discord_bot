import discord
import yaml
import os
import asyncio
from dotenv import load_dotenv

# .env.secret 파일 로드
load_dotenv('.env.secret')
TOKEN = os.getenv('DISCORD_TOKEN')

# 대상 채널 ID - 민감한 정보이므로 환경 변수에서 로드
TARGET_CHANNEL_ID = int(os.getenv('MEMBERS_CHANNEL_ID', '0'))  # 민감한 채널

# 인텐트 설정
intents = discord.Intents.default()
intents.members = True  # 멤버 정보를 가져오기 위한 인텐트 설정

# 클라이언트 초기화
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'{client.user}로 로그인했습니다!')
    
    try:
        # 대상 채널 가져오기
        channel = client.get_channel(TARGET_CHANNEL_ID)
        
        if not channel:
            # fetch_channel을 통해 다시 시도 (비공개 채널이거나 접근할 수 없는 채널일 수 있음)
            try:
                channel = await client.fetch_channel(TARGET_CHANNEL_ID)
            except discord.errors.NotFound:
                print(f"채널 ID {TARGET_CHANNEL_ID}를 찾을 수 없습니다.")
                await client.close()
                return
            except discord.errors.Forbidden:
                print(f"채널 ID {TARGET_CHANNEL_ID}에 접근할 권한이 없습니다.")
                await client.close()
                return
        
        # 채널 타입 확인
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
            print(f"채널 ID {TARGET_CHANNEL_ID}는 서버 채널이 아닙니다. (타입: {type(channel).__name__})")
            await client.close()
            return
            
        print(f"채널 '{channel.name}' 접속 완료. 멤버 정보 수집 중...")
        
        # 채널의 서버(길드) 가져오기
        guild = channel.guild
        members_data = {"members": []}
        
        # 채널의 권한 확인
        for member in guild.members:
            # 봇 계정은 제외
            if member.bot:
                continue
                
            # 해당 채널에 접근 권한이 있는지 확인
            permissions = channel.permissions_for(member)
            if permissions.view_channel:
                member_info = {
                    "id": "",  # 사용자가 직접 작성할 부분
                    "discord_name": member.display_name,
                    "discord_id": str(member.id),
                    "main_characters": []  # 사용자가 직접 작성할 부분
                }
                members_data["members"].append(member_info)
                print(f"멤버 추가: {member.display_name} (ID: {member.id})")
        
        # YAML 파일로 저장
        with open('configs/members_config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(members_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            
        print(f"총 {len(members_data['members'])}명의 멤버 정보를 configs/members_config.yaml 파일에 저장했습니다.")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    
    # 작업 완료 후 봇 종료
    await client.close()

# 봇 실행
if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_TOKEN이 설정되어 있지 않습니다. .env.secret 파일을 확인해주세요.")
    elif TARGET_CHANNEL_ID == 0:
        print("MEMBERS_CHANNEL_ID가 .env.secret 파일에 설정되어 있지 않습니다.")
    else:
        asyncio.run(client.start(TOKEN)) 