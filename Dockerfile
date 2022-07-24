FROM python:3.9.1-slim

WORKDIR /usr/src/app

RUN adduser --system --no-create-home --shell /usr/sbin/nologin mqtt_wled
COPY mqtt_wled.py requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

USER mqtt_wled

ENTRYPOINT [ "/usr/local/bin/python3", "-u", "/usr/src/app/mqtt_wled.py" ]