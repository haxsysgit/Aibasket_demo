<template>
  <div
    v-if="products.length > 0"
    class="bg-gradient-to-r from-fuchsia-900/20 to-purple-900/20 border border-fuchsia-500/20 rounded-xl p-5 text-center animate-fade-in"
  >
    <p class="text-sm text-fuchsia-300 mb-4 font-medium">✨ {{ message }}</p>

    <div class="flex justify-center gap-3 flex-wrap">
      <div
        v-for="product in products"
        :key="product.id"
        class="bg-slate-800/60 rounded-lg border border-slate-700/60 p-4 max-w-xs"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="font-medium text-slate-100 text-sm">{{ product.name }}</span>
          <span class="text-fuchsia-400 font-bold text-sm ml-2">£{{ product.price.toFixed(2) }}</span>
        </div>
        <button
          @click="$emit('add', product)"
          class="w-full py-2 rounded-lg bg-gradient-to-r from-fuchsia-600 to-purple-600 text-white text-sm font-medium
                 hover:from-fuchsia-500 hover:to-purple-500 transition-all duration-200 cursor-pointer"
        >
          Add to basket
        </button>
      </div>
    </div>

    <button
      @click="$emit('dismiss')"
      class="mt-3 text-xs text-slate-500 hover:text-slate-300 cursor-pointer transition-colors"
    >
      No thanks
    </button>
  </div>
</template>

<script setup>
defineProps({
  products: Array,
  message: String,
})
defineEmits(['add', 'dismiss'])
</script>
