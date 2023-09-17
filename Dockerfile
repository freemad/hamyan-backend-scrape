FROM python:3.6
ENV PYTHONUNBUFFERED 1
RUN mkdir /code

WORKDIR /code
COPY requirements.txt /code/

RUN pip install -r requirements.txt

COPY . /code/
RUN chmod +x /code/start.sh
# RUN sysctl -w net.core.somaxconn=1024
#RUN python manage.py collectstatic --noinput
ENTRYPOINT [ "/bin/sh", "/code/start.sh" ]
