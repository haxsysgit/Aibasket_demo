<script setup>
import { ref, computed, watch } from 'vue'
import { classifyIntent, getRecommendations, getUpsell } from './api.js'
import IntentSelector from './components/IntentSelector.vue'
import ClarificationStep from './components/ClarificationStep.vue'
import ProductCards from './components/ProductCards.vue'
import UpsellPrompt from './components/UpsellPrompt.vue'
import BasketPanel from './components/BasketPanel.vue'
import CheckoutScreen from './components/CheckoutScreen.vue'

const stage = ref('intent')   // intent | clarifying | loading | results | upsell | checkout
const loading = ref(false)

// Store type
const storeType = ref('cafe')
const storeOptions = [
  { value: 'cafe', label: '☕ Café', name: "Amy's Café" },
  { value: 'pub', label: '🍺 Pub', name: 'The Red Lion' },
  { value: 'bakery', label: '🥐 Bakery', name: 'Golden Crust Bakery' },
  { value: 'corner_shop', label: '🏪 Corner Shop', name: 'QuickStop' },
]
const activeStore = computed(() => storeOptions.find(s => s.value === storeType.value))

watch(storeType, () => {
  restart()
  basket.value = []
})

// Current intent state
const currentIntent = ref(null)
const currentPrefs = ref([])
const currentMods = ref([])
const currentDietary = ref([])
const currentBehaviour = ref('exploring')

// Recommendations + upsell
const recommendations = ref([])
const clarification = ref(null)
const clarificationOptions = ref([])
const upsellProducts = ref([])
const upsellMessage = ref('')

// Basket
const basket = ref([])
const basketIds = computed(() => basket.value.map(i => i.id))

function addToBasket(product) {
  const existing = basket.value.find(i => i.id === product.id)
  if (existing) {
    existing.qty++
  } else {
    basket.value.push({ ...product, qty: 1 })
  }
}

function removeFromBasket(productId) {
  basket.value = basket.value.filter(i => i.id !== productId)
}

function clearBasket() {
  basket.value = []
}

async function handleChipSelect(chip) {
  currentIntent.value = chip.intent || null
  currentPrefs.value = chip.preferences || []
  currentMods.value = chip.modifiers || []
  currentDietary.value = chip.dietary || []
  currentBehaviour.value = chip.modifiers?.includes('cheap') ? 'budget'
    : chip.modifiers?.includes('quick') ? 'rushed'
    : chip.preferences?.includes('healthy') ? 'health_focused'
    : 'exploring'

  await fetchRecommendations()
}

async function handleCustomInput(text) {
  loading.value = true
  stage.value = 'loading'
  try {
    const intent = await classifyIntent(text, storeType.value)
    currentIntent.value = intent.category
    currentPrefs.value = intent.preferences
    currentMods.value = intent.modifiers
    currentDietary.value = intent.dietary
    currentBehaviour.value = intent.behaviour
    await fetchRecommendations()
  } catch {
    stage.value = 'intent'
  } finally {
    loading.value = false
  }
}

async function fetchRecommendations() {
  loading.value = true
  stage.value = 'loading'
  try {
    const data = await getRecommendations({
      intent: currentIntent.value,
      preferences: currentPrefs.value,
      modifiers: currentMods.value,
      dietary: currentDietary.value,
      behaviour: currentBehaviour.value,
      store_type: storeType.value,
    })
    recommendations.value = data.products || []

    if (data.clarification && !currentPrefs.value.length && !currentMods.value.length) {
      clarification.value = data.clarification
      clarificationOptions.value = buildClarificationOptions(data.clarification)
      stage.value = 'clarifying'
    } else {
      stage.value = 'results'
    }
  } catch {
    stage.value = 'intent'
  } finally {
    loading.value = false
  }
}

function buildClarificationOptions(question) {
  if (question.includes('rush')) {
    return [
      { label: '⚡ Quick', modifier: 'quick', behaviour: 'rushed' },
      { label: '🧘 No rush', modifier: null, behaviour: 'exploring' },
    ]
  }
  if (question.includes('light') || question.includes('bigger')) {
    return [
      { label: '🥗 Light and quick', preference: 'light', modifier: 'quick' },
      { label: '🍳 Big meal', preference: 'filling', modifier: null },
    ]
  }
  if (question.includes('Sweet') || question.includes('savoury')) {
    return [
      { label: '🍫 Sweet', preference: 'indulgent', modifier: null },
      { label: '🧀 Savoury', preference: 'filling', modifier: null },
    ]
  }
  if (question.includes('Hot') || question.includes('cold')) {
    return [
      { label: '☕ Hot', preference: 'light', modifier: null },
      { label: '🧊 Cold', preference: 'healthy', modifier: null },
    ]
  }
  return [
    { label: 'Show me options', modifier: null, behaviour: 'exploring' },
  ]
}

async function handleClarificationAnswer(option) {
  if (option.preference) currentPrefs.value.push(option.preference)
  if (option.modifier) currentMods.value.push(option.modifier)
  if (option.behaviour) currentBehaviour.value = option.behaviour
  await fetchRecommendations()
}

function handleClarificationSkip() {
  stage.value = 'results'
}

async function handleAddProduct(product) {
  addToBasket(product)
  try {
    const data = await getUpsell(product.id, basketIds.value, storeType.value)
    if (data.products && data.products.length > 0) {
      upsellProducts.value = data.products
      upsellMessage.value = data.message
      stage.value = 'upsell'
    } else {
      upsellProducts.value = []
    }
  } catch {
    // No upsell, that's fine
  }
}

function handleUpsellAdd(product) {
  addToBasket(product)
  upsellProducts.value = []
  stage.value = 'results'
}

function handleUpsellDismiss() {
  upsellProducts.value = []
  stage.value = 'results'
}

function goToCheckout() {
  stage.value = 'checkout'
}

function handleCheckoutDone() {
  basket.value = []
  restart()
}

function restart() {
  stage.value = 'intent'
  recommendations.value = []
  upsellProducts.value = []
  clarification.value = null
  currentIntent.value = null
  currentPrefs.value = []
  currentMods.value = []
  currentDietary.value = []
  currentBehaviour.value = 'exploring'
}
</script>

<template>
  <div class="min-h-screen bg-slate-950">
    <!-- Header -->
    <header class="bg-slate-900/80 border-b border-slate-800 px-6 py-4 backdrop-blur-sm sticky top-0 z-50">
      <div class="max-w-5xl mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h1 class="text-lg font-bold bg-gradient-to-r from-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
            AI Basket Builder
          </h1>
          <span class="text-xs text-slate-600 hidden sm:inline">by Strivonex</span>
        </div>

        <!-- Store selector -->
        <div class="flex items-center gap-3">
          <span class="text-xs text-slate-500 hidden sm:inline">{{ activeStore?.name }}</span>
          <select
            v-model="storeType"
            class="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/60 text-slate-200 text-sm
                   focus:outline-none focus:ring-2 focus:ring-fuchsia-500/40 cursor-pointer appearance-none
                   pr-8 bg-[url('data:image/svg+xml;charset=UTF-8,%3csvg%20xmlns%3d%22http%3a//www.w3.org/2000/svg%22%20width%3d%2212%22%20height%3d%2212%22%20viewBox%3d%220%200%2012%2012%22%3e%3cpath%20fill%3d%22%2394a3b8%22%20d%3d%22M2%204l4%204%204-4%22/%3e%3c/svg%3e')] bg-[right_8px_center] bg-no-repeat"
          >
            <option v-for="store in storeOptions" :key="store.value" :value="store.value">
              {{ store.label }}
            </option>
          </select>
        </div>
      </div>
    </header>

    <div class="max-w-5xl mx-auto px-4 py-8 flex gap-6">
      <!-- Main content -->
      <div class="flex-1 min-w-0">
        <!-- Loading -->
        <div v-if="stage === 'loading'" class="text-center py-16">
          <div class="inline-block w-8 h-8 border-3 border-fuchsia-900 border-t-fuchsia-400 rounded-full animate-spin"></div>
          <p class="mt-3 text-sm text-slate-500">Finding the best options...</p>
        </div>

        <!-- Intent selection -->
        <div v-else-if="stage === 'intent'" class="py-12">
          <IntentSelector
            :store-type="storeType"
            @select="handleChipSelect"
            @custom="handleCustomInput"
          />
        </div>

        <!-- Clarification -->
        <div v-else-if="stage === 'clarifying'" class="py-12">
          <ClarificationStep
            :question="clarification"
            :options="clarificationOptions"
            @answer="handleClarificationAnswer"
            @skip="handleClarificationSkip"
          />
        </div>

        <!-- Results -->
        <div v-else-if="stage === 'results'" class="py-6">
          <ProductCards
            :products="recommendations"
            @add="handleAddProduct"
            @restart="restart"
          />
        </div>

        <!-- Upsell -->
        <div v-else-if="stage === 'upsell'" class="py-6 space-y-6">
          <ProductCards
            :products="recommendations"
            @add="handleAddProduct"
            @restart="restart"
          />
          <UpsellPrompt
            :products="upsellProducts"
            :message="upsellMessage"
            @add="handleUpsellAdd"
            @dismiss="handleUpsellDismiss"
          />
        </div>

        <!-- Checkout -->
        <div v-else-if="stage === 'checkout'">
          <CheckoutScreen
            :items="basket"
            @back="stage = 'results'"
            @done="handleCheckoutDone"
          />
        </div>
      </div>

      <!-- Basket sidebar -->
      <div class="w-72 shrink-0 hidden md:block">
        <div class="sticky top-24">
          <BasketPanel
            :items="basket"
            @remove="removeFromBasket"
            @clear="clearBasket"
            @checkout="goToCheckout"
          />
        </div>
      </div>
    </div>

    <!-- Mobile basket (bottom bar) -->
    <div v-if="basket.length > 0 && stage !== 'checkout'" class="md:hidden fixed bottom-0 inset-x-0 bg-slate-900/95 border-t border-slate-800 px-4 py-3 flex items-center justify-between backdrop-blur-sm">
      <div>
        <span class="text-sm font-medium text-slate-300">🧺 {{ basket.length }} item{{ basket.length > 1 ? 's' : '' }}</span>
        <span class="text-lg font-bold text-fuchsia-400 ml-2">£{{ basket.reduce((s, i) => s + i.price * i.qty, 0).toFixed(2) }}</span>
      </div>
      <button
        @click="goToCheckout"
        class="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium cursor-pointer"
      >
        Checkout
      </button>
    </div>

    <!-- Footer -->
    <footer class="border-t border-slate-800 mt-16 py-6 text-center">
      <p class="text-xs text-slate-600">AI Basket Builder — Prototype Demo · Not a real shop · Logic is deterministic, not LLM</p>
    </footer>
  </div>
</template>
