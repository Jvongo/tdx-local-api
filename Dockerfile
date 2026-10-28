# 通达信本地行情服务镜像：仅含运行时依赖，行情数据通过卷挂载接入
FROM python:3.13-slim

# 使用清华镜像源加速依赖安装（海外网络可删除此行）
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# 先装依赖（层缓存：依赖不变则不重复安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制服务代码
COPY tdx_service/ ./tdx_service/
COPY run.py .

# 容器内默认配置：行情数据挂载到 /data，监听所有网卡
ENV TDX_HOME=/data \
    TDX_HOST=0.0.0.0 \
    TDX_PORT=8000

EXPOSE 8000

# 健康检查：slim 镜像无 curl，用 python 标准库探测 /api/v1/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status==200 else 1)"

CMD ["python", "run.py"]
