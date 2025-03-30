import discord
from discord.ext import commands

class MessageCommands(commands.Cog):
    """메시지 및 쓰레드 관련 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
        self.CHANNEL_ID = int(bot.config["CHANNEL_ID"])
    
    @commands.command(name='send')
    async def send_message(self, ctx, *, message):
        """
        특정 채널에 메시지 보내기
        사용법: !send 보낼 메시지
        """
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if channel and isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            sent_message = await channel.send(message)
            await ctx.send(f'메시지가 성공적으로 전송되었습니다! 메시지 ID: {sent_message.id}')
        else:
            await ctx.send(f'채널을 찾을 수 없거나 메시지를 보낼 수 없는 채널입니다: {self.CHANNEL_ID}')

    @commands.command(name='create_thread')
    async def create_thread(self, ctx, message_id: int, thread_name: str):
        """
        메시지에서 쓰레드 생성하기
        사용법: !create_thread 메시지ID 쓰레드이름
        """
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            await ctx.send(f'텍스트 채널을 찾을 수 없습니다. 채널 ID를 확인해주세요: {self.CHANNEL_ID}')
            return
        
        try:
            message = await channel.fetch_message(message_id)
            thread = await message.create_thread(name=thread_name)
            await ctx.send(f'쓰레드가 성공적으로 생성되었습니다! 쓰레드 ID: {thread.id}')
        except discord.NotFound:
            await ctx.send('메시지를 찾을 수 없습니다. 메시지 ID를 확인해주세요.')
        except discord.HTTPException as e:
            await ctx.send(f'쓰레드 생성 중 오류가 발생했습니다: {e}')

    @commands.command(name='check_thread')
    async def check_thread(self, ctx, thread_id: int):
        """
        쓰레드의 메시지 확인하기
        사용법: !check_thread 쓰레드ID
        """
        try:
            thread = await self.bot.fetch_channel(thread_id)
            if not isinstance(thread, discord.Thread):
                await ctx.send('해당 ID는 쓰레드가 아닙니다.')
                return
                
            messages = [message async for message in thread.history(limit=10)]
            
            if not messages:
                await ctx.send('해당 쓰레드에 메시지가 없습니다.')
                return
                
            response = '쓰레드의 메시지:\n'
            for message in messages:
                content = message.content if message.content else '[콘텐츠 없음]'
                response += f'**{message.author.display_name}**: {content}\n'
                
            await ctx.send(response)
        except discord.NotFound:
            await ctx.send('쓰레드를 찾을 수 없습니다. 쓰레드 ID를 확인해주세요.')
        except Exception as e:
            await ctx.send(f'오류가 발생했습니다: {e}')

    @commands.command(name='edit_message')
    async def edit_message(self, ctx, message_id: int, *, new_content):
        """
        메시지 수정하기
        사용법: !edit_message 메시지ID 새로운내용
        """
        channel = self.bot.get_channel(self.CHANNEL_ID)
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            await ctx.send(f'채널을 찾을 수 없거나 메시지를 가져올 수 없는 채널입니다: {self.CHANNEL_ID}')
            return
        
        try:
            message = await channel.fetch_message(message_id)
            
            # 봇이 보냈는지 확인
            if not self.bot.user or message.author.id != self.bot.user.id:
                await ctx.send('이 봇이 보낸 메시지만 수정할 수 있습니다.')
                return
                
            await message.edit(content=new_content)
            await ctx.send('메시지가 성공적으로 수정되었습니다!')
        except discord.NotFound:
            await ctx.send('메시지를 찾을 수 없습니다. 메시지 ID를 확인해주세요.')
        except Exception as e:
            await ctx.send(f'메시지 수정 중 오류가 발생했습니다: {e}')

    @commands.command(name='mention_all')
    async def mention_members(self, ctx):
        """
        채널에 있는 모든 멤버를 멘션하기
        사용법: !mention_all
        """
        if ctx.guild is None:
            await ctx.send('이 명령어는 서버 채널에서만 사용할 수 있습니다.')
            return
            
        members = ctx.channel.members
        if not members:
            await ctx.send('채널에 멤버가 없습니다.')
            return
            
        mentions = ' '.join([member.mention for member in members if not member.bot])
        if mentions:
            await ctx.send(f'채널의 모든 멤버: {mentions}')
        else:
            await ctx.send('멘션할 멤버가 없습니다.')

async def setup(bot):
    await bot.add_cog(MessageCommands(bot)) 