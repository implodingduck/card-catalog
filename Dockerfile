FROM python:3.12

RUN apt-get update && apt-get install -y curl tcpdump net-tools vim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

#CMD ["pip", "freeze"]
CMD ["python", "-u", "-m", "app.main"]