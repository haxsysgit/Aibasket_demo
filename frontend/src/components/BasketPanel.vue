<template>
  <div class="bg-slate-800/60 rounded-xl border border-slate-700/60 p-5">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-slate-100 flex items-center gap-2">
        <span class="text-lg">🧺</span> Your Basket
      </h3>
      <button
        v-if="items.length > 0"
        @click="$emit('clear')"
        class="text-xs text-slate-500 hover:text-red-400 cursor-pointer transition-colors"
      >
        Clear all
      </button>
    </div>

    <div v-if="items.length === 0" class="text-sm text-slate-500 italic py-4 text-center">
      Nothing here yet
    </div>

    <div v-else>
      <div
        v-for="item in items"
        :key="item.id"
        class="flex items-center justify-between py-2.5 border-b border-slate-700/40 last:border-b-0"
      >
        <div class="flex-1 min-w-0">
          <span class="text-sm font-medium text-slate-200 truncate block">{{ item.name }}</span>
          <span v-if="item.qty > 1" class="text-xs text-slate-500">x{{ item.qty }}</span>
        </div>
        <div class="flex items-center gap-2 ml-3">
          <span class="text-sm font-medium text-slate-300">£{{ (item.price * item.qty).toFixed(2) }}</span>
          <button
            @click="$emit('remove', item.id)"
            class="text-slate-600 hover:text-red-400 transition-colors text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>
      </div>

      <div class="mt-4 pt-3 border-t border-slate-700/60 flex items-center justify-between">
        <span class="text-sm font-semibold text-slate-200">Total</span>
        <span class="text-lg font-bold text-fuchsia-400">£{{ total.toFixed(2) }}</span>
      </div>

      <button
        @click="$emit('checkout')"
        class="w-full mt-4 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium
               hover:from-cyan-400 hover:to-blue-500 transition-all duration-200 cursor-pointer"
      >
        Checkout →
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: Array,
})
defineEmits(['remove', 'clear', 'checkout'])

const total = computed(() =>
  props.items.reduce((sum, item) => sum + item.price * item.qty, 0)
)
</script>
