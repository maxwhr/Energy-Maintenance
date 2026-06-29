import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import '@/styles/tailwind.css'
import '@/styles/global.css'
import { TEXT } from '@/constants/text'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

document.title = TEXT.appTitle
app.mount('#app')
