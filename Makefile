.PHONY: help up down build logs logs-backend restart clean shell
#申明后面的这些都是伪目标，不是真实的文件名，而是一个动作标签
#为什么要写：如果当前目录下恰好存在一个名为 up 或 down 的普通文件，make 会误认为目标已是最新而不执行。.PHONY 强制 make 忽略文件存在性，每次都会执行对应命令。
#@：前缀表示不显示命令本身，只显示后面的输出内容

help:
	@echo Commands:
	@echo   make up          - start all services (background)
	@echo   make down        - stop all services
	@echo   make build       - rebuild images and start
	@echo   make logs        - follow all logs
	@echo   make logs-backend- follow backend logs
	@echo   make restart     - restart all services
	@echo   make clean       - stop and remove containers (keep data volumes)
	@echo   make shell       - open backend container shell

up:
	docker compose up -d
	@echo Services started! Open http://localhost:8080

down:
	docker compose down

build:
	docker compose up -d --build
	@echo Rebuild done!

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

restart:
	docker compose restart

clean:
	docker compose down
	@echo Containers removed, data volumes kept.

shell:
	docker compose exec backend sh