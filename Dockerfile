# 使用官方 Python 镜像作为基础镜像
#https://docker.aityp.com/image/docker.io/python:3.9-slim?platform=linux/arm64
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9-slim-linuxarm64
#FROM python:3.9


# 安装系统依赖
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    gcc \
#    g++ \
#    make \
#    graphviz \
#    graphviz-dev \
#    libgraphviz-dev \
#    build-essential \
#    python3-dev \
#    && rm -rf /var/lib/apt/lists/*

#FROM continuumio/miniconda3:latest
#FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/continuumio/miniconda3:latest 这个是 amd64 的，需要 arm64 的
FROM docker.m.daocloud.io/continuumio/miniconda3:latest

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    fontconfig\
    && rm -rf /var/lib/apt/lists/*

# 创建并激活 Conda 环境
RUN conda create -n myenv python=3.9
RUN echo "conda activate myenv" >> ~/.bashrc
ENV PATH /opt/conda/envs/myenv/bin:$PATH

# 创建字体目录
RUN mkdir -p /usr/share/fonts/truetype/source-han-sans

# 复制思源黑体字体文件到镜像
COPY fonts/SourceHanSansCNMedium.otf /usr/share/fonts/truetype/source-han-sans/SourceHanSansCNMedium.otf

# 更新字体缓存
RUN fc-cache -fv

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements_pip.txt .
COPY requirements_conda.txt .

# 安装依赖 - pip
RUN pip install --no-cache-dir -r requirements_pip.txt


RUN conda install -c conda-forge python-graphviz python=3.9


# 安装 gunicorn
#RUN pip install --no-cache-dir gunicorn

# 复制应用代码
COPY . .

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_DEBUG=1

# 暴露端口
EXPOSE 8000

# 使用 gunicorn 启动应用
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]