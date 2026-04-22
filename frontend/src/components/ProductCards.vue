<template>
  <div class="animate-fade-in">
    <h3 class="text-lg font-semibold text-slate-100 mb-1 text-center">Here's what I'd suggest</h3>
    <p class="text-sm text-slate-500 mb-6 text-center">Based on what you told me</p>

    <div v-if="products.length === 0" class="text-center py-8">
      <p class="text-slate-400">No products match your criteria. Try something different?</p>
    </div>

    <div v-else class="grid gap-4" :class="products.length === 1 ? 'max-w-sm mx-auto' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'">
      <div
        v-for="product in products"
        :key="product.id"
        class="bg-slate-800/60 rounded-xl border border-slate-700/60 p-5
               hover:border-fuchsia-500/30 hover:bg-slate-800/80 transition-all duration-200"
      >
        <div class="flex items-start justify-between mb-3">
          <h4 class="font-semibold text-slate-100">{{ product.name }}</h4>
          <span class="text-fuchsia-400 font-bold text-lg whitespace-nowrap ml-3">£{{ product.price.toFixed(2) }}</span>
        </div>

        <div class="flex flex-wrap gap-1.5 mb-3">
          <span
            v-for="tag in product.tags.slice(0, 4)"
            :key="tag"
            class="px-2 py-0.5 text-xs rounded-full bg-slate-700/60 text-slate-400"
          >
            {{ tag }}
          </span>
          <span
            v-for="d in product.dietary"
            :key="d"
            class="px-2 py-0.5 text-xs rounded-full bg-emerald-500/10 text-emerald-400"
          >
            {{ d }}
          </span>
        </div>

        <p v-if="product.reason" class="text-sm text-slate-400 mb-4 italic">
          {{ product.reason }}
        </p>

        <div class="flex items-center justify-between text-xs text-slate-500 mb-4">
          <span>{{ product.calories_band }} cal</span>
          <span v-if="product.prep_time_minutes > 0">{{ product.prep_time_minutes }} min prep</span>
          <span v-else>Ready now</span>
        </div>

        <button
          @click="$emit('add', product)"
          class="w-full py-2.5 rounded-lg bg-gradient-to-r from-fuchsia-600 to-purple-600 text-white text-sm font-medium
                 hover:from-fuchsia-500 hover:to-purple-500 transition-all duration-200 cursor-pointer"
        >
          Add to basket
        </button>
      </div>
    </div>

    <div class="text-center mt-6">
      <button
        @click="$emit('restart')"
        class="text-sm text-slate-500 hover:text-slate-300 underline cursor-pointer transition-colors"
      >
        Start over
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  products: Array,
})
defineEmits(['add', 'restart'])
</script>
