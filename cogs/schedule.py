import discord
from discord.ext import commands
import yaml
import os

class ScheduleCommands(commands.Cog):
    """레이드 스케줄 관련 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
        self.CHANNEL_ID = int(os.getenv('SCHEDULE_CHANNEL_ID', '0'))
    
    @commands.command(name='init_schedule')
    async def init_schedule(self, ctx, raid_id=None):
        """
        레이드 스케줄을 생성하고 쓰레드 생성
        사용법: !init_schedule [raid_id]
        """
        try:
            # 레이드 및 멤버 정보 로드
            with open('configs/raids_config.yaml', 'r', encoding='utf-8') as raid_file:
                raid_data = yaml.safe_load(raid_file)
            
            with open('configs/members_config.yaml', 'r', encoding='utf-8') as member_file:
                member_data = yaml.safe_load(member_file)
            
            channel = self.bot.get_channel(self.CHANNEL_ID)
            if not channel:
                await ctx.send(f'채널을 찾을 수 없습니다: {self.CHANNEL_ID}')
                return
                
            # 채널 타입 확인 (TextChannel만 허용)
            if not isinstance(channel, discord.TextChannel):
                await ctx.send(f'대상 채널이 텍스트 채널이 아닙니다: {self.CHANNEL_ID}')
                return
            
            # 멘션 정보 구성
            members = {member['id']: member['discord_name'] for member in member_data['members']}
            
            # 레이드 정보 필터링
            schedules = member_data['schedules']
            if raid_id:
                schedules = [s for s in schedules if s['raid_id'] == raid_id]
                if not schedules:
                    await ctx.send(f'해당 레이드 ID를 찾을 수 없습니다: {raid_id}')
                    return
            
            raid_count = 0
            for schedule in schedules:
                # 레이드 정보 찾기
                raid_info = next((r for r in raid_data['raids'] if r['name'] == schedule['raid_id']), None)
                if not raid_info:
                    continue
                    
                for entry in schedule['entries']:
                    # 메시지 구성
                    entry_num = entry['entry']
                    message_content = f"## {raid_info['name']} (레벨: {raid_info['min_level']}~{raid_info['max_level'] or '무제한'})\n\n"
                    message_content += f"• {entry_num}차\n"
                    message_content += f"  ◦ when: {entry['when']}\n"
                    
                    # 탱커 멘션 구성
                    tanks = []
                    for tank_id in entry['tank']:
                        discord_name = members.get(tank_id, tank_id)
                        tanks.append(f"@{discord_name}")
                    
                    tank_mentions = " / ".join(tanks) if tanks else ""
                    
                    # 딜러 멘션 구성
                    dps_list = []
                    for dps_id in entry.get('dps', []):
                        discord_name = members.get(dps_id, dps_id)
                        dps_list.append(f"@{discord_name}")
                    
                    dps_mentions = " / ".join(dps_list) if dps_list else ""
                    
                    # who 줄 구성
                    message_content += f"  ◦ who: 폿( {tank_mentions} ) / 딜( {dps_mentions} )\n"
                    
                    # 노트 추가
                    if 'description' in raid_info:
                        message_content += f"  ◦ note: {raid_info['description']}\n"
                    
                    # 메시지 전송
                    sent_message = await channel.send(message_content)
                    
                    # 쓰레드 생성
                    thread_name = f"{raid_info['name']} {entry_num}차"
                    thread = await sent_message.create_thread(name=thread_name)
                    
                    # @everyone 멘션
                    await thread.send("@everyone 레이드 일정이 등록되었습니다!")
                    
                    raid_count += 1
                    
            await ctx.send(f'{raid_count}개의 레이드 일정이 성공적으로 등록되었습니다!')
            
        except FileNotFoundError as e:
            await ctx.send(f'필요한 YAML 파일을 찾을 수 없습니다: {e}')
        except yaml.YAMLError as e:
            await ctx.send(f'YAML 파일 형식이 올바르지 않습니다: {e}')
        except Exception as e:
            await ctx.send(f'오류가 발생했습니다: {e}')

async def setup(bot):
    await bot.add_cog(ScheduleCommands(bot)) 