FROM alpine:3.5

ENV WORKSPACE /home

WORKDIR ${WORKSPACE}
COPY ./ ./

RUN apk add --update python3 curl && \
    apk add --virtual build-deps python3-dev make g++ && \
    curl https://bootstrap.pypa.io/get-pip.py | python3 && \
    pip install nyuki dnspython && \
    apk del build-deps && \
    rm -rf /var/cache/apk/* $HOME/.cache

CMD python3 worker.py
