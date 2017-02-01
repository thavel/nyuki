import logging
from nyuki import Nyuki


class Worker(Nyuki):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


if __name__ == '__main__':
    nyuki = Worker()
    nyuki.start()
