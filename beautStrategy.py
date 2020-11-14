# To debug: print("Debug messages...", file=sys.stderr, flush=True)
# Write an action using print
# in the first league: BREW <id> | WAIT; later: BREW <id> | CAST <id> [<times>] | LEARN <id> | REST | WAIT
from typing import Optional, Set, Dict
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



class Ingredients(StringRepresenter):

    def __init__(self, tierQuantities: [IngredientTier, int]):
        # Map the tier to the quantity of that tier, defaulting to zero
        self.__tierQuantities = {
            tier: 0 for tier in IngredientTier
        }
        self.__tierQuantities.update(tierQuantities)

    def getQuantity(self, tier: IngredientTier) -> int:
        return self.__tierQuantities.get(tier, 0)

    def getPositiveTiers(self):
        return set([tier for tier in self.__tierQuantities if self.getQuantity(tier) > 0])

    def getNegativeTiers(self):
        return set([tier for tier in self.__tierQuantities if self.getQuantity(tier) < 0])

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

    def findLowestTierWithNegativeQuantity(self) -> Optional[IngredientTier]:
        sortedIngredientTiers = list(IngredientTier)
        for tier in sortedIngredientTiers:
            if self.getQuantity(tier) < 0:
                return tier

        return None

    def hasNoNegativeQuantities(self):
        return len(self.getNegativeTiers()) == 0

    # Diff ingredient quantities (subtracting other from self)
    def diff(self, other: 'Ingredients') -> 'Ingredients':
        newTiers = {
            tier: self.getQuantity(tier) - other.getQuantity(tier) for tier in self.__tierQuantities
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
            tier = getIngredientTierForNum(i)
            dict[tier] = tiers[i]
            i += 1

        return Ingredients(dict)


class Inventory(StringRepresenter):
    def __init__(self, ingredients: Ingredients):
        self.ingredients = ingredients


class ActionPath(StringRepresenter):
    def __init__(self, actions: [str], resultingInventory: Inventory):
        self.__actions = actions
        self.__resultingInventory = resultingInventory

    def getActions(self) -> [str]:
        return self.__actions

    def getResultingInventory(self) -> Inventory:
        return self.__resultingInventory


class ClientOrder(StringRepresenter):
    def __init__(self, orderId, tier0, tier1, tier2, tier3, price):
        self.orderId = orderId
        self.ingredients = Ingredients.fromTierArgs(tier0, tier1, tier2, tier3)
        self.price = price

    def getBrewAction(self) -> str:
        return f"{ActionType.BREW.value} {self.orderId}"

class Spell(StringRepresenter):
    def __init__(self, spellId, tier0, tier1, tier2, tier3, castable):
        self.spellId = spellId
        self.ingredients = Ingredients.fromTierArgs(tier0, tier1, tier2, tier3)
        self.castable = castable != 0

    def createsAny(self, ingredientTiers: Set[IngredientTier]) -> bool:
        tiersCreated = self.ingredients.getPositiveTiers()
        return len(tiersCreated.intersection(ingredientTiers)) > 0

    def getActionToCast(self) -> str:
        return f"{ActionType.CAST.value} {self.spellId}"


class SpellTraversalNode(StringRepresenter):
    def __init__(self, missingIngredients: Ingredients, futureSpellCastsRequiredBeforeRest: Dict[str, int], availableInventory: Inventory, reverseActionList: [str]):
        self.__missingIngredients = missingIngredients
        self.__numSpellCastsRequiredBeforeNextRest = futureSpellCastsRequiredBeforeRest
        self.__availableInventory = availableInventory
        self.__reverseActionList = reverseActionList

    def getMissingIngredients(self) -> Ingredients:
        return self.__missingIngredients

    def getAvailableInventory(self) -> Inventory:
        return self.__availableInventory

    def getNumSpellCastsRequiredBeforeNextRest(self) -> Dict[str, int]:
        return self.__numSpellCastsRequiredBeforeNextRest

    # Reverse chronological order of the "future" actions
    def getReverseActionList(self) -> [str]:
        return self.__reverseActionList


class Witch(StringRepresenter):
    def __init__(self, inventory: Inventory, rupees: int, spells: [Spell]):
        self.inventory = inventory
        self.rupees = rupees
        self.spellsById: Dict[str, Spell] = {
            spell.spellId : spell for spell in spells
        }

    def hasIngredientsForOrder(self, order: ClientOrder) -> bool:
        for tier in IngredientTier:
            if self.inventory.ingredients.getQuantity(tier) < order.ingredients.getQuantity(tier):
                return False

        return True


    # This looks up possible action paths to get a single ingredient tier, searching a tree from the root where the final action leads to the root, and the first action for each action path is a link to a leaf node
    # TODO (sd): this function mostly already handles action paths to achieving a desired inventory, so maybe change the contract so it takes in a target inventory rather than a single ingredient tier
    def actionsToGetIngredient(self, startingInventory, desiredTier: IngredientTier) -> [ActionPath]:
        actionsPathsResult = []
        spellsById = self.spellsById
        stack = deque()
        rootNode = SpellTraversalNode(Ingredients({desiredTier: -1}), {}, startingInventory, [])
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
            for spell in spellsById.values():
                if spell.createsAny(ingredientsToLookFor):
                    # This is a valid spell we could use, compute what would happen if we used it and add to the action path
                    # Note that we are strictly ignoring any other gains that result from the spell besides the fact that
                    # it creates a tier that we need. There is room for improvement here
                    newActions = []  # actions we will be adding in this iteration
                    spellActionToTake = spell.getActionToCast()
                    newActions.append(spellActionToTake)
                    # Track the casting of this spell in our spell cast counter dictionary by incrementing this spell's cast count by 1
                    futureCastsRequiredForCurSpell = numSpellCastsRequiredBeforeNextRest.get(spell.spellId, 0)
                    numSpellCastsRequiredBeforeNextRest[spell.spellId] = futureCastsRequiredForCurSpell + 1

                    # Check if we need to rest after casting this spell so we can cast it again later
                    if futureCastsRequiredForCurSpell > 1:
                        newActions.append(ActionType.REST.value)
                        numSpellCastsRequiredBeforeNextRest = {
                            spell.spellId: 1
                        }

                    latestActionList = deepcopy(reverseActionList)
                    latestActionList.extend(newActions)

                    # Simulate inventory update after casting the spell, and keep track of what ingredients we are still missing
                    ingredientsCost = spell.ingredients.getNegativeQuantities()
                    resultingIngredients = curAvailableInventory.ingredients.merge(ingredientsCost)
                    newMissingIngredients = resultingIngredients.getNegativeQuantities()
                    remainingInventory = Inventory(resultingIngredients.getPositiveQuantities())

                    # If we have the ingredients needed already on hand then we don't need to do any more casting (leaf node!)
                    # Finalize the action path
                    if resultingIngredients.hasNoNegativeQuantities():
                        # Handle rests for spells that start as uncastable to make sure we can use them
                        for spellId in numSpellCastsRequiredBeforeNextRest:
                            if numSpellCastsRequiredBeforeNextRest[spellId] > 0 and not spellsById[spellId].castable:
                                latestActionList.append(ActionType.REST.value)
                                break
                        latestActionList.reverse()   # need to reverse this to be in chronological order since we create the action paths backwards
                        actionPath = ActionPath(latestActionList, remainingInventory)
                        actionsPathsResult.append(actionPath)
                    else:
                        # We need more ingredients, let's add a new node to the stack and keep going
                        newNode = SpellTraversalNode(newMissingIngredients, numSpellCastsRequiredBeforeNextRest, remainingInventory, latestActionList)
                        stack.append(newNode)


        return actionsPathsResult


    # Right now this just picks the shortest action path to get the highest tier missing ingredient
    # Needs a real algo that looks at all missing ingredients to figure out in what order to fulfill them (ideally optimizing rests)
    def actionsToGetInventory(self, desiredInventory: Inventory) -> ActionPath:
        ingredientsDiff = self.inventory.ingredients.diff(desiredInventory.ingredients)
        remainingInventory = Inventory(ingredientsDiff.getPositiveQuantities())
        missingIngredients = ingredientsDiff.getNegativeQuantities()
        # At some point, could experiment with aiming for the highest tier first if we wanted. Starting low showed marginally better test results on a few test cases
        desiredTier = missingIngredients.findLowestTierWithNegativeQuantity()

        if desiredTier is not None:
            possibleActionPaths = self.actionsToGetIngredient(remainingInventory, desiredTier)
            chosenActionPath = findShortestActionPath(possibleActionPaths)
            return chosenActionPath

        return ActionPath([], remainingInventory)




class GameState(StringRepresenter):
    def __init__(self, witches, clientOrders):
        self.witches = witches
        self.clientOrders = clientOrders

    def getOurWitch(self) -> Witch:
        return self.witches[0]

    def getOrdersSortedByPriceDesc(self) -> [ClientOrder]:
        return sorted(self.clientOrders, key=lambda o: o.price, reverse=True)


##############################
######## Input parsing #######
##############################


def parseInput() -> GameState:
    clientOrders, ourSpells, theirSpells, mainInputLines = parseClientOrdersOurSpellsTheirSpells()
    witches, witchInputLines = parseWitches(ourSpells, theirSpells)
    mainInputLines.extend(witchInputLines)
    # Uncomment this to print the game input (useful to record test cases)
    # print(mainInputLines)
    return GameState(witches, clientOrders)


def parseClientOrdersOurSpellsTheirSpells() -> [ClientOrder]:
    clientOrders = []
    ourSpells = []
    theirSpells = []
    inputLines = []
    curLine = input()
    inputLines.append(curLine)
    action_count = int(curLine)  # the number of spells and recipes in play
    for i in range(action_count):
        # tome_index: in the first two leagues: always 0; later: the index in the tome if this is a tome spell, equal to the read-ahead tax; For brews, this is the value of the current urgency bonus
        # tax_count: in the first two leagues: always 0; later: the amount of taxed tier-0 ingredients you gain from learning this spell; For brews, this is how many times you can still gain an urgency bonus
        # castable: in the first league: always 0; later: 1 if this is a castable player spell
        # repeatable: for the first two leagues: always 0; later: 1 if this is a repeatable player spell
        curLine = input()
        inputLines.append(curLine)
        action_id, action_type, delta_0, delta_1, delta_2, delta_3, price, tome_index, tax_count, castable, repeatable = curLine.split()
        action_id = int(action_id)
        action_type = ActionType[action_type]
        if action_type is ActionType.BREW:
            clientOrders.append(
                ClientOrder(action_id, abs(int(delta_0)), abs(int(delta_1)), abs(int(delta_2)), abs(int(delta_3)), abs(int(price)))
            )
        elif action_type is ActionType.CAST:
            ourSpells.append(
                Spell(action_id, int(delta_0), int(delta_1), int(delta_2), int(delta_3), int(castable))
            )
        elif action_type is ActionType.OPPONENT_CAST:
            theirSpells.append(
                Spell(action_id, int(delta_0), int(delta_1), int(delta_2), int(delta_3), int(castable))
            )
        else:
            raise ValueError(f"Unknown action type {action_type}")
        # tome_index = int(tome_index)
        # tax_count = int(tax_count)
        # castable = castable != "0"
        # repeatable = repeatable != "0"
    return clientOrders, ourSpells, theirSpells, inputLines


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
                Inventory(ingredients),
                rupees,
                ourSpells if i == 0 else theirSpells
            )
        )

    return witches, inputLines


#####################
######## Util #######
#####################

tierNumToTier = { tier.value: tier for tier in IngredientTier }
def getIngredientTierForNum(tierNum: int) -> IngredientTier:
    # No key checks here, we assume it is a valid key
    return tierNumToTier[tierNum]



#####################
######## Algo #######
#####################


def findShortestActionPath(actionPaths: [ActionPath]) -> ActionPath:
    return min(actionPaths, key=lambda path: len(path.getActions()))

def runAlgo(gameState: GameState):
    ourWitch = gameState.getOurWitch()
    sortedOrders = gameState.getOrdersSortedByPriceDesc()
    order = sortedOrders[-1]
    actionPath = ourWitch.actionsToGetInventory(Inventory(order.ingredients))
    if len(actionPath.getActions()) == 0:
        print(order.getBrewAction())
    else:
        print(actionPath.getActions()[0])

while True:
    runAlgo(parseInput())
