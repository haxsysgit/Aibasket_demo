<template>
  <div class="text-center animate-fade-in">
    <h2 class="text-2xl font-semibold text-slate-100 mb-2">What are you looking for?</h2>
    <p class="text-slate-400 mb-8 text-sm">Pick an option or describe what you want</p>

    <div class="flex flex-wrap justify-center gap-3 mb-8 max-w-2xl mx-auto">
      <button
        v-for="chip in activeChips"
        :key="chip.label"
        @click="$emit('select', chip)"
        class="px-5 py-2.5 rounded-full border border-slate-700 bg-slate-800/50 text-slate-200 text-sm font-medium
               hover:bg-fuchsia-500/10 hover:border-fuchsia-500/50 hover:text-fuchsia-300
               transition-all duration-200 cursor-pointer"
      >
        {{ chip.icon }} {{ chip.label }}
      </button>
    </div>

    <div class="max-w-md mx-auto flex gap-2">
      <input
        v-model="customText"
        @keyup.enter="submitCustom"
        type="text"
        :placeholder="placeholder"
        class="flex-1 px-4 py-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-slate-100 text-sm placeholder-slate-500
               focus:outline-none focus:ring-2 focus:ring-fuchsia-500/40 focus:border-fuchsia-500/40"
      />
      <button
        @click="submitCustom"
        :disabled="!customText.trim()"
        class="px-5 py-2.5 rounded-lg bg-gradient-to-r from-fuchsia-600 to-purple-600 text-white text-sm font-medium
               hover:from-fuchsia-500 hover:to-purple-500 disabled:opacity-40 disabled:cursor-not-allowed
               transition-all duration-200 cursor-pointer"
      >
        Go
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  storeType: { type: String, default: 'cafe' },
})
const emit = defineEmits(['select', 'custom'])
const customText = ref('')

const storeChips = {
  cafe: [
    { label: 'Light lunch', icon: '🥗', preferences: ['light'], intent: 'lunch' },
    { label: 'Something filling', icon: '🍔', preferences: ['filling'], intent: 'lunch' },
    { label: 'Quick bite', icon: '⚡', modifiers: ['quick'], intent: 'snack' },
    { label: 'Healthy option', icon: '💚', preferences: ['healthy'], intent: 'lunch' },
    { label: 'On a budget', icon: '💰', modifiers: ['cheap'], intent: 'lunch' },
    { label: 'Breakfast', icon: '🌅', preferences: [], intent: 'breakfast' },
    { label: 'Just a drink', icon: '☕', preferences: [], intent: 'drink' },
    { label: 'Something sweet', icon: '🍫', preferences: ['indulgent'], intent: 'snack' },
  ],
  pub: [
    { label: 'Pub grub', icon: '🍺', preferences: ['filling'], intent: 'lunch' },
    { label: 'Something light', icon: '🥗', preferences: ['light'], intent: 'lunch' },
    { label: 'Starters to share', icon: '🍗', preferences: ['indulgent'], intent: 'snack' },
    { label: 'A pint', icon: '🍻', preferences: [], intent: 'drink' },
    { label: 'Wine', icon: '🍷', preferences: ['light'], intent: 'drink' },
    { label: 'Something classic', icon: '🇬🇧', preferences: ['filling'], intent: 'lunch' },
    { label: 'Dessert', icon: '🍮', preferences: ['indulgent'], intent: 'snack' },
    { label: 'On a budget', icon: '💰', modifiers: ['cheap'], intent: 'lunch' },
  ],
  bakery: [
    { label: 'Fresh pastry', icon: '🥐', preferences: ['indulgent'], intent: 'breakfast' },
    { label: 'Bread to take home', icon: '🍞', preferences: ['filling'], intent: 'lunch' },
    { label: 'Something savoury', icon: '🥧', preferences: ['filling'], intent: 'lunch' },
    { label: 'Cake or sweet treat', icon: '🍰', preferences: ['indulgent'], intent: 'snack' },
    { label: 'Coffee & pastry', icon: '☕', preferences: [], intent: 'drink' },
    { label: 'Healthy option', icon: '💚', preferences: ['healthy'], intent: 'lunch' },
    { label: 'Quick grab', icon: '⚡', modifiers: ['quick'], intent: 'breakfast' },
    { label: 'Vegan', icon: '🌱', dietary: ['vegan'], intent: 'snack' },
  ],
  corner_shop: [
    { label: 'Meal deal', icon: '🥪', preferences: ['filling'], intent: 'lunch' },
    { label: 'Quick snack', icon: '⚡', modifiers: ['quick'], intent: 'snack' },
    { label: 'Something to drink', icon: '🥤', preferences: [], intent: 'drink' },
    { label: 'Breakfast on the go', icon: '🌅', preferences: [], intent: 'breakfast' },
    { label: 'Something healthy', icon: '💚', preferences: ['healthy'], intent: 'snack' },
    { label: 'On a budget', icon: '💰', modifiers: ['cheap'], intent: 'snack' },
    { label: 'Sweet treat', icon: '🍫', preferences: ['indulgent'], intent: 'snack' },
    { label: 'Energy boost', icon: '⚡', preferences: [], intent: 'drink' },
  ],
}

const placeholders = {
  cafe: 'e.g. "vegan lunch under £8"',
  pub: 'e.g. "pie and a pint"',
  bakery: 'e.g. "something with chocolate"',
  corner_shop: 'e.g. "cheap lunch deal"',
}

const activeChips = computed(() => storeChips[props.storeType] || storeChips.cafe)
const placeholder = computed(() => placeholders[props.storeType] || placeholders.cafe)

function submitCustom() {
  if (customText.value.trim()) {
    emit('custom', customText.value.trim())
    customText.value = ''
  }
}
</script>
