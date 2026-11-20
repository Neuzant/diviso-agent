FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
RUN useradd -m diviso
USER diviso
WORKDIR /home/diviso/workspace
ENTRYPOINT ["diviso"]
CMD ["doctor"]
