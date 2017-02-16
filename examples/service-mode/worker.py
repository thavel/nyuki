import logging
from nyuki.workflow import WorkflowNyuki


log = logging.getLogger(__name__)


class Worker(WorkflowNyuki):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def setup(self):
        pass


if __name__ == '__main__':
    nyuki = Worker()
    nyuki.start()
