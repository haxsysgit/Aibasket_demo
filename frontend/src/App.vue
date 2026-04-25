<script setup>
import { ref, computed, watch } from 'vue'
import { classifyIntent, getRecommendations, getUpsell, chat } from './api.js'
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

// AI state
const aiMessage = ref('')
const aiPrompts = ref({})
const aiLlmUsed = ref(false)
const showReasoning = ref(false)

// Multi-turn conversation
const conversationHistory = ref([])
const turnCount = ref(0)
const canFollowUp = ref(true)
const followUpText = ref('')

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
  // First turn — fresh conversation
  conversationHistory.value = []
  turnCount.value = 0
  canFollowUp.value = true
  await sendChat(text)
}

async function handleFollowUp() {
  const text = followUpText.value.trim()
  if (!text) return
  followUpText.value = ''
  await sendChat(text)
}

async function sendChat(text) {
  loading.value = true
  stage.value = 'loading'

  try {
    const data = await chat(text, storeType.value, basketIds.value, conversationHistory.value)

    // Update conversation history
    conversationHistory.value.push({ role: 'user', content: text })
    conversationHistory.value.push({ role: 'assistant', content: data.ai_message || data.clarification || '' })

    // Cap history at last 4 turns (8 messages)
    if (conversationHistory.value.length > 8) {
      conversationHistory.value = conversationHistory.value.slice(-8)
    }

    // Store AI state
    aiMessage.value = data.ai_message || ''
    aiPrompts.value = data.prompts || {}
    aiLlmUsed.value = data.llm_used || false
    turnCount.value = data.turn_count || 1
    canFollowUp.value = data.can_follow_up !== false

    // Store intent
    if (data.intent_used) {
      currentIntent.value = data.intent_used.category
      currentPrefs.value = data.intent_used.preferences || []
      currentMods.value = data.intent_used.modifiers || []
      currentDietary.value = data.intent_used.dietary || []
      currentBehaviour.value = data.intent_used.behaviour || 'exploring'
    }

    // Handle clarification — show as AI message with follow-up input (no chip stage)
    if (data.clarification) {
      recommendations.value = data.products || []
      aiMessage.value = data.clarification
      stage.value = 'results'
      return
    }

    // Handle recommendations
    recommendations.value = data.products || []

    // Handle upsell from chat response
    if (data.upsell) {
      upsellProducts.value = [data.upsell]
      upsellMessage.value = data.upsell_message || ''
    }

    stage.value = 'results'
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
  aiMessage.value = ''
  aiPrompts.value = {}
  aiLlmUsed.value = false
  showReasoning.value = false
  conversationHistory.value = []
  turnCount.value = 0
  canFollowUp.value = true
  followUpText.value = ''
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
        <div v-else-if="stage === 'results'" class="py-6 space-y-4">
          <!-- AI Message -->
          <div v-if="aiMessage" class="bg-slate-800/60 border border-slate-700 rounded-xl p-4 mb-2">
            <div class="flex items-start gap-3">
              <span class="text-lg mt-0.5">{{ aiLlmUsed ? '🤖' : '💡' }}</span>
              <div>
                <p class="text-slate-200 text-sm leading-relaxed">{{ aiMessage }}</p>
                <div class="flex items-center gap-3 mt-2">
                  <span v-if="aiLlmUsed" class="text-[10px] px-2 py-0.5 rounded-full bg-fuchsia-500/20 text-fuchsia-300 font-medium">GPT-4o-mini</span>
                  <span v-else class="text-[10px] px-2 py-0.5 rounded-full bg-slate-600/40 text-slate-400 font-medium">Deterministic</span>
                  <button
                    v-if="Object.keys(aiPrompts).length > 0"
                    @click="showReasoning = !showReasoning"
                    class="text-[10px] text-slate-500 hover:text-fuchsia-400 transition-colors cursor-pointer underline"
                  >
                    {{ showReasoning ? 'Hide' : 'Show' }} AI reasoning
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- AI Reasoning Panel -->
          <div v-if="showReasoning && Object.keys(aiPrompts).length > 0"
               class="bg-slate-900/80 border border-slate-700/50 rounded-xl p-4 text-xs font-mono space-y-4 overflow-x-auto">
            <h4 class="text-fuchsia-400 text-xs font-bold uppercase tracking-wider mb-2">Prompt Transparency</h4>

            <!-- Intent Extraction -->
            <div v-if="aiPrompts.intent_extraction" class="space-y-1">
              <p class="text-cyan-400 font-semibold">1. Intent Extraction</p>
              <p class="text-slate-500">System prompt:</p>
              <pre class="text-slate-400 whitespace-pre-wrap bg-slate-800/50 rounded p-2 max-h-32 overflow-y-auto">{{ aiPrompts.intent_extraction.system }}</pre>
              <p class="text-slate-500">User input:</p>
              <pre class="text-slate-300 bg-slate-800/50 rounded p-2">"{{ aiPrompts.intent_extraction.user }}"</pre>
              <p class="text-slate-500">Model output:</p>
              <pre class="text-green-400 bg-slate-800/50 rounded p-2">{{ JSON.stringify(aiPrompts.intent_extraction.model_output, null, 2) }}</pre>
            </div>

            <!-- Clarification -->
            <div v-if="aiPrompts.clarification" class="space-y-1">
              <p class="text-cyan-400 font-semibold">2. Contextual Clarification</p>
              <p class="text-slate-500">System prompt:</p>
              <pre class="text-slate-400 whitespace-pre-wrap bg-slate-800/50 rounded p-2 max-h-32 overflow-y-auto">{{ aiPrompts.clarification.system }}</pre>
              <p class="text-slate-500">Model output:</p>
              <pre class="text-green-400 bg-slate-800/50 rounded p-2">"{{ aiPrompts.clarification.model_output }}"</pre>
            </div>

            <!-- Response Generation -->
            <div v-if="aiPrompts.response_generation" class="space-y-1">
              <p class="text-cyan-400 font-semibold">{{ aiPrompts.clarification ? '3' : '2' }}. Response Generation</p>
              <p class="text-slate-500">System prompt:</p>
              <pre class="text-slate-400 whitespace-pre-wrap bg-slate-800/50 rounded p-2 max-h-32 overflow-y-auto">{{ aiPrompts.response_generation.system }}</pre>
              <p class="text-slate-500">Context sent to model:</p>
              <pre class="text-slate-300 whitespace-pre-wrap bg-slate-800/50 rounded p-2 max-h-40 overflow-y-auto">{{ aiPrompts.response_generation.user }}</pre>
              <p class="text-slate-500">Model output:</p>
              <pre class="text-green-400 whitespace-pre-wrap bg-slate-800/50 rounded p-2">"{{ aiPrompts.response_generation.model_output }}"</pre>
            </div>

            <!-- Decision flow -->
            <div class="border-t border-slate-700/50 pt-3 text-slate-500">
              <p class="font-semibold text-slate-400 mb-1">Decision flow:</p>
              <p>1. LLM extracts structured intent from free text → <span class="text-cyan-400">{{ aiLlmUsed ? 'GPT-4o-mini' : 'keyword fallback' }}</span></p>
              <p>2. Deterministic engine filters + ranks products → <span class="text-cyan-400">weighted scoring</span></p>
              <p>3. Deterministic engine selects upsell → <span class="text-cyan-400">curated pairs</span></p>
              <p>4. LLM phrases the response naturally → <span class="text-cyan-400">{{ aiLlmUsed ? 'GPT-4o-mini' : 'static template' }}</span></p>
            </div>
          </div>

          <ProductCards
            v-if="recommendations.length"
            :products="recommendations"
            @add="handleAddProduct"
            @restart="restart"
          />

          <!-- Follow-up input -->
          <div v-if="canFollowUp" class="mt-4">
            <div class="flex gap-2">
              <input
                v-model="followUpText"
                @keyup.enter="handleFollowUp"
                :placeholder="turnCount >= 4 ? 'Max turns reached — start fresh' : 'Refine, ask for alternatives, or change your mind...'"
                :disabled="turnCount >= 4"
                class="flex-1 px-4 py-2.5 rounded-lg border border-slate-700 bg-slate-800/60 text-slate-200 text-sm
                       placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-fuchsia-500/40
                       disabled:opacity-40 disabled:cursor-not-allowed"
              />
              <button
                @click="handleFollowUp"
                :disabled="!followUpText.trim() || turnCount >= 4"
                class="px-4 py-2.5 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-500 text-white text-sm font-medium
                       cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            </div>
            <div class="flex items-center justify-between mt-1.5">
              <p class="text-[10px] text-slate-600">
                Turn {{ turnCount }}/4 · Try "something cheaper", "make it vegan", or "actually, I want a drink"
              </p>
              <button
                @click="restart"
                class="text-[10px] text-slate-600 hover:text-fuchsia-400 transition-colors cursor-pointer underline"
              >
                Start fresh
              </button>
            </div>
          </div>
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
      <p class="text-xs text-slate-600">AI Basket Builder — Prototype Demo · Not a real shop · Hybrid: LLM understanding + deterministic decisions</p>
    </footer>
  </div>
</template>
