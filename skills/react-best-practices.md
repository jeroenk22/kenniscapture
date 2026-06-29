# React Best Practices — Kenniscapture Chatbot

## Tooling
- **Framework:** React 19.2.7 + Vite 8.1.0 + TypeScript 6.0.3
- **Stijl:** Tailwind CSS 4.3.1 (CSS-first, geen config nodig)
- **Linter:** Biome 2.5.1
- **Tests:** Vitest 4.1.9 + Testing Library (drempel ≥ 80%)

## Componenten
- Één component per bestand
- Props altijd expliciet getypeerd als `interface`
- Nooit `any` gebruiken

## State management
- `useState` voor lokale UI state
- `useRef` voor DOM-referenties (scroll, focus)
- Geen externe state library nodig voor dit project

## Tailwind v4 imports
```css
/* src/styles/index.css */
@import "tailwindcss";
```
Geen `tailwind.config.js` nodig.

## Pre-PR checklist
```bash
cd chatbot_ui
pnpm biome check .
pnpm test:coverage
pnpm typecheck
```
