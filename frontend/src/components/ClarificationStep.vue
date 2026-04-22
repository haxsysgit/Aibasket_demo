<template>
  <div class="text-center animate-fade-in">
    <p class="text-lg text-slate-200 mb-6">{{ question }}</p>
    <div class="flex flex-wrap justify-center gap-3">
      <button
        v-for="option in options"
        :key="option.label"
        @click="$emit('answer', option)"
        class="px-6 py-2.5 rounded-full border border-slate-700 bg-slate-800/50 text-slate-200 text-sm font-medium
               hover:bg-fuchsia-500/10 hover:border-fuchsia-500/50 hover:text-fuchsia-300
               transition-all duration-200 cursor-pointer"
      >
        {{ option.label }}
      </button>
    </div>
    <button
      @click="$emit('skip')"
      class="mt-5 text-sm text-slate-500 hover:text-slate-300 underline cursor-pointer transition-colors"
    >
      Skip — just show me what you've got
    </button>
  </div>
</template>

<script setup>
defineProps({
  question: String,
  options: Array,
})
defineEmits(['answer', 'skip'])
</script>
