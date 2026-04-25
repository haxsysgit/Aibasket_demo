import {
  loadProducts, filterByStore, extractIntent, filterProducts,
  getTopRecommendations, getUpsell as getUpsellLocal, productToOut,
  getClarification, buildReason,
} from './engine.js'

const BASE = '/api'

// Auto-detect backend availability once
let _backendAvailable = null

async function hasBackend() {
  if (_backendAvailable !== null) return _backendAvailable
  try {
    const res = await fetch(`${BASE}/classify-intent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'ping', store_type: 'cafe' }),
      signal: AbortSignal.timeout(2000),
    })
    _backendAvailable = res.ok
  } catch {
    _backendAvailable = false
  }
  if (!_backendAvailable) console.info('[api] No backend detected — using client-side engine')
  return _backendAvailable
}

// --- Fetch helpers (backend) ---

async function postJson(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

// --- Client-side fallback implementations ---

function localClassifyIntent(text) {
  const intent = extractIntent(text)
  return {
    category: intent.category,
    preferences: intent.preferences,
    modifiers: intent.modifiers,
    dietary: intent.dietary,
    behaviour: intent.behaviour,
  }
}

function localRecommend({ intent, preferences, modifiers, dietary, behaviour, store_type }) {
  const products = filterByStore(loadProducts(), store_type)
  const intentObj = { category: intent, preferences, modifiers, dietary, behaviour }
  const clarification = (!preferences.length && !modifiers.length && intent)
    ? getClarification(intent) : null
  const filtered = filterProducts(products, intentObj)
  const recs = filtered.length ? getTopRecommendations(filtered, intentObj) : []
  return {
    products: recs.map(p => productToOut(p, intentObj)),
    clarification: clarification && (!preferences.length && !modifiers.length) ? clarification : null,
  }
}

function localUpsell(productId, basketIds, storeType) {
  const products = filterByStore(loadProducts(), storeType)
  const productMap = new Map(products.map(p => [p.id, p]))
  const selected = productMap.get(productId)
  if (!selected) return { products: [], message: '' }
  const upsell = getUpsellLocal(selected, products, new Set(basketIds))
  if (!upsell) return { products: [], message: '' }
  return {
    products: [productToOut(upsell)],
    message: `Most people pair this with a ${upsell.name}`,
  }
}

const MAX_TURNS = 4

function localChat(message, storeType, basketIds, history = []) {
  const intent = extractIntent(message)
  const products = filterByStore(loadProducts(), storeType)
  const turnCount = history.filter(m => m.role === 'user').length + 1
  const canFollowUp = turnCount < MAX_TURNS

  // Clarification check — first turn only
  if (!intent.preferences.length && !intent.modifiers.length && !intent.dietary.length && intent.category && turnCount === 1) {
    const clarification = getClarification(intent.category)
    if (clarification) {
      const filtered = filterProducts(products, intent)
      const recs = filtered.length ? getTopRecommendations(filtered, intent) : []
      return {
        products: recs.map(p => productToOut(p, intent)),
        ai_message: '',
        clarification,
        upsell: null,
        upsell_message: '',
        intent_used: intent,
        llm_used: false,
        prompts: {},
        can_follow_up: true,
        turn_count: turnCount,
      }
    }
  }

  const filtered = filterProducts(products, intent)
  const recs = filtered.length ? getTopRecommendations(filtered, intent) : []
  const outs = recs.map(p => productToOut(p, intent))

  // Upsell
  let upsell = null, upsellMsg = ''
  if (recs.length > 0) {
    const upsellProduct = getUpsellLocal(recs[0], products, new Set(basketIds))
    if (upsellProduct) {
      upsell = productToOut(upsellProduct)
      upsellMsg = `Most people pair this with a ${upsellProduct.name}`
    }
  }

  // Static message
  const names = outs.map(p => p.name)
  let aiMsg
  if (names.length === 0) {
    aiMsg = "I couldn't find an exact match. Could you tell me more about what you're looking for?"
  } else if (names.length === 1) {
    aiMsg = `I'd recommend the ${names[0]} — it's a great fit for what you described.`
  } else {
    aiMsg = `Based on what you're looking for, I'd suggest the ${names.slice(0, -1).join(', ')} or the ${names[names.length - 1]}.`
  }

  return {
    products: outs,
    ai_message: aiMsg,
    clarification: null,
    upsell,
    upsell_message: upsellMsg,
    intent_used: intent,
    llm_used: false,
    prompts: {},
    can_follow_up: canFollowUp,
    turn_count: turnCount,
  }
}

// --- Exported API (auto-detect backend vs client-side) ---

export async function classifyIntent(text, storeType = 'cafe') {
  if (await hasBackend()) {
    return postJson('/classify-intent', { text, store_type: storeType })
  }
  return localClassifyIntent(text)
}

export async function getRecommendations({ intent, preferences, modifiers, dietary, behaviour, store_type }) {
  if (await hasBackend()) {
    return postJson('/recommend', { intent, preferences, modifiers, dietary, behaviour, store_type })
  }
  return localRecommend({ intent, preferences, modifiers, dietary, behaviour, store_type })
}

export async function getUpsell(productId, basketIds, storeType = 'cafe') {
  if (await hasBackend()) {
    return postJson('/upsell', { product_id: productId, basket_ids: basketIds, store_type: storeType })
  }
  return localUpsell(productId, basketIds, storeType)
}

export async function chat(message, storeType = 'cafe', basketIds = [], history = []) {
  if (await hasBackend()) {
    return postJson('/chat', { message, store_type: storeType, basket_ids: basketIds, history })
  }
  return localChat(message, storeType, basketIds, history)
}
