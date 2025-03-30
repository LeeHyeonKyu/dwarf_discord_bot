import discord
import asyncio
import os
import yaml
import sys
import argparse
from dotenv import load_dotenv

# 상위 디렉토리 경로를 추가하여 프로젝트 모듈을 import할 수 있게 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# .env.secret 파일 로드
load_dotenv('.env.secret')
TOKEN = os.getenv('DISCORD_TOKEN')
MEMBERS_CHANNEL_ID = int(os.getenv('MEMBERS_CHANNEL_ID', '0'))

# 파일 경로 설정
MEMBERS_CONFIG_PATH = 'configs/members_config.yaml'

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # 멤버 정보 접근 권한

# 클라이언트 초기화
client = discord.Client(intents=intents)

async def load_members_config():
    """멤버 구성 정보 로드"""
    try:
        with open(MEMBERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        print(f"멤버 구성 정보 로드 중 오류: {e}")
        return {"members": []}

async def save_members_config(config):
    """멤버 구성 정보 저장"""
    try:
        # 백업 파일 생성
        backup_path = f"{MEMBERS_CONFIG_PATH}.bak"
        if os.path.exists(MEMBERS_CONFIG_PATH):
            with open(MEMBERS_CONFIG_PATH, 'r', encoding='utf-8') as src, open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            print(f"기존 설정 파일을 {backup_path}에 백업했습니다.")
        
        # 새 설정 저장
        with open(MEMBERS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"멤버 구성 정보를 {MEMBERS_CONFIG_PATH}에 저장했습니다.")
        return True
    except Exception as e:
        print(f"멤버 구성 정보 저장 중 오류: {e}")
        return False

@client.event
async def on_ready():
    print(f'{client.user}로 로그인했습니다!')
    
    try:
        # 멤버 채널 가져오기
        channel = client.get_channel(MEMBERS_CHANNEL_ID)
        if not channel:
            print(f"채널 ID {MEMBERS_CHANNEL_ID}를 찾을 수 없습니다.")
            await client.close()
            return
        
        # 채널 타입 확인
        if not isinstance(channel, discord.TextChannel):
            print(f"채널 ID {MEMBERS_CHANNEL_ID}는 텍스트 채널이 아닙니다. 텍스트 채널만 지원됩니다.")
            await client.close()
            return
        
        # 채널이 속한 서버(길드) 가져오기
        guild = channel.guild
        if not guild:
            print(f"채널 {channel.name}이 서버에 속해 있지 않습니다.")
            await client.close()
            return
        
        print(f"'{guild.name}' 서버의 '{channel.name}' 채널에서 멤버 정보를 가져옵니다...")
        
        # 기존 멤버 구성 정보 로드
        config = await load_members_config()
        existing_members = config.get('members', [])
        
        # 기존 멤버의 discord_id를 쉽게 조회할 수 있게 매핑
        existing_member_ids = {member.get('discord_id'): member for member in existing_members}
        
        # 서버 멤버 목록 가져오기
        guild_members = guild.members
        
        # 기존 멤버에게 active 필드 추가
        updated_members = []
        for member in existing_members:
            # active 필드 추가 (기본값: True)
            if 'active' not in member:
                member['active'] = True
            updated_members.append(member)
        
        # 새로운 멤버 추가
        new_member_count = 0
        for guild_member in guild_members:
            # 봇은 제외
            if guild_member.bot:
                continue
                
            discord_id = str(guild_member.id)
            
            # 기존 멤버인지 확인
            if discord_id not in existing_member_ids:
                # 기본 정보 추출
                display_name = guild_member.display_name
                user_name = guild_member.name
                
                # 새 멤버 정보 생성
                new_member = {
                    'id': user_name,  # 기본값으로 사용자 이름 사용
                    'discord_name': display_name,
                    'discord_id': discord_id,
                    'main_characters': [],
                    'active': False  # 새로운 멤버는 active: False로 설정
                }
                
                updated_members.append(new_member)
                new_member_count += 1
                print(f"새 멤버 추가: {display_name} (Discord ID: {discord_id})")
        
        # 업데이트된 구성 정보 저장
        updated_config = {'members': updated_members}
        success = await save_members_config(updated_config)
        
        if success:
            print(f"멤버 정보 업데이트 완료: 기존 멤버 {len(existing_members)}명, 새 멤버 {new_member_count}명")
        else:
            print("멤버 정보 업데이트 실패")
        
    except Exception as e:
        print(f"멤버 정보 업데이트 중 오류 발생: {e}")
    
    # 작업 완료 후 봇 종료
    await client.close()

async def main():
    parser = argparse.ArgumentParser(description='멤버 정보 업데이트')
    parser.add_argument('--dry-run', action='store_true', help='변경 사항을 저장하지 않고 테스트 실행')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("테스트 모드로 실행합니다 (변경 사항이 저장되지 않습니다).")
        global save_members_config
        original_save = save_members_config
        
        # 저장 함수를 오버라이드
        async def mock_save(config):
            print("테스트 모드: 설정 파일이 저장되지 않습니다.")
            print(yaml.dump(config, default_flow_style=False, allow_unicode=True))
            return True
        
        save_members_config = mock_save
    
    if not TOKEN:
        print("DISCORD_TOKEN이 설정되어 있지 않습니다. .env.secret 파일을 확인해주세요.")
        return
    elif MEMBERS_CHANNEL_ID == 0:
        print("MEMBERS_CHANNEL_ID가 .env.secret 파일에 설정되어 있지 않습니다.")
        return
    
    try:
        await client.start(TOKEN)
    except Exception as e:
        print(f"봇 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 