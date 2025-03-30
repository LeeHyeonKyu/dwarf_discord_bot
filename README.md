# 디스코드 봇

디스코드 서버에서 메시지 관리 및 사용자 멘션 기능을 제공하는 봇입니다.

## 기능

1. 특정 채널에 메시지 보내기
2. 보낸 메시지에서 쓰레드 생성하기
3. 쓰레드에 달린 댓글을 확인하고 메시지 수정하기
4. 채널에 참여한 사용자 멘션하기

## 설치 방법

1. 레포지토리 클론
```bash
git clone [레포지토리 URL]
cd [프로젝트 폴더]
```

2. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

3. 환경 설정
`.env.example` 파일을 `.env.secret`로 복사하고 디스코드 봇 토큰과 채널 ID를 설정합니다.
```bash
cp .env.example .env.secret
```

## 봇 설정하기

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 새 애플리케이션을 생성합니다.
2. "Bot" 탭으로 이동하여 봇을 추가합니다.
3. 봇 토큰을 복사하여 `.env.secret` 파일의 `DISCORD_TOKEN`에 붙여넣습니다.
4. "OAuth2" 탭에서 봇을 서버에 초대할 수 있는 URL을 생성합니다.
   - 스코프: `bot`
   - 권한: `Send Messages`, `Create Public Threads`, `Send Messages in Threads`, `Read Message History`, `Mention Everyone`
5. 생성된 URL을 통해 봇을 서버에 초대합니다.
6. 메시지를 보낼 채널의 ID를 복사하여 `.env.secret` 파일의 `CHANNEL_ID`에 붙여넣습니다.

## 실행 방법

```bash
python bot.py
```

## 명령어

- `!send [메시지]`: 설정된 채널에 메시지를 보냅니다.
- `!create_thread [메시지ID] [쓰레드이름]`: 보낸 메시지에서 쓰레드를 생성합니다.
- `!check_thread [쓰레드ID]`: 쓰레드에 달린 댓글을 확인합니다.
- `!edit_message [메시지ID] [새로운내용]`: 봇이 보낸 메시지를 수정합니다.
- `!mention_all`: 채널에 참여한 모든 사용자를 멘션합니다. 