FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 필요한 파일 복사
COPY requirements.txt .
COPY setup.py .
COPY pyproject.toml .
COPY bot.py .
COPY clean_channel.py .
COPY analyze_members.py .
COPY run_sync_collector.py .
COPY pytest.ini .

# 디렉토리 복사
COPY cogs/ ./cogs/
COPY utils/ ./utils/
COPY services/ ./services/
COPY configs/ ./configs/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

# 데이터 디렉토리 생성
RUN mkdir -p data

# 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -e .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1

# 볼륨 설정
VOLUME ["/app/data", "/app/configs"]

# 실행
CMD ["python", "bot.py"] 