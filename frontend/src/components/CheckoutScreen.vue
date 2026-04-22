<template>
  <div class="animate-fade-in max-w-lg mx-auto text-center py-8">
    <!-- Simulated checkout stages -->
    <div v-if="phase === 'summary'">
      <h2 class="text-2xl font-semibold text-slate-100 mb-2">Order Summary</h2>
      <p class="text-slate-400 text-sm mb-6">Ready for pickup in ~{{ prepTime }} minutes</p>

      <div class="bg-slate-800/60 rounded-xl border border-slate-700/60 p-5 text-left mb-6">
        <div
          v-for="item in items"
          :key="item.id"
          class="flex items-center justify-between py-2 border-b border-slate-700/40 last:border-b-0"
        >
          <span class="text-sm text-slate-200">{{ item.name }} <span v-if="item.qty > 1" class="text-slate-500">x{{ item.qty }}</span></span>
          <span class="text-sm text-slate-300 font-medium">£{{ (item.price * item.qty).toFixed(2) }}</span>
        </div>
        <div class="mt-3 pt-3 border-t border-slate-700/60 flex justify-between">
          <span class="font-semibold text-slate-100">Total</span>
          <span class="font-bold text-fuchsia-400 text-lg">£{{ total.toFixed(2) }}</span>
        </div>
      </div>

      <button
        @click="startProcessing"
        class="w-full py-3 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-medium
               hover:from-cyan-400 hover:to-blue-500 transition-all duration-200 cursor-pointer"
      >
        Place Order (Simulated)
      </button>
      <button
        @click="$emit('back')"
        class="mt-3 text-sm text-slate-500 hover:text-slate-300 cursor-pointer transition-colors"
      >
        ← Back to shopping
      </button>
    </div>

    <!-- Processing animation -->
    <div v-else-if="phase === 'processing'" class="py-12">
      <div class="inline-block w-10 h-10 border-3 border-fuchsia-200 border-t-fuchsia-500 rounded-full animate-spin mb-4"></div>
      <p class="text-slate-300 font-medium">Processing your order...</p>
      <p class="text-slate-500 text-sm mt-1">This is a simulated checkout</p>
    </div>

    <!-- Confirmation -->
    <div v-else-if="phase === 'confirmed'" class="py-8">
      <div class="w-16 h-16 rounded-full bg-emerald-500/20 border-2 border-emerald-500/50 flex items-center justify-center mx-auto mb-4">
        <span class="text-3xl">✓</span>
      </div>
      <h2 class="text-2xl font-semibold text-slate-100 mb-2">Order Confirmed!</h2>
      <p class="text-slate-400 text-sm mb-1">Order #{{ orderId }}</p>
      <p class="text-slate-400 text-sm mb-6">Estimated pickup: {{ prepTime }} minutes</p>

      <div class="bg-slate-800/60 rounded-xl border border-emerald-500/20 p-4 mb-6 inline-block">
        <p class="text-sm text-slate-300">
          <span class="font-medium text-emerald-400">{{ items.length }} item{{ items.length > 1 ? 's' : '' }}</span>
          — £{{ total.toFixed(2) }}
        </p>
      </div>

      <div>
        <button
          @click="$emit('done')"
          class="px-8 py-3 rounded-lg bg-gradient-to-r from-fuchsia-600 to-purple-600 text-white font-medium
                 hover:from-fuchsia-500 hover:to-purple-500 transition-all duration-200 cursor-pointer"
        >
          Start New Order
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  items: Array,
})
defineEmits(['back', 'done'])

const phase = ref('summary')
const orderId = ref('')

const total = computed(() =>
  props.items.reduce((sum, item) => sum + item.price * item.qty, 0)
)

const prepTime = computed(() => {
  const maxPrep = Math.max(...props.items.map(i => i.prep_time_minutes || 0))
  return Math.max(maxPrep, 3)
})

function startProcessing() {
  phase.value = 'processing'
  orderId.value = 'STV-' + Math.random().toString(36).substring(2, 8).toUpperCase()
  setTimeout(() => {
    phase.value = 'confirmed'
  }, 2000)
}
</script>
