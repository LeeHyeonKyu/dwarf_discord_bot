# 드워프 디스코드 봇

Discord 서버를 위한 다목적 봇입니다.

## 기능

- 기본적인 명령어 처리
- 모듈식 구조 (Cogs)
- 오류 처리 및 로깅
- 로스트아크 캐릭터 정보 수집 및 조회

## 설치 방법

1. 저장소 클론하기:
   ```
   git clone https://github.com/유저네임/dwarf_discord_bot.git
   cd dwarf_discord_bot
   ```

2. 가상 환경 설정 (선택 사항이지만 권장):
   ```
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. 의존성 설치:
   ```
   pip install -r requirements.txt
   ```

4. 환경 변수 설정:
   `.env.secret` 파일을 편집하여 Discord 토큰을 추가하세요:
   ```
   DISCORD_TOKEN=귀하의_디스코드_봇_토큰
   COMMAND_PREFIX=!
   ```

## 사용 방법

봇 실행:
```
python bot.py
```

## 확장 모듈 개발

새로운 기능을 추가하려면 `cogs` 디렉토리에 새 모듈을 생성하세요:

```python
from discord.ext import commands

class 새로운기능(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command()
    async def 테스트(self, ctx):
        await ctx.send("테스트 명령어가 작동합니다!")

async def setup(bot):
    await bot.add_cog(새로운기능(bot))
```

## 로스트아크 캐릭터 정보 수집

봇은 로스트아크 API를 사용하여 멤버들의 캐릭터 정보를 수집할 수 있습니다. 이 기능을 사용하기 위해서는 다음이 필요합니다:

1. `.env.secret` 파일에 로스트아크 API 키 설정:
   ```
   LOSTARK_API_KEY=귀하의_로스트아크_API_키
   ```

2. `configs/members_config.yaml` 파일에 멤버 정보 설정

3. 캐릭터 정보 수집 명령어 사용:
   ```
   !캐릭터갱신
   ```

4. 수집된 캐릭터 정보 조회:
   ```
   !캐릭터목록 [멤버ID]
   ```

스크립트를 통한 캐릭터 정보 수집:
```
python scripts/collect_characters.py --min-level 1600.0
```

## Docker로 실행하기

### Docker로 빌드 및 실행

1. Docker 이미지 빌드:
   ```
   docker build -t dwarf-discord-bot .
   ```

2. Docker 컨테이너 실행:
   ```
   docker run -d --name dwarf-discord-bot \
     --restart unless-stopped \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/configs:/app/configs \
     -v $(pwd)/bot.log:/app/bot.log \
     --env-file .env.secret \
     dwarf-discord-bot
   ```

### Docker Compose로 실행

1. Docker Compose를 사용하여 봇 실행:
   ```
   docker-compose up -d
   ```

2. 로그 확인:
   ```
   docker-compose logs -f
   ```

3. 서비스 중지:
   ```
   docker-compose down
   ```

### 환경 변수 설정

Docker 실행 시 `.env.secret` 파일이 자동으로 로드됩니다. 파일이 없는 경우 `.env.secret.example`을 참고하여 생성하세요.

## 프로젝트 구조

```
.
├── bot.py             # 봇 메인 파일
├── cogs/              # 확장 모듈 디렉토리
│   ├── lostark.py     # 로스트아크 관련 명령어
│   └── utils.py       # 유틸리티 명령어
├── configs/           # 설정 파일 디렉토리
├── data/              # 데이터 파일 저장 디렉토리
├── services/          # 서비스 모듈 디렉토리
│   └── lostark_service.py # 로스트아크 API 서비스
├── scripts/           # 유틸리티 스크립트 디렉토리
└── tests/             # 테스트 코드 디렉토리
```

## 라이선스

MIT

## 기여

이슈와 PR은 언제나 환영입니다! 