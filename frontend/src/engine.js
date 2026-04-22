// Client-side port of the Python engine — deterministic, no server needed.
// Products, filtering, ranking, intent extraction, upsell logic.

import productsData from '../data/products.json'

// --- Data ---
export function loadProducts() {
  return productsData
}

export function filterByStore(products, storeType) {
  return products.filter(p => p.store_type === storeType)
}

// --- Intent extraction ---
const CATEGORY_KEYWORDS = {
  lunch: ['lunch', 'midday', 'noon', 'mid-day'],
  breakfast: ['breakfast', 'morning', 'start the day', 'brunch'],
  snack: ['snack', 'nibble', 'small bite', 'something small'],
  drink: ['drink', 'beverage', 'thirsty', 'juice', 'coffee', 'tea', 'smoothie'],
  dinner: ['dinner', 'evening', 'supper'],
}

const PREFERENCE_KEYWORDS = {
  light: ['light', 'not heavy', 'something light'],
  healthy: ['healthy', 'nutritious', 'clean', 'low calorie', 'low-calorie'],
  filling: ['filling', 'big', 'hearty', 'hungry', 'starving'],
  indulgent: ['indulgent', 'treat', 'rich', 'comfort', 'cheat'],
}

const MODIFIER_KEYWORDS = {
  quick: ['quick', 'fast', 'rush', 'hurry', 'no time', 'rushed'],
  cheap: ['cheap', 'affordable', 'budget', 'low cost', 'inexpensive'],
}

const DIETARY_KEYWORDS = {
  halal: ['halal'],
  vegan: ['vegan', 'plant-based', 'plant based'],
  gluten_free: ['gluten free', 'gluten-free', 'no gluten', 'coeliac', 'celiac'],
  dairy_free: ['dairy free', 'dairy-free', 'no dairy', 'lactose'],
}

const BEHAVIOUR_MAP = {
  rushed: { triggers: ['quick', 'fast', 'hurry', 'rush', 'no time', 'rushed'] },
  budget: { triggers: ['cheap', 'affordable', 'budget', 'low cost', 'inexpensive'] },
  health_focused: { triggers: ['healthy', 'light', 'low calorie', 'clean', 'nutritious'] },
  exploring: { triggers: [] },
}

function matchKeywords(text, keywordMap) {
  const lower = text.toLowerCase()
  const matches = []
  for (const [key, keywords] of Object.entries(keywordMap)) {
    for (const kw of keywords) {
      if (lower.includes(kw)) {
        matches.push(key)
        break
      }
    }
  }
  return matches
}

function classifyBehaviour(text) {
  const lower = text.toLowerCase()
  for (const [behaviour, config] of Object.entries(BEHAVIOUR_MAP)) {
    if (behaviour === 'exploring') continue
    for (const trigger of config.triggers) {
      if (lower.includes(trigger)) return behaviour
    }
  }
  return 'exploring'
}

export function extractIntent(text) {
  const categories = matchKeywords(text, CATEGORY_KEYWORDS)
  const preferences = matchKeywords(text, PREFERENCE_KEYWORDS)
  const modifiers = matchKeywords(text, MODIFIER_KEYWORDS)
  const dietary = matchKeywords(text, DIETARY_KEYWORDS)
  const behaviour = classifyBehaviour(text)
  return {
    category: categories[0] || null,
    preferences,
    modifiers,
    dietary,
    behaviour,
  }
}

// --- Filtering ---
function passesDietaryCheck(product, dietary) {
  for (const req of dietary) {
    if (req === 'vegan' && !product.dietary.includes('vegan')) return false
    if (req === 'gluten_free' && product.allergens.includes('gluten')) return false
    if (req === 'dairy_free' && product.allergens.includes('dairy')) return false
  }
  return true
}

export function filterProducts(products, intent) {
  let filtered = [...products]
  if (intent.category) {
    const catMatch = filtered.filter(p => p.category === intent.category)
    if (catMatch.length > 0) filtered = catMatch
  }
  if (intent.dietary && intent.dietary.length > 0) {
    filtered = filtered.filter(p => passesDietaryCheck(p, intent.dietary))
  }
  return filtered
}

// --- Ranking ---
const WEIGHTS = {
  intent_match: 0.30,
  dietary_match: 0.20,
  behaviour_match: 0.15,
  prep_speed_match: 0.10,
  popularity: 0.10,
  conversion: 0.10,
  margin: 0.05,
}

const BEHAVIOUR_TO_SIGNAL = {
  rushed: 'rushed',
  budget: 'budget',
  health_focused: 'healthy',
  exploring: 'light',
}

const MAX_PREP_TIME = 15

function calcIntentMatch(product, intent) {
  if (!intent.preferences || intent.preferences.length === 0) return 0.5
  let total = 0
  for (const pref of intent.preferences) {
    total += product.intent_signals[pref] ?? 0
  }
  return total / intent.preferences.length
}

function calcDietaryMatch(product, intent) {
  if (!intent.dietary || intent.dietary.length === 0) return 1.0
  for (const req of intent.dietary) {
    if (req === 'vegan' && !product.dietary.includes('vegan')) return 0
    if (req === 'gluten_free' && product.allergens.includes('gluten')) return 0
    if (req === 'dairy_free' && product.allergens.includes('dairy')) return 0
  }
  return 1.0
}

function calcBehaviourMatch(product, intent) {
  const key = BEHAVIOUR_TO_SIGNAL[intent.behaviour] ?? 'light'
  return product.intent_signals[key] ?? 0.5
}

function scoreProduct(product, intent) {
  const intentScore = calcIntentMatch(product, intent)
  const dietaryScore = calcDietaryMatch(product, intent)
  const behaviourScore = calcBehaviourMatch(product, intent)
  const prepScore = Math.max(0, 1 - product.prep_time_minutes / MAX_PREP_TIME)
  const popularity = product.popularity_score / 100
  const conversion = product.conversion_score / 100
  const margin = product.margin_score / 100

  return (
    WEIGHTS.intent_match * intentScore +
    WEIGHTS.dietary_match * dietaryScore +
    WEIGHTS.behaviour_match * behaviourScore +
    WEIGHTS.prep_speed_match * prepScore +
    WEIGHTS.popularity * popularity +
    WEIGHTS.conversion * conversion +
    WEIGHTS.margin * margin
  )
}

export function getTopRecommendations(products, intent) {
  const numOptions = { rushed: 1, budget: 2, health_focused: 2, exploring: 3 }
  const n = numOptions[intent.behaviour] ?? 3

  const scored = products.map(p => ({ product: p, score: scoreProduct(p, intent) }))

  if (intent.behaviour === 'budget') {
    scored.sort((a, b) => b.score - a.score || a.product.price - b.product.price)
  } else {
    scored.sort((a, b) => b.score - a.score)
  }

  return scored.slice(0, n).map(s => s.product)
}

// --- Upsell ---
export function getUpsell(recommended, allProducts, basketIds) {
  const productMap = new Map(allProducts.map(p => [p.id, p]))
  const candidates = []

  for (const pair of recommended.upsell_pairs) {
    if (basketIds.has(pair.product_id)) continue
    const product = productMap.get(pair.product_id)
    if (product) candidates.push(product)
  }

  if (candidates.length === 0) return null
  candidates.sort((a, b) => b.popularity_score - a.popularity_score)
  return candidates[0]
}

// --- Reason builder ---
export function buildReason(product, intent) {
  if (!intent) return ''
  const parts = []
  if (intent.preferences?.includes('light') && (product.intent_signals.light ?? 0) > 0.7)
    parts.push('light')
  if (intent.preferences?.includes('healthy') && (product.intent_signals.healthy ?? 0) > 0.7)
    parts.push('healthy')
  if (intent.preferences?.includes('filling') && (product.intent_signals.filling ?? 0) > 0.7)
    parts.push('filling')
  if (product.prep_time_minutes <= 5) parts.push('quick to prepare')
  if (product.popularity_score >= 80) parts.push('very popular')
  else if (product.popularity_score >= 70) parts.push('popular')
  if (product.price <= 4.0) parts.push('great value')
  if (parts.length === 0) parts.push('a great choice')
  const joined = parts.slice(0, 3).join(', ')
  return joined.charAt(0).toUpperCase() + joined.slice(1)
}

export function productToOut(product, intent = null) {
  return {
    id: product.id,
    name: product.name,
    store_type: product.store_type,
    price: product.price,
    tags: product.tags,
    dietary: product.dietary,
    calories_band: product.calories_band,
    prep_time_minutes: product.prep_time_minutes,
    reason: buildReason(product, intent),
  }
}

// --- Clarification ---
const CLARIFICATION_MAP = {
  lunch: 'Are you in a rush, or taking your time?',
  breakfast: 'Something light and quick, or a bigger meal to start the day?',
  snack: 'Sweet or savoury?',
  drink: 'Hot or cold?',
  meal: 'Are you in a rush, or taking your time?',
}

export function getClarification(intent) {
  return CLARIFICATION_MAP[intent] ?? null
}
