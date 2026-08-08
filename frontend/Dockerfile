FROM nginx:alpine

#复制静态页面
COPY html/index.html /usr/share/nginx/html/index.html
#复制Nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80