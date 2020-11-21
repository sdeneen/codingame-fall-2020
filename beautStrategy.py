# To debug: print("Debug messages...", file=sys.stderr, flush=True)
# Write an action using print
# in the first league: BREW <id> | WAIT; later: BREW <id> | CAST <id> [<times>] | LEARN <id> | REST | WAIT
import sys
from typing import Optional, List, Dict
from enum import Enum
from collections import deque
from copy import deepcopy


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
        return sum([self.getQuantity(tier) * tier.value for tier in self.__tierQuantities if self.getQuantity(tier) > 0])

    # Test algo
    def getPositiveTiersTotalQuantity(self) -> int:
        return sum([self.getQuantity(tier) for tier in self.__tierQuantities if self.getQuantity(tier) > 0])

    def getPositiveTiers(self):
        return [tier for tier in self.__tierQuantities if self.getQuantity(tier) > 0]

    def getNegativeTiers(self):
        return [tier for tier in self.__tierQuantities if self.getQuantity(tier) < 0]

    # Return a new ingredients object that only includes the tiers with negative quantities
    def getNegativeQuantities(self) -> 'Ingredients':
        newTiers = {
            tier: self.getQuantity(tier) for tier in self.__tierQuantities if self.getQuantity(tier) < 0
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
    def __init__(self, missingIngredients: Ingredients, futureSpellCastsRequiredBeforeRest: Dict[str, int], availableInventory: Ingredients, reverseActionList: [str]):
        self.__missingIngredients = missingIngredients
        self.__numSpellCastsRequiredBeforeNextRest = futureSpellCastsRequiredBeforeRest
        self.__availableInventory = availableInventory
        self.__reverseActionList = reverseActionList

    def getMissingIngredients(self) -> Ingredients:
        return self.__missingIngredients

    def getAvailableInventory(self) -> Ingredients:
        return self.__availableInventory

    def getNumSpellCastsRequiredBeforeNextRest(self) -> Dict[str, int]:
        return self.__numSpellCastsRequiredBeforeNextRest

    # Reverse chronological order of the "future" actions
    def getReverseActionList(self) -> [str]:
        return self.__reverseActionList


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

    # This looks up possible action paths to get missing ingredients, searching a tree from the root where the final
    # action leads to the root, and the first action for each action path is a link to a leaf node
    def actionsToGetMissingIngredients(self, startingInventory: Ingredients, missingIngredients: Ingredients) -> [ActionPath]:
        actionsPathsResult = []
        stack = deque()
        rootNode = SpellTraversalNode(missingIngredients, {}, startingInventory, [])
        stack.append(rootNode)
        while len(stack) > 0:
            curNode: SpellTraversalNode = stack.pop()
            # Precondition: any nodes in the stack with missing ingredients represent ingredients that we do NOT have in our available inventory
            curMissingIngredients = curNode.getMissingIngredients()
            curAvailableInventory = curNode.getAvailableInventory()
            numSpellCastsRequiredBeforeNextRest = curNode.getNumSpellCastsRequiredBeforeNextRest()
            reverseActionList = curNode.getReverseActionList()  # future actions that we've already determined that we need to perform for this action path
            ingredientsToLookFor = curMissingIngredients.getNegativeTiers()

            # Find spells that could generate any of the missing ingredients
            # Do NOT modify any of the above variables in this for loop. Each spell has to result in its own independent state
            for spell in self.spellsById.values():
                if spell.createsAny(ingredientsToLookFor):
                    # This is a valid spell we could use, compute what would happen if we used it and add to the action path
                    # Note that we are strictly ignoring any other gains that result from the spell besides the fact that
                    # it creates a tier that we need. There is room for improvement here
                    # TODO (algo++): prioritize spells that get us closest to the desired ingredients
                    newActions = []  # actions we will be adding in this iteration
                    spellActionToTake = spell.getActionToCast()
                    newActions.append(spellActionToTake)
                    # Track the casting of this spell in our spell cast counter dictionary by incrementing this spell's cast count by 1
                    futureCastsRequiredForCurSpell = numSpellCastsRequiredBeforeNextRest.get(spell.spellId, 0)
                    newNumSpellCastsRequiredBeforeNextRest = deepcopy(numSpellCastsRequiredBeforeNextRest)
                    newNumSpellCastsRequiredBeforeNextRest[spell.spellId] = futureCastsRequiredForCurSpell + 1

                    # TODO (algo++): optimize resting. save rests for when we have casted multiple spells. e.g. [cast1, rest, cast1, cast2] => [cast1, cast2, rest, cast1]
                    # TODO (algo++): can this cause an infinite loop??
                    # Check if we need to rest after casting this spell so we can cast it again later
                    if futureCastsRequiredForCurSpell >= 1:
                        newActions.append(ActionType.REST.value)
                        newNumSpellCastsRequiredBeforeNextRest = {
                            spell.spellId: 1
                        }

                    latestActionList = deepcopy(reverseActionList)
                    latestActionList.extend(newActions)

                    # Simulate inventory update after casting the spell, and keep track of what ingredients we are still missing
                    resultingIngredients = curAvailableInventory.merge(spell.ingredients)
                    if resultingIngredients.getPositiveTiersTotalQuantity() > 10:
                        logDebug("Too many ingredients!")
                    newMissingIngredients = resultingIngredients.getNegativeQuantities()
                    remainingInventory = resultingIngredients.getPositiveQuantities()

                    # If we have the ingredients needed already on hand then we don't need to do any more casting (leaf node!)
                    # Finalize the action path
                    if resultingIngredients.hasNoNegativeQuantities():
                        # Handle rests for spells that start as uncastable to make sure we can use them
                        for spellId in newNumSpellCastsRequiredBeforeNextRest:
                            if newNumSpellCastsRequiredBeforeNextRest[spellId] > 0 and not self.spellsById[spellId].castable:
                                latestActionList.append(ActionType.REST.value)
                                break
                        latestActionList.reverse()   # need to reverse this to be in chronological order since we create the action paths backwards
                        actionPath = ActionPath(latestActionList, remainingInventory)
                        actionsPathsResult.append(actionPath)
                    else:
                        # We need more ingredients, let's add a new node to the stack and keep going
                        newNode = SpellTraversalNode(newMissingIngredients, newNumSpellCastsRequiredBeforeNextRest, remainingInventory, latestActionList)
                        stack.append(newNode)

        return actionsPathsResult

    # Right now this just picks the shortest action path to get the highest tier missing ingredient
    # todo (algo++): Needs a real algo that looks at all missing ingredients to figure out in
    #                what order to fulfill them (ideally optimizing rests)
    def actionsToGetInventory(self, desiredInventory: Ingredients) -> Optional[ActionPath]:
        ingredientsDiff = self.inventory.subtract(desiredInventory)
        remainingIngredients = ingredientsDiff.getPositiveQuantities()
        missingIngredients = ingredientsDiff.getNegativeQuantities()

        if missingIngredients.hasNoNegativeQuantities():
            return ActionPath([], remainingIngredients)

        possibleActionPaths = self.actionsToGetMissingIngredients(remainingIngredients, missingIngredients)
        logDebug("\n".join([str(a) for a in possibleActionPaths]))
        chosenActionPath = findHighestWeightedResultingInventory(findShortestActionPaths(possibleActionPaths))
        return chosenActionPath


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
