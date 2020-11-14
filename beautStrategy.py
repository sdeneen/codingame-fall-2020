# To debug: print("Debug messages...", file=sys.stderr, flush=True)
# Write an action using print
# in the first league: BREW <id> | WAIT; later: BREW <id> | CAST <id> [<times>] | LEARN <id> | REST | WAIT
from enum import Enum


#####################
###### Classes ######
#####################

class StringRepresenter(object):
    def __repr__(self):
        return repr(vars(self))


class ActionType(Enum):
    CAST = "CAST"
    OPPONENT_CAST = "OPPONENT_CAST"
    LEARN = "LEARN"
    BREW = "BREW"


class ClientOrder(StringRepresenter):
    def __init__(self, orderId, numBlue, numGreen, numOrange, numYellow, price):
        self.orderId = orderId
        self.numBlue = numBlue
        self.numGreen = numGreen
        self.numOrange = numOrange
        self.numYellow = numYellow
        self.price = price


class Inventory(StringRepresenter):
    def __init__(self, numBlue, numGreen, numOrange, numYellow):
        self.numBlue = numBlue
        self.numGreen = numGreen
        self.numOrange = numOrange
        self.numYellow = numYellow


class Witch(StringRepresenter):
    def __init__(self, inventory: Inventory, rupees: int):
        self.inventory = inventory
        self.rupees = rupees


class GameState(StringRepresenter):
    def __init__(self, witches, clientOrders):
        self.witches = witches
        self.clientOrders = clientOrders


#####################
######## Algo #######
#####################

def parseInput() -> GameState:
    clientOrders = parseClientOrders()
    witches = parseWitches()
    return GameState(witches, clientOrders)


def parseClientOrders() -> [ClientOrder]:
    clientOrders = []
    action_count = int(input())  # the number of spells and recipes in play
    for i in range(action_count):
        # tome_index: in the first two leagues: always 0; later: the index in the tome if this is a tome spell, equal to the read-ahead tax; For brews, this is the value of the current urgency bonus
        # tax_count: in the first two leagues: always 0; later: the amount of taxed tier-0 ingredients you gain from learning this spell; For brews, this is how many times you can still gain an urgency bonus
        # castable: in the first league: always 0; later: 1 if this is a castable player spell
        # repeatable: for the first two leagues: always 0; later: 1 if this is a repeatable player spell
        action_id, action_type, delta_0, delta_1, delta_2, delta_3, price, tome_index, tax_count, castable, repeatable = input().split()
        action_id = int(action_id)
        action_type = ActionType[action_type]
        if action_type is ActionType.BREW:
            clientOrders.append(
                ClientOrder(action_id, int(delta_0), int(delta_1), int(delta_2), int(delta_3), int(price))
            )
        # tome_index = int(tome_index)
        # tax_count = int(tax_count)
        # castable = castable != "0"
        # repeatable = repeatable != "0"
    return clientOrders


def parseWitches():
    witches = []

    for i in range(2):
        # inv_0: tier-0 ingredients in inventory
        # score: amount of rupees
        inv_0, inv_1, inv_2, inv_3, rupees = [int(j) for j in input().split()]
        witches.append(Witch(Inventory(inv_0, inv_1, inv_2, inv_3), rupees))

    return witches


def runAlgo(gameState: GameState):
    # TODO (mv): brew 2 pots
    pass


gameState = parseInput()
runAlgo(gameState)
