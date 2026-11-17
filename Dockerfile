FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .
COPY data ./data
COPY app ./app
COPY scripts ./scripts
COPY reports ./reports
COPY configs ./configs
COPY .streamlit ./.streamlit
ENV PYTHONUNBUFFERED=1
CMD ["streamlit", "run", "app/Home.py", "--server.address=0.0.0.0", "--server.port=8501"]
