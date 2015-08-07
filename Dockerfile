FROM python:3.4

ENV NYUKI_PATH /home

ADD . ${NYUKI_PATH}/
RUN pip3 install -e ${NYUKI_PATH}/
RUN pip3 install -r ${NYUKI_PATH}/requirements_test.txt

WORKDIR ${NYUKI_PATH}
CMD python3.4 testnyuki.py start