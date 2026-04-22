const BASE = '/api'

export async function classifyIntent(text, storeType = 'cafe') {
  const res = await fetch(`${BASE}/classify-intent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, store_type: storeType }),
  })
  return res.json()
}

export async function getRecommendations({ intent, preferences, modifiers, dietary, behaviour, store_type }) {
  const res = await fetch(`${BASE}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intent, preferences, modifiers, dietary, behaviour, store_type }),
  })
  return res.json()
}

export async function getUpsell(productId, basketIds, storeType = 'cafe') {
  const res = await fetch(`${BASE}/upsell`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId, basket_ids: basketIds, store_type: storeType }),
  })
  return res.json()
}
