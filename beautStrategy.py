# To debug: print("Debug messages...", file=sys.stderr, flush=True)
# Write an action using print
# in the first league: BREW <id> | WAIT; later: BREW <id> | CAST <id> [<times>] | LEARN <id> | REST | WAIT
import sys
from typing import Optional, List, Dict
from enum import Enum
from collections import deque
from copy import deepcopy


MAX_INVENTORY_SIZE = 10

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
    REST = "REST"


class IngredientTier(Enum):
    TIER_0 = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3

    @staticmethod
    def getIngredientTierForNum(tierNum: int) -> 'IngredientTier':
        return IngredientTier(tierNum)


class Ingredients(StringRepresenter):

    def __init__(self, tierQuantities: [IngredientTier, int]):
        # Map the tier to the quantity of that tier, defaulting to zero
        self.__tierQuantities = {
            tier: 0 for tier in IngredientTier
        }
        self.__tierQuantities.update(tierQuantities)

    def getQuantity(self, tier: IngredientTier) -> int:
        return self.__tierQuantities.get(tier, 0)

    # Test algo
    def getPositiveTiersWeight(self) -> int:
        return sum([self.getQuantity(tier) * (tier.value + 1) for tier in self.__tierQuantities if self.getQuantity(tier) > 0])

    # Test algo
    def getPositiveTiersTotalQuantity(self) -> int:
        return sum([self.getQuantity(tier) for tier in self.__tierQuantities if self.getQuantity(tier) > 0])

    def getPositiveTiers(self):
        return [tier for tier in self.__tierQuantities if self.getQuantity(tier) > 0]

    def getNegativeTiers(self):
        return [tier for tier in self.__tierQuantities if self.getQuantity(tier) < 0]

    # Return a new ingredients object that only includes the tiers with negative quantities
    def getNegativeQuantities(self, absoluteValue: bool = False) -> 'Ingredients':
        newTiers = {
            tier: abs(self.getQuantity(tier)) if absoluteValue else self.getQuantity(tier) for tier in self.__tierQuantities if self.getQuantity(tier) < 0
        }
        return Ingredients(newTiers)

    # Return a new ingredients object that only includes the tiers with positive quantities
    def getPositiveQuantities(self) -> 'Ingredients':
        newTiers = {
            tier: self.getQuantity(tier) for tier in self.__tierQuantities if self.getQuantity(tier) > 0
        }
        return Ingredients(newTiers)

    def hasNoNegativeQuantities(self):
        return len(self.getNegativeTiers()) == 0

    # Diff ingredient quantities (subtracting other from self)
    def subtract(self, ingredientsToRemove: 'Ingredients') -> 'Ingredients':
        for tier in self.__tierQuantities:
            assert ingredientsToRemove.getQuantity(tier) >= 0

        newTiers = {
            tier: self.getQuantity(tier) - ingredientsToRemove.getQuantity(tier) for tier in self.__tierQuantities
        }
        return Ingredients(newTiers)

    # Merge ingredient quantities (adding or subtracting depending on if the quantities are positive or negative)
    def merge(self, other: 'Ingredients') -> 'Ingredients':
        newTiers = {
            tier: self.getQuantity(tier) + other.getQuantity(tier) for tier in self.__tierQuantities
        }
        return Ingredients(newTiers)

    # Replace tiers from source (like Object.assign in JS)
    def overwrite(self, source: 'Ingredients'):
        self.__tierQuantities.update(source.__tierQuantities)

    def has(self, ingredients: 'Ingredients') -> bool:
        assert ingredients.hasNoNegativeQuantities()
        return self.subtract(ingredients).hasNoNegativeQuantities()

    @staticmethod
    def fromTierArgs(*tiers):
        i = 0
        dict = {}
        while i < len(tiers) and i < len(IngredientTier):
            tier = IngredientTier.getIngredientTierForNum(i)
            dict[tier] = tiers[i]
            i += 1

        return Ingredients(dict)


class ActionPath(StringRepresenter):
    def __init__(self, actions: [str], resultingInventory: Ingredients):
        self.__actions = actions
        self.__resultingInventory = deepcopy(resultingInventory)

    def getActions(self) -> [str]:
        return self.__actions

    def getResultingInventory(self) -> Ingredients:
        return self.__resultingInventory


class ClientOrder(StringRepresenter):
    def __init__(self, orderId, tier0, tier1, tier2, tier3, price, urgencyBonus):
        self.orderId = orderId
        self.ingredients = Ingredients.fromTierArgs(tier0, tier1, tier2, tier3)
        self.price = price  # includes urgency bonus already
        self.urgencyBonus = urgencyBonus

    def getBrewAction(self) -> str:
        return f"{ActionType.BREW.value} {self.orderId}"


class Spell(StringRepresenter):
    def __init__(self, spellId, tier0, tier1, tier2, tier3, castable, repeatable):
        self.spellId = spellId
        self.ingredients = Ingredients.fromTierArgs(tier0, tier1, tier2, tier3)
        self.castable = castable != 0
        self.repeatable = repeatable != 0

    def createsAny(self, ingredientTiers: List[IngredientTier]) -> bool:
        tiersCreated = set(self.ingredients.getPositiveTiers())
        return len(tiersCreated.intersection(ingredientTiers)) > 0

    def getActionToCast(self, times: int = 1) -> str:
        if times > 1:
            assert self.repeatable
        return f"{ActionType.CAST.value} {self.spellId} {times}"


class TomeSpell(StringRepresenter):
    def __init__(self, spellId, spellIndex, tier0, tier1, tier2, tier3, tier0Earned):
        self.spellId = spellId
        self.spellIndex = spellIndex
        self.ingredients = Ingredients.fromTierArgs(tier0, tier1, tier2, tier3)
        self.tier0Earned = tier0Earned


class SpellTraversalNode(StringRepresenter):
    def __init__(self, curInventory: Ingredients, learnedSpellsById: Dict[str, Spell], actionsSoFar: [str]):
        self.__curInventory = curInventory
        self.__learnedSpellsById = learnedSpellsById
        self.__actionsSoFar = actionsSoFar

    def getCurInventory(self) -> Ingredients:
        return self.__curInventory

    def getLearnedSpellsById(self) -> Dict[str, Spell]:
        return self.__learnedSpellsById

    # Chronological order of the actions we've taken in this action path so far
    def getActionsSoFar(self) -> [str]:
        return self.__actionsSoFar


class Witch(StringRepresenter):
    def __init__(self, inventory: Ingredients, rupees: int, spells: [Spell]):
        self.inventory = inventory
        self.rupees = rupees
        self.spellsById: Dict[str, Spell] = {
            spell.spellId : spell for spell in spells
        }

    def hasIngredientsForOrder(self, order: ClientOrder) -> bool:
        for tier in IngredientTier:
            if self.inventory.getQuantity(tier) < order.ingredients.getQuantity(tier):
                return False

        return True


    def actionsToGetTargetInventory(self, startingInventory: Ingredients, targetInventory: Ingredients) -> [ActionPath]:
        assert startingInventory.hasNoNegativeQuantities() and targetInventory.hasNoNegativeQuantities()
        validActionPaths = []

        if startingInventory.has(targetInventory):
            return validActionPaths

        stack = deque()
        rootNode = SpellTraversalNode(startingInventory, self.spellsById, [])
        stack.append(rootNode)
        while len(stack) > 0:
            # logDebug(f"stack length: {len(stack)}")
            curNode: SpellTraversalNode = stack.pop()
            # logDebug(f"Actions so far: {curNode.getActionsSoFar()}")
            # logDebug(f"Cur inventory: {curNode.getCurInventory()}")
            for spell in curNode.getLearnedSpellsById().values():
                actionsToAdd = []
                updatedLearnedSpells = deepcopy(curNode.getLearnedSpellsById())
                resultingInventory = curNode.getCurInventory().merge(spell.ingredients)
                if curNode.getCurInventory().has(spell.ingredients.getNegativeQuantities(True)):
                    # debugging overflowed inventory
                    if (resultingInventory.getPositiveTiersTotalQuantity() > MAX_INVENTORY_SIZE):
                        logDebug(f"Considered casting a spell that would overflow our inventory. Action path length is {len(curNode.getActionsSoFar())}")
                        continue

                    if not spell.castable:
                        # Take a REST
                        actionsToAdd.append(ActionType.REST.value)
                        updatedLearnedSpells = refreshSpells(curNode.getLearnedSpellsById())

                    # Cast spell!
                    updatedLearnedSpells.get(spell.spellId).castable = 0
                    actionsToAdd.append(spell.getActionToCast())
                    updatedActionsSoFar = curNode.getActionsSoFar() + actionsToAdd

                    if resultingInventory.has(targetInventory):
                        # Leaf node, finalize action path
                        validActionPath = ActionPath(updatedActionsSoFar, resultingInventory)
                        validActionPaths.append(validActionPath)
                    else:
                        if len(updatedActionsSoFar) <= 15:
                            stack.append(SpellTraversalNode(resultingInventory, updatedLearnedSpells, updatedActionsSoFar))

        return validActionPaths



    # Right now this just picks the shortest action path to get the highest tier missing ingredient
    # todo (algo++): Needs a real algo that looks at all missing ingredients to figure out in
    #                what order to fulfill them (ideally optimizing rests)
    def actionsToGetInventory(self, desiredInventory: Ingredients) -> Optional[ActionPath]:
        possibleActionPaths = self.actionsToGetTargetInventory(self.inventory, desiredInventory)
        logDebug("\n".join([str(a) for a in possibleActionPaths]))
        #chosenActionPath = findHighestWeightedResultingInventory(findShortestActionPaths(possibleActionPaths))
        return findShortestActionPath(possibleActionPaths)


class GameState(StringRepresenter):
    def __init__(self, witches, clientOrders, tomeSpells):
        self.witches = witches
        self.clientOrders = clientOrders
        self.tomeSpells = tomeSpells

    def getOurWitch(self) -> Witch:
        return self.witches[0]

    def getOrdersSortedByPriceDesc(self) -> [ClientOrder]:
        return sorted(self.clientOrders, key=lambda o: o.price, reverse=True)


##############################
######## Input parsing #######
##############################


def parseInput() -> GameState:
    clientOrders, ourSpells, theirSpells, tomeSpells, mainInputLines = parseClientOrdersOurSpellsTheirSpellsTomeSpells()
    witches, witchInputLines = parseWitches(ourSpells, theirSpells)
    mainInputLines.extend(witchInputLines)
    # Uncomment this to print the game input (useful to record test cases)
    # logDebug("\n".join(mainInputLines))
    return GameState(witches, clientOrders, tomeSpells)


def parseClientOrdersOurSpellsTheirSpellsTomeSpells() -> [ClientOrder]:
    clientOrders = []
    ourSpells = []
    theirSpells = []
    tomeSpells = []
    inputLines = []
    curLine = input()
    inputLines.append(curLine)
    action_count = int(curLine)  # the number of spells and recipes in play

    for i in range(action_count):
        curLine = input()
        inputLines.append(curLine)
        action_id, action_type, delta_0, delta_1, delta_2, delta_3, price, tome_index, tax_count, castable, repeatable = curLine.split()
        action_id = int(action_id)
        action_type = ActionType[action_type]
        if action_type is ActionType.BREW:
            clientOrders.append(
                ClientOrder(action_id, abs(int(delta_0)), abs(int(delta_1)), abs(int(delta_2)), abs(int(delta_3)), abs(int(price)), int(tome_index))
            )
        elif action_type is ActionType.CAST:
            ourSpells.append(
                Spell(action_id, int(delta_0), int(delta_1), int(delta_2), int(delta_3), int(castable), int(repeatable))
            )
        elif action_type is ActionType.OPPONENT_CAST:
            theirSpells.append(
                Spell(action_id, int(delta_0), int(delta_1), int(delta_2), int(delta_3), int(castable), int(repeatable))
            )
        elif action_type is ActionType.LEARN:
            tomeSpells.append(
                TomeSpell(action_id, int(tome_index), int(delta_0), int(delta_1), int(delta_2), int(delta_3), tax_count)
            )
        else:
            raise ValueError(f"Unknown action type {action_type}")

    return clientOrders, ourSpells, theirSpells, tomeSpells, inputLines


def parseWitches(ourSpells: [Spell], theirSpells: [Spell]):
    witches = []
    inputLines = []

    for i in range(2):
        curLine = input()
        inputLines.append(curLine)
        # inv_0: tier-0 ingredients in inventory
        # score: amount of rupees
        inv_0, inv_1, inv_2, inv_3, rupees = [int(j) for j in curLine.split()]
        ingredients = Ingredients.fromTierArgs(inv_0, inv_1, inv_2, inv_3)
        witches.append(
            Witch(
                ingredients,
                rupees,
                ourSpells if i == 0 else theirSpells
            )
        )

    return witches, inputLines


#####################
######## Util #######
#####################

def logDebug(msg: str):
    print(msg, file=sys.stderr, flush=True)


def refreshSpells(spells: Dict[str, Spell]):
    def refreshSpell(spell: Spell) -> Spell:
        newSpell = deepcopy(spell)
        newSpell.castable = 1
        return newSpell

    return {
        spell.spellId : refreshSpell(spell) for spell in spells.values()
    }


#####################
######## Algo #######
#####################


def findShortestActionPath(actionPaths: [ActionPath]) -> Optional[ActionPath]:
    if len(actionPaths) == 0:
        logDebug("Couldn't find any possible action path")
        return None
    return min(actionPaths, key=lambda path: len(path.getActions()))


def findHighestWeightedResultingInventory(actionPaths: [ActionPath]) -> Optional[ActionPath]:
    if len(actionPaths) == 0:
        logDebug("Couldn't find any possible action path")
        return None
    return max(actionPaths, key=lambda p: p.getResultingInventory().getPositiveTiersWeight())


def findShortestActionPaths(actionPaths: [ActionPath]) -> [ActionPath]:
    if len(actionPaths) == 0:
        logDebug("Couldn't find any possible action path")
        return []
    shortestPathLength = min([len(a.getActions()) for a in actionPaths])
    return [a for a in actionPaths if len(a.getActions()) == shortestPathLength]


def runAlgo(gameState: GameState):
    learnSpellMaybe = testTomeAlgo(gameState)
    if learnSpellMaybe is not None:
        logDebug("Learning a spell ")
        return print(learnSpellMaybe)

    ourWitch = gameState.getOurWitch()
    sortedOrders = gameState.getOrdersSortedByPriceDesc()
    lowestPricedOrder = sortedOrders[-1]  # we're assuming lowest price order is the fastest order to make

    if ourWitch.hasIngredientsForOrder(lowestPricedOrder):
        print(lowestPricedOrder.getBrewAction())
    else:
        actionPath = ourWitch.actionsToGetInventory(lowestPricedOrder.ingredients)
        if actionPath is None:
            # Shouldn't happen? Hopefully
            logDebug("Ay dios mio. No action path found!!")
            print(ActionType.REST.value)
        else:
            logDebug(f"Chose action path with length {len(actionPath.getActions())}")
            print(actionPath.getActions()[0])


def testTomeAlgo(gameState: GameState) -> Optional[str]:
    def isCheapAndCanAfford(spell: TomeSpell):
        return spell.ingredients.hasNoNegativeQuantities() \
               and gameState.getOurWitch().inventory.getQuantity(IngredientTier.TIER_0) >= spell.spellIndex

    for spell in [t for t in gameState.tomeSpells if t.spellIndex <= 3]:
        if isCheapAndCanAfford(spell):
            return f"{ActionType.LEARN.value} {spell.spellId}"

    return None


while True:
    runAlgo(parseInput())
