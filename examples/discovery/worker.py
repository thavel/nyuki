import logging
from nyuki import Nyuki


log = logging.getLogger(__name__)


class Worker(Nyuki):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.discovery.register(self.handler)

    async def handler(self, addresses):
        log.critical(
            "Discovery found %d instances of the service '%s'\n%s",
            len(addresses), self.config['name'], addresses
        )


if __name__ == '__main__':
    nyuki = Worker()
    nyuki.start()
