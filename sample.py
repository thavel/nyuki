from nyuki import Nyuki


class Sample(Nyuki):

    def __init__(self):
        super().__init__()
        self.message = 'hello world'


if __name__ == '__main__':
    nyuki = Sample()
    nyuki.start()