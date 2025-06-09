FROM openeuler/openeuler:24.03

WORKDIR /app

COPY requirements.txt .

RUN dnf update -y && \
    dnf install -y \
        python3 \
        python3-pip \
        gcc \
        python3-devel \
        gcc-c++ \
        make \
        libffi-devel \
        postgresql-devel \
        postgresql-libs \
        git && \
    dnf install -y libstdc++ libffi && \
    pip install --no-cache-dir gunicorn uvicorn && \
    pip install --no-cache-dir -r requirements.txt --upgrade && \
    dnf remove -y \
        python3-devel \
        gcc \
        gcc-c++ \
        make \
        libffi-devel \
        postgresql-devel && \
    dnf clean all && \
    adduser -u 1000 hotopic-collect-clean && \
    chown -R hotopic-collect-clean:hotopic-collect-clean /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER hotopic-collect-clean
COPY --chown=hotopic-collect-clean:hotopic-collect-clean . .

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
