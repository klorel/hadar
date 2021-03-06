import time

from pykka import ThreadingActor, ActorRegistry

from hadar.solver.broker import Broker
from hadar.solver.domain import *


def singleton(class_):
    instances = {}
    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance


@singleton
class Waiter:
    def __init__(self, wait_ms=0):
        self.updated = True
        self.wait_ms = wait_ms

    def wait(self):
        while self.updated:
            self.updated = False
            time.sleep(self.wait_ms / 1000)

    def update(self):
        self.updated = True


class Dispatcher(ThreadingActor):

    def __init__(self, name,
                 min_exchange: int=1,
                 consumptions: List[Consumption] = [],
                 productions: List[Production] = [],
                 borders: List[Border] = []):
        super().__init__()

        self.name = name
        self.broker = Broker(name=name,
                             tell=self.tell_to,
                             ask=self.ask_to,
                             min_exchange=min_exchange,
                             consumptions=consumptions,
                             productions=productions,
                             borders=borders)

        self.waiter = Waiter()
        self.events = []

        self.actor_ref.actor_urn = name
        ActorRegistry.register(self.actor_ref)

    def on_receive(self, message):
        """
        Mail box of actor.

        :param message: next message to process
        :return:
        """
        self.waiter.update()
        self.events.append(Event(type='recv', message=message))

        if isinstance(message, Start):
            self.broker.init()
        elif isinstance(message, Snapshot):
            return self
        elif isinstance(message, Next):
            return self.name, self.next()
        elif isinstance(message, ProposalOffer):
            ex = self.broker.receive_proposal_offer(proposal=message)
            self.events.append(Event(type='recv res', message=ex))
            return ex
        elif isinstance(message, Proposal):
            self.broker.receive_proposal(proposal=message)
        elif isinstance(message, ConsumerCanceledExchange):
            self.broker.receive_cancel_exchange(cancel=message)

    def on_stop(self):
        ActorRegistry.unregister(self.actor_ref)

    def tell_to(self, to: str, mes):
        self.events.append(Event(type='tell', message=mes))
        ActorRegistry.get_by_urn(to).tell(mes)

    def ask_to(self, to: str, mes):
        self.events.append(Event(type='ask', message=mes))
        res = ActorRegistry.get_by_urn(to).ask(mes)
        self.events.append(Event(type='ask res', message=res))
        return res

    def next(self):
        c, p, b = self.broker.compute_total()
        # plot(self)
        return c, p, b
