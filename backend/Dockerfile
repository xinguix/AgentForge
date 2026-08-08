FROM python:3.11-slim
#基础镜像，只包含Python3.11和最小化的Linux系统（slim版本很精简，镜像体积小，方便传输）

WORKDIR /app
#设置容器内的工作目录，后续的COPY和RUN命令都会默认在这个目录下执行。相当于容器里的 cd /app

RUN mkdir -p /app/uploads

#只复制依赖文件（利用Docker缓冲层，不改依赖就不用重装）
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
#cache(缓存)  --no-cache-die : 装完立刻删掉安装包，为的是减小最终镜像体积
#分层缓存：好处在于只要没加新库，这层就不变，docker直接拿缓存的“已安装依赖层”用，然后才复制代码变动

#复制全部代码
COPY ./app /app/app

#注意：这里的启动命令加了 --reload，方便本地改代码热更新
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--reload"]
#--reload 本地改了main.py文件不用手动重启Uvicorn，他会自动检测文件变动并重启进程，刷新浏览器就能看到新效果
#线上禁用--reload原因：1.性能开销：他会不断检视硬盘文件变化，消耗cpu
#2.安全隐患：万一线上代码被篡改，他会自动重启加载恶意代码
#3.稳定性差：如果代码有语法错误，启动崩溃，--reload会陷入无限崩溃重启循环，导致服务彻底不能用
#端口号：80 HTTP默认端口（访问网站不用输端口号）
#443 HTTPS默认端口号（加密）：只有服务器能解码，即使被截获，对方看到的也是乱码
#3306 MySQL数据库   5432  postgreSQL数据库   6379 Redis(缓存数据库)   5000 Flask 开发默认端口
#8000  FastAPI/Uvicorn默认端口