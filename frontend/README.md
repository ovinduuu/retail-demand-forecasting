# Retail Demand Forecast — frontend

An interactive demo: pick a store/item, see its recent sales and the
model's one-step-ahead forecast on a chart. Calls the serving API in
`../src/retail_demand/serving/app.py` (`/series`, `/history/{store}/{item}`,
`/forecast/{store}/{item}`).

## Local development

The backend needs to be running somewhere reachable — either the real
deployed Cloud Run service (once `../infra/terraform` is applied), or a
local instance for development:

```bash
# from the repo root, with a trained model at artifacts/lightgbm_model.txt
# and a local sample CSV (see ../data/README.md for how to make one) —
# LOCAL_DATA_CSV avoids needing real BigQuery/GCP credentials for local dev
MODEL_PATH=artifacts/lightgbm_model.txt LOCAL_DATA_CSV=path/to/history.csv \
  uv run uvicorn retail_demand.serving.app:app --port 8080
```

Then, in this directory:

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL defaults to localhost:8080
npm install
npm run dev
```

Open http://localhost:3000.

If the backend isn't reachable, the page shows a clear "Backend not
reachable" message instead of failing silently — that's expected until
either the local backend above is running or `NEXT_PUBLIC_API_BASE_URL`
points at a real deployment.

## Deploying to Vercel

1. Push this repo to GitHub (already done — see the root README).
2. On [vercel.com](https://vercel.com), "Add New Project" → import this
   repo → set **Root Directory** to `frontend`.
3. Add an environment variable: `NEXT_PUBLIC_API_BASE_URL` = the deployed
   serving API's Cloud Run URL (Terraform output `serving_url` once
   applied with `serving_image_uri` set — see `../infra/terraform/README.md`).
4. Deploy. Vercel auto-detects Next.js — no build config needed.

Once the frontend has a real Vercel URL, tighten the backend's CORS policy
by re-applying Terraform with `-var="frontend_origin=https://your-app.vercel.app"`
instead of the default `*`.

## Stack

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4. The chart in
`components/ForecastChart.tsx` is hand-built SVG (no charting library) —
axes, gridlines, hover crosshair + tooltip, a legend, and a table-view
toggle for accessibility.
