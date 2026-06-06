# Investment Report Agent Frontend

Next.js 16 frontend for the investment report agent.

## Run Locally

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`.

The frontend defaults to `http://localhost:8000/api/v1` for backend API calls. Override it for deployed environments:

```powershell
$env:NEXT_PUBLIC_API_URL = "https://your-backend.example.com/api/v1"
```

## Checks

```powershell
npm run lint
npm run build
npm run test:e2e:smoke
```

## Smoke E2E Coverage

`npm run test:e2e:smoke` verifies:

- Home page shows the core analysis entry.
- `/report` without `task` is explicitly labeled as Demo data.
- Invalid real task shows a real-report error instead of Demo fallback.
- Progress failure stays on the real-report error state.
- Reports, portfolio, archive, and settings pages render.

## Notes

- Use `http://localhost:3000` for Next dev server tests.
- `127.0.0.1:3000` may trigger Next dev origin restrictions in some local flows.
