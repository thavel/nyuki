import logging
from nyuki.workflow import WorkflowNyuki


log = logging.getLogger(__name__)


class Worker(WorkflowNyuki):
    pass


if __name__ == '__main__':
    nyuki = Worker()
    nyuki.start()
