import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
<<<<<<< HEAD
  plugins: [react(), tailwindcss()],
  theme: {
    extend: {
      fontFamily: {
        inria: ['"Inria Sans"', 'sans-serif'],
      },
    },
  },
})
=======
  plugins: [react()],
})
>>>>>>> bb23d5235afa54507dbb3480bfb6baa723475251
