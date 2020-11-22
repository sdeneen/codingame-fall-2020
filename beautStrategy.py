import sys
import random
import time

from typing import Optional, List, Dict
from enum import Enum
from collections import deque, Counter
from copy import deepcopy


#####################
##### Constants #####
#####################
MAX_INVENTORY_SIZE = 10
SMACK_TALKS = ["Get got!", "Im gonna brew you something nice", "Whippin' it"]

#####################
###### Toggles ######
#####################
HAS_INGREDIENTS_TARGET_PERCENTAGE = 0.85
ACTION_PATH_DEDUPE_MAX_SIMILAR_ACTIONS = 2
MAX_VALID_PATHS = 30
TOME_SPELL_ORDER_MATCHING_TARGET_PERCENTAGE = 0.75
MAX_ACTIONS_FOR_VALID_PATH = 1

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

    def getPositiveTiersWeight(self) -> int:
        # Calculated based off number of actions to get two of a single tier ingredient
        # Tier 0 = 1 action     (starting spell is 2 tier zeros for free)
        # Tier 1 = 4 actions    (1 action for 2 tier zeros, then use starting spell to convert 1 tier zero to 1 tier one, then REST, then repeat spell)
        # Tier 2 = 7 actions    (4 actions for 2 tier ones, then use starting spell to convert 1 tier one to 1 tier two, then REST, then repeat spell)
        # Tier 3 = 10 actions   (7 actions for 2 tier twos, then use starting spell to convert 1 tier two to 1 tier three, then REST, then repeat spell)

        tierWeights = {
            IngredientTier.TIER_0: 1,
            IngredientTier.TIER_1: 4,
            IngredientTier.TIER_2: 7,
            IngredientTier.TIER_3: 10
        }
        return sum([self.getQuantity(tier) * tierWeights[tier] for tier in self.__tierQuantities if self.getQuantity(tier) > 0])

    def getPositiveTiersTotalQuantity(self) -> int:
        return sum([self.getQuantity(tier) for tier in self.__tierQuantities if self.getQuantity(tier) > 0])

    def getPositiveTiers(self):
        return [tier for tier in self.__tierQuantities if self.getQuantity(tier) > 0]

    def getNegativeTiers(self):
        return [tier for tier in self.__tierQuantities if self.getQuantity(tier) < 0]

    def getMissingTiers(self):
        return [tier for tier in self.__tierQuantities if self.getQuantity(tier) == 0]

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

    def has(self, ingredients: 'Ingredients', targetPercentage: float = 1.0) -> bool:
        assert ingredients.hasNoNegativeQuantities()
        # have = [1, 0, 0, 1]
        # need = [1, 0, 1, 1] => score = targetTierWeight
        # missing = [0, 0, 1, 0] => score = missingTierWeight
        # percentageMissing = missingTierWeight/targetTierWeight
        targetTierWeight = ingredients.getPositiveTiersWeight()
        missingIngredients = self.subtract(ingredients).getNegativeQuantities(True)
        missingTierWeight = missingIngredients.getPositiveTiersWeight()
        percentageMissing = 0 if targetTierWeight == 0 else missingTierWeight / targetTierWeight

        return 1 - percentageMissing >= targetPercentage

    def equals(self, other: 'Ingredients') -> bool:
        for tier in IngredientTier:
            if self.getQuantity(tier) != other.getQuantity(tier):
                return False

        return True

    def __eq__(self, other: 'Ingredients') -> bool:
        for tier in IngredientTier:
            if self.getQuantity(tier) != other.getQuantity(tier):
                return False

        return True

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
        return f"{ActionType.BREW.value} {self.orderId} {random.choice(SMACK_TALKS)}"


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

    def isFree(self) -> bool:
        return self.ingredients.hasNoNegativeQuantities()


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
        # logDebug(f"starting inventory: {startingInventory}")
        stack.append(rootNode)
        while len(stack) > 0:
            # logDebug(f"stack length: {len(stack)}")
            curNode: SpellTraversalNode = stack.pop()
            for spell in getBestSpells(curNode.getLearnedSpellsById(), curNode.getCurInventory(), targetInventory):
                actionsToAdd = []
                updatedLearnedSpells = deepcopy(curNode.getLearnedSpellsById())
                resultingInventoryAfterSpellCast = curNode.getCurInventory().merge(spell.ingredients)

                tookRest = False
                if not spell.castable:
                    # Take a REST
                    tookRest = True
                    actionsToAdd.append(ActionType.REST.value)
                    updatedLearnedSpells = refreshSpells(curNode.getLearnedSpellsById())

                # Cast spell!
                updatedLearnedSpells.get(spell.spellId).castable = 0
                actionsToAdd.append(spell.getActionToCast())
                updatedActionsSoFar = curNode.getActionsSoFar() + actionsToAdd

                if resultingInventoryAfterSpellCast.has(
                        targetInventory,
                        targetPercentage=HAS_INGREDIENTS_TARGET_PERCENTAGE
                ) or tookRest:
                    # Leaf node, finalize action path
                    logDebug(f"Action path: {updatedActionsSoFar}")
                    validActionPath = ActionPath(updatedActionsSoFar, resultingInventoryAfterSpellCast)
                    validActionPaths.append(validActionPath)
                    if len(validActionPaths) == MAX_VALID_PATHS:
                        return validActionPaths
                else:
                    if shouldContinueTraversal(updatedActionsSoFar, validActionPaths):
                        stack.append(SpellTraversalNode(resultingInventoryAfterSpellCast, updatedLearnedSpells, updatedActionsSoFar))

        return validActionPaths

    def actionsToGetInventory(self, desiredInventory: Ingredients) -> Optional[ActionPath]:
        possibleActionPaths = self.actionsToGetTargetInventory(self.inventory, desiredInventory)
        # logDebug("Possible action paths: " + "\n--\\".join([str(a) for a in possibleActionPaths]))
        return findClosestToTargetInventory(possibleActionPaths, desiredInventory)


class GameState(StringRepresenter):
    def __init__(self, witches, clientOrders, tomeSpells):
        self.witches = witches
        self.clientOrders = clientOrders
        self.tomeSpells: List[TomeSpell] = tomeSpells

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
                TomeSpell(action_id, int(tome_index), int(delta_0), int(delta_1), int(delta_2), int(delta_3), int(tax_count))
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


def timed(method):
    def timeMethod(*args, **kw):
        startTime = time.time()
        result = method(*args, **kw)
        endTime = time.time()
        diff = endTime - startTime
        logDebug(f"Took {diff * 1000:.2f} milliseconds")
        return result
    return timeMethod

#####################
######## Algo #######
#####################


ALL_ORDERS_COSTS = [
    Ingredients.fromTierArgs(2, 2, 0, 0),
    Ingredients.fromTierArgs(3, 2, 0, 0),
    Ingredients.fromTierArgs(0, 4, 0, 0),
    Ingredients.fromTierArgs(2, 0, 2, 0),
    Ingredients.fromTierArgs(2, 3, 0, 0),
    Ingredients.fromTierArgs(3, 0, 2, 0),
    Ingredients.fromTierArgs(0, 2, 2, 0),
    Ingredients.fromTierArgs(0, 5, 0, 0),
    Ingredients.fromTierArgs(2, 0, 0, 2),
    Ingredients.fromTierArgs(2, 0, 3, 0),
    Ingredients.fromTierArgs(3, 0, 0, 2),
    Ingredients.fromTierArgs(0, 0, 4, 0),
    Ingredients.fromTierArgs(0, 2, 0, 2),
    Ingredients.fromTierArgs(0, 3, 2, 0),
    Ingredients.fromTierArgs(0, 2, 3, 0),
    Ingredients.fromTierArgs(0, 0, 2, 2),
    Ingredients.fromTierArgs(0, 3, 0, 2),
    Ingredients.fromTierArgs(2, 0, 0, 3),
    Ingredients.fromTierArgs(0, 0, 5, 0),
    Ingredients.fromTierArgs(0, 0, 0, 4),
    Ingredients.fromTierArgs(0, 2, 0, 3),
    Ingredients.fromTierArgs(0, 0, 3, 2),
    Ingredients.fromTierArgs(0, 0, 2, 3),
    Ingredients.fromTierArgs(0, 0, 0, 5),
    Ingredients.fromTierArgs(2, 1, 0, 1),
    Ingredients.fromTierArgs(0, 2, 1, 1),
    Ingredients.fromTierArgs(1, 0, 2, 1),
    Ingredients.fromTierArgs(2, 2, 2, 0),
    Ingredients.fromTierArgs(2, 2, 0, 2),
    Ingredients.fromTierArgs(2, 0, 2, 2),
    Ingredients.fromTierArgs(0, 2, 2, 2),
    Ingredients.fromTierArgs(1, 1, 1, 1),
    Ingredients.fromTierArgs(3, 1, 1, 1),
    Ingredients.fromTierArgs(1, 3, 1, 1),
    Ingredients.fromTierArgs(1, 1, 3, 1),
    Ingredients.fromTierArgs(1, 1, 1, 3)
]

ALL_TOME_SPELLS_DELTAS = [
    Ingredients.fromTierArgs(-3, 0, 0, 1),
    Ingredients.fromTierArgs(3, -1, 0, 0),
    Ingredients.fromTierArgs(1, 1, 0, 0),
    Ingredients.fromTierArgs(0, 0, 1, 0),
    Ingredients.fromTierArgs(3, 0, 0, 0),
    Ingredients.fromTierArgs(2, 3, -2, 0),
    Ingredients.fromTierArgs(2, 1, -2, 1),
    Ingredients.fromTierArgs(3, 0, 1, -1),
    Ingredients.fromTierArgs(3, -2, 1, 0),
    Ingredients.fromTierArgs(2, -3, 2, 0),
    Ingredients.fromTierArgs(2, 2, 0, -1),
    Ingredients.fromTierArgs(-4, 0, 2, 0),
    Ingredients.fromTierArgs(2, 1, 0, 0),
    Ingredients.fromTierArgs(4, 0, 0, 0),
    Ingredients.fromTierArgs(0, 0, 0, 1),
    Ingredients.fromTierArgs(0, 2, 0, 0),
    Ingredients.fromTierArgs(1, 0, 1, 0),
    Ingredients.fromTierArgs(-2, 0, 1, 0),
    Ingredients.fromTierArgs(-1, 0, -1, 1),
    Ingredients.fromTierArgs(0, 2, -1, 0),
    Ingredients.fromTierArgs(2, -2, 0, 1),
    Ingredients.fromTierArgs(-3, 1, 1, 0),
    Ingredients.fromTierArgs(0, 2, -2, 1),
    Ingredients.fromTierArgs(1, -3, 1, 1),
    Ingredients.fromTierArgs(0, 3, 0, -1),
    Ingredients.fromTierArgs(0, -3, 0, 2),
    Ingredients.fromTierArgs(1, 1, 1, -1),
    Ingredients.fromTierArgs(1, 2, -1, 0),
    Ingredients.fromTierArgs(4, 1, -1, 0),
    Ingredients.fromTierArgs(-5, 0, 0, 2),
    Ingredients.fromTierArgs(-4, 0, 1, 1),
    Ingredients.fromTierArgs(0, 3, 2, -2),
    Ingredients.fromTierArgs(1, 1, 3, -2),
    Ingredients.fromTierArgs(-5, 0, 3, 0),
    Ingredients.fromTierArgs(-2, 0, -1, 2),
    Ingredients.fromTierArgs(0, 0, -3, 3),
    Ingredients.fromTierArgs(0, -3, 3, 0),
    Ingredients.fromTierArgs(-3, 3, 0, 0),
    Ingredients.fromTierArgs(-2, 2, 0, 0),
    Ingredients.fromTierArgs(0, 0, -2, 2),
    Ingredients.fromTierArgs(0, -2, 2, 0),
    Ingredients.fromTierArgs(0, 0, 2, -1)
]

HIGH_VALUE_TOME_SPELLS = [
    Ingredients.fromTierArgs(4, 0, 0, 0)
]


def findOrderIndexForOrder(order: ClientOrder, orderCosts: [Ingredients]) -> Optional[int]:
    for index, orderCost in enumerate(orderCosts):
        if order.ingredients.equals(orderCost):
            return index

    return None


def calculateBestTomeSpellsByOrderIndex() -> Dict[int, List[int]]:
    bestTomeSpellByOrderIndex = {}
    for orderIndex, orderCost in enumerate(ALL_ORDERS_COSTS):
        for spellDeltaIndex, spellDelta in enumerate(ALL_TOME_SPELLS_DELTAS):
            if spellDelta.getPositiveQuantities().has(orderCost, TOME_SPELL_ORDER_MATCHING_TARGET_PERCENTAGE):
                matchingSpells = bestTomeSpellByOrderIndex.get(orderIndex, [])
                matchingSpells.append(spellDeltaIndex)
                bestTomeSpellByOrderIndex[orderIndex] = matchingSpells

    return bestTomeSpellByOrderIndex


BEST_TOME_SPELLS_BY_ORDER_INDEX = calculateBestTomeSpellsByOrderIndex()


def getBestSpells(spells: Dict[str, Spell], curInventory: Ingredients, targetInventory: Ingredients) -> [Spell]:
    # MAX_BEST_SPELLS_TO_CONSIDER = 4
    # spellIdToResultingMissingIngredientsWeight = {}
    # spellIdToResultingInventoryWeight = {}
    spellsToSort = []
    for spell in spells.values():
        if curInventory.has(spell.ingredients.getNegativeQuantities(True)):  # cur inventory has ingredients to cast spell
            resultingInventoryAfterSpellCast = curInventory.merge(spell.ingredients)
            if resultingInventoryAfterSpellCast.getPositiveTiersTotalQuantity() > MAX_INVENTORY_SIZE:
                # logDebug(f"Considered casting a spell {spell} that would overflow our inventory {curInventory}.")
                continue

            spellsToSort.append(spell)

    return spellsToSort


def shouldContinueTraversal(actionsSoFar: [str], validActionPaths: [ActionPath]) -> bool:
    for validActionPath in validActionPaths:
        for actionIndex in range(ACTION_PATH_DEDUPE_MAX_SIMILAR_ACTIONS):
            if actionsSoFar[actionIndex] != validActionPath.getActions()[actionIndex]:
                break
            if actionIndex == ACTION_PATH_DEDUPE_MAX_SIMILAR_ACTIONS - 1:
                return False

    return len(actionsSoFar) <= MAX_ACTIONS_FOR_VALID_PATH


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


def findClosestToTargetInventory(actionPaths: [ActionPath], targetInventory: Ingredients) -> Optional[ActionPath]:
    def calculateMissingIngredientsWeight(resultingInventoryForActionPath: Ingredients, targetInventory: Ingredients):
        return resultingInventoryForActionPath.subtract(targetInventory).getNegativeQuantities(True).getPositiveTiersWeight()

    lowestActionPath = min(actionPaths,
        key=lambda actionPath: calculateMissingIngredientsWeight(actionPath.getResultingInventory(), targetInventory))
    lowestActionPathWeight = calculateMissingIngredientsWeight(lowestActionPath.getResultingInventory(), targetInventory)
    closestActionPaths = [a for a in actionPaths if calculateMissingIngredientsWeight(a.getResultingInventory(), targetInventory) == lowestActionPathWeight]
    logDebug(f"Best action paths: {closestActionPaths}")
    return min(closestActionPaths, key=lambda actionPath: len(actionPath.getActions()))


def findMostCommonFirstAction(actionPaths: [ActionPath]) -> Optional[ActionPath]:
    firstActions = [a.getActions()[0] for a in actionPaths]
    firstActionCounts = Counter(firstActions)
    # logDebug(str(firstActionCounts))
    mostCommonFirstAction = max(firstActionCounts, key=firstActionCounts.get)
    return ActionPath([mostCommonFirstAction], None)


def findShortestActionPaths(actionPaths: [ActionPath]) -> [ActionPath]:
    if len(actionPaths) == 0:
        logDebug("Couldn't find any possible action path")
        return []
    shortestPathLength = min([len(a.getActions()) for a in actionPaths])
    return [a for a in actionPaths if len(a.getActions()) == shortestPathLength]


def chooseOrder(orders: [ClientOrder], currentInventory: Ingredients) -> ClientOrder:
    def calculateMissingIngredientsWeight(order: ClientOrder, currentInventory: Ingredients):
        return currentInventory.subtract(order.ingredients).getNegativeQuantities(True).getPositiveTiersWeight()

    # TODO (mv): clean this code
    lowestWeightedOrder = min(orders, key=lambda order: calculateMissingIngredientsWeight(order, currentInventory))
    lowestWeight = calculateMissingIngredientsWeight(lowestWeightedOrder, currentInventory)
    return max([o for o in orders if calculateMissingIngredientsWeight(o, currentInventory) == lowestWeight], key=lambda order: order.price)

def chooseOrderBasedOffInventoryAfterOneSpellCast(orders: [ClientOrder], currentInventory: Ingredients, spells: [Spell]) -> [ClientOrder]:
    orderToLowestMissingIngredientsWeight = {}
    for order in orders:
        minMissingIngredientsWeight = None
        for spell in spells:
            resultingInventoryAfterSpellCast = currentInventory
            if spell.castable:
                resultingInventoryAfterSpellCast = currentInventory.merge(spell.ingredients)
            missingIngredientsWeight = resultingInventoryAfterSpellCast.subtract(order.ingredients).getNegativeQuantities(True).getPositiveTiersWeight()
            if minMissingIngredientsWeight is None or missingIngredientsWeight < minMissingIngredientsWeight:
                minMissingIngredientsWeight = missingIngredientsWeight

        orderToLowestMissingIngredientsWeight[order] = minMissingIngredientsWeight

    return min(orderToLowestMissingIngredientsWeight.keys(), key=lambda orderKey: orderToLowestMissingIngredientsWeight[orderKey])

@timed
def runAlgo(gameState: GameState):
    ourWitch = gameState.getOurWitch()
    for o in gameState.clientOrders:
        if ourWitch.hasIngredientsForOrder(o):
            return print(o.getBrewAction())
    chosenOrder = chooseOrderBasedOffInventoryAfterOneSpellCast(gameState.clientOrders, ourWitch.inventory, ourWitch.spellsById.values())
    logDebug(f"Going for order={chosenOrder}")

    # learnSpellMaybe = testTomeAlgo(gameState)
    learnSpellMaybe = learnSpellsSean(gameState)
    if learnSpellMaybe is not None:
        logDebug("Learning a spell ")
        return print(learnSpellMaybe)

    if ourWitch.hasIngredientsForOrder(chosenOrder):
        print(chosenOrder.getBrewAction())
    else:
        actionPath = ourWitch.actionsToGetInventory(chosenOrder.ingredients)
        if actionPath is None:
            # Shouldn't happen? Hopefully
            logDebug("Ay dios mio. No action path found!!")
            print(ActionType.REST.value)
        else:
            logDebug(f"Chose action path with length {len(actionPath.getActions())}: {actionPath}")
            print(actionPath.getActions()[0])


def testTomeAlgo(gameState: GameState) -> Optional[str]:
    def isCheapAndCanAfford(spell: TomeSpell):
        return spell.ingredients.hasNoNegativeQuantities() \
               and gameState.getOurWitch().inventory.getQuantity(IngredientTier.TIER_0) >= spell.spellIndex

    for spell in [t for t in gameState.tomeSpells if t.spellIndex <= 3]:
        if isCheapAndCanAfford(spell):
            return f"{ActionType.LEARN.value} {spell.spellId}"

    return None


def learnSpellsSean(gameState: GameState) -> Optional[str]:
    def isFreeToCast(spell: TomeSpell):
        return spell.ingredients.hasNoNegativeQuantities()

    def isHighValueSpell(spell: TomeSpell):
        return spell.ingredients in HIGH_VALUE_TOME_SPELLS

    def canAffordTomeSpell(spell: TomeSpell) -> bool:
        return gameState.getOurWitch().inventory.getQuantity(IngredientTier.TIER_0) >= spell.spellIndex

    # Take free to cast spells that are in the rest couple of tome spells
    for spell in [t for t in gameState.tomeSpells if t.spellIndex <= 2]:
        if isFreeToCast(spell) and canAffordTomeSpell(spell):
            return f"{ActionType.LEARN.value} {spell.spellId}"

    # Learn high value spells that are in the rest couple of tome spells
    for spell in [t for t in gameState.tomeSpells if t.spellIndex <= 2]:
        if isHighValueSpell(spell) and canAffordTomeSpell(spell):
            return f"{ActionType.LEARN.value} {spell.spellId}"

    spellsToLearn: [Spell] = []
    for clientOrder in gameState.clientOrders:
        orderIndex = findOrderIndexForOrder(clientOrder, ALL_ORDERS_COSTS)
        if orderIndex is not None and orderIndex in BEST_TOME_SPELLS_BY_ORDER_INDEX:
            bestTomeSpellIndices = BEST_TOME_SPELLS_BY_ORDER_INDEX[orderIndex]
            tomeSpellDeltas = list(map(lambda index: ALL_TOME_SPELLS_DELTAS[index], bestTomeSpellIndices))
            for tomeSpellDelta in tomeSpellDeltas:
                for spell in gameState.tomeSpells:
                    if spell.spellIndex <=2 and canAffordTomeSpell(spell) and tomeSpellDelta.equals(spell.ingredients):
                        spellsToLearn.append(spell)
    if len(spellsToLearn) == 0:
        return None
    logDebug(f"Spells to learn: {spellsToLearn}")
    cheapestSpellToLearn = min(spellsToLearn, key=lambda spell: spell.spellIndex)
    return f"{ActionType.LEARN.value} {cheapestSpellToLearn.spellId}"

    # numStartingSpells = 4
    # numCurSpellsKnown = len(gameState.getOurWitch().spellsById.values())
    # numSpellsLearnedFromTomeSoFar = numCurSpellsKnown - numStartingSpells
    # firstSpell = next(spell for spell in gameState.tomeSpells if spell.spellIndex == 0)
    # if numSpellsLearnedFromTomeSoFar < 5 or firstSpell.tier0Earned > 0:
    #     return f"{ActionType.LEARN.value} {firstSpell.spellId}"

while True:
    runAlgo(parseInput())
