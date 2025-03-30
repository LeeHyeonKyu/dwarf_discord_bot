import discord
from discord.ext import commands

class EventHandlers(commands.Cog):
    """디스코드 이벤트 핸들러"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # 쓰레드에 새 메시지가 올 때마다 실행
    @commands.Cog.listener()
    async def on_message(self, message):
        # 봇 자신의 메시지는 무시
        if message.author == self.bot.user:
            return
        
        # 쓰레드 메시지인지 확인
        if isinstance(message.channel, discord.Thread):
            print(f"쓰레드 {message.channel.name}에 새 메시지: {message.content}")
            # 여기에 원하는 동작 추가
            await message.channel.send(f"{message.author.mention}님이 메시지를 보냈습니다!")
    
    # 새 쓰레드가 생성될 때 실행
    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        print(f"새 쓰레드 생성됨: {thread.name}")
        await thread.send("새 쓰레드에 오신 것을 환영합니다!")
    
    # 봇이 쓰레드에 추가될 때 실행
    @commands.Cog.listener()
    async def on_thread_join(self, thread):
        print(f"봇이 쓰레드에 참여함: {thread.name}")
        await thread.send("이 쓰레드에 참여했습니다. 무엇을 도와드릴까요?")

async def setup(bot):
    await bot.add_cog(EventHandlers(bot)) 